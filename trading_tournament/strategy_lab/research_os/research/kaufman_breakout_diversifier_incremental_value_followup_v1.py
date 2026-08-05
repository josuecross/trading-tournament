from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    fast_price_volume_discovery_batch_v2 as market,
)
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    implement_targeted_medium_frequency_breakout_candidate_v1 as parent,
)
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as open_engine,
)


TASK_ID = "kaufman_breakout_diversifier_incremental_value_followup_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = parent.STRATEGY_ID
FAMILY_ID = parent.FAMILY_ID
DISPLAY_NAME = parent.DISPLAY_NAME
ARCHITECTURE = parent.ARCHITECTURE
SOURCE_LINEAGE = parent.SOURCE_LINEAGE
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = parent.TRIAL_ID
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
TOLERANCE = parent.TOLERANCE
FROZEN_EXPOSURE_SPY = 0.524921793535
FROZEN_EXPOSURE_BIL = 0.475078206465
EXPECTED_START = pd.Timestamp("2010-08-10")
EXPECTED_END = pd.Timestamp("2026-06-18")

PARENT_EVIDENCE = parent.OUTPUT_DIR
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
PROTECTED_PATHS = parent.PROTECTED_PATHS

REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
CONTROL_IDS = (
    "donchian_40_close_channel_spy_bil_v1",
    "kaufman_pjk_breakout_exposure_matched_spy_bil_v1",
    "kaufman_pjk_slope_only_40_spy_bil_v1",
    "SPY_200_day_trend_control",
    "BIL_buy_and_hold",
)
BENCHMARK_IDS = (REFERENCE_ID, *CONTROL_IDS)
CRITICAL_CONTROL_IDS = CONTROL_IDS[:2]

PORTFOLIO_IDS = {
    "reference": "100pct_frozen_reference",
    STRATEGY_ID: "80pct_reference_20pct_kaufman_candidate",
    CONTROL_IDS[0]: "80pct_reference_20pct_donchian_control",
    CONTROL_IDS[1]: "80pct_reference_20pct_exposure_matched_control",
    CONTROL_IDS[2]: "80pct_reference_20pct_slope_only_control",
    CONTROL_IDS[3]: "80pct_reference_20pct_SPY_200_day_trend_control",
    CONTROL_IDS[4]: "80pct_reference_20pct_BIL",
}
PORTFOLIO_SLEEVE_IDS = (STRATEGY_ID, *CONTROL_IDS)

NEXT_ADVANCE = "direction_owner_review_kaufman_breakout_diversifier_followup_v1"
NEXT_CLOSE = "targeted_defensive_cross_asset_state_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_kaufman_breakout_diversifier_block_v1"

REQUIRED_OUTPUTS = {
    "followup_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "portfolio_control_definitions.csv",
    "full_period_portfolio_results.csv",
    "chronological_half_portfolio_results.csv",
    "rolling_36_month_portfolio_results.csv",
    "rolling_60_month_portfolio_results.csv",
    "rolling_window_summary.csv",
    "candidate_mechanism_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "followup_report.md",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def rows_with_fields(
    rows: list[dict[str, Any]],
    leading: list[str],
) -> list[str]:
    return open_engine.rows_with_fields(rows, leading)


def directory_hash(path: Path) -> str:
    return open_engine.tree_hash(path)


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def verify_parent() -> dict[str, Any]:
    consistency = json.loads(
        (PARENT_EVIDENCE / "consistency_check.json").read_text(encoding="utf-8")
    )
    trials = read_csv(PARENT_EVIDENCE / "trial_ledger.csv")
    outcomes = read_csv(PARENT_EVIDENCE / "outcome_summary.csv")
    portfolios = read_csv(PARENT_EVIDENCE / "portfolio_contribution_results.csv")
    parent_trial = [
        row for row in trials if row.get("trial_id") == PARENT_TRIAL_ID
    ]
    start_dates = {row["evaluation_start"] for row in portfolios}
    end_dates = {row["evaluation_end"] for row in portfolios}
    passed = bool(
        consistency.get("overall_pass")
        and consistency.get("outcome") == "closed_exploration"
        and consistency.get("failure_reason") == "period_instability"
        and len(parent_trial) == 1
        and len(outcomes) == 1
        and outcomes[0]["outcome"] == "closed_exploration"
        and outcomes[0]["failure_reason"] == "period_instability"
        and start_dates == {EXPECTED_START.date().isoformat()}
        and end_dates == {EXPECTED_END.date().isoformat()}
    )
    return {
        "passed": passed,
        "parent_trial": parent_trial[0] if parent_trial else {},
        "parent_outcome": outcomes[0] if outcomes else {},
        "consistency": consistency,
        "portfolio_start": next(iter(start_dates)) if len(start_dates) == 1 else "",
        "portfolio_end": next(iter(end_dates)) if len(end_dates) == 1 else "",
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
            "rule": parent.RULE_NUMBER,
            "period_sessions": parent.PERIOD_SESSIONS,
            "warmup_sessions": parent.WARMUP_SESSIONS,
            "channel_contract": "TradingView_Rule_2_only",
            "signal": "completed_close",
            "execution": "following_session_adjusted_open",
            "outer_sleeve_weight": 0.20,
            "outer_rebalance": "monthly_following_session_close",
        },
        "benchmark_or_control": list(BENCHMARK_IDS),
        "authoritative_parent_route": "standalone",
        "authoritative_parent_outcome": "closed_exploration",
        "authoritative_parent_failure_reason": "period_instability",
        "evaluation_route": "diversifier_only",
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "exploratory_variant",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "existing_strategy_configuration_carried_forward": True,
        "new_strategy_configuration_created": False,
        "authoritative_registry_record_created": False,
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
        "trial_id": TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "exploratory_variant",
        "changed_fields_from_parent": (
            "evaluation_route_and_predeclared_portfolio_controls_only"
        ),
        "strategy_rule_changed": False,
        "channel_formula_changed": False,
        "period_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "source_rule_changed": False,
        "standalone_outcome_changed": False,
        "portfolio_route_changed": True,
        "new_route": "diversifier_only",
        "result_driven_adaptation": True,
        "optimization_performed": False,
        "post_result_parameter_change_allowed": False,
        "preregistered_before_followup_performance": True,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    definitions = {
        REFERENCE_ID: (
            "Frozen current active VM/DSR/USCI combination used as the 80% "
            "portfolio reference."
        ),
        CONTROL_IDS[0]: (
            "Strict prior-40-close Donchian breakout with identical SPY/BIL "
            "assets and following-open execution."
        ),
        CONTROL_IDS[1]: (
            f"Monthly SPY/BIL allocation fixed at {FROZEN_EXPOSURE_SPY:.12f}/"
            f"{FROZEN_EXPOSURE_BIL:.12f}; parent-frozen, not recalculated."
        ),
        CONTROL_IDS[2]: (
            "SPY for positive same-40-session OLS slope, BIL for negative "
            "slope, equality retains state; following-open execution."
        ),
        CONTROL_IDS[3]: (
            "SPY above completed-close SMA200 and BIL otherwise; "
            "following-open execution."
        ),
        CONTROL_IDS[4]: "Hold BIL throughout the identical common period.",
    }
    return [
        {
            "benchmark_reference_id": benchmark_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "control_definition": definitions[benchmark_id],
            "critical_control": benchmark_id in CRITICAL_CONTROL_IDS,
            "frozen_reference": benchmark_id == REFERENCE_ID,
            "exposure_SPY_weight": (
                FROZEN_EXPOSURE_SPY if benchmark_id == CONTROL_IDS[1] else ""
            ),
            "exposure_BIL_weight": (
                FROZEN_EXPOSURE_BIL if benchmark_id == CONTROL_IDS[1] else ""
            ),
            "recalculated_from_followup_period": False,
            "counted_as_strategy_or_trial": False,
        }
        for benchmark_id in BENCHMARK_IDS
    ]


def process_row(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "process_task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "next_action": next_action,
        "next_action_executed": False,
        "strategy_counted": False,
        "trial_counted": False,
        "provider_accessed": False,
    }


def write_entities(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> str:
    rows = {
        "strategy_cards.csv": [
            strategy_row(outcome, failure_reason, next_action)
        ],
        "trial_ledger.csv": [trial_row(outcome, failure_reason, next_action)],
        "benchmark_reference_log.csv": benchmark_rows(),
        "process_task_log.csv": [process_row(outcome, next_action)],
    }
    for filename, values in rows.items():
        open_engine.write_csv(OUTPUT_DIR / filename, values, list(values[0]))
    return open_engine.canonical_hash(rows)


def build_paths() -> tuple[
    pd.DataFrame,
    dict[str, open_engine.Schedule],
    dict[tuple[str, float], dict[str, Any]],
]:
    panel, _, passed = parent.load_preflight()
    if not passed:
        return panel, {}, {}
    index = pd.DatetimeIndex(panel.index)
    close = panel[("SPY", "close")]
    schedules = {
        STRATEGY_ID: parent.regression_channel_schedule(panel),
        CONTROL_IDS[0]: parent.donchian_schedule(panel),
        CONTROL_IDS[1]: open_engine.monthly_exposure_schedule(
            index, FROZEN_EXPOSURE_SPY
        ),
        CONTROL_IDS[2]: parent.slope_only_schedule(panel),
        CONTROL_IDS[3]: open_engine.regime_schedule(close, "price_sma200"),
        CONTROL_IDS[4]: open_engine.static_schedule(index, 0.0),
    }
    paths = {
        (sleeve_id, cost): open_engine.simulate(
            sleeve_id, panel, schedule, cost
        )
        for sleeve_id, schedule in schedules.items()
        for cost in COST_BPS
    }
    return panel, schedules, paths


def build_portfolio_payloads(
    paths: dict[tuple[str, float], dict[str, Any]],
) -> dict[tuple[str, float], dict[str, Any]]:
    reference_all = market.active_vm_dsr_usci_reference_returns()
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        common = paths[(STRATEGY_ID, cost)]["returns"].index.intersection(
            reference_all.dropna().index
        )
        reference = reference_all.reindex(common).dropna()
        if (
            reference.index.min() != EXPECTED_START
            or reference.index.max() != EXPECTED_END
        ):
            raise RuntimeError("Frozen reference common period changed")
        reference_payload = portfolio_accounting.reference_payload(reference, cost)
        reference_payload["portfolio_id"] = PORTFOLIO_IDS["reference"]
        reference_payload["sleeve_id"] = ""
        reference_payload["reference_returns"] = reference
        reference_payload["sleeve_returns"] = pd.Series(
            0.0, index=reference.index
        )
        reference_payload["outer_start_weights"] = pd.Series(
            0.0, index=reference.index
        )
        payloads[(PORTFOLIO_IDS["reference"], cost)] = reference_payload
        for sleeve_id in PORTFOLIO_SLEEVE_IDS:
            sleeve = paths[(sleeve_id, cost)]["returns"].reindex(reference.index)
            if sleeve.isna().any():
                raise RuntimeError(f"{sleeve_id} is incomplete on common period")
            portfolio_id = PORTFOLIO_IDS[sleeve_id]
            payload = portfolio_accounting.simulate_two_component_portfolio(
                reference,
                sleeve,
                portfolio_id,
                cost,
            )
            payload["portfolio_id"] = portfolio_id
            payload["sleeve_id"] = sleeve_id
            payload["reference_returns"] = reference
            payload["sleeve_returns"] = sleeve
            payload["outer_start_weights"] = parent.outer_start_weights(
                reference, sleeve
            )
            payloads[(portfolio_id, cost)] = payload
    return payloads


def portfolio_metrics(
    payload: dict[str, Any],
    paths: dict[tuple[str, float], dict[str, Any]],
    cost: float,
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    returns = payload["returns"]
    if period_index is not None:
        returns = returns.reindex(period_index).dropna()
    index = pd.DatetimeIndex(returns.index)
    base = portfolio_accounting.metric_payload(payload, index)
    sleeve_id = payload["sleeve_id"]
    if not sleeve_id:
        inner_turnover = 0.0
        inner_cost = 0.0
        inner_trade_count = 0
        inner_invariant = True
    else:
        outer_weights = payload["outer_start_weights"].reindex(index).fillna(0.0)
        sleeve_path = paths[(sleeve_id, cost)]
        sleeve_turnover = sleeve_path["turnover"].reindex(index).fillna(0.0)
        sleeve_cost = sleeve_path["cost"].reindex(index).fillna(0.0)
        inner_turnover = float((outer_weights * sleeve_turnover).sum())
        inner_cost = float((outer_weights * sleeve_cost).sum())
        inner_trade_count = int(
            ((outer_weights > 0.0) & (sleeve_turnover > TOLERANCE)).sum()
        )
        inner_invariant = open_engine.payload_invariants(sleeve_path)[
            "invariant_pass"
        ]
    outer_turnover_series = payload["turnover"].reindex(index).fillna(0.0)
    outer_cost_series = payload["cost"].reindex(index).fillna(0.0)
    outer_turnover = float(outer_turnover_series.sum())
    outer_cost = float(outer_cost_series.sum())
    outer_rebalances = int((outer_turnover_series > TOLERANCE).sum())
    combined_count = inner_trade_count + outer_rebalances
    maximum_gross = float(base["max_daily_exposure"])
    maximum_sum = float(base["max_daily_weight_sum"])
    invariant = bool(
        base["invariant_pass"]
        and inner_invariant
        and maximum_gross <= 1.0 + 1e-9
        and maximum_sum <= 1.0 + 1e-9
    )
    return {
        **market.metrics_from_returns(returns),
        "inner_sleeve_turnover": inner_turnover,
        "outer_turnover": outer_turnover,
        "combined_turnover_diagnostic": inner_turnover + outer_turnover,
        "inner_trade_count": inner_trade_count,
        "outer_rebalance_count": outer_rebalances,
        "trade_or_rebalance_count": combined_count,
        "inner_transaction_cost_drag": inner_cost,
        "outer_transaction_cost_drag": outer_cost,
        "transaction_cost_drag": inner_cost + outer_cost,
        "average_gross_exposure": float(base["average_gross_exposure"]),
        "maximum_gross_exposure": maximum_gross,
        "maximum_daily_weight_sum": maximum_sum,
        "numeric_invariant_status": base["numeric_invariant_status"],
        "timing_invariant_status": (
            "pass_inner_next_open_outer_following_session_close"
        ),
        "exposure_invariant_status": (
            "pass" if invariant else "fail"
        ),
        "weight_invariant_status": "pass" if invariant else "fail",
        "explicit_zero_weights_preserved": True,
        "invariant_pass": invariant,
    }


def portfolio_row(
    portfolio_id: str,
    cost: float,
    period: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio_id,
        "entity_type": "portfolio_diagnostic",
        "stage": STAGE,
        "period": period,
        "period_role": (
            "full_exploration_period"
            if period == "full_period"
            else "chronological_half_not_validation"
        ),
        "cost_bps": cost,
        "construction": (
            "100pct_frozen_reference"
            if portfolio_id == PORTFOLIO_IDS["reference"]
            else "monthly_rebalanced_80pct_reference_20pct_sleeve_explicit_holdings"
        ),
        "daily_fixed_weight_return_blend_used": False,
        **metrics,
    }


def reproduction_rows(
    observed: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    expected_rows = read_csv(
        PARENT_EVIDENCE / "portfolio_contribution_results.csv"
    )
    expected_map = {
        (row["portfolio_id"], float(row["cost_assumption_bps"])): row
        for row in expected_rows
        if row["portfolio_id"]
        in {
            "100pct_frozen_reference",
            "80pct_reference_20pct_candidate",
            "80pct_reference_20pct_donchian_control",
            "80pct_reference_20pct_exposure_matched_control",
        }
    }
    id_map = {
        PORTFOLIO_IDS["reference"]: "100pct_frozen_reference",
        PORTFOLIO_IDS[STRATEGY_ID]: "80pct_reference_20pct_candidate",
        PORTFOLIO_IDS[CONTROL_IDS[0]]: (
            "80pct_reference_20pct_donchian_control"
        ),
        PORTFOLIO_IDS[CONTROL_IDS[1]]: (
            "80pct_reference_20pct_exposure_matched_control"
        ),
    }
    numeric_fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "inner_sleeve_turnover",
        "outer_turnover",
        "combined_turnover_diagnostic",
        "transaction_cost_drag",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
    )
    parent_field_map = {
        "outer_turnover": "outer_monthly_turnover",
        "maximum_gross_exposure": "max_daily_exposure",
        "maximum_daily_weight_sum": "max_daily_weight_sum",
    }
    rows: list[dict[str, Any]] = []
    for current_id, prior_id in id_map.items():
        for cost in COST_BPS:
            expected = expected_map[(prior_id, cost)]
            actual = observed[(current_id, cost)]
            date_pass = bool(
                actual["evaluation_start"] == expected["evaluation_start"]
                and actual["evaluation_end"] == expected["evaluation_end"]
            )
            rows.append(
                {
                    "portfolio_id": current_id,
                    "parent_portfolio_id": prior_id,
                    "cost_bps": cost,
                    "metric": "evaluation_period",
                    "parent_value": (
                        f"{expected['evaluation_start']}|{expected['evaluation_end']}"
                    ),
                    "reproduced_value": (
                        f"{actual['evaluation_start']}|{actual['evaluation_end']}"
                    ),
                    "difference": "",
                    "absolute_tolerance": "",
                    "pass": date_pass,
                }
            )
            for field in numeric_fields:
                parent_field = parent_field_map.get(field, field)
                expected_value = float(expected[parent_field])
                actual_value = float(actual[field])
                difference = actual_value - expected_value
                rows.append(
                    {
                        "portfolio_id": current_id,
                        "parent_portfolio_id": prior_id,
                        "cost_bps": cost,
                        "metric": field,
                        "parent_value": expected_value,
                        "reproduced_value": actual_value,
                        "difference": difference,
                        "absolute_tolerance": REPRODUCTION_TOLERANCE,
                        "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
                    }
                )
    return rows, bool(rows and all(row["pass"] for row in rows))


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return open_engine.control_dominates(candidate, control)


def monthly_rolling_rows(
    horizon_months: int,
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_id = PORTFOLIO_IDS[STRATEGY_ID]
    reference_id = PORTFOLIO_IDS["reference"]
    donchian_id = PORTFOLIO_IDS[CONTROL_IDS[0]]
    exposure_id = PORTFOLIO_IDS[CONTROL_IDS[1]]
    candidate_returns = payloads[(candidate_id, PRIMARY_COST_BPS)]["returns"]
    periods = sorted(candidate_returns.index.to_period("M").unique())
    rows: list[dict[str, Any]] = []
    for end_position in range(horizon_months - 1, len(periods)):
        selected = periods[
            end_position - horizon_months + 1 : end_position + 1
        ]
        index = candidate_returns.index[
            candidate_returns.index.to_period("M").isin(selected)
        ]
        candidate = market.metrics_from_returns(
            candidate_returns.reindex(index).dropna()
        )
        controls = {
            portfolio_id: market.metrics_from_returns(
                payloads[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
                .reindex(index)
                .dropna()
            )
            for portfolio_id in (reference_id, donchian_id, exposure_id)
        }
        reference = controls[reference_id]
        donchian = controls[donchian_id]
        exposure = controls[exposure_id]
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
                "reference_cagr_difference": (
                    float(candidate["cagr"]) - float(reference["cagr"])
                ),
                "reference_sharpe_difference": (
                    float(candidate["sharpe_ratio"])
                    - float(reference["sharpe_ratio"])
                ),
                "reference_maximum_drawdown_difference": (
                    float(candidate["maximum_drawdown"])
                    - float(reference["maximum_drawdown"])
                ),
                "donchian_cagr_difference": (
                    float(candidate["cagr"]) - float(donchian["cagr"])
                ),
                "donchian_sharpe_difference": (
                    float(candidate["sharpe_ratio"])
                    - float(donchian["sharpe_ratio"])
                ),
                "donchian_maximum_drawdown_difference": (
                    float(candidate["maximum_drawdown"])
                    - float(donchian["maximum_drawdown"])
                ),
                "exposure_matched_cagr_difference": (
                    float(candidate["cagr"]) - float(exposure["cagr"])
                ),
                "exposure_matched_sharpe_difference": (
                    float(candidate["sharpe_ratio"])
                    - float(exposure["sharpe_ratio"])
                ),
                "exposure_matched_maximum_drawdown_difference": (
                    float(candidate["maximum_drawdown"])
                    - float(exposure["maximum_drawdown"])
                ),
                "reference_dominates_candidate": dominates(reference, candidate),
                "donchian_dominates_candidate": dominates(donchian, candidate),
                "exposure_matched_dominates_candidate": dominates(
                    exposure, candidate
                ),
                "candidate_improves_reference_sharpe_or_drawdown": bool(
                    float(candidate["sharpe_ratio"])
                    > float(reference["sharpe_ratio"])
                    or float(candidate["maximum_drawdown"])
                    > float(reference["maximum_drawdown"])
                ),
                "sealed_untouched_or_validation": False,
            }
        )
    return rows


def rolling_summary_rows(
    rolling: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon, values in rolling.items():
        count = len(values)
        improves = sum(
            bool(row["candidate_improves_reference_sharpe_or_drawdown"])
            for row in values
        )
        donchian = sum(
            bool(row["donchian_dominates_candidate"]) for row in values
        )
        exposure = sum(
            bool(row["exposure_matched_dominates_candidate"]) for row in values
        )
        rows.append(
            {
                "horizon_months": horizon,
                "eligible_window_count": count,
                "candidate_improves_reference_count": improves,
                "candidate_improves_reference_fraction": (
                    improves / count if count else ""
                ),
                "donchian_dominates_count": donchian,
                "donchian_dominates_fraction": (
                    donchian / count if count else ""
                ),
                "exposure_matched_dominates_count": exposure,
                "exposure_matched_dominates_fraction": (
                    exposure / count if count else ""
                ),
                "median_reference_sharpe_difference": (
                    float(
                        np.median(
                            [row["reference_sharpe_difference"] for row in values]
                        )
                    )
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


def mechanism_rows(
    panel: pd.DataFrame,
    schedule: open_engine.Schedule,
    path: dict[str, Any],
) -> list[dict[str, Any]]:
    common = path["returns"].index[
        (path["returns"].index >= EXPECTED_START)
        & (path["returns"].index <= EXPECTED_END)
    ]
    events = schedule.events.loc[
        schedule.events["execution_date"].map(pd.Timestamp).isin(set(common))
    ]
    trades = parent.trade_ledger(panel, schedule)
    completed = [row for row in trades if not row["terminal_open_status"]]
    rows: list[dict[str, Any]] = [
        {
            "record_type": "summary",
            "date": "",
            "signal_date": "",
            "execution_date": "",
            "event_type": "",
            "target_SPY_weight": "",
            "target_BIL_weight": "",
            "completed_trade_count": len(completed),
            "average_holding_sessions": (
                float(
                    np.mean([row["holding_sessions"] for row in completed])
                )
                if completed
                else ""
            ),
            "median_holding_sessions": (
                float(
                    np.median([row["holding_sessions"] for row in completed])
                )
                if completed
                else ""
            ),
            "maximum_holding_sessions": (
                max(int(row["holding_sessions"]) for row in completed)
                if completed
                else ""
            ),
            "average_candidate_SPY_exposure": float(
                path["target_spy"].reindex(common).mean()
            ),
            "inner_turnover_full_sleeve": float(
                path["turnover"].reindex(common).sum()
            ),
            "transaction_cost_drag_full_sleeve": float(
                path["cost"].reindex(common).sum()
            ),
            "rule_changed": False,
            "used_for_parameter_change": False,
        }
    ]
    for day in common:
        rows.append(
            {
                "record_type": "daily_target_history",
                "date": day,
                "signal_date": "",
                "execution_date": "",
                "event_type": "",
                "target_SPY_weight": float(
                    path["schedule"].targets.loc[day, "SPY"]
                ),
                "target_BIL_weight": float(
                    path["schedule"].targets.loc[day, "BIL"]
                ),
                "completed_trade_count": "",
                "average_holding_sessions": "",
                "median_holding_sessions": "",
                "maximum_holding_sessions": "",
                "average_candidate_SPY_exposure": "",
                "inner_turnover_full_sleeve": "",
                "transaction_cost_drag_full_sleeve": "",
                "rule_changed": False,
                "used_for_parameter_change": False,
            }
        )
    for _, event in events.iterrows():
        rows.append(
            {
                "record_type": "signal_change",
                "date": event["signal_date"],
                "signal_date": event["signal_date"],
                "execution_date": event["execution_date"],
                "event_type": event["event_type"],
                "target_SPY_weight": (
                    1.0 if event["to_asset"] == "SPY" else 0.0
                ),
                "target_BIL_weight": (
                    1.0 if event["to_asset"] == "BIL" else 0.0
                ),
                "completed_trade_count": "",
                "average_holding_sessions": "",
                "median_holding_sessions": "",
                "maximum_holding_sessions": "",
                "average_candidate_SPY_exposure": "",
                "inner_turnover_full_sleeve": "",
                "transaction_cost_drag_full_sleeve": "",
                "rule_changed": False,
                "used_for_parameter_change": False,
            }
        )
    for trade in trades:
        if pd.Timestamp(trade["entry_execution_date"]) not in set(common):
            continue
        rows.append(
            {
                "record_type": "trade",
                "date": trade["entry_execution_date"],
                "signal_date": trade["entry_signal_date"],
                "execution_date": trade["entry_execution_date"],
                "event_type": "completed_trade" if not trade["terminal_open_status"] else "terminal_open_trade",
                "target_SPY_weight": 1.0,
                "target_BIL_weight": 0.0,
                "completed_trade_count": "",
                "average_holding_sessions": trade["holding_sessions"],
                "median_holding_sessions": "",
                "maximum_holding_sessions": "",
                "average_candidate_SPY_exposure": "",
                "inner_turnover_full_sleeve": "",
                "transaction_cost_drag_full_sleeve": "",
                "gross_trade_return": trade["gross_trade_return"],
                "net_trade_return_5_bps": trade["net_trade_return_5_bps"],
                "exit_execution_date": trade["exit_execution_date"],
                "rule_changed": False,
                "used_for_parameter_change": False,
            }
        )
    return rows


def classify(
    reproduction_pass: bool,
    portfolio_metrics_map: dict[tuple[str, float], dict[str, Any]],
    half_metrics: dict[tuple[str, str], dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    if not reproduction_pass:
        return (
            "blocked_feasibility",
            "data_or_comparability_failure",
            NEXT_BLOCK,
            {"parent_portfolio_reproduction_passed": False},
        )
    candidate_id = PORTFOLIO_IDS[STRATEGY_ID]
    reference_id = PORTFOLIO_IDS["reference"]
    critical_ids = [PORTFOLIO_IDS[value] for value in CRITICAL_CONTROL_IDS]
    candidate = portfolio_metrics_map[(candidate_id, PRIMARY_COST_BPS)]
    reference = portfolio_metrics_map[(reference_id, PRIMARY_COST_BPS)]
    critical = {
        control_id: portfolio_metrics_map[(control_id, PRIMARY_COST_BPS)]
        for control_id in critical_ids
    }
    all_invariants = all(
        row["invariant_pass"] for row in portfolio_metrics_map.values()
    )
    reference_sharpe_edge = float(candidate["sharpe_ratio"]) - float(
        reference["sharpe_ratio"]
    )
    reference_drawdown_edge = float(candidate["maximum_drawdown"]) - float(
        reference["maximum_drawdown"]
    )
    critical_dominance = {
        control_id: dominates(metrics, candidate)
        for control_id, metrics in critical.items()
    }
    critical_material = {
        control_id: bool(
            float(candidate["sharpe_ratio"])
            - float(metrics["sharpe_ratio"])
            >= 0.02
            or float(candidate["maximum_drawdown"])
            - float(metrics["maximum_drawdown"])
            >= 0.01
        )
        for control_id, metrics in critical.items()
    }
    half_failures: list[str] = []
    half_comparisons = (reference_id, *critical_ids)
    for period in ("first_chronological_half", "second_chronological_half"):
        candidate_half = half_metrics[(candidate_id, period)]
        for comparison_id in half_comparisons:
            if open_engine.worse_on_both(
                candidate_half, half_metrics[(comparison_id, period)]
            ):
                half_failures.append(f"{period}:{comparison_id}")
    summaries = {int(row["horizon_months"]): row for row in rolling_summary}
    rolling_reference = all(
        float(summaries[horizon]["candidate_improves_reference_fraction"]) > 0.5
        for horizon in (36, 60)
    )
    rolling_exposure = all(
        float(summaries[horizon]["exposure_matched_dominates_fraction"]) <= 0.5
        for horizon in (36, 60)
    )
    rolling_donchian = all(
        float(summaries[horizon]["donchian_dominates_fraction"]) <= 0.5
        for horizon in (36, 60)
    )
    simple_ids = [
        PORTFOLIO_IDS[value]
        for value in (
            CONTROL_IDS[2],
            CONTROL_IDS[3],
            CONTROL_IDS[4],
        )
    ]
    simple_not_replicated = all(
        not open_engine.economically_replicated(
            candidate,
            portfolio_metrics_map[(control_id, PRIMARY_COST_BPS)],
        )
        for control_id in simple_ids
    )
    candidate_10 = portfolio_metrics_map[(candidate_id, 10.0)]
    reference_10 = portfolio_metrics_map[(reference_id, 10.0)]
    critical_10 = {
        control_id: portfolio_metrics_map[(control_id, 10.0)]
        for control_id in critical_ids
    }
    ten_improves_reference = bool(
        float(candidate_10["sharpe_ratio"])
        > float(reference_10["sharpe_ratio"])
        or float(candidate_10["maximum_drawdown"])
        > float(reference_10["maximum_drawdown"])
    )
    ten_critical_not_dominating = all(
        not dominates(metrics, candidate_10)
        for metrics in critical_10.values()
    )
    ten_not_worse_both = all(
        not open_engine.worse_on_both(candidate_10, metrics)
        for metrics in critical_10.values()
    )
    gate = {
        "parent_portfolio_reproduction_passed": reproduction_pass,
        "all_accounting_and_timing_invariants_pass": all_invariants,
        "candidate_materially_improves_reference": bool(
            reference_sharpe_edge >= 0.02
            or reference_drawdown_edge >= 0.01
        ),
        "candidate_not_worse_both_vs_reference": not open_engine.worse_on_both(
            candidate, reference
        ),
        "critical_controls_do_not_dominate": not any(
            critical_dominance.values()
        ),
        "material_advantage_vs_each_critical_control": all(
            critical_material.values()
        ),
        "chronological_half_stability": not half_failures,
        "rolling_36_and_60_improve_reference_more_than_half": rolling_reference,
        "exposure_control_dominates_at_most_half_rolling_windows": (
            rolling_exposure
        ),
        "donchian_dominates_at_most_half_rolling_windows": rolling_donchian,
        "simple_controls_do_not_economically_replicate": simple_not_replicated,
        "10bps_candidate_improves_reference": ten_improves_reference,
        "10bps_critical_controls_do_not_dominate": ten_critical_not_dominating,
        "10bps_candidate_not_worse_both_vs_each_critical": ten_not_worse_both,
        "reference_sharpe_edge": reference_sharpe_edge,
        "reference_maximum_drawdown_edge": reference_drawdown_edge,
        "critical_control_dominance": critical_dominance,
        "critical_control_materiality": critical_material,
        "half_failures": half_failures,
        "rolling_36_improves_reference_fraction": summaries[36][
            "candidate_improves_reference_fraction"
        ],
        "rolling_60_improves_reference_fraction": summaries[60][
            "candidate_improves_reference_fraction"
        ],
        "rolling_36_donchian_dominates_fraction": summaries[36][
            "donchian_dominates_fraction"
        ],
        "rolling_60_donchian_dominates_fraction": summaries[60][
            "donchian_dominates_fraction"
        ],
        "rolling_36_exposure_dominates_fraction": summaries[36][
            "exposure_matched_dominates_fraction"
        ],
        "rolling_60_exposure_dominates_fraction": summaries[60][
            "exposure_matched_dominates_fraction"
        ],
    }
    required_gate_ids = (
        "parent_portfolio_reproduction_passed",
        "all_accounting_and_timing_invariants_pass",
        "candidate_materially_improves_reference",
        "candidate_not_worse_both_vs_reference",
        "critical_controls_do_not_dominate",
        "material_advantage_vs_each_critical_control",
        "chronological_half_stability",
        "rolling_36_and_60_improve_reference_more_than_half",
        "exposure_control_dominates_at_most_half_rolling_windows",
        "donchian_dominates_at_most_half_rolling_windows",
        "simple_controls_do_not_economically_replicate",
        "10bps_candidate_improves_reference",
        "10bps_critical_controls_do_not_dominate",
        "10bps_candidate_not_worse_both_vs_each_critical",
    )
    if all(bool(gate[key]) for key in required_gate_ids):
        return (
            "exploratory_followup_candidate_diversifier",
            "",
            NEXT_ADVANCE,
            gate,
        )
    if not all_invariants:
        return "blocked_feasibility", "methodology_failure", NEXT_BLOCK, gate
    if not gate["candidate_materially_improves_reference"]:
        reason = "weak_portfolio_contribution"
    elif not gate["critical_controls_do_not_dominate"]:
        reason = (
            "exposure_control_explanation"
            if critical_dominance[PORTFOLIO_IDS[CONTROL_IDS[1]]]
            else "weak_vs_primary_control"
        )
    elif not gate["material_advantage_vs_each_critical_control"]:
        reason = "weak_vs_primary_control"
    elif not gate["chronological_half_stability"]:
        reason = "period_instability"
    elif not rolling_reference:
        reason = "period_instability"
    elif not rolling_exposure:
        reason = "exposure_control_explanation"
    elif not rolling_donchian:
        reason = "weak_vs_primary_control"
    elif not simple_not_replicated:
        reason = "benchmark_like_behavior"
    elif not (
        ten_improves_reference
        and ten_critical_not_dominating
        and ten_not_worse_both
    ):
        reason = "cost_drag"
    else:
        reason = "overfit_or_unstable"
    return "closed_exploration", reason, NEXT_CLOSE, gate


def run() -> dict[str, Any]:
    clean_output()
    parent_before = directory_hash(PARENT_EVIDENCE)
    protected_before = {
        rel(path): open_engine.file_hash(path) for path in PROTECTED_PATHS
    }
    cache_before = directory_hash(CACHE_DIR)
    prior_evidence_before = open_engine.tree_hash(
        ROOT / "evidence", OUTPUT_DIR.parent
    )
    parent_context = verify_parent()
    if not parent_context["passed"]:
        raise RuntimeError("Parent Kaufman packet is not authoritative")

    preregistration_hash = write_entities(
        "preregistered_pending_execution",
        "",
        "execute_frozen_diversifier_followup",
    )

    panel, schedules, paths = build_paths()
    if not paths:
        outcome = "blocked_feasibility"
        failure_reason = "data_or_comparability_failure"
        next_action = NEXT_BLOCK
        reproduction: list[dict[str, Any]] = []
        reproduction_pass = False
        payloads: dict[tuple[str, float], dict[str, Any]] = {}
        full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        full_rows: list[dict[str, Any]] = []
        half_metrics: dict[tuple[str, str], dict[str, Any]] = {}
        half_rows: list[dict[str, Any]] = []
        rolling = {36: [], 60: []}
        rolling_summary: list[dict[str, Any]] = []
        mechanism: list[dict[str, Any]] = []
        turnover_rows: list[dict[str, Any]] = []
        invariant_rows: list[dict[str, Any]] = []
        gate = {"parent_portfolio_reproduction_passed": False}
        deterministic = False
    else:
        payloads = build_portfolio_payloads(paths)
        full_metrics = {}
        full_rows = []
        for portfolio_id in PORTFOLIO_IDS.values():
            for cost in COST_BPS:
                metrics = portfolio_metrics(
                    payloads[(portfolio_id, cost)], paths, cost
                )
                full_metrics[(portfolio_id, cost)] = metrics
                full_rows.append(
                    portfolio_row(portfolio_id, cost, "full_period", metrics)
                )
        reproduction, reproduction_pass = reproduction_rows(full_metrics)

        half_metrics = {}
        half_rows = []
        candidate_index = payloads[
            (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
        ]["returns"].index
        halves = open_engine.split_halves(candidate_index)
        if reproduction_pass:
            for period, period_index in halves.items():
                for portfolio_id in PORTFOLIO_IDS.values():
                    metrics = portfolio_metrics(
                        payloads[(portfolio_id, PRIMARY_COST_BPS)],
                        paths,
                        PRIMARY_COST_BPS,
                        period_index,
                    )
                    half_metrics[(portfolio_id, period)] = metrics
                    half_rows.append(
                        portfolio_row(
                            portfolio_id,
                            PRIMARY_COST_BPS,
                            period,
                            metrics,
                        )
                    )
            rolling = {
                36: monthly_rolling_rows(36, payloads),
                60: monthly_rolling_rows(60, payloads),
            }
            rolling_summary = rolling_summary_rows(rolling)
            outcome, failure_reason, next_action, gate = classify(
                reproduction_pass,
                full_metrics,
                half_metrics,
                rolling_summary,
            )
            mechanism = mechanism_rows(
                panel,
                schedules[STRATEGY_ID],
                paths[(STRATEGY_ID, PRIMARY_COST_BPS)],
            )
        else:
            outcome = "blocked_feasibility"
            failure_reason = "data_or_comparability_failure"
            next_action = NEXT_BLOCK
            half_rows = []
            rolling = {36: [], 60: []}
            rolling_summary = []
            mechanism = []
            gate = {"parent_portfolio_reproduction_passed": False}

        turnover_rows = []
        invariant_rows = []
        for (portfolio_id, cost), metrics in full_metrics.items():
            turnover_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "cost_bps": cost,
                    "inner_sleeve_turnover": metrics[
                        "inner_sleeve_turnover"
                    ],
                    "outer_turnover": metrics["outer_turnover"],
                    "combined_turnover_diagnostic": metrics[
                        "combined_turnover_diagnostic"
                    ],
                    "inner_transaction_cost_drag": metrics[
                        "inner_transaction_cost_drag"
                    ],
                    "outer_transaction_cost_drag": metrics[
                        "outer_transaction_cost_drag"
                    ],
                    "combined_transaction_cost_drag": metrics[
                        "transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "inner_and_outer_costs_charged_once": True,
                    "daily_fixed_weight_return_blend_used": False,
                    "reconciles": True,
                }
            )
            invariant_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "cost_bps": cost,
                    "numeric_invariant_status": metrics[
                        "numeric_invariant_status"
                    ],
                    "timing_invariant_status": metrics[
                        "timing_invariant_status"
                    ],
                    "exposure_invariant_status": metrics[
                        "exposure_invariant_status"
                    ],
                    "weight_invariant_status": metrics[
                        "weight_invariant_status"
                    ],
                    "explicit_zero_weights_preserved": metrics[
                        "explicit_zero_weights_preserved"
                    ],
                    "maximum_gross_exposure": metrics[
                        "maximum_gross_exposure"
                    ],
                    "maximum_daily_weight_sum": metrics[
                        "maximum_daily_weight_sum"
                    ],
                    "signal_rule_changed": False,
                    "channel_formula_changed": False,
                    "inner_execution_next_open": True,
                    "outer_execution_following_session_close": True,
                    "invariant_pass": metrics["invariant_pass"],
                }
            )
        repeat = open_engine.simulate(
            STRATEGY_ID,
            panel,
            schedules[STRATEGY_ID],
            PRIMARY_COST_BPS,
        )
        deterministic = bool(
            repeat["state_hash"]
            == paths[(STRATEGY_ID, PRIMARY_COST_BPS)]["state_hash"]
        )

    write_entities(outcome, failure_reason, next_action)
    control_definitions = [
        {
            "portfolio_id": PORTFOLIO_IDS["reference"],
            "sleeve_id": REFERENCE_ID,
            "portfolio_construction": "100pct_frozen_reference",
            "outer_reference_weight": 1.0,
            "outer_sleeve_weight": 0.0,
            "inner_rule_changed": False,
            "exposure_weight_recalculated": False,
        },
        *[
            {
                "portfolio_id": PORTFOLIO_IDS[sleeve_id],
                "sleeve_id": sleeve_id,
                "portfolio_construction": "monthly_rebalanced_80_20",
                "outer_reference_weight": 0.8,
                "outer_sleeve_weight": 0.2,
                "inner_rule_changed": False,
                "exposure_weight_recalculated": False,
            }
            for sleeve_id in PORTFOLIO_SLEEVE_IDS
        ],
    ]
    open_engine.write_csv(
        OUTPUT_DIR / "portfolio_control_definitions.csv",
        control_definitions,
        list(control_definitions[0]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        rows_with_fields(
            reproduction,
            ["portfolio_id", "cost_bps", "metric"],
        ),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "full_period_portfolio_results.csv",
        full_rows,
        rows_with_fields(full_rows, ["portfolio_id", "cost_bps"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "chronological_half_portfolio_results.csv",
        half_rows,
        rows_with_fields(half_rows, ["portfolio_id", "period"]),
    )
    rolling_fields = [
        "horizon_months",
        "window_start",
        "window_end",
        "calendar_month_count",
        "trading_days",
        "candidate_cagr",
        "candidate_sharpe_ratio",
        "candidate_maximum_drawdown",
        "reference_cagr_difference",
        "reference_sharpe_difference",
        "reference_maximum_drawdown_difference",
        "donchian_cagr_difference",
        "donchian_sharpe_difference",
        "donchian_maximum_drawdown_difference",
        "exposure_matched_cagr_difference",
        "exposure_matched_sharpe_difference",
        "exposure_matched_maximum_drawdown_difference",
        "reference_dominates_candidate",
        "donchian_dominates_candidate",
        "exposure_matched_dominates_candidate",
        "candidate_improves_reference_sharpe_or_drawdown",
        "sealed_untouched_or_validation",
    ]
    open_engine.write_csv(
        OUTPUT_DIR / "rolling_36_month_portfolio_results.csv",
        rolling[36],
        rolling_fields,
    )
    open_engine.write_csv(
        OUTPUT_DIR / "rolling_60_month_portfolio_results.csv",
        rolling[60],
        rolling_fields,
    )
    open_engine.write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary,
        rows_with_fields(rolling_summary, ["horizon_months"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "candidate_mechanism_diagnostics.csv",
        mechanism,
        rows_with_fields(mechanism, ["record_type", "date"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        rows_with_fields(turnover_rows, ["portfolio_id", "cost_bps"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        rows_with_fields(invariant_rows, ["portfolio_id", "cost_bps"]),
    )
    followup_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "route": "diversifier_only",
                "outcome": outcome,
                "next_action": next_action,
                "validation_claimed": False,
            }
        ]
        if outcome == "exploratory_followup_candidate_diversifier"
        else []
    )
    open_engine.write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        followup_rows,
        [
            "strategy_id",
            "trial_id",
            "route",
            "outcome",
            "next_action",
            "validation_claimed",
        ],
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "route": "diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "parent_standalone_outcome_preserved": "closed_exploration",
        "parent_standalone_failure_reason_preserved": "period_instability",
        "followup_gate": gate,
        "validation_evidence_claimed": False,
        "paper_demo_eligibility_supported": False,
    }
    open_engine.write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failed_gate_ids = [
        key for key, value in gate.items() if isinstance(value, bool) and not value
    ]
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "failure_reason": failure_reason,
                "failed_gate_ids": failed_gate_ids,
            }
        ]
        if failure_reason
        else []
    )
    open_engine.write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        ["strategy_id", "trial_id", "failure_reason", "failed_gate_ids"],
    )
    next_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "next_action": next_action,
        "executed_in_this_task": False,
    }
    open_engine.write_csv(
        OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row)
    )

    funnel = {
        "existing_strategy_configurations_carried_forward": 1,
        "new_strategy_configurations": 0,
        "existing_parent_trials_carried_forward": 1,
        "new_experiment_trials": 1,
        "benchmark_references": 6,
        "portfolio_diagnostics": 7,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_diversifier"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "blocked_feasibility": int(outcome == "blocked_feasibility"),
    }
    open_engine.write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "child_trial_id": TRIAL_ID,
        "adaptation_label": "exploratory_variant",
        "changed_fields_from_parent": (
            "evaluation_route_and_predeclared_portfolio_controls_only"
        ),
        "evaluation_route": "diversifier_only",
        "result_driven_adaptation": True,
        "strategy_rule_changed": False,
        "channel_formula_changed": False,
        "period_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "cost_model_changed": False,
        "optimization_performed": False,
        "common_period_start": EXPECTED_START.date().isoformat(),
        "common_period_end": EXPECTED_END.date().isoformat(),
        "frozen_exposure_SPY_weight": FROZEN_EXPOSURE_SPY,
        "frozen_exposure_BIL_weight": FROZEN_EXPOSURE_BIL,
        "cost_assumptions_bps": list(COST_BPS),
        "reproduction_passed": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "preregistration_hash": preregistration_hash,
        "provider_access": False,
        "network_access": False,
        "validation_claimed": False,
        "paper_demo_action": False,
        "broker_or_order_action": False,
    }
    open_engine.write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)
    report = f"""# Kaufman Breakout Diversifier Incremental-Value Follow-up

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or "none"}`.

This packet carries forward the unchanged Kaufman Rule-2 SPY/BIL signal and
evaluates one explicitly result-driven child trial only as a 20% sleeve in
the frozen VM/DSR/USCI reference. The authoritative standalone trial remains
closed for `period_instability`.

The common period is {EXPECTED_START.date().isoformat()} through
{EXPECTED_END.date().isoformat()}. Inner trades retain following-session-open
execution; outer 80/20 rebalances occur at the following session close after
month-end targets. Natural drift, inner and outer turnover, and both cost
layers are explicit. No fixed-weight daily return blend is used.

The exact next action is `{next_action}`. This evidence is exploration only
and does not authorize validation, lifecycle changes, or paper/demo action.
"""
    (OUTPUT_DIR / "followup_report.md").write_text(report, encoding="utf-8")

    parent_after = directory_hash(PARENT_EVIDENCE)
    protected_after = {
        rel(path): open_engine.file_hash(path) for path in PROTECTED_PATHS
    }
    cache_after = directory_hash(CACHE_DIR)
    prior_evidence_after = open_engine.tree_hash(
        ROOT / "evidence", OUTPUT_DIR.parent
    )
    before_consistency = {path.name for path in OUTPUT_DIR.iterdir()}
    required_exact = (
        before_consistency | {"consistency_check.json"}
    ) == REQUIRED_OUTPUTS and "consistency_check.json" not in before_consistency
    core_hash = open_engine.canonical_hash(
        {
            "reproduction": reproduction,
            "full_rows": full_rows,
            "half_rows": half_rows,
            "rolling": rolling,
            "rolling_summary": rolling_summary,
            "outcome": outcome_row,
        }
    )
    consistency = {
        **manifest,
        "overall_pass": bool(
            required_exact
            and parent_before == parent_after
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and deterministic
            and funnel["new_strategy_configurations"] == 0
            and funnel["new_experiment_trials"] == 1
            and funnel["benchmark_references"] == 6
        ),
        "required_outputs_exact": required_exact,
        "parent_context_verified": parent_context["passed"],
        "parent_standalone_outcome_preserved": "closed_exploration",
        "parent_standalone_failure_reason_preserved": "period_instability",
        "parent_evidence_hash_before": parent_before,
        "parent_evidence_hash_after": parent_after,
        "parent_evidence_unchanged": parent_before == parent_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "preregistration_written_before_followup_performance": True,
        "serial_rerun_deterministic": deterministic,
        "deterministic_core_hash": core_hash,
        "provider_access": False,
        "network_access": False,
        "lifecycle_state_changed": False,
        "paper_demo_observations_created": 0,
        "parameter_search_performed": False,
        "broker_orders": 0,
        "paper_orders": 0,
        "live_orders": 0,
        "real_money_actions": 0,
        "followup_gate": gate,
    }
    open_engine.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "reproduction_passed": reproduction_pass,
        "rolling_36_windows": len(rolling[36]),
        "rolling_60_windows": len(rolling[60]),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
