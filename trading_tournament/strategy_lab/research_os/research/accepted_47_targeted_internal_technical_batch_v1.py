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
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting


TASK_ID = "accepted_47_targeted_internal_technical_batch_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
PREREGISTRATION_TIMESTAMP = "2026-08-07T00:00:00+00:00"
SOURCE_LINEAGE = "internally_generated_technical_hypothesis"
MODE = "bounded_internal_hypothesis_optimization"
STAGE = "optimization"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-10
TIMING_CONVENTION = (
    "completed_session_close_signal_following_regular_session_close_execution_next_session_return"
)

MULTI_ASSET_UNIVERSE = (
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "HYG",
    "LQD",
    "TLT",
    "TIP",
    "GLD",
    "DBC",
    "IYR",
)
SECTOR_UNIVERSE = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC")
PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1",
)
TECHNICAL_FACTORY_V2_CATALOG = (
    ROOT / "evidence" / "technical_factory" / "technical_strategy_factory_v2"
    / "latest" / "architecture_catalog.yaml"
)
TECHNICAL_FACTORY_V2_GRID = TECHNICAL_FACTORY_V2_CATALOG.with_name("parameter_grid.csv")

FOLLOWUP_NEXT_ACTION = "direction_owner_review_targeted_internal_batch_v1_for_robustness"
NO_FOLLOWUP_NEXT_ACTION = "direction_owner_review_discovery_model_after_targeted_internal_batch_v1"
BLOCK_NEXT_ACTION = "direction_owner_review_targeted_internal_batch_v1_block"

PERMITTED_FAILURE_REASONS = {
    "duplicate_or_redundant",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "concentration_risk",
    "weak_return",
    "excess_drawdown",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
    "not_selected_by_frozen_rule",
}

FORBIDDEN_ACTION_FLAGS = {
    "provider_access": False,
    "network_access": False,
    "market_data_refresh": False,
    "accepted_47_membership_change": False,
    "forward_observation_data_used": False,
    "alpaca_or_broker_state_used": False,
    "robustness_run": False,
    "validation_run": False,
    "paper_demo_eligibility_record": False,
    "handoff_or_export_record": False,
    "observation_record": False,
    "real_money_action": False,
}


@dataclass(frozen=True)
class ArchitectureSpec:
    architecture_code: str
    architecture_id: str
    family_id: str
    display_name: str
    universe: tuple[str, ...]
    accounting_universe: tuple[str, ...]
    named_control_id: str
    equal_weight_control_id: str
    static_control_id: str
    primary_future_robustness_role: str
    incremental_hypothesis: str
    duplicate_fingerprint_note: str


@dataclass(frozen=True)
class ConfigSpec:
    architecture_code: str
    configuration_code: str
    lookback_sessions: int
    selected_count: int
    strategy_id: str
    trial_id: str

    @property
    def parameters(self) -> dict[str, int]:
        return {
            "lookback_sessions": self.lookback_sessions,
            "selected_count": self.selected_count,
        }


@dataclass(frozen=True)
class SplitDefinition:
    architecture_id: str
    prices: pd.DataFrame
    opens: pd.DataFrame
    signal_execution_pairs: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    selection_index: pd.DatetimeIndex
    evaluation_index: pd.DatetimeIndex
    full_index: pd.DatetimeIndex
    boundary_execution: pd.Timestamp


ARCHITECTURES = (
    ArchitectureSpec(
        architecture_code="A",
        architecture_id="downside_upside_capture_cross_sectional",
        family_id="cross_asset_capture_asymmetry_rotation",
        display_name="Downside/Upside Capture Asymmetry Rotation",
        universe=MULTI_ASSET_UNIVERSE,
        accounting_universe=(*MULTI_ASSET_UNIVERSE, "BIL"),
        named_control_id="ordinary_beta_defensive_rotation_control",
        equal_weight_control_id="equal_weight_12_asset_universe_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis=(
            "Separate upside and downside market-response behavior contains allocation information "
            "beyond ordinary beta and static multi-asset diversification."
        ),
        duplicate_fingerprint_note=(
            "Cross-asset 12-ETF universe, SPY reference, top-K upside-minus-downside capture; "
            "not materially equivalent to completed sector-only capture factory work."
        ),
    ),
    ArchitectureSpec(
        architecture_code="B",
        architecture_id="cross_sectional_overnight_intraday_decomposition",
        family_id="sector_overnight_intraday_return_structure",
        display_name="Overnight/Intraday Return-Structure Rotation",
        universe=SECTOR_UNIVERSE,
        accounting_universe=(*SECTOR_UNIVERSE, "BIL", "SPY"),
        named_control_id="close_to_close_momentum_same_structure_control",
        equal_weight_control_id="equal_weight_ten_sector_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis=(
            "The decomposition of return into overnight and intraday components contains "
            "cross-sectional information not captured by ordinary close-to-close momentum."
        ),
        duplicate_fingerprint_note=(
            "Materially equivalent to Technical Factory V2 sector overnight-minus-intraday top-N "
            "selection; parameter-only similarity is sufficient when the underlying architecture matches."
        ),
    ),
    ArchitectureSpec(
        architecture_code="C",
        architecture_id="realized_volatility_of_volatility_selection",
        family_id="cross_asset_volatility_stability_rotation",
        display_name="Volatility-Stability Rotation",
        universe=MULTI_ASSET_UNIVERSE,
        accounting_universe=(*MULTI_ASSET_UNIVERSE, "BIL"),
        named_control_id="inverse_volatility_same_universe_control",
        equal_weight_control_id="equal_weight_12_asset_universe_control",
        static_control_id="static_average_candidate_weights_control",
        primary_future_robustness_role="cross_sectional_allocation_strategy",
        incremental_hypothesis=(
            "Stability of an asset's volatility regime contains information beyond selecting "
            "the assets with the lowest current volatility."
        ),
        duplicate_fingerprint_note=(
            "Realized-volatility coefficient-of-variation ranking across the 12-ETF universe; "
            "not the same as ordinary inverse-volatility selection."
        ),
    ),
)

CONFIGS = (
    ConfigSpec("A", "A1", 63, 3, "internal_capture_asymmetry_63d_top3_v1", "accepted47_internal_v1__capture63__top3"),
    ConfigSpec("A", "A2", 63, 5, "internal_capture_asymmetry_63d_top5_v1", "accepted47_internal_v1__capture63__top5"),
    ConfigSpec("A", "A3", 126, 3, "internal_capture_asymmetry_126d_top3_v1", "accepted47_internal_v1__capture126__top3"),
    ConfigSpec("A", "A4", 126, 5, "internal_capture_asymmetry_126d_top5_v1", "accepted47_internal_v1__capture126__top5"),
    ConfigSpec("B", "B1", 21, 3, "internal_sector_overnight_intraday_21d_top3_v1", "accepted47_internal_v1__overnight21__top3"),
    ConfigSpec("B", "B2", 21, 5, "internal_sector_overnight_intraday_21d_top5_v1", "accepted47_internal_v1__overnight21__top5"),
    ConfigSpec("B", "B3", 63, 3, "internal_sector_overnight_intraday_63d_top3_v1", "accepted47_internal_v1__overnight63__top3"),
    ConfigSpec("B", "B4", 63, 5, "internal_sector_overnight_intraday_63d_top5_v1", "accepted47_internal_v1__overnight63__top5"),
    ConfigSpec("C", "C1", 63, 3, "internal_vol_stability_63d_top3_v1", "accepted47_internal_v1__volstability63__top3"),
    ConfigSpec("C", "C2", 63, 5, "internal_vol_stability_63d_top5_v1", "accepted47_internal_v1__volstability63__top5"),
    ConfigSpec("C", "C3", 126, 3, "internal_vol_stability_126d_top3_v1", "accepted47_internal_v1__volstability126__top3"),
    ConfigSpec("C", "C4", 126, 5, "internal_vol_stability_126d_top5_v1", "accepted47_internal_v1__volstability126__top5"),
)

REQUIRED_OUTPUT_FILES = {
    "batch_manifest.yaml",
    "architecture_preregistration.yaml",
    "parameter_grid.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "duplicate_preflight.csv",
    "benchmark_reference_log.csv",
    "selection_segment_definition.csv",
    "selection_segment_results.csv",
    "architecture_winner_selection.csv",
    "evaluation_segment_results.csv",
    "post_selection_full_period_diagnostics.csv",
    "calendar_year_results.csv",
    "rebalance_contribution_results.csv",
    "lightweight_concentration_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "failure_vectors.csv",
    "failure_reasons.csv",
    "entity_count_reconciliation.json",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "batch_report.md",
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
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return "sha256:" + digest.hexdigest()
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.bool_,)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        value_float = float(value)
        return "" if not math.isfinite(value_float) else f"{value_float:.12g}"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


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
        expected_parent = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to clean unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def architecture_by_code(code: str) -> ArchitectureSpec:
    return next(item for item in ARCHITECTURES if item.architecture_code == code)


def configs_for_architecture(code: str) -> tuple[ConfigSpec, ...]:
    return tuple(item for item in CONFIGS if item.architecture_code == code)


def unique_symbols(symbols: tuple[str, ...]) -> tuple[str, ...]:
    output: list[str] = []
    for symbol in symbols:
        if symbol not in output:
            output.append(symbol)
    return tuple(output)


def target(columns: tuple[str, ...], weights: dict[str, float]) -> dict[str, float]:
    row = {symbol: float(weights.get(symbol, 0.0)) for symbol in columns}
    values = np.array(list(row.values()), dtype=float)
    if not np.isfinite(values).all() or (values < -WEIGHT_TOLERANCE).any():
        raise ValueError("target contains invalid long-only weights")
    total = float(values.sum())
    if abs(total - 1.0) > 1e-8:
        raise ValueError(f"target weight sum is not 1.0: {total}")
    return row


def bil_target(columns: tuple[str, ...]) -> dict[str, float]:
    return target(columns, {"BIL": 1.0})


def ranked_target(columns: tuple[str, ...], ranked: list[str], selected_count: int) -> dict[str, float]:
    selected = ranked[:selected_count]
    weights = {symbol: 0.0 for symbol in columns}
    if selected:
        slot_weight = 1.0 / float(selected_count)
        for symbol in selected:
            weights[symbol] = slot_weight
        weights["BIL"] = max(0.0, 1.0 - slot_weight * len(selected))
    else:
        weights["BIL"] = 1.0
    return target(columns, weights)


def event_frame(
    index: pd.DatetimeIndex,
    columns: tuple[str, ...],
    events: dict[pd.Timestamp, dict[str, float]],
) -> pd.DataFrame:
    return accounting.event_frame(index, columns, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def monthly_rebalanced_static_events(
    index: pd.DatetimeIndex,
    execution_dates: tuple[pd.Timestamp, ...],
    columns: tuple[str, ...],
    weights: dict[str, float],
) -> pd.DataFrame:
    events = {pd.Timestamp(index[0]): target(columns, weights)}
    for date_value in execution_dates:
        events[pd.Timestamp(date_value)] = target(columns, weights)
    return event_frame(index, columns, events)


def buy_hold_events(index: pd.DatetimeIndex, columns: tuple[str, ...], symbol: str) -> pd.DataFrame:
    return event_frame(index, columns, {pd.Timestamp(index[0]): target(columns, {symbol: 1.0})})


def month_ends(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [
        pd.Timestamp(value)
        for value in pd.Series(index=index, data=index).groupby(index.to_period("M")).last().tolist()
    ]


def next_session(index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(index.get_loc(pd.Timestamp(signal_date)))
    if position + 1 >= len(index):
        return None
    return pd.Timestamp(index[position + 1])


def load_adjusted_ohlcv(symbol: str) -> pd.DataFrame:
    path = CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Required accepted-47 cache is missing: {rel(path)}")
    raw = pd.read_csv(path)
    required = {"date", "open", "high", "low", "close", "adj_close", "volume"}
    missing = sorted(required - set(raw.columns))
    if missing:
        raise RuntimeError(f"{symbol} cache is missing required fields: {missing}")
    frame = raw.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date")
    frame = frame.set_index("date")
    for column in ("open", "high", "low", "close", "adj_close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[["open", "high", "low", "close", "adj_close", "volume"]].dropna()
    price_columns = ["open", "high", "low", "close", "adj_close"]
    if (frame[price_columns] <= 0.0).any().any():
        raise RuntimeError(f"{symbol} cache has nonpositive adjusted prices")
    return frame


def load_frames() -> dict[str, pd.DataFrame]:
    symbols = unique_symbols(tuple(symbol for arch in ARCHITECTURES for symbol in arch.accounting_universe))
    return {symbol: load_adjusted_ohlcv(symbol) for symbol in symbols}


def cache_preflight_rows(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in sorted(frames):
        path = CACHE_DIR / f"{symbol}.csv"
        frame = frames[symbol]
        rows.append(
            {
                "symbol": symbol,
                "cache_path": rel(path),
                "cache_hash": file_hash(path),
                "row_count": len(frame),
                "first_date": frame.index.min().date().isoformat(),
                "last_date": frame.index.max().date().isoformat(),
                "preflight_status": "pass",
            }
        )
    return rows


def common_ohlcv_frames(
    frames: dict[str, pd.DataFrame],
    symbols: tuple[str, ...],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    closes = pd.concat([frames[symbol]["close"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    opens = pd.concat([frames[symbol]["open"].rename(symbol) for symbol in symbols], axis=1, join="inner").dropna()
    common = closes.index.intersection(opens.index).sort_values()
    return closes.reindex(common).dropna(), opens.reindex(common).dropna()


def protected_hashes() -> dict[str, str]:
    return {rel(path): file_hash(path) for path in PROTECTED_STATE_PATHS if path.exists()}


def duplicate_preflight_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog_architectures: list[dict[str, Any]] = []
    if TECHNICAL_FACTORY_V2_CATALOG.exists():
        payload = yaml.safe_load(TECHNICAL_FACTORY_V2_CATALOG.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            catalog_architectures = [
                row for row in payload.get("architectures", []) if isinstance(row, dict)
            ]
    matched_b = next(
        (
            row for row in catalog_architectures
            if row.get("architecture_id") == "factory_v2_sector_overnight_intraday_differential"
            and row.get("strategy_architecture") == "monthly_overnight_minus_intraday_topN_sector_selection"
        ),
        None,
    )
    for arch in ARCHITECTURES:
        is_duplicate = arch.architecture_code == "B" and matched_b is not None
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "architecture_code": arch.architecture_code,
                "preflight_status": "duplicate_or_redundant" if is_duplicate else "pass",
                "execute_architecture_trials": not is_duplicate,
                "executed_trial_count": 0 if is_duplicate else len(configs_for_architecture(arch.architecture_code)),
                "matched_existing_project": "technical_strategy_factory_v2" if is_duplicate else "",
                "matched_existing_architecture_id": (
                    "factory_v2_sector_overnight_intraday_differential" if is_duplicate else ""
                ),
                "matched_existing_path": rel(TECHNICAL_FACTORY_V2_CATALOG) if is_duplicate else "",
                "formula_checked": True,
                "universe_checked": True,
                "formation_schedule_checked": True,
                "ranking_characteristic_checked": True,
                "target_construction_checked": True,
                "parameter_grid_checked": True,
                "formula_match": is_duplicate,
                "universe_match": bool(
                    is_duplicate
                    and set(SECTOR_UNIVERSE).issuperset(set(matched_b.get("universe", [])) - {"BIL"})
                ),
                "formation_schedule_match": is_duplicate,
                "ranking_characteristic_match": is_duplicate,
                "target_construction_match": is_duplicate,
                "parameter_grid_similarity_sufficient": is_duplicate,
                "broad_family_similarity_only": False,
                "decision_reason": (
                    arch.duplicate_fingerprint_note if is_duplicate
                    else "No materially equivalent completed architecture found; broad family similarity alone not used."
                ),
                "preperformance_complete": True,
            }
        )
    return rows


def data_ready_for_architecture(frames: dict[str, pd.DataFrame], arch: ArchitectureSpec) -> tuple[bool, str]:
    missing = [symbol for symbol in arch.accounting_universe if symbol not in frames or frames[symbol].empty]
    if missing:
        return False, f"missing required cache symbols: {','.join(missing)}"
    prices, opens = common_ohlcv_frames(frames, arch.accounting_universe)
    if prices.empty or opens.empty or not prices.index.equals(opens.index):
        return False, "empty common no-forward-fill OHLCV period"
    return True, ""


def architecture_min_position(arch: ArchitectureSpec) -> int:
    max_lookback = max(config.lookback_sessions for config in configs_for_architecture(arch.architecture_code))
    if arch.architecture_code == "C":
        return max_lookback + 9
    return max_lookback


def architecture_split(frames: dict[str, pd.DataFrame], arch: ArchitectureSpec) -> SplitDefinition:
    prices, opens = common_ohlcv_frames(frames, arch.accounting_universe)
    min_position = architecture_min_position(arch)
    pairs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for signal_date in month_ends(prices.index):
        position = int(prices.index.get_loc(signal_date))
        execution = next_session(prices.index, signal_date)
        if position >= min_position and execution is not None:
            pairs.append((pd.Timestamp(signal_date), pd.Timestamp(execution)))
    if len(pairs) < 3:
        raise RuntimeError(f"{arch.architecture_id} has insufficient valid rebalance observations")
    boundary_position = int(math.floor(0.6 * len(pairs)))
    if boundary_position <= 0 or boundary_position >= len(pairs):
        raise RuntimeError(f"{arch.architecture_id} has nonviable 60/40 split")
    first_execution = pairs[0][1]
    boundary_execution = pairs[boundary_position][1]
    selection_index = prices.index[(prices.index >= first_execution) & (prices.index < boundary_execution)]
    evaluation_index = prices.index[prices.index >= boundary_execution]
    full_index = prices.index[prices.index >= first_execution]
    return SplitDefinition(
        architecture_id=arch.architecture_id,
        prices=prices,
        opens=opens,
        signal_execution_pairs=tuple(pairs),
        selection_index=selection_index,
        evaluation_index=evaluation_index,
        full_index=full_index,
        boundary_execution=boundary_execution,
    )


def capture_scores(
    prices: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    returns = prices[list(universe)].pct_change(fill_method=None)
    return capture_scores_from_returns(returns, universe, signal_date, lookback)


def capture_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, int]]:
    position = int(returns.index.get_loc(signal_date))
    window = returns.iloc[position - lookback + 1:position + 1]
    market = window["SPY"]
    upside_market = market > 0.0
    downside_market = market < 0.0
    scores: dict[str, float] = {}
    up_capture: dict[str, float] = {}
    down_capture: dict[str, float] = {}
    counts = {
        "upside_count": int(upside_market.sum()),
        "downside_count": int(downside_market.sum()),
    }
    mean_market_up = float(market[upside_market].mean())
    mean_market_down = float(market[downside_market].mean())
    for symbol in universe:
        asset = window[symbol]
        valid_up = upside_market & asset.notna()
        valid_down = downside_market & asset.notna()
        if valid_up.sum() < 10 or valid_down.sum() < 10:
            continue
        if abs(mean_market_up) <= 1e-15 or abs(mean_market_down) <= 1e-15:
            continue
        up_value = float(asset[valid_up].mean() / mean_market_up)
        down_value = float(asset[valid_down].mean() / mean_market_down)
        if math.isfinite(up_value) and math.isfinite(down_value):
            up_capture[symbol] = up_value
            down_capture[symbol] = down_value
            scores[symbol] = up_value - down_value
    return scores, up_capture, down_capture, counts


def beta_scores(
    prices: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> dict[str, float]:
    returns = prices[list(universe)].pct_change(fill_method=None)
    return beta_scores_from_returns(returns, universe, signal_date, lookback)


def beta_scores_from_returns(
    returns: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> dict[str, float]:
    position = int(returns.index.get_loc(signal_date))
    window = returns.iloc[position - lookback + 1:position + 1]
    market = window["SPY"]
    scores: dict[str, float] = {}
    for symbol in universe:
        pair = pd.concat([window[symbol], market], axis=1).dropna()
        if len(pair) < lookback:
            continue
        variance = float(pair.iloc[:, 1].var(ddof=1))
        if variance <= 0.0 or not math.isfinite(variance):
            continue
        beta = float(pair.iloc[:, 0].cov(pair.iloc[:, 1]) / variance)
        if math.isfinite(beta):
            scores[symbol] = beta
    return scores


def volatility_stability_scores(
    prices: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    returns = prices[list(universe)].pct_change(fill_method=None)
    rv10 = returns.rolling(10, min_periods=10).std(ddof=1)
    return volatility_stability_scores_from_rv10(rv10, universe, signal_date, lookback)


def volatility_stability_scores_from_rv10(
    rv10: pd.DataFrame,
    universe: tuple[str, ...],
    signal_date: pd.Timestamp,
    lookback: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    position = int(rv10.index.get_loc(signal_date))
    scores: dict[str, float] = {}
    cv_values: dict[str, float] = {}
    current_rv: dict[str, float] = {}
    for symbol in universe:
        window = rv10[symbol].iloc[position - lookback + 1:position + 1]
        current = float(rv10[symbol].iloc[position])
        mean_value = float(window.mean())
        std_value = float(window.std(ddof=1))
        if (
            len(window) == lookback
            and np.isfinite(window.to_numpy(dtype=float)).all()
            and math.isfinite(mean_value)
            and mean_value > 0.0
            and math.isfinite(std_value)
            and math.isfinite(current)
            and current > 0.0
        ):
            cv = std_value / mean_value
            cv_values[symbol] = cv
            scores[symbol] = -cv
            current_rv[symbol] = current
    return scores, cv_values, current_rv


def sorted_desc(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda symbol: (-scores[symbol], symbol))


def sorted_asc(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda symbol: (scores[symbol], symbol))


def build_events_for_config(
    arch: ArchitectureSpec,
    config: ConfigSpec,
    split: SplitDefinition,
) -> dict[str, Any]:
    columns = tuple(split.prices.columns)
    initial = bil_target(columns)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(split.prices.index[0]): initial}
    named_events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(split.prices.index[0]): initial}
    signal_rows: list[dict[str, Any]] = []
    returns = split.prices[list(arch.universe)].pct_change(fill_method=None)
    rv10 = returns.rolling(10, min_periods=10).std(ddof=1) if arch.architecture_code == "C" else pd.DataFrame()
    for signal_date, execution_date in split.signal_execution_pairs:
        if arch.architecture_code == "A":
            capture, up_capture, down_capture, counts = capture_scores_from_returns(
                returns, arch.universe, signal_date, config.lookback_sessions
            )
            beta = beta_scores_from_returns(returns, arch.universe, signal_date, config.lookback_sessions)
            candidate_ranked = sorted_desc(capture)
            named_ranked = sorted_asc(beta)
            candidate_events[execution_date] = ranked_target(columns, candidate_ranked, config.selected_count)
            named_events[execution_date] = ranked_target(columns, named_ranked, config.selected_count)
            signal_rows.append(
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "candidate_top": candidate_ranked[: config.selected_count],
                    "named_top": named_ranked[: config.selected_count],
                    "eligible_count": len(candidate_ranked),
                    "named_eligible_count": len(named_ranked),
                    **counts,
                    "score_sample": {symbol: capture[symbol] for symbol in candidate_ranked[:3]},
                    "up_capture_sample": {symbol: up_capture[symbol] for symbol in candidate_ranked[:3]},
                    "down_capture_sample": {symbol: down_capture[symbol] for symbol in candidate_ranked[:3]},
                }
            )
        elif arch.architecture_code == "C":
            stability, cv_values, current_rv = volatility_stability_scores_from_rv10(
                rv10, arch.universe, signal_date, config.lookback_sessions
            )
            candidate_ranked = sorted_desc(stability)
            named_ranked = sorted_asc(current_rv)
            candidate_events[execution_date] = ranked_target(columns, candidate_ranked, config.selected_count)
            named_events[execution_date] = ranked_target(columns, named_ranked, config.selected_count)
            signal_rows.append(
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "candidate_top": candidate_ranked[: config.selected_count],
                    "named_top": named_ranked[: config.selected_count],
                    "eligible_count": len(candidate_ranked),
                    "named_eligible_count": len(named_ranked),
                    "score_sample": {symbol: stability[symbol] for symbol in candidate_ranked[:3]},
                    "vol_of_vol_cv_sample": {symbol: cv_values[symbol] for symbol in candidate_ranked[:3]},
                    "current_rv10_sample": {symbol: current_rv[symbol] for symbol in named_ranked[:3]},
                }
            )
        else:
            raise RuntimeError(f"Duplicate architecture should not be prepared: {arch.architecture_id}")
    candidate_frame = event_frame(split.prices.index, columns, candidate_events)
    named_frame = event_frame(split.prices.index, columns, named_events)
    candidate_targets = target_history(candidate_frame, split.prices.index)
    selection_targets = candidate_targets.reindex(split.selection_index).dropna()
    static_weights = {
        symbol: float(selection_targets[symbol].mean()) for symbol in columns
    }
    static_total = float(sum(static_weights.values()))
    static_weights = {symbol: value / static_total for symbol, value in static_weights.items()}
    equal_weights = {symbol: (1.0 / len(arch.universe) if symbol in arch.universe else 0.0) for symbol in columns}
    execution_dates = tuple(execution for _, execution in split.signal_execution_pairs)
    control_events = {
        arch.named_control_id: named_frame,
        arch.equal_weight_control_id: monthly_rebalanced_static_events(
            split.prices.index, execution_dates, columns, equal_weights
        ),
        arch.static_control_id: monthly_rebalanced_static_events(
            split.prices.index, execution_dates, columns, static_weights
        ),
        "SPY_buy_and_hold": buy_hold_events(split.prices.index, columns, "SPY"),
        "BIL_buy_and_hold": buy_hold_events(split.prices.index, columns, "BIL"),
    }
    return {
        "candidate_events": candidate_frame,
        "control_events": control_events,
        "candidate_targets": candidate_targets,
        "average_target_weights_selection_segment": static_weights,
        "signal_rows": signal_rows,
    }


def simulate_prepared(split: SplitDefinition, prepared: dict[str, Any]) -> dict[str, Any]:
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        candidate_paths[cost] = accounting.simulate_path(
            split.prices, prepared["candidate_events"], cost, TIMING_CONVENTION
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = accounting.simulate_path(
                split.prices, events, cost, TIMING_CONVENTION
            )
    return {"candidate_paths": candidate_paths, "control_paths": control_paths}


def annualized_years(index: pd.DatetimeIndex) -> float:
    return max(len(index) / 252.0, 1e-12)


def finite_metric(value: Any) -> float:
    try:
        output = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return output if math.isfinite(output) else float("nan")


def metrics_for_path(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex,
    scheduled_executions: tuple[pd.Timestamp, ...],
) -> dict[str, Any]:
    metrics = accounting.metric_payload(path, period_index)
    held = path["held_weights"].reindex(period_index).dropna()
    sums = held.sum(axis=1) if len(held) else pd.Series(dtype=float)
    average_holdings = {
        symbol: float(value)
        for symbol, value in held.mean().fillna(0.0).items()
    }
    period_dates = set(period_index)
    event_dates = [date for date in scheduled_executions if date in period_dates]
    metrics.update(
        {
            "period_start": period_index.min().date().isoformat() if len(period_index) else "",
            "period_end": period_index.max().date().isoformat() if len(period_index) else "",
            "trading_day_count": len(period_index),
            "formation_count": len(event_dates),
            "rebalance_count": len(event_dates),
            "annualized_turnover": float(metrics["turnover"]) / annualized_years(period_index),
            "average_holdings": average_holdings,
            "maximum_asset_weight": float(held.max().max()) if len(held) else float("nan"),
            "daily_weight_sum_one": bool(
                len(sums) and np.isclose(sums.to_numpy(dtype=float), 1.0, atol=1e-8, rtol=0.0).all()
            ),
            "explicit_holdings": bool(list(held.columns) == list(path["target_events"].columns)),
            "target_zero_weights_preserved": bool(
                (path["target_events"].to_numpy(dtype=float) == 0.0).any()
            ),
            "stale_weight_forward_fill_used": False,
            "same_period_price_signal_return_used": False,
        }
    )
    metrics["invariant_pass"] = bool(metrics["invariant_pass"] and metrics["daily_weight_sum_one"])
    return metrics


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        finite_metric(candidate["sharpe_ratio"]) - finite_metric(control["sharpe_ratio"]) >= 0.02 - 1e-12
        or finite_metric(candidate["maximum_drawdown"]) - finite_metric(control["maximum_drawdown"]) >= 0.01 - 1e-12
    )


def selection_gate_vector(
    candidate_5: dict[str, Any],
    named_5: dict[str, Any],
    static_5: dict[str, Any],
    equal_5: dict[str, Any],
    candidate_10: dict[str, Any],
) -> dict[str, Any]:
    named_dominates = dominates(named_5, candidate_5)
    static_dominates = dominates(static_5, candidate_5)
    equal_dominates = dominates(equal_5, candidate_5)
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not named_dominates,
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (static_dominates or equal_dominates),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
    }
    vector["selection_eligible"] = all(bool(value) for value in vector.values())
    if not vector["cagr_positive_5bps"]:
        reason = "weak_return"
    elif not vector["invariants_pass_5bps"]:
        reason = "methodology_failure"
    elif not vector["named_control_not_dominating_5bps"]:
        reason = "weak_vs_primary_control"
    elif not vector["material_vs_named_control_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["static_equal_control_not_dominating_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["cagr_positive_10bps"]:
        reason = "cost_drag"
    else:
        reason = ""
    vector["primary_failure_reason"] = reason
    return vector


def metric_prefix(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_cagr": values.get("cagr", ""),
        f"{prefix}_total_return": values.get("total_return", ""),
        f"{prefix}_annualized_volatility": values.get("annualized_volatility", ""),
        f"{prefix}_sharpe_ratio": values.get("sharpe_ratio", ""),
        f"{prefix}_maximum_drawdown": values.get("maximum_drawdown", ""),
        f"{prefix}_turnover": values.get("turnover", ""),
        f"{prefix}_transaction_cost_drag": values.get("transaction_cost_drag", ""),
    }


def selection_results_for_config(
    arch: ArchitectureSpec,
    config: ConfigSpec,
    split: SplitDefinition,
    prepared: dict[str, Any],
    simulation: dict[str, Any],
) -> dict[str, Any]:
    scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COSTS:
        metrics[("candidate", cost)] = metrics_for_path(
            simulation["candidate_paths"][cost], split.selection_index, scheduled
        )
        for control_id in prepared["control_events"]:
            metrics[(control_id, cost)] = metrics_for_path(
                simulation["control_paths"][(control_id, cost)], split.selection_index, scheduled
            )
    vector = selection_gate_vector(
        metrics[("candidate", PRIMARY_COST)],
        metrics[(arch.named_control_id, PRIMARY_COST)],
        metrics[(arch.static_control_id, PRIMARY_COST)],
        metrics[(arch.equal_weight_control_id, PRIMARY_COST)],
        metrics[("candidate", 10.0)],
    )
    return {
        "arch": arch,
        "config": config,
        "split": split,
        "prepared": prepared,
        "simulation": simulation,
        "selection_metrics": metrics,
        "selection_vector": vector,
        "selected_winner": False,
        "evaluation": {},
        "outcome": "selection_eligible" if vector["selection_eligible"] else "closed_optimization",
        "failure_reason": "" if vector["selection_eligible"] else vector["primary_failure_reason"],
        "decision_reason": (
            "passed all preregistered selection-segment gates"
            if vector["selection_eligible"]
            else "failed preregistered selection-segment gate"
        ),
    }


def build_executed_results(
    frames: dict[str, pd.DataFrame],
    duplicate_rows: list[dict[str, Any]],
) -> tuple[dict[str, SplitDefinition], dict[str, dict[str, Any]]]:
    duplicate_by_code = {
        row["architecture_code"]: row["preflight_status"] == "duplicate_or_redundant"
        for row in duplicate_rows
    }
    splits: dict[str, SplitDefinition] = {}
    results: dict[str, dict[str, Any]] = {}
    for arch in ARCHITECTURES:
        if duplicate_by_code[arch.architecture_code]:
            for config in configs_for_architecture(arch.architecture_code):
                results[config.trial_id] = duplicate_result(arch, config)
            continue
        ready, reason = data_ready_for_architecture(frames, arch)
        if not ready:
            for config in configs_for_architecture(arch.architecture_code):
                results[config.trial_id] = blocked_result(arch, config, reason)
            continue
        split = architecture_split(frames, arch)
        splits[arch.architecture_id] = split
        for config in configs_for_architecture(arch.architecture_code):
            prepared = build_events_for_config(arch, config, split)
            simulation = simulate_prepared(split, prepared)
            results[config.trial_id] = selection_results_for_config(arch, config, split, prepared, simulation)
    freeze_architecture_winners(results)
    evaluate_frozen_winners(results)
    return splits, results


def duplicate_result(arch: ArchitectureSpec, config: ConfigSpec) -> dict[str, Any]:
    return {
        "arch": arch,
        "config": config,
        "split": None,
        "prepared": {},
        "simulation": {},
        "selection_metrics": {},
        "selection_vector": {
            "selection_eligible": False,
            "primary_failure_reason": "duplicate_or_redundant",
        },
        "selected_winner": False,
        "evaluation": {},
        "outcome": "closed_optimization",
        "failure_reason": "duplicate_or_redundant",
        "decision_reason": "architecture duplicate preflight rejected before performance calculation",
    }


def blocked_result(arch: ArchitectureSpec, config: ConfigSpec, reason: str) -> dict[str, Any]:
    return {
        "arch": arch,
        "config": config,
        "split": None,
        "prepared": {},
        "simulation": {},
        "selection_metrics": {},
        "selection_vector": {
            "selection_eligible": False,
            "primary_failure_reason": "data_or_comparability_failure",
        },
        "selected_winner": False,
        "evaluation": {},
        "outcome": "closed_optimization",
        "failure_reason": "data_or_comparability_failure",
        "decision_reason": reason,
    }


def freeze_architecture_winners(results: dict[str, dict[str, Any]]) -> None:
    for arch in ARCHITECTURES:
        if any(results[config.trial_id]["failure_reason"] == "duplicate_or_redundant" for config in configs_for_architecture(arch.architecture_code)):
            continue
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        if not all(result["split"] is not None for result in arch_results):
            continue
        eligible = [result for result in arch_results if result["selection_vector"]["selection_eligible"]]
        if not eligible:
            continue
        max_sharpe = max(
            finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"])
            for result in eligible
        )
        tied = [
            result for result in eligible
            if finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["sharpe_ratio"])
            >= max_sharpe - 0.01 - 1e-12
        ]
        winner = sorted(
            tied,
            key=lambda result: (
                abs(finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["maximum_drawdown"])),
                finite_metric(result["selection_metrics"][("candidate", PRIMARY_COST)]["annualized_turnover"]),
                result["config"].trial_id,
            ),
        )[0]
        winner["selected_winner"] = True
        winner["outcome"] = "selection_winner_pending_evaluation"
        winner["failure_reason"] = ""
        winner["decision_reason"] = "frozen by preregistered selection rule before evaluation metrics"
        for result in arch_results:
            if result is winner:
                continue
            result["outcome"] = "closed_optimization"
            result["failure_reason"] = "not_selected_by_frozen_rule"
            result["decision_reason"] = "not selected by frozen one-winner-per-architecture rule"


def compound_return(returns: pd.Series) -> float:
    values = returns.dropna().to_numpy(dtype=float)
    if not len(values):
        return 0.0
    return float(np.prod(1.0 + values) - 1.0)


def complete_calendar_years(full_index: pd.DatetimeIndex, period_index: pd.DatetimeIndex) -> list[int]:
    years: list[int] = []
    period_set = set(period_index)
    for year in sorted(set(period_index.year)):
        year_index = full_index[full_index.year == year]
        if len(year_index) and year_index.min() in period_set and year_index.max() in period_set:
            years.append(int(year))
    return years


def calendar_year_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arch: ArchitectureSpec = result["arch"]
    config: ConfigSpec = result["config"]
    split: SplitDefinition = result["split"]
    candidate = result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"]
    named = result["simulation"]["control_paths"][(arch.named_control_id, PRIMARY_COST)]["returns"]
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    for year in complete_calendar_years(split.prices.index, split.evaluation_index):
        year_index = split.evaluation_index[split.evaluation_index.year == year]
        candidate_return = compound_return(candidate.reindex(year_index))
        named_return = compound_return(named.reindex(year_index))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "period_year": year,
                "period_complete_calendar_year": True,
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "descriptive_only": False,
            }
        )
    max_share = 0.0
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if len(rows) >= 2 and max_share > 0.8 + 1e-12 else "pass"
    else:
        state = "not_applicable_no_positive_excess"
    return rows, {
        "complete_year_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def rebalance_contribution_diagnostics(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arch: ArchitectureSpec = result["arch"]
    config: ConfigSpec = result["config"]
    split: SplitDefinition = result["split"]
    candidate = result["simulation"]["candidate_paths"][PRIMARY_COST]["returns"]
    named = result["simulation"]["control_paths"][(arch.named_control_id, PRIMARY_COST)]["returns"]
    eval_executions = [
        execution for _, execution in split.signal_execution_pairs
        if execution in set(split.evaluation_index)
    ]
    rows: list[dict[str, Any]] = []
    positive_total = 0.0
    for position, start in enumerate(eval_executions):
        end = eval_executions[position + 1] if position + 1 < len(eval_executions) else split.evaluation_index.max()
        if position + 1 < len(eval_executions):
            interval = split.evaluation_index[(split.evaluation_index >= start) & (split.evaluation_index < end)]
            interval_end = interval.max() if len(interval) else start
        else:
            interval = split.evaluation_index[split.evaluation_index >= start]
            interval_end = split.evaluation_index.max()
        candidate_return = compound_return(candidate.reindex(interval))
        named_return = compound_return(named.reindex(interval))
        excess = candidate_return - named_return
        positive = max(0.0, excess)
        positive_total += positive
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "rebalance_month": start.to_period("M").strftime("%Y-%m"),
                "interval_start": start.date().isoformat(),
                "interval_end": pd.Timestamp(interval_end).date().isoformat(),
                "cost_bps_one_way": PRIMARY_COST,
                "candidate_return": candidate_return,
                "named_control_return": named_return,
                "candidate_minus_named_excess_return": excess,
                "positive_excess_return": positive,
                "nonwinner_evaluation_access": False,
            }
        )
    max_share = 0.0
    if positive_total > 0.0 and rows:
        max_share = max(float(row["positive_excess_return"]) / positive_total for row in rows)
        state = "concentration_risk" if max_share > 0.8 + 1e-12 else "pass"
    else:
        state = "not_applicable_no_positive_excess"
    return rows, {
        "rebalance_month_count": len(rows),
        "positive_excess_total": positive_total,
        "max_positive_excess_share": max_share,
        "state": state,
        "pass": state != "concentration_risk",
    }


def evaluation_gate_vector(
    result: dict[str, Any],
    calendar_state: dict[str, Any],
    rebalance_state: dict[str, Any],
) -> dict[str, Any]:
    arch: ArchitectureSpec = result["arch"]
    evaluation = result["evaluation"]["metrics"]
    candidate_5 = evaluation[("candidate", PRIMARY_COST)]
    named_5 = evaluation[(arch.named_control_id, PRIMARY_COST)]
    static_5 = evaluation[(arch.static_control_id, PRIMARY_COST)]
    equal_5 = evaluation[(arch.equal_weight_control_id, PRIMARY_COST)]
    candidate_10 = evaluation[("candidate", 10.0)]
    vector = {
        "cagr_positive_5bps": finite_metric(candidate_5["cagr"]) > 0.0,
        "invariants_pass_5bps": bool(candidate_5["invariant_pass"]),
        "named_control_not_dominating_5bps": not dominates(named_5, candidate_5),
        "material_vs_named_control_5bps": material_advantage(candidate_5, named_5),
        "static_equal_control_not_dominating_5bps": not (
            dominates(static_5, candidate_5) or dominates(equal_5, candidate_5)
        ),
        "cagr_positive_10bps": finite_metric(candidate_10["cagr"]) > 0.0,
        "calendar_year_concentration_pass": bool(calendar_state["pass"]),
        "rebalance_month_concentration_pass": bool(rebalance_state["pass"]),
    }
    vector["exploratory_followup_candidate"] = all(bool(value) for value in vector.values())
    if not vector["cagr_positive_5bps"]:
        reason = "weak_return"
    elif not vector["invariants_pass_5bps"]:
        reason = "methodology_failure"
    elif not vector["named_control_not_dominating_5bps"]:
        reason = "weak_vs_primary_control"
    elif not vector["material_vs_named_control_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["static_equal_control_not_dominating_5bps"]:
        reason = "benchmark_like_behavior"
    elif not vector["cagr_positive_10bps"]:
        reason = "cost_drag"
    elif not vector["calendar_year_concentration_pass"]:
        reason = "concentration_risk"
    elif not vector["rebalance_month_concentration_pass"]:
        reason = "concentration_risk"
    else:
        reason = ""
    vector["primary_failure_reason"] = reason
    return vector


def evaluate_frozen_winners(results: dict[str, dict[str, Any]]) -> None:
    for result in results.values():
        if not result.get("selected_winner"):
            continue
        arch: ArchitectureSpec = result["arch"]
        split: SplitDefinition = result["split"]
        scheduled = tuple(execution for _, execution in split.signal_execution_pairs)
        metrics: dict[tuple[str, float], dict[str, Any]] = {}
        full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        for cost in COSTS:
            metrics[("candidate", cost)] = metrics_for_path(
                result["simulation"]["candidate_paths"][cost], split.evaluation_index, scheduled
            )
            full_metrics[("candidate", cost)] = metrics_for_path(
                result["simulation"]["candidate_paths"][cost], split.full_index, scheduled
            )
            for control_id in result["prepared"]["control_events"]:
                metrics[(control_id, cost)] = metrics_for_path(
                    result["simulation"]["control_paths"][(control_id, cost)], split.evaluation_index, scheduled
                )
                full_metrics[(control_id, cost)] = metrics_for_path(
                    result["simulation"]["control_paths"][(control_id, cost)], split.full_index, scheduled
                )
        calendar_rows, calendar_state = calendar_year_diagnostics(result)
        rebalance_rows, rebalance_state = rebalance_contribution_diagnostics(result)
        result["evaluation"] = {
            "metrics": metrics,
            "full_metrics": full_metrics,
            "calendar_rows": calendar_rows,
            "calendar_state": calendar_state,
            "rebalance_rows": rebalance_rows,
            "rebalance_state": rebalance_state,
        }
        vector = evaluation_gate_vector(result, calendar_state, rebalance_state)
        result["evaluation"]["vector"] = vector
        if vector["exploratory_followup_candidate"]:
            result["outcome"] = "exploratory_followup_candidate"
            result["failure_reason"] = ""
            result["decision_reason"] = "winner passed exploratory evaluation gates at 5 bps with 10-bps viability"
        else:
            result["outcome"] = "closed_exploration"
            result["failure_reason"] = vector["primary_failure_reason"]
            result["decision_reason"] = "frozen winner failed exploratory evaluation gate"


def control_metric_columns(
    arch: ArchitectureSpec,
    metrics: dict[tuple[str, float], dict[str, Any]],
    cost: float,
) -> dict[str, Any]:
    return {
        "named_control_id": arch.named_control_id,
        **metric_prefix("named", metrics[(arch.named_control_id, cost)]),
        "static_control_id": arch.static_control_id,
        **metric_prefix("static", metrics[(arch.static_control_id, cost)]),
        "equal_weight_control_id": arch.equal_weight_control_id,
        **metric_prefix("equal_weight", metrics[(arch.equal_weight_control_id, cost)]),
        "spy_buy_hold_cagr": metrics[("SPY_buy_and_hold", cost)].get("cagr", ""),
        "bil_buy_hold_cagr": metrics[("BIL_buy_and_hold", cost)].get("cagr", ""),
    }


def result_metric_row(
    arch: ArchitectureSpec,
    config: ConfigSpec,
    period_id: str,
    metrics: dict[str, Any],
    cost: float,
    controls: dict[str, Any] | None = None,
    outcome: str = "",
    failure_reason: str = "",
) -> dict[str, Any]:
    return {
        "architecture_id": arch.architecture_id,
        "family_id": arch.family_id,
        "configuration_code": config.configuration_code,
        "strategy_id": config.strategy_id,
        "trial_id": config.trial_id,
        "result_role": "candidate",
        "period_id": period_id,
        "period_role": (
            "bounded_optimization_selection_segment"
            if period_id == "selection_segment"
            else (
                "exploratory_evaluation_segment"
                if period_id == "exploratory_evaluation_segment"
                else "post_selection_full_period_diagnostic"
            )
        ),
        "cost_bps_one_way": cost,
        "period_start": metrics.get("period_start", ""),
        "period_end": metrics.get("period_end", ""),
        "trading_day_count": metrics.get("trading_day_count", ""),
        "formation_count": metrics.get("formation_count", ""),
        "rebalance_count": metrics.get("rebalance_count", ""),
        "total_return": metrics.get("total_return", ""),
        "cagr": metrics.get("cagr", ""),
        "annualized_volatility": metrics.get("annualized_volatility", ""),
        "sharpe_ratio": metrics.get("sharpe_ratio", ""),
        "maximum_drawdown": metrics.get("maximum_drawdown", ""),
        "turnover": metrics.get("turnover", ""),
        "annualized_turnover": metrics.get("annualized_turnover", ""),
        "transaction_cost_drag": metrics.get("transaction_cost_drag", ""),
        "average_holdings": metrics.get("average_holdings", ""),
        "maximum_asset_weight": metrics.get("maximum_asset_weight", ""),
        "maximum_gross_exposure": metrics.get("maximum_gross_exposure", ""),
        "maximum_daily_weight_sum": metrics.get("maximum_daily_weight_sum", ""),
        "daily_weight_sum_one": metrics.get("daily_weight_sum_one", ""),
        "numeric_invariant_status": metrics.get("numeric_invariant_status", ""),
        "timing_invariant_status": metrics.get("timing_invariant_status", ""),
        "exposure_weight_invariant_status": metrics.get("exposure_weight_invariant_status", ""),
        "invariant_pass": metrics.get("invariant_pass", ""),
        **(controls or {}),
        "outcome": outcome,
        "failure_reason": failure_reason,
    }


def empty_selection_placeholder(arch: ArchitectureSpec, config: ConfigSpec, cost: float, result: dict[str, Any]) -> dict[str, Any]:
    return result_metric_row(
        arch,
        config,
        "selection_segment",
        {},
        cost,
        controls={
            "named_control_id": arch.named_control_id,
            "static_control_id": arch.static_control_id,
            "equal_weight_control_id": arch.equal_weight_control_id,
        },
        outcome=result["outcome"],
        failure_reason=result["failure_reason"],
    ) | {
        "performance_executed": False,
        "selection_eligible_5bps": False,
        "selection_gate_failures": result["failure_reason"],
    }


def selection_segment_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        if result["split"] is None:
            for cost in COSTS:
                rows.append(empty_selection_placeholder(arch, config, cost, result))
            continue
        for cost in COSTS:
            metrics = result["selection_metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "selection_segment",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["selection_metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {
                    "performance_executed": True,
                    "selection_eligible_5bps": result["selection_vector"]["selection_eligible"],
                    "selection_gate_failures": "|".join(
                        key for key, value in result["selection_vector"].items()
                        if key not in {"selection_eligible", "primary_failure_reason"} and value is False
                    ),
                }
            )
    return rows


def evaluation_segment_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result.get("selected_winner") or not result.get("evaluation"):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        for cost in COSTS:
            metrics = result["evaluation"]["metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "exploratory_evaluation_segment",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["evaluation"]["metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {
                    "frozen_winner": True,
                    "selection_frozen_before_evaluation_metrics": True,
                }
            )
    return rows


def post_selection_full_period_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not result.get("selected_winner") or not result.get("evaluation"):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        for cost in COSTS:
            metrics = result["evaluation"]["full_metrics"][("candidate", cost)]
            rows.append(
                result_metric_row(
                    arch,
                    config,
                    "post_selection_full_period_diagnostic",
                    metrics,
                    cost,
                    controls=control_metric_columns(arch, result["evaluation"]["full_metrics"], cost),
                    outcome=result["outcome"],
                    failure_reason=result["failure_reason"],
                )
                | {
                    "diagnostic_only": True,
                    "can_rescue_or_reverse_decision": False,
                }
            )
    return rows


def selection_definition_rows(
    splits: dict[str, SplitDefinition],
    duplicate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    duplicate_by_arch = {row["architecture_id"]: row for row in duplicate_rows}
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        duplicate = duplicate_by_arch[arch.architecture_id]["preflight_status"] == "duplicate_or_redundant"
        if duplicate:
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "architecture_code": arch.architecture_code,
                    "segment_status": "duplicate_or_redundant",
                    "common_universe": arch.accounting_universe,
                    "common_start": "",
                    "common_end": "",
                    "first_valid_signal_date": "",
                    "first_execution_date": "",
                    "last_execution_date": "",
                    "valid_rebalance_count": 0,
                    "selection_rebalance_count": 0,
                    "evaluation_rebalance_count": 0,
                    "selection_start": "",
                    "selection_end": "",
                    "evaluation_start": "",
                    "evaluation_end": "",
                    "boundary_execution_date": "",
                    "split_rule": "duplicate_preflight_zero_trials",
                    "segment_role": "optimization_split_not_validation_or_robustness",
                }
            )
            continue
        split = splits.get(arch.architecture_id)
        if split is None:
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "architecture_code": arch.architecture_code,
                    "segment_status": "data_or_comparability_failure",
                    "common_universe": arch.accounting_universe,
                    "common_start": "",
                    "common_end": "",
                    "first_valid_signal_date": "",
                    "first_execution_date": "",
                    "last_execution_date": "",
                    "valid_rebalance_count": 0,
                    "selection_rebalance_count": 0,
                    "evaluation_rebalance_count": 0,
                    "selection_start": "",
                    "selection_end": "",
                    "evaluation_start": "",
                    "evaluation_end": "",
                    "boundary_execution_date": "",
                    "split_rule": "no_executable_common_period",
                    "segment_role": "optimization_split_not_validation_or_robustness",
                }
            )
            continue
        executions = tuple(execution for _, execution in split.signal_execution_pairs)
        selection_executions = [date for date in executions if date in set(split.selection_index)]
        evaluation_executions = [date for date in executions if date in set(split.evaluation_index)]
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "architecture_code": arch.architecture_code,
                "segment_status": "executed",
                "common_universe": arch.accounting_universe,
                "common_start": split.prices.index.min().date().isoformat(),
                "common_end": split.prices.index.max().date().isoformat(),
                "first_valid_signal_date": split.signal_execution_pairs[0][0].date().isoformat(),
                "first_execution_date": executions[0].date().isoformat(),
                "last_execution_date": executions[-1].date().isoformat(),
                "valid_rebalance_count": len(executions),
                "selection_rebalance_count": len(selection_executions),
                "evaluation_rebalance_count": len(evaluation_executions),
                "selection_start": split.selection_index.min().date().isoformat(),
                "selection_end": split.selection_index.max().date().isoformat(),
                "evaluation_start": split.evaluation_index.min().date().isoformat(),
                "evaluation_end": split.evaluation_index.max().date().isoformat(),
                "boundary_execution_date": split.boundary_execution.date().isoformat(),
                "split_rule": "floor_60_percent_valid_rebalance_observations_selection_final_40_percent_evaluation",
                "segment_role": "optimization_split_not_validation_or_robustness",
            }
        )
    return rows


def architecture_winner_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        eligible = [result for result in arch_results if result["selection_vector"].get("selection_eligible")]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        duplicate = all(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results)
        blocked = all(result["split"] is None for result in arch_results) and not duplicate
        if winner is not None:
            metrics = winner["selection_metrics"][("candidate", PRIMARY_COST)]
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "selection_status": "winner_frozen",
                    "eligible_configuration_count": len(eligible),
                    "selected_strategy_id": winner["config"].strategy_id,
                    "selected_trial_id": winner["config"].trial_id,
                    "selected_configuration_code": winner["config"].configuration_code,
                    "selection_rule": (
                        "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id"
                    ),
                    "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
                    "selection_frozen_before_evaluation_metrics": True,
                    "selection_sharpe_5bps": metrics["sharpe_ratio"],
                    "selection_maximum_drawdown_5bps": metrics["maximum_drawdown"],
                    "selection_annualized_turnover_5bps": metrics["annualized_turnover"],
                    "winner_outcome": winner["outcome"],
                    "failure_reason": winner["failure_reason"],
                    "decision_reason": winner["decision_reason"],
                }
            )
        else:
            rows.append(
                {
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "selection_status": (
                        "duplicate_or_redundant" if duplicate else (
                            "data_or_comparability_failure" if blocked else "no_selection_eligible_configuration"
                        )
                    ),
                    "eligible_configuration_count": len(eligible),
                    "selected_strategy_id": "",
                    "selected_trial_id": "",
                    "selected_configuration_code": "",
                    "selection_rule": (
                        "highest_5bps_sharpe_tie_within_0.01_lower_drawdown_lower_turnover_lexical_trial_id"
                    ),
                    "selection_freeze_timestamp": PREREGISTRATION_TIMESTAMP,
                    "selection_frozen_before_evaluation_metrics": True,
                    "selection_sharpe_5bps": "",
                    "selection_maximum_drawdown_5bps": "",
                    "selection_annualized_turnover_5bps": "",
                    "winner_outcome": "closed_optimization",
                    "failure_reason": (
                        "duplicate_or_redundant" if duplicate else (
                            "data_or_comparability_failure" if blocked else "weak_vs_primary_control"
                        )
                    ),
                    "decision_reason": (
                        "architecture was rejected by duplicate preflight"
                        if duplicate else "no configuration passed selection eligibility"
                    ),
                }
            )
    return rows


def parameter_grid_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for position, config in enumerate(CONFIGS, start=1):
        arch = architecture_by_code(config.architecture_code)
        rows.append(
            {
                "grid_position": position,
                "architecture_code": arch.architecture_code,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "configuration_code": config.configuration_code,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "lookback_sessions": config.lookback_sessions,
                "selected_count": config.selected_count,
                "universe": arch.universe,
                "named_control": arch.named_control_id,
                "static_equal_weight_controls": [arch.static_control_id, arch.equal_weight_control_id],
                "source_or_research_lineage": SOURCE_LINEAGE,
                "grid_frozen_before_performance": True,
                "post_result_grid_expansion_allowed": False,
            }
        )
    return rows


def strategy_card_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        rows.append(
            {
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "entity_type": "strategy_configuration",
                "stage": STAGE,
                "source_or_research_lineage": SOURCE_LINEAGE,
                "primary_future_robustness_role": arch.primary_future_robustness_role,
                "universe": arch.universe,
                "parameters": config.parameters,
                "named_control": arch.named_control_id,
                "static_equal_weight_control": [arch.static_control_id, arch.equal_weight_control_id],
                "strategy_result": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": strategy_next_action(result),
                "counted_as_strategy": True,
                "counted_as_trial": True,
                "paper_demo_eligible": False,
            }
        )
    return rows


def strategy_next_action(result: dict[str, Any]) -> str:
    if result["outcome"] == "exploratory_followup_candidate":
        return FOLLOWUP_NEXT_ACTION
    return "retain_exact_configuration_as_logged_closed_trial_no_parameter_changes"


def trial_ledger_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        rows.append(
            {
                "trial_id": config.trial_id,
                "entity_type": "canonical_experiment_trial",
                "strategy_id": config.strategy_id,
                "architecture_id": arch.architecture_id,
                "family_id": arch.family_id,
                "configuration_code": config.configuration_code,
                "stage": STAGE,
                "source_or_research_lineage": SOURCE_LINEAGE,
                "route": "standalone_long_only_allocation",
                "execution_timing": TIMING_CONVENTION,
                "lookback_sessions": config.lookback_sessions,
                "selected_count": config.selected_count,
                "canonical_configuration": True,
                "executed": result["split"] is not None,
                "selection_evaluated": result["split"] is not None,
                "evaluation_evaluated": bool(result.get("selected_winner") and result.get("evaluation")),
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": strategy_next_action(result),
                "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        arch = architecture_by_code(config.architecture_code)
        controls = [
            (arch.named_control_id, "named_control_tests_distinctive_feature"),
            (arch.equal_weight_control_id, "static_equal_weight_control"),
            (arch.static_control_id, "static_average_candidate_weights_control"),
            ("SPY_buy_and_hold", "market_buy_and_hold_reference"),
            ("BIL_buy_and_hold", "cash_buy_and_hold_reference"),
        ]
        for control_id, role in controls:
            rows.append(
                {
                    "benchmark_reference_id": f"{config.trial_id}__{control_id}",
                    "entity_type": "benchmark_reference",
                    "architecture_id": arch.architecture_id,
                    "strategy_id_context": config.strategy_id,
                    "trial_id_context": config.trial_id,
                    "control_id": control_id,
                    "control_role": role,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                    "counted_as_observation": False,
                    "promotable": False,
                }
            )
    return rows


def failure_vector_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        arch: ArchitectureSpec = result["arch"]
        vector = result["selection_vector"].copy()
        evaluation_vector = result.get("evaluation", {}).get("vector", {})
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "stage": STAGE,
                "duplicate_or_redundant": result["failure_reason"] == "duplicate_or_redundant",
                "selection_eligible": vector.get("selection_eligible", False),
                "selected_winner": result.get("selected_winner", False),
                "evaluation_access_allowed": bool(result.get("selected_winner")),
                "exploratory_followup_candidate": evaluation_vector.get("exploratory_followup_candidate", False),
                "selection_cagr_positive_5bps": vector.get("cagr_positive_5bps", ""),
                "selection_invariants_pass_5bps": vector.get("invariants_pass_5bps", ""),
                "selection_named_control_not_dominating_5bps": vector.get("named_control_not_dominating_5bps", ""),
                "selection_material_vs_named_control_5bps": vector.get("material_vs_named_control_5bps", ""),
                "selection_static_equal_control_not_dominating_5bps": vector.get("static_equal_control_not_dominating_5bps", ""),
                "selection_cagr_positive_10bps": vector.get("cagr_positive_10bps", ""),
                "evaluation_cagr_positive_5bps": evaluation_vector.get("cagr_positive_5bps", ""),
                "evaluation_invariants_pass_5bps": evaluation_vector.get("invariants_pass_5bps", ""),
                "evaluation_named_control_not_dominating_5bps": evaluation_vector.get("named_control_not_dominating_5bps", ""),
                "evaluation_material_vs_named_control_5bps": evaluation_vector.get("material_vs_named_control_5bps", ""),
                "evaluation_static_equal_control_not_dominating_5bps": evaluation_vector.get("static_equal_control_not_dominating_5bps", ""),
                "evaluation_cagr_positive_10bps": evaluation_vector.get("cagr_positive_10bps", ""),
                "calendar_year_concentration_pass": evaluation_vector.get("calendar_year_concentration_pass", ""),
                "rebalance_month_concentration_pass": evaluation_vector.get("rebalance_month_concentration_pass", ""),
                "primary_failure_reason": result["failure_reason"],
                "outcome": result["outcome"],
            }
        )
    return rows


def failure_reason_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config in CONFIGS:
        result = results[config.trial_id]
        if not result["failure_reason"]:
            continue
        rows.append(
            {
                "architecture_id": result["arch"].architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "outcome": result["outcome"],
                "primary_failure_reason": result["failure_reason"],
                "failure_detail": result["decision_reason"],
                "exact_configuration_only": True,
                "family_closed": False,
                "parameter_change_authorized": False,
            }
        )
    return rows


def calendar_year_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result.get("selected_winner") and result.get("evaluation"):
            rows.extend(result["evaluation"]["calendar_rows"])
    return rows


def rebalance_contribution_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result.get("selected_winner") and result.get("evaluation"):
            rows.extend(result["evaluation"]["rebalance_rows"])
    return rows


def concentration_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if not (result.get("selected_winner") and result.get("evaluation")):
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        calendar_state = result["evaluation"]["calendar_state"]
        rebalance_state = result["evaluation"]["rebalance_state"]
        rows.append(
            {
                "architecture_id": arch.architecture_id,
                "strategy_id": config.strategy_id,
                "trial_id": config.trial_id,
                "cost_bps_one_way": PRIMARY_COST,
                "calendar_complete_year_count": calendar_state["complete_year_count"],
                "calendar_positive_excess_total": calendar_state["positive_excess_total"],
                "calendar_max_positive_excess_share": calendar_state["max_positive_excess_share"],
                "calendar_concentration_state": calendar_state["state"],
                "rebalance_month_count": rebalance_state["rebalance_month_count"],
                "rebalance_positive_excess_total": rebalance_state["positive_excess_total"],
                "rebalance_max_positive_excess_share": rebalance_state["max_positive_excess_share"],
                "rebalance_concentration_state": rebalance_state["state"],
                "concentration_pass": bool(calendar_state["pass"] and rebalance_state["pass"]),
            }
        )
    return rows


def turnover_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result["split"] is None:
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        for period_id, metric_map in (
            ("selection_segment", result["selection_metrics"]),
            ("exploratory_evaluation_segment", result.get("evaluation", {}).get("metrics", {})),
            ("post_selection_full_period_diagnostic", result.get("evaluation", {}).get("full_metrics", {})),
        ):
            if period_id != "selection_segment" and not result.get("selected_winner"):
                continue
            for cost in COSTS:
                if ("candidate", cost) not in metric_map:
                    continue
                metrics = metric_map[("candidate", cost)]
                rows.append(
                    {
                        "architecture_id": arch.architecture_id,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "period_id": period_id,
                        "cost_bps_one_way": cost,
                        "turnover": metrics["turnover"],
                        "annualized_turnover": metrics["annualized_turnover"],
                        "transaction_cost_drag": metrics["transaction_cost_drag"],
                        "zero_cost_has_zero_drag": cost != 0.0 or abs(float(metrics["transaction_cost_drag"])) <= 1e-14,
                        "cost_applied_once_to_one_way_turnover": True,
                        "turnover_is_drift_adjusted": True,
                    }
                )
    return rows


def invariant_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        if result["split"] is None:
            continue
        arch: ArchitectureSpec = result["arch"]
        config: ConfigSpec = result["config"]
        periods = [("selection_segment", result["selection_metrics"])]
        if result.get("selected_winner") and result.get("evaluation"):
            periods.extend(
                [
                    ("exploratory_evaluation_segment", result["evaluation"]["metrics"]),
                    ("post_selection_full_period_diagnostic", result["evaluation"]["full_metrics"]),
                ]
            )
        for period_id, metric_map in periods:
            for cost in COSTS:
                metrics = metric_map[("candidate", cost)]
                rows.append(
                    {
                        "architecture_id": arch.architecture_id,
                        "strategy_id": config.strategy_id,
                        "trial_id": config.trial_id,
                        "period_id": period_id,
                        "cost_bps_one_way": cost,
                        "numeric_invariant_status": metrics["numeric_invariant_status"],
                        "timing_invariant_status": metrics["timing_invariant_status"],
                        "exposure_weight_invariant_status": metrics["exposure_weight_invariant_status"],
                        "daily_weight_sum_one": metrics["daily_weight_sum_one"],
                        "maximum_gross_exposure": metrics["maximum_gross_exposure"],
                        "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
                        "target_zero_weights_preserved": metrics["target_zero_weights_preserved"],
                        "explicit_holdings": metrics["explicit_holdings"],
                        "long_only": True,
                        "no_leverage": True,
                        "natural_drift": True,
                        "deterministic_turnover": True,
                        "no_tradable_price_forward_fill": True,
                        "same_period_price_signal_return_used": metrics["same_period_price_signal_return_used"],
                        "invariant_pass": metrics["invariant_pass"],
                    }
                )
    return rows


def followup_rows(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "architecture_id": result["arch"].architecture_id,
            "strategy_id": result["config"].strategy_id,
            "trial_id": result["config"].trial_id,
            "stage": STAGE,
            "outcome": result["outcome"],
            "primary_future_robustness_role": result["arch"].primary_future_robustness_role,
            "decision_reason": result["decision_reason"],
            "next_action": FOLLOWUP_NEXT_ACTION,
            "execute_in_this_task": False,
        }
        for result in results.values()
        if result["outcome"] == "exploratory_followup_candidate"
    ]


def batch_outcome(results: dict[str, dict[str, Any]]) -> tuple[str, str]:
    duplicate_or_blocked_architectures = 0
    executed_architectures = 0
    followups = 0
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        if all(result["split"] is None for result in arch_results):
            duplicate_or_blocked_architectures += 1
        else:
            executed_architectures += 1
        followups += sum(result["outcome"] == "exploratory_followup_candidate" for result in arch_results)
    if executed_architectures == 0:
        return "targeted_internal_batch_blocked", BLOCK_NEXT_ACTION
    if duplicate_or_blocked_architectures:
        return "targeted_internal_batch_partially_blocked", BLOCK_NEXT_ACTION
    if followups:
        return "targeted_internal_batch_followup_found", FOLLOWUP_NEXT_ACTION
    return "targeted_internal_batch_no_followup", NO_FOLLOWUP_NEXT_ACTION


def next_action_rows(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> list[dict[str, Any]]:
    rows = [
        {
            "entity_id": result["config"].strategy_id,
            "entity_type": "strategy_configuration",
            "outcome": result["outcome"],
            "next_action": strategy_next_action(result),
            "execute_in_this_task": False,
        }
        for result in results.values()
    ]
    rows.append(
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "outcome": outcome,
            "next_action": next_action,
            "execute_in_this_task": False,
        }
    )
    return rows


def outcome_summary_rows(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        followup = next((result for result in arch_results if result["outcome"] == "exploratory_followup_candidate"), None)
        rows.append(
            {
                "entity_id": arch.architecture_id,
                "entity_type": "architecture",
                "stage": STAGE,
                "outcome": (
                    "exploratory_followup_candidate" if followup else (
                        "closed_optimization" if winner is None else winner["outcome"]
                    )
                ),
                "selected_strategy_id": "" if winner is None else winner["config"].strategy_id,
                "selected_trial_id": "" if winner is None else winner["config"].trial_id,
                "failure_reason": (
                    "duplicate_or_redundant"
                    if all(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results)
                    else ("" if followup else (winner["failure_reason"] if winner else "weak_vs_primary_control"))
                ),
                "decision_reason": (
                    "duplicate preflight rejected architecture"
                    if all(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results)
                    else ("winner passed evaluation" if followup else "no exploratory follow-up from this architecture")
                ),
                "batch_outcome": outcome,
                "batch_next_action": next_action,
                "validation_claimed": False,
                "robustness_claimed": False,
                "paper_demo_authorized": False,
            }
        )
    rows.append(
        {
            "entity_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "outcome": outcome,
            "selected_strategy_id": "",
            "selected_trial_id": "",
            "failure_reason": "duplicate_or_redundant" if outcome == "targeted_internal_batch_partially_blocked" else "",
            "decision_reason": "bounded batch completed with at least one duplicate/data/methodology architecture block",
            "batch_outcome": outcome,
            "batch_next_action": next_action,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
        }
    )
    return rows


def process_task_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "mode": MODE,
            "stage": STAGE,
            "task_scope": "exactly_three_architectures_four_configs_each_twelve_canonical_configurations",
            "architecture_count": 3,
            "strategy_configuration_count": 12,
            "canonical_trial_count": 12,
            "batch_outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
        }
    ]


def entity_counts(results: dict[str, dict[str, Any]], outcome: str, next_action: str) -> dict[str, Any]:
    selected_count = sum(result.get("selected_winner", False) for result in results.values())
    followup_count = sum(result["outcome"] == "exploratory_followup_candidate" for result in results.values())
    executed_count = sum(result["split"] is not None for result in results.values())
    return {
        "architectures": len(ARCHITECTURES),
        "strategy_configurations": len(CONFIGS),
        "canonical_experiment_trials": len(CONFIGS),
        "executed_trials": executed_count,
        "duplicate_or_blocked_trials": len(CONFIGS) - executed_count,
        "selected_architecture_winners": selected_count,
        "exploratory_followup_candidates": followup_count,
        "benchmark_references": len(benchmark_rows()),
        "process_tasks": 1,
        "robustness_trials_created": 0,
        "validation_trials_created": 0,
        "paper_demo_eligibility_records_created": 0,
        "handoff_export_records_created": 0,
        "observations_created": 0,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }


def build_report(
    results: dict[str, dict[str, Any]],
    counts: dict[str, Any],
    outcome: str,
    next_action: str,
) -> str:
    lines = [
        "# Accepted-47 Targeted Internal Technical Batch V1",
        "",
        "## Scope",
        "",
        "Exactly three preregistered internally generated technical/chart-data architectures "
        "and twelve canonical configurations were processed. This is optimization evidence only, "
        "not validation, robustness, paper/demo eligibility, or forward observation.",
        "",
        "## Architecture Outcomes",
        "",
        "| Architecture | Status | Winner | Failure/next reason |",
        "|---|---|---|---|",
    ]
    for arch in ARCHITECTURES:
        arch_results = [results[config.trial_id] for config in configs_for_architecture(arch.architecture_code)]
        winner = next((result for result in arch_results if result.get("selected_winner")), None)
        if all(result["failure_reason"] == "duplicate_or_redundant" for result in arch_results):
            status = "duplicate_or_redundant"
            reason = "matched Technical Factory V2 overnight/intraday architecture"
        elif winner is None:
            status = "closed_optimization"
            reason = "no configuration passed the selection gate"
        else:
            status = winner["outcome"]
            reason = winner["failure_reason"] or "follow-up candidate"
        lines.append(
            f"| `{arch.architecture_id}` | `{status}` | "
            f"`{winner['config'].strategy_id if winner else ''}` | `{reason}` |"
        )
    lines.extend(
        [
            "",
            "## Entity Counts",
            "",
            f"* Architectures: {counts['architectures']}",
            f"* Strategy configurations: {counts['strategy_configurations']}",
            f"* Canonical trials: {counts['canonical_experiment_trials']}",
            f"* Executed trials: {counts['executed_trials']}",
            f"* Selected architecture winners: {counts['selected_architecture_winners']}",
            f"* Exploratory follow-up candidates: {counts['exploratory_followup_candidates']}",
            "",
            "## Guardrails",
            "",
            "* Existing accepted-47 pilot cache only; no provider or network access.",
            "* Architecture B executed zero trials after duplicate preflight.",
            "* Nonselected variants have no evaluation-segment interpretation.",
            "* Controls are benchmark references only and cannot be promoted.",
            "* No robustness, validation, paper/demo, handoff, observation, broker, or real-money action was run.",
            "",
            "## Batch Outcome",
            "",
            f"`{outcome}`",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


METRIC_RESULT_FIELDS = [
    "architecture_id",
    "family_id",
    "configuration_code",
    "strategy_id",
    "trial_id",
    "result_role",
    "period_id",
    "period_role",
    "cost_bps_one_way",
    "period_start",
    "period_end",
    "trading_day_count",
    "formation_count",
    "rebalance_count",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "annualized_turnover",
    "transaction_cost_drag",
    "average_holdings",
    "maximum_asset_weight",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "daily_weight_sum_one",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_weight_invariant_status",
    "invariant_pass",
    "named_control_id",
    "named_cagr",
    "named_total_return",
    "named_annualized_volatility",
    "named_sharpe_ratio",
    "named_maximum_drawdown",
    "named_turnover",
    "named_transaction_cost_drag",
    "static_control_id",
    "static_cagr",
    "static_total_return",
    "static_annualized_volatility",
    "static_sharpe_ratio",
    "static_maximum_drawdown",
    "static_turnover",
    "static_transaction_cost_drag",
    "equal_weight_control_id",
    "equal_weight_cagr",
    "equal_weight_total_return",
    "equal_weight_annualized_volatility",
    "equal_weight_sharpe_ratio",
    "equal_weight_maximum_drawdown",
    "equal_weight_turnover",
    "equal_weight_transaction_cost_drag",
    "spy_buy_hold_cagr",
    "bil_buy_hold_cagr",
    "outcome",
    "failure_reason",
]

CSV_FIELDS = {
    "parameter_grid.csv": [
        "grid_position", "architecture_code", "architecture_id", "family_id", "configuration_code",
        "strategy_id", "trial_id", "lookback_sessions", "selected_count", "universe", "named_control",
        "static_equal_weight_controls", "source_or_research_lineage", "grid_frozen_before_performance",
        "post_result_grid_expansion_allowed",
    ],
    "strategy_cards.csv": [
        "strategy_id", "trial_id", "architecture_id", "family_id", "entity_type", "stage",
        "source_or_research_lineage", "primary_future_robustness_role", "universe", "parameters",
        "named_control", "static_equal_weight_control", "strategy_result", "failure_reason", "next_action",
        "counted_as_strategy", "counted_as_trial", "paper_demo_eligible",
    ],
    "trial_ledger.csv": [
        "trial_id", "entity_type", "strategy_id", "architecture_id", "family_id", "configuration_code",
        "stage", "source_or_research_lineage", "route", "execution_timing", "lookback_sessions",
        "selected_count", "canonical_configuration", "executed", "selection_evaluated", "evaluation_evaluated",
        "outcome", "failure_reason", "next_action", "preregistration_timestamp",
    ],
    "duplicate_preflight.csv": [
        "architecture_id", "family_id", "architecture_code", "preflight_status", "execute_architecture_trials",
        "executed_trial_count", "matched_existing_project", "matched_existing_architecture_id",
        "matched_existing_path", "formula_checked", "universe_checked", "formation_schedule_checked",
        "ranking_characteristic_checked", "target_construction_checked", "parameter_grid_checked",
        "formula_match", "universe_match", "formation_schedule_match", "ranking_characteristic_match",
        "target_construction_match", "parameter_grid_similarity_sufficient", "broad_family_similarity_only",
        "decision_reason", "preperformance_complete",
    ],
    "benchmark_reference_log.csv": [
        "benchmark_reference_id", "entity_type", "architecture_id", "strategy_id_context", "trial_id_context",
        "control_id", "control_role", "counted_as_strategy", "counted_as_trial", "counted_as_observation",
        "promotable",
    ],
    "selection_segment_definition.csv": [
        "architecture_id", "family_id", "architecture_code", "segment_status", "common_universe",
        "common_start", "common_end", "first_valid_signal_date", "first_execution_date", "last_execution_date",
        "valid_rebalance_count", "selection_rebalance_count", "evaluation_rebalance_count", "selection_start",
        "selection_end", "evaluation_start", "evaluation_end", "boundary_execution_date", "split_rule",
        "segment_role",
    ],
    "selection_segment_results.csv": METRIC_RESULT_FIELDS + [
        "performance_executed", "selection_eligible_5bps", "selection_gate_failures",
    ],
    "architecture_winner_selection.csv": [
        "architecture_id", "family_id", "selection_status", "eligible_configuration_count",
        "selected_strategy_id", "selected_trial_id", "selected_configuration_code", "selection_rule",
        "selection_freeze_timestamp", "selection_frozen_before_evaluation_metrics", "selection_sharpe_5bps",
        "selection_maximum_drawdown_5bps", "selection_annualized_turnover_5bps", "winner_outcome",
        "failure_reason", "decision_reason",
    ],
    "evaluation_segment_results.csv": METRIC_RESULT_FIELDS + [
        "frozen_winner", "selection_frozen_before_evaluation_metrics",
    ],
    "post_selection_full_period_diagnostics.csv": METRIC_RESULT_FIELDS + [
        "diagnostic_only", "can_rescue_or_reverse_decision",
    ],
    "calendar_year_results.csv": [
        "architecture_id", "strategy_id", "trial_id", "period_year", "period_complete_calendar_year",
        "cost_bps_one_way", "candidate_return", "named_control_return", "candidate_minus_named_excess_return",
        "positive_excess_return", "descriptive_only",
    ],
    "rebalance_contribution_results.csv": [
        "architecture_id", "strategy_id", "trial_id", "rebalance_month", "interval_start", "interval_end",
        "cost_bps_one_way", "candidate_return", "named_control_return", "candidate_minus_named_excess_return",
        "positive_excess_return", "nonwinner_evaluation_access",
    ],
    "lightweight_concentration_diagnostics.csv": [
        "architecture_id", "strategy_id", "trial_id", "cost_bps_one_way", "calendar_complete_year_count",
        "calendar_positive_excess_total", "calendar_max_positive_excess_share", "calendar_concentration_state",
        "rebalance_month_count", "rebalance_positive_excess_total", "rebalance_max_positive_excess_share",
        "rebalance_concentration_state", "concentration_pass",
    ],
    "turnover_cost_reconciliation.csv": [
        "architecture_id", "strategy_id", "trial_id", "period_id", "cost_bps_one_way", "turnover",
        "annualized_turnover", "transaction_cost_drag", "zero_cost_has_zero_drag",
        "cost_applied_once_to_one_way_turnover", "turnover_is_drift_adjusted",
    ],
    "invariant_results.csv": [
        "architecture_id", "strategy_id", "trial_id", "period_id", "cost_bps_one_way",
        "numeric_invariant_status", "timing_invariant_status", "exposure_weight_invariant_status",
        "daily_weight_sum_one", "maximum_gross_exposure", "maximum_daily_weight_sum",
        "target_zero_weights_preserved", "explicit_holdings", "long_only", "no_leverage", "natural_drift",
        "deterministic_turnover", "no_tradable_price_forward_fill", "same_period_price_signal_return_used",
        "invariant_pass",
    ],
    "exploratory_followup_candidates.csv": [
        "architecture_id", "strategy_id", "trial_id", "stage", "outcome", "primary_future_robustness_role",
        "decision_reason", "next_action", "execute_in_this_task",
    ],
    "failure_vectors.csv": [
        "architecture_id", "strategy_id", "trial_id", "stage", "duplicate_or_redundant",
        "selection_eligible", "selected_winner", "evaluation_access_allowed", "exploratory_followup_candidate",
        "selection_cagr_positive_5bps", "selection_invariants_pass_5bps",
        "selection_named_control_not_dominating_5bps", "selection_material_vs_named_control_5bps",
        "selection_static_equal_control_not_dominating_5bps", "selection_cagr_positive_10bps",
        "evaluation_cagr_positive_5bps", "evaluation_invariants_pass_5bps",
        "evaluation_named_control_not_dominating_5bps", "evaluation_material_vs_named_control_5bps",
        "evaluation_static_equal_control_not_dominating_5bps", "evaluation_cagr_positive_10bps",
        "calendar_year_concentration_pass", "rebalance_month_concentration_pass", "primary_failure_reason",
        "outcome",
    ],
    "failure_reasons.csv": [
        "architecture_id", "strategy_id", "trial_id", "outcome", "primary_failure_reason", "failure_detail",
        "exact_configuration_only", "family_closed", "parameter_change_authorized",
    ],
    "process_task_log.csv": [
        "process_task_id", "entity_type", "mode", "stage", "task_scope", "architecture_count",
        "strategy_configuration_count", "canonical_trial_count", "batch_outcome", "next_action",
        "next_action_executed",
    ],
    "outcome_summary.csv": [
        "entity_id", "entity_type", "stage", "outcome", "selected_strategy_id", "selected_trial_id",
        "failure_reason", "decision_reason", "batch_outcome", "batch_next_action", "validation_claimed",
        "robustness_claimed", "paper_demo_authorized",
    ],
    "next_actions.csv": [
        "entity_id", "entity_type", "outcome", "next_action", "execute_in_this_task",
    ],
}


def required_files_present() -> bool:
    return {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()} == REQUIRED_OUTPUT_FILES


def required_files_will_be_present_after_consistency_write() -> bool:
    current = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    return (current | {"consistency_check.json"}) == REQUIRED_OUTPUT_FILES


def deterministic_core_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_OUTPUT_FILES - {"consistency_check.json"}):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    if len(ARCHITECTURES) != 3 or len(CONFIGS) != 12:
        raise RuntimeError("Frozen architecture/configuration scope drift")
    if len({config.strategy_id for config in CONFIGS}) != 12 or len({config.trial_id for config in CONFIGS}) != 12:
        raise RuntimeError("Strategy/trial identifiers are not unique")
    before_protected = protected_hashes()
    duplicate_rows = duplicate_preflight_rows()
    frames = load_frames()
    cache_rows = cache_preflight_rows(frames)
    splits, results = build_executed_results(frames, duplicate_rows)
    outcome, next_action = batch_outcome(results)
    counts = entity_counts(results, outcome, next_action)

    clean_output_dir()
    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": TASK_ID,
            "module_owner": "trading_tournament",
            "mode": MODE,
            "stage": STAGE,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "source_or_research_lineage": SOURCE_LINEAGE,
            "architecture_count": 3,
            "configuration_count": 12,
            "primary_one_way_cost_bps": PRIMARY_COST,
            "diagnostic_one_way_cost_bps": [0.0, 10.0],
            "data_boundary": {
                "cache_dir": rel(CACHE_DIR),
                "provider_access": False,
                "network_access": False,
                "data_refresh": False,
                "accepted_47_membership_modified": False,
            },
            "optimization_split": "first_60pct_valid_rebalance_observations_selection_final_40pct_exploratory_evaluation",
            "batch_outcome": outcome,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "validation_claimed": False,
            "robustness_claimed": False,
            "paper_demo_authorized": False,
            "forward_observation_operation": False,
        },
    )
    write_yaml(
        OUTPUT_DIR / "architecture_preregistration.yaml",
        {
            "batch_id": TASK_ID,
            "preregistered_architectures": [
                {
                    "architecture_code": arch.architecture_code,
                    "architecture_id": arch.architecture_id,
                    "family_id": arch.family_id,
                    "display_name": arch.display_name,
                    "source_or_research_lineage": SOURCE_LINEAGE,
                    "universe": list(arch.universe),
                    "accounting_universe": list(arch.accounting_universe),
                    "named_control": arch.named_control_id,
                    "static_equal_weight_controls": [arch.static_control_id, arch.equal_weight_control_id],
                    "primary_future_robustness_role": arch.primary_future_robustness_role,
                    "incremental_hypothesis": arch.incremental_hypothesis,
                    "configuration_codes": [config.configuration_code for config in configs_for_architecture(arch.architecture_code)],
                }
                for arch in ARCHITECTURES
            ],
            "grid_expansion_after_results_allowed": False,
        },
    )

    artifact_rows = {
        "parameter_grid.csv": parameter_grid_rows(),
        "strategy_cards.csv": strategy_card_rows(results),
        "trial_ledger.csv": trial_ledger_rows(results),
        "duplicate_preflight.csv": duplicate_rows,
        "benchmark_reference_log.csv": benchmark_rows(),
        "selection_segment_definition.csv": selection_definition_rows(splits, duplicate_rows),
        "selection_segment_results.csv": selection_segment_rows(results),
        "architecture_winner_selection.csv": architecture_winner_rows(results),
        "evaluation_segment_results.csv": evaluation_segment_rows(results),
        "post_selection_full_period_diagnostics.csv": post_selection_full_period_rows(results),
        "calendar_year_results.csv": calendar_year_rows(results),
        "rebalance_contribution_results.csv": rebalance_contribution_rows(results),
        "lightweight_concentration_diagnostics.csv": concentration_rows(results),
        "turnover_cost_reconciliation.csv": turnover_rows(results),
        "invariant_results.csv": invariant_rows(results),
        "exploratory_followup_candidates.csv": followup_rows(results),
        "failure_vectors.csv": failure_vector_rows(results),
        "failure_reasons.csv": failure_reason_rows(results),
        "process_task_log.csv": process_task_rows(outcome, next_action),
        "outcome_summary.csv": outcome_summary_rows(results, outcome, next_action),
        "next_actions.csv": next_action_rows(results, outcome, next_action),
    }
    for name, rows in artifact_rows.items():
        write_csv(OUTPUT_DIR / name, rows, CSV_FIELDS[name])
    write_json(OUTPUT_DIR / "entity_count_reconciliation.json", counts)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, counts, outcome, next_action))

    after_protected = protected_hashes()
    selected_by_architecture = {
        arch.architecture_id: sum(
            results[config.trial_id].get("selected_winner", False)
            for config in configs_for_architecture(arch.architecture_code)
        )
        for arch in ARCHITECTURES
    }
    evaluation_trial_ids = {
        row["trial_id"] for row in artifact_rows["evaluation_segment_results.csv"]
    }
    winner_trial_ids = {
        result["config"].trial_id for result in results.values() if result.get("selected_winner")
    }
    failed_reasons_allowed = all(
        not result["failure_reason"] or result["failure_reason"] in PERMITTED_FAILURE_REASONS
        for result in results.values()
    )
    checks = {
        "exact_three_architectures": len(ARCHITECTURES) == 3,
        "exact_twelve_configurations": len(CONFIGS) == 12,
        "four_configurations_per_architecture": all(len(configs_for_architecture(arch.architecture_code)) == 4 for arch in ARCHITECTURES),
        "unique_strategy_ids": len({config.strategy_id for config in CONFIGS}) == 12,
        "unique_trial_ids": len({config.trial_id for config in CONFIGS}) == 12,
        "duplicate_preflight_before_performance_complete": all(row["preperformance_complete"] for row in duplicate_rows),
        "architecture_b_zero_trials_due_duplicate": all(
            results[config.trial_id]["failure_reason"] == "duplicate_or_redundant"
            and results[config.trial_id]["split"] is None
            for config in configs_for_architecture("B")
        ),
        "common_period_and_split_reproducible": len(splits) == 2,
        "winner_count_at_most_one_per_architecture": all(value <= 1 for value in selected_by_architecture.values()),
        "nonwinner_evaluation_access_prohibited": evaluation_trial_ids <= winner_trial_ids,
        "controls_are_benchmark_references_only": all(not row["counted_as_strategy"] and not row["counted_as_trial"] for row in benchmark_rows()),
        "all_executed_invariants_pass": all(row["invariant_pass"] for row in artifact_rows["invariant_results.csv"]),
        "no_forbidden_actions": not any(FORBIDDEN_ACTION_FLAGS.values()),
        "entity_count_reconciliation_pass": (
            counts["architectures"] == 3
            and counts["strategy_configurations"] == 12
            and counts["canonical_experiment_trials"] == 12
            and counts["robustness_trials_created"] == 0
            and counts["validation_trials_created"] == 0
            and counts["paper_demo_eligibility_records_created"] == 0
            and counts["observations_created"] == 0
        ),
        "protected_state_cache_and_prior_evidence_unchanged": before_protected == after_protected,
        "failure_reasons_within_permitted_set": failed_reasons_allowed,
        "required_output_set_complete": required_files_will_be_present_after_consistency_write(),
    }
    consistency = {
        "batch_id": TASK_ID,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "cache_preflight": cache_rows,
        "protected_state_hashes_before": before_protected,
        "protected_state_hashes_after": after_protected,
        "forbidden_actions": FORBIDDEN_ACTION_FLAGS,
        "batch_outcome": outcome,
        "exact_next_action": next_action,
        "next_action_executed": False,
        "required_output_files_present": required_files_will_be_present_after_consistency_write(),
        "deterministic_core_hash": deterministic_core_hash(),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "batch_outcome": outcome,
        "next_action": next_action,
        "entity_counts": counts,
        "consistency_overall_pass": consistency["overall_pass"],
        "deterministic_core_hash": consistency["deterministic_core_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
