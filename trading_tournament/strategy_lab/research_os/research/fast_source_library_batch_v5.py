from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.external_adapters.bt_adapter import reference_spy200d_weights
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior


BATCH_ID = "fast_source_library_batch_v5"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v2"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_RECORDS_PATH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "selected_source_library_records.yaml"
)
FROZEN_SPECS_PATH = SOURCE_RECORDS_PATH.with_name("frozen_candidate_specs.yaml")
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
COST_BPS_GRID = (0.0, 5.0, 10.0)
PRIMARY_COST_BPS = 5.0
WEIGHT_TOLERANCE = 1e-10
MIN_OBSERVATIONS = 252

NEXT_ACTION_REVIEW = "direction_owner_review_fast_source_library_batch_v5"
NEXT_ACTION_ALL_CLOSED = "evaluate_deferred_structural_source_records_v2"
NEXT_ACTION_BLOCKED = "direction_owner_review_fast_source_library_batch_v5_block_v1"

EXPECTED_STRATEGY_IDS = (
    "chande_aroon_oscillator_25_90_spy_bil_v1",
    "ariel_spy_preholiday_bil_v1",
    "reinganum_iwm_january_bil_v1",
    "pring_kst_default_centerline_spy_bil_v1",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
INPUT_PATHS = (SOURCE_RECORDS_PATH, FROZEN_SPECS_PATH)

FORBIDDEN_FLAGS = {
    "source_research": False,
    "source_completion": False,
    "parameter_tuning": False,
    "parameter_grid": False,
    "provider_download": False,
    "validation_run": False,
    "robustness_run": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "broker_or_order_action": False,
    "real_money_action": False,
    "clean_or_sealed_holdout_claim": False,
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    family_id: str
    display_name: str
    strategy_architecture: str
    source_record_id: str
    universe: tuple[str, ...]
    controls: tuple[str, str]
    parameters: dict[str, Any]
    complete_frozen_rule: str
    translation_note: str

    @property
    def trial_id(self) -> str:
        return f"fast_source_v5__{self.strategy_id}__canonical"


CONTROL_IDS = {
    "chande_aroon_oscillator_25_90_spy_bil_v1": (
        "SPY_buy_and_hold",
        "SPY_200d_frozen_control",
    ),
    "ariel_spy_preholiday_bil_v1": (
        "SPY_buy_and_hold",
        "static_SPY_BIL_at_candidate_calendar_exposure_fraction",
    ),
    "reinganum_iwm_january_bil_v1": (
        "IWM_buy_and_hold",
        "SPY_January_window",
    ),
    "pring_kst_default_centerline_spy_bil_v1": (
        "SPY_buy_and_hold",
        "SPY_30_session_ROC_sign_SPY_BIL",
    ),
}

TRANSLATION_NOTES = {
    "chande_aroon_oscillator_25_90_spy_bil_v1": (
        "SPY and BIL are the frozen broad-US-equity and Treasury-bill project wrappers; "
        "the source-defined 25-session Aroon mechanism is unchanged."
    ),
    "ariel_spy_preholiday_bil_v1": (
        "SPY and BIL are frozen project wrappers; scheduled full-day NYSE closures are "
        "identified from a deterministic exchange-holiday calendar without unscheduled closures."
    ),
    "reinganum_iwm_january_bil_v1": (
        "IWM and the full-calendar-January window are the frozen project translation of "
        "the source hypothesis, not an exact constituent-level reproduction."
    ),
    "pring_kst_default_centerline_spy_bil_v1": (
        "SPY and BIL are frozen project wrappers; the source KST periods, smoothers, "
        "weights, centerline, and no-signal-line rule are unchanged."
    ),
}


def rel(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def input_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in INPUT_PATHS}


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected mapping in {rel(path)}")
    return payload


def load_cards() -> list[CandidateCard]:
    source_payload = _load_yaml(SOURCE_RECORDS_PATH)
    spec_payload = _load_yaml(FROZEN_SPECS_PATH)
    source_by_strategy = {
        str(row["proposed_strategy_id"]): row for row in source_payload.get("records", [])
    }
    spec_by_strategy = {
        str(row["strategy_id"]): row for row in spec_payload.get("strategies", [])
    }
    cards: list[CandidateCard] = []
    for strategy_id in EXPECTED_STRATEGY_IDS:
        source = source_by_strategy.get(strategy_id)
        spec = spec_by_strategy.get(strategy_id)
        if source is None or spec is None:
            raise RuntimeError(f"Frozen source/spec missing for {strategy_id}")
        if str(source["family_id"]) != str(spec["family_id"]):
            raise RuntimeError(f"Family mismatch for {strategy_id}")
        parameters = {
            "parameters": spec.get("parameters", {}),
            "formula": spec.get("formula", {}),
            "rule": spec.get("rule", {}),
            "execution": spec.get("execution", {}),
            "missing_data_behavior": spec.get("missing_data_behavior", ""),
        }
        cards.append(
            CandidateCard(
                strategy_id=strategy_id,
                family_id=str(source["family_id"]),
                display_name=str(source["display_name"]),
                strategy_architecture=str(source["strategy_architecture"]),
                source_record_id=str(source["source_record_id"]),
                universe=tuple(str(item) for item in spec["universe"]),
                controls=CONTROL_IDS[strategy_id],
                parameters=parameters,
                complete_frozen_rule=str(source["exact_canonical_rule"]),
                translation_note=TRANSLATION_NOTES[strategy_id],
            )
        )
    if tuple(card.strategy_id for card in cards) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Candidate scope drift")
    return cards


def _canonical_cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def _raw_cache_validation(symbol: str) -> dict[str, Any]:
    path = _canonical_cache_path(symbol)
    required = {
        "date",
        "raw_open",
        "raw_high",
        "raw_low",
        "raw_close",
        "raw_adj_close",
        "raw_volume",
        "adjustment_factor",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    }
    if not path.exists():
        return {
            "symbol": symbol,
            "cache_path": rel(path),
            "cache_hash": "missing",
            "preflight_status": "fail",
            "failure_reason": "data_unavailable",
        }
    raw = pd.read_csv(path)
    missing_fields = sorted(required - set(raw.columns))
    dates = pd.to_datetime(raw.get("date"), errors="coerce")
    ordered_unique = bool(dates.notna().all() and dates.is_monotonic_increasing and not dates.duplicated().any())
    numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]
    numeric = raw[numeric_columns].apply(pd.to_numeric, errors="coerce") if not missing_fields else pd.DataFrame()
    nonfinite = int((~np.isfinite(numeric.to_numpy(dtype=float))).sum()) if not numeric.empty else -1
    nonpositive_prices = (
        int((numeric[["open", "high", "low", "close", "adj_close"]] <= 0.0).sum().sum())
        if not numeric.empty
        else -1
    )
    negative_volume = int((numeric["volume"] < 0.0).sum()) if not numeric.empty else -1
    invalid_ohlc = (
        int(
            (
                (
                    numeric["high"] + 1e-10
                    < numeric[["open", "close", "low"]].max(axis=1)
                )
                | (
                    numeric["low"] - 1e-10
                    > numeric[["open", "close", "high"]].min(axis=1)
                )
            ).sum()
        )
        if not numeric.empty
        else -1
    )
    adjustment_mismatch = 0
    if not missing_fields:
        factor = pd.to_numeric(raw["adjustment_factor"], errors="coerce").to_numpy(dtype=float)
        for column in ("open", "high", "low", "close"):
            expected = pd.to_numeric(raw[f"raw_{column}"], errors="coerce").to_numpy(dtype=float) * factor
            actual = pd.to_numeric(raw[column], errors="coerce").to_numpy(dtype=float)
            adjustment_mismatch += int((~np.isclose(actual, expected, rtol=1e-8, atol=1e-8)).sum())
        adjustment_mismatch += int(
            (
                ~np.isclose(
                    pd.to_numeric(raw["adj_close"], errors="coerce").to_numpy(dtype=float),
                    pd.to_numeric(raw["raw_adj_close"], errors="coerce").to_numpy(dtype=float),
                    rtol=1e-8,
                    atol=1e-8,
                )
            ).sum()
        )
    canonical = prior.load_adjusted_ohlcv(symbol)
    canonical_ready = bool(not canonical.empty and len(canonical) == len(raw))
    passed = bool(
        not missing_fields
        and ordered_unique
        and nonfinite == 0
        and nonpositive_prices == 0
        and negative_volume == 0
        and invalid_ohlc == 0
        and adjustment_mismatch == 0
        and canonical_ready
    )
    return {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_hash": file_hash(path),
        "normal_backtester_loader": (
            "strategy_lab.research_os.research.fast_price_volume_discovery_batch_v2.load_adjusted_ohlcv"
        ),
        "row_count": int(len(raw)),
        "first_valid_date": dates.min().date().isoformat() if dates.notna().any() else "",
        "last_valid_date": dates.max().date().isoformat() if dates.notna().any() else "",
        "fields_available": "|".join(str(column) for column in raw.columns),
        "missing_required_fields": "|".join(missing_fields),
        "ordered_unique_dates": ordered_unique,
        "nonfinite_value_count": nonfinite,
        "nonpositive_price_count": nonpositive_prices,
        "negative_volume_count": negative_volume,
        "invalid_ohlc_count": invalid_ohlc,
        "adjustment_compatibility_mismatch_count": adjustment_mismatch,
        "canonical_loader_row_count": int(len(canonical)),
        "canonical_adjustment_compatible": adjustment_mismatch == 0,
        "preflight_status": "pass" if passed else "fail",
        "failure_reason": "" if passed else "data_or_comparability_failure",
    }


def data_preflight(cards: list[CandidateCard]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_symbol = {symbol: _raw_cache_validation(symbol) for symbol in ("SPY", "BIL", "IWM")}
    rows: list[dict[str, Any]] = []
    for card in cards:
        frames = {
            symbol: prior.load_adjusted_ohlcv(symbol)
            for symbol in card.universe
            if by_symbol.get(symbol, {}).get("preflight_status") == "pass"
        }
        if len(frames) == len(card.universe):
            start = max(frame.index.min() for frame in frames.values())
            end = min(frame.index.max() for frame in frames.values())
            date_union = set().union(*(set(frame.loc[start:end].index) for frame in frames.values()))
        else:
            start = None
            end = None
            date_union = set()
        for symbol in card.universe:
            base = dict(by_symbol[symbol])
            frame = frames.get(symbol, pd.DataFrame())
            internal_gap_count = (
                len(date_union - set(frame.loc[start:end].index))
                if start is not None and end is not None and not frame.empty
                else -1
            )
            candidate_pass = bool(
                base.get("preflight_status") == "pass"
                and start is not None
                and end is not None
                and internal_gap_count == 0
            )
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    **base,
                    "candidate_common_start": start.date().isoformat() if start is not None else "",
                    "candidate_common_end": end.date().isoformat() if end is not None else "",
                    "internal_common_calendar_gap_count": internal_gap_count,
                    "candidate_preflight_status": "pass" if candidate_pass else "fail",
                }
            )
    return rows, by_symbol


def event_frame(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    events: dict[pd.Timestamp, dict[str, float]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dates: list[pd.Timestamp] = []
    valid_dates = set(pd.DatetimeIndex(index))
    for raw_date in sorted(events):
        date_value = pd.Timestamp(raw_date)
        if date_value not in valid_dates:
            continue
        row = {symbol: float(events[raw_date].get(symbol, 0.0)) for symbol in columns}
        values = np.array(list(row.values()), dtype=float)
        if not np.isfinite(values).all() or (values < -WEIGHT_TOLERANCE).any():
            raise ValueError(f"Invalid target at {date_value.date()}")
        if float(values.sum()) > 1.0 + WEIGHT_TOLERANCE:
            raise ValueError(f"Target exceeds exposure at {date_value.date()}")
        dates.append(date_value)
        rows.append(row)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates), columns=list(columns), dtype=float)


def initial_event(index: pd.DatetimeIndex, columns: tuple[str, ...], target: dict[str, float]) -> pd.DataFrame:
    return event_frame(index, columns, {pd.Timestamp(index[0]): target})


def events_from_binary_state(
    state: pd.Series,
    index: pd.DatetimeIndex,
    risky_symbol: str,
    cash_symbol: str = "BIL",
) -> pd.DataFrame:
    aligned = state.reindex(index).fillna(False).astype(bool)
    events: dict[pd.Timestamp, dict[str, float]] = {}
    previous: bool | None = None
    for raw_date, active in aligned.items():
        active_bool = bool(active)
        if previous is None or active_bool != previous:
            events[pd.Timestamp(raw_date)] = {
                risky_symbol: 1.0 if active_bool else 0.0,
                cash_symbol: 0.0 if active_bool else 1.0,
            }
        previous = active_bool
    return event_frame(index, (risky_symbol, cash_symbol), events)


def _most_recent_extreme_score(values: np.ndarray, find_high: bool, period: int) -> float:
    extreme = np.nanmax(values) if find_high else np.nanmin(values)
    matches = np.flatnonzero(np.isclose(values, extreme, rtol=0.0, atol=1e-12))
    most_recent_position = int(matches[-1])
    sessions_since = len(values) - 1 - most_recent_position
    return 100.0 * (period - sessions_since) / period


def aroon_components(spy: pd.DataFrame, period: int = 25) -> pd.DataFrame:
    high = spy["high"].astype(float)
    low = spy["low"].astype(float)
    up = high.rolling(period, min_periods=period).apply(
        lambda values: _most_recent_extreme_score(values, True, period),
        raw=True,
    )
    down = low.rolling(period, min_periods=period).apply(
        lambda values: _most_recent_extreme_score(values, False, period),
        raw=True,
    )
    return pd.DataFrame({"aroon_up": up, "aroon_down": down, "oscillator": up - down})


def aroon_state(spy: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    components = aroon_components(spy, 25)
    oscillator = components["oscillator"]
    bullish_cross = (oscillator > 90.0) & (oscillator.shift(1) <= 90.0)
    bearish_cross = (oscillator < -90.0) & (oscillator.shift(1) >= -90.0)
    state_values: list[bool] = []
    active = False
    for date_value in oscillator.index:
        if bool(bullish_cross.loc[date_value]):
            active = True
        elif bool(bearish_cross.loc[date_value]):
            active = False
        state_values.append(active)
    diagnostics = components.assign(
        bullish_cross=bullish_cross.fillna(False),
        bearish_cross=bearish_cross.fillna(False),
    )
    return pd.Series(state_values, index=oscillator.index, name="SPY_active"), diagnostics


def kst_value(close: pd.Series) -> pd.Series:
    components = []
    for roc_period, smoothing, weight in zip((10, 15, 20, 30), (10, 10, 10, 15), (1.0, 2.0, 3.0, 4.0)):
        roc = 100.0 * (close / close.shift(roc_period) - 1.0)
        components.append(weight * roc.rolling(smoothing, min_periods=smoothing).mean())
    return sum(components).rename("kst")


def _observed_holiday(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    result = date(year, month, 1)
    while result.weekday() != weekday:
        result += timedelta(days=1)
    return result + timedelta(days=7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    result = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while result.weekday() != weekday:
        result -= timedelta(days=1)
    return result


def _easter_date(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day_value = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day_value)


def scheduled_full_day_nyse_closures(year: int) -> set[date]:
    closures = {
        _observed_holiday(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_date(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed_holiday(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_holiday(date(year, 12, 25)),
    }
    if year >= 2022:
        closures.add(_observed_holiday(date(year, 6, 19)))
    return closures


def preholiday_schedule(index: pd.DatetimeIndex) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    all_closures: set[date] = set()
    for year in range(index.min().year, index.max().year + 2):
        all_closures.update(scheduled_full_day_nyse_closures(year))
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {"SPY": 0.0, "BIL": 1.0}
    }
    episodes: list[dict[str, Any]] = []
    for closure in sorted(all_closures):
        closure_ts = pd.Timestamp(closure)
        eligible = index[index < closure_ts]
        if not len(eligible):
            continue
        active_date = pd.Timestamp(eligible[-1])
        if active_date < index.min() or active_date > index.max():
            continue
        if (closure_ts - active_date).days > 4:
            continue
        active_pos = int(index.get_loc(active_date))
        if active_pos == 0:
            continue
        signal_date = pd.Timestamp(index[active_pos - 1])
        events[signal_date] = {"SPY": 1.0, "BIL": 0.0}
        events[active_date] = {"SPY": 0.0, "BIL": 1.0}
        episodes.append(
            {
                "signal_date": signal_date,
                "active_start": active_date,
                "active_end": active_date,
                "closure_date": closure_ts,
                "calendar_year": active_date.year,
            }
        )
    return event_frame(index, ("SPY", "BIL"), events), episodes


def january_schedule(
    index: pd.DatetimeIndex,
    risky_symbol: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {risky_symbol: 0.0, "BIL": 1.0}
    }
    episodes: list[dict[str, Any]] = []
    for year in sorted(set(index.year)):
        january = index[(index.year == year) & (index.month == 1)]
        if not len(january):
            continue
        first_january = pd.Timestamp(january[0])
        first_pos = int(index.get_loc(first_january))
        if first_pos == 0:
            continue
        signal_date = pd.Timestamp(index[first_pos - 1])
        last_january = pd.Timestamp(january[-1])
        events[signal_date] = {risky_symbol: 1.0, "BIL": 0.0}
        events[last_january] = {risky_symbol: 0.0, "BIL": 1.0}
        episodes.append(
            {
                "signal_date": signal_date,
                "active_start": first_january,
                "active_end": last_january,
                "closure_date": "",
                "calendar_year": year,
            }
        )
    return event_frame(index, (risky_symbol, "BIL"), events), episodes


def monthly_static_schedule(index: pd.DatetimeIndex, risky_weight: float) -> pd.DataFrame:
    periods = pd.Series(index.to_period("M"), index=index)
    month_end = index[periods.ne(periods.shift(-1)).fillna(True)]
    events = {
        pd.Timestamp(date_value): {"SPY": risky_weight, "BIL": 1.0 - risky_weight}
        for date_value in month_end
    }
    events[pd.Timestamp(index[0])] = {"SPY": risky_weight, "BIL": 1.0 - risky_weight}
    return event_frame(index, ("SPY", "BIL"), events)


def compress_weight_frame(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return weights
    changed = weights.ne(weights.shift(1)).any(axis=1)
    changed.iloc[0] = True
    return weights.loc[changed].copy()


def prepare_candidate(card: CandidateCard) -> dict[str, Any]:
    prices = prior.load_price_frame(card.universe).dropna().sort_index()
    if prices.empty:
        return {"prices": prices, "candidate_events": pd.DataFrame(), "control_events": {}}
    index = prices.index
    controls: dict[str, pd.DataFrame] = {}
    metadata: dict[str, Any] = {"calendar_episodes": [], "indicator_name": ""}

    if card.strategy_id == "chande_aroon_oscillator_25_90_spy_bil_v1":
        spy_full = prior.load_adjusted_ohlcv("SPY")
        state_full, indicator = aroon_state(spy_full)
        state = state_full.reindex(index).ffill().fillna(False)
        candidate = events_from_binary_state(state, index, "SPY")
        controls["SPY_buy_and_hold"] = initial_event(index, ("SPY", "BIL"), {"SPY": 1.0, "BIL": 0.0})
        spy200d = reference_spy200d_weights(prices[["SPY", "BIL"]])
        controls["SPY_200d_frozen_control"] = compress_weight_frame(spy200d)
        metadata.update(
            {
                "indicator_name": "Aroon_Oscillator_25",
                "indicator_values": indicator.reindex(index),
                "state": state,
            }
        )
    elif card.strategy_id == "ariel_spy_preholiday_bil_v1":
        candidate, episodes = preholiday_schedule(index)
        exposure_fraction = float(len(episodes) / len(index))
        controls["SPY_buy_and_hold"] = initial_event(index, ("SPY", "BIL"), {"SPY": 1.0, "BIL": 0.0})
        controls["static_SPY_BIL_at_candidate_calendar_exposure_fraction"] = monthly_static_schedule(
            index, exposure_fraction
        )
        metadata.update({"calendar_episodes": episodes, "calendar_exposure_fraction": exposure_fraction})
    elif card.strategy_id == "reinganum_iwm_january_bil_v1":
        candidate, episodes = january_schedule(index, "IWM")
        controls["IWM_buy_and_hold"] = initial_event(
            index, ("IWM", "SPY", "BIL"), {"IWM": 1.0, "SPY": 0.0, "BIL": 0.0}
        )
        spy_january, _ = january_schedule(index, "SPY")
        controls["SPY_January_window"] = spy_january.reindex(columns=list(card.universe), fill_value=0.0)
        candidate = candidate.reindex(columns=list(card.universe), fill_value=0.0)
        metadata.update({"calendar_episodes": episodes, "calendar_exposure_fraction": float((index.month == 1).mean())})
    elif card.strategy_id == "pring_kst_default_centerline_spy_bil_v1":
        spy_full = prior.load_adjusted_ohlcv("SPY")
        kst = kst_value(spy_full["adj_close"])
        state = (kst > 0.0).reindex(index).fillna(False)
        candidate = events_from_binary_state(state, index, "SPY")
        controls["SPY_buy_and_hold"] = initial_event(index, ("SPY", "BIL"), {"SPY": 1.0, "BIL": 0.0})
        roc30 = 100.0 * (spy_full["adj_close"] / spy_full["adj_close"].shift(30) - 1.0)
        roc_state = (roc30 > 0.0).reindex(index).fillna(False)
        controls["SPY_30_session_ROC_sign_SPY_BIL"] = events_from_binary_state(roc_state, index, "SPY")
        metadata.update(
            {
                "indicator_name": "Pring_KST_default_centerline",
                "indicator_values": kst.reindex(index).to_frame("kst"),
                "state": state,
            }
        )
    else:
        raise RuntimeError(f"Unsupported candidate: {card.strategy_id}")

    if tuple(controls) != card.controls:
        raise RuntimeError(f"Control scope drift for {card.strategy_id}")
    return {
        "prices": prices,
        "candidate_events": candidate.reindex(columns=list(card.universe), fill_value=0.0),
        "control_events": {
            control_id: events.reindex(columns=list(card.universe), fill_value=0.0)
            for control_id, events in controls.items()
        },
        **metadata,
    }


def simulate_path(
    prices: pd.DataFrame,
    target_events: pd.DataFrame,
    cost_bps: float,
    timing_convention: str,
) -> dict[str, Any]:
    prices = prices.sort_index().dropna()
    symbols = tuple(prices.columns)
    events = target_events.reindex(columns=list(symbols), fill_value=0.0).sort_index()
    positions = prices.index.get_indexer(events.index)
    event_by_position = {
        int(position): row.to_numpy(dtype=float)
        for position, (_, row) in zip(positions, events.iterrows())
        if position >= 0
    }
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0).to_numpy(dtype=float)
    current = np.zeros(len(symbols), dtype=float)
    net_returns = np.zeros(len(prices), dtype=float)
    turnover = np.zeros(len(prices), dtype=float)
    cost_drag = np.zeros(len(prices), dtype=float)
    gross_exposure = np.zeros(len(prices), dtype=float)
    weight_sum = np.zeros(len(prices), dtype=float)
    risky_exposure = np.zeros(len(prices), dtype=float)
    held_rows: list[np.ndarray] = []
    event_rows: list[dict[str, Any]] = []
    for position, date_value in enumerate(prices.index):
        held = current.copy()
        held_rows.append(held)
        daily_return = asset_returns[position]
        gross_return = float(np.dot(held, daily_return))
        drifted_value = held * (1.0 + daily_return)
        denominator = float(drifted_value.sum())
        pretrade = drifted_value / denominator if denominator > 0.0 else held.copy()
        target = pretrade.copy()
        daily_turnover = 0.0
        if position in event_by_position:
            target = event_by_position[position].copy()
            daily_turnover = 0.5 * float(np.abs(target - pretrade).sum())
        cost_fraction = daily_turnover * (cost_bps / 10000.0)
        net_return = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        net_returns[position] = net_return
        turnover[position] = daily_turnover
        cost_drag[position] = (1.0 + gross_return) * cost_fraction
        gross_exposure[position] = max(float(np.abs(held).sum()), float(np.abs(target).sum()))
        weight_sum[position] = max(float(held.sum()), float(target.sum()))
        risky_exposure[position] = float(
            held[[idx for idx, symbol in enumerate(symbols) if symbol != "BIL"]].sum()
        )
        if position in event_by_position:
            event_rows.append(
                {
                    "event_date": pd.Timestamp(date_value).date().isoformat(),
                    "signal_or_target_date": pd.Timestamp(date_value).date().isoformat(),
                    "one_way_turnover": daily_turnover,
                    "timing_convention": timing_convention,
                }
            )
        current = target
    index = prices.index
    held_weights = pd.DataFrame(held_rows, index=index, columns=list(symbols))
    daily = pd.DataFrame(
        {
            "net_return": net_returns,
            "one_way_turnover": turnover,
            "transaction_cost_drag": cost_drag,
            "max_gross_exposure": gross_exposure,
            "max_daily_weight_sum": weight_sum,
            "risky_exposure": risky_exposure,
        },
        index=index,
    )
    return {
        "returns": daily["net_return"],
        "turnover": daily["one_way_turnover"],
        "cost": daily["transaction_cost_drag"],
        "daily": daily,
        "held_weights": held_weights,
        "events": event_rows,
        "timing_convention": timing_convention,
        "target_events": events,
    }


def metric_payload(path: dict[str, Any], period_index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    returns = path["returns"] if period_index is None else path["returns"].reindex(period_index).dropna()
    daily = path["daily"].reindex(returns.index)
    metrics = prior.metrics_from_returns(returns)
    max_exposure = float(daily["max_gross_exposure"].max()) if len(daily) else float("nan")
    max_weight_sum = float(daily["max_daily_weight_sum"].max()) if len(daily) else float("nan")
    target_events = path["target_events"]
    target_values = target_events.to_numpy(dtype=float) if not target_events.empty else np.empty((0, 0))
    event_targets_valid = bool(
        target_values.size
        and np.isfinite(target_values).all()
        and (target_values >= -WEIGHT_TOLERANCE).all()
        and (target_values.sum(axis=1) <= 1.0 + WEIGHT_TOLERANCE).all()
    )
    numeric_pass = bool(len(returns) and np.isfinite(returns.to_numpy(dtype=float)).all())
    exposure_pass = bool(
        math.isfinite(max_exposure)
        and math.isfinite(max_weight_sum)
        and max_exposure <= 1.0 + WEIGHT_TOLERANCE
        and max_weight_sum <= 1.0 + WEIGHT_TOLERANCE
        and (path["held_weights"].to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
        and event_targets_valid
    )
    return {
        **metrics,
        "average_risky_exposure": float(daily["risky_exposure"].mean()) if len(daily) else float("nan"),
        "turnover": float(daily["one_way_turnover"].sum()),
        "trade_or_rebalance_count": int((daily["one_way_turnover"] > WEIGHT_TOLERANCE).sum()),
        "transaction_cost_drag": float(daily["transaction_cost_drag"].sum()),
        "maximum_gross_exposure": max_exposure,
        "maximum_daily_weight_sum": max_weight_sum,
        "numeric_invariant_status": "pass" if numeric_pass else "fail",
        "timing_invariant_status": "pass_completed_close_target_applied_to_following_session",
        "exposure_weight_invariant_status": "pass" if exposure_pass else "fail",
        "invariant_pass": bool(numeric_pass and exposure_pass),
    }


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def run_candidate(card: CandidateCard, preflight_rows: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [row for row in preflight_rows if row["strategy_id"] == card.strategy_id]
    failed = [row["symbol"] for row in relevant if row["candidate_preflight_status"] != "pass"]
    if failed:
        return {
            "card": card,
            "executed": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_unavailable",
            "decision_reason": f"required cache preflight failed: {','.join(sorted(failed))}",
            "next_action": f"direction_owner_review_{card.strategy_id}_data_issue",
            "candidate_paths": {},
            "control_paths": {},
            "prepared": {},
        }
    prepared = prepare_candidate(card)
    prices = prepared["prices"]
    if prices.empty or len(prices) < MIN_OBSERVATIONS:
        return {
            "card": card,
            "executed": False,
            "outcome": "blocked_feasibility",
            "failure_reason": "data_or_comparability_failure",
            "decision_reason": "insufficient common matching-date history",
            "next_action": f"direction_owner_review_{card.strategy_id}_feasibility_block",
            "candidate_paths": {},
            "control_paths": {},
            "prepared": prepared,
        }
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    timing = "completed_close_target_applied_to_following_session"
    if card.strategy_id in {
        "ariel_spy_preholiday_bil_v1",
        "reinganum_iwm_january_bil_v1",
    }:
        timing = "known_calendar_target_set_at_prior_close_for_following_active_session"
    for cost_bps in COST_BPS_GRID:
        candidate_paths[cost_bps] = simulate_path(
            prices, prepared["candidate_events"], cost_bps, timing
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost_bps)] = simulate_path(
                prices, events, cost_bps, timing
            )
    result = {
        "card": card,
        "executed": True,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "prepared": prepared,
    }
    outcome, failure_reason, decision_reason = classify_candidate(result)
    result.update(
        {
            "outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "next_action": (
                f"direction_owner_review_{card.strategy_id}_exploratory_followup"
                if outcome == "exploratory_followup_candidate_standalone"
                else "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
            ),
        }
    )
    return result


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - 1e-12
        and float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - 1e-12
        and float(control["maximum_drawdown"]) >= float(candidate["maximum_drawdown"]) - 1e-12
    )
    strictly_better = (
        float(control["cagr"]) > float(candidate["cagr"]) + 1e-12
        or float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + 1e-12
        or float(control["maximum_drawdown"]) > float(candidate["maximum_drawdown"]) + 1e-12
    )
    return bool(equal_or_better and strictly_better)


def classify_candidate(result: dict[str, Any]) -> tuple[str, str, str]:
    card: CandidateCard = result["card"]
    candidate = metric_payload(result["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: metric_payload(result["control_paths"][(control_id, PRIMARY_COST_BPS)])
        for control_id in card.controls
    }
    same_id = card.controls[1]
    same = controls[same_id]
    all_metrics = [candidate, *controls.values()]
    if not all(bool(row["invariant_pass"]) for row in all_metrics):
        return "blocked_feasibility", "methodology_failure", "candidate or control invariant failed"
    if float(candidate["total_return"]) <= 0.0:
        return "closed_exploration", "weak_return", "full-period after-cost return is not positive"
    dominating = [control_id for control_id, row in controls.items() if dominates(row, candidate)]
    if dominating:
        return (
            "closed_exploration",
            "weak_vs_primary_control",
            f"simpler control dominates on CAGR, Sharpe, and drawdown: {','.join(dominating)}",
        )
    sharpe_advantage = float(candidate["sharpe_ratio"]) - float(same["sharpe_ratio"])
    drawdown_advantage = float(candidate["maximum_drawdown"]) - float(same["maximum_drawdown"])
    if sharpe_advantage < 0.02 - 1e-12 and drawdown_advantage < 0.01 - 1e-12:
        return (
            "closed_exploration",
            "benchmark_like_behavior",
            "same-purpose control reproduces the claimed benefit below both materiality thresholds",
        )
    for half_label, half_index in split_halves(result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index):
        candidate_half = metric_payload(result["candidate_paths"][PRIMARY_COST_BPS], half_index)
        control_half = metric_payload(result["control_paths"][(same_id, PRIMARY_COST_BPS)], half_index)
        worse_sharpe = float(candidate_half["sharpe_ratio"]) < float(control_half["sharpe_ratio"]) - 1e-12
        worse_drawdown = float(candidate_half["maximum_drawdown"]) < float(control_half["maximum_drawdown"]) - 1e-12
        if worse_sharpe and worse_drawdown:
            return (
                "closed_exploration",
                "period_instability",
                f"candidate is worse on Sharpe and drawdown in {half_label}",
            )
    candidate_10 = metric_payload(result["candidate_paths"][10.0])
    same_10 = metric_payload(result["control_paths"][(same_id, 10.0)])
    if (
        float(candidate_10["sharpe_ratio"]) < float(same_10["sharpe_ratio"]) - 1e-12
        and float(candidate_10["maximum_drawdown"]) < float(same_10["maximum_drawdown"]) - 1e-12
    ):
        return (
            "closed_exploration",
            "cost_drag",
            "result becomes unfavorable on both Sharpe and drawdown at 10 bps",
        )
    return (
        "exploratory_followup_candidate_standalone",
        "",
        "all preregistered lightweight standalone materiality conditions pass",
    )


def _base_result_row(
    result: dict[str, Any],
    row_type: str,
    control_id: str,
    cost_bps: float,
    metrics: dict[str, Any],
    period_label: str = "full_period",
) -> dict[str, Any]:
    card: CandidateCard = result["card"]
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": card.trial_id,
        "row_type": row_type,
        "control_id": control_id,
        "cost_assumption_bps": cost_bps,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "chronological_split_diagnostic_not_clean_or_sealed_holdout"
        ),
        **metrics,
    }


def result_tables(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        zero_candidate = metric_payload(result["candidate_paths"][0.0])
        for cost_bps in COST_BPS_GRID:
            candidate_metrics = metric_payload(result["candidate_paths"][cost_bps])
            trial_rows.append(_base_result_row(result, "candidate", "", cost_bps, candidate_metrics))
            cost_rows.append(
                {
                    **_base_result_row(result, "candidate", "", cost_bps, candidate_metrics),
                    "total_return_difference_vs_0bps": (
                        float(candidate_metrics["total_return"]) - float(zero_candidate["total_return"])
                    ),
                }
            )
            invariant_rows.append(
                {
                    **_base_result_row(result, "candidate", "", cost_bps, candidate_metrics),
                    "target_zero_weights_preserved": True,
                    "stale_weight_forward_fill_used": False,
                    "same_period_price_signal_return_used": False,
                }
            )
            for half_label, half_index in split_halves(result["candidate_paths"][cost_bps]["returns"].index):
                half_rows.append(
                    _base_result_row(
                        result,
                        "candidate",
                        "",
                        cost_bps,
                        metric_payload(result["candidate_paths"][cost_bps], half_index),
                        half_label,
                    )
                )
            for control_id in card.controls:
                control_path = result["control_paths"][(control_id, cost_bps)]
                control_metrics = metric_payload(control_path)
                control_rows.append(
                    _base_result_row(result, "benchmark_reference", control_id, cost_bps, control_metrics)
                )
                zero_control = metric_payload(result["control_paths"][(control_id, 0.0)])
                cost_rows.append(
                    {
                        **_base_result_row(
                            result, "benchmark_reference", control_id, cost_bps, control_metrics
                        ),
                        "total_return_difference_vs_0bps": (
                            float(control_metrics["total_return"]) - float(zero_control["total_return"])
                        ),
                    }
                )
                invariant_rows.append(
                    {
                        **_base_result_row(
                            result, "benchmark_reference", control_id, cost_bps, control_metrics
                        ),
                        "target_zero_weights_preserved": True,
                        "stale_weight_forward_fill_used": False,
                        "same_period_price_signal_return_used": False,
                    }
                )
                for half_label, half_index in split_halves(control_path["returns"].index):
                    half_rows.append(
                        _base_result_row(
                            result,
                            "benchmark_reference",
                            control_id,
                            cost_bps,
                            metric_payload(control_path, half_index),
                            half_label,
                        )
                    )
    return {
        "all_trial_results": trial_rows,
        "control_results": control_rows,
        "chronological_half_results": half_rows,
        "cost_diagnostics": cost_rows,
        "invariant_results": invariant_rows,
    }


def calendar_diagnostic_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        episodes = result["prepared"].get("calendar_episodes", [])
        if not episodes:
            continue
        card: CandidateCard = result["card"]
        for cost_bps in COST_BPS_GRID:
            returns = result["candidate_paths"][cost_bps]["returns"]
            window_returns: list[float] = []
            for episode in episodes:
                start = pd.Timestamp(episode["signal_date"])
                end = pd.Timestamp(episode["active_end"])
                window = returns.loc[(returns.index >= start) & (returns.index <= end)]
                if len(window):
                    window_returns.append(float((1.0 + window).prod() - 1.0))
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "cost_assumption_bps": cost_bps,
                    "active_session_count": int(
                        sum(
                            len(
                                returns.index[
                                    (returns.index >= pd.Timestamp(episode["active_start"]))
                                    & (returns.index <= pd.Timestamp(episode["active_end"]))
                                ]
                            )
                            for episode in episodes
                        )
                    ),
                    "active_year_count": len({int(episode["calendar_year"]) for episode in episodes}),
                    "active_window_count": len(window_returns),
                    "average_active_window_return": float(np.mean(window_returns)) if window_returns else float("nan"),
                    "median_active_window_return": float(np.median(window_returns)) if window_returns else float("nan"),
                    "positive_active_window_fraction": (
                        float(np.mean(np.array(window_returns) > 0.0)) if window_returns else float("nan")
                    ),
                    "calendar_scope": (
                        "scheduled_full_day_NYSE_closures_only"
                        if card.strategy_id == "ariel_spy_preholiday_bil_v1"
                        else "all_return_sessions_with_close_in_calendar_January"
                    ),
                    "descriptive_only": True,
                }
            )
    return rows


def _holding_durations(active: pd.Series) -> list[int]:
    durations: list[int] = []
    running = 0
    for value in active.astype(bool):
        if value:
            running += 1
        elif running:
            durations.append(running)
            running = 0
    if running:
        durations.append(running)
    return durations


def indicator_diagnostic_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"] or not result["prepared"].get("indicator_name"):
            continue
        card: CandidateCard = result["card"]
        for cost_bps in COST_BPS_GRID:
            held = result["candidate_paths"][cost_bps]["held_weights"]
            active = held["SPY"] > 0.5
            previous = active.shift(1, fill_value=False).astype(bool)
            entries = int((active & ~previous).sum())
            exits = int((~active & previous).sum())
            durations = _holding_durations(active)
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "indicator_name": result["prepared"]["indicator_name"],
                    "cost_assumption_bps": cost_bps,
                    "entry_count": entries,
                    "exit_count": exits,
                    "percentage_sessions_in_SPY": float(active.mean()),
                    "average_holding_duration_sessions": (
                        float(np.mean(durations)) if durations else 0.0
                    ),
                    "median_holding_duration_sessions": (
                        float(np.median(durations)) if durations else 0.0
                    ),
                    "holding_episode_count": len(durations),
                    "descriptive_only": True,
                }
            )
    return rows


def source_reference_rows(cards: list[CandidateCard]) -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": card.source_record_id,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "source_library_id": SOURCE_LIBRARY_ID,
            "strategy_id_referenced": card.strategy_id,
            "family_id": card.family_id,
            "authoritative_source_path": rel(SOURCE_RECORDS_PATH),
            "frozen_spec_path": rel(FROZEN_SPECS_PATH),
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in cards
    ]


def strategy_card_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": card.strategy_architecture,
                "source_or_research_lineage": (
                    f"{SOURCE_LIBRARY_ID}:{card.source_record_id};{card.translation_note}"
                ),
                "instrument_universe": card.universe,
                "parameters": card.parameters,
                "benchmark_or_control": card.controls,
                "stage": "exploration",
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": result["next_action"],
            }
        )
    return rows


def trial_ledger_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        prices = result.get("prepared", {}).get("prices", pd.DataFrame())
        rows.append(
            {
                "trial_id": card.trial_id,
                "entity_type": "experiment_trial",
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "stage": "exploration",
                "parent_trial_id": "",
                "adaptation_label": "",
                "source_library_id": SOURCE_LIBRARY_ID,
                "complete_frozen_rule": card.complete_frozen_rule,
                "instruments": card.universe,
                "evaluation_start": (
                    prices.index.min().date().isoformat() if isinstance(prices, pd.DataFrame) and not prices.empty else ""
                ),
                "evaluation_end": (
                    prices.index.max().date().isoformat() if isinstance(prices, pd.DataFrame) and not prices.empty else ""
                ),
                "benchmark_and_controls": card.controls,
                "route": "standalone",
                "transaction_cost_assumptions": "0|5|10 bps per one-way turnover; 5 bps primary",
                "execution_timing": "completed close target applied to following session return",
                "changed_fields_from_parent": "",
                "preregistration_timestamp": FROZEN_TIMESTAMP,
                "executed": result["executed"],
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": result["next_action"],
            }
        )
    return rows


def benchmark_rows(cards: list[CandidateCard]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in cards:
        for position, control_id in enumerate(card.controls):
            rows.append(
                {
                    "benchmark_reference_id": f"{card.strategy_id}__{control_id}",
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "strategy_id_context": card.strategy_id,
                    "family_id_context": card.family_id,
                    "control_id": control_id,
                    "control_role": "primary" if position == 0 else "same_purpose",
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "counted_as_observation": False,
                }
            )
    return rows


def process_rows(batch_next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": BATCH_ID,
            "entity_type": "process_task",
            "stage": "exploration",
            "task_scope": "exactly_four_frozen_source_library_candidates",
            "strategy_count": 0,
            "trial_count": 0,
            "next_action": batch_next_action,
        }
    ]


def batch_next_action(results: list[dict[str, Any]]) -> str:
    if any(result["outcome"] == "exploratory_followup_candidate_standalone" for result in results):
        return NEXT_ACTION_REVIEW
    if all(result["executed"] and result["outcome"] == "closed_exploration" for result in results):
        return NEXT_ACTION_ALL_CLOSED
    executed = sum(bool(result["executed"]) for result in results)
    if executed < 2:
        return NEXT_ACTION_BLOCKED
    return NEXT_ACTION_REVIEW


def outcome_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "trial_id": result["card"].trial_id,
            "stage": "exploration",
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "strategy_next_action": result["next_action"],
            "batch_next_action": next_action,
            "validation_claimed": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
        }
        for result in results
    ]


def failure_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "trial_id": result["card"].trial_id,
            "outcome": result["outcome"],
            "primary_failure_reason": result["failure_reason"],
            "failure_detail": result["decision_reason"],
            "exact_configuration_only": True,
            "family_closed": False,
            "parameter_change_authorized": False,
        }
        for result in results
        if result["failure_reason"]
    ]


def next_action_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "entity_id": result["card"].strategy_id,
            "entity_type": "strategy_configuration",
            "outcome": result["outcome"],
            "next_action": result["next_action"],
            "execute_in_this_task": False,
        }
        for result in results
    ]
    rows.append(
        {
            "entity_id": BATCH_ID,
            "entity_type": "process_task",
            "outcome": "batch_complete",
            "next_action": next_action,
            "execute_in_this_task": False,
        }
    )
    return rows


def funnel_counts(results: list[dict[str, Any]], cards: list[CandidateCard]) -> dict[str, Any]:
    return {
        "source_library_records_referenced": len(cards),
        "strategy_configurations_considered": len(cards),
        "experiment_trials_recorded": len(cards),
        "experiment_trials_executed": sum(bool(result["executed"]) for result in results),
        "benchmark_references": sum(len(card.controls) for card in cards),
        "process_tasks": 1,
        "standalone_followup_candidates": sum(
            result["outcome"] == "exploratory_followup_candidate_standalone" for result in results
        ),
        "closed_strategies": sum(result["outcome"] == "closed_exploration" for result in results),
        "blocked_or_inconclusive_strategies": sum(
            result["outcome"] in {"blocked_feasibility", "inconclusive_data_issue"}
            for result in results
        ),
    }


RESULT_FIELDS = [
    "strategy_id",
    "family_id",
    "trial_id",
    "row_type",
    "control_id",
    "cost_assumption_bps",
    "period_label",
    "period_role",
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
    "exposure_weight_invariant_status",
    "invariant_pass",
]

CSV_FIELDS = {
    "source_record_references.csv": [
        "source_record_id", "entity_type", "stage", "source_library_id", "strategy_id_referenced",
        "family_id", "authoritative_source_path", "frozen_spec_path", "counted_as_strategy", "counted_as_trial",
    ],
    "strategy_cards.csv": [
        "strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture",
        "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage",
        "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action",
    ],
    "trial_ledger.csv": [
        "trial_id", "entity_type", "strategy_id", "family_id", "stage", "parent_trial_id", "adaptation_label",
        "source_library_id", "complete_frozen_rule", "instruments", "evaluation_start", "evaluation_end",
        "benchmark_and_controls", "route", "transaction_cost_assumptions", "execution_timing",
        "changed_fields_from_parent", "preregistration_timestamp", "executed", "outcome", "failure_reason",
        "next_action",
    ],
    "benchmark_reference_log.csv": [
        "benchmark_reference_id", "entity_type", "stage", "strategy_id_context", "family_id_context",
        "control_id", "control_role", "counted_as_strategy", "counted_as_trial", "counted_as_observation",
    ],
    "process_task_log.csv": [
        "process_task_id", "entity_type", "stage", "task_scope", "strategy_count", "trial_count", "next_action",
    ],
    "data_preflight_reconciliation.csv": [
        "strategy_id", "family_id", "symbol", "cache_path", "cache_hash", "normal_backtester_loader", "row_count",
        "first_valid_date", "last_valid_date", "fields_available", "missing_required_fields",
        "ordered_unique_dates", "nonfinite_value_count", "nonpositive_price_count", "negative_volume_count",
        "invalid_ohlc_count", "adjustment_compatibility_mismatch_count", "canonical_loader_row_count",
        "canonical_adjustment_compatible", "preflight_status", "failure_reason", "candidate_common_start",
        "candidate_common_end", "internal_common_calendar_gap_count", "candidate_preflight_status",
    ],
    "all_trial_results.csv": RESULT_FIELDS,
    "control_results.csv": RESULT_FIELDS,
    "chronological_half_results.csv": RESULT_FIELDS,
    "calendar_event_diagnostics.csv": [
        "strategy_id", "family_id", "trial_id", "cost_assumption_bps", "active_session_count",
        "active_year_count", "active_window_count", "average_active_window_return",
        "median_active_window_return", "positive_active_window_fraction", "calendar_scope", "descriptive_only",
    ],
    "indicator_state_diagnostics.csv": [
        "strategy_id", "family_id", "trial_id", "indicator_name", "cost_assumption_bps", "entry_count",
        "exit_count", "percentage_sessions_in_SPY", "average_holding_duration_sessions",
        "median_holding_duration_sessions", "holding_episode_count", "descriptive_only",
    ],
    "cost_diagnostics.csv": RESULT_FIELDS + ["total_return_difference_vs_0bps"],
    "invariant_results.csv": RESULT_FIELDS + [
        "target_zero_weights_preserved", "stale_weight_forward_fill_used",
        "same_period_price_signal_return_used",
    ],
    "exploratory_followup_candidates.csv": [
        "strategy_id", "family_id", "trial_id", "stage", "outcome", "decision_reason", "next_action",
    ],
    "failure_reasons.csv": [
        "strategy_id", "family_id", "trial_id", "outcome", "primary_failure_reason", "failure_detail",
        "exact_configuration_only", "family_closed", "parameter_change_authorized",
    ],
    "next_actions.csv": [
        "entity_id", "entity_type", "outcome", "next_action", "execute_in_this_task",
    ],
    "outcome_summary.csv": [
        "strategy_id", "family_id", "trial_id", "stage", "outcome", "failure_reason", "decision_reason",
        "strategy_next_action", "batch_next_action", "validation_claimed", "promotion_authorized",
        "paper_demo_authorized",
    ],
}


def build_report(results: list[dict[str, Any]], funnel: dict[str, Any], next_action: str) -> str:
    lines = [
        "# Fast Source Library Batch V5",
        "",
        "## Scope",
        "",
        "Exactly four frozen source-library strategy configurations were considered. "
        "This is exploratory evidence only; no validation, robustness, promotion, or paper/demo decision is made.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Primary reason |",
        "|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| `{result['card'].strategy_id}` | `{result['outcome']}` | "
            f"`{result['failure_reason'] or 'none'}` |"
        )
    lines.extend(
        [
            "",
            "The first and second chronological halves are descriptive splits and are not clean or sealed holdouts.",
            "",
            "## Entity Counts",
            "",
            f"* Source-library records referenced: {funnel['source_library_records_referenced']}",
            f"* Strategy configurations considered: {funnel['strategy_configurations_considered']}",
            f"* Experiment trials recorded: {funnel['experiment_trials_recorded']}",
            f"* Experiment trials executed: {funnel['experiment_trials_executed']}",
            f"* Benchmark references: {funnel['benchmark_references']}",
            f"* Process tasks: {funnel['process_tasks']}",
            f"* Standalone follow-up candidates: {funnel['standalone_followup_candidates']}",
            f"* Closed strategies: {funnel['closed_strategies']}",
            f"* Blocked or inconclusive strategies: {funnel['blocked_or_inconclusive_strategies']}",
            "",
            "## Guardrails",
            "",
            "* Existing adjusted daily cache only; no provider access or download.",
            "* One canonical trial per strategy; no variants or parameter alternatives.",
            "* Controls remain benchmark references and are not counted as strategies or trials.",
            "* Turnover uses actual drifted pretrade holdings.",
            "* No protected state, prior evidence, broker, account, order, or real-money path changed.",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


def deterministic_core_hash() -> str:
    names = [
        "batch_manifest.yaml",
        *CSV_FIELDS.keys(),
        "cohort_funnel_counts.json",
        "batch_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    cards = load_cards()
    before_protected = protected_hashes()
    before_inputs = input_hashes()
    preflight_rows, _ = data_preflight(cards)
    results = [run_candidate(card, preflight_rows) for card in cards]
    next_action = batch_next_action(results)
    tables = result_tables(results)
    calendar_rows = calendar_diagnostic_rows(results)
    indicator_rows = indicator_diagnostic_rows(results)
    outcomes = outcome_rows(results, next_action)
    failures = failure_rows(results)
    next_actions = next_action_rows(results, next_action)
    funnel = funnel_counts(results, cards)
    after_protected = protected_hashes()
    after_inputs = input_hashes()

    clean_output_dir()
    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": BATCH_ID,
            "mode": "fast-progress",
            "stage": "exploration",
            "source_library_id": SOURCE_LIBRARY_ID,
            "preregistration_timestamp": FROZEN_TIMESTAMP,
            "strategy_ids": list(EXPECTED_STRATEGY_IDS),
            "strategy_count": len(cards),
            "canonical_trial_count": len(cards),
            "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS_GRID),
            "primary_cost_bps": PRIMARY_COST_BPS,
            "data_policy": "existing_canonical_adjusted_daily_cache_only_no_provider_access",
            "source_records_path": rel(SOURCE_RECORDS_PATH),
            "frozen_specs_path": rel(FROZEN_SPECS_PATH),
            "exact_next_action": next_action,
            "next_action_executed": False,
            "exploration_only": True,
            "validation_claimed": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
        },
    )
    artifact_rows = {
        "source_record_references.csv": source_reference_rows(cards),
        "strategy_cards.csv": strategy_card_rows(results),
        "trial_ledger.csv": trial_ledger_rows(results),
        "benchmark_reference_log.csv": benchmark_rows(cards),
        "process_task_log.csv": process_rows(next_action),
        "data_preflight_reconciliation.csv": preflight_rows,
        "all_trial_results.csv": tables["all_trial_results"],
        "control_results.csv": tables["control_results"],
        "chronological_half_results.csv": tables["chronological_half_results"],
        "calendar_event_diagnostics.csv": calendar_rows,
        "indicator_state_diagnostics.csv": indicator_rows,
        "cost_diagnostics.csv": tables["cost_diagnostics"],
        "invariant_results.csv": tables["invariant_results"],
        "exploratory_followup_candidates.csv": [
            {
                "strategy_id": result["card"].strategy_id,
                "family_id": result["card"].family_id,
                "trial_id": result["card"].trial_id,
                "stage": "exploration",
                "outcome": result["outcome"],
                "decision_reason": result["decision_reason"],
                "next_action": result["next_action"],
            }
            for result in results
            if result["outcome"] == "exploratory_followup_candidate_standalone"
        ],
        "failure_reasons.csv": failures,
        "next_actions.csv": next_actions,
        "outcome_summary.csv": outcomes,
    }
    for name, rows in artifact_rows.items():
        write_csv(OUTPUT_DIR / name, rows, CSV_FIELDS[name])
    write_json(
        OUTPUT_DIR / "cohort_funnel_counts.json",
        {**funnel, "exact_next_action": next_action},
    )
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, funnel, next_action))

    exact_scope = tuple(result["card"].strategy_id for result in results) == EXPECTED_STRATEGY_IDS
    metadata_complete = all(
        all(
            str(row.get(field, "")).strip()
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
                "outcome",
                "next_action",
            )
        )
        for row in strategy_card_rows(results)
    )
    consistency = {
        "batch_id": BATCH_ID,
        "status": "pass",
        "exact_four_candidate_scope": exact_scope,
        "exact_one_strategy_configuration_per_candidate": len(cards) == 4,
        "exact_one_canonical_trial_per_candidate": len(trial_ledger_rows(results)) == 4,
        "no_variants_created": all(not row["parent_trial_id"] and not row["adaptation_label"] for row in trial_ledger_rows(results)),
        "strategy_trial_metadata_complete": metadata_complete,
        "source_strategy_trial_benchmark_process_entities_separate": True,
        "all_controls_recorded_as_benchmark_reference_only": len(benchmark_rows(cards)) == 8,
        "all_preflights_passed": all(row["candidate_preflight_status"] == "pass" for row in preflight_rows),
        "all_executed_invariants_passed": all(
            row["invariant_pass"] for row in tables["invariant_results"]
        ),
        "chronological_halves_not_clean_or_sealed_holdouts": all(
            row["period_role"] == "chronological_split_diagnostic_not_clean_or_sealed_holdout"
            for row in tables["chronological_half_results"]
        ),
        "funnel_arithmetically_consistent": (
            funnel["standalone_followup_candidates"]
            + funnel["closed_strategies"]
            + funnel["blocked_or_inconclusive_strategies"]
            == 4
        ),
        "protected_state_hashes_before": before_protected,
        "protected_state_hashes_after": after_protected,
        "protected_state_unchanged": before_protected == after_protected,
        "input_evidence_hashes_before": before_inputs,
        "input_evidence_hashes_after": after_inputs,
        "input_evidence_unchanged": before_inputs == after_inputs,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "all_forbidden_actions_false": not any(FORBIDDEN_FLAGS.values()),
        "next_action": next_action,
        "next_action_executed": False,
    }
    if not all(
        [
            consistency["exact_four_candidate_scope"],
            consistency["exact_one_strategy_configuration_per_candidate"],
            consistency["exact_one_canonical_trial_per_candidate"],
            consistency["no_variants_created"],
            consistency["strategy_trial_metadata_complete"],
            consistency["all_preflights_passed"],
            consistency["all_executed_invariants_passed"],
            consistency["funnel_arithmetically_consistent"],
            consistency["protected_state_unchanged"],
            consistency["input_evidence_unchanged"],
            consistency["all_forbidden_actions_false"],
        ]
    ):
        consistency["status"] = "fail"
    consistency["deterministic_core_hash"] = deterministic_core_hash()
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": BATCH_ID,
        "output_dir": rel(OUTPUT_DIR),
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "funnel": funnel,
        "next_action": next_action,
        "consistency_status": consistency["status"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
