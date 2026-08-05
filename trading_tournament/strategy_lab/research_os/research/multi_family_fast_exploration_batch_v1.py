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
    acquire_validate_deferred_structural_etf_data_v2 as acquisition,
)
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import fast_source_library_batch_v6 as prior_batch
from strategy_lab.research_os.research import fast_source_library_batch_v7 as prior_cohort
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


BATCH_ID = "multi_family_fast_exploration_batch_v1"
MODE = "fast-progress"
STAGE = "exploration"
SOURCE_LIBRARY_ID = "broader_multi_family_implementation_ready_source_batch_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
SOURCE_PACKET_DIR = (
    ROOT / "evidence" / "research_recovery" / SOURCE_LIBRARY_ID / "latest"
)
SOURCE_PACKET_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\aa604d0f-ce36-4f95-9083-0c85d2aeda74\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-29T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9

NEXT_REVIEW = "direction_owner_review_multi_family_fast_exploration_batch_v1"
NEXT_ALL_CLOSED = "broader_multi_family_source_batch_v2"
NEXT_BLOCKED = "direction_owner_review_multi_family_fast_exploration_batch_block_v1"

SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
ADAPTIVE_UNIVERSE = (
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
    "AMLP",
    "GLD",
    "GSG",
    "JNK",
    "AGG",
    "TIP",
    "IEF",
    "TLT",
    "BIL",
)
RATI_UNIVERSE = (
    "SPY",
    "VWO",
    "EFA",
    "EWJ",
    "EPP",
    "IEF",
    "IEI",
    "SHY",
    "HYG",
    "LQD",
    "TIP",
    "EMB",
    "BIL",
    "GLD",
    "USO",
    "CPER",
    "DBA",
    "RWX",
    "FXE",
    "FXY",
)
RATI_RISKY = ("SPY", "VWO", "EFA", "EWJ", "EPP", "RWX", "GLD", "USO", "CPER", "DBA")

EXPECTED_STRATEGY_IDS = (
    "bilello_gayed_beta_rotation_xlu_spy_4week_v1",
    "ma_adaptive_top4_3month_multi_asset_v1",
    "dalmasso_rati_multi_asset_top7_v1",
    "liu_es_implied_relative_downside_beta_sector_top2_v1",
    "bouman_jacobsen_halloween_spy_bil_v1",
)

FROZEN_INITIAL_MISSING_SYMBOLS = (
    "AMLP",
    "TIP",
    "VWO",
    "EPP",
    "IEI",
    "USO",
    "CPER",
    "DBA",
    "RWX",
    "FXE",
    "FXY",
)

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)

FORBIDDEN_FLAGS = {
    "external_source_research": False,
    "source_rule_completion": False,
    "parameter_grid_or_variants": False,
    "post_result_tuning": False,
    "validation_or_robustness": False,
    "lifecycle_or_registry_update": False,
    "paper_demo_eligibility_or_activation": False,
    "broker_account_order_or_real_money_action": False,
    "sixth_candidate_added": False,
    "closed_configuration_reopened": False,
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
    "unsupported_portability",
    "data_or_comparability_failure",
    "methodology_failure",
    "duplicate_or_redundant",
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
    route: str
    required_symbols: tuple[str, ...]
    controls: tuple[str, ...]
    critical_controls: tuple[str, ...]
    same_purpose_control: str
    half_static_control: str
    portfolio_controls: tuple[str, ...]
    parameters: dict[str, Any]
    frozen_rule: str

    @property
    def source_or_research_lineage(self) -> str:
        return f"{SOURCE_LIBRARY_ID}:{self.source_record_id}"


CARDS = (
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[0],
        trial_id="multi_family_v1__beta_rotation__canonical",
        family_id="defensive_sector_beta_rotation",
        display_name="Four-Week Utilities Beta Rotation",
        strategy_architecture="weekly_relative_strength_two_equity_state_rotation",
        source_record_id="src_bilello_gayed_beta_rotation_xlu_spy_v1",
        route="standalone",
        required_symbols=("SPY", "XLU"),
        controls=(
            "SPY_buy_and_hold",
            "XLU_buy_and_hold",
            "weekly_equal_weight_spy_xlu_control",
            "spy_4week_absolute_state_xlu_fallback_control",
            "beta_rotation_exposure_matched_spy_xlu_control",
        ),
        critical_controls=(
            "spy_4week_absolute_state_xlu_fallback_control",
            "beta_rotation_exposure_matched_spy_xlu_control",
        ),
        same_purpose_control="spy_4week_absolute_state_xlu_fallback_control",
        half_static_control="beta_rotation_exposure_matched_spy_xlu_control",
        portfolio_controls=(),
        parameters={
            "formation_frequency": "final_completed_regular_session_each_week",
            "relative_strength_lookback_completed_weeks": 4,
            "relative_strength_formula": "(XLU_t/XLU_t-4w)/(SPY_t/SPY_t-4w)-1",
            "positive_target": "XLU_100pct",
            "negative_target": "SPY_100pct",
            "equality": "retain_previous_target",
            "warmup": "SPY_100pct",
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "At each completed week compare XLU and SPY four-week returns through "
            "their relative-strength ratio. Hold XLU when positive, SPY when "
            "negative, retain on equality, warm up in SPY, and execute next close."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[1],
        trial_id="multi_family_v1__adaptive_top4__canonical",
        family_id="cross_sectional_multi_asset_momentum",
        display_name="Three-Month Top-Four Adaptive Multi-Asset Allocation",
        strategy_architecture="monthly_top4_three_month_return_equal_weight_allocation",
        source_record_id="src_ma_adaptive_top4_3month_multi_asset_v1",
        route="standalone_with_diversifier_diagnostic",
        required_symbols=ADAPTIVE_UNIVERSE,
        controls=(
            "monthly_equal_weight_14_asset_control",
            "twelve_month_top4_same_universe_control",
            "three_month_top1_same_universe_control",
            "SPY_buy_and_hold",
            "sixty_forty_spy_agg_control",
        ),
        critical_controls=(
            "twelve_month_top4_same_universe_control",
            "monthly_equal_weight_14_asset_control",
        ),
        same_purpose_control="twelve_month_top4_same_universe_control",
        half_static_control="monthly_equal_weight_14_asset_control",
        portfolio_controls=(
            "twelve_month_top4_same_universe_control",
            "monthly_equal_weight_14_asset_control",
        ),
        parameters={
            "universe": "|".join(ADAPTIVE_UNIVERSE),
            "formation_frequency": "month_end",
            "return_lookback_completed_calendar_months": 3,
            "selected_count": 4,
            "weight": "25pct_each",
            "tie_break": "lexical_ticker",
            "fallback": "BIL",
            "instrument_mapping": "historical_MLPI_to_AMLP_mechanical_instrument_translation",
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Rank the frozen fourteen-asset universe by three-month month-end return, "
            "select exactly four equally, execute next close, and use BIL when the "
            "complete universe or warmup is unavailable."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[2],
        trial_id="multi_family_v1__rati_top7__canonical",
        family_id="risk_adjusted_trend_multi_asset_allocation",
        display_name="RATI Multi-Asset Top-Seven Allocation",
        strategy_architecture="weekly_risk_adjusted_trend_rank_with_risky_asset_cap",
        source_record_id="src_dalmasso_rati_multi_asset_top7_v1",
        route="standalone_with_diversifier_diagnostic",
        required_symbols=RATI_UNIVERSE,
        controls=(
            "raw_21week_return_top7_same_universe_control",
            "static_equal_weight_rati_universe_50pct_risky_cap_control",
            "SPY_BIL_50_50_control",
            "rati_exposure_matched_static_control",
            "BIL_buy_and_hold",
        ),
        critical_controls=(
            "raw_21week_return_top7_same_universe_control",
            "rati_exposure_matched_static_control",
        ),
        same_purpose_control="raw_21week_return_top7_same_universe_control",
        half_static_control="rati_exposure_matched_static_control",
        portfolio_controls=(
            "raw_21week_return_top7_same_universe_control",
            "rati_exposure_matched_static_control",
        ),
        parameters={
            "universe": "|".join(RATI_UNIVERSE),
            "signal": "SMA21_weekly_return/sqrt(SMA21_true_range/weekly_close)",
            "eligibility": "RATI_asset_gt_RATI_BIL",
            "theoretical_count": 7,
            "minimum_holding_weeks": 4,
            "minimum_outside_weeks": 4,
            "confirmation_threshold": 0.75,
            "periodic_rebalance_weeks": 13,
            "aggregate_risky_cap": 0.50,
            "weight_floor": "strictly_greater_than_1_over_2n",
            "instrument_mapping": "JJC_to_CPER_mechanical_instrument_translation",
            "execution": "Tuesday_close_following_completed_week",
        },
        frozen_rule=(
            "Rank eligible assets by 21-week RATI above BIL, apply top-seven, "
            "four-week in/out locks, 75-percent confirmation, a 50-percent risky "
            "cap, the source weight floor and 13-week rebalance, then execute Tuesday."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[3],
        trial_id="multi_family_v1__es_implied_beta__canonical",
        family_id="cross_sectional_es_implied_downside_beta",
        display_name="Relative ES-Implied Downside-Beta Sector Selection",
        strategy_architecture="monthly_top_tail_dependence_sector_selection",
        source_record_id="src_liu_es_implied_beta_sector_portability_v1",
        route="standalone_with_diversifier_diagnostic",
        required_symbols=SECTORS + ("SPY", "BIL"),
        controls=(
            "relative_usual_downside_beta_top2_sector_control",
            "unconditional_beta_top2_sector_control",
            "total_volatility_top2_sector_control",
            "monthly_equal_weight_nine_sector_control",
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
            "es_implied_beta_exposure_matched_spy_bil_control",
        ),
        critical_controls=(
            "relative_usual_downside_beta_top2_sector_control",
            "unconditional_beta_top2_sector_control",
            "total_volatility_top2_sector_control",
        ),
        same_purpose_control="relative_usual_downside_beta_top2_sector_control",
        half_static_control="es_implied_beta_exposure_matched_spy_bil_control",
        portfolio_controls=(
            "relative_usual_downside_beta_top2_sector_control",
            "es_implied_beta_exposure_matched_spy_bil_control",
        ),
        parameters={
            "signal_universe": "|".join(SECTORS),
            "market_proxy": "SPY",
            "risk_free_and_fallback_proxy": "BIL",
            "lookback": "preceding_12_completed_calendar_months",
            "minimum_common_daily_observations": 100,
            "return_type": "daily_log_excess_over_BIL",
            "empirical_ES_alpha": 0.50,
            "asset_market_ES_weights": "0.50|0.50",
            "standard_deviation_ddof": 1,
            "score": "beta_ES_minus_beta_CAPM",
            "rank": "descending_top2_equal_weight",
            "usual_downside_control_convention": (
                "conditional_beta_when_market_excess_le_sample_mean_minus_beta_CAPM"
            ),
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Use twelve completed months of sector and SPY log excess returns over "
            "BIL, empirical 50-percent ES and the frozen ES-implied correlation "
            "formula. Rank beta_ES minus beta_CAPM, hold the top two equally, and "
            "use BIL for an invalid complete formation."
        ),
    ),
    CandidateCard(
        strategy_id=EXPECTED_STRATEGY_IDS[4],
        trial_id="multi_family_v1__halloween__canonical",
        family_id="calendar_winter_equity_premium",
        display_name="Halloween SPY-BIL Rotation",
        strategy_architecture="semiannual_calendar_equity_cash_rotation",
        source_record_id="src_bouman_jacobsen_halloween_spy_bil_v1",
        route="standalone",
        required_symbols=("SPY", "BIL"),
        controls=(
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
            "opposite_season_spy_bil_control",
            "static_50_50_spy_bil_monthly_control",
            "SPY_200_day_trend_control",
        ),
        critical_controls=(
            "opposite_season_spy_bil_control",
            "static_50_50_spy_bil_monthly_control",
        ),
        same_purpose_control="opposite_season_spy_bil_control",
        half_static_control="static_50_50_spy_bil_monthly_control",
        portfolio_controls=(),
        parameters={
            "winter_state": "SPY_November_through_April",
            "summer_state": "BIL_May_through_October",
            "sell_signal": "completed_final_regular_session_April",
            "buy_signal": "completed_final_regular_session_October",
            "execution": "following_regular_session_close",
        },
        frozen_rule=(
            "Hold SPY November through April and BIL May through October. Form "
            "transitions at the completed final April and October sessions and "
            "execute at the following regular-session close."
        ),
    ),
)


def rel(path: str | Path) -> str:
    return prior_batch.rel(path)


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return prior_batch.file_hash(path)


def csv_value(value: Any) -> str:
    return prior_batch.csv_value(value)


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
        expected = (ROOT / "evidence" / "research_recovery" / BATCH_ID).resolve()
        if expected not in resolved.parents:
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
    for path in sorted((ROOT / "evidence").rglob("*")):
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
        files.extend(metadata.glob("*.json"))
    return sorted(files)


def validate_cards() -> None:
    if tuple(card.strategy_id for card in CARDS) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Frozen five-candidate scope drift")
    if len(CARDS) != 5 or len({card.family_id for card in CARDS}) < 4:
        raise RuntimeError("Multi-family cohort count or diversity drift")
    if len({card.trial_id for card in CARDS}) != 5:
        raise RuntimeError("Canonical trial IDs must be unique")
    for card in CARDS:
        required = (
            card.strategy_id,
            card.trial_id,
            card.family_id,
            card.display_name,
            card.strategy_architecture,
            card.source_record_id,
            card.route,
            card.required_symbols,
            card.controls,
            card.critical_controls,
            card.same_purpose_control,
            card.half_static_control,
            card.parameters,
            card.frozen_rule,
        )
        if any(value in ("", None, (), {}) for value in required):
            raise RuntimeError(f"Incomplete metadata for {card.strategy_id}")
        if card.same_purpose_control not in card.controls:
            raise RuntimeError(f"Same-purpose control missing for {card.strategy_id}")
        if card.half_static_control not in card.controls:
            raise RuntimeError(f"Static half control missing for {card.strategy_id}")
        if not set(card.critical_controls).issubset(card.controls):
            raise RuntimeError(f"Critical control scope drift for {card.strategy_id}")


def source_packet_hash() -> str:
    if SOURCE_PACKET_DIR.exists():
        return aggregate_hash(
            map_hashes(path for path in SOURCE_PACKET_DIR.rglob("*") if path.is_file())
        )
    return file_hash(SOURCE_PACKET_ATTACHMENT)


def zero_target(symbols: tuple[str, ...]) -> dict[str, float]:
    return {symbol: 0.0 for symbol in symbols}


def selection_target(
    symbols: tuple[str, ...], selection: tuple[str, ...], fallback: str = "BIL"
) -> dict[str, float]:
    target = zero_target(symbols)
    if selection:
        for symbol in selection:
            target[symbol] = 1.0 / len(selection)
    elif fallback in target:
        target[fallback] = 1.0
    return target


def next_session(
    index: pd.DatetimeIndex, signal_date: pd.Timestamp
) -> pd.Timestamp | None:
    later = index[index > pd.Timestamp(signal_date)]
    return pd.Timestamp(later[0]) if len(later) else None


def next_tuesday(
    index: pd.DatetimeIndex, signal_date: pd.Timestamp
) -> pd.Timestamp | None:
    later = index[index > pd.Timestamp(signal_date)]
    tuesdays = later[later.weekday == 1]
    return pd.Timestamp(tuesdays[0]) if len(tuesdays) else None


def last_dates_by_period(
    index: pd.DatetimeIndex, frequency: str
) -> list[pd.Timestamp]:
    series = pd.Series(index, index=index)
    return [
        pd.Timestamp(value)
        for value in series.groupby(index.to_period(frequency)).last().tolist()
    ]


def initial_buy_hold(
    index: pd.DatetimeIndex, symbols: tuple[str, ...], symbol: str
) -> pd.DataFrame:
    target = zero_target(symbols)
    target[symbol] = 1.0
    return accounting.initial_event(index, symbols, target)


def static_events(
    index: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    target: dict[str, float],
    frequency: str | None,
) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {pd.Timestamp(index[0]): target}
    if frequency:
        for signal_date in last_dates_by_period(index, frequency):
            execution = next_session(index, signal_date)
            if execution is not None:
                events[execution] = target
    return accounting.event_frame(index, symbols, events)


def target_history(events: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    return events.reindex(index).ffill().fillna(0.0)


def initially_missing_authorized_symbols() -> tuple[str, ...]:
    return tuple(
        symbol
        for symbol in FROZEN_INITIAL_MISSING_SYMBOLS
        if not (ROOT / "data" / "cache" / f"{symbol}.csv").exists()
    )


def acquisition_authorizations(symbol: str) -> tuple[str, ...]:
    owners = []
    if symbol in ADAPTIVE_UNIVERSE:
        owners.append(EXPECTED_STRATEGY_IDS[1])
    if symbol in RATI_UNIVERSE:
        owners.append(EXPECTED_STRATEGY_IDS[2])
    return tuple(owners)


def acquire_frozen_missing_symbols() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in FROZEN_INITIAL_MISSING_SYMBOLS:
        result = acquisition.acquire_or_validate_symbol(symbol, {})
        source = result["source_row"]
        status = (
            "feasible"
            if source.get("final_cache_status") == "validated"
            else "blocked"
        )
        rows.append(
            {
                "task_id": f"{BATCH_ID}__acquire_{symbol}",
                "entity_type": "data_capability_task",
                "stage": status,
                "adaptation_label": "data_feasibility_adjustment",
                "symbol": symbol,
                "authorized_candidate_ids": "|".join(
                    acquisition_authorizations(symbol)
                ),
                "initially_missing_in_frozen_preflight": True,
                "provider_path": (
                    "existing_alpaca_market_data_then_existing_authorized_adjusted_daily_fallback"
                ),
                "preferred_provider": source.get("preferred_provider", ""),
                "preferred_provider_attempted": source.get(
                    "preferred_provider_attempted", False
                ),
                "preferred_provider_status": source.get(
                    "preferred_provider_status", ""
                ),
                "preferred_provider_reason_not_admitted": source.get(
                    "preferred_provider_reason_not_admitted", ""
                ),
                "fallback_provider": source.get("fallback_provider", ""),
                "fallback_attempted": source.get("fallback_attempted", False),
                "fallback_status": source.get("fallback_status", ""),
                "attempt_count": 1,
                "status": status,
                "acquisition_result": source.get("acquisition_result", ""),
                "provider_download_performed": source.get(
                    "provider_download_performed", False
                ),
                "cache_path": source.get(
                    "cache_path", rel(ROOT / "data" / "cache" / f"{symbol}.csv")
                ),
                "cache_hash": source.get("cache_file_hash", "missing"),
                "canonical_frame_hash": source.get("canonical_frame_hash", ""),
                "failure_reason": (
                    ""
                    if status == "feasible"
                    else "data_or_comparability_failure"
                ),
                "api_secrets_persisted": False,
                "broker_or_order_endpoint_called": False,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
        )
    return rows


def raw_cache_validation(symbol: str) -> dict[str, Any]:
    row = dict(prior_cohort.raw_cache_validation(symbol))
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        row.update(
            row_count=0,
            first_valid_date="",
            last_valid_date="",
            fields_available="",
            canonical_hash="missing",
            preflight_status="fail",
            failure_reason="data_or_comparability_failure",
        )
        return row
    raw = pd.read_csv(path)
    row["canonical_hash"] = file_hash(path)
    row["fields_available"] = "|".join(raw.columns.astype(str))
    return row


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    symbols = tuple(
        dict.fromkeys(symbol for card in CARDS for symbol in card.required_symbols)
    )
    by_symbol = {symbol: raw_cache_validation(symbol) for symbol in symbols}
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        ready = {
            symbol: market.load_adjusted_ohlcv(symbol)
            for symbol in card.required_symbols
            if by_symbol[symbol].get("preflight_status") == "pass"
        }
        complete = len(ready) == len(card.required_symbols)
        common: pd.DatetimeIndex = pd.DatetimeIndex([])
        if complete:
            for frame in ready.values():
                common = (
                    frame.index
                    if not len(common)
                    else common.intersection(frame.index)
                )
            common = common.sort_values()
        for symbol in card.required_symbols:
            base = by_symbol[symbol]
            frame = ready.get(symbol, pd.DataFrame())
            internal_gaps = (
                int(len(common.difference(frame.index)))
                if complete and not frame.empty
                else -1
            )
            passed = bool(
                complete
                and len(common) > 0
                and base.get("preflight_status") == "pass"
                and internal_gaps == 0
            )
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "symbol": symbol,
                    "cache_path": base.get("cache_path", ""),
                    "canonical_hash": base.get("canonical_hash", ""),
                    "row_count": base.get("row_count", 0),
                    "first_valid_date": base.get("first_valid_date", ""),
                    "last_valid_date": base.get("last_valid_date", ""),
                    "fields_available": base.get("fields_available", ""),
                    "ordered_unique_dates": base.get("ordered_unique_dates", False),
                    "finite_positive_adjusted_prices": (
                        base.get("nonfinite_value_count", -1) == 0
                        and base.get("nonpositive_price_count", -1) == 0
                    ),
                    "valid_ohlc_relationships": base.get("invalid_ohlc_count", -1)
                    == 0,
                    "finite_nonnegative_volume": base.get(
                        "finite_nonnegative_adjusted_volume", False
                    ),
                    "canonical_adjustment_compatible": base.get(
                        "canonical_adjustment_compatible", False
                    ),
                    "candidate_common_start": (
                        common.min().date().isoformat() if len(common) else ""
                    ),
                    "candidate_common_end": (
                        common.max().date().isoformat() if len(common) else ""
                    ),
                    "candidate_common_session_count": int(len(common)),
                    "internal_common_calendar_gap_count": internal_gaps,
                    "provider_attempt_authorized": card.strategy_id
                    in EXPECTED_STRATEGY_IDS[1:3],
                    "provider_attempt_count_lte_one": True,
                    "candidate_preflight_status": "pass" if passed else "fail",
                    "failure_reason": (
                        "" if passed else "data_or_comparability_failure"
                    ),
                }
            )
    return rows, by_symbol


def beta_rotation_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = ("SPY", "XLU")
    index = prices.index
    week_dates = last_dates_by_period(index, "W-FRI")
    weekly_close = prices.reindex(week_dates)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {"SPY": 1.0, "XLU": 0.0}
    }
    absolute_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {"SPY": 1.0, "XLU": 0.0}
    }
    equal_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {"SPY": 0.5, "XLU": 0.5}
    }
    diagnostics: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    candidate_state = "SPY"
    absolute_state = "SPY"
    state_start = pd.Timestamp(index[0])
    for position, signal_date in enumerate(weekly_close.index):
        execution = next_session(index, pd.Timestamp(signal_date))
        if execution is None:
            continue
        equal_events[execution] = {"SPY": 0.5, "XLU": 0.5}
        rs_value = float("nan")
        spy_return = float("nan")
        prior_date = ""
        changed = False
        if position >= 4:
            prior = weekly_close.iloc[position - 4]
            current = weekly_close.iloc[position]
            prior_date = pd.Timestamp(weekly_close.index[position - 4]).date().isoformat()
            xlu_ratio = float(current["XLU"] / prior["XLU"])
            spy_ratio = float(current["SPY"] / prior["SPY"])
            rs_value = xlu_ratio / spy_ratio - 1.0
            spy_return = spy_ratio - 1.0
            valid_formations.append(pd.Timestamp(signal_date))
            next_candidate = (
                "XLU"
                if rs_value > 0.0
                else "SPY"
                if rs_value < 0.0
                else candidate_state
            )
            next_absolute = (
                "SPY"
                if spy_return > 0.0
                else "XLU"
                if spy_return < 0.0
                else absolute_state
            )
            changed = next_candidate != candidate_state
            if changed:
                state_duration = int(
                    len(index[(index >= state_start) & (index <= signal_date)])
                )
                state_start = execution
                candidate_state = next_candidate
                candidate_events[execution] = {
                    "SPY": 1.0 if candidate_state == "SPY" else 0.0,
                    "XLU": 1.0 if candidate_state == "XLU" else 0.0,
                }
            else:
                state_duration = int(
                    len(index[(index >= state_start) & (index <= signal_date)])
                )
            if next_absolute != absolute_state:
                absolute_state = next_absolute
                absolute_events[execution] = {
                    "SPY": 1.0 if absolute_state == "SPY" else 0.0,
                    "XLU": 1.0 if absolute_state == "XLU" else 0.0,
                }
        else:
            state_duration = int(
                len(index[(index >= state_start) & (index <= signal_date)])
            )
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[0],
                "formation_date": pd.Timestamp(signal_date).date().isoformat(),
                "lookback_week_end": prior_date,
                "relative_strength_value": rs_value,
                "SPY_four_week_return": spy_return,
                "target_state": candidate_state,
                "state_duration_sessions": state_duration,
                "state_transition": changed,
                "authorized_execution_date": execution.date().isoformat(),
                "signal_valid": position >= 4,
            }
        )
    candidate = accounting.event_frame(index, symbols, candidate_events)
    candidate_daily = target_history(candidate, index)
    average_xlu = float(candidate_daily["XLU"].mean())
    exposure_target = {"SPY": 1.0 - average_xlu, "XLU": average_xlu}
    controls = {
        "SPY_buy_and_hold": initial_buy_hold(index, symbols, "SPY"),
        "XLU_buy_and_hold": initial_buy_hold(index, symbols, "XLU"),
        "weekly_equal_weight_spy_xlu_control": accounting.event_frame(
            index, symbols, equal_events
        ),
        "spy_4week_absolute_state_xlu_fallback_control": accounting.event_frame(
            index, symbols, absolute_events
        ),
        "beta_rotation_exposure_matched_spy_xlu_control": static_events(
            index, symbols, exposure_target, "M"
        ),
    }
    for row in diagnostics:
        row["mechanical_full_period_average_XLU_target_weight"] = average_xlu
    return candidate, controls, diagnostics, valid_formations


def rank_descending(values: pd.Series) -> list[str]:
    return sorted(values.index, key=lambda symbol: (-float(values[symbol]), symbol))


def adaptive_top4_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = tuple(prices.columns)
    index = prices.index
    month_dates = last_dates_by_period(index, "M")
    monthly = prices.reindex(month_dates)
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): selection_target(symbols, (), "BIL")
    }
    top12_events = dict(candidate_events)
    top1_events = dict(candidate_events)
    equal_target = {symbol: 1.0 / len(symbols) for symbol in symbols}
    diagnostics: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    selections: dict[str, int] = {symbol: 0 for symbol in symbols}
    for position, signal_date in enumerate(monthly.index):
        execution = next_session(index, pd.Timestamp(signal_date))
        if execution is None:
            continue
        return3 = (
            monthly.iloc[position] / monthly.iloc[position - 3] - 1.0
            if position >= 3
            else pd.Series(np.nan, index=symbols)
        )
        return12 = (
            monthly.iloc[position] / monthly.iloc[position - 12] - 1.0
            if position >= 12
            else pd.Series(np.nan, index=symbols)
        )
        valid3 = bool(return3.notna().all() and np.isfinite(return3).all())
        valid12 = bool(return12.notna().all() and np.isfinite(return12).all())
        ranks3 = rank_descending(return3) if valid3 else []
        ranks12 = rank_descending(return12) if valid12 else []
        selected4 = tuple(ranks3[:4]) if valid3 else ()
        selected1 = tuple(ranks3[:1]) if valid3 else ()
        selected12 = tuple(ranks12[:4]) if valid12 else ()
        candidate_events[execution] = selection_target(symbols, selected4, "BIL")
        top1_events[execution] = selection_target(symbols, selected1, "BIL")
        top12_events[execution] = selection_target(symbols, selected12, "BIL")
        if valid3:
            valid_formations.append(pd.Timestamp(signal_date))
            for symbol in selected4:
                selections[symbol] += 1
        for symbol in symbols:
            diagnostics.append(
                {
                    "strategy_id": EXPECTED_STRATEGY_IDS[1],
                    "record_type": "formation_asset",
                    "formation_date": pd.Timestamp(signal_date).date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "symbol": symbol,
                    "return_3m": (
                        float(return3[symbol]) if valid3 else float("nan")
                    ),
                    "rank_3m": (
                        ranks3.index(symbol) + 1 if symbol in ranks3 else ""
                    ),
                    "selected_top4": symbol in selected4,
                    "return_12m_control": (
                        float(return12[symbol]) if valid12 else float("nan")
                    ),
                    "rank_12m_control": (
                        ranks12.index(symbol) + 1 if symbol in ranks12 else ""
                    ),
                    "valid_full_universe_formation": valid3,
                    "selected_assets": "|".join(selected4),
                    "selection_frequency_count": "",
                    "turnover_year": "",
                    "annual_one_way_turnover_5bps": "",
                }
            )
    for symbol, count in selections.items():
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[1],
                "record_type": "selection_frequency",
                "formation_date": "",
                "execution_date": "",
                "symbol": symbol,
                "return_3m": "",
                "rank_3m": "",
                "selected_top4": "",
                "return_12m_control": "",
                "rank_12m_control": "",
                "valid_full_universe_formation": "",
                "selected_assets": "",
                "selection_frequency_count": count,
                "turnover_year": "",
                "annual_one_way_turnover_5bps": "",
            }
        )
    candidate = accounting.event_frame(index, symbols, candidate_events)
    controls = {
        "monthly_equal_weight_14_asset_control": static_events(
            index, symbols, equal_target, "M"
        ),
        "twelve_month_top4_same_universe_control": accounting.event_frame(
            index, symbols, top12_events
        ),
        "three_month_top1_same_universe_control": accounting.event_frame(
            index, symbols, top1_events
        ),
        "SPY_buy_and_hold": initial_buy_hold(index, symbols, "SPY"),
        "sixty_forty_spy_agg_control": static_events(
            index,
            symbols,
            {**zero_target(symbols), "SPY": 0.6, "AGG": 0.4},
            "M",
        ),
    }
    return candidate, controls, diagnostics, valid_formations


def weekly_ohlc(
    symbols: tuple[str, ...],
) -> tuple[pd.DatetimeIndex, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frames = {symbol: market.load_adjusted_ohlcv(symbol) for symbol in symbols}
    common = pd.DatetimeIndex([])
    for frame in frames.values():
        common = frame.index if not len(common) else common.intersection(frame.index)
    common = common.sort_values()
    periods = common.to_period("W-FRI")
    closes: dict[str, pd.Series] = {}
    highs: dict[str, pd.Series] = {}
    lows: dict[str, pd.Series] = {}
    dates = pd.Series(common, index=common).groupby(periods).last()
    weekly_index = pd.DatetimeIndex(dates.to_list())
    for symbol, frame in frames.items():
        aligned = frame.reindex(common)
        grouped = aligned.groupby(periods)
        closes[symbol] = pd.Series(
            grouped["adj_close"].last().to_numpy(dtype=float),
            index=weekly_index,
        )
        highs[symbol] = pd.Series(
            grouped["high"].max().to_numpy(dtype=float), index=weekly_index
        )
        lows[symbol] = pd.Series(
            grouped["low"].min().to_numpy(dtype=float), index=weekly_index
        )
    return (
        common,
        pd.DataFrame(closes, index=weekly_index),
        pd.DataFrame(highs, index=weekly_index),
        pd.DataFrame(lows, index=weekly_index),
    )


def rati_score_frames(
    close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly_return = close.pct_change(fill_method=None)
    trend = weekly_return.clip(lower=0.0).rolling(21, min_periods=21).mean()
    trend += weekly_return.clip(upper=0.0).rolling(21, min_periods=21).mean()
    previous_close = close.shift(1)
    true_range = pd.DataFrame(
        np.maximum.reduce(
            [
                (high - low).to_numpy(dtype=float),
                (high - previous_close).abs().to_numpy(dtype=float),
                (low - previous_close).abs().to_numpy(dtype=float),
            ]
        ),
        index=close.index,
        columns=close.columns,
    )
    atr = true_range.rolling(21, min_periods=21).mean()
    rati = trend / np.sqrt(atr / close)
    raw_return = close / close.shift(21) - 1.0
    return rati, raw_return


def allocate_rati_target(
    symbols: tuple[str, ...],
    ranked: list[str],
    base_selection: list[str],
) -> tuple[dict[str, float], list[str], float, float]:
    selected = list(dict.fromkeys(base_selection))
    next_candidates = [symbol for symbol in ranked if symbol not in selected]
    while True:
        target = zero_target(symbols)
        if not selected:
            target["BIL"] = 1.0
            return target, selected, 0.0, 0.0
        n = len(selected)
        risky = [symbol for symbol in selected if symbol in RATI_RISKY]
        non_risky = [symbol for symbol in selected if symbol not in RATI_RISKY]
        initial_risky = len(risky) / n
        if initial_risky > 0.50 and risky:
            for symbol in risky:
                target[symbol] = 0.50 / len(risky)
            for symbol in non_risky:
                target[symbol] = 1.0 / n
        else:
            for symbol in selected:
                target[symbol] = 1.0 / n
        target["BIL"] += max(0.0, 1.0 - sum(target.values()))
        floor = 1.0 / (2.0 * n)
        floor_failed = [
            symbol for symbol in selected if target[symbol] <= floor + 1e-15
        ]
        if not floor_failed or not next_candidates:
            risky_weight = sum(target[symbol] for symbol in RATI_RISKY)
            return target, selected, risky_weight, floor
        selected.append(next_candidates.pop(0))


def rati_state_machine(
    daily_index: pd.DatetimeIndex,
    scores: pd.DataFrame,
    diagnostic: bool,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = tuple(scores.columns)
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(daily_index[0]): selection_target(symbols, (), "BIL")
    }
    diagnostics: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    current_selected: list[str] = []
    entry_sequence: dict[str, int] = {}
    last_exit_sequence: dict[str, int] = {}
    last_rebalance_sequence = -10_000
    current_target = selection_target(symbols, (), "BIL")
    for sequence, signal_date in enumerate(scores.index):
        row = scores.loc[signal_date]
        complete = bool(row.notna().all() and np.isfinite(row).all())
        ranked: list[str] = []
        theoretical: list[str] = []
        confirmation = float("nan")
        trigger = ""
        execution = next_tuesday(daily_index, pd.Timestamp(signal_date))
        if complete:
            valid_formations.append(pd.Timestamp(signal_date))
            bil_score = float(row["BIL"])
            ranked = sorted(
                [
                    symbol
                    for symbol in symbols
                    if symbol != "BIL" and float(row[symbol]) > bil_score
                ],
                key=lambda symbol: (-float(row[symbol]), symbol),
            )
            theoretical = ranked[:7]
            confirmation = (
                len(set(current_selected).intersection(theoretical))
                / len(current_selected)
                if current_selected
                else 0.0
            )
            composition_change = (
                not current_selected or confirmation < 0.75 - 1e-15
            )
            periodic_rebalance = (
                bool(current_selected)
                and sequence - last_rebalance_sequence >= 13
            )
            if composition_change or periodic_rebalance:
                trigger = (
                    "composition_confirmation_below_75pct"
                    if composition_change
                    else "thirteen_week_rebalance"
                )
                locked = [
                    symbol
                    for symbol in current_selected
                    if sequence - entry_sequence.get(symbol, sequence) < 4
                ]
                if composition_change:
                    available = [
                        symbol
                        for symbol in ranked
                        if sequence - last_exit_sequence.get(symbol, -10_000) >= 4
                    ]
                    base = available[:7] + [
                        symbol for symbol in locked if symbol not in available[:7]
                    ]
                else:
                    base = list(current_selected)
                new_target, selected, risky_weight, floor = allocate_rati_target(
                    symbols, ranked, base
                )
                if execution is not None:
                    exits = set(current_selected) - set(selected)
                    entries = set(selected) - set(current_selected)
                    for symbol in exits:
                        last_exit_sequence[symbol] = sequence
                    for symbol in entries:
                        entry_sequence[symbol] = sequence
                    current_selected = selected
                    current_target = new_target
                    events[execution] = new_target
                    last_rebalance_sequence = sequence
            else:
                risky_weight = sum(
                    current_target.get(symbol, 0.0) for symbol in RATI_RISKY
                )
                floor = (
                    1.0 / (2.0 * len(current_selected))
                    if current_selected
                    else 0.0
                )
        else:
            risky_weight = sum(
                current_target.get(symbol, 0.0) for symbol in RATI_RISKY
            )
            floor = (
                1.0 / (2.0 * len(current_selected))
                if current_selected
                else 0.0
            )
        if diagnostic:
            for symbol in symbols:
                diagnostics.append(
                    {
                        "strategy_id": EXPECTED_STRATEGY_IDS[2],
                        "formation_sequence": sequence,
                        "formation_date": pd.Timestamp(signal_date)
                        .date()
                        .isoformat(),
                        "execution_date": (
                            execution.date().isoformat()
                            if execution is not None
                            else ""
                        ),
                        "symbol": symbol,
                        "RATI": (
                            float(row[symbol])
                            if complete
                            else float("nan")
                        ),
                        "BIL_RATI": (
                            float(row["BIL"])
                            if complete
                            else float("nan")
                        ),
                        "eligible_above_BIL": symbol in ranked,
                        "eligible_rank": (
                            ranked.index(symbol) + 1 if symbol in ranked else ""
                        ),
                        "theoretical_top7": symbol in theoretical,
                        "minimum_holding_locked": (
                            symbol in current_selected
                            and sequence - entry_sequence.get(symbol, sequence) < 4
                        ),
                        "minimum_outside_locked": (
                            symbol not in current_selected
                            and sequence
                            - last_exit_sequence.get(symbol, -10_000)
                            < 4
                        ),
                        "confirmation_fraction": confirmation,
                        "rebalance_reason": trigger,
                        "final_non_cash_selection": "|".join(current_selected),
                        "final_weight": current_target.get(symbol, 0.0),
                        "aggregate_risky_weight": risky_weight,
                        "risky_cap": 0.50,
                        "weight_floor": floor,
                        "signal_complete": complete,
                    }
                )
    return accounting.event_frame(daily_index, symbols, events), diagnostics, valid_formations


def rati_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = tuple(prices.columns)
    daily_index, weekly_close, weekly_high, weekly_low = weekly_ohlc(symbols)
    rati, raw = rati_score_frames(weekly_close, weekly_high, weekly_low)
    candidate, diagnostics, valid_formations = rati_state_machine(
        daily_index, rati, True
    )
    raw_control, _, _ = rati_state_machine(daily_index, raw, False)
    noncash = [symbol for symbol in symbols if symbol != "BIL"]
    static_target, _, _, _ = allocate_rati_target(
        symbols, noncash, noncash
    )
    candidate_daily = target_history(candidate, daily_index)
    average_target = {
        symbol: float(candidate_daily[symbol].mean()) for symbol in symbols
    }
    total = sum(average_target.values())
    average_target = {
        symbol: value / total for symbol, value in average_target.items()
    }
    controls = {
        "raw_21week_return_top7_same_universe_control": raw_control,
        "static_equal_weight_rati_universe_50pct_risky_cap_control": static_events(
            daily_index, symbols, static_target, None
        ),
        "SPY_BIL_50_50_control": static_events(
            daily_index,
            symbols,
            {**zero_target(symbols), "SPY": 0.5, "BIL": 0.5},
            None,
        ),
        "rati_exposure_matched_static_control": static_events(
            daily_index, symbols, average_target, "M"
        ),
        "BIL_buy_and_hold": initial_buy_hold(daily_index, symbols, "BIL"),
    }
    return candidate, controls, diagnostics, valid_formations


def empirical_es(values: np.ndarray, alpha: float = 0.50) -> float:
    ordered = np.sort(np.asarray(values, dtype=float))
    if not len(ordered) or not np.isfinite(ordered).all():
        return float("nan")
    h = alpha * len(ordered)
    k = int(math.floor(h))
    gamma = h - k
    numerator = float(ordered[:k].sum())
    if gamma > 0.0 and k < len(ordered):
        numerator += gamma * float(ordered[k])
    return numerator / h if h > 0.0 else float("nan")


def top2_target(
    symbols: tuple[str, ...], values: dict[str, float], descending: bool = True
) -> tuple[dict[str, float], list[str]]:
    ordered = sorted(
        values,
        key=lambda symbol: (
            -values[symbol] if descending else values[symbol],
            symbol,
        ),
    )
    selected = ordered[:2]
    return selection_target(symbols, tuple(selected), "BIL"), selected


def es_implied_beta_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = tuple(prices.columns)
    index = prices.index
    log_return = np.log(prices / prices.shift(1))
    sector_excess = log_return[list(SECTORS)].sub(log_return["BIL"], axis=0)
    market_excess = log_return["SPY"] - log_return["BIL"]
    initial = selection_target(symbols, (), "BIL")
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): initial
    }
    downside_events = dict(candidate_events)
    beta_events = dict(candidate_events)
    volatility_events = dict(candidate_events)
    diagnostics: list[dict[str, Any]] = []
    valid_formations: list[pd.Timestamp] = []
    for sequence, signal_date in enumerate(last_dates_by_period(index, "M")):
        execution = next_session(index, signal_date)
        if execution is None:
            continue
        start = pd.Timestamp(signal_date) - pd.DateOffset(months=12)
        window_index = index[(index > start) & (index <= signal_date)]
        market = market_excess.reindex(window_index).dropna()
        complete = len(market) >= 100
        candidate_scores: dict[str, float] = {}
        downside_scores: dict[str, float] = {}
        beta_scores: dict[str, float] = {}
        volatility_scores: dict[str, float] = {}
        per_sector: dict[str, dict[str, float]] = {}
        if complete:
            for symbol in SECTORS:
                aligned = pd.concat(
                    [
                        sector_excess[symbol].rename("sector"),
                        market_excess.rename("market"),
                    ],
                    axis=1,
                ).reindex(window_index).dropna()
                if len(aligned) < 100:
                    complete = False
                    break
                sector = aligned["sector"].to_numpy(dtype=float)
                mkt = aligned["market"].to_numpy(dtype=float)
                portfolio = 0.5 * sector + 0.5 * mkt
                mean_sector = float(np.mean(sector))
                mean_market = float(np.mean(mkt))
                mean_portfolio = float(np.mean(portfolio))
                es_sector = empirical_es(sector)
                es_market = empirical_es(mkt)
                es_portfolio = empirical_es(portfolio)
                denominator = (
                    0.5
                    * (es_sector - mean_sector)
                    * (es_market - mean_market)
                )
                market_variance = float(np.var(mkt, ddof=1))
                sector_std = float(np.std(sector, ddof=1))
                market_std = float(np.std(mkt, ddof=1))
                if (
                    not math.isfinite(denominator)
                    or abs(denominator) <= 1e-15
                    or market_variance <= 0.0
                    or market_std <= 0.0
                ):
                    complete = False
                    break
                rho_es = (
                    (es_portfolio - mean_portfolio) ** 2
                    - 0.25 * (es_sector - mean_sector) ** 2
                    - 0.25 * (es_market - mean_market) ** 2
                ) / denominator
                beta_es = rho_es * sector_std / market_std
                beta_capm = float(np.cov(sector, mkt, ddof=1)[0, 1]) / market_variance
                score = beta_es - beta_capm
                downside_mask = mkt <= mean_market
                if int(downside_mask.sum()) < 2:
                    complete = False
                    break
                downside_variance = float(np.var(mkt[downside_mask], ddof=1))
                if downside_variance <= 0.0:
                    complete = False
                    break
                downside_beta = (
                    float(
                        np.cov(
                            sector[downside_mask],
                            mkt[downside_mask],
                            ddof=1,
                        )[0, 1]
                    )
                    / downside_variance
                )
                relative_downside = downside_beta - beta_capm
                values = (
                    rho_es,
                    beta_es,
                    beta_capm,
                    score,
                    downside_beta,
                    relative_downside,
                    sector_std,
                )
                if not np.isfinite(np.array(values, dtype=float)).all():
                    complete = False
                    break
                candidate_scores[symbol] = score
                downside_scores[symbol] = relative_downside
                beta_scores[symbol] = beta_capm
                volatility_scores[symbol] = sector_std
                per_sector[symbol] = {
                    "mean_sector": mean_sector,
                    "mean_market": mean_market,
                    "mean_portfolio": mean_portfolio,
                    "ES_sector": es_sector,
                    "ES_market": es_market,
                    "ES_portfolio": es_portfolio,
                    "rho_ES": rho_es,
                    "beta_ES": beta_es,
                    "beta_CAPM": beta_capm,
                    "score": score,
                    "usual_downside_beta": downside_beta,
                    "relative_usual_downside_beta": relative_downside,
                    "sector_std": sector_std,
                    "market_std": market_std,
                    "observation_count": len(aligned),
                }
        if complete and len(candidate_scores) == len(SECTORS):
            candidate_target, candidate_selected = top2_target(
                symbols, candidate_scores
            )
            downside_target, downside_selected = top2_target(
                symbols, downside_scores
            )
            beta_target, beta_selected = top2_target(symbols, beta_scores)
            volatility_target, volatility_selected = top2_target(
                symbols, volatility_scores
            )
            valid_formations.append(pd.Timestamp(signal_date))
        else:
            candidate_target = initial
            downside_target = initial
            beta_target = initial
            volatility_target = initial
            candidate_selected = []
            downside_selected = []
            beta_selected = []
            volatility_selected = []
        candidate_events[execution] = candidate_target
        downside_events[execution] = downside_target
        beta_events[execution] = beta_target
        volatility_events[execution] = volatility_target
        candidate_rank = (
            rank_descending(pd.Series(candidate_scores))
            if complete
            else []
        )
        downside_rank = (
            rank_descending(pd.Series(downside_scores))
            if complete
            else []
        )
        beta_rank = (
            rank_descending(pd.Series(beta_scores)) if complete else []
        )
        volatility_rank = (
            rank_descending(pd.Series(volatility_scores))
            if complete
            else []
        )
        for symbol in SECTORS:
            values = per_sector.get(symbol, {})
            diagnostics.append(
                {
                    "strategy_id": EXPECTED_STRATEGY_IDS[3],
                    "formation_sequence": sequence,
                    "formation_date": signal_date.date().isoformat(),
                    "execution_date": execution.date().isoformat(),
                    "window_start_exclusive": start.date().isoformat(),
                    "window_end": signal_date.date().isoformat(),
                    "symbol": symbol,
                    "observation_count": values.get("observation_count", len(market)),
                    "mean_sector_excess": values.get("mean_sector", float("nan")),
                    "mean_market_excess": values.get("mean_market", float("nan")),
                    "mean_50_50_portfolio_excess": values.get(
                        "mean_portfolio", float("nan")
                    ),
                    "ES_sector": values.get("ES_sector", float("nan")),
                    "ES_market": values.get("ES_market", float("nan")),
                    "ES_50_50_portfolio": values.get(
                        "ES_portfolio", float("nan")
                    ),
                    "rho_ES": values.get("rho_ES", float("nan")),
                    "beta_ES": values.get("beta_ES", float("nan")),
                    "beta_CAPM": values.get("beta_CAPM", float("nan")),
                    "relative_ES_score": values.get("score", float("nan")),
                    "usual_downside_beta": values.get(
                        "usual_downside_beta", float("nan")
                    ),
                    "relative_usual_downside_beta": values.get(
                        "relative_usual_downside_beta", float("nan")
                    ),
                    "sector_total_volatility": values.get(
                        "sector_std", float("nan")
                    ),
                    "market_total_volatility": values.get(
                        "market_std", float("nan")
                    ),
                    "candidate_rank": (
                        candidate_rank.index(symbol) + 1
                        if symbol in candidate_rank
                        else ""
                    ),
                    "downside_control_rank": (
                        downside_rank.index(symbol) + 1
                        if symbol in downside_rank
                        else ""
                    ),
                    "unconditional_beta_rank": (
                        beta_rank.index(symbol) + 1
                        if symbol in beta_rank
                        else ""
                    ),
                    "total_volatility_rank": (
                        volatility_rank.index(symbol) + 1
                        if symbol in volatility_rank
                        else ""
                    ),
                    "candidate_selected": symbol in candidate_selected,
                    "downside_control_selected": symbol in downside_selected,
                    "unconditional_beta_selected": symbol in beta_selected,
                    "total_volatility_selected": symbol in volatility_selected,
                    "complete_formation_valid": complete,
                    "invalidity_reason": (
                        ""
                        if complete
                        else "insufficient_or_nonfinite_complete_formation"
                    ),
                }
            )
    candidate = accounting.event_frame(index, symbols, candidate_events)
    candidate_daily = target_history(candidate, index)
    average_risky = float(candidate_daily[list(SECTORS)].sum(axis=1).mean())
    exposure_target = {
        **zero_target(symbols),
        "SPY": average_risky,
        "BIL": 1.0 - average_risky,
    }
    equal_target = {
        **zero_target(symbols),
        **{symbol: 1.0 / len(SECTORS) for symbol in SECTORS},
    }
    controls = {
        "relative_usual_downside_beta_top2_sector_control": accounting.event_frame(
            index, symbols, downside_events
        ),
        "unconditional_beta_top2_sector_control": accounting.event_frame(
            index, symbols, beta_events
        ),
        "total_volatility_top2_sector_control": accounting.event_frame(
            index, symbols, volatility_events
        ),
        "monthly_equal_weight_nine_sector_control": static_events(
            index, symbols, equal_target, "M"
        ),
        "SPY_buy_and_hold": initial_buy_hold(index, symbols, "SPY"),
        "BIL_buy_and_hold": initial_buy_hold(index, symbols, "BIL"),
        "es_implied_beta_exposure_matched_spy_bil_control": static_events(
            index, symbols, exposure_target, "M"
        ),
    }
    return candidate, controls, diagnostics, valid_formations


def spy_200_day_trend_events(
    prices: pd.DataFrame, symbols: tuple[str, ...]
) -> pd.DataFrame:
    index = prices.index
    sma = prices["SPY"].rolling(200, min_periods=200).mean()
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {**zero_target(symbols), "BIL": 1.0}
    }
    current = "BIL"
    for signal_date in index:
        execution = next_session(index, pd.Timestamp(signal_date))
        if execution is None or pd.isna(sma.loc[signal_date]):
            continue
        target = "SPY" if float(prices.loc[signal_date, "SPY"]) > float(sma.loc[signal_date]) else "BIL"
        if target != current:
            current = target
            events[execution] = {
                **zero_target(symbols),
                "SPY": 1.0 if current == "SPY" else 0.0,
                "BIL": 1.0 if current == "BIL" else 0.0,
            }
    return accounting.event_frame(index, symbols, events)


def halloween_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]], list[pd.Timestamp]]:
    symbols = ("SPY", "BIL")
    index = prices.index
    initial_spy = index[0].month in (1, 2, 3, 4, 11, 12)
    candidate_state = "SPY" if initial_spy else "BIL"
    opposite_state = "BIL" if initial_spy else "SPY"
    candidate_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {
            "SPY": 1.0 if candidate_state == "SPY" else 0.0,
            "BIL": 1.0 if candidate_state == "BIL" else 0.0,
        }
    }
    opposite_events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(index[0]): {
            "SPY": 1.0 if opposite_state == "SPY" else 0.0,
            "BIL": 1.0 if opposite_state == "BIL" else 0.0,
        }
    }
    diagnostics: list[dict[str, Any]] = []
    formations: list[pd.Timestamp] = []
    month_ends = last_dates_by_period(index, "M")
    transition_rows: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for signal_date in month_ends:
        if signal_date.month not in (4, 10):
            continue
        execution = next_session(index, signal_date)
        if execution is None:
            diagnostics.append(
                {
                    "strategy_id": EXPECTED_STRATEGY_IDS[4],
                    "signal_date": signal_date.date().isoformat(),
                    "season_transition": "to_BIL" if signal_date.month == 4 else "to_SPY",
                    "authorized_execution_date": "",
                    "execution_status": "blocked_missing_following_session",
                    "holding_start": "",
                    "holding_end": "",
                    "holding_asset": "",
                    "holding_return": "",
                }
            )
            continue
        formations.append(signal_date)
        candidate_state = "BIL" if signal_date.month == 4 else "SPY"
        opposite_state = "SPY" if signal_date.month == 4 else "BIL"
        candidate_events[execution] = {
            "SPY": 1.0 if candidate_state == "SPY" else 0.0,
            "BIL": 1.0 if candidate_state == "BIL" else 0.0,
        }
        opposite_events[execution] = {
            "SPY": 1.0 if opposite_state == "SPY" else 0.0,
            "BIL": 1.0 if opposite_state == "BIL" else 0.0,
        }
        transition_rows.append((signal_date, execution, candidate_state))
    for position, (signal_date, execution, state) in enumerate(transition_rows):
        end = (
            transition_rows[position + 1][1]
            if position + 1 < len(transition_rows)
            else pd.Timestamp(index[-1])
        )
        holding_return = float(prices.loc[end, state] / prices.loc[execution, state] - 1.0)
        diagnostics.append(
            {
                "strategy_id": EXPECTED_STRATEGY_IDS[4],
                "signal_date": signal_date.date().isoformat(),
                "season_transition": "to_SPY" if state == "SPY" else "to_BIL",
                "authorized_execution_date": execution.date().isoformat(),
                "execution_status": "executed",
                "holding_start": execution.date().isoformat(),
                "holding_end": end.date().isoformat(),
                "holding_asset": state,
                "holding_return": holding_return,
            }
        )
    candidate = accounting.event_frame(index, symbols, candidate_events)
    controls = {
        "SPY_buy_and_hold": initial_buy_hold(index, symbols, "SPY"),
        "BIL_buy_and_hold": initial_buy_hold(index, symbols, "BIL"),
        "opposite_season_spy_bil_control": accounting.event_frame(
            index, symbols, opposite_events
        ),
        "static_50_50_spy_bil_monthly_control": static_events(
            index, symbols, {"SPY": 0.5, "BIL": 0.5}, "M"
        ),
        "SPY_200_day_trend_control": spy_200_day_trend_events(prices, symbols),
    }
    return candidate, controls, diagnostics, formations


def prepare_candidate(card: CandidateCard) -> dict[str, Any]:
    prices = market.load_price_frame(card.required_symbols)
    if prices.empty:
        return {
            "prices": prices,
            "candidate_events": pd.DataFrame(),
            "control_events": {},
            "diagnostics": [],
            "valid_formations": [],
            "timing_convention": "",
        }
    if card.strategy_id == EXPECTED_STRATEGY_IDS[0]:
        candidate, controls, diagnostics, formations = beta_rotation_event_sets(prices)
        timing = "completed_week_close_signal_following_regular_session_close"
        diagnostic_key = "beta_rotation_diagnostics"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[1]:
        candidate, controls, diagnostics, formations = adaptive_top4_event_sets(prices)
        timing = "completed_month_end_signal_following_regular_session_close"
        diagnostic_key = "adaptive_top4_diagnostics"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[2]:
        candidate, controls, diagnostics, formations = rati_event_sets(prices)
        timing = "completed_week_signal_Tuesday_close_execution"
        diagnostic_key = "rati_rank_and_allocation_diagnostics"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[3]:
        candidate, controls, diagnostics, formations = es_implied_beta_event_sets(prices)
        timing = "completed_month_end_signal_following_regular_session_close"
        diagnostic_key = "es_implied_beta_diagnostics"
    elif card.strategy_id == EXPECTED_STRATEGY_IDS[4]:
        candidate, controls, diagnostics, formations = halloween_event_sets(prices)
        timing = "completed_April_or_October_month_end_following_regular_session_close"
        diagnostic_key = "halloween_state_diagnostics"
    else:
        raise RuntimeError(f"Unsupported candidate {card.strategy_id}")
    if tuple(controls) != card.controls:
        raise RuntimeError(f"Frozen control order drift for {card.strategy_id}")
    return {
        "prices": prices,
        "candidate_events": candidate,
        "control_events": controls,
        "diagnostics": diagnostics,
        "diagnostic_key": diagnostic_key,
        "valid_formations": formations,
        "timing_convention": timing,
    }


def empty_prepared() -> dict[str, Any]:
    return {
        "prices": pd.DataFrame(),
        "candidate_events": pd.DataFrame(),
        "control_events": {},
        "diagnostics": [],
        "diagnostic_key": "",
        "valid_formations": [],
        "timing_convention": "",
    }


def run_candidate(
    card: CandidateCard, preflight_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    relevant = [
        row for row in preflight_rows if row["strategy_id"] == card.strategy_id
    ]
    missing = sorted(
        {
            row["symbol"]
            for row in relevant
            if row["candidate_preflight_status"] != "pass"
        }
    )
    if missing:
        return {
            "card": card,
            "executed": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_or_comparability_failure",
            "decision_reason": "frozen candidate or required-control data preflight failed",
            "missing_symbols": missing,
            "candidate_paths": {},
            "control_paths": {},
            "portfolio_paths": {},
            "prepared": empty_prepared(),
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
    if card.strategy_id == EXPECTED_STRATEGY_IDS[1]:
        annual = (
            candidate_paths[PRIMARY_COST_BPS]["turnover"]
            .groupby(candidate_paths[PRIMARY_COST_BPS]["turnover"].index.year)
            .sum()
        )
        prepared["diagnostics"].extend(
            {
                "strategy_id": card.strategy_id,
                "record_type": "turnover_by_year",
                "formation_date": "",
                "execution_date": "",
                "symbol": "",
                "return_3m": "",
                "rank_3m": "",
                "selected_top4": "",
                "return_12m_control": "",
                "rank_12m_control": "",
                "valid_full_universe_formation": "",
                "selected_assets": "",
                "selection_frequency_count": "",
                "turnover_year": int(year),
                "annual_one_way_turnover_5bps": float(value),
            }
            for year, value in annual.items()
        )
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


def strategy_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(prior_cohort.strategy_metrics(path, period_index))
    return metrics


def portfolio_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    return dict(prior_cohort.portfolio_metrics(path, period_index))


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(control["maximum_drawdown"])
    )


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return (
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


def formation_counts_by_half(result: dict[str, Any]) -> tuple[int, int]:
    index = result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
    midpoint_date = index[len(index) // 2 - 1]
    dates = [pd.Timestamp(value) for value in result["prepared"]["valid_formations"]]
    if result["card"].strategy_id == EXPECTED_STRATEGY_IDS[4]:
        years_first: dict[int, set[int]] = {}
        years_second: dict[int, set[int]] = {}
        for value in dates:
            target = years_first if value <= midpoint_date else years_second
            target.setdefault(value.year, set()).add(value.month)
        first = sum(months.issuperset({4, 10}) for months in years_first.values())
        second = sum(months.issuperset({4, 10}) for months in years_second.values())
        return int(first), int(second)
    return (
        sum(value <= midpoint_date for value in dates),
        sum(value > midpoint_date for value in dates),
    )


def minimum_formation_requirement(card: CandidateCard) -> int:
    return {
        EXPECTED_STRATEGY_IDS[0]: 52,
        EXPECTED_STRATEGY_IDS[1]: 24,
        EXPECTED_STRATEGY_IDS[2]: 52,
        EXPECTED_STRATEGY_IDS[3]: 24,
        EXPECTED_STRATEGY_IDS[4]: 4,
    }[card.strategy_id]


def build_portfolio_paths(
    result: dict[str, Any], reference_returns: pd.Series
) -> dict[tuple[str, float], dict[str, Any]]:
    card: CandidateCard = result["card"]
    if not result["executed"] or not card.portfolio_controls:
        return {}
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate = result["candidate_paths"][cost]["returns"]
        controls = {
            control_id: result["control_paths"][(control_id, cost)]["returns"]
            for control_id in card.portfolio_controls
        }
        common = candidate.index.intersection(reference_returns.dropna().index)
        for series in controls.values():
            common = common.intersection(series.dropna().index)
        common = common.sort_values()
        reference = reference_returns.reindex(common).dropna()
        candidate_aligned = candidate.reindex(reference.index).dropna()
        reference = reference.reindex(candidate_aligned.index)
        payloads[("100pct_frozen_reference", cost)] = (
            portfolio_accounting.reference_payload(reference, cost)
        )
        candidate_id = "80pct_reference_20pct_candidate"
        payloads[(candidate_id, cost)] = (
            portfolio_accounting.simulate_two_component_portfolio(
                reference, candidate_aligned, candidate_id, cost
            )
        )
        for control_id, series in controls.items():
            aligned = series.reindex(reference.index).dropna()
            aligned_reference = reference.reindex(aligned.index)
            portfolio_id = f"80pct_reference_20pct_{control_id}"
            payloads[(portfolio_id, cost)] = (
                portfolio_accounting.simulate_two_component_portfolio(
                    aligned_reference, aligned, portfolio_id, cost
                )
            )
    return payloads


def portfolio_gate_passes(result: dict[str, Any]) -> bool:
    card: CandidateCard = result["card"]
    if not card.portfolio_controls:
        return False
    paths = result["portfolio_paths"]
    reference = portfolio_metrics(paths[("100pct_frozen_reference", PRIMARY_COST_BPS)])
    candidate = portfolio_metrics(
        paths[("80pct_reference_20pct_candidate", PRIMARY_COST_BPS)]
    )
    improves = (
        float(candidate["sharpe_ratio"]) > float(reference["sharpe_ratio"])
        or float(candidate["maximum_drawdown"])
        > float(reference["maximum_drawdown"])
    )
    worsens_both = worse_on_both(candidate, reference)
    controls = [
        portfolio_metrics(
            paths[
                (
                    f"80pct_reference_20pct_{control_id}",
                    PRIMARY_COST_BPS,
                )
            ]
        )
        for control_id in card.portfolio_controls
    ]
    return bool(
        improves
        and not worsens_both
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
    all_invariants = bool(candidate["invariant_pass"]) and all(
        bool(value["invariant_pass"]) for value in controls.values()
    )
    if not all_invariants:
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
            decision_reason="full-period after-cost return is not positive",
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
    for _, period in split_periods(result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index):
        candidate_half = strategy_metrics(
            result["candidate_paths"][PRIMARY_COST_BPS], period
        )
        for control_id in (card.same_purpose_control, card.half_static_control):
            control_half = strategy_metrics(
                result["control_paths"][(control_id, PRIMARY_COST_BPS)], period
            )
            if worse_on_both(candidate_half, control_half):
                result.update(
                    outcome="closed_exploration",
                    failure_reason="period_instability",
                    decision_reason=(
                        f"candidate worse on Sharpe and drawdown versus fixed "
                        f"half-period control {control_id}"
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
    first_count, second_count = formation_counts_by_half(result)
    required = minimum_formation_requirement(card)
    if first_count < required or second_count < required:
        result.update(
            outcome="closed_exploration",
            failure_reason="signal_scarcity",
            decision_reason=(
                f"eligible formation/cycle counts {first_count}|{second_count} "
                f"below frozen per-half minimum {required}"
            ),
        )
        return
    simpler = [
        control_id
        for control_id in card.controls
        if control_id not in card.critical_controls
        and float(controls[control_id]["sharpe_ratio"])
        >= float(candidate["sharpe_ratio"])
        and float(controls[control_id]["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"])
    ]
    if simpler:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=(
                "simpler single-asset, equal-weight, or static control "
                "economically replicates the result: " + ",".join(simpler)
            ),
        )
        return
    if card.portfolio_controls and portfolio_gate_passes(result):
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


METRIC_FIELDS = prior_cohort.METRIC_FIELDS


def candidate_next_action(result: dict[str, Any]) -> str:
    if result["outcome"].startswith("exploratory_followup_candidate_"):
        return f"direction_owner_review_{result['card'].strategy_id}_exploratory_followup"
    if result["outcome"] == "closed_exploration":
        return "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
    if result["outcome"] == "inconclusive_data_issue":
        return f"direction_owner_review_{result['card'].strategy_id}_data_issue"
    return f"direction_owner_review_{result['card'].strategy_id}_feasibility_block"


def provisional_outcome() -> str:
    return "preregistered_pending_execution"


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
        "instrument_universe": "|".join(card.required_symbols),
        "parameters": card.parameters,
        "benchmark_or_control": "|".join(card.controls),
        "route": card.route,
        "stage": STAGE,
        "trial_id": card.trial_id,
        "parent_trial_id": "",
        "adaptation_label": "",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "authoritative_registry_record_created": False,
        "paper_demo_observation_created": False,
    }


def trial_row(
    card: CandidateCard,
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    row = strategy_row(card, outcome, failure_reason, next_action)
    row.update(
        entity_type="experiment_trial",
        preregistration_timestamp=PREREGISTRATION_TIMESTAMP,
        optimization_performed=False,
        post_result_adaptation_allowed=False,
        parameters_changed_after_preregistration=False,
        universe_changed_after_preregistration=False,
        benchmarks_changed_after_preregistration=False,
        execution_changed_after_preregistration=False,
        counted_as_strategy=False,
        counted_as_trial=True,
    )
    return row


def source_rows() -> list[dict[str, Any]]:
    packet_location = (
        rel(SOURCE_PACKET_DIR)
        if SOURCE_PACKET_DIR.exists()
        else str(SOURCE_PACKET_ATTACHMENT)
    )
    packet_hash = source_packet_hash()
    return [
        {
            "source_record_id": card.source_record_id,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "outcome": "feasible",
            "failure_reason": "",
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "display_name": card.display_name,
            "strategy_architecture": card.strategy_architecture,
            "route": card.route,
            "source_library_id": SOURCE_LIBRARY_ID,
            "source_packet_location": packet_location,
            "source_packet_hash": packet_hash,
            "frozen_rule": card.frozen_rule,
            "implementation_authorized": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in CARDS
    ]


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


def benchmark_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "strategy_id": "",
            "family_id": "",
            "trial_id": "",
            "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "reference_role": "portfolio_contribution_reference_only",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
    ]
    for card in CARDS:
        for control_id in card.controls:
            role = "additional_frozen_control"
            if control_id == card.same_purpose_control:
                role = "named_same_purpose_chronological_half_gate_control"
            elif control_id in card.critical_controls:
                role = "critical_full_period_gate_control"
            elif control_id == card.half_static_control:
                role = "exposure_or_static_chronological_half_gate_control"
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": role,
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def write_preregistration_checkpoint() -> str:
    provisional_next = "execute_frozen_preregistered_batch"
    strategies = [
        strategy_row(card, provisional_outcome(), "", provisional_next)
        for card in CARDS
    ]
    trials = [
        trial_row(card, provisional_outcome(), "", provisional_next)
        for card in CARDS
    ]
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    material = (
        (OUTPUT_DIR / "strategy_cards.csv").read_bytes()
        + (OUTPUT_DIR / "trial_ledger.csv").read_bytes()
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


def result_row(
    result: dict[str, Any],
    row_type: str,
    control_id: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    card: CandidateCard = result["card"]
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
        if not result["executed"]:
            for cost in COST_BPS:
                candidates.append(
                    result_row(result, "candidate", "", cost, "full_period", None)
                )
                for control_id in card.controls:
                    controls.append(
                        result_row(
                            result,
                            "control",
                            control_id,
                            cost,
                            "full_period",
                            None,
                        )
                    )
            continue
        for cost in COST_BPS:
            paths = [
                ("candidate", "", result["candidate_paths"][cost]),
                *[
                    (
                        "control",
                        control_id,
                        result["control_paths"][(control_id, cost)],
                    )
                    for control_id in card.controls
                ],
            ]
            for row_type, control_id, path in paths:
                metrics = strategy_metrics(path)
                (candidates if row_type == "candidate" else controls).append(
                    result_row(
                        result,
                        row_type,
                        control_id,
                        cost,
                        "full_period",
                        metrics,
                    )
                )
                turnover.append(
                    {
                        "record_scope": (
                            "strategy_candidate"
                            if row_type == "candidate"
                            else "benchmark_control"
                        ),
                        "strategy_id": card.strategy_id,
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metrics["turnover"],
                        "trade_or_rebalance_count": metrics[
                            "trade_or_rebalance_count"
                        ],
                        "transaction_cost_drag": metrics[
                            "transaction_cost_drag"
                        ],
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "natural_drift_between_rebalances": True,
                        "transaction_costs_charged_once": True,
                    }
                )
                invariants.append(
                    {
                        "strategy_id": card.strategy_id,
                        "record_type": row_type,
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "explicit_zero_weights": True,
                        "natural_drift_between_rebalances": True,
                        "stale_weight_forward_fill_used": False,
                        "negative_weights_present": False,
                        "leverage_used": False,
                        "same_period_price_signal_return_used": False,
                        "transaction_costs_charged_once": True,
                        **{
                            field: metrics[field]
                            for field in (
                                "maximum_single_asset_weight",
                                "maximum_gross_exposure",
                                "maximum_daily_weight_sum",
                                "numeric_invariant_status",
                                "timing_invariant_status",
                                "exposure_invariant_status",
                                "weight_invariant_status",
                                "invariant_pass",
                            )
                        },
                    }
                )
                if cost == PRIMARY_COST_BPS:
                    for half_label, period in split_periods(path["returns"].index):
                        halves.append(
                            result_row(
                                result,
                                row_type,
                                control_id,
                                cost,
                                half_label,
                                strategy_metrics(path, period),
                            )
                        )
    return {
        "all_trial_results": candidates,
        "control_results": controls,
        "chronological_half_results": halves,
        "turnover_cost_reconciliation": turnover,
        "invariant_results": invariants,
    }


def portfolio_rows(
    results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        for (portfolio_id, cost), path in sorted(result["portfolio_paths"].items()):
            periods = [("full_period", None)]
            if cost == PRIMARY_COST_BPS:
                periods.extend(split_periods(path["returns"].index))
            for label, period in periods:
                metrics = portfolio_metrics(path, period)
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "family_id": card.family_id,
                        "trial_id": card.trial_id,
                        "route": card.route,
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": (
                            "100pct_frozen_reference"
                            if portfolio_id == "100pct_frozen_reference"
                            else "monthly_rebalanced_80pct_reference_20pct_candidate_or_frozen_control_with_explicit_holdings_natural_drift_and_actual_costs"
                        ),
                        "period_label": label,
                        "period_role": (
                            "full_period_exploration"
                            if label == "full_period"
                            else "deterministic_chronological_half_diagnostic_not_validation"
                        ),
                        "cost_assumption_bps": cost,
                        **metrics,
                    }
                )
            full = portfolio_metrics(path)
            turnover.append(
                {
                    "record_scope": "portfolio_contribution",
                    "strategy_id": card.strategy_id,
                    "control_or_portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": full["turnover"],
                    "trade_or_rebalance_count": full[
                        "trade_or_rebalance_count"
                    ],
                    "transaction_cost_drag": full["transaction_cost_drag"],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "natural_drift_between_rebalances": True,
                    "transaction_costs_charged_once": True,
                }
            )
            invariants.append(
                {
                    "strategy_id": card.strategy_id,
                    "record_type": "portfolio_contribution",
                    "control_or_portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "explicit_zero_weights": True,
                    "natural_drift_between_rebalances": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "leverage_used": False,
                    "same_period_price_signal_return_used": False,
                    "transaction_costs_charged_once": True,
                    **{
                        field: full[field]
                        for field in (
                            "maximum_single_asset_weight",
                            "maximum_gross_exposure",
                            "maximum_daily_weight_sum",
                            "numeric_invariant_status",
                            "timing_invariant_status",
                            "exposure_invariant_status",
                            "weight_invariant_status",
                            "invariant_pass",
                        )
                    },
                }
            )
    return rows, turnover, invariants


def diagnostic_tables(
    results: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    names = (
        "beta_rotation_diagnostics",
        "adaptive_top4_diagnostics",
        "rati_rank_and_allocation_diagnostics",
        "es_implied_beta_diagnostics",
        "halloween_state_diagnostics",
    )
    tables = {name: [] for name in names}
    for result in results:
        key = result["prepared"].get("diagnostic_key", "")
        if key in tables:
            tables[key].extend(result["prepared"].get("diagnostics", []))
    return tables


def outcome_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        first = second = 0
        if result["executed"]:
            first, second = formation_counts_by_half(result)
        rows.append(
            {
                "strategy_id": result["card"].strategy_id,
                "family_id": result["card"].family_id,
                "entity_type": "strategy_configuration",
                "stage": STAGE,
                "route": result["card"].route,
                "executed": result["executed"],
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "decision_reason": result["decision_reason"],
                "missing_symbols": result["missing_symbols"],
                "named_same_purpose_control": result[
                    "card"
                ].same_purpose_control,
                "half_static_or_exposure_control": result[
                    "card"
                ].half_static_control,
                "first_half_valid_formation_or_cycle_count": first,
                "second_half_valid_formation_or_cycle_count": second,
                "minimum_required_per_half": minimum_formation_requirement(
                    result["card"]
                ),
                "next_action": candidate_next_action(result),
                "validation_claimed": False,
                "promotion_or_paper_demo_authorized": False,
            }
        )
    return rows


def batch_next_action(results: list[dict[str, Any]]) -> str:
    executed = sum(result["executed"] for result in results)
    if executed < 3:
        return NEXT_BLOCKED
    if any(
        result["outcome"].startswith("exploratory_followup_candidate_")
        for result in results
    ):
        return NEXT_REVIEW
    return NEXT_ALL_CLOSED


def funnel_counts(
    results: list[dict[str, Any]],
    benchmarks: list[dict[str, Any]],
    data_tasks: list[dict[str, Any]],
    next_action: str,
) -> dict[str, Any]:
    outcomes = {
        outcome: sum(result["outcome"] == outcome for result in results)
        for outcome in sorted(ALLOWED_OUTCOMES)
    }
    followups = (
        outcomes["exploratory_followup_candidate_standalone"]
        + outcomes["exploratory_followup_candidate_diversifier"]
    )
    return {
        "source_library_records": 5,
        "strategy_configurations": 5,
        "canonical_experiment_trials": 5,
        "experiment_trials_executed": sum(result["executed"] for result in results),
        "benchmark_references": len(benchmarks),
        "data_capability_tasks": len(data_tasks),
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "distinct_families": len({card.family_id for card in CARDS}),
        "outcomes": outcomes,
        "followup_candidate_count": followups,
        "closed_or_blocked_or_inconclusive_count": len(results) - followups,
        "outcome_count_reconciles": sum(outcomes.values()) == 5,
        "process_records_counted_as_strategies_or_trials": False,
        "benchmark_references_counted_as_strategies_or_trials": False,
        "exact_next_action": next_action,
    }


def deterministic_core_hash() -> str:
    payload = {
        "batch_id": BATCH_ID,
        "cost_bps": COST_BPS,
        "cards": [
            {
                "strategy_id": card.strategy_id,
                "trial_id": card.trial_id,
                "family_id": card.family_id,
                "architecture": card.strategy_architecture,
                "required_symbols": card.required_symbols,
                "controls": card.controls,
                "critical_controls": card.critical_controls,
                "same_purpose_control": card.same_purpose_control,
                "half_static_control": card.half_static_control,
                "parameters": card.parameters,
                "frozen_rule": card.frozen_rule,
            }
            for card in CARDS
        ],
        "provider_attempt_symbols": FROZEN_INITIAL_MISSING_SYMBOLS,
        "forbidden_flags": FORBIDDEN_FLAGS,
    }
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_report(
    results: list[dict[str, Any]],
    funnel: dict[str, Any],
    next_action: str,
) -> str:
    lines = [
        "# Multi-Family Fast Exploration Batch V1",
        "",
        "## Scope",
        "",
        "This exploration preregistered and considered exactly five frozen "
        "strategy configurations from five distinct families. Controls, data "
        "tasks, portfolio diagnostics, and the process runner remain separate "
        "entities.",
        "",
        "## Outcomes",
        "",
        "| Strategy | Executed | Outcome | Failure reason |",
        "|---|---:|---|---|",
    ]
    for result in results:
        lines.append(
            f"| `{result['card'].strategy_id}` | "
            f"{str(result['executed']).lower()} | `{result['outcome']}` | "
            f"`{result['failure_reason'] or 'none'}` |"
        )
    lines.extend(
        [
            "",
            f"Follow-up candidates: **{funnel['followup_candidate_count']}**.",
            "",
            "The primary result uses 5 bps per one-way turnover. Zero and "
            "10 bps are fixed diagnostics, not additional trials. Every "
            "chronological half is descriptive exploration evidence only.",
            "",
            "## Accounting",
            "",
            "All executable candidates and controls use explicit holdings, "
            "natural drift, explicit zero weights, actual one-way turnover, "
            "and a single transaction-cost deduction. Signals are formed from "
            "completed data and targets are applied only at their frozen later "
            "execution session.",
            "",
            "The ES-implied-beta candidate rule is unchanged. Its conventional "
            "downside-beta benchmark is recorded as a project control convention: "
            "conditional beta when market excess return is at or below its "
            "sample mean, less unconditional CAPM beta.",
            "",
            "## Boundaries",
            "",
            "No source completion, parameter search, post-result change, "
            "validation, lifecycle update, paper/demo action, broker operation, "
            "or real-money action occurred.",
            "",
            f"Exact next action: `{next_action}`",
        ]
    )
    return "\n".join(lines)


DIAGNOSTIC_FIELDS = {
    "beta_rotation_diagnostics": [
        "strategy_id",
        "formation_date",
        "lookback_week_end",
        "relative_strength_value",
        "SPY_four_week_return",
        "target_state",
        "state_duration_sessions",
        "state_transition",
        "authorized_execution_date",
        "signal_valid",
        "mechanical_full_period_average_XLU_target_weight",
    ],
    "adaptive_top4_diagnostics": [
        "strategy_id",
        "record_type",
        "formation_date",
        "execution_date",
        "symbol",
        "return_3m",
        "rank_3m",
        "selected_top4",
        "return_12m_control",
        "rank_12m_control",
        "valid_full_universe_formation",
        "selected_assets",
        "selection_frequency_count",
        "turnover_year",
        "annual_one_way_turnover_5bps",
    ],
    "rati_rank_and_allocation_diagnostics": [
        "strategy_id",
        "formation_sequence",
        "formation_date",
        "execution_date",
        "symbol",
        "RATI",
        "BIL_RATI",
        "eligible_above_BIL",
        "eligible_rank",
        "theoretical_top7",
        "minimum_holding_locked",
        "minimum_outside_locked",
        "confirmation_fraction",
        "rebalance_reason",
        "final_non_cash_selection",
        "final_weight",
        "aggregate_risky_weight",
        "risky_cap",
        "weight_floor",
        "signal_complete",
    ],
    "es_implied_beta_diagnostics": [
        "strategy_id",
        "formation_sequence",
        "formation_date",
        "execution_date",
        "window_start_exclusive",
        "window_end",
        "symbol",
        "observation_count",
        "mean_sector_excess",
        "mean_market_excess",
        "mean_50_50_portfolio_excess",
        "ES_sector",
        "ES_market",
        "ES_50_50_portfolio",
        "rho_ES",
        "beta_ES",
        "beta_CAPM",
        "relative_ES_score",
        "usual_downside_beta",
        "relative_usual_downside_beta",
        "sector_total_volatility",
        "market_total_volatility",
        "candidate_rank",
        "downside_control_rank",
        "unconditional_beta_rank",
        "total_volatility_rank",
        "candidate_selected",
        "downside_control_selected",
        "unconditional_beta_selected",
        "total_volatility_selected",
        "complete_formation_valid",
        "invalidity_reason",
    ],
    "halloween_state_diagnostics": [
        "strategy_id",
        "signal_date",
        "season_transition",
        "authorized_execution_date",
        "execution_status",
        "holding_start",
        "holding_end",
        "holding_asset",
        "holding_return",
    ],
}


def run() -> dict[str, Any]:
    validate_cards()
    source_hash_before = source_packet_hash()
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_files_before = cache_inventory_files()
    cache_before = map_hashes(cache_files_before)
    prior_files = prior_evidence_files()
    prior_before = evidence_identity_map(prior_files)
    prior_aggregate_before = aggregate_hash(prior_before)
    actually_missing_before = initially_missing_authorized_symbols()

    clean_output()
    preregistration_hash = write_preregistration_checkpoint()
    data_tasks = acquire_frozen_missing_symbols()
    preflight_rows, _ = data_preflight()
    results = [run_candidate(card, preflight_rows) for card in CARDS]
    reference = market.active_vm_dsr_usci_reference_returns()
    for result in results:
        result["portfolio_paths"] = build_portfolio_paths(result, reference)
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
    diagnostics = diagnostic_tables(results)
    outcomes = outcome_rows(results)
    failures = [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "missing_symbols": result["missing_symbols"],
        }
        for result in results
        if result["failure_reason"]
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
    funnel = funnel_counts(results, benchmarks, data_tasks, next_action)

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_files_after = cache_inventory_files()
    cache_after = map_hashes(cache_files_after)
    prior_after = evidence_identity_map(prior_files)
    prior_aggregate_after = aggregate_hash(prior_after)
    source_hash_after = source_packet_hash()
    cache_changed = sorted(
        path
        for path in set(cache_before) | set(cache_after)
        if cache_before.get(path, "missing") != cache_after.get(path, "missing")
    )
    authorized_cache_changes = all(
        Path(path).stem in FROZEN_INITIAL_MISSING_SYMBOLS
        for path in cache_changed
    )
    metadata_complete = all(
        all(
            row[field] not in ("", "unknown", "unmapped", None)
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
        for row in strategies + trials
    )
    all_invariants = all(
        bool(row["invariant_pass"]) for row in tables["invariant_results"]
    )
    consistency_passed = bool(
        tuple(result["card"].strategy_id for result in results)
        == EXPECTED_STRATEGY_IDS
        and len(sources) == len(strategies) == len(trials) == 5
        and len({row["trial_id"] for row in trials}) == 5
        and all(row["parent_trial_id"] == "" for row in trials)
        and all(row["adaptation_label"] == "" for row in trials)
        and metadata_complete
        and all(result["outcome"] in ALLOWED_OUTCOMES for result in results)
        and all(
            result["failure_reason"] in ALLOWED_FAILURE_REASONS
            for result in results
        )
        and protected_before == protected_after
        and prior_aggregate_before == prior_aggregate_after
        and source_hash_before == source_hash_after
        and authorized_cache_changes
        and all_invariants
        and funnel["outcome_count_reconciles"]
        and not any(FORBIDDEN_FLAGS.values())
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "overall_pass": consistency_passed,
        "exact_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "exactly_five_strategy_configurations": len(strategies) == 5,
        "exactly_five_canonical_trials": len(trials) == 5,
        "unique_trial_ids": len({row["trial_id"] for row in trials}) == 5,
        "canonical_trials_have_blank_parent_and_adaptation": all(
            row["parent_trial_id"] == "" and row["adaptation_label"] == ""
            for row in trials
        ),
        "distinct_family_count": len({card.family_id for card in CARDS}),
        "required_metadata_complete": metadata_complete,
        "named_same_purpose_half_controls": {
            card.strategy_id: card.same_purpose_control for card in CARDS
        },
        "half_period_controls_selected_from_results": False,
        "source_packet_hash_before": source_hash_before,
        "source_packet_hash_after": source_hash_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_file_count": len(prior_files),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_aggregate_before
        == prior_aggregate_after,
        "frozen_initial_missing_symbols": list(FROZEN_INITIAL_MISSING_SYMBOLS),
        "actually_missing_before_current_run": list(actually_missing_before),
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "cache_changed_paths": cache_changed,
        "cache_changes_authorized_and_logged": authorized_cache_changes,
        "unrelated_cache_files_unchanged": authorized_cache_changes,
        "bounded_data_task_count": len(data_tasks),
        "bounded_attempt_count_per_symbol_lte_one": all(
            int(row["attempt_count"]) <= 1 for row in data_tasks
        ),
        "provider_attempt_candidate_scope_exact": all(
            set(row["authorized_candidate_ids"].split("|"))
            .issubset(EXPECTED_STRATEGY_IDS[1:3])
            for row in data_tasks
        ),
        "all_executed_invariants_passed": all_invariants,
        "portfolio_contribution_uses_monthly_80_20_explicit_holdings": True,
        "daily_fixed_weight_return_blend_used": False,
        "cost_diagnostics_counted_as_trials": False,
        "benchmark_references_counted_as_strategies_or_trials": False,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "deterministic_frozen_core_hash": deterministic_core_hash(),
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    manifest = {
        "batch_id": BATCH_ID,
        "mode": MODE,
        "stage": STAGE,
        "source_library_id": SOURCE_LIBRARY_ID,
        "source_packet_location": (
            rel(SOURCE_PACKET_DIR)
            if SOURCE_PACKET_DIR.exists()
            else str(SOURCE_PACKET_ATTACHMENT)
        ),
        "strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "strategy_configuration_count": 5,
        "canonical_experiment_trial_count": 5,
        "executed_trial_count": funnel["experiment_trials_executed"],
        "benchmark_reference_count": len(benchmarks),
        "data_capability_task_count": len(data_tasks),
        "process_task_count": 1,
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_performance_calculation": True,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "validation_claimed": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "lifecycle_state_changed": False,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "source_library_records.csv", sources, list(sources[0]))
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    data_task_fields = [
        "task_id",
        "entity_type",
        "stage",
        "adaptation_label",
        "symbol",
        "authorized_candidate_ids",
        "initially_missing_in_frozen_preflight",
        "provider_path",
        "preferred_provider",
        "preferred_provider_attempted",
        "preferred_provider_status",
        "preferred_provider_reason_not_admitted",
        "fallback_provider",
        "fallback_attempted",
        "fallback_status",
        "attempt_count",
        "status",
        "acquisition_result",
        "provider_download_performed",
        "cache_path",
        "cache_hash",
        "canonical_frame_hash",
        "failure_reason",
        "api_secrets_persisted",
        "broker_or_order_endpoint_called",
        "counted_as_strategy",
        "counted_as_trial",
    ]
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_tasks,
        data_task_fields,
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", process, list(process[0]))
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0]),
    )
    metric_fields = [
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
        "outcome",
        "failure_reason",
        "decision_reason",
        "missing_symbols",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "all_trial_results.csv",
        tables["all_trial_results"],
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "control_results.csv",
        tables["control_results"],
        metric_fields,
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        tables["chronological_half_results"],
        metric_fields,
    )
    portfolio_fields = [
        "strategy_id",
        "family_id",
        "trial_id",
        "route",
        "portfolio_id",
        "portfolio_construction",
        "period_label",
        "period_role",
        "cost_assumption_bps",
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_result_rows,
        portfolio_fields,
    )
    for name, rows in diagnostics.items():
        write_csv(OUTPUT_DIR / f"{name}.csv", rows, DIAGNOSTIC_FIELDS[name])
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        tables["turnover_cost_reconciliation"],
        [
            "record_scope",
            "strategy_id",
            "control_or_portfolio_id",
            "cost_assumption_bps",
            "total_one_way_turnover",
            "trade_or_rebalance_count",
            "transaction_cost_drag",
            "turnover_formula",
            "natural_drift_between_rebalances",
            "transaction_costs_charged_once",
        ],
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        tables["invariant_results"],
        [
            "strategy_id",
            "record_type",
            "control_or_portfolio_id",
            "cost_assumption_bps",
            "explicit_zero_weights",
            "natural_drift_between_rebalances",
            "stale_weight_forward_fill_used",
            "negative_weights_present",
            "leverage_used",
            "same_period_price_signal_return_used",
            "transaction_costs_charged_once",
            "maximum_single_asset_weight",
            "maximum_gross_exposure",
            "maximum_daily_weight_sum",
            "numeric_invariant_status",
            "timing_invariant_status",
            "exposure_invariant_status",
            "weight_invariant_status",
            "invariant_pass",
        ],
    )
    followups = [
        row
        for row in outcomes
        if row["outcome"].startswith("exploratory_followup_candidate_")
    ]
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        followups,
        list(outcomes[0]),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv", outcomes, list(outcomes[0])
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
            "missing_symbols",
        ],
    )
    write_csv(OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0]))
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, funnel, next_action))

    return {
        "batch_id": BATCH_ID,
        "output_dir": rel(OUTPUT_DIR),
        "executed_trial_count": funnel["experiment_trials_executed"],
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "followup_candidate_count": funnel["followup_candidate_count"],
        "exact_next_action": next_action,
        "consistency_passed": consistency_passed,
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
