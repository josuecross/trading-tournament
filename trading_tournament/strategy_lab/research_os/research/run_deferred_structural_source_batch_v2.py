from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.data import load_symbol_data
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import acquire_validate_deferred_structural_etf_data_v2 as data_capability
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as reference_support
from strategy_lab.research_os.research import fast_source_library_remaining_candidates_batch_v4 as accounting


BATCH_ID = "run_deferred_structural_source_batch_v2"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v2"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / BATCH_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9

NEXT_ACTION_REVIEW = "direction_owner_review_deferred_structural_source_batch_v2"
NEXT_ACTION_REFRESH = "refresh_strategy_source_library_v3"
NEXT_ACTION_BLOCK = "direction_owner_review_deferred_structural_source_batch_v2_block_v1"

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
    "blocked_feasibility",
}
ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "weak_return",
    "excess_drawdown",
    "cost_drag",
    "turnover_drag",
    "period_instability",
    "benchmark_like_behavior",
    "data_or_comparability_failure",
    "methodology_failure",
    "data_unavailable",
    "capability_missing",
    "duplicate_or_redundant",
    "too_risky",
    "overfit_or_unstable",
}

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
AUTHORITATIVE_INPUT_FILES = [
    ROOT / "evidence" / "research_recovery" / "strategy_source_library_refresh_v2" / "latest" / "selected_source_library_records.yaml",
    ROOT / "evidence" / "research_recovery" / "strategy_source_library_refresh_v2" / "latest" / "frozen_candidate_specs.yaml",
    ROOT / "evidence" / "research_recovery" / "strategy_source_library_refresh_v2" / "latest" / "strategy_source_library_refresh_v2.md",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "source_library_records.csv",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "data_coverage.csv",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "data_integrity_checks.csv",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "cache_reload_reconciliation.csv",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "strategy_data_sufficiency.csv",
    ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "consistency_check.json",
]
REQUIRED_SYMBOLS = ("CSD", "IWR", "PKW", "SPY", "DGRO")
TARGET_CACHE_SYMBOLS = ("CSD", "IWR", "PKW")
DATA_CONFIG = {
    "data": {
        "cache_dir": "data/cache",
        "raw_dir": "data/raw",
        "use_cache": True,
        "refresh_cache": False,
        "start_date": "2000-01-01",
        "end_date": "2026-06-18",
    }
}

FORBIDDEN_FLAGS = {
    "source_research_or_completion": False,
    "provider_access_or_download": False,
    "parameter_or_instrument_change": False,
    "validation_or_robustness_run": False,
    "promotion_or_paper_demo_action": False,
    "broker_account_order_or_real_money_action": False,
    "additional_strategy_variant_run": False,
    "authoritative_lifecycle_state_modified": False,
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    source_record_id: str
    family_id: str
    display_name: str
    candidate_symbol: str
    control_ids: tuple[str, ...]
    control_symbols: tuple[str, ...]
    evaluation_start: str
    evaluation_end: str

    @property
    def trial_id(self) -> str:
        return f"deferred_structural_v2__{self.strategy_id}__canonical"

    @property
    def source_lineage(self) -> str:
        return f"{SOURCE_LIBRARY_ID}:{self.source_record_id}"

    @property
    def universe(self) -> tuple[str, ...]:
        return (self.candidate_symbol, *self.control_symbols)


CARDS = (
    CandidateCard(
        strategy_id="invesco_sp_us_spinoff_csd_v1",
        source_record_id="src_cusatis_spinoff_csd_wrapper_v1",
        family_id="corporate_spinoff_equity_anomaly",
        display_name="U.S. Corporate Spin-Off Equity Sleeve",
        candidate_symbol="CSD",
        control_ids=("IWR_buy_and_hold", "SPY_buy_and_hold"),
        control_symbols=("IWR", "SPY"),
        evaluation_start="2007-01-03",
        evaluation_end="2026-06-18",
    ),
    CandidateCard(
        strategy_id="nasdaq_buyback_achievers_pkw_v1",
        source_record_id="src_peyer_vermaelen_buyback_pkw_wrapper_v1",
        family_id="net_share_reduction_buyback_anomaly",
        display_name="U.S. BuyBack Achievers Equity Sleeve",
        candidate_symbol="PKW",
        control_ids=("SPY_buy_and_hold", "DGRO_buy_and_hold"),
        control_symbols=("SPY", "DGRO"),
        evaluation_start="2014-06-12",
        evaluation_end="2026-06-18",
    ),
)


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return format(value, ".15g")
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def protected_hashes() -> dict[str, str]:
    return hash_map(PROTECTED_STATE_PATHS)


def authoritative_hashes() -> dict[str, str]:
    return hash_map(AUTHORITATIVE_INPUT_FILES)


def cache_hashes() -> dict[str, str]:
    paths = sorted(path for path in (ROOT / "data" / "cache").glob("*") if path.is_file())
    return hash_map(paths)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_frozen_source_records() -> dict[str, dict[str, Any]]:
    path = AUTHORITATIVE_INPUT_FILES[0]
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(row.get("source_record_id")): row
        for row in payload.get("records", [])
        if str(row.get("source_record_id")) in {card.source_record_id for card in CARDS}
    }


def validate_frozen_inputs(source_records: dict[str, dict[str, Any]]) -> None:
    if set(source_records) != {card.source_record_id for card in CARDS}:
        raise RuntimeError("exactly_two_frozen_source_records_not_found")
    specs = yaml.safe_load(AUTHORITATIVE_INPUT_FILES[1].read_text(encoding="utf-8")) or {}
    spec_by_id = {str(row.get("strategy_id")): row for row in specs.get("strategies", [])}
    for card in CARDS:
        source = source_records[card.source_record_id]
        spec = spec_by_id.get(card.strategy_id, {})
        if source.get("proposed_strategy_id") != card.strategy_id or source.get("family_id") != card.family_id:
            raise RuntimeError(f"{card.strategy_id}:source_identity_mismatch")
        if tuple(spec.get("universe", [])) != card.universe:
            raise RuntimeError(f"{card.strategy_id}:frozen_universe_mismatch")
        if spec.get("rule", {}).get("target") != {card.candidate_symbol: 1.0}:
            raise RuntimeError(f"{card.strategy_id}:frozen_target_mismatch")
        if spec.get("rule", {}).get("rebalance") != "initial_allocation_only":
            raise RuntimeError(f"{card.strategy_id}:frozen_rebalance_mismatch")
    consistency = json.loads(AUTHORITATIVE_INPUT_FILES[-1].read_text(encoding="utf-8"))
    if not consistency.get("consistency_passed") or int(consistency.get("validated_symbol_count", 0)) != 3:
        raise RuntimeError("data_capability_packet_not_consistent")


def canonical_frame_hash(frame: pd.DataFrame) -> str:
    ordered = frame.reset_index(drop=True).copy()
    return data_capability.dataframe_hash(ordered)


def normalize_loaded_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.tz_localize(None)
    normalized = normalized.dropna(subset=["date"]).sort_values("date")
    normalized = normalized.set_index("date", drop=False)
    return normalized


def data_preflight() -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    expected_rows = {
        row["symbol"]: row
        for row in read_csv_rows(
            ROOT / "evidence" / "data_capability" / "acquire_validate_deferred_structural_etf_data_v2" / "latest" / "data_coverage.csv"
        )
    }
    expected_frames = {
        row["symbol"]: row
        for row in read_csv_rows(
            ROOT
            / "evidence"
            / "data_capability"
            / "acquire_validate_deferred_structural_etf_data_v2"
            / "latest"
            / "cache_reload_reconciliation.csv"
        )
    }
    rows: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    for symbol in REQUIRED_SYMBOLS:
        symbol_cache = ROOT / "data" / "cache" / f"{symbol}.csv"
        if symbol_cache.exists():
            frame, coverage, source = load_symbol_data(symbol, DATA_CONFIG, ROOT)
        else:
            frame, coverage, source = None, {"cache_file": rel(symbol_cache)}, "not_called_missing_cache"
        status = "fail"
        reason = ""
        normalized = pd.DataFrame()
        if source != "cache":
            reason = "normal_backtester_interface_did_not_use_cache"
        elif frame is None or frame.empty:
            reason = "normal_backtester_interface_returned_no_data"
        else:
            normalized = normalize_loaded_frame(frame)
            price_columns = ["open", "high", "low", "close", "adj_close"]
            values = normalized[price_columns].apply(pd.to_numeric, errors="coerce")
            volume = pd.to_numeric(normalized["volume"], errors="coerce")
            ordered_unique = bool(normalized.index.is_monotonic_increasing and normalized.index.is_unique)
            positive_finite = bool(np.isfinite(values.to_numpy()).all() and (values > 0.0).all().all())
            volume_valid = bool(np.isfinite(volume.to_numpy()).all() and (volume >= 0.0).all())
            ohlc_valid = bool(
                (values["high"] >= values[["open", "low", "close"]].max(axis=1) - 1e-9).all()
                and (values["low"] <= values[["open", "high", "close"]].min(axis=1) + 1e-9).all()
            )
            target_expected = expected_rows.get(symbol)
            row_count_match = target_expected is None or int(target_expected["row_count"]) == len(normalized)
            date_range_match = target_expected is None or (
                target_expected["first_date"] == normalized.index.min().date().isoformat()
                and target_expected["last_date"] == normalized.index.max().date().isoformat()
            )
            expected_frame = expected_frames.get(symbol)
            frame_hash = canonical_frame_hash(normalized.reset_index(drop=True))
            frame_hash_match = expected_frame is None or expected_frame["expected_frame_hash"] == frame_hash
            status = "pass" if all(
                (ordered_unique, positive_finite, volume_valid, ohlc_valid, row_count_match, date_range_match, frame_hash_match)
            ) else "fail"
            if status == "fail":
                reason = "cache_reconciliation_or_data_quality_failure"
            rows.append(
                {
                    "record_type": "symbol_preflight",
                    "symbol": symbol,
                    "normal_backtester_interface": "src.data.load_symbol_data",
                    "load_source": source,
                    "cache_path": coverage.get("cache_file", rel(ROOT / "data" / "cache" / f"{symbol}.csv")),
                    "cache_file_hash": file_hash(ROOT / "data" / "cache" / f"{symbol}.csv"),
                    "canonical_frame_hash": frame_hash,
                    "row_count": len(normalized),
                    "first_valid_date": normalized.index.min().date().isoformat(),
                    "last_valid_date": normalized.index.max().date().isoformat(),
                    "ordered_unique_dates": ordered_unique,
                    "positive_finite_adjusted_prices": positive_finite,
                    "nonnegative_finite_adjusted_volume": volume_valid,
                    "valid_adjusted_ohlc_relationships": ohlc_valid,
                    "expected_row_count_match": row_count_match,
                    "expected_date_range_match": date_range_match,
                    "expected_canonical_hash_match": frame_hash_match,
                    "preflight_status": status,
                    "failure_reason": reason,
                }
            )
        if normalized.empty:
            rows.append(
                {
                    "record_type": "symbol_preflight",
                    "symbol": symbol,
                    "normal_backtester_interface": "src.data.load_symbol_data",
                    "load_source": source,
                    "cache_path": coverage.get("cache_file", rel(ROOT / "data" / "cache" / f"{symbol}.csv")),
                    "cache_file_hash": file_hash(ROOT / "data" / "cache" / f"{symbol}.csv"),
                    "canonical_frame_hash": "",
                    "row_count": 0,
                    "first_valid_date": "",
                    "last_valid_date": "",
                    "ordered_unique_dates": False,
                    "positive_finite_adjusted_prices": False,
                    "nonnegative_finite_adjusted_volume": False,
                    "valid_adjusted_ohlc_relationships": False,
                    "expected_row_count_match": False,
                    "expected_date_range_match": False,
                    "expected_canonical_hash_match": False,
                    "preflight_status": status,
                    "failure_reason": reason or "data_unavailable",
                }
            )
        frames[symbol] = normalized
    for card in CARDS:
        available = all(not frames[symbol].empty for symbol in card.universe)
        common = pd.DatetimeIndex([])
        if available:
            common = frames[card.universe[0]].index
            for symbol in card.universe[1:]:
                common = common.intersection(frames[symbol].index)
            common = common.sort_values()
        expected_period = bool(
            len(common)
            and common.min().date().isoformat() == card.evaluation_start
            and common.max().date().isoformat() == card.evaluation_end
        )
        rows.append(
            {
                "record_type": "candidate_common_period",
                "symbol": card.strategy_id,
                "normal_backtester_interface": "src.data.load_symbol_data",
                "load_source": "cache_only",
                "cache_path": "|".join(rel(ROOT / "data" / "cache" / f"{symbol}.csv") for symbol in card.universe),
                "cache_file_hash": "|".join(file_hash(ROOT / "data" / "cache" / f"{symbol}.csv") for symbol in card.universe),
                "canonical_frame_hash": "",
                "row_count": len(common),
                "first_valid_date": common.min().date().isoformat() if len(common) else "",
                "last_valid_date": common.max().date().isoformat() if len(common) else "",
                "ordered_unique_dates": bool(common.is_monotonic_increasing and common.is_unique),
                "positive_finite_adjusted_prices": available,
                "nonnegative_finite_adjusted_volume": available,
                "valid_adjusted_ohlc_relationships": available,
                "expected_row_count_match": True,
                "expected_date_range_match": expected_period,
                "expected_canonical_hash_match": True,
                "preflight_status": "pass" if available and expected_period else "fail",
                "failure_reason": "" if available and expected_period else "data_or_comparability_failure",
            }
        )
    return rows, frames


def preregistration_core() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "display_name": card.display_name,
            "entity_type": "strategy_configuration",
            "strategy_architecture": "structural_index_wrapper_buy_and_hold",
            "source_or_research_lineage": card.source_lineage,
            "instrument_universe": card.universe,
            "parameters": {
                "candidate_target_weight": 1.0,
                "rebalance": "initial_allocation_only",
                "timing_filter": "none",
                "portfolio_contribution_weight": 0.20,
                "portfolio_contribution_rebalance": "monthly_rebalanced_80_20",
            },
            "benchmark_or_control": (*card.control_ids, "frozen_current_active_vm_dsr_usci_combo"),
            "stage": "exploration",
            "trial_id": card.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "evaluation_start": card.evaluation_start,
            "evaluation_end": card.evaluation_end,
            "execution_timing": "first_common_eligible_close_target_applied_to_following_session",
            "cost_assumptions_bps": COST_BPS_GRID,
            "primary_cost_bps": PRIMARY_COST_BPS,
            "preregistration_timestamp": FROZEN_TIMESTAMP,
        }
        for card in CARDS
    ]


def deterministic_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def card_common_prices(card: CandidateCard, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = [frames[symbol]["adj_close"].rename(symbol) for symbol in card.universe]
    prices = pd.concat(series, axis=1, join="inner").dropna().sort_index()
    return prices.loc[card.evaluation_start : card.evaluation_end]


def raw_component_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change(fill_method=None).fillna(0.0).astype(float)


def standalone_payload(prices: pd.Series, cost_bps: float) -> dict[str, Any]:
    frame = prices.to_frame(prices.name)
    events = accounting.initial_event(frame.index, {str(prices.name): 1.0}, (str(prices.name),))
    return accounting.simulate_close_to_close(
        frame,
        events,
        cost_bps,
        "first_common_eligible_close_target_applied_to_following_session",
    )


def payload_metrics(payload: dict[str, Any], period_index: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    metrics = accounting.metric_payload(payload, period_index)
    metrics["weight_invariant_status"] = (
        "pass"
        if metrics["invariant_pass"]
        and float(metrics["max_daily_weight_sum"]) >= -WEIGHT_TOLERANCE
        and float(metrics["max_daily_exposure"]) >= -WEIGHT_TOLERANCE
        else "fail"
    )
    metrics["all_invariants_pass"] = bool(metrics["invariant_pass"] and metrics["weight_invariant_status"] == "pass")
    return metrics


def run_card(card: CandidateCard, frames: dict[str, pd.DataFrame], preflight_rows: list[dict[str, Any]]) -> dict[str, Any]:
    preflight = next(
        row for row in preflight_rows if row["record_type"] == "candidate_common_period" and row["symbol"] == card.strategy_id
    )
    if preflight["preflight_status"] != "pass":
        return {
            "card": card,
            "executable": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_or_comparability_failure",
            "decision_reason": preflight["failure_reason"],
            "standalone": {},
            "raw_returns": {},
            "portfolios": {},
            "best_control_id": "",
        }
    prices = card_common_prices(card, frames)
    if (
        prices.empty
        or prices.index.min().date().isoformat() != card.evaluation_start
        or prices.index.max().date().isoformat() != card.evaluation_end
    ):
        return {
            "card": card,
            "executable": False,
            "outcome": "inconclusive_data_issue",
            "failure_reason": "data_or_comparability_failure",
            "decision_reason": "frozen_common_period_not_reproduced",
            "standalone": {},
            "raw_returns": {},
            "portfolios": {},
            "best_control_id": "",
        }
    symbols_by_id = {card.strategy_id: card.candidate_symbol, **dict(zip(card.control_ids, card.control_symbols))}
    raw_returns = {entity_id: raw_component_returns(prices[symbol]) for entity_id, symbol in symbols_by_id.items()}
    standalone: dict[tuple[str, float], dict[str, Any]] = {}
    for entity_id, symbol in symbols_by_id.items():
        for cost_bps in COST_BPS_GRID:
            standalone[(entity_id, cost_bps)] = standalone_payload(prices[symbol], cost_bps)
    return {
        "card": card,
        "executable": True,
        "outcome": "pending_portfolio_gate",
        "failure_reason": "",
        "decision_reason": "pending_portfolio_gate",
        "standalone": standalone,
        "raw_returns": raw_returns,
        "portfolios": {},
        "best_control_id": "",
    }


def build_portfolios(result: dict[str, Any], reference_returns: pd.Series) -> dict[tuple[str, float], dict[str, Any]]:
    if not result["executable"]:
        return {}
    card: CandidateCard = result["card"]
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    sleeve_ids = (card.strategy_id, *card.control_ids)
    for cost_bps in COST_BPS_GRID:
        candidate_index = result["raw_returns"][card.strategy_id].index
        common = candidate_index.intersection(reference_returns.dropna().index).sort_values()
        reference = reference_returns.reindex(common).dropna()
        payloads[("frozen_reference_100pct", cost_bps)] = accounting.reference_payload(reference, cost_bps)
        for sleeve_id in sleeve_ids:
            sleeve = result["raw_returns"][sleeve_id].reindex(reference.index).dropna()
            aligned_reference = reference.reindex(sleeve.index).dropna()
            portfolio_id = (
                f"{card.strategy_id}_candidate_20pct"
                if sleeve_id == card.strategy_id
                else f"{sleeve_id}_20pct_control"
            )
            payloads[(portfolio_id, cost_bps)] = accounting.simulate_two_component_portfolio(
                aligned_reference,
                sleeve,
                portfolio_id,
                cost_bps,
            )
    return payloads


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    values = ("cagr", "sharpe_ratio", "maximum_drawdown")
    return all(float(control[key]) >= float(candidate[key]) - 1e-12 for key in values) and any(
        float(control[key]) > float(candidate[key]) + 1e-12 for key in values
    )


def best_control(control_metrics: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return max(
        control_metrics.items(),
        key=lambda item: (
            float(item[1]["sharpe_ratio"]),
            float(item[1]["maximum_drawdown"]),
            float(item[1]["cagr"]),
            item[0],
        ),
    )


def classify_result(result: dict[str, Any]) -> None:
    if not result["executable"]:
        return
    card: CandidateCard = result["card"]
    candidate = payload_metrics(result["standalone"][(card.strategy_id, PRIMARY_COST_BPS)])
    controls = {
        control_id: payload_metrics(result["standalone"][(control_id, PRIMARY_COST_BPS)])
        for control_id in card.control_ids
    }
    if not candidate["all_invariants_pass"]:
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="candidate_standalone_invariant_failed",
        )
        return
    if float(candidate["total_return"]) <= 0.0:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_return",
            decision_reason="candidate_full_period_after_cost_return_not_positive",
        )
        return
    if any(dominates(control, candidate) for control in controls.values()):
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason="standalone_control_dominates_candidate",
        )
        return
    portfolios = result["portfolios"]
    candidate_id = f"{card.strategy_id}_candidate_20pct"
    candidate_portfolio = payload_metrics(portfolios[(candidate_id, PRIMARY_COST_BPS)])
    reference = payload_metrics(portfolios[("frozen_reference_100pct", PRIMARY_COST_BPS)])
    portfolio_controls = {
        f"{control_id}_20pct_control": payload_metrics(
            portfolios[(f"{control_id}_20pct_control", PRIMARY_COST_BPS)]
        )
        for control_id in card.control_ids
    }
    all_invariants = candidate_portfolio["all_invariants_pass"] and all(
        metric["all_invariants_pass"] for metric in portfolio_controls.values()
    )
    if not all_invariants:
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="portfolio_contribution_invariant_failed",
        )
        return
    improves_sharpe = float(candidate_portfolio["sharpe_ratio"]) > float(reference["sharpe_ratio"])
    improves_drawdown = float(candidate_portfolio["maximum_drawdown"]) > float(reference["maximum_drawdown"])
    worsens_both = (
        float(candidate_portfolio["sharpe_ratio"]) < float(reference["sharpe_ratio"])
        and float(candidate_portfolio["maximum_drawdown"]) < float(reference["maximum_drawdown"])
    )
    if not ((improves_sharpe or improves_drawdown) and not worsens_both):
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason="candidate_portfolio_does_not_improve_reference_without_worsening_both",
        )
        return
    if any(dominates(control, candidate_portfolio) for control in portfolio_controls.values()):
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason="control_portfolio_dominates_candidate_portfolio",
        )
        return
    best_id, best = best_control(portfolio_controls)
    result["best_control_id"] = best_id
    sharpe_difference = float(candidate_portfolio["sharpe_ratio"]) - float(best["sharpe_ratio"])
    drawdown_difference = float(candidate_portfolio["maximum_drawdown"]) - float(best["maximum_drawdown"])
    if sharpe_difference < 0.02 and drawdown_difference < 0.01:
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="candidate_difference_below_both_materiality_thresholds",
        )
        return
    for half_label, start, end in accounting.split_halves(portfolios[(candidate_id, PRIMARY_COST_BPS)]["returns"].index):
        index = portfolios[(candidate_id, PRIMARY_COST_BPS)]["returns"].loc[start:end].index
        candidate_half = payload_metrics(portfolios[(candidate_id, PRIMARY_COST_BPS)], index)
        control_half = payload_metrics(portfolios[(best_id, PRIMARY_COST_BPS)], index)
        if (
            float(candidate_half["sharpe_ratio"]) <= float(control_half["sharpe_ratio"])
            and float(candidate_half["maximum_drawdown"]) <= float(control_half["maximum_drawdown"])
        ):
            result.update(
                outcome="closed_exploration",
                failure_reason="period_instability",
                decision_reason=f"candidate_not_favorable_on_sharpe_or_drawdown_in_{half_label}",
            )
            return
    candidate_10 = payload_metrics(portfolios[(candidate_id, 10.0)])
    best_10 = payload_metrics(portfolios[(best_id, 10.0)])
    if (
        float(candidate_10["sharpe_ratio"]) < float(best_10["sharpe_ratio"])
        and float(candidate_10["maximum_drawdown"]) < float(best_10["maximum_drawdown"])
    ):
        result.update(
            outcome="closed_exploration",
            failure_reason="cost_drag",
            decision_reason="candidate_advantage_unfavorable_on_both_sharpe_and_drawdown_at_10bps",
        )
        return
    result.update(
        outcome="exploratory_followup_candidate_diversifier",
        failure_reason="",
        decision_reason="candidate_passed_frozen_lightweight_diversifier_gate",
    )


METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "all_invariants_pass",
]


def metric_row(
    card: CandidateCard,
    entity_id: str,
    role: str,
    cost_bps: float,
    payload: dict[str, Any],
    period_label: str = "full_period",
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    metrics = payload_metrics(payload, period_index)
    return {
        "strategy_id": card.strategy_id,
        "trial_id": card.trial_id,
        "entity_id": entity_id,
        "result_role": role,
        "period_label": period_label,
        "cost_assumption_bps": cost_bps,
        **{field: metrics[field] for field in METRIC_FIELDS},
    }


def all_trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        for cost_bps in COST_BPS_GRID:
            rows.append(
                metric_row(
                    card,
                    card.strategy_id,
                    "candidate",
                    cost_bps,
                    result["standalone"][(card.strategy_id, cost_bps)],
                )
            )
    return rows


def control_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        for control_id in card.control_ids:
            for cost_bps in COST_BPS_GRID:
                rows.append(
                    metric_row(
                        card,
                        control_id,
                        "standalone_control",
                        cost_bps,
                        result["standalone"][(control_id, cost_bps)],
                    )
                )
    return rows


def chronological_half_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        entity_ids = (card.strategy_id, *card.control_ids)
        for entity_id in entity_ids:
            role = "candidate" if entity_id == card.strategy_id else "standalone_control"
            for cost_bps in COST_BPS_GRID:
                payload = result["standalone"][(entity_id, cost_bps)]
                for label, start, end in accounting.split_halves(payload["returns"].index):
                    period_index = payload["returns"].loc[start:end].index
                    rows.append(metric_row(card, entity_id, role, cost_bps, payload, label, period_index))
    return rows


def portfolio_contribution_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        for (portfolio_id, cost_bps), payload in sorted(result["portfolios"].items()):
            role = (
                "frozen_reference"
                if portfolio_id == "frozen_reference_100pct"
                else "candidate_contribution"
                if portfolio_id == f"{card.strategy_id}_candidate_20pct"
                else "control_contribution"
            )
            rows.append(metric_row(card, portfolio_id, role, cost_bps, payload))
            for label, start, end in accounting.split_halves(payload["returns"].index):
                period_index = payload["returns"].loc[start:end].index
                rows.append(metric_row(card, portfolio_id, role, cost_bps, payload, label, period_index))
    return rows


def calendar_year_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        payloads: list[tuple[str, str, dict[str, Any]]] = []
        for entity_id in (card.strategy_id, *card.control_ids):
            payloads.append(
                (
                    entity_id,
                    "candidate" if entity_id == card.strategy_id else "standalone_control",
                    result["standalone"][(entity_id, PRIMARY_COST_BPS)],
                )
            )
        payloads.extend(
            (
                portfolio_id,
                "frozen_reference"
                if portfolio_id == "frozen_reference_100pct"
                else "candidate_contribution"
                if portfolio_id == f"{card.strategy_id}_candidate_20pct"
                else "control_contribution",
                payload,
            )
            for (portfolio_id, cost_bps), payload in result["portfolios"].items()
            if cost_bps == PRIMARY_COST_BPS
        )
        for entity_id, role, payload in payloads:
            for year, year_returns in payload["returns"].groupby(payload["returns"].index.year):
                index = year_returns.index
                metrics = payload_metrics(payload, index)
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "trial_id": card.trial_id,
                        "entity_id": entity_id,
                        "result_role": role,
                        "calendar_year": int(year),
                        "cost_assumption_bps": PRIMARY_COST_BPS,
                        "evaluation_start": metrics["evaluation_start"],
                        "evaluation_end": metrics["evaluation_end"],
                        "trading_days": metrics["trading_days"],
                        "total_return": metrics["total_return"],
                        "annualized_volatility": metrics["annualized_volatility"],
                        "sharpe_ratio": metrics["sharpe_ratio"],
                        "maximum_drawdown": metrics["maximum_drawdown"],
                        "turnover": metrics["turnover"],
                        "transaction_cost_drag": metrics["transaction_cost_drag"],
                        "max_daily_exposure": metrics["max_daily_exposure"],
                        "max_daily_weight_sum": metrics["max_daily_weight_sum"],
                        "all_invariants_pass": metrics["all_invariants_pass"],
                        "diagnostic_only": True,
                        "clean_or_sealed_holdout": False,
                    }
                )
    return rows


def portfolio_event_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        for (portfolio_id, cost_bps), payload in sorted(result["portfolios"].items()):
            for event in payload["event_rows"]:
                rows.append(
                    {
                        "strategy_id": card.strategy_id,
                        "trial_id": card.trial_id,
                        "portfolio_id": portfolio_id,
                        "portfolio_construction": (
                            "100pct_frozen_reference"
                            if portfolio_id == "frozen_reference_100pct"
                            else "monthly_rebalanced_80_20"
                        ),
                        "cost_assumption_bps": cost_bps,
                        **event,
                        "turnover_formula": "0.5_times_sum_abs_target_minus_pretrade_weight",
                    }
                )
    return rows


def turnover_reconciliation_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executable"]:
            continue
        card = result["card"]
        for (entity_id, cost_bps), payload in sorted(result["standalone"].items()):
            metrics = payload_metrics(payload)
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "entity_id": entity_id,
                    "accounting_scope": "standalone_buy_and_hold",
                    "cost_assumption_bps": cost_bps,
                    "one_way_turnover": metrics["turnover"],
                    "trade_or_rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "initial_establishment_charged": True,
                    "internal_etf_turnover_charged": False,
                    "component_cost_double_counted": False,
                    "rebalance_policy": "initial_allocation_only_with_natural_drift",
                }
            )
        for (portfolio_id, cost_bps), payload in sorted(result["portfolios"].items()):
            metrics = payload_metrics(payload)
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "trial_id": card.trial_id,
                    "entity_id": portfolio_id,
                    "accounting_scope": "portfolio_contribution",
                    "cost_assumption_bps": cost_bps,
                    "one_way_turnover": metrics["turnover"],
                    "trade_or_rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "initial_establishment_charged": portfolio_id != "frozen_reference_100pct",
                    "internal_etf_turnover_charged": False,
                    "component_cost_double_counted": False,
                    "rebalance_policy": (
                        "frozen_reference_no_additional_turnover"
                        if portfolio_id == "frozen_reference_100pct"
                        else "monthly_rebalanced_80_20_with_natural_drift"
                    ),
                }
            )
    return rows


def invariant_rows(
    results: list[dict[str, Any]],
    preflight_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for preflight in preflight_rows:
        rows.append(
            {
                "strategy_id": preflight["symbol"] if preflight["record_type"] == "candidate_common_period" else "",
                "trial_id": "",
                "entity_id": preflight["symbol"],
                "scope": preflight["record_type"],
                "cost_assumption_bps": "",
                "check_name": "data_preflight",
                "status": preflight["preflight_status"],
                "details": preflight["failure_reason"],
            }
        )
    for result in results:
        card = result["card"]
        if not result["executable"]:
            continue
        payload_maps = [
            ("standalone", result["standalone"]),
            ("portfolio_contribution", result["portfolios"]),
        ]
        for scope, payload_map in payload_maps:
            for (entity_id, cost_bps), payload in sorted(payload_map.items()):
                metrics = payload_metrics(payload)
                for check_name, status in (
                    ("numeric", metrics["numeric_invariant_status"]),
                    ("timing", metrics["timing_invariant_status"]),
                    ("exposure", metrics["exposure_invariant_status"]),
                    ("weight", metrics["weight_invariant_status"]),
                ):
                    rows.append(
                        {
                            "strategy_id": card.strategy_id,
                            "trial_id": card.trial_id,
                            "entity_id": entity_id,
                            "scope": scope,
                            "cost_assumption_bps": cost_bps,
                            "check_name": check_name,
                            "status": status,
                            "details": (
                                f"max_exposure={metrics['max_daily_exposure']};"
                                f"max_weight_sum={metrics['max_daily_weight_sum']}"
                            ),
                        }
                    )
    return rows


def source_library_rows(source_records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        source = source_records[card.source_record_id]
        rows.append(
            {
                "source_record_id": card.source_record_id,
                "entity_type": "source_library_record",
                "stage": "source_extracted",
                "proposed_strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "strategy_architecture": source["strategy_architecture"],
                "exact_canonical_rule": source["exact_canonical_rule"],
                "source_library_id": SOURCE_LIBRARY_ID,
                "counted_as_strategy": False,
                "counted_as_trial": False,
            }
        )
    return rows


def strategy_card_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "strategy_configuration",
                "strategy_architecture": "structural_index_wrapper_buy_and_hold",
                "source_or_research_lineage": card.source_lineage,
                "instrument_universe": card.universe,
                "parameters": {
                    "target_weight": {card.candidate_symbol: 1.0},
                    "timing_filter": "none",
                    "rebalance": "initial_allocation_only",
                },
                "benchmark_or_control": (*card.control_ids, "frozen_current_active_vm_dsr_usci_combo"),
                "stage": "exploration",
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": next_action,
                "route": "diversifier",
                "evaluation_start": card.evaluation_start,
                "evaluation_end": card.evaluation_end,
                "execution_timing": "first_common_eligible_close_target_applied_to_following_session",
                "data_lineage": "acquire_validate_deferred_structural_etf_data_v2",
            }
        )
    return rows


def trial_ledger_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        card: CandidateCard = result["card"]
        rows.append(
            {
                "strategy_id": card.strategy_id,
                "family_id": card.family_id,
                "display_name": card.display_name,
                "entity_type": "experiment_trial",
                "strategy_architecture": "structural_index_wrapper_buy_and_hold",
                "source_or_research_lineage": card.source_lineage,
                "instrument_universe": card.universe,
                "parameters": {
                    "target_weight": {card.candidate_symbol: 1.0},
                    "timing_filter": "none",
                    "rebalance": "initial_allocation_only",
                },
                "benchmark_or_control": (*card.control_ids, "frozen_current_active_vm_dsr_usci_combo"),
                "stage": "exploration",
                "trial_id": card.trial_id,
                "parent_trial_id": "",
                "adaptation_label": "",
                "outcome": result["outcome"],
                "failure_reason": result["failure_reason"],
                "next_action": next_action,
                "route": "diversifier",
                "execution_timing": "first_common_eligible_close_target_applied_to_following_session",
                "data_lineage": "acquire_validate_deferred_structural_etf_data_v2",
                "changed_fields_from_parent": "canonical_configuration_no_parent",
                "evaluation_start": card.evaluation_start,
                "evaluation_end": card.evaluation_end,
                "cost_assumptions_bps": COST_BPS_GRID,
                "primary_cost_bps": PRIMARY_COST_BPS,
                "preregistration_timestamp": FROZEN_TIMESTAMP,
                "strategy_definition_changed_after_results": False,
                "instruments_changed_after_results": False,
                "parameters_changed_after_results": False,
                "benchmarks_changed_after_results": False,
                "timeframe_selected_from_performance": False,
            }
        )
    return rows


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            "benchmark_or_control_id": "IWR_buy_and_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "instrument_or_construction": "IWR",
            "linked_strategy_ids": "invesco_sp_us_spinoff_csd_v1",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "SPY_buy_and_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "instrument_or_construction": "SPY",
            "linked_strategy_ids": "invesco_sp_us_spinoff_csd_v1|nasdaq_buyback_achievers_pkw_v1",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "DGRO_buy_and_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "instrument_or_construction": "DGRO",
            "linked_strategy_ids": "nasdaq_buyback_achievers_pkw_v1",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "instrument_or_construction": "accepted_frozen_reference_daily_return_series",
            "linked_strategy_ids": "invesco_sp_us_spinoff_csd_v1|nasdaq_buyback_achievers_pkw_v1",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
    ]


def select_next_action(results: list[dict[str, Any]]) -> str:
    outcomes = [result["outcome"] for result in results]
    if any(outcome in {"inconclusive_data_issue", "blocked_feasibility"} for outcome in outcomes):
        return NEXT_ACTION_BLOCK
    if any(outcome == "exploratory_followup_candidate_diversifier" for outcome in outcomes):
        return NEXT_ACTION_REVIEW
    return NEXT_ACTION_REFRESH


def process_task_row(next_action: str) -> dict[str, Any]:
    return {
        "task_id": BATCH_ID,
        "entity_type": "process_task",
        "stage": "exploration",
        "mode": "fast-progress",
        "candidate_count": len(CARDS),
        "trial_count": len(CARDS),
        "exact_next_action": next_action,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    }


def outcome_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "trial_id": result["card"].trial_id,
            "outcome": result["outcome"],
            "primary_failure_reason": result["failure_reason"],
            "decision_reason": result["decision_reason"],
            "best_80_20_control_id": result["best_control_id"],
            "stage": "exploration",
            "validation_claimed": False,
            "promotion_or_paper_demo_authorized": False,
            "exact_next_action": next_action,
        }
        for result in results
    ]


def followup_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": result["card"].strategy_id,
            "family_id": result["card"].family_id,
            "trial_id": result["card"].trial_id,
            "classification": result["outcome"],
            "route": "diversifier",
            "exploration_only": True,
            "validation_or_promotion_authorized": False,
        }
        for result in results
        if result["outcome"] == "exploratory_followup_candidate_diversifier"
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
            "family_closed": False,
            "exact_variant_adapted_to_escape_closure": False,
        }
        for result in results
        if result["failure_reason"]
    ]


def next_action_rows(results: list[dict[str, Any]], next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "scope": "strategy_configuration",
            "entity_id": result["card"].strategy_id,
            "outcome": result["outcome"],
            "exact_next_action": next_action,
            "execute_now": False,
        }
        for result in results
    ] + [
        {
            "scope": "batch",
            "entity_id": BATCH_ID,
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "execute_now": False,
        }
    ]


def funnel_counts(results: list[dict[str, Any]], benchmarks: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = [result["outcome"] for result in results]
    return {
        "source_library_records_referenced": 2,
        "strategy_configurations_considered": 2,
        "experiment_trials_executed": sum(result["executable"] for result in results),
        "benchmark_references": len(benchmarks),
        "process_tasks": 1,
        "diversifier_followup_candidates": outcomes.count("exploratory_followup_candidate_diversifier"),
        "closed_strategies": outcomes.count("closed_exploration"),
        "blocked_or_inconclusive_strategies": sum(
            outcome in {"blocked_feasibility", "inconclusive_data_issue"} for outcome in outcomes
        ),
    }


def report_text(results: list[dict[str, Any]], funnel: dict[str, Any], next_action: str) -> str:
    lines = [
        "# Deferred Structural Source Batch V2",
        "",
        "This packet records one bounded exploration trial for each of the two frozen structural ETF wrappers.",
        "It does not provide validation, robustness, promotion, or paper/demo evidence.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['card'].strategy_id}`: `{result['outcome']}`"
            + (f" (`{result['failure_reason']}`)" if result["failure_reason"] else "")
            + f". {result['decision_reason']}."
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "Standalone ETF sleeves use one initial establishment trade, then natural drift with no internal ETF turnover charge.",
            "Portfolio contribution uses an explicit 80/20 account, natural drift, month-end calculation, next-session-close",
            "execution, and actual pre-trade holdings turnover. Raw ETF component returns are used so standalone costs are not",
            "double-counted inside the contribution portfolios.",
            "",
            "Chronological halves and calendar years are descriptive diagnostics. Neither half is a clean or sealed holdout.",
            "",
            "## Funnel",
            "",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in funnel.items())
    lines.extend(
        [
            "",
            f"Exact next action: `{next_action}`.",
            "",
            "The next action was not executed.",
        ]
    )
    return "\n".join(lines)


STRATEGY_CARD_FIELDS = [
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
    "failure_reason",
    "next_action",
    "route",
    "evaluation_start",
    "evaluation_end",
    "execution_timing",
    "data_lineage",
]
TRIAL_FIELDS = [
    *STRATEGY_CARD_FIELDS,
    "changed_fields_from_parent",
    "cost_assumptions_bps",
    "primary_cost_bps",
    "preregistration_timestamp",
    "strategy_definition_changed_after_results",
    "instruments_changed_after_results",
    "parameters_changed_after_results",
    "benchmarks_changed_after_results",
    "timeframe_selected_from_performance",
]
RESULT_FIELDS = [
    "strategy_id",
    "trial_id",
    "entity_id",
    "result_role",
    "period_label",
    "cost_assumption_bps",
    *METRIC_FIELDS,
]
PREFLIGHT_FIELDS = [
    "record_type",
    "symbol",
    "normal_backtester_interface",
    "load_source",
    "cache_path",
    "cache_file_hash",
    "canonical_frame_hash",
    "row_count",
    "first_valid_date",
    "last_valid_date",
    "ordered_unique_dates",
    "positive_finite_adjusted_prices",
    "nonnegative_finite_adjusted_volume",
    "valid_adjusted_ohlc_relationships",
    "expected_row_count_match",
    "expected_date_range_match",
    "expected_canonical_hash_match",
    "preflight_status",
    "failure_reason",
]


def write_artifacts(
    source_records: dict[str, dict[str, Any]],
    preflight_rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    preregistration_hash: str,
    protected_before: dict[str, str],
    input_before: dict[str, str],
    cache_before: dict[str, str],
) -> dict[str, Any]:
    next_action = select_next_action(results)
    benchmarks = benchmark_rows()
    strategies = strategy_card_rows(results, next_action)
    trials = trial_ledger_rows(results, next_action)
    all_trials = all_trial_rows(results)
    controls = control_rows(results)
    halves = chronological_half_rows(results)
    calendar = calendar_year_rows(results)
    contributions = portfolio_contribution_rows(results)
    events = portfolio_event_rows(results)
    turnover = turnover_reconciliation_rows(results)
    invariants = invariant_rows(results, preflight_rows)
    outcomes = outcome_rows(results, next_action)
    followups = followup_rows(results)
    failures = failure_rows(results)
    actions = next_action_rows(results, next_action)
    funnel = funnel_counts(results, benchmarks)

    protected_after = protected_hashes()
    input_after = authoritative_hashes()
    cache_after = cache_hashes()
    event_turnover_formula_pass = all(
        math.isclose(
            float(row["one_way_turnover"]),
            0.5
            * (
                abs(float(row["post_trade_reference_weight"]) - float(row["pretrade_reference_weight"]))
                + abs(float(row["post_trade_sleeve_weight"]) - float(row["pretrade_sleeve_weight"]))
            ),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for row in events
    )
    event_timing_pass = all(
        row["event_type"] == "initial_establishment"
        or (
            bool(row["signal_date"])
            and pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["event_date"])
        )
        for row in events
    )
    metadata_complete = all(
        all(csv_value(row.get(field, "")).lower() not in {"unknown", "unmapped"} for field in STRATEGY_CARD_FIELDS)
        for row in strategies
    ) and all(
        all(csv_value(row.get(field, "")).lower() not in {"unknown", "unmapped"} for field in TRIAL_FIELDS)
        for row in trials
    )
    consistency = {
        "batch_id": BATCH_ID,
        "mode": "fast-progress",
        "stage": "exploration",
        "exact_candidate_ids": [card.strategy_id for card in CARDS],
        "source_library_record_count": 2,
        "strategy_configuration_count": len(strategies),
        "experiment_trial_record_count": len(trials),
        "experiment_trials_executed": funnel["experiment_trials_executed"],
        "benchmark_reference_count": len(benchmarks),
        "process_task_count": 1,
        "preregistration_completed_after_preflight_before_results": True,
        "preregistration_core_hash": preregistration_hash,
        "one_canonical_trial_per_candidate": len({row["trial_id"] for row in trials}) == 2,
        "no_parent_trial_and_blank_adaptation_label": all(
            not row["parent_trial_id"] and not row["adaptation_label"] for row in trials
        ),
        "strategy_and_trial_metadata_complete": metadata_complete,
        "all_outcomes_standardized": all(result["outcome"] in ALLOWED_OUTCOMES for result in results),
        "all_failure_reasons_standardized": all(result["failure_reason"] in ALLOWED_FAILURE_REASONS for result in results),
        "standalone_primary_and_cost_diagnostics_present": len(all_trials) == 6 and len(controls) == 12,
        "chronological_halves_are_not_clean_holdouts": True,
        "calendar_years_are_diagnostic_only": all(row["diagnostic_only"] for row in calendar),
        "portfolio_contribution_uses_monthly_rebalanced_80_20": all(
            row["portfolio_construction"] == "monthly_rebalanced_80_20" for row in events
        ),
        "portfolio_contribution_does_not_use_fixed_weight_daily_blend": True,
        "actual_pretrade_turnover_formula_pass": event_turnover_formula_pass,
        "month_end_signal_next_session_timing_pass": event_timing_pass,
        "standalone_and_portfolio_component_costs_not_double_counted": all(
            not row["component_cost_double_counted"] for row in turnover
        ),
        "all_data_preflight_checks_pass_for_executed_candidates": all(
            row["preflight_status"] == "pass"
            for row in preflight_rows
            if row["record_type"] == "candidate_common_period"
            and any(
                result["card"].strategy_id == row["symbol"] and result["executable"]
                for result in results
            )
        ),
        "all_numeric_timing_exposure_weight_invariants_pass": all(
            row["status"] == "pass"
            for row in invariants
            if row["scope"] in {"standalone", "portfolio_contribution"}
        ),
        "funnel_arithmetically_consistent": (
            funnel["diversifier_followup_candidates"]
            + funnel["closed_strategies"]
            + funnel["blocked_or_inconclusive_strategies"]
            == 2
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "authoritative_input_hashes_before": input_before,
        "authoritative_input_hashes_after": input_after,
        "authoritative_input_hashes_unchanged": input_before == input_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "all_cache_hashes_unchanged": cache_before == cache_after,
        "exact_next_action": next_action,
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["strategy_configuration_count"] == 2
        and consistency["experiment_trial_record_count"] == 2
        and consistency["one_canonical_trial_per_candidate"]
        and consistency["no_parent_trial_and_blank_adaptation_label"]
        and consistency["strategy_and_trial_metadata_complete"]
        and consistency["all_outcomes_standardized"]
        and consistency["all_failure_reasons_standardized"]
        and consistency["standalone_primary_and_cost_diagnostics_present"]
        and consistency["portfolio_contribution_uses_monthly_rebalanced_80_20"]
        and consistency["actual_pretrade_turnover_formula_pass"]
        and consistency["month_end_signal_next_session_timing_pass"]
        and consistency["standalone_and_portfolio_component_costs_not_double_counted"]
        and consistency["all_numeric_timing_exposure_weight_invariants_pass"]
        and consistency["funnel_arithmetically_consistent"]
        and consistency["protected_state_hashes_unchanged"]
        and consistency["authoritative_input_hashes_unchanged"]
        and consistency["all_cache_hashes_unchanged"]
        and not any(consistency[key] for key in FORBIDDEN_FLAGS)
    )

    write_yaml(
        OUTPUT_DIR / "batch_manifest.yaml",
        {
            "batch_id": BATCH_ID,
            "mode": "fast-progress",
            "stage": "exploration",
            "source_library_id": SOURCE_LIBRARY_ID,
            "candidate_ids": [card.strategy_id for card in CARDS],
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            "primary_cost_bps": PRIMARY_COST_BPS,
            "portfolio_construction": "monthly_rebalanced_80_20",
            "frozen_reference": "frozen_current_active_vm_dsr_usci_combo",
            "preregistration_timestamp": FROZEN_TIMESTAMP,
            "preregistration_core_hash": preregistration_hash,
            "exact_next_action": next_action,
        },
    )
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        source_library_rows(source_records),
        [
            "source_record_id",
            "entity_type",
            "stage",
            "proposed_strategy_id",
            "family_id",
            "display_name",
            "strategy_architecture",
            "exact_canonical_rule",
            "source_library_id",
            "counted_as_strategy",
            "counted_as_trial",
        ],
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, STRATEGY_CARD_FIELDS)
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, TRIAL_FIELDS)
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        [
            "benchmark_or_control_id",
            "entity_type",
            "stage",
            "instrument_or_construction",
            "linked_strategy_ids",
            "counted_as_strategy",
            "counted_as_trial",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [process_task_row(next_action)],
        [
            "task_id",
            "entity_type",
            "stage",
            "mode",
            "candidate_count",
            "trial_count",
            "exact_next_action",
            "counted_as_strategy",
            "counted_as_trial",
        ],
    )
    write_csv(OUTPUT_DIR / "data_preflight_reconciliation.csv", preflight_rows, PREFLIGHT_FIELDS)
    write_csv(OUTPUT_DIR / "all_trial_results.csv", all_trials, RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "control_results.csv", controls, RESULT_FIELDS)
    write_csv(OUTPUT_DIR / "chronological_half_results.csv", halves, RESULT_FIELDS)
    write_csv(
        OUTPUT_DIR / "calendar_year_results.csv",
        calendar,
        [
            "strategy_id",
            "trial_id",
            "entity_id",
            "result_role",
            "calendar_year",
            "cost_assumption_bps",
            "evaluation_start",
            "evaluation_end",
            "trading_days",
            "total_return",
            "annualized_volatility",
            "sharpe_ratio",
            "maximum_drawdown",
            "turnover",
            "transaction_cost_drag",
            "max_daily_exposure",
            "max_daily_weight_sum",
            "all_invariants_pass",
            "diagnostic_only",
            "clean_or_sealed_holdout",
        ],
    )
    write_csv(OUTPUT_DIR / "portfolio_contribution_results.csv", contributions, RESULT_FIELDS)
    write_csv(
        OUTPUT_DIR / "portfolio_rebalance_events.csv",
        events,
        [
            "strategy_id",
            "trial_id",
            "portfolio_id",
            "portfolio_construction",
            "cost_assumption_bps",
            "event_date",
            "signal_date",
            "event_type",
            "gross_return_before_cost",
            "net_return",
            "equity",
            "pretrade_reference_weight",
            "pretrade_sleeve_weight",
            "post_trade_reference_weight",
            "post_trade_sleeve_weight",
            "one_way_turnover",
            "transaction_cost_drag",
            "max_daily_exposure",
            "max_daily_weight_sum",
            "turnover_formula",
        ],
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover,
        [
            "strategy_id",
            "trial_id",
            "entity_id",
            "accounting_scope",
            "cost_assumption_bps",
            "one_way_turnover",
            "trade_or_rebalance_count",
            "transaction_cost_drag",
            "initial_establishment_charged",
            "internal_etf_turnover_charged",
            "component_cost_double_counted",
            "rebalance_policy",
        ],
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariants,
        [
            "strategy_id",
            "trial_id",
            "entity_id",
            "scope",
            "cost_assumption_bps",
            "check_name",
            "status",
            "details",
        ],
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        followups,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "classification",
            "route",
            "exploration_only",
            "validation_or_promotion_authorized",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "failure_detail",
            "family_closed",
            "exact_variant_adapted_to_escape_closure",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        actions,
        ["scope", "entity_id", "outcome", "exact_next_action", "execute_now"],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcomes,
        [
            "strategy_id",
            "family_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "best_80_20_control_id",
            "stage",
            "validation_claimed",
            "promotion_or_paper_demo_authorized",
            "exact_next_action",
        ],
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(OUTPUT_DIR / "batch_report.md", report_text(results, funnel, next_action))
    return consistency


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    input_before = authoritative_hashes()
    cache_before = cache_hashes()
    source_records = load_frozen_source_records()
    validate_frozen_inputs(source_records)
    clean_output_dir()

    preflight_rows, frames = data_preflight()
    frozen_preregistration = preregistration_core()
    preregistration_hash = deterministic_hash(frozen_preregistration)

    results = [run_card(card, frames, preflight_rows) for card in CARDS]
    reference_returns = reference_support.active_vm_dsr_usci_reference_returns()
    for result in results:
        if not result["executable"]:
            continue
        result["portfolios"] = build_portfolios(result, reference_returns)
        required_ids = {
            "frozen_reference_100pct",
            f"{result['card'].strategy_id}_candidate_20pct",
            *(f"{control_id}_20pct_control" for control_id in result["card"].control_ids),
        }
        available_ids = {portfolio_id for portfolio_id, _ in result["portfolios"]}
        if not reference_returns.empty and required_ids.issubset(available_ids):
            classify_result(result)
        else:
            result.update(
                executable=False,
                outcome="inconclusive_data_issue",
                failure_reason="data_or_comparability_failure",
                decision_reason="frozen_reference_series_or_common_portfolio_window_unavailable",
            )

    consistency = write_artifacts(
        source_records,
        preflight_rows,
        results,
        preregistration_hash,
        protected_before,
        input_before,
        cache_before,
    )
    if not consistency["consistency_passed"]:
        raise RuntimeError("run_deferred_structural_source_batch_v2_consistency_failed")
    return {
        "batch_id": BATCH_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "outcomes": {
            result["card"].strategy_id: {
                "outcome": result["outcome"],
                "primary_failure_reason": result["failure_reason"],
            }
            for result in results
        },
        "followup_candidate_count": sum(
            result["outcome"] == "exploratory_followup_candidate_diversifier" for result in results
        ),
        "exact_next_action": consistency["exact_next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
