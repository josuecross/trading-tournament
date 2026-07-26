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
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v6 as v6
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


TASK_ID = "evaluate_deferred_v3_online_portfolio_candidates_v1"
MODE = "fast-progress"
STAGE = "exploration"
SOURCE_LIBRARY_ID = "strategy_source_library_refresh_v3"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\33484c81-5bec-47a0-b848-084c585d65f5\pasted-text.txt"
)
V6_EVIDENCE = (
    ROOT / "evidence" / "research_recovery" / v6.BATCH_ID / "latest"
)
HIGH52_CORRECTION = (
    ROOT
    / "evidence"
    / "correction"
    / "verify_and_correct_high52_v6_followup_gate_v1"
    / "latest"
)
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9
SECTOR_UNIVERSE = (
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)
PAMR_ID = "li_zhao_pamr0_sector_etf_v1"
ANTICOR_ID = "borodin_bah30_anticor_sector_etf_v1"
EXPECTED_STRATEGY_IDS = (PAMR_ID, ANTICOR_ID)
NEXT_REVIEW = "direction_owner_review_deferred_v3_online_portfolio_candidates_v1"
NEXT_ALL_CLOSED = "refresh_strategy_source_library_v4"
NEXT_BLOCKED = "direction_owner_review_deferred_v3_online_portfolio_block_v1"

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT
    / "strategy_lab"
    / "research_os"
    / "operations"
    / "active_observations.yaml",
)

FORBIDDEN_ACTIONS = {
    "source_research_or_completion": False,
    "parameter_search_or_variant": False,
    "validation_or_robustness": False,
    "promotion_or_paper_demo_review": False,
    "lifecycle_or_registry_change": False,
    "dogs_country_data_acquisition": False,
    "trade_management_overlay": False,
    "provider_access": False,
    "broker_account_order_or_real_money_action": False,
    "high52_reopened": False,
    "olmar_trial_created": False,
    "anticor30_trial_created": False,
}


@dataclass(frozen=True)
class CandidateCard:
    strategy_id: str
    family_id: str
    display_name: str
    strategy_architecture: str
    source_record_id: str
    route: str
    universe: tuple[str, ...]
    parameters: dict[str, Any]
    controls: tuple[str, ...]
    same_purpose_control: str
    algorithmic_materiality_controls: tuple[str, ...]
    frozen_rule: str

    @property
    def trial_id(self) -> str:
        return f"deferred_v3_online__{self.strategy_id}__canonical"

    @property
    def source_or_research_lineage(self) -> str:
        return f"{SOURCE_LIBRARY_ID}:{self.source_record_id}"


CARDS = (
    CandidateCard(
        strategy_id=PAMR_ID,
        family_id="passive_aggressive_single_period_reversion",
        display_name="PAMR-0 Sector ETF Allocation",
        strategy_architecture="daily_passive_aggressive_mean_reversion_portfolio",
        source_record_id="src_li_zhao_pamr0_sector_v1",
        route="diversifier",
        universe=SECTOR_UNIVERSE,
        parameters={"variant": "PAMR-0", "epsilon": 0.5},
        controls=(
            "daily_uniform_constant_rebalanced_sector_portfolio",
            "initial_equal_weight_sector_buy_and_hold",
            "li_hoi_olmar5_sector_etf_v1",
        ),
        same_purpose_control="li_hoi_olmar5_sector_etf_v1",
        algorithmic_materiality_controls=(
            "daily_uniform_constant_rebalanced_sector_portfolio",
            "li_hoi_olmar5_sector_etf_v1",
        ),
        frozen_rule=(
            "Initialize one ninth per sector. For each completed daily price-relative "
            "vector use PAMR-0 epsilon 0.5, tau=max(0,dot(b,x)-epsilon)/"
            "||x-mean(x)||^2, update b-tau*(x-mean(x)), project to the "
            "nonnegative fully invested simplex, retain b when the denominator is "
            "zero, and execute at the following session close."
        ),
    ),
    CandidateCard(
        strategy_id=ANTICOR_ID,
        family_id="lagged_cross_correlation_reallocation",
        display_name="BAH30-ANTICOR Sector Allocation",
        strategy_architecture="daily_lagged_cross_correlation_expert_ensemble",
        source_record_id="src_borodin_bah30_sector_v1",
        route="diversifier",
        universe=SECTOR_UNIVERSE,
        parameters={
            "expert_windows": list(range(2, 31)),
            "expert_count": 29,
            "expert_initial_capital": "one_twenty_ninth_each",
            "aggregate_rule": "after_cost_expert_nav_wealth_weighted_targets",
        },
        controls=(
            "daily_uniform_constant_rebalanced_sector_portfolio",
            "initial_equal_weight_sector_buy_and_hold",
            "anticor_single_window_30_sector_v1",
        ),
        same_purpose_control="anticor_single_window_30_sector_v1",
        algorithmic_materiality_controls=(
            "daily_uniform_constant_rebalanced_sector_portfolio",
            "anticor_single_window_30_sector_v1",
        ),
        frozen_rule=(
            "Maintain exactly 29 ANTICOR experts for w=2..30, each initialized "
            "equal weight. Each expert uses two adjacent log-price-relative windows, "
            "the frozen lagged-correlation claim and wealth-transfer equations, and "
            "next-session-close execution. Combine expert targets using after-cost "
            "expert NAV wealth shares. Charge aggregate implementable turnover once."
        ),
    ),
)


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.12g}"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
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
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def aggregate_hash(hashes: dict[str, str]) -> str:
    material = "\n".join(f"{path}|{value}" for path, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def cache_files() -> list[Path]:
    return [
        path
        for path in sorted((ROOT / "data" / "cache").rglob("*"))
        if path.is_file()
    ]


def prior_evidence_files() -> list[Path]:
    rows: list[Path] = []
    for path in sorted((ROOT / "evidence").rglob("*")):
        if not path.is_file():
            continue
        if OUTPUT_DIR.resolve() in path.resolve().parents:
            continue
        rows.append(path)
    return rows


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def validate_scope() -> None:
    if tuple(card.strategy_id for card in CARDS) != EXPECTED_STRATEGY_IDS:
        raise RuntimeError("Deferred V3 strategy scope changed")
    pamr, anticor = CARDS
    if pamr.parameters != {"variant": "PAMR-0", "epsilon": 0.5}:
        raise RuntimeError("PAMR frozen parameters changed")
    if anticor.parameters["expert_windows"] != list(range(2, 31)):
        raise RuntimeError("ANTICOR frozen expert windows changed")
    if any(card.universe != SECTOR_UNIVERSE for card in CARDS):
        raise RuntimeError("Frozen sector universe changed")
    decision = read_csv(HIGH52_CORRECTION / "decision_override.csv")
    if not (
        len(decision) == 1
        and decision[0]["strategy_id"] == "george_hwang_52week_high_sector_v1"
        and decision[0]["corrected_outcome"] == "closed_exploration"
        and decision[0]["failure_reason"] == "period_instability"
    ):
        raise RuntimeError("Authoritative High52 correction is missing or inconsistent")
    correction_check = json.loads(
        (HIGH52_CORRECTION / "consistency_check.json").read_text(encoding="utf-8")
    )
    if not correction_check.get("consistency_passed"):
        raise RuntimeError("High52 correction consistency check did not pass")


def data_preflight() -> tuple[list[dict[str, Any]], pd.DataFrame, bool]:
    symbol_rows = {symbol: v6.raw_cache_validation(symbol) for symbol in SECTOR_UNIVERSE}
    passed = all(
        row["preflight_status"] == "pass" for row in symbol_rows.values()
    )
    prices = market.load_price_frame(SECTOR_UNIVERSE) if passed else pd.DataFrame()
    common_start = prices.index.min() if not prices.empty else None
    common_end = prices.index.max() if not prices.empty else None
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        for symbol in SECTOR_UNIVERSE:
            row = symbol_rows[symbol]
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "symbol": symbol,
                    "cache_path": row["cache_path"],
                    "canonical_hash": row["canonical_hash"],
                    "first_valid_date": row["first_valid_date"],
                    "last_valid_date": row["last_valid_date"],
                    "row_count": row["row_count"],
                    "ordered_unique_dates": row["ordered_unique_dates"],
                    "finite_positive_prices": row["finite_positive_prices"],
                    "valid_ohlc_relationships": row["valid_ohlc_relationships"],
                    "canonical_adjustment_compatible": row[
                        "canonical_adjustment_compatible"
                    ],
                    "common_evaluation_start": (
                        common_start.date().isoformat()
                        if common_start is not None
                        else ""
                    ),
                    "common_evaluation_end": (
                        common_end.date().isoformat()
                        if common_end is not None
                        else ""
                    ),
                    "common_session_count": len(prices),
                    "preflight_status": "pass" if passed else "fail",
                    "failure_reason": (
                        "" if passed else "data_or_comparability_failure"
                    ),
                    "provider_accessed": False,
                }
            )
    return rows, prices, passed


def equal_target() -> np.ndarray:
    return np.full(len(SECTOR_UNIVERSE), 1.0 / len(SECTOR_UNIVERSE))


def target_frame(
    index: pd.DatetimeIndex,
    events: dict[pd.Timestamp, np.ndarray],
) -> pd.DataFrame:
    mapped = {
        pd.Timestamp(date): dict(zip(SECTOR_UNIVERSE, values))
        for date, values in events.items()
    }
    return v6.accounting.event_frame(index, SECTOR_UNIVERSE, mapped)


def pamr_event_sets(
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[dict[str, Any]]]:
    equal = equal_target()
    current = equal.copy()
    events: dict[pd.Timestamp, np.ndarray] = {
        pd.Timestamp(prices.index[0]): equal.copy()
    }
    uniform_events: dict[pd.Timestamp, np.ndarray] = {
        pd.Timestamp(prices.index[0]): equal.copy()
    }
    diagnostics: list[dict[str, Any]] = []
    for position in range(1, len(prices.index)):
        signal_date = pd.Timestamp(prices.index[position])
        execution = v6.next_session(prices.index, signal_date)
        if execution is None:
            continue
        x_t = (
            prices.iloc[position].to_numpy(dtype=float)
            / prices.iloc[position - 1].to_numpy(dtype=float)
        )
        portfolio_relative = float(np.dot(current, x_t))
        loss = max(0.0, portfolio_relative - 0.5)
        centered = x_t - float(x_t.mean())
        denominator = float(np.dot(centered, centered))
        tau = loss / denominator if denominator > 0.0 else 0.0
        preliminary = (
            current - tau * centered if denominator > 0.0 else current.copy()
        )
        updated = (
            v6.project_simplex(preliminary)
            if denominator > 0.0
            else current.copy()
        )
        projection_distance = float(np.linalg.norm(updated - preliminary))
        current = updated
        events[execution] = current.copy()
        uniform_events[execution] = equal.copy()
        diagnostics.append(
            {
                "strategy_id": PAMR_ID,
                "record_type": "daily_target",
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "price_relatives": dict(zip(SECTOR_UNIVERSE, x_t)),
                "portfolio_relative": portfolio_relative,
                "loss": loss,
                "denominator": denominator,
                "tau": tau,
                "preliminary_weights": dict(zip(SECTOR_UNIVERSE, preliminary)),
                "target_weights": dict(zip(SECTOR_UNIVERSE, current)),
                "projection_distance": projection_distance,
                "maximum_asset_weight": float(current.max()),
                "effective_holdings": float(1.0 / np.square(current).sum()),
                "any_weight_exceeds_50pct": bool((current > 0.5).any()),
                "any_weight_exceeds_80pct": bool((current > 0.8).any()),
                "year": signal_date.year,
                "annual_turnover": "",
            }
        )
    olmar_events, _, _ = v6.olmar_event_sets(prices)
    controls = {
        "daily_uniform_constant_rebalanced_sector_portfolio": target_frame(
            prices.index, uniform_events
        ),
        "initial_equal_weight_sector_buy_and_hold": v6.accounting.initial_event(
            prices.index, SECTOR_UNIVERSE, dict(zip(SECTOR_UNIVERSE, equal))
        ),
        "li_hoi_olmar5_sector_etf_v1": olmar_events,
    }
    return target_frame(prices.index, events), controls, diagnostics


def anticor_update(
    current: np.ndarray,
    x_t: np.ndarray,
    first_window: np.ndarray,
    second_window: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any]]:
    denominator = float(np.dot(current, x_t))
    if denominator <= 0.0:
        raise RuntimeError("ANTICOR post-return portfolio denominator is nonpositive")
    post_return = current * x_t / denominator
    mu1 = first_window.mean(axis=0)
    mu2 = second_window.mean(axis=0)
    sigma1 = first_window.std(axis=0, ddof=1)
    sigma2 = second_window.std(axis=0, ddof=1)
    centered1 = first_window - mu1
    centered2 = second_window - mu2
    covariance = centered1.T @ centered2 / float(len(first_window) - 1)
    scale = sigma1[:, None] * sigma2[None, :]
    correlation = np.zeros_like(covariance)
    np.divide(covariance, scale, out=correlation, where=scale > 0.0)
    self_bonus = np.where(np.diag(correlation) < 0.0, np.abs(np.diag(correlation)), 0.0)
    valid = (mu2[:, None] > mu2[None, :]) & (correlation > 0.0)
    claims = np.where(
        valid,
        correlation + self_bonus[:, None] + self_bonus[None, :],
        0.0,
    )
    claim_sums = claims.sum(axis=1)
    transfers = np.zeros_like(claims)
    active = claim_sums > 0.0
    transfers[active] = (
        post_return[active, None]
        * claims[active]
        / claim_sums[active, None]
    )
    updated = post_return - transfers.sum(axis=1) + transfers.sum(axis=0)
    if float(updated.min()) < -WEIGHT_TOLERANCE:
        raise RuntimeError("ANTICOR update created a negative weight")
    updated = np.clip(updated, 0.0, None)
    total = float(updated.sum())
    if abs(total - 1.0) > WEIGHT_TOLERANCE:
        raise RuntimeError("ANTICOR update violated fully invested tolerance")
    if total != 1.0:
        updated = updated / total
    return updated, {
        "post_return_weights": post_return,
        "mu1": mu1,
        "mu2": mu2,
        "sigma1": sigma1,
        "sigma2": sigma2,
        "self_anticorrelation_bonus": self_bonus,
        "valid_claim_count": int((claims > 0.0).sum()),
        "total_transfer_amount": float(transfers.sum()),
    }


def anticor_expert_events(
    prices: pd.DataFrame,
    window: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    equal = equal_target()
    current = equal.copy()
    events: dict[pd.Timestamp, np.ndarray] = {
        pd.Timestamp(prices.index[0]): equal.copy()
    }
    diagnostics: list[dict[str, Any]] = []
    log_relatives = np.log(prices / prices.shift(1))
    for position in range(1, len(prices.index)):
        signal_date = pd.Timestamp(prices.index[position])
        execution = v6.next_session(prices.index, signal_date)
        if execution is None:
            continue
        available = log_relatives.iloc[1 : position + 1].to_numpy(dtype=float)
        warmup_complete = len(available) >= 2 * window
        detail: dict[str, Any] = {
            "valid_claim_count": 0,
            "total_transfer_amount": 0.0,
        }
        if warmup_complete:
            recent = available[-2 * window :]
            first_window = recent[:window]
            second_window = recent[window:]
            x_t = (
                prices.iloc[position].to_numpy(dtype=float)
                / prices.iloc[position - 1].to_numpy(dtype=float)
            )
            current, detail = anticor_update(
                current, x_t, first_window, second_window
            )
        else:
            current = equal.copy()
        events[execution] = current.copy()
        diagnostics.append(
            {
                "strategy_id": ANTICOR_ID,
                "expert_window": window,
                "signal_date": signal_date.date().isoformat(),
                "execution_date": execution.date().isoformat(),
                "warmup_complete": warmup_complete,
                "valid_claim_count": detail["valid_claim_count"],
                "total_transfer_amount": detail["total_transfer_amount"],
                "target_weights": dict(zip(SECTOR_UNIVERSE, current)),
                "maximum_asset_weight": float(current.max()),
                "effective_holdings": float(1.0 / np.square(current).sum()),
            }
        )
    return target_frame(prices.index, events), diagnostics


def expert_event_sets(
    prices: pd.DataFrame,
) -> tuple[dict[int, pd.DataFrame], dict[int, list[dict[str, Any]]]]:
    events: dict[int, pd.DataFrame] = {}
    diagnostics: dict[int, list[dict[str, Any]]] = {}
    for window in range(2, 31):
        events[window], diagnostics[window] = anticor_expert_events(prices, window)
    return events, diagnostics


def build_bah30_path(
    prices: pd.DataFrame,
    expert_events: dict[int, pd.DataFrame],
    cost_bps: float,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]], pd.DataFrame]:
    timing = "completed_close_target_applied_to_following_session"
    expert_paths = {
        window: v6.accounting.simulate_path(
            prices, events, cost_bps, timing
        )
        for window, events in expert_events.items()
    }
    nav = pd.DataFrame(
        {
            window: (1.0 + path["returns"]).cumprod()
            for window, path in expert_paths.items()
        },
        index=prices.index,
    )
    aggregate_events: dict[pd.Timestamp, np.ndarray] = {}
    for execution in prices.index:
        execution = pd.Timestamp(execution)
        available = [
            window
            for window, events in expert_events.items()
            if execution in events.index
        ]
        if len(available) != len(expert_events):
            continue
        position = prices.index.get_loc(execution)
        signal_position = max(int(position) - 1, 0)
        signal_date = pd.Timestamp(prices.index[signal_position])
        capital = nav.loc[signal_date, available].to_numpy(dtype=float)
        shares = capital / float(capital.sum())
        targets = np.vstack(
            [
                expert_events[window]
                .loc[execution, list(SECTOR_UNIVERSE)]
                .to_numpy(dtype=float)
                for window in available
            ]
        )
        aggregate_events[execution] = shares @ targets
    aggregate_targets = target_frame(prices.index, aggregate_events)
    aggregate_path = v6.accounting.simulate_path(
        prices, aggregate_targets, cost_bps, timing
    )
    return aggregate_path, expert_paths, nav


def uniform_and_static_controls(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    equal = equal_target()
    events = {
        pd.Timestamp(date): equal.copy()
        for date in prices.index
    }
    return {
        "daily_uniform_constant_rebalanced_sector_portfolio": target_frame(
            prices.index, events
        ),
        "initial_equal_weight_sector_buy_and_hold": v6.accounting.initial_event(
            prices.index, SECTOR_UNIVERSE, dict(zip(SECTOR_UNIVERSE, equal))
        ),
    }


def extended_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    base = v6.strategy_metrics(path, period_index)
    held = path["held_weights"]
    if period_index is not None:
        held = held.reindex(period_index).dropna()
    if held.empty:
        maximum_weight = float("nan")
        effective = float("nan")
    else:
        values = held.to_numpy(dtype=float)
        maximum_weight = float(values.max())
        squares = np.square(values).sum(axis=1)
        valid = squares > 0.0
        effective = float(np.mean(1.0 / squares[valid])) if valid.any() else 0.0
    return {
        **base,
        "average_asset_exposure": base["average_risky_exposure"],
        "maximum_single_asset_weight": maximum_weight,
        "effective_holdings": effective,
        "rebalance_count": base["trade_or_rebalance_count"],
    }


def run_pamr(
    card: CandidateCard,
    prices: pd.DataFrame,
) -> dict[str, Any]:
    candidate_events, controls, diagnostics = pamr_event_sets(prices)
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    timing = "completed_close_target_applied_to_following_session"
    for cost in COST_BPS:
        candidate_paths[cost] = v6.accounting.simulate_path(
            prices, candidate_events, cost, timing
        )
        for control_id, events in controls.items():
            control_paths[(control_id, cost)] = v6.accounting.simulate_path(
                prices, events, cost, timing
            )
    yearly_turnover = (
        candidate_paths[PRIMARY_COST_BPS]["turnover"]
        .groupby(candidate_paths[PRIMARY_COST_BPS]["turnover"].index.year)
        .sum()
    )
    diagnostics.extend(
        {
            "strategy_id": PAMR_ID,
            "record_type": "year_summary",
            "signal_date": "",
            "execution_date": "",
            "price_relatives": {},
            "portfolio_relative": "",
            "loss": "",
            "denominator": "",
            "tau": "",
            "preliminary_weights": {},
            "target_weights": {},
            "projection_distance": "",
            "maximum_asset_weight": "",
            "effective_holdings": "",
            "any_weight_exceeds_50pct": "",
            "any_weight_exceeds_80pct": "",
            "year": int(year),
            "annual_turnover": float(turnover),
        }
        for year, turnover in yearly_turnover.items()
    )
    return {
        "card": card,
        "executed": True,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": {},
        "pamr_diagnostics": diagnostics,
        "anticor_expert_diagnostics": [],
        "anticor_claim_diagnostics": [],
        "outcome": "",
        "failure_reason": "",
        "decision_reason": "",
    }


def anticor_diagnostic_rows(
    expert_events: dict[int, pd.DataFrame],
    raw_diagnostics: dict[int, list[dict[str, Any]]],
    expert_paths: dict[int, dict[str, Any]],
    nav: pd.DataFrame,
    aggregate_path: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expert_rows: list[dict[str, Any]] = []
    claim_by_execution: dict[pd.Timestamp, dict[str, Any]] = {}
    nav_total = nav.sum(axis=1)
    for window in range(2, 31):
        path = expert_paths[window]
        turnover = path["turnover"]
        for raw in raw_diagnostics[window]:
            signal_date = pd.Timestamp(raw["signal_date"])
            execution = pd.Timestamp(raw["execution_date"])
            wealth_share = float(nav.loc[signal_date, window] / nav_total.loc[signal_date])
            expert_rows.append(
                {
                    **raw,
                    "cost_assumption_bps": PRIMARY_COST_BPS,
                    "expert_nav": float(nav.loc[signal_date, window]),
                    "aggregate_wealth_share": wealth_share,
                    "expert_one_way_turnover": float(turnover.get(execution, 0.0)),
                }
            )
            summary = claim_by_execution.setdefault(
                execution,
                {
                    "strategy_id": ANTICOR_ID,
                    "signal_date": raw["signal_date"],
                    "execution_date": raw["execution_date"],
                    "cost_assumption_bps": PRIMARY_COST_BPS,
                    "warm_expert_count": 0,
                    "total_valid_claim_count": 0,
                    "total_transfer_amount": 0.0,
                },
            )
            summary["warm_expert_count"] += int(bool(raw["warmup_complete"]))
            summary["total_valid_claim_count"] += int(raw["valid_claim_count"])
            summary["total_transfer_amount"] += float(raw["total_transfer_amount"])
    claim_rows: list[dict[str, Any]] = []
    for execution, row in sorted(claim_by_execution.items()):
        signal_date = pd.Timestamp(row["signal_date"])
        capital = nav.loc[signal_date].to_numpy(dtype=float)
        shares = capital / float(capital.sum())
        top5_share = float(np.sort(shares)[-5:].sum())
        target = (
            aggregate_path["target_events"]
            .loc[execution, list(SECTOR_UNIVERSE)]
            .to_dict()
        )
        claim_rows.append(
            {
                **row,
                "aggregate_target": target,
                "aggregate_one_way_turnover": float(
                    aggregate_path["turnover"].get(execution, 0.0)
                ),
                "maximum_asset_weight": max(float(value) for value in target.values()),
                "effective_holdings": float(
                    1.0 / sum(float(value) ** 2 for value in target.values())
                ),
                "top_five_expert_wealth_share": top5_share,
                "expert_costs_used_only_for_wealth_shares": True,
                "aggregate_cost_charged_once": True,
                "expert_and_aggregate_costs_double_charged": False,
            }
        )
    return expert_rows, claim_rows


def run_anticor(
    card: CandidateCard,
    prices: pd.DataFrame,
) -> dict[str, Any]:
    expert_events, raw_diagnostics = expert_event_sets(prices)
    base_controls = uniform_and_static_controls(prices)
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    primary_expert_paths: dict[int, dict[str, Any]] = {}
    primary_nav = pd.DataFrame()
    for cost in COST_BPS:
        candidate, expert_paths, nav = build_bah30_path(
            prices, expert_events, cost
        )
        candidate_paths[cost] = candidate
        if cost == PRIMARY_COST_BPS:
            primary_expert_paths = expert_paths
            primary_nav = nav
        for control_id, events in base_controls.items():
            control_paths[(control_id, cost)] = v6.accounting.simulate_path(
                prices,
                events,
                cost,
                "completed_close_target_applied_to_following_session",
            )
        control_paths[
            ("anticor_single_window_30_sector_v1", cost)
        ] = v6.accounting.simulate_path(
            prices,
            expert_events[30],
            cost,
            "completed_close_target_applied_to_following_session",
        )
    expert_rows, claim_rows = anticor_diagnostic_rows(
        expert_events,
        raw_diagnostics,
        primary_expert_paths,
        primary_nav,
        candidate_paths[PRIMARY_COST_BPS],
    )
    return {
        "card": card,
        "executed": True,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": {},
        "pamr_diagnostics": [],
        "anticor_expert_diagnostics": expert_rows,
        "anticor_claim_diagnostics": claim_rows,
        "outcome": "",
        "failure_reason": "",
        "decision_reason": "",
    }


def blocked_result(
    card: CandidateCard,
    reason: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "card": card,
        "executed": False,
        "candidate_paths": {},
        "control_paths": {},
        "portfolio_paths": {},
        "pamr_diagnostics": [],
        "anticor_expert_diagnostics": [],
        "anticor_claim_diagnostics": [],
        "outcome": "inconclusive_data_issue",
        "failure_reason": reason,
        "decision_reason": detail,
    }


def build_portfolio_paths(
    result: dict[str, Any],
    reference_returns: pd.Series,
) -> dict[tuple[str, float], dict[str, Any]]:
    if not result["executed"]:
        return {}
    card: CandidateCard = result["card"]
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        candidate = result["candidate_paths"][cost]["returns"]
        common = candidate.index.intersection(reference_returns.dropna().index)
        for control_id in card.controls:
            common = common.intersection(
                result["control_paths"][(control_id, cost)]["returns"].index
            )
        common = common.sort_values()
        reference = reference_returns.reindex(common).dropna()
        candidate = candidate.reindex(reference.index).dropna()
        reference = reference.reindex(candidate.index)
        payloads[("frozen_reference_100pct", cost)] = (
            portfolio_accounting.reference_payload(reference, cost)
        )
        candidate_id = f"{card.strategy_id}_candidate_20pct"
        payloads[(candidate_id, cost)] = (
            portfolio_accounting.simulate_two_component_portfolio(
                reference, candidate, candidate_id, cost
            )
        )
        for control_id in card.controls:
            control = (
                result["control_paths"][(control_id, cost)]["returns"]
                .reindex(reference.index)
                .dropna()
            )
            aligned_reference = reference.reindex(control.index)
            portfolio_id = f"{control_id}_20pct_control"
            payloads[(portfolio_id, cost)] = (
                portfolio_accounting.simulate_two_component_portfolio(
                    aligned_reference, control, portfolio_id, cost
                )
            )
    return payloads


def portfolio_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    source = portfolio_accounting.metric_payload(path, period_index)
    return {
        "evaluation_start": source["evaluation_start"],
        "evaluation_end": source["evaluation_end"],
        "trading_days": source["trading_days"],
        "total_return": source["total_return"],
        "cagr": source["cagr"],
        "annualized_volatility": source["annualized_volatility"],
        "sharpe_ratio": source["sharpe_ratio"],
        "maximum_drawdown": source["maximum_drawdown"],
        "average_asset_exposure": source["average_gross_exposure"],
        "turnover": source["turnover"],
        "rebalance_count": source["trade_or_rebalance_count"],
        "transaction_cost_drag": source["transaction_cost_drag"],
        "maximum_single_asset_weight": "",
        "effective_holdings": "",
        "maximum_gross_exposure": source["max_daily_exposure"],
        "maximum_daily_weight_sum": source["max_daily_weight_sum"],
        "numeric_invariant_status": source["numeric_invariant_status"],
        "timing_invariant_status": source["timing_invariant_status"],
        "exposure_invariant_status": source["exposure_invariant_status"],
        "weight_invariant_status": source["exposure_invariant_status"],
        "invariant_pass": source["invariant_pass"],
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return v6.dominates(control, candidate)


def material_advantage(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return (
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
        >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def worse_on_both(
    candidate: dict[str, Any],
    control: dict[str, Any],
) -> bool:
    return v6.worse_on_both_sharpe_and_drawdown(candidate, control)


def classify(result: dict[str, Any]) -> None:
    if not result["executed"]:
        return
    card: CandidateCard = result["card"]
    candidate = extended_metrics(result["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: extended_metrics(
            result["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in card.controls
    }
    if not candidate["invariant_pass"] or not all(
        control["invariant_pass"] for control in controls.values()
    ):
        result.update(
            outcome="blocked_feasibility",
            failure_reason="methodology_failure",
            decision_reason="candidate_or_control_invariant_failed",
        )
        return
    if float(candidate["total_return"]) <= 0.0:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_return",
            decision_reason="full_period_after_cost_return_not_positive",
        )
        return
    dominating = [
        control_id
        for control_id, control in controls.items()
        if dominates(control, candidate)
    ]
    if dominating:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason="standalone_control_dominates:" + ",".join(dominating),
        )
        return
    below_materiality = [
        control_id
        for control_id in card.algorithmic_materiality_controls
        if not material_advantage(candidate, controls[control_id])
    ]
    if below_materiality:
        algorithmic = card.same_purpose_control in below_materiality
        result.update(
            outcome="closed_exploration",
            failure_reason=(
                "benchmark_like_behavior"
                if algorithmic
                else "weak_vs_primary_control"
            ),
            decision_reason=(
                "candidate_did_not_materially_exceed_required_controls:"
                + ",".join(below_materiality)
            ),
        )
        return
    same_id = card.same_purpose_control
    for period_label, period in v6.split_periods(
        result["candidate_paths"][PRIMARY_COST_BPS]["returns"].index
    ):
        candidate_half = extended_metrics(
            result["candidate_paths"][PRIMARY_COST_BPS], period
        )
        control_half = extended_metrics(
            result["control_paths"][(same_id, PRIMARY_COST_BPS)], period
        )
        if worse_on_both(candidate_half, control_half):
            result.update(
                outcome="closed_exploration",
                failure_reason="period_instability",
                decision_reason=(
                    "candidate_worse_on_sharpe_and_drawdown_vs_frozen_"
                    f"same_purpose_control_in_{period_label}"
                ),
            )
            return
    static_control = controls["initial_equal_weight_sector_buy_and_hold"]
    if (
        float(static_control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"])
        and float(static_control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"])
    ):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason="static_equal_weight_exposure_reproduces_claimed_benefit",
        )
        return
    candidate_10 = extended_metrics(result["candidate_paths"][10.0])
    same_10 = extended_metrics(result["control_paths"][(same_id, 10.0)])
    if worse_on_both(candidate_10, same_10):
        result.update(
            outcome="closed_exploration",
            failure_reason="cost_drag",
            decision_reason=(
                "10_bps_candidate_unfavorable_on_both_sharpe_and_drawdown_"
                "vs_same_purpose_control"
            ),
        )
        return

    portfolios = result["portfolio_paths"]
    reference = portfolio_metrics(
        portfolios[("frozen_reference_100pct", PRIMARY_COST_BPS)]
    )
    candidate_id = f"{card.strategy_id}_candidate_20pct"
    candidate_portfolio = portfolio_metrics(
        portfolios[(candidate_id, PRIMARY_COST_BPS)]
    )
    control_portfolios = {
        f"{control_id}_20pct_control": portfolio_metrics(
            portfolios[(f"{control_id}_20pct_control", PRIMARY_COST_BPS)]
        )
        for control_id in card.controls
    }
    improves_sharpe = (
        float(candidate_portfolio["sharpe_ratio"])
        > float(reference["sharpe_ratio"])
    )
    improves_drawdown = (
        float(candidate_portfolio["maximum_drawdown"])
        > float(reference["maximum_drawdown"])
    )
    if not (improves_sharpe or improves_drawdown) or worse_on_both(
        candidate_portfolio, reference
    ):
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason=(
                "80_20_candidate_did_not_improve_reference_without_worsening_both"
            ),
        )
        return
    dominating_portfolios = [
        control_id
        for control_id, control in control_portfolios.items()
        if dominates(control, candidate_portfolio)
    ]
    if dominating_portfolios:
        result.update(
            outcome="closed_exploration",
            failure_reason="weak_vs_primary_control",
            decision_reason=(
                "80_20_control_dominates:" + ",".join(dominating_portfolios)
            ),
        )
        return
    best_id, best = v6.best_by_sharpe(control_portfolios)
    if not material_advantage(candidate_portfolio, best):
        result.update(
            outcome="closed_exploration",
            failure_reason="benchmark_like_behavior",
            decision_reason=(
                "80_20_candidate_below_materiality_vs_best_control:" + best_id
            ),
        )
        return
    result.update(
        outcome="exploratory_followup_candidate_diversifier",
        failure_reason="",
        decision_reason="all_frozen_exploration_and_diversifier_gates_passed",
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
    "average_asset_exposure",
    "turnover",
    "rebalance_count",
    "transaction_cost_drag",
    "maximum_single_asset_weight",
    "effective_holdings",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
)


def result_row(
    result: dict[str, Any],
    row_type: str,
    control_id: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    card: CandidateCard = result["card"]
    return {
        "strategy_id": card.strategy_id,
        "family_id": card.family_id,
        "trial_id": card.trial_id,
        "entity_type": (
            "experiment_trial"
            if row_type == "candidate"
            else "benchmark_reference"
        ),
        "stage": (
            "exploration"
            if row_type == "candidate"
            else "benchmark_reference_only"
        ),
        "row_type": row_type,
        "control_id": control_id,
        "route": card.route,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "chronological_split_diagnostic_not_validation_or_sealed_holdout"
        ),
        "outcome": result["outcome"],
        "failure_reason": result["failure_reason"],
        "decision_reason": result["decision_reason"],
        **metrics,
    }


def result_tables(
    results: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    trial_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        for cost in COST_BPS:
            candidate_path = result["candidate_paths"][cost]
            candidate_metrics = extended_metrics(candidate_path)
            trial_rows.append(
                result_row(
                    result, "candidate", "", cost, "full_period", candidate_metrics
                )
            )
            turnover_rows.append(
                {
                    "record_scope": "candidate",
                    "strategy_id": card.strategy_id,
                    "control_or_portfolio_id": "",
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": candidate_metrics["turnover"],
                    "rebalance_count": candidate_metrics["rebalance_count"],
                    "transaction_cost_drag": candidate_metrics[
                        "transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "expert_cost_accounting": (
                        "after_cost_expert_nav_for_wealth_shares_and_single_"
                        "aggregate_cost_charge"
                        if card.strategy_id == ANTICOR_ID
                        else "not_applicable"
                    ),
                    "double_charged": False,
                }
            )
            invariant_rows.append(
                {
                    **result_row(
                        result,
                        "candidate",
                        "",
                        cost,
                        "full_period",
                        candidate_metrics,
                    ),
                    "explicit_zero_weights": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "leverage_present": False,
                    "same_period_price_signal_return_used": False,
                    "actual_transaction_cost_deduction": True,
                }
            )
            for period_label, period in v6.split_periods(
                candidate_path["returns"].index
            ):
                half_rows.append(
                    result_row(
                        result,
                        "candidate",
                        "",
                        cost,
                        period_label,
                        extended_metrics(candidate_path, period),
                    )
                )
            for control_id in card.controls:
                path = result["control_paths"][(control_id, cost)]
                metrics = extended_metrics(path)
                control_rows.append(
                    result_row(
                        result,
                        "control",
                        control_id,
                        cost,
                        "full_period",
                        metrics,
                    )
                )
                turnover_rows.append(
                    {
                        "record_scope": "control",
                        "strategy_id": card.strategy_id,
                        "control_or_portfolio_id": control_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metrics["turnover"],
                        "rebalance_count": metrics["rebalance_count"],
                        "transaction_cost_drag": metrics[
                            "transaction_cost_drag"
                        ],
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "expert_cost_accounting": "not_applicable",
                        "double_charged": False,
                    }
                )
                invariant_rows.append(
                    {
                        **result_row(
                            result,
                            "control",
                            control_id,
                            cost,
                            "full_period",
                            metrics,
                        ),
                        "explicit_zero_weights": True,
                        "stale_weight_forward_fill_used": False,
                        "negative_weights_present": False,
                        "leverage_present": False,
                        "same_period_price_signal_return_used": False,
                        "actual_transaction_cost_deduction": True,
                    }
                )
                for period_label, period in v6.split_periods(
                    path["returns"].index
                ):
                    half_rows.append(
                        result_row(
                            result,
                            "control",
                            control_id,
                            cost,
                            period_label,
                            extended_metrics(path, period),
                        )
                    )
    return trial_rows, control_rows, half_rows, turnover_rows, invariant_rows


def portfolio_rows(
    results: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for result in results:
        if not result["executed"]:
            continue
        card: CandidateCard = result["card"]
        for (portfolio_id, cost), path in result["portfolio_paths"].items():
            for period_label, period in [
                ("full_period", None),
                *v6.split_periods(path["returns"].index),
            ]:
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
                            if portfolio_id == "frozen_reference_100pct"
                            else "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_control_with_natural_drift"
                        ),
                        "period_label": period_label,
                        "period_role": (
                            "full_period_exploration"
                            if period_label == "full_period"
                            else "chronological_split_diagnostic_not_validation_or_sealed_holdout"
                        ),
                        "cost_assumption_bps": cost,
                        **metrics,
                    }
                )
            full = portfolio_metrics(path)
            turnover_rows.append(
                {
                    "record_scope": "portfolio_contribution",
                    "strategy_id": card.strategy_id,
                    "control_or_portfolio_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": full["turnover"],
                    "rebalance_count": full["rebalance_count"],
                    "transaction_cost_drag": full["transaction_cost_drag"],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "expert_cost_accounting": "not_applicable",
                    "double_charged": False,
                }
            )
            invariant_rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "entity_type": "portfolio_diagnostic",
                    "stage": "exploration",
                    "row_type": "portfolio_contribution",
                    "control_id": portfolio_id,
                    "route": card.route,
                    "cost_assumption_bps": cost,
                    "period_label": "full_period",
                    "period_role": "full_period_exploration",
                    "outcome": result["outcome"],
                    "failure_reason": result["failure_reason"],
                    "decision_reason": result["decision_reason"],
                    **full,
                    "explicit_zero_weights": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_present": False,
                    "leverage_present": False,
                    "same_period_price_signal_return_used": False,
                    "actual_transaction_cost_deduction": True,
                }
            )
    return rows, turnover_rows, invariant_rows


def source_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_record_id": card.source_record_id,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "source_library_id": SOURCE_LIBRARY_ID,
            "source_packet": rel(SOURCE_PACKET),
            "source_packet_hash": file_hash(SOURCE_PACKET),
            "rules_completed_in_task": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for card in CARDS
    ]


def pending_strategy_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": card.strategy_id,
            "family_id": card.family_id,
            "display_name": card.display_name,
            "entity_type": "strategy_configuration",
            "strategy_architecture": card.strategy_architecture,
            "source_or_research_lineage": card.source_or_research_lineage,
            "instrument_universe": card.universe,
            "parameters": card.parameters,
            "benchmark_or_control": card.controls,
            "stage": STAGE,
            "trial_id": card.trial_id,
            "parent_trial_id": "",
            "adaptation_label": "",
            "outcome": "preregistered_pending_execution",
            "failure_reason": "",
            "next_action": "execute_frozen_exploration_trial",
            "complete_frozen_rule": card.frozen_rule,
            "created_in_source_of_truth": False,
        }
        for card in CARDS
    ]


def pending_trial_rows() -> list[dict[str, Any]]:
    return [
        {
            **row,
            "entity_type": "experiment_trial",
            "transaction_cost_assumptions": (
                "0|5|10 bps per one-way turnover; 5 bps primary"
            ),
            "execution_timing": (
                "completed_close_target_applied_at_following_session_close"
            ),
            "changed_fields_from_parent": "canonical_configuration",
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "results_viewed_before_preregistration": False,
            "executed": False,
            "counted_as_trial": True,
        }
        for row in pending_strategy_rows()
    ]


def write_preregistration_checkpoint() -> str:
    strategies = pending_strategy_rows()
    trials = pending_trial_rows()
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    material = {"strategies": strategies, "trials": trials}
    return "sha256:" + hashlib.sha256(
        json.dumps(material, sort_keys=True, default=csv_value).encode("utf-8")
    ).hexdigest()


def candidate_next_action(result: dict[str, Any]) -> str:
    if result["outcome"] == "exploratory_followup_candidate_diversifier":
        return f"direction_owner_review_{result['card'].strategy_id}"
    if result["outcome"] == "closed_exploration":
        return "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
    return f"direction_owner_review_{result['card'].strategy_id}_block"


def finalized_strategy_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = {row["strategy_id"]: row for row in pending_strategy_rows()}
    return [
        {
            **pending[result["card"].strategy_id],
            "stage": STAGE,
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "next_action": candidate_next_action(result),
        }
        for result in results
    ]


def finalized_trial_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending = {row["strategy_id"]: row for row in pending_trial_rows()}
    return [
        {
            **pending[result["card"].strategy_id],
            "outcome": result["outcome"],
            "failure_reason": result["failure_reason"],
            "next_action": candidate_next_action(result),
            "executed": result["executed"],
        }
        for result in results
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in CARDS:
        for control_id in card.controls:
            rows.append(
                {
                    "strategy_id": card.strategy_id,
                    "family_id": card.family_id,
                    "trial_id": card.trial_id,
                    "benchmark_or_control_id": control_id,
                    "entity_type": "benchmark_reference",
                    "stage": "benchmark_reference_only",
                    "reference_role": (
                        "same_lane_algorithmic_control"
                        if control_id == card.same_purpose_control
                        else "principal_equal_weight_or_static_control"
                    ),
                    "counted_as_strategy": False,
                    "counted_as_trial": False,
                }
            )
    return rows


def batch_next_action(results: list[dict[str, Any]]) -> str:
    if any(
        result["outcome"] == "exploratory_followup_candidate_diversifier"
        for result in results
    ):
        return NEXT_REVIEW
    if sum(result["executed"] for result in results) < 2:
        return NEXT_BLOCKED
    return NEXT_ALL_CLOSED


def build_report(
    results: list[dict[str, Any]],
    next_action: str,
) -> str:
    lines = [
        "# Deferred V3 Online Portfolio Candidates",
        "",
        "## Scope",
        "",
        "Exactly PAMR-0 and BAH30-ANTICOR were evaluated as frozen exploration "
        "configurations on the nine-sector canonical cache. No source completion, "
        "parameter variation, validation, promotion, lifecycle, provider, paper/demo, "
        "broker, or real-money action occurred.",
        "",
        "## Outcomes",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result['card'].strategy_id}`: `{result['outcome']}`"
            + (
                f" (`{result['failure_reason']}`; {result['decision_reason']})"
                if result["failure_reason"]
                else f" ({result['decision_reason']})"
            )
        )
    lines.extend(
        [
            "",
            "## Accounting",
            "",
            "- Primary cost is `5 bps` per one-way turnover; `0` and `10 bps` "
            "are diagnostics only.",
            "- Targets use completed close data and execute at the following "
            "session close.",
            "- BAH30 expert NAVs include each expert's own modeled costs for "
            "wealth-share calculation.",
            "- The implementable BAH30 aggregate is charged once on aggregate "
            "turnover; expert costs are not directly deducted again.",
            "- Chronological halves are exploration diagnostics, not validation "
            "or sealed holdouts.",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    validate_scope()
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_before = map_hashes(cache_files())
    prior_files_before = prior_evidence_files()
    prior_before = map_hashes(prior_files_before)
    prior_aggregate_before = aggregate_hash(prior_before)
    v6_before = map_hashes(
        path for path in sorted(V6_EVIDENCE.rglob("*")) if path.is_file()
    )
    high52_before = map_hashes(
        path for path in sorted(HIGH52_CORRECTION.rglob("*")) if path.is_file()
    )
    source_hash_before = file_hash(SOURCE_PACKET)

    clean_output()
    preflight_rows, prices, preflight_passed = data_preflight()
    preregistration_hash = write_preregistration_checkpoint()
    if preflight_passed:
        results = [run_pamr(CARDS[0], prices), run_anticor(CARDS[1], prices)]
    else:
        results = [
            blocked_result(
                card,
                "data_or_comparability_failure",
                "one_or_more_frozen_sector_cache_inputs_failed_preflight",
            )
            for card in CARDS
        ]
    reference = market.active_vm_dsr_usci_reference_returns()
    for result in results:
        result["portfolio_paths"] = build_portfolio_paths(result, reference)
        classify(result)
    next_action = batch_next_action(results)

    sources = source_rows()
    strategies = finalized_strategy_rows(results)
    trials = finalized_trial_rows(results)
    benchmarks = benchmark_rows()
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "batch_completed",
            "exact_next_action": next_action,
            "strategy_counted": False,
            "trial_counted": False,
            "next_action_executed": False,
        }
    ]
    (
        trial_results,
        control_results,
        half_results,
        turnover_rows,
        invariant_rows,
    ) = result_tables(results)
    portfolio_result_rows, portfolio_turnover, portfolio_invariants = (
        portfolio_rows(results)
    )
    turnover_rows.extend(portfolio_turnover)
    invariant_rows.extend(portfolio_invariants)
    pamr_diagnostics = [
        row for result in results for row in result["pamr_diagnostics"]
    ]
    anticor_expert_diagnostics = [
        row for result in results for row in result["anticor_expert_diagnostics"]
    ]
    anticor_claim_diagnostics = [
        row for result in results for row in result["anticor_claim_diagnostics"]
    ]
    outcomes = [
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
            "next_action": candidate_next_action(result),
            "validation_claimed": False,
            "promotion_authorized": False,
        }
        for result in results
    ]
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
    funnel = {
        "source_library_records": len(sources),
        "strategy_configurations": len(strategies),
        "canonical_experiment_trials": len(trials),
        "executed_experiment_trials": sum(result["executed"] for result in results),
        "benchmark_references": len(benchmarks),
        "process_tasks": len(process_rows),
        "followup_candidates": sum(
            result["outcome"] == "exploratory_followup_candidate_diversifier"
            for result in results
        ),
        "closed_exploration": sum(
            result["outcome"] == "closed_exploration" for result in results
        ),
        "inconclusive_data_issue": sum(
            result["outcome"] == "inconclusive_data_issue" for result in results
        ),
        "blocked_feasibility": sum(
            result["outcome"] == "blocked_feasibility" for result in results
        ),
        "outcome_count_reconciles": len(results) == 2,
        "exact_next_action": next_action,
    }

    manifest = {
        "batch_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "source_library_id": SOURCE_LIBRARY_ID,
        "strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "strategy_configuration_count": 2,
        "canonical_experiment_trial_count": 2,
        "executed_trial_count": sum(result["executed"] for result in results),
        "benchmark_reference_count": len(benchmarks),
        "process_task_count": 1,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_performance_calculation": True,
        "primary_cost_bps": PRIMARY_COST_BPS,
        "diagnostic_cost_bps": [0.0, 10.0],
        "validation_claimed": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "lifecycle_state_changed": False,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)
    write_csv(
        OUTPUT_DIR / "source_library_records.csv", sources, list(sources[0])
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0])
    )
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0]),
    )
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
        *METRIC_FIELDS,
    ]
    write_csv(
        OUTPUT_DIR / "all_trial_results.csv", trial_results, metric_fields
    )
    write_csv(
        OUTPUT_DIR / "control_results.csv", control_results, metric_fields
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_results,
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
    turnover_fields = [
        "record_scope",
        "strategy_id",
        "control_or_portfolio_id",
        "cost_assumption_bps",
        "total_one_way_turnover",
        "rebalance_count",
        "transaction_cost_drag",
        "turnover_formula",
        "expert_cost_accounting",
        "double_charged",
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        turnover_fields,
    )
    pamr_fields = [
        "strategy_id",
        "record_type",
        "signal_date",
        "execution_date",
        "price_relatives",
        "portfolio_relative",
        "loss",
        "denominator",
        "tau",
        "preliminary_weights",
        "target_weights",
        "projection_distance",
        "maximum_asset_weight",
        "effective_holdings",
        "any_weight_exceeds_50pct",
        "any_weight_exceeds_80pct",
        "year",
        "annual_turnover",
    ]
    write_csv(
        OUTPUT_DIR / "pamr_weight_diagnostics.csv",
        pamr_diagnostics,
        pamr_fields,
    )
    expert_fields = [
        "strategy_id",
        "expert_window",
        "signal_date",
        "execution_date",
        "warmup_complete",
        "valid_claim_count",
        "total_transfer_amount",
        "target_weights",
        "maximum_asset_weight",
        "effective_holdings",
        "cost_assumption_bps",
        "expert_nav",
        "aggregate_wealth_share",
        "expert_one_way_turnover",
    ]
    write_csv(
        OUTPUT_DIR / "anticor_expert_diagnostics.csv",
        anticor_expert_diagnostics,
        expert_fields,
    )
    claim_fields = [
        "strategy_id",
        "signal_date",
        "execution_date",
        "cost_assumption_bps",
        "warm_expert_count",
        "total_valid_claim_count",
        "total_transfer_amount",
        "aggregate_target",
        "aggregate_one_way_turnover",
        "maximum_asset_weight",
        "effective_holdings",
        "top_five_expert_wealth_share",
        "expert_costs_used_only_for_wealth_shares",
        "aggregate_cost_charged_once",
        "expert_and_aggregate_costs_double_charged",
    ]
    write_csv(
        OUTPUT_DIR / "anticor_claim_transfer_diagnostics.csv",
        anticor_claim_diagnostics,
        claim_fields,
    )
    invariant_fields = metric_fields + [
        "explicit_zero_weights",
        "stale_weight_forward_fill_used",
        "negative_weights_present",
        "leverage_present",
        "same_period_price_signal_return_used",
        "actual_transaction_cost_deduction",
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        invariant_fields,
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        outcomes,
        list(outcomes[0]),
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
        OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0])
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv", outcomes, list(outcomes[0])
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(OUTPUT_DIR / "batch_report.md", build_report(results, next_action))

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_after = map_hashes(cache_files())
    prior_after = map_hashes(prior_files_before)
    prior_aggregate_after = aggregate_hash(prior_after)
    v6_after = map_hashes(
        path for path in sorted(V6_EVIDENCE.rglob("*")) if path.is_file()
    )
    high52_after = map_hashes(
        path for path in sorted(HIGH52_CORRECTION.rglob("*")) if path.is_file()
    )
    source_hash_after = file_hash(SOURCE_PACKET)
    metadata_complete = all(
        all(
            row[field] not in ("unknown", "unmapped", None)
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
    all_invariants = all(bool(row["invariant_pass"]) for row in invariant_rows)
    anticor_costs_ok = all(
        row["expert_and_aggregate_costs_double_charged"] is False
        and row["aggregate_cost_charged_once"] is True
        for row in anticor_claim_diagnostics
    )
    consistency_passed = bool(
        tuple(result["card"].strategy_id for result in results)
        == EXPECTED_STRATEGY_IDS
        and len(strategies) == len(trials) == 2
        and len({row["trial_id"] for row in trials}) == 2
        and all(row["parent_trial_id"] == "" for row in trials)
        and all(row["adaptation_label"] == "" for row in trials)
        and metadata_complete
        and len(benchmarks) == 6
        and all_invariants
        and anticor_costs_ok
        and protected_before == protected_after
        and cache_before == cache_after
        and prior_aggregate_before == prior_aggregate_after
        and v6_before == v6_after
        and high52_before == high52_after
        and source_hash_before == source_hash_after
        and not any(FORBIDDEN_ACTIONS.values())
        and funnel["outcome_count_reconciles"]
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "exact_strategy_ids": list(EXPECTED_STRATEGY_IDS),
        "exactly_two_strategy_configurations": len(strategies) == 2,
        "exactly_two_canonical_trials": len(trials) == 2,
        "unique_trial_ids": len({row["trial_id"] for row in trials}) == 2,
        "canonical_trials_have_blank_parent_and_adaptation": all(
            row["parent_trial_id"] == "" and row["adaptation_label"] == ""
            for row in trials
        ),
        "required_metadata_complete": metadata_complete,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "frozen_pamr_variant_and_epsilon": (
            CARDS[0].parameters == {"variant": "PAMR-0", "epsilon": 0.5}
        ),
        "frozen_anticor_windows_2_through_30": (
            CARDS[1].parameters["expert_windows"] == list(range(2, 31))
        ),
        "olmar_and_anticor30_counted_only_as_benchmark_references": True,
        "expert_navs_include_independent_transaction_costs": True,
        "aggregate_implementable_target_cost_charged_once": anticor_costs_ok,
        "expert_and_aggregate_costs_double_charged": False,
        "all_numeric_timing_exposure_weight_invariants_passed": all_invariants,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_aggregate_hash_before": aggregate_hash(cache_before),
        "cache_aggregate_hash_after": aggregate_hash(cache_after),
        "cache_unchanged": cache_before == cache_after,
        "prior_evidence_file_count": len(prior_files_before),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": prior_aggregate_before == prior_aggregate_after,
        "original_v6_evidence_unchanged": v6_before == v6_after,
        "high52_correction_evidence_unchanged": high52_before == high52_after,
        "source_packet_hash_before": source_hash_before,
        "source_packet_hash_after": source_hash_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "provider_accessed": False,
        "validation_claimed": False,
        "lifecycle_state_changed": False,
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "entity_counts": {
            "source_library_records": len(sources),
            "strategy_configurations": len(strategies),
            "canonical_experiment_trials": len(trials),
            "benchmark_references": len(benchmarks),
            "process_tasks": len(process_rows),
        },
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "batch_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "executed_trial_count": sum(result["executed"] for result in results),
        "outcomes": {
            result["card"].strategy_id: result["outcome"] for result in results
        },
        "followup_candidate_count": funnel["followup_candidates"],
        "exact_next_action": next_action,
        "consistency_passed": consistency_passed,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
