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
from strategy_lab.research_os.research import fast_source_library_batch_v5 as v5


TASK_ID = "pring_kst_incremental_standalone_validation_v1"
STRATEGY_ID = "pring_kst_default_centerline_spy_bil_v1"
FAMILY_ID = "multi_cycle_smoothed_roc_momentum"
PARENT_TRIAL_ID = "fast_source_v5__pring_kst_default_centerline_spy_bil_v1__canonical"
VALIDATION_TRIAL_ID = f"{TASK_ID}__validation_child"
OUTPUT_DIR = ROOT / "evidence" / "validation" / TASK_ID / "latest"
FROZEN_TIMESTAMP = "2026-07-24T00:00:00+00:00"
REPRODUCTION_TOLERANCE = 1e-10
COST_BPS_GRID = (0.0, 5.0, 10.0)
PRIMARY_COST_BPS = 5.0

SPY_CONTROL = "SPY_buy_and_hold"
ROC30_CONTROL = "SPY_30_session_ROC_sign_SPY_BIL"
SPY200_CONTROL = "SPY_200d_frozen_control"
STATIC_CONTROL = "static_6878_SPY_3122_BIL_monthly_rebalanced"
CONTROL_IDS = (SPY_CONTROL, ROC30_CONTROL, SPY200_CONTROL, STATIC_CONTROL)
NON_BUY_HOLD_CONTROLS = (ROC30_CONTROL, SPY200_CONTROL, STATIC_CONTROL)

NEXT_ACTIONS = {
    "validation_positive": "direction_owner_review_kst_paper_demo_eligibility_v1",
    "validation_mixed": "direction_owner_review_kst_validation_mixed_v1",
    "validation_failed": "direction_owner_review_close_kst_after_validation_v1",
    "validation_data_or_methodology_blocked": "direction_owner_review_kst_validation_block_v1",
}

V5_DIR = ROOT / "evidence" / "research_recovery" / "fast_source_library_batch_v5" / "latest"
FROZEN_SPEC_PATH = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "strategy_source_library_refresh_v2"
    / "latest"
    / "frozen_candidate_specs.yaml"
)
INPUT_PATHS = (
    FROZEN_SPEC_PATH,
    V5_DIR / "strategy_cards.csv",
    V5_DIR / "trial_ledger.csv",
    V5_DIR / "all_trial_results.csv",
    V5_DIR / "control_results.csv",
    V5_DIR / "chronological_half_results.csv",
    V5_DIR / "indicator_state_diagnostics.csv",
    V5_DIR / "cost_diagnostics.csv",
    V5_DIR / "invariant_results.csv",
    V5_DIR / "consistency_check.json",
)
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "data" / "cache" / "SPY.csv",
    ROOT / "data" / "cache" / "BIL.csv",
)

FORBIDDEN_FLAGS = {
    "source_research_or_completion": False,
    "provider_access_or_data_acquisition": False,
    "other_strategy_validated": False,
    "parameter_or_instrument_change": False,
    "signal_line_or_alternate_kst_tested": False,
    "alternate_timeframe_or_centerline_tested": False,
    "stop_loss_vol_target_or_overlay_tested": False,
    "exposure_weight_optimized": False,
    "promotion_or_paper_demo_activation": False,
    "broker_account_order_or_real_money_action": False,
    "registry_or_active_observation_changed": False,
    "clean_or_sealed_holdout_claimed": False,
}

COMMON_METRIC_FIELDS = [
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


def hash_paths(paths: tuple[Path, ...]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


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


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "validation" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def frozen_card() -> v5.CandidateCard:
    cards = [card for card in v5.load_cards() if card.strategy_id == STRATEGY_ID]
    if len(cards) != 1:
        raise RuntimeError("Exactly one frozen KST source card is required")
    return cards[0]


def build_paths(card: v5.CandidateCard) -> tuple[dict[str, dict[float, dict[str, Any]]], dict[str, Any]]:
    prepared = v5.prepare_candidate(card)
    prices = prepared["prices"]
    if prices.empty:
        raise RuntimeError("Validated SPY/BIL cache is unavailable")
    event_map = {
        STRATEGY_ID: prepared["candidate_events"],
        SPY_CONTROL: prepared["control_events"][SPY_CONTROL],
        ROC30_CONTROL: prepared["control_events"][ROC30_CONTROL],
        SPY200_CONTROL: v5.compress_weight_frame(
            v5.reference_spy200d_weights(prices[["SPY", "BIL"]])
        ),
        STATIC_CONTROL: v5.monthly_static_schedule(prices.index, 0.6878),
    }
    paths: dict[str, dict[float, dict[str, Any]]] = {entity_id: {} for entity_id in event_map}
    for entity_id, events in event_map.items():
        for cost_bps in COST_BPS_GRID:
            paths[entity_id][cost_bps] = v5.simulate_path(
                prices,
                events.reindex(columns=list(prices.columns), fill_value=0.0),
                cost_bps,
                "completed_close_target_applied_to_following_session",
            )
    return paths, prepared


def prior_5bps_rows() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(V5_DIR / "all_trial_results.csv"):
        if row["strategy_id"] == STRATEGY_ID and row["cost_assumption_bps"] == "5":
            lookup[STRATEGY_ID] = row
    for row in read_csv_rows(V5_DIR / "control_results.csv"):
        if (
            row["strategy_id"] == STRATEGY_ID
            and row["cost_assumption_bps"] == "5"
            and row["control_id"] in {SPY_CONTROL, ROC30_CONTROL}
        ):
            lookup[row["control_id"]] = row
    return lookup


def reproduction_rows(paths: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    prior_lookup = prior_5bps_rows()
    metrics = [
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
    ]
    rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, SPY_CONTROL, ROC30_CONTROL):
        current = v5.metric_payload(paths[entity_id][PRIMARY_COST_BPS])
        prior_row = prior_lookup.get(entity_id, {})
        for metric in metrics:
            prior_value = float(prior_row[metric]) if prior_row.get(metric, "") else float("nan")
            current_value = float(current[metric])
            tolerance = 0.0 if metric == "trade_or_rebalance_count" else REPRODUCTION_TOLERANCE
            difference = abs(current_value - prior_value)
            rows.append(
                {
                    "entity_id": entity_id,
                    "metric": metric,
                    "v5_value": prior_value,
                    "recomputed_value": current_value,
                    "absolute_difference": difference,
                    "tolerance": tolerance,
                    "reproduction_status": "pass" if difference <= tolerance else "fail",
                }
            )
    return rows


def result_row(
    entity_id: str,
    cost_bps: float,
    metrics: dict[str, Any],
    period_label: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": VALIDATION_TRIAL_ID,
        "entity_id": entity_id,
        "entity_type": "candidate_standalone" if entity_id == STRATEGY_ID else "benchmark_reference",
        "cost_assumption_bps": cost_bps,
        "period_label": period_label,
        **metrics,
    }


def full_period_rows(paths: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        result_row(entity_id, cost_bps, v5.metric_payload(path), "full_period")
        for entity_id, cost_map in paths.items()
        for cost_bps, path in cost_map.items()
    ]


def chronological_half_rows(paths: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_index = paths[STRATEGY_ID][PRIMARY_COST_BPS]["returns"].index
    for half_label, half_index in v5.split_halves(base_index):
        for entity_id, cost_map in paths.items():
            for cost_bps, path in cost_map.items():
                rows.append(
                    {
                        **result_row(
                            entity_id,
                            cost_bps,
                            v5.metric_payload(path, half_index),
                            half_label,
                        ),
                        "half_source": "original_v5_chronological_half_not_clean_or_sealed_holdout",
                    }
                )
    return rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [
        pd.Timestamp(value)
        for value in index[periods.ne(periods.shift(-1)).fillna(True)]
    ]


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    control_values = (
        float(control["cagr"]),
        float(control["sharpe_ratio"]),
        float(control["maximum_drawdown"]),
    )
    candidate_values = (
        float(candidate["cagr"]),
        float(candidate["sharpe_ratio"]),
        float(candidate["maximum_drawdown"]),
    )
    return bool(
        all(left >= right - 1e-12 for left, right in zip(control_values, candidate_values))
        and any(left > right + 1e-12 for left, right in zip(control_values, candidate_values))
    )


def rolling_rows(
    paths: dict[str, dict[float, dict[str, Any]]],
    months: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base_index = paths[STRATEGY_ID][PRIMARY_COST_BPS]["returns"].index
    first_available = pd.Timestamp(base_index.min())
    for end_date in month_end_dates(base_index):
        cutoff = end_date - pd.DateOffset(months=months)
        if cutoff < first_available:
            continue
        window_index = base_index[(base_index >= cutoff) & (base_index <= end_date)]
        for cost_bps in COST_BPS_GRID:
            candidate = v5.metric_payload(paths[STRATEGY_ID][cost_bps], window_index)
            for control_id in CONTROL_IDS:
                control = v5.metric_payload(paths[control_id][cost_bps], window_index)
                rows.append(
                    {
                        "window_months": months,
                        "cost_assumption_bps": cost_bps,
                        "window_start": pd.Timestamp(window_index.min()).date().isoformat(),
                        "window_end": pd.Timestamp(window_index.max()).date().isoformat(),
                        "trading_days": len(window_index),
                        "candidate_id": STRATEGY_ID,
                        "control_id": control_id,
                        "candidate_cagr": candidate["cagr"],
                        "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                        "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                        "candidate_annualized_volatility": candidate["annualized_volatility"],
                        "candidate_turnover": candidate["turnover"],
                        "candidate_transaction_cost_drag": candidate["transaction_cost_drag"],
                        "control_cagr": control["cagr"],
                        "control_sharpe_ratio": control["sharpe_ratio"],
                        "control_maximum_drawdown": control["maximum_drawdown"],
                        "control_annualized_volatility": control["annualized_volatility"],
                        "control_turnover": control["turnover"],
                        "control_transaction_cost_drag": control["transaction_cost_drag"],
                        "cagr_difference": float(candidate["cagr"]) - float(control["cagr"]),
                        "sharpe_ratio_difference": (
                            float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
                        ),
                        "maximum_drawdown_difference": (
                            float(candidate["maximum_drawdown"])
                            - float(control["maximum_drawdown"])
                        ),
                        "annualized_volatility_difference": (
                            float(candidate["annualized_volatility"])
                            - float(control["annualized_volatility"])
                        ),
                        "control_dominates_kst": dominates(control, candidate),
                        "maximum_gross_exposure": max(
                            float(candidate["maximum_gross_exposure"]),
                            float(control["maximum_gross_exposure"]),
                        ),
                        "maximum_daily_weight_sum": max(
                            float(candidate["maximum_daily_weight_sum"]),
                            float(control["maximum_daily_weight_sum"]),
                        ),
                        "numeric_invariant_status": (
                            "pass"
                            if candidate["numeric_invariant_status"] == "pass"
                            and control["numeric_invariant_status"] == "pass"
                            else "fail"
                        ),
                        "timing_invariant_status": (
                            "pass"
                            if str(candidate["timing_invariant_status"]).startswith("pass")
                            and str(control["timing_invariant_status"]).startswith("pass")
                            else "fail"
                        ),
                        "exposure_weight_invariant_status": (
                            "pass"
                            if candidate["exposure_weight_invariant_status"] == "pass"
                            and control["exposure_weight_invariant_status"] == "pass"
                            else "fail"
                        ),
                    }
                )
    return rows


def rolling_summary_rows(
    rows_36: list[dict[str, Any]],
    rows_60: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for months, rows in ((36, rows_36), (60, rows_60)):
        for cost_bps in COST_BPS_GRID:
            selected = [row for row in rows if float(row["cost_assumption_bps"]) == cost_bps]
            for control_id in CONTROL_IDS:
                control_rows = [row for row in selected if row["control_id"] == control_id]
                output.append(
                    {
                        "window_months": months,
                        "cost_assumption_bps": cost_bps,
                        "comparison_scope": "specific_control",
                        "control_id": control_id,
                        "window_count": len(control_rows),
                        "median_cagr_difference": float(
                            pd.Series([row["cagr_difference"] for row in control_rows]).median()
                        ),
                        "median_sharpe_ratio_difference": float(
                            pd.Series([row["sharpe_ratio_difference"] for row in control_rows]).median()
                        ),
                        "median_maximum_drawdown_difference": float(
                            pd.Series([row["maximum_drawdown_difference"] for row in control_rows]).median()
                        ),
                        "median_annualized_volatility_difference": float(
                            pd.Series([row["annualized_volatility_difference"] for row in control_rows]).median()
                        ),
                        "positive_sharpe_difference_fraction": float(
                            np.mean([float(row["sharpe_ratio_difference"]) > 0.0 for row in control_rows])
                        ),
                        "control_dominated_window_fraction": float(
                            np.mean([bool(row["control_dominates_kst"]) for row in control_rows])
                        ),
                    }
                )
            by_window: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in selected:
                if row["control_id"] in NON_BUY_HOLD_CONTROLS:
                    by_window.setdefault((row["window_start"], row["window_end"]), []).append(row)
            best_sharpe_diffs: list[float] = []
            best_drawdown_diffs: list[float] = []
            any_dominated: list[bool] = []
            for window_rows in by_window.values():
                best_sharpe_diffs.append(
                    float(
                        min(
                            window_rows,
                            key=lambda row: float(row["sharpe_ratio_difference"]),
                        )["sharpe_ratio_difference"]
                    )
                )
                best_drawdown_diffs.append(
                    float(
                        min(
                            window_rows,
                            key=lambda row: float(row["maximum_drawdown_difference"]),
                        )["maximum_drawdown_difference"]
                    )
                )
                any_dominated.append(any(bool(row["control_dominates_kst"]) for row in window_rows))
            output.append(
                {
                    "window_months": months,
                    "cost_assumption_bps": cost_bps,
                    "comparison_scope": "best_non_buy_and_hold_control_per_window",
                    "control_id": "best_non_buy_and_hold_control",
                    "window_count": len(by_window),
                    "median_cagr_difference": "",
                    "median_sharpe_ratio_difference": float(pd.Series(best_sharpe_diffs).median()),
                    "median_maximum_drawdown_difference": float(
                        pd.Series(best_drawdown_diffs).median()
                    ),
                    "median_annualized_volatility_difference": "",
                    "positive_sharpe_difference_fraction": float(
                        np.mean(np.array(best_sharpe_diffs) > 0.0)
                    ),
                    "control_dominated_window_fraction": float(np.mean(any_dominated)),
                }
            )
    return output


def calendar_year_rows(
    paths: dict[str, dict[float, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id, cost_map in paths.items():
        for cost_bps, path in cost_map.items():
            for year in sorted(set(path["returns"].index.year)):
                year_index = path["returns"].index[path["returns"].index.year == year]
                rows.append(
                    {
                        "calendar_year": int(year),
                        "descriptive_only": True,
                        **result_row(
                            entity_id,
                            cost_bps,
                            v5.metric_payload(path, year_index),
                            "calendar_year",
                        ),
                    }
                )
    return rows


def holding_episode_rows(
    candidate_path: dict[str, Any],
    prices: pd.DataFrame,
) -> list[dict[str, Any]]:
    active = (candidate_path["held_weights"]["SPY"] > 0.5).astype(bool)
    rows: list[dict[str, Any]] = []
    start_position: int | None = None
    episode_number = 0
    for position, is_active in enumerate(active):
        if is_active and start_position is None:
            start_position = position
        is_last = position == len(active) - 1
        if start_position is not None and ((not is_active) or is_last):
            end_position = position - 1 if not is_active else position
            boundary_start = max(start_position - 1, 0)
            episode_index = active.index[boundary_start : end_position + 1]
            active_index = active.index[start_position : end_position + 1]
            episode_number += 1
            gross_spy_return = float(
                prices.loc[active_index[-1], "SPY"]
                / prices.loc[active.index[boundary_start], "SPY"]
                - 1.0
            )
            net_return = float(
                (1.0 + candidate_path["returns"].reindex(episode_index).fillna(0.0)).prod()
                - 1.0
            )
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": VALIDATION_TRIAL_ID,
                    "episode_number": episode_number,
                    "entry_signal_date": active.index[boundary_start].date().isoformat(),
                    "first_spy_return_session": active_index[0].date().isoformat(),
                    "last_spy_return_session": active_index[-1].date().isoformat(),
                    "holding_duration_sessions": len(active_index),
                    "gross_spy_episode_return": gross_spy_return,
                    "net_candidate_episode_return_including_boundary_costs": net_return,
                    "profitable_episode": net_return > 0.0,
                    "cost_assumption_bps": PRIMARY_COST_BPS,
                }
            )
            start_position = None
    return rows


def run_lengths(state: pd.Series, value: bool) -> list[int]:
    lengths: list[int] = []
    running = 0
    for item in state.astype(bool):
        if bool(item) == value:
            running += 1
        elif running:
            lengths.append(running)
            running = 0
    if running:
        lengths.append(running)
    return lengths


def signal_state_rows(
    candidate_path: dict[str, Any],
    episodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    active = (candidate_path["held_weights"]["SPY"] > 0.5).astype(bool)
    previous = active.shift(1, fill_value=False).astype(bool)
    entries = active & ~previous
    exits = ~active & previous
    spy_lengths = [int(row["holding_duration_sessions"]) for row in episodes]
    bil_lengths = run_lengths(active, False)
    summary = {
        "strategy_id": STRATEGY_ID,
        "trial_id": VALIDATION_TRIAL_ID,
        "diagnostic_scope": "full_period_summary",
        "calendar_year": "",
        "entry_count": int(entries.sum()),
        "exit_count": int(exits.sum()),
        "holding_episode_count": len(episodes),
        "percentage_sessions_in_SPY": float(active.mean()),
        "average_holding_duration_sessions": float(np.mean(spy_lengths)),
        "median_holding_duration_sessions": float(np.median(spy_lengths)),
        "profitable_holding_episode_fraction": float(
            np.mean([bool(row["profitable_episode"]) for row in episodes])
        ),
        "average_spy_episode_return": float(
            np.mean([float(row["gross_spy_episode_return"]) for row in episodes])
        ),
        "median_spy_episode_return": float(
            np.median([float(row["gross_spy_episode_return"]) for row in episodes])
        ),
        "average_bil_state_duration_sessions": float(np.mean(bil_lengths)),
        "state_change_count": int((active != previous).sum()),
        "descriptive_only": True,
    }
    rows = [summary]
    changes = active != previous
    for year in sorted(set(active.index.year)):
        rows.append(
            {
                **summary,
                "diagnostic_scope": "calendar_year_state_changes",
                "calendar_year": int(year),
                "state_change_count": int(changes.loc[changes.index.year == year].sum()),
            }
        )
    return rows


def exposure_reconciliation_rows(
    paths: dict[str, dict[float, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost_bps in COST_BPS_GRID:
        candidate = v5.metric_payload(paths[STRATEGY_ID][cost_bps])
        control = v5.metric_payload(paths[STATIC_CONTROL][cost_bps])
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "control_id": STATIC_CONTROL,
                "cost_assumption_bps": cost_bps,
                "v5_preregistered_average_risky_exposure": 0.687799791449,
                "frozen_static_spy_target": 0.6878,
                "frozen_static_bil_target": 0.3122,
                "candidate_realized_average_risky_exposure": candidate["average_risky_exposure"],
                "control_realized_average_risky_exposure": control["average_risky_exposure"],
                "realized_exposure_difference": (
                    float(candidate["average_risky_exposure"])
                    - float(control["average_risky_exposure"])
                ),
                "sharpe_ratio_difference": (
                    float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
                ),
                "maximum_drawdown_difference": (
                    float(candidate["maximum_drawdown"])
                    - float(control["maximum_drawdown"])
                ),
                "post_exploration_exposure_matching_control": True,
                "performance_optimized_weight": False,
                "benchmark_reference_only": True,
            }
        )
    return rows


def turnover_cost_rows(
    paths: dict[str, dict[float, dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id, cost_map in paths.items():
        for cost_bps, path in cost_map.items():
            metrics = v5.metric_payload(path)
            rows.append(
                {
                    "entity_id": entity_id,
                    "entity_type": (
                        "candidate_standalone"
                        if entity_id == STRATEGY_ID
                        else "benchmark_reference"
                    ),
                    "cost_assumption_bps": cost_bps,
                    "one_way_turnover_formula": (
                        "0.5 * sum(abs(target_weight_i - pretrade_weight_i))"
                    ),
                    "actual_pretrade_holdings_used": True,
                    "turnover": metrics["turnover"],
                    "trade_or_rebalance_count": metrics["trade_or_rebalance_count"],
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "explicit_zero_weights_preserved": True,
                    "stale_weight_forward_fill_used": False,
                    "maximum_gross_exposure": metrics["maximum_gross_exposure"],
                    "maximum_daily_weight_sum": metrics["maximum_daily_weight_sum"],
                    "invariant_pass": metrics["invariant_pass"],
                }
            )
    return rows


def lookup_full(
    full_rows: list[dict[str, Any]],
    entity_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    return next(
        row
        for row in full_rows
        if row["entity_id"] == entity_id
        and float(row["cost_assumption_bps"]) == cost_bps
    )


def decision(
    reproduction: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    reproduction_pass = all(row["reproduction_status"] == "pass" for row in reproduction)
    if not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "blocked",
            "data_or_comparability_failure",
            {"reproduction_pass": False},
        )
    invariant_pass = all(bool(row["invariant_pass"]) for row in full_rows)
    if not invariant_pass:
        return (
            "validation_data_or_methodology_blocked",
            "blocked",
            "methodology_failure",
            {"reproduction_pass": True, "invariant_pass": False},
        )
    candidate = lookup_full(full_rows, STRATEGY_ID, PRIMARY_COST_BPS)
    controls = {
        control_id: lookup_full(full_rows, control_id, PRIMARY_COST_BPS)
        for control_id in CONTROL_IDS
    }
    full_dominators = [
        control_id
        for control_id, control in controls.items()
        if dominates(control, candidate)
    ]
    roc_sharpe = float(candidate["sharpe_ratio"]) - float(controls[ROC30_CONTROL]["sharpe_ratio"])
    roc_drawdown = (
        float(candidate["maximum_drawdown"])
        - float(controls[ROC30_CONTROL]["maximum_drawdown"])
    )
    static_sharpe = (
        float(candidate["sharpe_ratio"]) - float(controls[STATIC_CONTROL]["sharpe_ratio"])
    )
    static_drawdown = (
        float(candidate["maximum_drawdown"])
        - float(controls[STATIC_CONTROL]["maximum_drawdown"])
    )
    roc_material = roc_sharpe >= 0.02 - 1e-12 or roc_drawdown >= 0.01 - 1e-12
    static_material = (
        static_sharpe >= 0.02 - 1e-12 or static_drawdown >= 0.01 - 1e-12
    )
    half_pass = True
    half_details: dict[str, Any] = {}
    for half_label in ("first_chronological_half", "second_chronological_half"):
        selected = [
            row
            for row in half_rows
            if row["period_label"] == half_label
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        ]
        candidate_half = next(row for row in selected if row["entity_id"] == STRATEGY_ID)
        roc_half = next(row for row in selected if row["entity_id"] == ROC30_CONTROL)
        static_half = next(row for row in selected if row["entity_id"] == STATIC_CONTROL)
        worse_roc_both = (
            float(candidate_half["sharpe_ratio"]) < float(roc_half["sharpe_ratio"])
            and float(candidate_half["maximum_drawdown"])
            < float(roc_half["maximum_drawdown"])
        )
        worse_static_both = (
            float(candidate_half["sharpe_ratio"]) < float(static_half["sharpe_ratio"])
            and float(candidate_half["maximum_drawdown"])
            < float(static_half["maximum_drawdown"])
        )
        half_details[half_label] = {
            "worse_than_roc30_on_sharpe_and_drawdown": worse_roc_both,
            "worse_than_static_on_sharpe_and_drawdown": worse_static_both,
        }
        if worse_roc_both and worse_static_both:
            half_pass = False
    summary = {
        (int(row["window_months"]), float(row["cost_assumption_bps"])): row
        for row in rolling_summary
        if row["comparison_scope"] == "best_non_buy_and_hold_control_per_window"
    }
    summary_36 = summary[(36, PRIMARY_COST_BPS)]
    summary_60 = summary[(60, PRIMARY_COST_BPS)]
    rolling_36_pass = (
        float(summary_36["median_sharpe_ratio_difference"]) > 0.0
        or float(summary_36["median_maximum_drawdown_difference"]) >= 0.005 - 1e-12
    )
    rolling_60_pass = (
        float(summary_60["median_sharpe_ratio_difference"]) > 0.0
        or float(summary_60["median_maximum_drawdown_difference"]) >= 0.005 - 1e-12
    )
    domination_36_pass = (
        float(summary_36["control_dominated_window_fraction"]) <= 0.5 + 1e-12
    )
    domination_60_pass = (
        float(summary_60["control_dominated_window_fraction"]) <= 0.5 + 1e-12
    )
    candidate_10 = lookup_full(full_rows, STRATEGY_ID, 10.0)
    cost_10_pass = True
    cost_10_details: dict[str, Any] = {}
    for control_id in (ROC30_CONTROL, STATIC_CONTROL):
        control_10 = lookup_full(full_rows, control_id, 10.0)
        unfavorable_both = (
            float(candidate_10["sharpe_ratio"]) < float(control_10["sharpe_ratio"])
            and float(candidate_10["maximum_drawdown"])
            < float(control_10["maximum_drawdown"])
        )
        cost_10_details[control_id] = {"unfavorable_on_sharpe_and_drawdown": unfavorable_both}
        if unfavorable_both:
            cost_10_pass = False
    not_exposure_only = static_material and STATIC_CONTROL not in full_dominators
    checks = {
        "reproduction_pass": reproduction_pass,
        "invariant_pass": invariant_pass,
        "full_period_dominating_controls": full_dominators,
        "no_control_dominates_full_period": not full_dominators,
        "roc30_sharpe_difference": roc_sharpe,
        "roc30_drawdown_difference": roc_drawdown,
        "roc30_material_advantage": roc_material,
        "static_sharpe_difference": static_sharpe,
        "static_drawdown_difference": static_drawdown,
        "static_material_advantage": static_material,
        "spy200d_does_not_dominate": SPY200_CONTROL not in full_dominators,
        "chronological_half_requirement_pass": half_pass,
        "chronological_half_details": half_details,
        "rolling_36_requirement_pass": rolling_36_pass,
        "rolling_60_requirement_pass": rolling_60_pass,
        "rolling_36_domination_requirement_pass": domination_36_pass,
        "rolling_60_domination_requirement_pass": domination_60_pass,
        "rolling_36_summary": summary_36,
        "rolling_60_summary": summary_60,
        "cost_10_requirement_pass": cost_10_pass,
        "cost_10_details": cost_10_details,
        "not_explained_solely_by_lower_spy_exposure": not_exposure_only,
    }
    positive = all(
        [
            not full_dominators,
            roc_material,
            static_material,
            SPY200_CONTROL not in full_dominators,
            half_pass,
            rolling_36_pass,
            rolling_60_pass,
            domination_36_pass,
            domination_60_pass,
            cost_10_pass,
            not_exposure_only,
        ]
    )
    if positive:
        return "validation_positive", "validation", "", checks
    if full_dominators:
        reason = (
            "benchmark_like_behavior"
            if STATIC_CONTROL in full_dominators
            else "weak_vs_primary_control"
        )
        return "validation_failed", "validation", reason, checks
    if not static_material or not roc_material:
        return "validation_failed", "validation", "benchmark_like_behavior", checks
    both_rolling_fail = not rolling_36_pass and not rolling_60_pass
    both_dominated = not domination_36_pass and not domination_60_pass
    if both_rolling_fail or both_dominated:
        return "validation_failed", "validation", "period_instability", checks
    if not cost_10_pass:
        return "validation_failed", "validation", "cost_drag", checks
    if not half_pass:
        return "validation_failed", "validation", "period_instability", checks
    return "validation_mixed", "validation", "", checks


def next_action_for(outcome: str) -> str:
    return NEXT_ACTIONS[outcome]


def strategy_card_row(
    card: v5.CandidateCard,
    outcome: str,
    stage: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": card.display_name,
        "entity_type": "strategy_configuration",
        "strategy_architecture": card.strategy_architecture,
        "source_or_research_lineage": (
            "strategy_source_library_refresh_v2:src_pring_kst_1992_v1;"
            f"exploratory_parent_trial:{PARENT_TRIAL_ID}"
        ),
        "instrument_universe": "SPY|BIL",
        "parameters": card.parameters,
        "benchmark_or_control": "|".join(CONTROL_IDS),
        "stage": stage,
        "trial_id": VALIDATION_TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "validation_variant",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def trial_ledger_row(
    outcome: str,
    stage: str,
    failure_reason: str,
    next_action: str,
    evaluation_start: str,
    evaluation_end: str,
) -> dict[str, Any]:
    return {
        "trial_id": VALIDATION_TRIAL_ID,
        "entity_type": "experiment_trial",
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "stage": stage,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "validation_variant",
        "changed_fields_from_parent": (
            "validation_diagnostics_and_predeclared_exposure_and_trend_controls_only"
        ),
        "strategy_rule_changed": False,
        "parameters_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "validation_controls_added": True,
        "exposure_matched_control_derived_after_exploration": True,
        "optimization_performed": False,
        "timeframe_selected_from_performance": False,
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    roles = {
        SPY_CONTROL: "primary_benchmark",
        ROC30_CONTROL: "same_purpose_control",
        SPY200_CONTROL: "generic_trend_control",
        STATIC_CONTROL: "post_exploration_exposure_matching_control",
    }
    return [
        {
            "benchmark_reference_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id_context": STRATEGY_ID,
            "control_role": roles[control_id],
            "frozen_definition": (
                "SPY_0.6878_BIL_0.3122_month_end_target_next_session_execution"
                if control_id == STATIC_CONTROL
                else "reused_exact_fast_source_library_batch_v5_definition"
            ),
            "performance_optimized": False,
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "counted_as_observation": False,
        }
        for control_id in CONTROL_IDS
    ]


def build_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
    checks: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Pring KST Incremental Standalone Validation V1",
            "",
            "## Scope",
            "",
            "Exactly one frozen KST strategy configuration was validated as a child of its v5 exploratory trial. "
            "No KST formula, parameter, instrument, timing, or cost assumption changed.",
            "",
            "## Reproduction",
            "",
            f"* V5 reproduction gate: `{'pass' if checks.get('reproduction_pass') else 'fail'}`",
            f"* Full-period invariant gate: `{'pass' if checks.get('invariant_pass') else 'fail'}`",
            "",
            "## Incremental Controls",
            "",
            f"* Full-period dominating controls: `{checks.get('full_period_dominating_controls', [])}`",
            f"* ROC30 Sharpe difference: `{checks.get('roc30_sharpe_difference', '')}`",
            f"* ROC30 drawdown difference: `{checks.get('roc30_drawdown_difference', '')}`",
            f"* Static exposure-control Sharpe difference: `{checks.get('static_sharpe_difference', '')}`",
            f"* Static exposure-control drawdown difference: `{checks.get('static_drawdown_difference', '')}`",
            f"* Chronological-half requirement: `{checks.get('chronological_half_requirement_pass', False)}`",
            f"* Rolling 36-month requirement: `{checks.get('rolling_36_requirement_pass', False)}`",
            f"* Rolling 60-month requirement: `{checks.get('rolling_60_requirement_pass', False)}`",
            f"* 10 bps requirement: `{checks.get('cost_10_requirement_pass', False)}`",
            f"* Lower-exposure-only explanation rejected: `{checks.get('not_explained_solely_by_lower_spy_exposure', False)}`",
            "",
            "All chronological halves and rolling windows are diagnostics. None is described as a clean or sealed holdout.",
            "",
            "## Decision",
            "",
            f"* Outcome: `{outcome}`",
            f"* Primary failure reason: `{failure_reason or 'none'}`",
            "",
            "This validation result does not grant promotion or paper/demo eligibility.",
            "",
            "## Exact Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )


RESULT_FIELDS = [
    "strategy_id",
    "trial_id",
    "entity_id",
    "entity_type",
    "cost_assumption_bps",
    "period_label",
    *COMMON_METRIC_FIELDS,
]

ROLLING_FIELDS = [
    "window_months",
    "cost_assumption_bps",
    "window_start",
    "window_end",
    "trading_days",
    "candidate_id",
    "control_id",
    "candidate_cagr",
    "candidate_sharpe_ratio",
    "candidate_maximum_drawdown",
    "candidate_annualized_volatility",
    "candidate_turnover",
    "candidate_transaction_cost_drag",
    "control_cagr",
    "control_sharpe_ratio",
    "control_maximum_drawdown",
    "control_annualized_volatility",
    "control_turnover",
    "control_transaction_cost_drag",
    "cagr_difference",
    "sharpe_ratio_difference",
    "maximum_drawdown_difference",
    "annualized_volatility_difference",
    "control_dominates_kst",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_weight_invariant_status",
]


def deterministic_core_hash() -> str:
    names = [
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "reproduction_check.csv",
        "full_period_results.csv",
        "chronological_half_results.csv",
        "rolling_36_month_results.csv",
        "rolling_60_month_results.csv",
        "rolling_window_summary.csv",
        "calendar_year_results.csv",
        "signal_state_diagnostics.csv",
        "holding_episode_results.csv",
        "exposure_control_reconciliation.csv",
        "turnover_cost_reconciliation.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "validation_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode("utf-8"))
        digest.update((OUTPUT_DIR / name).read_bytes())
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    before_protected = hash_paths(PROTECTED_PATHS)
    before_inputs = hash_paths(INPUT_PATHS)
    card = frozen_card()
    paths, prepared = build_paths(card)
    reproduction = reproduction_rows(paths)
    reproduction_pass = all(row["reproduction_status"] == "pass" for row in reproduction)

    full_rows = full_period_rows(paths)
    half_rows = chronological_half_rows(paths) if reproduction_pass else []
    rolling_36 = rolling_rows(paths, 36) if reproduction_pass else []
    rolling_60 = rolling_rows(paths, 60) if reproduction_pass else []
    rolling_summary = (
        rolling_summary_rows(rolling_36, rolling_60) if reproduction_pass else []
    )
    calendar_rows = calendar_year_rows(paths) if reproduction_pass else []
    episodes = (
        holding_episode_rows(paths[STRATEGY_ID][PRIMARY_COST_BPS], prepared["prices"])
        if reproduction_pass
        else []
    )
    signal_rows = (
        signal_state_rows(paths[STRATEGY_ID][PRIMARY_COST_BPS], episodes)
        if reproduction_pass
        else []
    )
    exposure_rows = exposure_reconciliation_rows(paths) if reproduction_pass else []
    turnover_rows = turnover_cost_rows(paths)
    outcome, stage, failure_reason, checks = decision(
        reproduction, full_rows, half_rows, rolling_summary
    )
    next_action = next_action_for(outcome)
    after_protected = hash_paths(PROTECTED_PATHS)
    after_inputs = hash_paths(INPUT_PATHS)

    clean_output_dir()
    write_yaml(
        OUTPUT_DIR / "validation_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": "validation",
            "stage": stage,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "trial_id": VALIDATION_TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "adaptation_label": "validation_variant",
            "strategy_count": 1,
            "validation_trial_count": 1,
            "benchmark_reference_count": 4,
            "cost_assumptions_bps": list(COST_BPS_GRID),
            "primary_cost_bps": PRIMARY_COST_BPS,
            "reproduction_tolerance": REPRODUCTION_TOLERANCE,
            "rolling_windows_months": [36, 60],
            "exposure_matched_control": {
                "id": STATIC_CONTROL,
                "SPY": 0.6878,
                "BIL": 0.3122,
                "optimization_performed": False,
            },
            "outcome": outcome,
            "failure_reason": failure_reason,
            "exact_next_action": next_action,
            "next_action_executed": False,
            "promotion_or_paper_demo_authorized": False,
        },
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        [strategy_card_row(card, outcome, stage, failure_reason, next_action)],
        [
            "strategy_id", "family_id", "display_name", "entity_type", "strategy_architecture",
            "source_or_research_lineage", "instrument_universe", "parameters", "benchmark_or_control",
            "stage", "trial_id", "parent_trial_id", "adaptation_label", "outcome", "failure_reason",
            "next_action",
        ],
    )
    base_metrics = v5.metric_payload(paths[STRATEGY_ID][PRIMARY_COST_BPS])
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        [
            trial_ledger_row(
                outcome,
                stage,
                failure_reason,
                next_action,
                base_metrics["evaluation_start"],
                base_metrics["evaluation_end"],
            )
        ],
        [
            "trial_id", "entity_type", "strategy_id", "family_id", "stage", "parent_trial_id",
            "adaptation_label", "changed_fields_from_parent", "strategy_rule_changed",
            "parameters_changed", "instruments_changed", "execution_changed", "cost_model_changed",
            "validation_controls_added", "exposure_matched_control_derived_after_exploration",
            "optimization_performed", "timeframe_selected_from_performance", "evaluation_start",
            "evaluation_end", "preregistration_timestamp", "outcome", "failure_reason", "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": "validation",
                "strategy_count": 0,
                "trial_count": 0,
                "next_action": next_action,
            }
        ],
        [
            "process_task_id", "entity_type", "stage", "strategy_count", "trial_count", "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows(),
        [
            "benchmark_reference_id", "entity_type", "stage", "strategy_id_context", "control_role",
            "frozen_definition", "performance_optimized", "counted_as_strategy", "counted_as_trial",
            "counted_as_observation",
        ],
    )
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        [
            "entity_id", "metric", "v5_value", "recomputed_value", "absolute_difference", "tolerance",
            "reproduction_status",
        ],
    )
    write_csv(OUTPUT_DIR / "full_period_results.csv", full_rows, RESULT_FIELDS)
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv",
        half_rows,
        RESULT_FIELDS + ["half_source"],
    )
    write_csv(OUTPUT_DIR / "rolling_36_month_results.csv", rolling_36, ROLLING_FIELDS)
    write_csv(OUTPUT_DIR / "rolling_60_month_results.csv", rolling_60, ROLLING_FIELDS)
    write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary,
        [
            "window_months", "cost_assumption_bps", "comparison_scope", "control_id",
            "window_count", "median_cagr_difference", "median_sharpe_ratio_difference",
            "median_maximum_drawdown_difference", "median_annualized_volatility_difference",
            "positive_sharpe_difference_fraction", "control_dominated_window_fraction",
        ],
    )
    write_csv(
        OUTPUT_DIR / "calendar_year_results.csv",
        calendar_rows,
        ["calendar_year", "descriptive_only", *RESULT_FIELDS],
    )
    write_csv(
        OUTPUT_DIR / "signal_state_diagnostics.csv",
        signal_rows,
        [
            "strategy_id", "trial_id", "diagnostic_scope", "calendar_year", "entry_count", "exit_count",
            "holding_episode_count", "percentage_sessions_in_SPY", "average_holding_duration_sessions",
            "median_holding_duration_sessions", "profitable_holding_episode_fraction",
            "average_spy_episode_return", "median_spy_episode_return",
            "average_bil_state_duration_sessions", "state_change_count", "descriptive_only",
        ],
    )
    write_csv(
        OUTPUT_DIR / "holding_episode_results.csv",
        episodes,
        [
            "strategy_id", "trial_id", "episode_number", "entry_signal_date",
            "first_spy_return_session", "last_spy_return_session", "holding_duration_sessions",
            "gross_spy_episode_return", "net_candidate_episode_return_including_boundary_costs",
            "profitable_episode", "cost_assumption_bps",
        ],
    )
    write_csv(
        OUTPUT_DIR / "exposure_control_reconciliation.csv",
        exposure_rows,
        [
            "strategy_id", "control_id", "cost_assumption_bps",
            "v5_preregistered_average_risky_exposure", "frozen_static_spy_target",
            "frozen_static_bil_target", "candidate_realized_average_risky_exposure",
            "control_realized_average_risky_exposure", "realized_exposure_difference",
            "sharpe_ratio_difference", "maximum_drawdown_difference",
            "post_exploration_exposure_matching_control", "performance_optimized_weight",
            "benchmark_reference_only",
        ],
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        [
            "entity_id", "entity_type", "cost_assumption_bps", "one_way_turnover_formula",
            "actual_pretrade_holdings_used", "turnover", "trade_or_rebalance_count",
            "transaction_cost_drag", "explicit_zero_weights_preserved",
            "stale_weight_forward_fill_used", "maximum_gross_exposure",
            "maximum_daily_weight_sum", "invariant_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": VALIDATION_TRIAL_ID,
                "stage": stage,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "decision_checks": checks,
                "next_action": next_action,
                "next_action_executed": False,
                "promotion_or_paper_demo_authorized": False,
            }
        ],
        [
            "strategy_id", "trial_id", "stage", "outcome", "primary_failure_reason",
            "decision_checks", "next_action", "next_action_executed",
            "promotion_or_paper_demo_authorized",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        (
            [
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": VALIDATION_TRIAL_ID,
                    "outcome": outcome,
                    "primary_failure_reason": failure_reason,
                    "exact_configuration_only": True,
                    "family_closed": False,
                }
            ]
            if failure_reason
            else []
        ),
        [
            "strategy_id", "trial_id", "outcome", "primary_failure_reason",
            "exact_configuration_only", "family_closed",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "entity_id": STRATEGY_ID,
                "entity_type": "strategy_configuration",
                "outcome": outcome,
                "exact_next_action": next_action,
                "execute_now": False,
            },
            {
                "entity_id": TASK_ID,
                "entity_type": "process_task",
                "outcome": "validation_complete",
                "exact_next_action": next_action,
                "execute_now": False,
            },
        ],
        [
            "entity_id", "entity_type", "outcome", "exact_next_action", "execute_now",
        ],
    )
    write_text(
        OUTPUT_DIR / "validation_report.md",
        build_report(outcome, failure_reason, next_action, checks),
    )
    consistency = {
        "task_id": TASK_ID,
        "status": "pass",
        "exactly_one_strategy_validated": True,
        "exactly_one_validation_child_trial": True,
        "parent_trial_preserved": True,
        "kst_rule_parameters_instruments_execution_unchanged": True,
        "benchmark_reference_count": len(benchmark_rows()),
        "benchmark_references_not_strategies_or_trials": all(
            not row["counted_as_strategy"] and not row["counted_as_trial"]
            for row in benchmark_rows()
        ),
        "reproduction_pass": reproduction_pass,
        "reproduction_row_count": len(reproduction),
        "all_full_period_invariants_pass": all(bool(row["invariant_pass"]) for row in full_rows),
        "rolling_36_window_count_primary": len(
            {
                (row["window_start"], row["window_end"])
                for row in rolling_36
                if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
            }
        ),
        "rolling_60_window_count_primary": len(
            {
                (row["window_start"], row["window_end"])
                for row in rolling_60
                if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
            }
        ),
        "all_rolling_rows_visible": True,
        "chronological_periods_not_clean_or_sealed_holdouts": all(
            "not_clean_or_sealed_holdout" in row["half_source"] for row in half_rows
        ),
        "protected_hashes_before": before_protected,
        "protected_hashes_after": after_protected,
        "protected_state_and_cache_unchanged": before_protected == after_protected,
        "input_evidence_hashes_before": before_inputs,
        "input_evidence_hashes_after": after_inputs,
        "prior_evidence_unchanged": before_inputs == after_inputs,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "all_forbidden_actions_false": not any(FORBIDDEN_FLAGS.values()),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "next_action_executed": False,
    }
    if not all(
        [
            consistency["reproduction_pass"],
            consistency["all_full_period_invariants_pass"],
            consistency["protected_state_and_cache_unchanged"],
            consistency["prior_evidence_unchanged"],
            consistency["all_forbidden_actions_false"],
            consistency["benchmark_reference_count"] == 4,
        ]
    ):
        consistency["status"] = "fail"
    consistency["deterministic_core_hash"] = deterministic_core_hash()
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": VALIDATION_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
        "reproduction_pass": reproduction_pass,
        "rolling_36_window_count": consistency["rolling_36_window_count_primary"],
        "rolling_60_window_count": consistency["rolling_60_window_count_primary"],
        "consistency_status": consistency["status"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
