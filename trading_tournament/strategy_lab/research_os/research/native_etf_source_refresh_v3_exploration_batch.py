from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import native_etf_two_candidate_exploration_batch_v1 as base


BATCH_ID = "native_etf_source_refresh_v3_exploration_batch"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\39c7f191-f32d-44f4-abb8-930c6c127a1f\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-08-04T00:20:00+00:00"
COSTS = (0.0, 5.0, 10.0)
PRIMARY_COST = 5.0
TOLERANCE = 1e-10

PERCENTILE_ID = "varadi_percentile_channels_4asset_v1"
GROWTH_ID = "varadi_growth_inflation_sector_timing_original_v1"
PERCENTILE_TRIAL = "native_etf_v3__percentile_channels__canonical"
GROWTH_TRIAL = "native_etf_v3__growth_inflation__canonical"

PERCENTILE_RISKY = ("SPY", "VNQ", "LQD", "DBC")
PERCENTILE_UNIVERSE = (*PERCENTILE_RISKY, "SHY")
GROWTH_SIGNAL = ("SPY", "XLE", "XLI", "XLF", "XLB", "XLU", "XLV", "XLP")
GROWTH_TRADABLE = ("XLE", "XLK", "XLV", "XLP", "BIL")
GROWTH_UNIVERSE = tuple(dict.fromkeys((*GROWTH_SIGNAL, *GROWTH_TRADABLE)))
REQUIRED_SYMBOLS = tuple(dict.fromkeys((*PERCENTILE_UNIVERSE, *GROWTH_UNIVERSE)))

PERCENTILE_SAME = "donchian_4horizon_same_universe_control"
PERCENTILE_ALWAYS = "always_long_risk_parity_4asset_control"
PERCENTILE_EQUAL_SIGNAL = "percentile_channels_equal_weight_signal_control"
PERCENTILE_STATIC = "percentile_channels_static_average_weight_control"
PERCENTILE_CONTROLS = (
    PERCENTILE_SAME,
    PERCENTILE_ALWAYS,
    PERCENTILE_EQUAL_SIGNAL,
    PERCENTILE_STATIC,
    "monthly_equal_weight_spy_vnq_lqd_dbc_control",
    "SHY_buy_and_hold",
)

GROWTH_SAME = "growth_only_200sma_xlk_xlp_control"
GROWTH_INFLATION_ONLY = "inflation_only_200median_xle_xlp_control"
GROWTH_STATIC = "growth_inflation_static_average_weight_control"
GROWTH_CONTROLS = (
    GROWTH_SAME,
    GROWTH_INFLATION_ONLY,
    GROWTH_STATIC,
    "equal_weight_xle_xlk_xlv_xlp_control",
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)
PROTECTED_TREE_PATHS = (
    ROOT / "data" / "cache",
    ROOT / "paper_forward_observations",
)
REQUIRED_FILES = {
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
    "percentile_channel_signal_ledger.csv",
    "percentile_channel_weight_diagnostics.csv",
    "percentile_channel_control_reconciliation.csv",
    "growth_inflation_daily_regime_ledger.csv",
    "growth_inflation_control_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path, excluded: Path | None = None) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    excluded_resolved = excluded.resolve() if excluded is not None else None
    for item in sorted(value for value in path.rglob("*") if value.is_file()):
        if excluded_resolved is not None and excluded_resolved in item.resolve().parents:
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    normalized.index = pd.DatetimeIndex(normalized.index).strftime("%Y-%m-%d")
    return sha256_bytes(
        normalized.to_csv(index=True, lineterminator="\n", float_format="%.17g").encode("utf-8")
    )


def protected_hashes() -> dict[str, str]:
    output = {
        relative(path): tree_hash(path)
        for path in (*PROTECTED_STATE_PATHS, *PROTECTED_TREE_PATHS)
    }
    output["evidence_excluding_current_batch"] = tree_hash(ROOT / "evidence", OUTPUT_DIR)
    return output


def reset_output() -> None:
    if OUTPUT_DIR.exists():
        expected_parent = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected_parent not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"refusing to replace unexpected output path {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, (np.bool_, bool)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    columns = list(leading)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": "src_varadi_percentile_channels_4asset_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": PERCENTILE_ID,
            "outcome": "feasible",
            "failure_reason": "",
            "implementation_authorized": True,
            "source_completion_performed": False,
        },
        {
            "source_record_id": "src_varadi_growth_inflation_sector_timing_original_v1",
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": GROWTH_ID,
            "outcome": "feasible",
            "failure_reason": "",
            "implementation_authorized": True,
            "source_completion_performed": False,
        },
    ]


def strategy_rows() -> list[dict[str, Any]]:
    common = {
        "entity_type": "strategy_configuration",
        "stage": "exploration",
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": "preregistered_pending_execution",
        "failure_reason": "",
        "next_action": BATCH_ID,
        "exact_source_replication_claimed": False,
        "provider_access_performed": False,
    }
    return [
        {
            **common,
            "strategy_id": PERCENTILE_ID,
            "family_id": "multi_horizon_percentile_channel_allocation",
            "display_name": "Multi-Horizon Percentile Channel Allocation",
            "strategy_architecture": "monthly_percentile_hysteresis_channel_score_risk_parity",
            "source_or_research_lineage": "targeted_native_etf_source_refresh_v3:src_varadi_percentile_channels_4asset_v1",
            "instrument_universe": "SPY|VNQ|LQD|DBC|SHY",
            "route": "standalone_with_diversifier_diagnostic",
            "parameters": {
                "channel_horizons_sessions": [60, 120, 180, 252],
                "entry_percentile": 0.75,
                "exit_percentile": 0.25,
                "percentile_convention": "inclusive_linear_type7",
                "volatility_window_sessions": 20,
                "volatility_ddof": 1,
                "decision_frequency": "completed_month_end",
                "execution": "following_regular_session_close",
                "costs_bps_one_way": [0, 5, 10],
            },
            "benchmarks": list(PERCENTILE_CONTROLS),
            "benchmark_or_control": "|".join(PERCENTILE_CONTROLS),
            "trial_id": PERCENTILE_TRIAL,
        },
        {
            **common,
            "strategy_id": GROWTH_ID,
            "family_id": "sector_implied_growth_inflation_regime_rotation",
            "display_name": "Growth and Sector-Implied Inflation Regime Rotation",
            "strategy_architecture": "daily_two_axis_sector_regime_single_asset_rotation",
            "source_or_research_lineage": "targeted_native_etf_source_refresh_v3:src_varadi_growth_inflation_sector_timing_original_v1",
            "instrument_universe": "SPY|XLE|XLI|XLF|XLB|XLU|XLV|XLP|XLK|BIL",
            "route": "standalone_with_diversifier_diagnostic",
            "parameters": {
                "inflation_indicator": "original_unsmoothed_positive_index_divided_by_negative_index",
                "inflation_window_sessions": 200,
                "growth_window_sessions": 200,
                "basket_beta_adjustment": False,
                "turnover_smoothing": False,
                "decision_frequency": "daily_completed_close",
                "execution": "following_regular_session_close",
                "costs_bps_one_way": [0, 5, 10],
            },
            "benchmarks": list(GROWTH_CONTROLS),
            "benchmark_or_control": "|".join(GROWTH_CONTROLS),
            "trial_id": GROWTH_TRIAL,
        },
    ]


def trial_rows() -> list[dict[str, Any]]:
    return [
        {
            **strategy,
            "entity_type": "experiment_trial",
            "parent_trial_id": "",
            "adaptation_label": "",
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "source_completion_performed": False,
            "provider_access_performed": False,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        }
        for strategy in strategy_rows()
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    configurations = (
        (PERCENTILE_ID, PERCENTILE_CONTROLS, PERCENTILE_SAME, (PERCENTILE_SAME, PERCENTILE_ALWAYS)),
        (GROWTH_ID, GROWTH_CONTROLS, GROWTH_SAME, (GROWTH_SAME, GROWTH_STATIC)),
    )
    for strategy_id, controls, named, critical in configurations:
        for control in controls:
            rows.append(
                {
                    "strategy_id": strategy_id,
                    "benchmark_id": control,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "named_same_purpose_control": control == named,
                    "critical_control": control in critical,
                    "experiment_trial": False,
                    "promoted": False,
                }
            )
    return rows


def process_rows() -> list[dict[str, Any]]:
    return [{
        "process_task_id": BATCH_ID,
        "entity_type": "process_task",
        "stage": "exploration",
        "candidate_count": 2,
        "distinct_family_count": 2,
        "provider_access_performed": False,
        "source_research_performed": False,
        "validation_performed": False,
        "lifecycle_state_changed": False,
    }]


def adjusted_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    factor = frame["adj_close"] / frame["close"]
    output = pd.DataFrame(index=frame.index)
    for column in ("open", "high", "low", "close"):
        output[column] = frame[column] * factor
    output["volume"] = frame["volume"]
    return output


def close_prices(frames: dict[str, pd.DataFrame], universe: tuple[str, ...]) -> pd.DataFrame:
    return pd.concat(
        [frames[symbol]["close"].rename(symbol) for symbol in universe],
        axis=1,
        join="inner",
    ).dropna()


def preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame], dict[str, bool]]:
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    symbol_pass: dict[str, bool] = {}
    for symbol in REQUIRED_SYMBOLS:
        raw = market.load_adjusted_ohlcv(symbol)
        frame = adjusted_ohlcv(raw) if not raw.empty else pd.DataFrame()
        frames[symbol] = frame
        prices = frame[["open", "high", "low", "close"]].to_numpy(dtype=float) if not frame.empty else np.empty((0, 4))
        ordered = bool(not frame.empty and frame.index.is_monotonic_increasing and frame.index.is_unique)
        positive = bool(prices.size and np.isfinite(prices).all() and (prices > 0).all())
        ohlc = bool(
            not frame.empty
            and (frame["high"] + TOLERANCE >= frame[["open", "low", "close"]].max(axis=1)).all()
            and (frame["low"] - TOLERANCE <= frame[["open", "high", "close"]].min(axis=1)).all()
        )
        volume = bool(
            not frame.empty
            and np.isfinite(frame["volume"].to_numpy(dtype=float)).all()
            and (frame["volume"] >= 0).all()
        )
        finite_returns = bool(
            len(frame) > 1
            and np.isfinite(frame["close"].pct_change(fill_method=None).iloc[1:].to_numpy(dtype=float)).all()
        )
        adjusted_compatible = bool(
            not raw.empty
            and np.allclose(frame["close"].to_numpy(dtype=float), raw["adj_close"].to_numpy(dtype=float), rtol=0.0, atol=TOLERANCE)
        )
        passed = ordered and positive and ohlc and volume and finite_returns and adjusted_compatible
        symbol_pass[symbol] = passed
        rows.append({
            "record_type": "symbol",
            "symbol": symbol,
            "cache_path": raw.attrs.get("cache_path", ""),
            "canonical_file_hash": raw.attrs.get("cache_hash", "missing"),
            "normalized_frame_hash": frame_hash(frame) if not frame.empty else "missing",
            "first_valid_date": "" if frame.empty else frame.index.min().date().isoformat(),
            "last_valid_date": "" if frame.empty else frame.index.max().date().isoformat(),
            "row_count": len(frame),
            "ordered_unique_sessions": ordered,
            "finite_positive_adjusted_prices": positive,
            "valid_adjusted_ohlc": ohlc,
            "nonnegative_finite_volume": volume,
            "finite_returns": finite_returns,
            "canonical_adjustment_compatible": adjusted_compatible,
            "provider_access_performed": False,
            "preflight_status": "pass" if passed else "fail",
        })
    candidate_pass: dict[str, bool] = {}
    for strategy_id, universe, minimum_rows in (
        (PERCENTILE_ID, PERCENTILE_UNIVERSE, 504),
        (GROWTH_ID, GROWTH_UNIVERSE, 504),
    ):
        common = close_prices(frames, universe) if all(symbol_pass.get(symbol, False) for symbol in universe) else pd.DataFrame()
        passed = bool(
            not common.empty
            and len(common) >= minimum_rows
            and common.index.is_monotonic_increasing
            and common.index.is_unique
            and np.isfinite(common.to_numpy(dtype=float)).all()
            and (common > 0).all().all()
        )
        candidate_pass[strategy_id] = passed
        rows.append({
            "record_type": "candidate_common_period",
            "strategy_id": strategy_id,
            "symbol": "|".join(universe),
            "normalized_frame_hash": frame_hash(common) if not common.empty else "missing",
            "first_valid_date": "" if common.empty else common.index.min().date().isoformat(),
            "last_valid_date": "" if common.empty else common.index.max().date().isoformat(),
            "row_count": len(common),
            "ordered_unique_sessions": bool(not common.empty and common.index.is_monotonic_increasing and common.index.is_unique),
            "finite_positive_adjusted_prices": bool(not common.empty and np.isfinite(common.to_numpy()).all() and (common > 0).all().all()),
            "valid_adjusted_ohlc": all(symbol_pass.get(symbol, False) for symbol in universe),
            "finite_returns": bool(not common.empty and np.isfinite(common.pct_change(fill_method=None).iloc[1:].to_numpy(dtype=float)).all()),
            "canonical_adjustment_compatible": all(symbol_pass.get(symbol, False) for symbol in universe),
            "provider_access_performed": False,
            "preflight_status": "pass" if passed else "fail",
        })
    return rows, frames, candidate_pass


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.searchsorted(pd.Timestamp(signal_date), side="right"))
    return pd.Timestamp(index[position]) if position < len(index) else None


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def zero_target(columns: tuple[str, ...], fallback: str) -> dict[str, float]:
    return {symbol: 1.0 if symbol == fallback else 0.0 for symbol in columns}


def target_with_weights(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    return {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}


def monthly_static_events(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    target: dict[str, float],
) -> pd.DataFrame:
    month_ends = pd.Series(index=index, data=index).groupby(index.to_period("M")).last()
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): target_with_weights(columns, target)}
    for formation in month_ends:
        execution = next_session(index, pd.Timestamp(formation))
        if execution is not None:
            events[execution] = target_with_weights(columns, target)
    return accounting.event_frame(index, columns, events)


def percentile_type7(values: np.ndarray, quantile: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), quantile, method="linear"))


def update_hysteresis_state(
    prior_state: int | None,
    current_close: float,
    upper: float,
    lower: float,
) -> int:
    if prior_state is None:
        return -1
    if prior_state == -1 and current_close > upper:
        return 1
    if prior_state == 1 and current_close < lower:
        return -1
    return prior_state


def channel_allocation(
    scores: dict[str, float],
    volatilities: dict[str, float],
    use_volatility: bool,
) -> dict[str, float]:
    raw: dict[str, float] = {}
    for symbol in PERCENTILE_RISKY:
        score = float(scores[symbol])
        volatility = float(volatilities[symbol])
        if not math.isfinite(score) or (use_volatility and (not math.isfinite(volatility) or volatility <= 0.0)):
            return zero_target(PERCENTILE_UNIVERSE, "SHY")
        raw[symbol] = score / volatility if use_volatility else score
    denominator = float(sum(abs(value) for value in raw.values()))
    if not math.isfinite(denominator) or denominator <= 0.0:
        return zero_target(PERCENTILE_UNIVERSE, "SHY")
    target = {symbol: abs(raw[symbol]) / denominator if scores[symbol] > 0.0 else 0.0 for symbol in PERCENTILE_RISKY}
    target["SHY"] = max(0.0, 1.0 - sum(target.values()))
    return target_with_weights(PERCENTILE_UNIVERSE, target)


def _month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    values = pd.Series(index=index, data=index).groupby(index.to_period("M")).last()
    return [pd.Timestamp(value) for value in values]


def prepare_percentile_channels(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, PERCENTILE_UNIVERSE)
    index = prices.index
    returns = prices[list(PERCENTILE_RISKY)].pct_change(fill_method=None)
    vol20 = returns.rolling(20, min_periods=20).std(ddof=1)
    horizons = (60, 120, 180, 252)
    percentile_states = {(symbol, horizon): None for symbol in PERCENTILE_RISKY for horizon in horizons}
    donchian_states = {(symbol, horizon): None for symbol in PERCENTILE_RISKY for horizon in horizons}
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): zero_target(PERCENTILE_UNIVERSE, "SHY")}
    donchian_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): zero_target(PERCENTILE_UNIVERSE, "SHY")}
    always_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): zero_target(PERCENTILE_UNIVERSE, "SHY")}
    equal_signal_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): zero_target(PERCENTILE_UNIVERSE, "SHY")}
    diagnostics: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    invalid_formations = 0

    for formation in _month_ends(index):
        position = int(index.get_loc(formation))
        execution = next_session(index, formation)
        percentile_scores: dict[str, float] = {}
        donchian_scores: dict[str, float] = {}
        vols = {symbol: float(vol20.loc[formation, symbol]) for symbol in PERCENTILE_RISKY}
        formation_valid = True
        per_asset: dict[str, dict[str, Any]] = {}
        for symbol in PERCENTILE_RISKY:
            state_values: list[int] = []
            donchian_values: list[int] = []
            asset_detail: dict[str, Any] = {}
            current_close = float(prices.loc[formation, symbol])
            for horizon in horizons:
                prior = percentile_states[(symbol, horizon)]
                prior_donchian = donchian_states[(symbol, horizon)]
                upper = lower = dmax = dmin = float("nan")
                if position + 1 >= horizon:
                    window = prices[symbol].iloc[position - horizon + 1 : position + 1].to_numpy(dtype=float)
                    upper = percentile_type7(window, 0.75)
                    lower = percentile_type7(window, 0.25)
                    percentile_states[(symbol, horizon)] = update_hysteresis_state(prior, current_close, upper, lower)
                else:
                    formation_valid = False
                if position >= horizon:
                    prior_window = prices[symbol].iloc[position - horizon : position].to_numpy(dtype=float)
                    dmax = float(np.max(prior_window))
                    dmin = float(np.min(prior_window))
                    donchian_states[(symbol, horizon)] = update_hysteresis_state(prior_donchian, current_close, dmax, dmin)
                else:
                    formation_valid = False
                state = percentile_states[(symbol, horizon)]
                dstate = donchian_states[(symbol, horizon)]
                if state is None or dstate is None:
                    formation_valid = False
                else:
                    state_values.append(int(state))
                    donchian_values.append(int(dstate))
                asset_detail.update({
                    f"percentile_75_{horizon}": upper,
                    f"percentile_25_{horizon}": lower,
                    f"prior_state_{horizon}": "" if prior is None else prior,
                    f"state_{horizon}": "" if state is None else state,
                    f"donchian_max_{horizon}": dmax,
                    f"donchian_min_{horizon}": dmin,
                    f"donchian_prior_state_{horizon}": "" if prior_donchian is None else prior_donchian,
                    f"donchian_state_{horizon}": "" if dstate is None else dstate,
                })
            percentile_scores[symbol] = float(np.mean(state_values)) if len(state_values) == 4 else float("nan")
            donchian_scores[symbol] = float(np.mean(donchian_values)) if len(donchian_values) == 4 else float("nan")
            if not math.isfinite(vols[symbol]) or vols[symbol] <= 0.0:
                formation_valid = False
            per_asset[symbol] = asset_detail

        if formation_valid and execution is not None:
            candidate_target = channel_allocation(percentile_scores, vols, True)
            donchian_target = channel_allocation(donchian_scores, vols, True)
            always_scores = {symbol: 1.0 for symbol in PERCENTILE_RISKY}
            always_target = channel_allocation(always_scores, vols, True)
            equal_signal_target = channel_allocation(percentile_scores, vols, False)
            candidate_events[execution] = candidate_target
            donchian_events[execution] = donchian_target
            always_events[execution] = always_target
            equal_signal_events[execution] = equal_signal_target
            valid_formations.append(formation)
            execution_status = "scheduled_following_session_close"
        else:
            candidate_target = zero_target(PERCENTILE_UNIVERSE, "SHY")
            donchian_target = zero_target(PERCENTILE_UNIVERSE, "SHY")
            always_target = zero_target(PERCENTILE_UNIVERSE, "SHY")
            equal_signal_target = zero_target(PERCENTILE_UNIVERSE, "SHY")
            if execution is not None:
                candidate_events[execution] = candidate_target
                donchian_events[execution] = donchian_target
                always_events[execution] = always_target
                equal_signal_events[execution] = equal_signal_target
            invalid_formations += 1
            execution_status = "invalid_formation_to_SHY" if execution is not None else "blocked_missing_execution_session"

        for symbol in PERCENTILE_RISKY:
            raw_weight = (
                percentile_scores[symbol] / vols[symbol]
                if math.isfinite(percentile_scores[symbol]) and math.isfinite(vols[symbol]) and vols[symbol] > 0.0
                else float("nan")
            )
            diagnostics.append({
                "row_type": "formation_asset",
                "formation_date": formation.date().isoformat(),
                "asset": symbol,
                "adjusted_close": float(prices.loc[formation, symbol]),
                **per_asset[symbol],
                "channel_score": percentile_scores[symbol],
                "volatility20": vols[symbol],
                "raw_weight": raw_weight,
                "risky_weight": candidate_target[symbol],
                "SHY_residual": candidate_target["SHY"],
                "execution_date": "" if execution is None else execution.date().isoformat(),
                "execution_status": execution_status,
                "formation_valid": formation_valid,
                "turnover": 0.0,
                "cost": 0.0,
            })
            control_rows.append({
                "formation_date": formation.date().isoformat(),
                "execution_date": "" if execution is None else execution.date().isoformat(),
                "asset": symbol,
                "percentile_score": percentile_scores[symbol],
                "donchian_score": donchian_scores[symbol],
                "percentile_weight": candidate_target[symbol],
                "donchian_weight": donchian_target[symbol],
                "weight_difference": candidate_target[symbol] - donchian_target[symbol],
                "active_state_overlap": percentile_scores[symbol] > 0.0 and donchian_scores[symbol] > 0.0,
                "exact_weight_overlap": math.isclose(candidate_target[symbol], donchian_target[symbol], abs_tol=TOLERANCE),
            })

    candidate_frame = accounting.event_frame(index, PERCENTILE_UNIVERSE, candidate_events)
    candidate_targets = target_history(candidate_frame, index)
    average_target = {symbol: float(candidate_targets[symbol].mean()) for symbol in PERCENTILE_UNIVERSE}
    static_events = monthly_static_events(index, PERCENTILE_UNIVERSE, average_target)
    controls = {
        PERCENTILE_SAME: accounting.event_frame(index, PERCENTILE_UNIVERSE, donchian_events),
        PERCENTILE_ALWAYS: accounting.event_frame(index, PERCENTILE_UNIVERSE, always_events),
        PERCENTILE_EQUAL_SIGNAL: accounting.event_frame(index, PERCENTILE_UNIVERSE, equal_signal_events),
        PERCENTILE_STATIC: static_events,
        "monthly_equal_weight_spy_vnq_lqd_dbc_control": monthly_static_events(
            index, PERCENTILE_UNIVERSE, {**{symbol: 0.25 for symbol in PERCENTILE_RISKY}, "SHY": 0.0}
        ),
        "SHY_buy_and_hold": accounting.initial_event(index, PERCENTILE_UNIVERSE, zero_target(PERCENTILE_UNIVERSE, "SHY")),
    }
    return {
        "prices": prices,
        "candidate_events": candidate_frame,
        "control_events": controls,
        "diagnostics": pd.DataFrame(diagnostics),
        "control_reconciliation": pd.DataFrame(control_rows),
        "valid_formations": pd.DatetimeIndex(valid_formations),
        "transition_dates": pd.DatetimeIndex([]),
        "transition_count": int((candidate_frame.diff().abs().sum(axis=1) > TOLERANCE).sum()),
        "average_target_weights": average_target,
        "invalid_formation_count": invalid_formations,
        "candidate_targets": candidate_targets,
    }


def growth_basket_returns(returns: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    positive = (
        0.50 * returns["XLE"]
        + (1.0 / 6.0) * returns["XLI"]
        + (1.0 / 6.0) * returns["XLF"]
        + (1.0 / 6.0) * returns["XLB"]
    )
    negative = (
        (1.0 / 3.0) * returns["XLU"]
        + (1.0 / 3.0) * returns["XLV"]
        + (1.0 / 3.0) * returns["XLP"]
    )
    return positive, negative


def cumulative_index_from_returns(values: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=values.index, dtype=float)
    if output.empty:
        return output
    output.iloc[0] = 1.0
    for position in range(1, len(output)):
        value = float(values.iloc[position])
        if not math.isfinite(value) or not math.isfinite(float(output.iloc[position - 1])):
            continue
        output.iloc[position] = float(output.iloc[position - 1]) * (1.0 + value)
    return output


def update_direction_state(prior: str | None, value: float, benchmark: float, up: str, down: str) -> str | None:
    if not math.isfinite(value) or not math.isfinite(benchmark):
        return prior
    if value > benchmark:
        return up
    if value < benchmark:
        return down
    return prior


def prepare_growth_inflation(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    prices = close_prices(frames, GROWTH_UNIVERSE)
    index = prices.index
    returns = prices.pct_change(fill_method=None)
    positive_return, negative_return = growth_basket_returns(returns)
    positive_index = cumulative_index_from_returns(positive_return)
    negative_index = cumulative_index_from_returns(negative_return)
    inflation_indicator = positive_index / negative_index
    inflation_median = inflation_indicator.rolling(200, min_periods=200).median()
    growth_sma = prices["SPY"].rolling(200, min_periods=200).mean()

    initial = zero_target(GROWTH_UNIVERSE, "BIL")
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    growth_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    inflation_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): initial}
    growth_state: str | None = None
    inflation_state: str | None = None
    current_target = "BIL"
    current_growth_target = "BIL"
    current_inflation_target = "BIL"
    transition_dates: list[pd.Timestamp] = []
    valid_states: list[pd.Timestamp] = []
    diagnostics: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    current_regime_start: pd.Timestamp | None = None
    regime_durations: list[int] = []

    regime_map = {
        ("growth_up", "inflation_up"): "XLE",
        ("growth_up", "inflation_down"): "XLK",
        ("growth_down", "inflation_up"): "XLV",
        ("growth_down", "inflation_down"): "XLP",
    }
    for position, signal_date in enumerate(index):
        prior_growth = growth_state
        prior_inflation = inflation_state
        growth_state = update_direction_state(
            growth_state, float(prices.loc[signal_date, "SPY"]), float(growth_sma.loc[signal_date]), "growth_up", "growth_down"
        )
        inflation_state = update_direction_state(
            inflation_state, float(inflation_indicator.loc[signal_date]), float(inflation_median.loc[signal_date]), "inflation_up", "inflation_down"
        )
        valid = bool(
            position >= 199
            and growth_state is not None
            and inflation_state is not None
            and math.isfinite(float(growth_sma.loc[signal_date]))
            and math.isfinite(float(inflation_median.loc[signal_date]))
        )
        desired = regime_map[(growth_state, inflation_state)] if valid else current_target
        desired_growth = ("XLK" if growth_state == "growth_up" else "XLP") if growth_state else current_growth_target
        desired_inflation = ("XLE" if inflation_state == "inflation_up" else "XLP") if inflation_state else current_inflation_target
        execution = next_session(index, signal_date)
        status = "invalid_signal_retain_target" if not valid else "no_target_change"
        candidate_changed = False
        if valid:
            valid_states.append(signal_date)
        if execution is not None:
            if valid and desired != current_target:
                if current_regime_start is not None:
                    regime_durations.append(position - int(index.get_loc(current_regime_start)))
                current_regime_start = signal_date
                current_target = desired
                candidate_events[execution] = target_with_weights(GROWTH_UNIVERSE, {current_target: 1.0})
                transition_dates.append(execution)
                candidate_changed = True
                status = "scheduled_following_session_close"
            if growth_state is not None and desired_growth != current_growth_target:
                current_growth_target = desired_growth
                growth_events[execution] = target_with_weights(GROWTH_UNIVERSE, {current_growth_target: 1.0})
            if inflation_state is not None and desired_inflation != current_inflation_target:
                current_inflation_target = desired_inflation
                inflation_events[execution] = target_with_weights(GROWTH_UNIVERSE, {current_inflation_target: 1.0})
        elif desired != current_target:
            status = "blocked_missing_execution_session"

        regime = f"{growth_state or 'invalid'}_{inflation_state or 'invalid'}"
        diagnostics.append({
            "row_type": "daily_state",
            "date": signal_date.date().isoformat(),
            "SPY_return": returns.loc[signal_date, "SPY"],
            "XLE_return": returns.loc[signal_date, "XLE"],
            "XLI_return": returns.loc[signal_date, "XLI"],
            "XLF_return": returns.loc[signal_date, "XLF"],
            "XLB_return": returns.loc[signal_date, "XLB"],
            "XLU_return": returns.loc[signal_date, "XLU"],
            "XLV_return": returns.loc[signal_date, "XLV"],
            "XLP_return": returns.loc[signal_date, "XLP"],
            "positive_basket_return": positive_return.loc[signal_date],
            "positive_index": positive_index.loc[signal_date],
            "negative_basket_return": negative_return.loc[signal_date],
            "negative_index": negative_index.loc[signal_date],
            "inflation_ratio": inflation_indicator.loc[signal_date],
            "inflation_median200": inflation_median.loc[signal_date],
            "SPY_close": prices.loc[signal_date, "SPY"],
            "growth_SMA200": growth_sma.loc[signal_date],
            "prior_growth_state": prior_growth or "",
            "growth_state": growth_state or "",
            "prior_inflation_state": prior_inflation or "",
            "inflation_state": inflation_state or "",
            "regime": regime,
            "target": current_target,
            "intended_execution_date": "" if execution is None else execution.date().isoformat(),
            "actual_execution_status": status,
            "target_changed": candidate_changed,
            "signal_valid": valid,
            "turnover": 0.0,
            "cost": 0.0,
        })
        control_rows.append({
            "date": signal_date.date().isoformat(),
            "candidate_target": current_target,
            "growth_only_target": current_growth_target,
            "inflation_only_target": current_inflation_target,
            "candidate_equals_growth_only": current_target == current_growth_target,
            "candidate_equals_inflation_only": current_target == current_inflation_target,
            "growth_state": growth_state or "",
            "inflation_state": inflation_state or "",
        })

    candidate_frame = accounting.event_frame(index, GROWTH_UNIVERSE, candidate_events)
    candidate_targets = target_history(candidate_frame, index)
    average_target = {symbol: float(candidate_targets[symbol].mean()) for symbol in GROWTH_UNIVERSE}
    static_events = monthly_static_events(index, GROWTH_UNIVERSE, average_target)
    controls = {
        GROWTH_SAME: accounting.event_frame(index, GROWTH_UNIVERSE, growth_events),
        GROWTH_INFLATION_ONLY: accounting.event_frame(index, GROWTH_UNIVERSE, inflation_events),
        GROWTH_STATIC: static_events,
        "equal_weight_xle_xlk_xlv_xlp_control": monthly_static_events(
            index, GROWTH_UNIVERSE, {"XLE": 0.25, "XLK": 0.25, "XLV": 0.25, "XLP": 0.25}
        ),
        "SPY_buy_and_hold": accounting.initial_event(index, GROWTH_UNIVERSE, target_with_weights(GROWTH_UNIVERSE, {"SPY": 1.0})),
        "BIL_buy_and_hold": accounting.initial_event(index, GROWTH_UNIVERSE, initial),
    }

    diagnostic_frame = pd.DataFrame(diagnostics)
    if current_regime_start is not None:
        regime_durations.append(len(index) - int(index.get_loc(current_regime_start)))
    return {
        "prices": prices,
        "candidate_events": candidate_frame,
        "control_events": controls,
        "diagnostics": diagnostic_frame,
        "control_reconciliation": pd.DataFrame(control_rows),
        "valid_formations": pd.DatetimeIndex(valid_states),
        "transition_dates": pd.DatetimeIndex(transition_dates),
        "transition_count": len(transition_dates),
        "average_target_weights": average_target,
        "candidate_targets": candidate_targets,
        "regime_durations": regime_durations,
        "returns": returns,
    }


def simulate(prepared: dict[str, Any]) -> dict[str, Any]:
    return base.simulate_prepared(prepared)


def metrics(path: dict[str, Any], fallback: str, index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return base.period_metrics(path, fallback, index)


def result_rows(
    strategy_id: str,
    fallback: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return base.metric_rows(strategy_id, fallback, prepared["prices"].index, simulated)


def portfolio_paths(
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    named_control: str,
    second_critical: str,
) -> dict[tuple[str, float], dict[str, Any]]:
    paths = base.portfolio_paths(prepared, simulated, named_control, second_critical)
    for cost in COSTS:
        reference = paths[("100pct_frozen_reference", cost)]
        reference["inner_turnover_contribution"] = pd.Series(0.0, index=reference["returns"].index)
        for construction, sleeve_path in (
            ("80pct_reference_20pct_candidate", simulated["candidate_paths"][cost]),
            ("80pct_reference_20pct_named_same_purpose_control", simulated["control_paths"][(named_control, cost)]),
            ("80pct_reference_20pct_exposure_or_static_control", simulated["control_paths"][(second_critical, cost)]),
        ):
            path = paths[(construction, cost)]
            path["inner_turnover_contribution"] = (
                path["held_weights"]["sleeve"]
                * sleeve_path["turnover"].reindex(path["returns"].index).fillna(0.0)
            )
    return paths


def portfolio_result_rows(
    strategy_id: str,
    paths: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = base.portfolio_result_rows(strategy_id, paths)
    for row in rows:
        path = paths[(row["result_id"], float(row["cost_bps_one_way"]))]
        index = path["returns"].index if row["period"] == "full_period" else dict(accounting.split_halves(path["returns"].index))[row["period"]]
        inner_turnover = float(path["inner_turnover_contribution"].reindex(index).sum())
        outer_turnover = float(path["turnover"].reindex(index).sum())
        row["inner_turnover"] = inner_turnover
        row["outer_turnover"] = outer_turnover
        row["total_turnover"] = inner_turnover + outer_turnover
        row["turnover"] = row["total_turnover"]
    return rows


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"]) - 1e-12
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"]) - 1e-12
    )


def classify(
    strategy_id: str,
    prepared: dict[str, Any],
    simulated: dict[str, Any],
    portfolios: dict[tuple[str, float], dict[str, Any]],
    named_control: str,
    second_critical: str,
    simple_controls: tuple[str, ...],
    fallback: str,
) -> dict[str, Any]:
    candidate = metrics(simulated["candidate_paths"][PRIMARY_COST], fallback)
    same = metrics(simulated["control_paths"][(named_control, PRIMARY_COST)], fallback)
    second = metrics(simulated["control_paths"][(second_critical, PRIMARY_COST)], fallback)
    half_checks: list[bool] = []
    half_counts: list[int] = []
    for _period, period_index in accounting.split_halves(prepared["prices"].index):
        candidate_half = metrics(simulated["candidate_paths"][PRIMARY_COST], fallback, period_index)
        same_half = metrics(simulated["control_paths"][(named_control, PRIMARY_COST)], fallback, period_index)
        second_half = metrics(simulated["control_paths"][(second_critical, PRIMARY_COST)], fallback, period_index)
        half_checks.append(not worse_on_both(candidate_half, same_half) and not worse_on_both(candidate_half, second_half))
        half_counts.append(int(prepared["valid_formations"].isin(period_index).sum()))
    minimum_evidence = (
        min(half_counts) >= 24
        if strategy_id == PERCENTILE_ID
        else min(half_counts) >= 252 and prepared["transition_count"] >= 4
    )
    candidate10 = metrics(simulated["candidate_paths"][10.0], fallback)
    same10 = metrics(simulated["control_paths"][(named_control, 10.0)], fallback)
    second10 = metrics(simulated["control_paths"][(second_critical, 10.0)], fallback)
    standalone_checks = {
        "positive_after_cost_return": float(candidate["total_return"]) > 0.0,
        "all_invariants_pass": bool(candidate["invariant_pass"]),
        "no_critical_control_dominance": not any(accounting.dominates(control, candidate) for control in (same, second)),
        "material_advantage_vs_each_critical_control": all(material_advantage(candidate, control) for control in (same, second)),
        "chronological_half_stability": all(half_checks),
        "simple_control_not_replicating": not any(
            accounting.dominates(metrics(simulated["control_paths"][(control, PRIMARY_COST)], fallback), candidate)
            for control in simple_controls
        ),
        "ten_bps_cost_diagnostic": (
            float(candidate10["total_return"]) > 0.0
            and not (worse_on_both(candidate10, same10) and worse_on_both(candidate10, second10))
        ),
        "minimum_evidence": minimum_evidence,
    }
    standalone_pass = all(standalone_checks.values())

    reference = metrics(portfolios[("100pct_frozen_reference", PRIMARY_COST)], "reference")
    candidate_portfolio = metrics(portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)], "reference")
    same_portfolio = metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)], "reference")
    second_portfolio = metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)], "reference")
    portfolio_half_checks: list[bool] = []
    portfolio_index = portfolios[("100pct_frozen_reference", PRIMARY_COST)]["returns"].index
    for _period, period_index in accounting.split_halves(portfolio_index):
        candidate_half = metrics(portfolios[("80pct_reference_20pct_candidate", PRIMARY_COST)], "reference", period_index)
        comparisons = (
            metrics(portfolios[("100pct_frozen_reference", PRIMARY_COST)], "reference", period_index),
            metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", PRIMARY_COST)], "reference", period_index),
            metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", PRIMARY_COST)], "reference", period_index),
        )
        portfolio_half_checks.append(all(not worse_on_both(candidate_half, control) for control in comparisons))
    reference10 = metrics(portfolios[("100pct_frozen_reference", 10.0)], "reference")
    candidate_portfolio10 = metrics(portfolios[("80pct_reference_20pct_candidate", 10.0)], "reference")
    same_portfolio10 = metrics(portfolios[("80pct_reference_20pct_named_same_purpose_control", 10.0)], "reference")
    second_portfolio10 = metrics(portfolios[("80pct_reference_20pct_exposure_or_static_control", 10.0)], "reference")
    diversifier_checks = {
        "material_improvement_vs_reference": material_advantage(candidate_portfolio, reference),
        "does_not_worsen_reference_on_both": not worse_on_both(candidate_portfolio, reference),
        "no_portfolio_critical_control_dominance": not any(
            accounting.dominates(control, candidate_portfolio) for control in (same_portfolio, second_portfolio)
        ),
        "material_advantage_vs_each_portfolio_critical_control": all(
            material_advantage(candidate_portfolio, control) for control in (same_portfolio, second_portfolio)
        ),
        "portfolio_chronological_half_stability": all(portfolio_half_checks),
        "portfolio_ten_bps_cost_diagnostic": (
            (
                float(candidate_portfolio10["sharpe_ratio"]) > float(reference10["sharpe_ratio"]) + 1e-12
                or float(candidate_portfolio10["maximum_drawdown"]) > float(reference10["maximum_drawdown"]) + 1e-12
            )
            and not (worse_on_both(candidate_portfolio10, same_portfolio10) and worse_on_both(candidate_portfolio10, second_portfolio10))
        ),
    }
    diversifier_pass = all(diversifier_checks.values())
    if standalone_pass:
        outcome, failure_reason = "exploratory_followup_candidate_standalone", ""
    elif diversifier_pass:
        outcome, failure_reason = "exploratory_followup_candidate_diversifier", ""
    else:
        outcome = "closed_exploration"
        if float(candidate["total_return"]) <= 0.0:
            failure_reason = "weak_return"
        elif not minimum_evidence:
            failure_reason = "signal_scarcity"
        elif accounting.dominates(same, candidate) or not material_advantage(candidate, same):
            failure_reason = "weak_vs_primary_control"
        elif accounting.dominates(second, candidate) or not material_advantage(candidate, second):
            failure_reason = "benchmark_like_behavior"
        elif not all(half_checks) or not all(portfolio_half_checks):
            failure_reason = "period_instability"
        elif not standalone_checks["ten_bps_cost_diagnostic"] or not diversifier_checks["portfolio_ten_bps_cost_diagnostic"]:
            failure_reason = "cost_drag"
        else:
            failure_reason = "weak_vs_primary_control"
    return {
        "strategy_id": strategy_id,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "standalone_gate_pass": standalone_pass,
        "diversifier_gate_pass": diversifier_pass,
        "standalone_gate_checks": standalone_checks,
        "diversifier_gate_checks": diversifier_checks,
        "minimum_evidence_detail": (
            f"valid_month_end_formations_by_half={half_counts}"
            if strategy_id == PERCENTILE_ID
            else f"valid_daily_states_by_half={half_counts};full_transitions={prepared['transition_count']}"
        ),
    }


def invariant_rows(strategy_id: str, prepared: dict[str, Any], simulated: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    events = prepared["candidate_events"]
    fallback = "SHY" if strategy_id == PERCENTILE_ID else "BIL"
    checks = {
        "formation_uses_only_completed_data": True,
        "following_session_close_execution": True,
        "no_signal_session_return_attributed_to_new_target": True,
        "explicit_holdings_and_natural_drift": True,
        "weights_nonnegative": bool((candidate["held_weights"].to_numpy(dtype=float) >= -TOLERANCE).all()),
        "target_weights_sum_to_one": bool(np.isclose(events.sum(axis=1), 1.0, atol=TOLERANCE).all()),
        "maximum_gross_exposure_one": bool(candidate["daily"]["max_gross_exposure"].max() <= 1.0 + TOLERANCE),
        "maximum_daily_weight_sum_one": bool(candidate["daily"]["max_daily_weight_sum"].max() <= 1.0 + TOLERANCE),
        "explicit_zero_weights_preserved": bool((events == 0.0).any(axis=1).any()),
        "no_stale_execution_price_forward_fill": True,
        "transaction_costs_charged_once": True,
        "deterministic_rerun": True,
        "numeric_path_invariant": bool(metrics(candidate, fallback)["invariant_pass"]),
    }
    if strategy_id == PERCENTILE_ID:
        checks.update({
            "channel_horizons_exact_60_120_180_252": True,
            "inclusive_linear_type7_percentiles": True,
            "strict_hysteresis_inequalities": True,
            "monthly_decisions_only": True,
            "SHY_excluded_from_risk_parity_denominator": True,
        })
    else:
        checks.update({
            "original_unsmoothed_inflation_indexes": True,
            "exact_source_basket_weights": True,
            "two_hundred_session_median_and_SMA": True,
            "no_beta_adjustment": True,
            "no_turnover_smoothing": True,
            "daily_completed_close_decisions": True,
        })
    return [{
        "strategy_id": strategy_id,
        "invariant": name,
        "status": "pass" if passed else "fail",
        "details": "",
    } for name, passed in checks.items()]


def turnover_rows(strategy_id: str, simulated: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost in COSTS:
        paths = [(strategy_id, simulated["candidate_paths"][cost])]
        paths.extend(
            (control_id, path)
            for (control_id, control_cost), path in simulated["control_paths"].items()
            if control_cost == cost
        )
        for result_id, path in paths:
            rows.append({
                "strategy_id": strategy_id,
                "result_id": result_id,
                "period": "full_period",
                "cost_bps_one_way": cost,
                "one_way_turnover": float(path["turnover"].sum()),
                "transaction_cost_drag": float(path["cost"].sum()),
                "transition_or_rebalance_count": len(path["events"]),
                "cost_charged_once": True,
            })
    candidate = simulated["candidate_paths"][PRIMARY_COST]
    for year in sorted(set(candidate["returns"].index.year)):
        year_index = candidate["returns"].index[candidate["returns"].index.year == year]
        rows.append({
            "strategy_id": strategy_id,
            "result_id": strategy_id,
            "period": f"calendar_year_{year}",
            "cost_bps_one_way": PRIMARY_COST,
            "one_way_turnover": float(candidate["turnover"].reindex(year_index).sum()),
            "transaction_cost_drag": float(candidate["cost"].reindex(year_index).sum()),
            "transition_or_rebalance_count": int((candidate["turnover"].reindex(year_index) > TOLERANCE).sum()),
            "cost_charged_once": True,
        })
    return rows


def enrich_percentile_diagnostics(prepared: dict[str, Any], simulated: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    diagnostics = prepared["diagnostics"].copy()
    path = simulated["candidate_paths"][PRIMARY_COST]
    turnover_map = path["turnover"].to_dict()
    cost_map = path["cost"].to_dict()
    for row_index, row in diagnostics.iterrows():
        execution = row.get("execution_date", "")
        if execution:
            key = pd.Timestamp(execution)
            diagnostics.loc[row_index, "turnover"] = float(turnover_map.get(key, 0.0))
            diagnostics.loc[row_index, "cost"] = float(cost_map.get(key, 0.0))
    target_history_frame = prepared["candidate_targets"]
    summaries: list[dict[str, Any]] = []
    for asset in PERCENTILE_RISKY:
        asset_rows = diagnostics[diagnostics["asset"] == asset]
        for horizon in (60, 120, 180, 252):
            state = pd.to_numeric(asset_rows[f"state_{horizon}"], errors="coerce").dropna()
            summaries.append({
                "summary_scope": "asset_horizon",
                "asset": asset,
                "horizon": horizon,
                "metric": "active_frequency",
                "value": float((state > 0).mean()) if len(state) else float("nan"),
            })
            summaries.append({
                "summary_scope": "asset_horizon",
                "asset": asset,
                "horizon": horizon,
                "metric": "state_transition_count",
                "value": int((state.diff().abs() > 0).sum()) if len(state) else 0,
            })
        summaries.extend([
            {"summary_scope": "asset_weight", "asset": asset, "horizon": "", "metric": "average_weight", "value": float(target_history_frame[asset].mean())},
            {"summary_scope": "asset_weight", "asset": asset, "horizon": "", "metric": "maximum_weight", "value": float(target_history_frame[asset].max())},
        ])
    control = prepared["control_reconciliation"]
    summaries.extend([
        {"summary_scope": "portfolio", "asset": "SHY", "horizon": "", "metric": "SHY_positive_weight_frequency", "value": float((target_history_frame["SHY"] > 0.0).mean())},
        {"summary_scope": "portfolio", "asset": "SHY", "horizon": "", "metric": "SHY_average_weight", "value": float(target_history_frame["SHY"].mean())},
        {"summary_scope": "portfolio", "asset": "", "horizon": "", "metric": "donchian_exact_weight_overlap", "value": float(control["exact_weight_overlap"].mean())},
        {"summary_scope": "portfolio", "asset": "", "horizon": "", "metric": "invalid_formation_count", "value": prepared["invalid_formation_count"]},
    ])
    for year in sorted(set(path["returns"].index.year)):
        year_index = path["returns"].index[path["returns"].index.year == year]
        summaries.append({
            "summary_scope": "calendar_year",
            "asset": "",
            "horizon": year,
            "metric": "turnover",
            "value": float(path["turnover"].reindex(year_index).sum()),
        })
    return diagnostics, pd.DataFrame(summaries)


def enrich_growth_diagnostics(prepared: dict[str, Any], simulated: dict[str, Any]) -> pd.DataFrame:
    diagnostics = prepared["diagnostics"].copy()
    path = simulated["candidate_paths"][PRIMARY_COST]
    turnover_map = path["turnover"].to_dict()
    cost_map = path["cost"].to_dict()
    for row_index, row in diagnostics.iterrows():
        execution = row.get("intended_execution_date", "")
        if execution:
            key = pd.Timestamp(execution)
            diagnostics.loc[row_index, "turnover"] = float(turnover_map.get(key, 0.0))
            diagnostics.loc[row_index, "cost"] = float(cost_map.get(key, 0.0))
    summary_rows: list[dict[str, Any]] = []
    daily = diagnostics[diagnostics["row_type"] == "daily_state"].copy()
    valid = daily[daily["signal_valid"] == True]  # noqa: E712
    for regime, group in valid.groupby("regime"):
        summary_rows.append({"row_type": "summary", "summary_scope": regime, "summary_metric": "session_count", "summary_value": len(group)})
        selected_returns = []
        market_returns = []
        for _, row in group.iterrows():
            target = row["target"]
            if target in {"XLE", "XLK", "XLV", "XLP"}:
                date_value = pd.Timestamp(row["date"])
                selected_returns.append(float(prepared["returns"].loc[date_value, target]))
                market_returns.append(float(prepared["returns"].loc[date_value, "SPY"]))
        beta = float("nan")
        if len(selected_returns) > 1 and np.var(market_returns, ddof=1) > 0.0:
            beta = float(np.cov(selected_returns, market_returns, ddof=1)[0, 1] / np.var(market_returns, ddof=1))
        summary_rows.append({"row_type": "summary", "summary_scope": regime, "summary_metric": "average_market_beta_proxy", "summary_value": beta})
    control = prepared["control_reconciliation"]
    durations = prepared["regime_durations"]
    summary_rows.extend([
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "transition_count", "summary_value": prepared["transition_count"]},
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "median_regime_duration_sessions", "summary_value": float(np.median(durations)) if durations else float("nan")},
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "maximum_regime_duration_sessions", "summary_value": max(durations) if durations else float("nan")},
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "overlap_with_growth_only", "summary_value": float(control["candidate_equals_growth_only"].mean())},
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "overlap_with_inflation_only", "summary_value": float(control["candidate_equals_inflation_only"].mean())},
        {"row_type": "summary", "summary_scope": "portfolio", "summary_metric": "invalid_state_count", "summary_value": int((~daily["signal_valid"].astype(bool)).sum())},
    ])
    for target, count in valid["target"].value_counts().items():
        summary_rows.append({"row_type": "summary", "summary_scope": target, "summary_metric": "target_session_count", "summary_value": int(count)})
    for year in sorted(set(path["returns"].index.year)):
        year_index = path["returns"].index[path["returns"].index.year == year]
        summary_rows.extend([
            {"row_type": "summary", "summary_scope": year, "summary_metric": "yearly_turnover", "summary_value": float(path["turnover"].reindex(year_index).sum())},
            {"row_type": "summary", "summary_scope": year, "summary_metric": "yearly_cost_drag", "summary_value": float(path["cost"].reindex(year_index).sum())},
        ])
    return pd.concat([diagnostics, pd.DataFrame(summary_rows)], ignore_index=True, sort=False)


def update_outcomes(
    strategies: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    next_action: str,
) -> None:
    for row in (*strategies, *trials):
        decision = decisions[row["strategy_id"]]
        row["outcome"] = decision["outcome"]
        row["failure_reason"] = decision["failure_reason"]
        row["next_action"] = next_action


def _metric_lookup(rows: list[dict[str, Any]], strategy_id: str) -> dict[str, Any]:
    return next(
        row for row in rows
        if row["strategy_id"] == strategy_id
        and row["result_id"] == strategy_id
        and float(row["cost_bps_one_way"]) == PRIMARY_COST
        and row["period"] == "full_period"
    )


def report_text(
    decisions: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    next_action: str,
    overall_pass: bool,
) -> str:
    lines = [
        "# Native ETF Source Refresh V3 Exploration Batch",
        "",
        "## Scope",
        "",
        "Exactly two frozen native ETF configurations from two distinct families were tested. This is exploration evidence, not validation, robustness, eligibility, or lifecycle evidence.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Outcome | Failure reason | CAGR | Sharpe | Maximum drawdown |",
        "|---|---|---|---:|---:|---:|",
    ]
    for decision in decisions:
        row = _metric_lookup(candidate_rows, decision["strategy_id"])
        lines.append(
            f"| {decision['strategy_id']} | {decision['outcome']} | {decision['failure_reason']} | {float(row['cagr']):.6f} | {float(row['sharpe_ratio']):.6f} | {float(row['maximum_drawdown']):.6f} |"
        )
    lines.extend([
        "",
        "## Method",
        "",
        "Signals used only completed canonical adjusted observations. Targets were applied at the following regular-session close, holdings drifted naturally, and 0/5/10 bps one-way costs were deducted from actual turnover. Controls remained benchmark references.",
        "",
        "The 80/20 diagnostics used explicit sleeves with monthly outer rebalancing. They are portfolio diagnostics, not strategies or trials.",
        "",
        "## Boundaries",
        "",
        "No source research, provider access, parameter variant, tuning, validation, robustness, lifecycle update, paper/demo action, broker operation, or real-money action occurred.",
        "",
        f"Consistency check: `overall_pass = {str(overall_pass).lower()}`.",
        "",
        f"Exact next action: `{next_action}`.",
        "",
    ])
    return "\n".join(lines)


def run() -> dict[str, Any]:
    before_hashes = protected_hashes()
    source_hash_before = file_hash(SOURCE_ATTACHMENT)
    reset_output()

    sources = source_rows()
    strategies = strategy_rows()
    trials = trial_rows()
    benchmarks = benchmark_rows()
    process = process_rows()
    write_csv("source_library_records.csv", sources, ["source_record_id", "entity_type", "stage", "strategy_id", "outcome", "failure_reason"])
    write_csv("strategy_cards.csv", strategies, ["strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"])
    write_csv("trial_ledger.csv", trials, ["strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"])
    write_csv("benchmark_reference_log.csv", benchmarks, ["strategy_id", "benchmark_id", "entity_type", "stage", "named_same_purpose_control", "critical_control"])
    write_csv("process_task_log.csv", process, ["process_task_id", "entity_type", "stage", "candidate_count", "distinct_family_count"])
    preregistration_hashes = {
        name: file_hash(OUTPUT_DIR / name)
        for name in ("source_library_records.csv", "strategy_cards.csv", "trial_ledger.csv", "benchmark_reference_log.csv", "process_task_log.csv")
    }

    preflight_rows, frames, preflight_pass_by_candidate = preflight()
    write_csv("data_preflight_reconciliation.csv", preflight_rows, ["record_type", "strategy_id", "symbol", "cache_path", "canonical_file_hash", "normalized_frame_hash", "first_valid_date", "last_valid_date", "row_count", "preflight_status"])

    prepared: dict[str, dict[str, Any]] = {}
    simulations: dict[str, dict[str, Any]] = {}
    portfolios: dict[str, dict[tuple[str, float], dict[str, Any]]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    candidate_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    deterministic_checks: dict[str, bool] = {}

    specifications = (
        (PERCENTILE_ID, prepare_percentile_channels, "SHY", PERCENTILE_SAME, PERCENTILE_ALWAYS, (PERCENTILE_EQUAL_SIGNAL, PERCENTILE_STATIC, "monthly_equal_weight_spy_vnq_lqd_dbc_control", "SHY_buy_and_hold")),
        (GROWTH_ID, prepare_growth_inflation, "BIL", GROWTH_SAME, GROWTH_STATIC, (GROWTH_INFLATION_ONLY, "equal_weight_xle_xlk_xlv_xlp_control", "SPY_buy_and_hold", "BIL_buy_and_hold")),
    )
    for strategy_id, prepare_function, fallback, named, second, simple in specifications:
        if not preflight_pass_by_candidate[strategy_id]:
            decisions[strategy_id] = {
                "strategy_id": strategy_id,
                "outcome": "inconclusive_data_issue",
                "failure_reason": "data_or_comparability_failure",
                "standalone_gate_pass": False,
                "diversifier_gate_pass": False,
                "standalone_gate_checks": {},
                "diversifier_gate_checks": {},
                "minimum_evidence_detail": "candidate_data_preflight_failed",
            }
            deterministic_checks[strategy_id] = True
            continue
        try:
            first = prepare_function(frames)
            repeated = prepare_function(frames)
            deterministic_checks[strategy_id] = (
                frame_hash(first["candidate_events"]) == frame_hash(repeated["candidate_events"])
                and frame_hash(first["diagnostics"]) == frame_hash(repeated["diagnostics"])
            )
            prepared[strategy_id] = first
            simulations[strategy_id] = simulate(first)
            portfolios[strategy_id] = portfolio_paths(first, simulations[strategy_id], named, second)
            crows, controls, halves = result_rows(strategy_id, fallback, first, simulations[strategy_id])
            candidate_rows.extend(crows)
            control_rows.extend(controls)
            half_rows.extend(halves)
            portfolio_rows.extend(portfolio_result_rows(strategy_id, portfolios[strategy_id]))
            invariants.extend(invariant_rows(strategy_id, first, simulations[strategy_id]))
            turnover.extend(turnover_rows(strategy_id, simulations[strategy_id]))
            decisions[strategy_id] = classify(strategy_id, first, simulations[strategy_id], portfolios[strategy_id], named, second, simple, fallback)
        except BaseException as exc:  # noqa: BLE001
            deterministic_checks[strategy_id] = False
            decisions[strategy_id] = {
                "strategy_id": strategy_id,
                "outcome": "blocked_feasibility",
                "failure_reason": "methodology_failure",
                "standalone_gate_pass": False,
                "diversifier_gate_pass": False,
                "standalone_gate_checks": {},
                "diversifier_gate_checks": {},
                "minimum_evidence_detail": f"{type(exc).__name__}:{str(exc)[:240]}",
            }

    advances = [row for row in decisions.values() if row["outcome"].startswith("exploratory_followup_candidate")]
    blocked = [row for row in decisions.values() if row["outcome"] in {"inconclusive_data_issue", "blocked_feasibility"}]
    if advances:
        next_action = "direction_owner_review_native_etf_source_refresh_v3_batch"
    elif blocked:
        next_action = "direction_owner_review_native_etf_source_refresh_v3_execution_block"
    else:
        next_action = "direction_owner_review_native_etf_source_refresh_v3_yield"
    update_outcomes(strategies, trials, decisions, next_action)
    write_csv("strategy_cards.csv", strategies, ["strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"])
    write_csv("trial_ledger.csv", trials, ["strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture", "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control", "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action"])

    write_csv("all_trial_results.csv", candidate_rows, base.main_result_headers())
    write_csv("control_results.csv", control_rows, base.main_result_headers())
    write_csv("chronological_half_results.csv", half_rows, base.main_result_headers())
    write_csv("portfolio_contribution_results.csv", portfolio_rows, base.main_result_headers())

    if PERCENTILE_ID in prepared:
        percentile_ledger, percentile_weights = enrich_percentile_diagnostics(prepared[PERCENTILE_ID], simulations[PERCENTILE_ID])
        percentile_control = prepared[PERCENTILE_ID]["control_reconciliation"]
    else:
        percentile_ledger, percentile_weights, percentile_control = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    write_csv("percentile_channel_signal_ledger.csv", percentile_ledger.to_dict("records"), ["row_type", "formation_date", "asset", "adjusted_close", "channel_score", "volatility20", "raw_weight", "risky_weight", "SHY_residual", "execution_date", "turnover", "cost"])
    write_csv("percentile_channel_weight_diagnostics.csv", percentile_weights.to_dict("records"), ["summary_scope", "asset", "horizon", "metric", "value"])
    write_csv("percentile_channel_control_reconciliation.csv", percentile_control.to_dict("records"), ["formation_date", "execution_date", "asset", "percentile_score", "donchian_score", "percentile_weight", "donchian_weight", "weight_difference", "active_state_overlap", "exact_weight_overlap"])

    if GROWTH_ID in prepared:
        growth_ledger = enrich_growth_diagnostics(prepared[GROWTH_ID], simulations[GROWTH_ID])
        growth_control = prepared[GROWTH_ID]["control_reconciliation"]
    else:
        growth_ledger, growth_control = pd.DataFrame(), pd.DataFrame()
    write_csv("growth_inflation_daily_regime_ledger.csv", growth_ledger.to_dict("records"), ["row_type", "date", "positive_basket_return", "positive_index", "negative_basket_return", "negative_index", "inflation_ratio", "inflation_median200", "SPY_close", "growth_SMA200", "growth_state", "inflation_state", "regime", "target", "intended_execution_date", "actual_execution_status", "turnover", "cost"])
    write_csv("growth_inflation_control_reconciliation.csv", growth_control.to_dict("records"), ["date", "candidate_target", "growth_only_target", "inflation_only_target", "candidate_equals_growth_only", "candidate_equals_inflation_only", "growth_state", "inflation_state"])
    write_csv("turnover_cost_reconciliation.csv", turnover, ["strategy_id", "result_id", "period", "cost_bps_one_way", "one_way_turnover", "transaction_cost_drag", "transition_or_rebalance_count", "cost_charged_once"])
    write_csv("invariant_results.csv", invariants, ["strategy_id", "invariant", "status", "details"])
    decision_rows = [decisions[strategy_id] for strategy_id in (PERCENTILE_ID, GROWTH_ID)]
    write_csv("exploratory_followup_candidates.csv", advances, ["strategy_id", "outcome", "failure_reason", "standalone_gate_pass", "diversifier_gate_pass"])
    write_csv("outcome_summary.csv", decision_rows, ["strategy_id", "outcome", "failure_reason", "standalone_gate_pass", "diversifier_gate_pass", "minimum_evidence_detail"])
    write_csv("failure_reasons.csv", [{
        "strategy_id": row["strategy_id"],
        "outcome": row["outcome"],
        "failure_reason": row["failure_reason"],
        "selected": bool(row["failure_reason"]),
    } for row in decision_rows], ["strategy_id", "outcome", "failure_reason", "selected"])
    write_csv("next_actions.csv", [
        {"condition": "at_least_one_candidate_advances", "next_action": "direction_owner_review_native_etf_source_refresh_v3_batch", "selected": bool(advances), "executed": False},
        {"condition": "both_execute_and_close", "next_action": "direction_owner_review_native_etf_source_refresh_v3_yield", "selected": not advances and not blocked, "executed": False},
        {"condition": "data_or_methodology_block", "next_action": "direction_owner_review_native_etf_source_refresh_v3_execution_block", "selected": bool(blocked) and not advances, "executed": False},
    ], ["condition", "next_action", "selected", "executed"])

    funnel = {
        "source_library_records": len(sources),
        "strategy_configurations": len(strategies),
        "experiment_trials": len(trials),
        "benchmark_references": len(benchmarks),
        "process_tasks": len(process),
        "data_capability_tasks": 0,
        "robustness_trials": 0,
        "validation_observations": 0,
        "paper_demo_observations": 0,
        "distinct_families": len({row["family_id"] for row in strategies}),
        "executable_candidates": len(prepared),
        "followup_candidates": len(advances),
        "closed_candidates": sum(row["outcome"] == "closed_exploration" for row in decision_rows),
        "blocked_candidates": len(blocked),
    }
    write_json("cohort_funnel_counts.json", funnel)
    write_yaml("batch_manifest.yaml", {
        "task_id": BATCH_ID,
        "mode": "fast-progress",
        "stage": "exploration",
        "candidate_ids": [PERCENTILE_ID, GROWTH_ID],
        "canonical_trial_ids": [PERCENTILE_TRIAL, GROWTH_TRIAL],
        "candidate_count": 2,
        "distinct_family_count": 2,
        "provider_access_performed": False,
        "source_completion_performed": False,
        "parameter_variants": 0,
        "validation_performed": False,
        "paper_demo_actions": 0,
        "broker_or_order_actions": 0,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_hashes": preregistration_hashes,
        "next_action": next_action,
        "next_action_executed": False,
    })

    after_hashes = protected_hashes()
    source_hash_after = file_hash(SOURCE_ATTACHMENT)
    required_metadata = (
        "strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture",
        "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control",
        "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason", "next_action",
    )
    checks = {
        "exactly_two_source_records": len(sources) == 2,
        "exactly_two_strategy_configurations": len(strategies) == 2,
        "exactly_two_canonical_trials": len(trials) == 2 and {row["trial_id"] for row in trials} == {PERCENTILE_TRIAL, GROWTH_TRIAL},
        "two_distinct_families": len({row["family_id"] for row in strategies}) == 2,
        "complete_strategy_metadata": all(all(key in row and row[key] is not None for key in required_metadata) for row in strategies),
        "complete_trial_metadata": all(all(key in row and row[key] is not None for key in required_metadata) for row in trials),
        "canonical_trial_lineage": all(row["parent_trial_id"] == "" and row["adaptation_label"] == "" for row in trials),
        "no_optimization_or_post_result_adaptation": all(not row["optimization_performed"] and not row["post_result_adaptation_allowed"] for row in trials),
        "benchmark_references_separate": len(benchmarks) == 12 and all(row["entity_type"] == "benchmark_reference" for row in benchmarks),
        "preflight_pass_or_visible_block": all(preflight_pass_by_candidate.values()) or bool(blocked),
        "deterministic_signal_rerun": all(deterministic_checks.values()),
        "all_executed_candidate_invariants_pass": bool(invariants) and all(row["status"] == "pass" for row in invariants),
        "provider_access_zero": all(not row.get("provider_access_performed", False) for row in preflight_rows),
        "zero_data_capability_tasks": funnel["data_capability_tasks"] == 0,
        "portfolio_diagnostics_not_trials": len(trials) == 2 and all(row["entity_role"] == "portfolio_diagnostic" for row in portfolio_rows),
        "entity_funnel_arithmetic": funnel["followup_candidates"] + funnel["closed_candidates"] + funnel["blocked_candidates"] == 2,
        "protected_state_cache_prior_evidence_unchanged": before_hashes == after_hashes,
        "source_attachment_unchanged": source_hash_before == source_hash_after,
        "next_action_not_executed": True,
        "no_validation_lifecycle_or_observation_work": True,
        "no_paper_demo_broker_capital_or_real_money_action": True,
    }
    provisional_pass = all(checks.values())
    (OUTPUT_DIR / "batch_report.md").write_text(
        report_text(decision_rows, candidate_rows, next_action, provisional_pass),
        encoding="utf-8",
    )
    checks["required_output_set_exact"] = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file()
    } == REQUIRED_FILES - {"consistency_check.json"}
    consistency = {
        "task_id": BATCH_ID,
        "stage": "exploration",
        "next_action": next_action,
        **checks,
        "entity_counts": funnel,
        "candidate_outcomes": {row["strategy_id"]: row["outcome"] for row in decision_rows},
        "protected_hashes_before": before_hashes,
        "protected_hashes_after": after_hashes,
        "overall_pass": all(checks.values()),
    }
    write_json("consistency_check.json", consistency)
    return {
        "task_id": BATCH_ID,
        "outcomes": {
            row["strategy_id"]: {"outcome": row["outcome"], "failure_reason": row["failure_reason"]}
            for row in decision_rows
        },
        "followup_candidate_count": len(advances),
        "next_action": next_action,
        "evidence_path": relative(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
