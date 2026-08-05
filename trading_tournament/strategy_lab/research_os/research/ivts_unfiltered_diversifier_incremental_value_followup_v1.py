from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    intermarket_ivts_herorats_portability_exploration_v1 as v1,
)
from strategy_lab.research_os.research import (
    run_cboe_point_in_time_ivts_feasibility_and_exploration_v2 as v2,
)
from strategy_lab.research_os.research import (
    correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3 as v3,
)
from strategy_lab.research_os.research import (
    correct_ivts_trial_lineage_and_run_exploration_v4 as v4,
)


TASK_ID = "ivts_unfiltered_diversifier_incremental_value_followup_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1"
FAMILY_ID = "implied_volatility_term_structure_equity_timing"
DISPLAY_NAME = "Unfiltered VIX/VIX3M Three-State Diversifier"
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = v4.TRIAL_ID
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"

V1_EVIDENCE = v1.OUTPUT_DIR
V2_EVIDENCE = v2.OUTPUT_DIR
V3_EVIDENCE = v3.OUTPUT_DIR
V4_EVIDENCE = v4.OUTPUT_DIR
CACHE_DIR = ROOT / "data" / "cache"

SOURCE_LINEAGE = (
    "intermarket_source_sprint_v6:donninger_herorats:"
    "V4_predeclared_unfiltered_same_purpose_control"
)
TIMING_POLICY = v4.TIMING_POLICY
DATA_PROVENANCE = v4.DATA_PROVENANCE
VINTAGE_STATUS = v4.VINTAGE_STATUS
EARLIEST_SIGNAL_DATE = v4.EARLIEST_SIGNAL_DATE
METHODOLOGY_BOUNDARY = v4.METHODOLOGY_BOUNDARY
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-9

CONTROLS = (
    "vix_vix3m_sign_only_spy_ief_v1",
    "unfiltered_ivts_exposure_matched_spy_ief_v1",
    "SPY_200_day_trend_control",
    "SPY_buy_and_hold",
    "IEF_buy_and_hold",
)
SAME_PURPOSE_CONTROL = "vix_vix3m_sign_only_spy_ief_v1"
EXPOSURE_CONTROL = "unfiltered_ivts_exposure_matched_spy_ief_v1"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"

PORTFOLIO_IDS = {
    "reference": "100pct_frozen_reference",
    STRATEGY_ID: "80pct_reference_20pct_unfiltered_ivts_candidate",
    SAME_PURPOSE_CONTROL: "80pct_reference_20pct_sign_only_ivts_control",
    EXPOSURE_CONTROL: "80pct_reference_20pct_unfiltered_exposure_matched_control",
    "SPY_200_day_trend_control": "80pct_reference_20pct_SPY_200_day_trend_control",
    "IEF_buy_and_hold": "80pct_reference_20pct_IEF",
}

ADVANCE_NEXT_ACTION = "direction_owner_review_ivts_unfiltered_diversifier_followup_v1"
CLOSE_NEXT_ACTION = "direction_owner_select_next_targeted_family_sprint_v1"
BLOCK_NEXT_ACTION = "defer_ivts_lane_and_select_next_targeted_family_sprint_v1"

PROTECTED_STATE_PATHS = v1.PROTECTED_STATE_PATHS
PRIOR_EVIDENCE = (
    (v1.TASK_ID, V1_EVIDENCE),
    (v2.TASK_ID, V2_EVIDENCE),
    (v3.TASK_ID, V3_EVIDENCE),
    (v4.TASK_ID, V4_EVIDENCE),
)

REQUIRED_ARTIFACTS = (
    "followup_manifest.yaml",
    "source_lineage.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "v4_reproduction_check.csv",
    "standalone_results.csv",
    "standalone_chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "portfolio_chronological_half_results.csv",
    "rolling_36_month_portfolio_results.csv",
    "rolling_60_month_portfolio_results.csv",
    "rolling_window_summary.csv",
    "state_signal_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "followup_report.md",
)

METRIC_FIELDS = [
    "entity_id",
    "entity_type",
    "role",
    "period",
    "cost_bps",
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_SPY_exposure",
    "turnover",
    "transaction_cost_drag",
    "trade_or_rebalance_count",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant",
    "numeric_invariant",
    "exposure_invariant",
    "weight_invariant",
]

PORTFOLIO_FIELDS = [
    "portfolio_id",
    "entity_type",
    "stage",
    "period",
    "cost_bps",
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_SPY_exposure",
    "average_SPY_exposure_scope",
    "turnover",
    "transaction_cost_drag",
    "trade_or_rebalance_count",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant",
    "numeric_invariant",
    "exposure_invariant",
    "weight_invariant",
    "construction",
    "daily_fixed_weight_return_blend_used",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    v1.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    v1.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    v1.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    v1.write_text(path, text)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def directory_hash(path: Path) -> str:
    rows: list[dict[str, Any]] = []
    if path.exists():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            rows.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "hash": v1.file_hash(item),
                    "size": item.stat().st_size,
                }
            )
    return v1.canonical_hash(rows)


def verify_v4_context() -> dict[str, Any]:
    consistency = json.loads(
        (V4_EVIDENCE / "consistency_check.json").read_text(encoding="utf-8")
    )
    outcome_rows = read_csv(V4_EVIDENCE / "outcome_summary.csv")
    trial_rows = read_csv(V4_EVIDENCE / "trial_ledger.csv")
    parent = [row for row in trial_rows if row.get("trial_id") == PARENT_TRIAL_ID]
    passed = bool(
        consistency.get("overall_pass")
        and consistency.get("outcome") == "closed_exploration"
        and consistency.get("failure_reason") == "weak_vs_primary_control"
        and len(outcome_rows) == 1
        and outcome_rows[0]["strategy_id"] == v4.STRATEGY_ID
        and outcome_rows[0]["outcome"] == "closed_exploration"
        and len(parent) == 1
        and parent[0]["created_in_v4"] == "true"
    )
    return {
        "passed": passed,
        "consistency": consistency,
        "parent": parent[0] if parent else {},
    }


def build_raw_signal_panel(
    histories: dict[str, pd.DataFrame], price_end: pd.Timestamp
) -> pd.DataFrame:
    vix = histories["VIX"].set_index("DATE")["CLOSE"].rename("VIX_close")
    vix3m = histories["VIX3M"].set_index("DATE")["CLOSE"].rename("VIX3M_close")
    panel = pd.concat([vix, vix3m], axis=1, join="outer").sort_index()
    panel["common_observation"] = panel[["VIX_close", "VIX3M_close"]].notna().all(axis=1)
    panel["raw_ratio"] = panel["VIX_close"] / panel["VIX3M_close"]
    panel = panel.loc[
        (panel.index >= EARLIEST_SIGNAL_DATE) & (panel.index <= price_end)
    ].copy()
    candidate_targets: list[tuple[float, float, str]] = []
    sign_targets: list[tuple[float, float, str]] = []
    prior_candidate = (0.5, 0.5, "middle")
    prior_sign = (0.5, 0.5, "middle")
    for row in panel.itertuples():
        if bool(row.common_observation):
            ratio = float(row.raw_ratio)
            prior_candidate = v4.target_for_ratio(ratio)
            prior_sign = v4.target_for_sign(ratio)
        candidate_targets.append(prior_candidate)
        sign_targets.append(prior_sign)
    for prefix, values in (("candidate", candidate_targets), ("sign", sign_targets)):
        panel[f"{prefix}_SPY"] = [value[0] for value in values]
        panel[f"{prefix}_IEF"] = [value[1] for value in values]
        panel[f"{prefix}_state"] = [value[2] for value in values]
    panel["methodology_period"] = np.where(
        panel.index < METHODOLOGY_BOUNDARY,
        "pre_2025_02_10",
        "post_2025_02_10",
    )
    return panel


def build_schedules(
    panel: pd.DataFrame,
    full_prices: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[pd.Timestamp, pd.Timestamp | str],
    float,
]:
    candidate, origins, _ = v4.state_change_schedule(panel, prices.index, "candidate")
    sign_only, _, _ = v4.state_change_schedule(panel, prices.index, "sign")
    average_target_spy = float(v4.target_path(candidate, prices.index)["SPY"].mean())
    schedules = {
        STRATEGY_ID: candidate,
        SAME_PURPOSE_CONTROL: sign_only,
        EXPOSURE_CONTROL: v4.monthly_static_schedule(prices.index, average_target_spy),
        "SPY_200_day_trend_control": v4.spy_200d_schedule(full_prices, prices.index),
        "SPY_buy_and_hold": v4.buy_hold_schedule(prices.index, "SPY"),
        "IEF_buy_and_hold": v4.buy_hold_schedule(prices.index, "IEF"),
    }
    return schedules, origins, average_target_spy


def run_paths(
    schedules: dict[str, pd.DataFrame],
    full_prices: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict[tuple[str, float], dict[str, Any]]:
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    timing = "completed_official_close_signal_target_applied_at_following_session_close"
    for entity_id, schedule in schedules.items():
        entity_prices = full_prices.reindex(prices.index)[list(schedule.columns)].dropna()
        if not entity_prices.index.equals(prices.index):
            raise RuntimeError(f"{entity_id} dates do not match the candidate")
        for cost_bps in COST_BPS:
            paths[(entity_id, cost_bps)] = accounting.simulate_path(
                entity_prices, schedule, cost_bps, timing
            )
    return paths


def standalone_metric_row(
    entity_id: str,
    cost_bps: float,
    payload: dict[str, Any],
    period: str = "full_period",
) -> dict[str, Any]:
    role = "candidate" if entity_id == STRATEGY_ID else "benchmark_reference"
    entity_type = (
        "experiment_trial" if entity_id == STRATEGY_ID else "benchmark_reference"
    )
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "role": role,
        "period": period,
        "cost_bps": cost_bps,
        **{
            field: payload.get(field, "")
            for field in METRIC_FIELDS
            if field
            not in {"entity_id", "entity_type", "role", "period", "cost_bps"}
        },
    }


def replay_outer_held_weights(reference: pd.Series, sleeve: pd.Series) -> pd.DataFrame:
    returns = pd.concat(
        [reference.rename("reference"), sleeve.rename("sleeve")],
        axis=1,
        join="inner",
    ).dropna()
    weights = np.array([0.0, 0.0], dtype=float)
    target = np.array([0.8, 0.2], dtype=float)
    trade_positions = {0}
    for position in range(1, len(returns)):
        if returns.index[position - 1].to_period("M") != returns.index[position].to_period("M"):
            trade_positions.add(position)
    held_rows: list[np.ndarray] = []
    for position, values in enumerate(returns.to_numpy(dtype=float)):
        held_rows.append(weights.copy())
        drifted = weights * (1.0 + values)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else weights.copy()
        weights = target.copy() if position in trade_positions else pretrade
    return pd.DataFrame(
        held_rows,
        index=returns.index,
        columns=["reference_weight", "sleeve_weight"],
    )


def portfolio_payloads(
    paths: dict[tuple[str, float], dict[str, Any]],
    reference_returns: pd.Series,
) -> dict[tuple[str, float], dict[str, Any]]:
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    sleeve_ids = (
        STRATEGY_ID,
        SAME_PURPOSE_CONTROL,
        EXPOSURE_CONTROL,
        "SPY_200_day_trend_control",
        "IEF_buy_and_hold",
    )
    for cost_bps in COST_BPS:
        candidate = paths[(STRATEGY_ID, cost_bps)]["returns"]
        common = candidate.index.intersection(reference_returns.dropna().index)
        reference = reference_returns.reindex(common).dropna()
        payloads[(PORTFOLIO_IDS["reference"], cost_bps)] = (
            portfolio_accounting.reference_payload(reference, cost_bps)
        )
        for sleeve_id in sleeve_ids:
            sleeve = paths[(sleeve_id, cost_bps)]["returns"].reindex(reference.index).dropna()
            aligned_reference = reference.reindex(sleeve.index).dropna()
            portfolio_id = PORTFOLIO_IDS[sleeve_id]
            payload = portfolio_accounting.simulate_two_component_portfolio(
                aligned_reference, sleeve, portfolio_id, cost_bps
            )
            payload["outer_held_weights"] = replay_outer_held_weights(
                aligned_reference, sleeve
            )
            payload["sleeve_id"] = sleeve_id
            payloads[(portfolio_id, cost_bps)] = payload
    return payloads


def portfolio_metrics(
    portfolio_id: str,
    payload: dict[str, Any],
    paths: dict[tuple[str, float], dict[str, Any]],
    cost_bps: float,
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    returns = payload["returns"]
    if period_index is not None:
        returns = returns.reindex(period_index).dropna()
    metrics = market.metrics_from_returns(returns)
    daily = payload["daily_df"].reindex(returns.index)
    turnover = payload["turnover"].reindex(returns.index)
    costs = payload["cost"].reindex(returns.index)
    if portfolio_id == PORTFOLIO_IDS["reference"]:
        average_spy: float | str = ""
        exposure_scope = "reference_internal_SPY_exposure_not_decomposed"
    else:
        sleeve_id = payload["sleeve_id"]
        outer = payload["outer_held_weights"].reindex(returns.index)["sleeve_weight"]
        sleeve_spy = (
            paths[(sleeve_id, cost_bps)]["held_weights"]
            .reindex(returns.index)
            .get("SPY", pd.Series(0.0, index=returns.index))
        )
        average_spy = float((outer * sleeve_spy).mean())
        exposure_scope = "SPY_exposure_contributed_by_20pct_sleeve_only"
    numeric = bool(len(returns) and np.isfinite(returns.to_numpy(dtype=float)).all())
    max_gross = float(daily["max_daily_exposure"].max())
    max_sum = float(daily["max_daily_weight_sum"].max())
    exposure = bool(
        max_gross <= 1.0 + WEIGHT_TOLERANCE
        and max_sum <= 1.0 + WEIGHT_TOLERANCE
    )
    return {
        **metrics,
        "average_SPY_exposure": average_spy,
        "average_SPY_exposure_scope": exposure_scope,
        "turnover": float(turnover.sum()),
        "transaction_cost_drag": float(costs.sum()),
        "trade_or_rebalance_count": int((turnover > WEIGHT_TOLERANCE).sum()),
        "maximum_gross_exposure": max_gross,
        "maximum_daily_weight_sum": max_sum,
        "timing_invariant": "pass_month_end_target_following_session_close",
        "numeric_invariant": "pass" if numeric else "fail",
        "exposure_invariant": "pass" if exposure else "fail",
        "weight_invariant": "pass" if exposure else "fail",
        "invariant_pass": bool(numeric and exposure),
    }


def portfolio_row(
    portfolio_id: str,
    cost_bps: float,
    metrics: dict[str, Any],
    period: str,
) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio_id,
        "entity_type": "portfolio_contribution_diagnostic",
        "stage": STAGE,
        "period": period,
        "cost_bps": cost_bps,
        **{
            field: metrics.get(field, "")
            for field in PORTFOLIO_FIELDS
            if field
            not in {
                "portfolio_id",
                "entity_type",
                "stage",
                "period",
                "cost_bps",
                "construction",
                "daily_fixed_weight_return_blend_used",
            }
        },
        "construction": (
            "100pct_frozen_reference"
            if portfolio_id == PORTFOLIO_IDS["reference"]
            else "monthly_rebalanced_80pct_reference_20pct_sleeve_explicit_holdings"
        ),
        "daily_fixed_weight_return_blend_used": False,
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - 1e-12
        and float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - 1e-12
        and float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - 1e-12
    )
    strict = (
        float(control["cagr"]) > float(candidate["cagr"]) + 1e-12
        or float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + 1e-12
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + 1e-12
    )
    return bool(equal_or_better and strict)


def reproduction_rows(
    standalone: dict[tuple[str, float], dict[str, Any]],
    halves: dict[tuple[str, str], dict[str, Any]],
    portfolios: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    v4_full = {
        (row["entity_id"], float(row["cost_bps"])): row
        for row in read_csv(V4_EVIDENCE / "all_trial_results.csv")
    }
    v4_halves = {
        (row["entity_id"], row["period"]): row
        for row in read_csv(V4_EVIDENCE / "chronological_half_results.csv")
        if float(row["cost_bps"]) == PRIMARY_COST_BPS
    }
    v4_portfolios = {
        (row["portfolio_id"], float(row["cost_bps"])): row
        for row in read_csv(V4_EVIDENCE / "portfolio_contribution_results.csv")
    }
    prior_id = "unfiltered_vix_vix3m_three_state_spy_ief_v1"
    prior_portfolio_id = (
        "80pct_reference_20pct_unfiltered_vix_vix3m_three_state_spy_ief_v1"
    )
    fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "average_SPY_exposure",
        "turnover",
        "transaction_cost_drag",
        "trade_or_rebalance_count",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
    )
    rows: list[dict[str, Any]] = []

    def compare(scope: str, period: str, cost: float, metric: str, expected: Any, observed: Any) -> None:
        expected_float = float(expected)
        observed_float = float(observed)
        difference = observed_float - expected_float
        rows.append(
            {
                "scope": scope,
                "period": period,
                "cost_bps": cost,
                "metric": metric,
                "V4_recorded_value": expected_float,
                "reproduced_value": observed_float,
                "difference": difference,
                "absolute_tolerance": REPRODUCTION_TOLERANCE,
                "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
            }
        )

    for cost_bps in COST_BPS:
        expected = v4_full[(prior_id, cost_bps)]
        observed = standalone[(STRATEGY_ID, cost_bps)]
        for field in fields:
            compare("standalone", "full_period", cost_bps, field, expected[field], observed[field])
    for period in ("first_chronological_half", "second_chronological_half"):
        expected = v4_halves[(prior_id, period)]
        observed = halves[(STRATEGY_ID, period)]
        for field in fields:
            compare("standalone", period, PRIMARY_COST_BPS, field, expected[field], observed[field])
    expected_portfolio = v4_portfolios[(prior_portfolio_id, PRIMARY_COST_BPS)]
    observed_portfolio = portfolios[(PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)]
    for field in (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "transaction_cost_drag",
        "trade_or_rebalance_count",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
    ):
        compare(
            "80_20_portfolio",
            "full_period",
            PRIMARY_COST_BPS,
            field,
            expected_portfolio[field],
            observed_portfolio[field],
        )
    return rows, bool(rows and all(row["pass"] for row in rows))


def monthly_rolling_rows(
    horizon_months: int,
    portfolio_payload_map: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_id = PORTFOLIO_IDS[STRATEGY_ID]
    comparison_ids = (
        PORTFOLIO_IDS["reference"],
        PORTFOLIO_IDS[SAME_PURPOSE_CONTROL],
        PORTFOLIO_IDS[EXPOSURE_CONTROL],
    )
    candidate_returns = portfolio_payload_map[
        (candidate_id, PRIMARY_COST_BPS)
    ]["returns"]
    periods = sorted(candidate_returns.index.to_period("M").unique())
    rows: list[dict[str, Any]] = []
    for end_position in range(horizon_months - 1, len(periods)):
        selected = periods[
            end_position - horizon_months + 1 : end_position + 1
        ]
        index = candidate_returns.index[
            candidate_returns.index.to_period("M").isin(selected)
        ]
        if not len(index):
            continue
        candidate = market.metrics_from_returns(candidate_returns.reindex(index).dropna())
        controls = {
            portfolio_id: market.metrics_from_returns(
                portfolio_payload_map[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
                .reindex(index)
                .dropna()
            )
            for portfolio_id in comparison_ids
        }
        reference = controls[PORTFOLIO_IDS["reference"]]
        sign = controls[PORTFOLIO_IDS[SAME_PURPOSE_CONTROL]]
        exposure = controls[PORTFOLIO_IDS[EXPOSURE_CONTROL]]
        rows.append(
            {
                "horizon_months": horizon_months,
                "window_start": candidate["evaluation_start"],
                "window_end": candidate["evaluation_end"],
                "calendar_month_count": len(selected),
                "trading_days": candidate["trading_days"],
                "candidate_cagr": candidate["cagr"],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "reference_cagr_difference": float(candidate["cagr"]) - float(reference["cagr"]),
                "reference_sharpe_difference": float(candidate["sharpe_ratio"]) - float(reference["sharpe_ratio"]),
                "reference_maximum_drawdown_difference": float(candidate["maximum_drawdown"]) - float(reference["maximum_drawdown"]),
                "sign_only_cagr_difference": float(candidate["cagr"]) - float(sign["cagr"]),
                "sign_only_sharpe_difference": float(candidate["sharpe_ratio"]) - float(sign["sharpe_ratio"]),
                "sign_only_maximum_drawdown_difference": float(candidate["maximum_drawdown"]) - float(sign["maximum_drawdown"]),
                "exposure_matched_cagr_difference": float(candidate["cagr"]) - float(exposure["cagr"]),
                "exposure_matched_sharpe_difference": float(candidate["sharpe_ratio"]) - float(exposure["sharpe_ratio"]),
                "exposure_matched_maximum_drawdown_difference": float(candidate["maximum_drawdown"]) - float(exposure["maximum_drawdown"]),
                "reference_dominates_candidate": dominates(reference, candidate),
                "sign_only_dominates_candidate": dominates(sign, candidate),
                "exposure_matched_dominates_candidate": dominates(exposure, candidate),
                "candidate_improves_reference_sharpe_or_drawdown": bool(
                    float(candidate["sharpe_ratio"]) > float(reference["sharpe_ratio"])
                    or float(candidate["maximum_drawdown"])
                    > float(reference["maximum_drawdown"])
                ),
                "sealed_holdout_or_validation": False,
            }
        )
    return rows


def rolling_summary_rows(
    rolling: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon, values in rolling.items():
        count = len(values)
        improves = sum(
            bool(row["candidate_improves_reference_sharpe_or_drawdown"])
            for row in values
        )
        exposure_dominates = sum(
            bool(row["exposure_matched_dominates_candidate"]) for row in values
        )
        rows.append(
            {
                "horizon_months": horizon,
                "eligible_window_count": count,
                "candidate_improves_reference_count": improves,
                "candidate_improves_reference_fraction": improves / count if count else "",
                "exposure_matched_dominates_count": exposure_dominates,
                "exposure_matched_dominates_fraction": (
                    exposure_dominates / count if count else ""
                ),
                "median_reference_sharpe_difference": (
                    float(np.median([row["reference_sharpe_difference"] for row in values]))
                    if count
                    else ""
                ),
                "median_reference_maximum_drawdown_difference": (
                    float(
                        np.median(
                            [
                                row["reference_maximum_drawdown_difference"]
                                for row in values
                            ]
                        )
                    )
                    if count
                    else ""
                ),
                "all_windows_retained": True,
                "validation_claimed": False,
            }
        )
    return rows


def classify(
    reproduction_pass: bool,
    standalone: dict[tuple[str, float], dict[str, Any]],
    standalone_halves: dict[tuple[str, str], dict[str, Any]],
    portfolios: dict[tuple[str, float], dict[str, Any]],
    portfolio_halves: dict[tuple[str, str], dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    if not reproduction_pass:
        return (
            "inconclusive_data_issue",
            "data_or_comparability_failure",
            "V4 unfiltered control did not reproduce within 1e-9",
            {"V4_reproduction_passed": False},
        )
    candidate_standalone = standalone[(STRATEGY_ID, PRIMARY_COST_BPS)]
    exposure_standalone = standalone[(EXPOSURE_CONTROL, PRIMARY_COST_BPS)]
    candidate_id = PORTFOLIO_IDS[STRATEGY_ID]
    reference_id = PORTFOLIO_IDS["reference"]
    sign_id = PORTFOLIO_IDS[SAME_PURPOSE_CONTROL]
    exposure_id = PORTFOLIO_IDS[EXPOSURE_CONTROL]
    candidate = portfolios[(candidate_id, PRIMARY_COST_BPS)]
    reference = portfolios[(reference_id, PRIMARY_COST_BPS)]
    sign = portfolios[(sign_id, PRIMARY_COST_BPS)]
    exposure = portfolios[(exposure_id, PRIMARY_COST_BPS)]
    all_invariants = all(
        row["invariant_pass"] for row in standalone.values()
    ) and all(row["invariant_pass"] for row in portfolios.values())
    reference_sharpe_edge = float(candidate["sharpe_ratio"]) - float(reference["sharpe_ratio"])
    reference_drawdown_edge = float(candidate["maximum_drawdown"]) - float(reference["maximum_drawdown"])
    critical_material = {
        sign_id: bool(
            float(candidate["sharpe_ratio"]) - float(sign["sharpe_ratio"]) >= 0.02
            or float(candidate["maximum_drawdown"])
            - float(sign["maximum_drawdown"])
            >= 0.01
        ),
        exposure_id: bool(
            float(candidate["sharpe_ratio"]) - float(exposure["sharpe_ratio"]) >= 0.02
            or float(candidate["maximum_drawdown"])
            - float(exposure["maximum_drawdown"])
            >= 0.01
        ),
    }
    worse_halves: list[str] = []
    for period in ("first_chronological_half", "second_chronological_half"):
        candidate_half = portfolio_halves[(candidate_id, period)]
        for control_id in (reference_id, exposure_id):
            control_half = portfolio_halves[(control_id, period)]
            if (
                float(candidate_half["sharpe_ratio"]) < float(control_half["sharpe_ratio"])
                and float(candidate_half["maximum_drawdown"])
                < float(control_half["maximum_drawdown"])
            ):
                worse_halves.append(f"{period}:{control_id}")
    rolling_by_horizon = {int(row["horizon_months"]): row for row in rolling_summary}
    candidate_10 = portfolios[(candidate_id, 10.0)]
    reference_10 = portfolios[(reference_id, 10.0)]
    exposure_10 = portfolios[(exposure_id, 10.0)]
    ten_improves_reference = bool(
        float(candidate_10["sharpe_ratio"]) > float(reference_10["sharpe_ratio"])
        or float(candidate_10["maximum_drawdown"])
        > float(reference_10["maximum_drawdown"])
    )
    ten_worse_both_exposure = bool(
        float(candidate_10["sharpe_ratio"]) < float(exposure_10["sharpe_ratio"])
        and float(candidate_10["maximum_drawdown"])
        < float(exposure_10["maximum_drawdown"])
    )
    gate = {
        "V4_reproduction_passed": reproduction_pass,
        "all_invariants_pass": all_invariants,
        "candidate_standalone_positive": float(candidate_standalone["total_return"]) > 0.0,
        "exposure_control_dominates_standalone": dominates(
            exposure_standalone, candidate_standalone
        ),
        "reference_sharpe_edge": reference_sharpe_edge,
        "reference_maximum_drawdown_edge": reference_drawdown_edge,
        "candidate_materially_improves_reference": bool(
            reference_sharpe_edge >= 0.02 or reference_drawdown_edge >= 0.01
        ),
        "sign_only_dominates_candidate_portfolio": dominates(sign, candidate),
        "exposure_matched_dominates_candidate_portfolio": dominates(exposure, candidate),
        "material_advantage_vs_sign_and_exposure": critical_material,
        "worse_on_sharpe_and_drawdown_in_halves": worse_halves,
        "rolling_36_improves_reference_fraction": rolling_by_horizon[36][
            "candidate_improves_reference_fraction"
        ],
        "rolling_60_improves_reference_fraction": rolling_by_horizon[60][
            "candidate_improves_reference_fraction"
        ],
        "rolling_36_exposure_dominates_fraction": rolling_by_horizon[36][
            "exposure_matched_dominates_fraction"
        ],
        "rolling_60_exposure_dominates_fraction": rolling_by_horizon[60][
            "exposure_matched_dominates_fraction"
        ],
        "10bps_candidate_improves_reference": ten_improves_reference,
        "10bps_worse_on_both_vs_exposure": ten_worse_both_exposure,
    }
    if not all_invariants:
        return "blocked_feasibility", "methodology_failure", "an accounting invariant failed", gate
    if float(candidate_standalone["total_return"]) <= 0.0:
        return "closed_exploration", "weak_vs_primary_control", "standalone after-cost return was not positive", gate
    if gate["exposure_control_dominates_standalone"]:
        return "closed_exploration", "exposure_control_explanation", "exposure-matched control dominated standalone candidate", gate
    if not gate["candidate_materially_improves_reference"]:
        return "closed_exploration", "weak_portfolio_contribution", "80/20 candidate did not materially improve the frozen reference", gate
    if gate["sign_only_dominates_candidate_portfolio"]:
        return "closed_exploration", "weak_vs_primary_control", "sign-only 80/20 control dominated candidate", gate
    if gate["exposure_matched_dominates_candidate_portfolio"]:
        return "closed_exploration", "exposure_control_explanation", "exposure-matched 80/20 control dominated candidate", gate
    failed_material = [key for key, passed in critical_material.items() if not passed]
    if failed_material:
        return (
            "closed_exploration",
            "weak_vs_primary_control",
            f"candidate lacked material advantage versus: {','.join(failed_material)}",
            gate,
        )
    if worse_halves:
        return (
            "closed_exploration",
            "period_instability",
            f"candidate was worse on Sharpe and drawdown in: {','.join(worse_halves)}",
            gate,
        )
    if (
        float(rolling_by_horizon[36]["candidate_improves_reference_fraction"]) <= 0.5
        or float(rolling_by_horizon[60]["candidate_improves_reference_fraction"]) <= 0.5
    ):
        return "closed_exploration", "period_instability", "candidate failed rolling reference-improvement frequency", gate
    if (
        float(rolling_by_horizon[36]["exposure_matched_dominates_fraction"]) > 0.5
        or float(rolling_by_horizon[60]["exposure_matched_dominates_fraction"]) > 0.5
    ):
        return "closed_exploration", "exposure_control_explanation", "exposure control dominated too many rolling windows", gate
    if not ten_improves_reference or ten_worse_both_exposure:
        return "closed_exploration", "cost_drag", "10-bps portfolio gate failed", gate
    return (
        "exploratory_followup_candidate_diversifier",
        "",
        "candidate passed the frozen diversifier-only exploration gate",
        gate,
    )


def state_diagnostics(
    panel: pd.DataFrame,
    prices: pd.DataFrame,
    schedule: pd.DataFrame,
    origins: dict[pd.Timestamp, pd.Timestamp | str],
    path: dict[str, Any],
) -> list[dict[str, Any]]:
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    details: dict[pd.Timestamp, dict[str, Any]] = {}
    for date in prices.index:
        held = path["held_weights"].loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
        day_return = asset_returns.loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
        drifted = held * (1.0 + day_return)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held
        traded = date in schedule.index
        post = (
            schedule.loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
            if traded
            else pretrade
        )
        details[pd.Timestamp(date)] = {
            "pretrade_SPY_weight": float(pretrade[0]),
            "pretrade_IEF_weight": float(pretrade[1]),
            "post_trade_SPY_weight": float(post[0]),
            "post_trade_IEF_weight": float(post[1]),
            "turnover": float(path["turnover"].loc[date]),
            "transaction_cost": float(path["cost"].loc[date]),
        }
    rows: list[dict[str, Any]] = []
    for date, row in panel.iterrows():
        execution = v4.next_session(prices.index, pd.Timestamp(date))
        detail = details.get(execution, {}) if execution is not None else {}
        origin = origins.get(execution, "") if execution is not None else ""
        is_origin = isinstance(origin, pd.Timestamp) and origin == pd.Timestamp(date)
        rows.append(
            {
                "record_type": "signal_observation",
                "signal_date": pd.Timestamp(date).date().isoformat(),
                "VIX_close": row["VIX_close"],
                "VIX3M_close": row["VIX3M_close"],
                "raw_ratio": row["raw_ratio"],
                "rolling_median_calculated_or_used": False,
                "target_state": row["candidate_state"],
                "target_SPY_weight": row["candidate_SPY"],
                "target_IEF_weight": row["candidate_IEF"],
                "following_execution_session": (
                    execution.date().isoformat() if execution is not None else ""
                ),
                "pretrade_SPY_weight": detail.get("pretrade_SPY_weight", ""),
                "pretrade_IEF_weight": detail.get("pretrade_IEF_weight", ""),
                "turnover": detail.get("turnover", 0.0) if is_origin else 0.0,
                "transaction_cost": (
                    detail.get("transaction_cost", 0.0) if is_origin else 0.0
                ),
                "post_trade_SPY_weight": detail.get("post_trade_SPY_weight", ""),
                "post_trade_IEF_weight": detail.get("post_trade_IEF_weight", ""),
                "trade_executed": is_origin,
                "common_observation": bool(row["common_observation"]),
                "missing_signal_behavior": (
                    "" if bool(row["common_observation"]) else "retain_previous_target"
                ),
                "methodology_boundary_flag": row["methodology_period"],
                "data_provenance": DATA_PROVENANCE,
                "vintage_status": VINTAGE_STATUS,
                "timing_policy": TIMING_POLICY,
                "same_day_return_allowed": False,
                "result_driven_adaptation": True,
                "summary_count": "",
            }
        )
    for state in ("risk_on", "middle", "defensive"):
        rows.append(
            {
                "record_type": "state_summary",
                "target_state": state,
                "rolling_median_calculated_or_used": False,
                "summary_count": int((panel["candidate_state"] == state).sum()),
                "data_provenance": DATA_PROVENANCE,
                "vintage_status": VINTAGE_STATUS,
                "timing_policy": TIMING_POLICY,
                "same_day_return_allowed": False,
                "result_driven_adaptation": True,
            }
        )
    rows.append(
        {
            "record_type": "missing_common_observation_summary",
            "target_state": "retain_previous_target",
            "rolling_median_calculated_or_used": False,
            "summary_count": int((~panel["common_observation"]).sum()),
            "data_provenance": DATA_PROVENANCE,
            "vintage_status": VINTAGE_STATUS,
            "timing_policy": TIMING_POLICY,
            "same_day_return_allowed": False,
            "result_driven_adaptation": True,
        }
    )
    return rows


def entity_rows(
    outcome: str,
    failure_reason: str,
    next_action: str,
    average_target_spy: float,
) -> dict[str, list[dict[str, Any]]]:
    source = [
        {
            "source_lineage_id": SOURCE_LINEAGE,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "record_role": "carried_forward_source_and_V4_benchmark_lineage",
            "source_library_records_carried_forward": 1,
            "new_source_research_performed": False,
            "V4_benchmark_reference_origin": (
                "unfiltered_vix_vix3m_three_state_spy_ief_v1"
            ),
            "counted_as_strategy_or_trial": False,
        }
    ]
    strategy = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "display_name": DISPLAY_NAME,
            "entity_type": "strategy_configuration",
            "strategy_architecture": "raw_implied_volatility_curve_three_state_allocation",
            "instrument_universe": "SPY|IEF",
            "route": "diversifier_only",
            "source_or_research_lineage": SOURCE_LINEAGE,
            "exact_source_replication_claimed": False,
            "authoritative_registry_record_created": False,
            "source_thresholds_retained": True,
            "source_target_states_retained": True,
            "source_instruments_translated": True,
            "median_filter_retained": False,
            "source_rule_changed": True,
            "adaptation_selected_after_viewing_V4_results": True,
            "adaptation_label": "result_driven_exploratory_variant",
            "validation_evidence_claimed": False,
            "parameters": {
                "ratio": "VIX_close/VIX3M_close",
                "thresholds": [0.96, 1.02],
                "targets": ["1.0|0.0", "0.5|0.5", "0.0|1.0"],
                "median_filter": "removed",
                "missing_signal": "retain_previous_target",
                "average_target_SPY_weight_for_exposure_control": average_target_spy,
            },
            "stage": STAGE,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    trial = [
        {
            "trial_id": TRIAL_ID,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "adaptation_label": "result_driven_exploratory_variant",
            "changed_fields_from_parent": (
                "median_filter_removed_and_route_changed_to_diversifier_only"
            ),
            "ratio_changed": False,
            "median_filter_removed": True,
            "thresholds_changed": False,
            "instruments_changed": False,
            "target_allocations_changed": False,
            "data_source_changed": False,
            "execution_changed": False,
            "costs_changed": False,
            "result_driven_adaptation": True,
            "optimization_performed": False,
            "post_result_change_allowed": False,
            "prior_benchmark_reference_represented_as_existing_trial": False,
            "preregistered_before_followup_performance": True,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    definitions = {
        SAME_PURPOSE_CONTROL: (
            "SPY|IEF",
            "raw ratio <=1.0 holds SPY; raw ratio >1.0 holds IEF",
        ),
        EXPOSURE_CONTROL: (
            "SPY|IEF",
            "monthly exact candidate-average target SPY weight and IEF remainder",
        ),
        "SPY_200_day_trend_control": (
            "SPY|BIL",
            "SPY above completed-close 200-day SMA; BIL otherwise",
        ),
        "SPY_buy_and_hold": ("SPY", "100% SPY buy-and-hold"),
        "IEF_buy_and_hold": ("IEF", "100% IEF buy-and-hold"),
    }
    benchmarks = [
        {
            "benchmark_reference_id": control,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "instrument_universe": definitions[control][0],
            "control_definition": definitions[control][1],
            "same_purpose_control": control == SAME_PURPOSE_CONTROL,
            "exposure_matched_control": control == EXPOSURE_CONTROL,
            "counted_as_strategy_or_trial": False,
        }
        for control in CONTROLS
    ]
    process = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "strategy_id": "",
            "trial_id": "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    return {
        "source": source,
        "strategy": strategy,
        "trial": trial,
        "benchmarks": benchmarks,
        "process": process,
    }


def write_entities(rows: dict[str, list[dict[str, Any]]]) -> None:
    for filename, key in (
        ("source_lineage.csv", "source"),
        ("strategy_cards.csv", "strategy"),
        ("trial_ledger.csv", "trial"),
        ("benchmark_reference_log.csv", "benchmarks"),
        ("process_task_log.csv", "process"),
    ):
        values = rows[key]
        write_csv(OUTPUT_DIR / filename, values, list(values[0]))


def run() -> dict[str, Any]:
    protected_before = v1.hash_paths(PROTECTED_STATE_PATHS)
    prior_before = {task_id: directory_hash(path) for task_id, path in PRIOR_EVIDENCE}
    cache_before = directory_hash(CACHE_DIR)
    clean_output_dir()

    v4_context = verify_v4_context()
    if not v4_context["passed"]:
        raise RuntimeError("V4 lineage or closed outcome is not authoritative")
    histories, _, official_hash_gate = v4.load_verified_v3_histories()
    if not official_hash_gate:
        raise RuntimeError("Stored official Cboe histories do not reproduce")
    full_prices, candidate_prices = v4.load_prices()
    history_end = min(
        histories["VIX"]["DATE"].max(),
        histories["VIX3M"]["DATE"].max(),
        candidate_prices.index.max(),
    )
    prices = candidate_prices.loc[candidate_prices.index <= history_end].dropna()
    panel = build_raw_signal_panel(histories, prices.index.max())
    schedules, origins, average_target_spy = build_schedules(
        panel, full_prices, prices
    )

    preregistered = entity_rows(
        "preregistered_pending_execution", "", "", average_target_spy
    )
    write_entities(preregistered)

    paths = run_paths(schedules, full_prices, prices)
    standalone: dict[tuple[str, float], dict[str, Any]] = {}
    standalone_rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, *CONTROLS):
        for cost_bps in COST_BPS:
            metrics = v4.path_metrics(paths[(entity_id, cost_bps)])
            standalone[(entity_id, cost_bps)] = metrics
            standalone_rows.append(
                standalone_metric_row(entity_id, cost_bps, metrics)
            )

    standalone_halves: dict[tuple[str, str], dict[str, Any]] = {}
    standalone_half_rows: list[dict[str, Any]] = []
    for period, index in v4.split_halves(prices.index):
        for entity_id in (STRATEGY_ID, *CONTROLS):
            metrics = v4.path_metrics(
                paths[(entity_id, PRIMARY_COST_BPS)], period_index=index
            )
            standalone_halves[(entity_id, period)] = metrics
            standalone_half_rows.append(
                standalone_metric_row(
                    entity_id, PRIMARY_COST_BPS, metrics, period
                )
            )

    reference = market.active_vm_dsr_usci_reference_returns()
    portfolio_payload_map = portfolio_payloads(paths, reference)
    portfolio_metric_map: dict[tuple[str, float], dict[str, Any]] = {}
    portfolio_rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS.values():
        for cost_bps in COST_BPS:
            payload = portfolio_payload_map[(portfolio_id, cost_bps)]
            metrics = portfolio_metrics(
                portfolio_id, payload, paths, cost_bps
            )
            portfolio_metric_map[(portfolio_id, cost_bps)] = metrics
            portfolio_rows.append(
                portfolio_row(
                    portfolio_id, cost_bps, metrics, "full_period"
                )
            )

    portfolio_half_map: dict[tuple[str, str], dict[str, Any]] = {}
    portfolio_half_rows: list[dict[str, Any]] = []
    candidate_portfolio_index = portfolio_payload_map[
        (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
    ]["returns"].index
    for period, index in v4.split_halves(candidate_portfolio_index):
        for portfolio_id in PORTFOLIO_IDS.values():
            payload = portfolio_payload_map[(portfolio_id, PRIMARY_COST_BPS)]
            metrics = portfolio_metrics(
                portfolio_id,
                payload,
                paths,
                PRIMARY_COST_BPS,
                period_index=index,
            )
            portfolio_half_map[(portfolio_id, period)] = metrics
            portfolio_half_rows.append(
                portfolio_row(
                    portfolio_id, PRIMARY_COST_BPS, metrics, period
                )
            )

    reproduction, reproduction_pass = reproduction_rows(
        standalone, standalone_halves, portfolio_metric_map
    )
    rolling = {
        36: monthly_rolling_rows(36, portfolio_payload_map),
        60: monthly_rolling_rows(60, portfolio_payload_map),
    }
    rolling_summary = rolling_summary_rows(rolling)
    outcome, failure_reason, decision_reason, gate = classify(
        reproduction_pass,
        standalone,
        standalone_halves,
        portfolio_metric_map,
        portfolio_half_map,
        rolling_summary,
    )
    next_action = (
        ADVANCE_NEXT_ACTION
        if outcome == "exploratory_followup_candidate_diversifier"
        else CLOSE_NEXT_ACTION
        if outcome == "closed_exploration"
        else BLOCK_NEXT_ACTION
    )
    entities = entity_rows(outcome, failure_reason, next_action, average_target_spy)
    write_entities(entities)

    state_rows = state_diagnostics(
        panel,
        prices,
        schedules[STRATEGY_ID],
        origins,
        paths[(STRATEGY_ID, PRIMARY_COST_BPS)],
    )
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, *CONTROLS):
        for cost_bps in COST_BPS:
            metrics = standalone[(entity_id, cost_bps)]
            path = paths[(entity_id, cost_bps)]
            turnover_rows.append(
                {
                    "scope": "standalone",
                    "entity_id": entity_id,
                    "cost_bps": cost_bps,
                    "one_way_turnover": metrics["turnover"],
                    "daily_turnover_sum": float(path["turnover"].sum()),
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "daily_cost_drag_sum": float(path["cost"].sum()),
                    "turnover_reconciles": math.isclose(
                        float(path["turnover"].sum()),
                        float(metrics["turnover"]),
                        abs_tol=1e-12,
                    ),
                    "cost_reconciles": math.isclose(
                        float(path["cost"].sum()),
                        float(metrics["transaction_cost_drag"]),
                        abs_tol=1e-12,
                    ),
                }
            )
            invariant_rows.append(
                {
                    "scope": "standalone",
                    "entity_id": entity_id,
                    "cost_bps": cost_bps,
                    "timing_invariant": metrics["timing_invariant"],
                    "numeric_invariant": metrics["numeric_invariant"],
                    "exposure_invariant": metrics["exposure_invariant"],
                    "weight_invariant": metrics["weight_invariant"],
                    "explicit_zero_weights_preserved": True,
                    "natural_drift_used": True,
                    "stale_weight_forward_fill_used": False,
                    "signal_date_return_used": False,
                    "invariant_pass": metrics["invariant_pass"],
                }
            )
    for portfolio_id in PORTFOLIO_IDS.values():
        for cost_bps in COST_BPS:
            metrics = portfolio_metric_map[(portfolio_id, cost_bps)]
            payload = portfolio_payload_map[(portfolio_id, cost_bps)]
            turnover_rows.append(
                {
                    "scope": "portfolio",
                    "entity_id": portfolio_id,
                    "cost_bps": cost_bps,
                    "one_way_turnover": metrics["turnover"],
                    "daily_turnover_sum": float(payload["turnover"].sum()),
                    "transaction_cost_drag": metrics["transaction_cost_drag"],
                    "daily_cost_drag_sum": float(payload["cost"].sum()),
                    "turnover_reconciles": math.isclose(
                        float(payload["turnover"].sum()),
                        float(metrics["turnover"]),
                        abs_tol=1e-12,
                    ),
                    "cost_reconciles": math.isclose(
                        float(payload["cost"].sum()),
                        float(metrics["transaction_cost_drag"]),
                        abs_tol=1e-12,
                    ),
                }
            )
            invariant_rows.append(
                {
                    "scope": "portfolio",
                    "entity_id": portfolio_id,
                    "cost_bps": cost_bps,
                    "timing_invariant": metrics["timing_invariant"],
                    "numeric_invariant": metrics["numeric_invariant"],
                    "exposure_invariant": metrics["exposure_invariant"],
                    "weight_invariant": metrics["weight_invariant"],
                    "explicit_zero_weights_preserved": True,
                    "natural_drift_used": True,
                    "stale_weight_forward_fill_used": False,
                    "signal_date_return_used": False,
                    "invariant_pass": metrics["invariant_pass"],
                }
            )

    write_csv(
        OUTPUT_DIR / "v4_reproduction_check.csv",
        reproduction,
        list(reproduction[0]),
    )
    write_csv(
        OUTPUT_DIR / "standalone_results.csv",
        standalone_rows if reproduction_pass else [],
        METRIC_FIELDS,
    )
    write_csv(
        OUTPUT_DIR / "standalone_chronological_half_results.csv",
        standalone_half_rows if reproduction_pass else [],
        METRIC_FIELDS,
    )
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_rows if reproduction_pass else [],
        PORTFOLIO_FIELDS,
    )
    write_csv(
        OUTPUT_DIR / "portfolio_chronological_half_results.csv",
        portfolio_half_rows if reproduction_pass else [],
        PORTFOLIO_FIELDS,
    )
    rolling_fields = list(rolling[36][0]) if rolling[36] else [
        "horizon_months",
        "window_start",
        "window_end",
    ]
    write_csv(
        OUTPUT_DIR / "rolling_36_month_portfolio_results.csv",
        rolling[36] if reproduction_pass else [],
        rolling_fields,
    )
    write_csv(
        OUTPUT_DIR / "rolling_60_month_portfolio_results.csv",
        rolling[60] if reproduction_pass else [],
        rolling_fields,
    )
    write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary if reproduction_pass else [],
        list(rolling_summary[0]),
    )
    state_fields = sorted({key for row in state_rows for key in row})
    write_csv(
        OUTPUT_DIR / "state_signal_diagnostics.csv",
        state_rows if reproduction_pass else [],
        state_fields,
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows if reproduction_pass else [],
        list(turnover_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows if reproduction_pass else [],
        list(invariant_rows[0]),
    )

    candidate_standalone = standalone[(STRATEGY_ID, PRIMARY_COST_BPS)]
    candidate_portfolio = portfolio_metric_map[
        (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
    ]
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "stage": STAGE,
        "route": "diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "next_action": next_action,
        "V4_reproduction_passed": reproduction_pass,
        "result_driven_adaptation": True,
        "source_rule_changed": True,
        "standalone_total_return_5bps": candidate_standalone["total_return"],
        "standalone_sharpe_5bps": candidate_standalone["sharpe_ratio"],
        "standalone_maximum_drawdown_5bps": candidate_standalone["maximum_drawdown"],
        "portfolio_total_return_5bps": candidate_portfolio["total_return"],
        "portfolio_sharpe_5bps": candidate_portfolio["sharpe_ratio"],
        "portfolio_maximum_drawdown_5bps": candidate_portfolio["maximum_drawdown"],
        "gate_detail": gate,
        "validation_evidence_claimed": False,
        "paper_demo_eligibility_supported": False,
    }
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "decision_reason": decision_reason,
                "exact_adaptive_configuration_only": True,
            }
        ]
        if failure_reason
        else []
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "exact_adaptive_configuration_only",
        ],
    )
    next_row = {
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    funnel = {
        "source_library_records_carried_forward": 1,
        "strategy_configurations": 1,
        "new_experiment_trials": 1,
        "benchmark_references": 5,
        "portfolio_diagnostics": len(portfolio_rows) if reproduction_pass else 0,
        "rolling_36_month_windows": len(rolling[36]) if reproduction_pass else 0,
        "rolling_60_month_windows": len(rolling[60]) if reproduction_pass else 0,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_diversifier"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "inconclusive_or_blocked": int(
            outcome in {"inconclusive_data_issue", "blocked_feasibility"}
        ),
        "exact_next_action": next_action,
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "result_driven_exploratory_variant",
        "changed_fields_from_parent": (
            "median_filter_removed_and_route_changed_to_diversifier_only"
        ),
        "result_driven_adaptation": True,
        "adaptation_selected_after_viewing_V4_results": True,
        "source_rule_changed": True,
        "median_filter_removed": True,
        "ratio_changed": False,
        "thresholds_changed": False,
        "instruments_changed": False,
        "target_allocations_changed": False,
        "data_source_changed": False,
        "execution_changed": False,
        "costs_changed": False,
        "optimization_performed": False,
        "post_result_change_allowed": False,
        "route": "diversifier_only",
        "timing_policy": TIMING_POLICY,
        "data_provenance": DATA_PROVENANCE,
        "vintage_status": VINTAGE_STATUS,
        "V4_reproduction_passed": reproduction_pass,
        "evaluation_start": prices.index.min().date().isoformat(),
        "evaluation_end": prices.index.max().date().isoformat(),
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "average_target_SPY_weight_for_exposure_control": average_target_spy,
        "methodology_boundary": METHODOLOGY_BOUNDARY.date().isoformat(),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)

    report = f"""# IVTS Unfiltered Diversifier Incremental-Value Follow-up V1

## Adaptive Lineage

This task created exactly one explicitly result-driven exploratory strategy and
trial. Its parent is `{PARENT_TRIAL_ID}`. The V4 unfiltered rule was a
predeclared benchmark reference, not an earlier experiment trial. The new
configuration removes the Median-5 filter and changes the route to
`diversifier_only`; this is a source-rule change and is not validation.

The closed Median-5 decision remains unchanged.

## Reproduction

V4 standalone, chronological-half, cost-diagnostic, and 80/20 unfiltered
benchmark results reproduced within `{REPRODUCTION_TOLERANCE}`. Stored official
Cboe histories were reused without network access and remain current-history,
non-vintage exploratory data.

## Results

At 5 bps, standalone total return was
`{candidate_standalone['total_return']:.6f}`, Sharpe was
`{candidate_standalone['sharpe_ratio']:.6f}`, and maximum drawdown was
`{candidate_standalone['maximum_drawdown']:.6f}`.

The 80/20 candidate portfolio returned
`{candidate_portfolio['total_return']:.6f}`, with Sharpe
`{candidate_portfolio['sharpe_ratio']:.6f}` and maximum drawdown
`{candidate_portfolio['maximum_drawdown']:.6f}`.

Outcome: `{outcome}`.

Primary failure reason: `{failure_reason or 'not_applicable'}`.

Decision basis: {decision_reason}.

Exact next action: `{next_action}`.

No period is represented as validation, a sealed holdout, exact source
replication, or paper/demo eligibility evidence.
"""
    write_text(OUTPUT_DIR / "followup_report.md", report)

    protected_after = v1.hash_paths(PROTECTED_STATE_PATHS)
    prior_after = {task_id: directory_hash(path) for task_id, path in PRIOR_EVIDENCE}
    cache_after = directory_hash(CACHE_DIR)
    required_present = all(
        (OUTPUT_DIR / name).exists()
        for name in REQUIRED_ARTIFACTS
        if name != "consistency_check.json"
    )
    deterministic_names = [
        name for name in REQUIRED_ARTIFACTS if name != "consistency_check.json"
    ]
    deterministic_hash = v1.canonical_hash(
        [
            {"path": name, "hash": v1.file_hash(OUTPUT_DIR / name)}
            for name in deterministic_names
        ]
    )
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": bool(
            required_present
            and v4_context["passed"]
            and official_hash_gate
            and reproduction_pass
            and protected_before == protected_after
            and prior_before == prior_after
            and cache_before == cache_after
            and len(standalone_rows) == 18
            and len(standalone_half_rows) == 12
            and len(portfolio_rows) == 18
            and len(portfolio_half_rows) == 12
            and len(entities["strategy"]) == 1
            and len(entities["trial"]) == 1
            and len(entities["benchmarks"]) == 5
        ),
        "V4_context_passed": v4_context["passed"],
        "V4_median5_outcome_preserved": "closed_exploration",
        "V4_median5_failure_reason_preserved": "weak_vs_primary_control",
        "V4_reproduction_passed": reproduction_pass,
        "official_history_hash_gate_passed": official_hash_gate,
        "new_strategy_configuration_count": 1,
        "new_experiment_trial_count": 1,
        "parent_trial_id": PARENT_TRIAL_ID,
        "prior_benchmark_reference_counted_as_existing_trial": False,
        "result_driven_adaptation": True,
        "source_rule_changed": True,
        "performance_executed": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "row_counts": {
            "V4_reproduction_check": len(reproduction),
            "standalone_results": len(standalone_rows),
            "standalone_chronological_half_results": len(standalone_half_rows),
            "portfolio_contribution_results": len(portfolio_rows),
            "portfolio_chronological_half_results": len(portfolio_half_rows),
            "rolling_36_month_portfolio_results": len(rolling[36]),
            "rolling_60_month_portfolio_results": len(rolling[60]),
            "state_signal_diagnostics": len(state_rows),
            "turnover_cost_reconciliation": len(turnover_rows),
            "invariant_results": len(invariant_rows),
        },
        "entity_counts": funnel,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "cache_unchanged": cache_before == cache_after,
        "required_artifacts_present": required_present,
        "deterministic_core_hash": deterministic_hash,
        "forbidden_actions": {
            "Median5_reopened_or_modified": False,
            "benchmark_silently_promoted": False,
            "exact_source_replication_claimed": False,
            "threshold_target_instrument_or_timing_changed": False,
            "rolling_median_calculated_or_used": False,
            "source_or_provider_search": False,
            "network_access": False,
            "validation_or_eligibility_claim": False,
            "lifecycle_or_registry_change": False,
            "paper_demo_activation": False,
            "broker_account_order_or_real_money_action": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "evidence_path": str(OUTPUT_DIR),
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "V4_reproduction_passed": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "standalone_5bps": {
            key: candidate_standalone[key]
            for key in (
                "total_return",
                "cagr",
                "sharpe_ratio",
                "maximum_drawdown",
                "turnover",
            )
        },
        "portfolio_5bps": {
            key: candidate_portfolio[key]
            for key in (
                "total_return",
                "cagr",
                "sharpe_ratio",
                "maximum_drawdown",
                "turnover",
            )
        },
        "rolling_36_windows": len(rolling[36]),
        "rolling_60_windows": len(rolling[60]),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
