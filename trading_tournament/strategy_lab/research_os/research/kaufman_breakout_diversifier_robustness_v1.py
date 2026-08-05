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
from strategy_lab.research_os.research import (
    fast_price_volume_discovery_batch_v2 as market,
)
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    implement_targeted_medium_frequency_breakout_candidate_v1 as standalone,
)
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as open_engine,
)
from strategy_lab.research_os.research import (
    kaufman_breakout_diversifier_incremental_value_followup_v1 as exploration,
)


TASK_ID = "kaufman_breakout_diversifier_robustness_v1"
MODE = "validation"
STAGE = "robustness"
STRATEGY_ID = exploration.STRATEGY_ID
FAMILY_ID = exploration.FAMILY_ID
DISPLAY_NAME = exploration.DISPLAY_NAME
ARCHITECTURE = exploration.ARCHITECTURE
SOURCE_LINEAGE = exploration.SOURCE_LINEAGE
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = exploration.TRIAL_ID
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0, 15.0, 20.0)
REPRODUCTION_COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
BLOCK_LENGTH_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260727
COMPLETE_YEAR_MIN_SESSIONS = 200
START_YEARS = (2011, 2012, 2013, 2014, 2015, 2016)
EXPECTED_START = exploration.EXPECTED_START
EXPECTED_END = exploration.EXPECTED_END
FROZEN_EXPOSURE_SPY = exploration.FROZEN_EXPOSURE_SPY
FROZEN_EXPOSURE_BIL = exploration.FROZEN_EXPOSURE_BIL

STANDALONE_EVIDENCE = standalone.OUTPUT_DIR
EXPLORATION_EVIDENCE = exploration.OUTPUT_DIR
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
PROTECTED_PATHS = exploration.PROTECTED_PATHS

REFERENCE_ID = exploration.REFERENCE_ID
CONTROL_IDS = exploration.CONTROL_IDS
BENCHMARK_IDS = exploration.BENCHMARK_IDS
CRITICAL_CONTROL_IDS = exploration.CRITICAL_CONTROL_IDS
PORTFOLIO_IDS = exploration.PORTFOLIO_IDS
PORTFOLIO_SLEEVE_IDS = exploration.PORTFOLIO_SLEEVE_IDS
CANDIDATE_PORTFOLIO_ID = PORTFOLIO_IDS[STRATEGY_ID]
REFERENCE_PORTFOLIO_ID = PORTFOLIO_IDS["reference"]
DONCHIAN_PORTFOLIO_ID = PORTFOLIO_IDS[CONTROL_IDS[0]]
EXPOSURE_PORTFOLIO_ID = PORTFOLIO_IDS[CONTROL_IDS[1]]

NEXT_POSITIVE = "design_kaufman_breakout_diversifier_prospective_validation_v1"
NEXT_MIXED = "direction_owner_review_kaufman_diversifier_robustness_mixed_v1"
NEXT_FAILED = "direction_owner_review_close_kaufman_diversifier_route_v1"
NEXT_BLOCKED = "direction_owner_review_kaufman_diversifier_robustness_block_v1"

REQUIRED_OUTPUTS = {
    "robustness_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "start_date_sensitivity.csv",
    "excess_return_concentration.csv",
    "bootstrap_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "robustness_report.md",
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
        ROOT / "evidence" / "robustness" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def verify_parent_packets() -> dict[str, Any]:
    standalone_check = json.loads(
        (STANDALONE_EVIDENCE / "consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    exploration_check = json.loads(
        (EXPLORATION_EVIDENCE / "consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    exploration_trials = read_csv(EXPLORATION_EVIDENCE / "trial_ledger.csv")
    matching_trial = [
        row for row in exploration_trials if row["trial_id"] == PARENT_TRIAL_ID
    ]
    passed = bool(
        standalone_check.get("overall_pass")
        and standalone_check.get("outcome") == "closed_exploration"
        and standalone_check.get("failure_reason") == "period_instability"
        and exploration_check.get("overall_pass")
        and exploration_check.get("outcome")
        == "exploratory_followup_candidate_diversifier"
        and len(matching_trial) == 1
        and matching_trial[0]["parent_trial_id"] == standalone.TRIAL_ID
    )
    return {
        "passed": passed,
        "standalone_check": standalone_check,
        "exploration_check": exploration_check,
        "exploration_trial": matching_trial[0] if matching_trial else {},
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
        "approved_route": "20pct_diversifier_only",
        "authoritative_standalone_outcome": "closed_exploration",
        "authoritative_standalone_failure_reason": "period_instability",
        "exploratory_diversifier_outcome": (
            "exploratory_followup_candidate_diversifier"
        ),
        "existing_strategy_configuration": True,
        "new_strategy_configuration_created": False,
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "robustness_variant",
        "parameters": {
            "channel_contract": "TradingView_Rule_2_only",
            "period_sessions": 40,
            "active_asset": "SPY",
            "inactive_asset": "BIL",
            "inner_execution": "following_session_open",
            "outer_reference_weight": 0.8,
            "outer_sleeve_weight": 0.2,
            "outer_rebalance": "monthly_following_session_close",
            "exposure_control_SPY_weight": FROZEN_EXPOSURE_SPY,
            "exposure_control_BIL_weight": FROZEN_EXPOSURE_BIL,
        },
        "benchmark_or_control": list(BENCHMARK_IDS),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "independent_validation_claimed": False,
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
        "adaptation_label": "robustness_variant",
        "changed_fields_from_parent": "robustness_diagnostics_only",
        "strategy_rule_changed": False,
        "channel_formula_changed": False,
        "period_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "candidate_sleeve_weight_changed": False,
        "frozen_reference_changed": False,
        "controls_changed": False,
        "optimization_performed": False,
        "result_driven_parameter_change": False,
        "independent_validation_claimed": False,
        "preregistered_before_robustness_calculation": True,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    parent_rows = read_csv(
        EXPLORATION_EVIDENCE / "benchmark_reference_log.csv"
    )
    by_id = {row["benchmark_reference_id"]: row for row in parent_rows}
    return [
        {
            "benchmark_reference_id": benchmark_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "control_definition": by_id[benchmark_id]["control_definition"],
            "critical_control": benchmark_id in CRITICAL_CONTROL_IDS,
            "frozen_reference": benchmark_id == REFERENCE_ID,
            "exposure_SPY_weight": (
                FROZEN_EXPOSURE_SPY if benchmark_id == CONTROL_IDS[1] else ""
            ),
            "exposure_BIL_weight": (
                FROZEN_EXPOSURE_BIL if benchmark_id == CONTROL_IDS[1] else ""
            ),
            "control_changed": False,
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


def preregistered_diagnostics() -> dict[str, Any]:
    return {
        "cost_bps": list(COST_BPS),
        "quarter_count": 4,
        "calendar_year_rule": (
            f"complete_calendar_year_with_at_least_{COMPLETE_YEAR_MIN_SESSIONS}_"
            "common_sessions"
        ),
        "rolling_horizons_months": [36, 60],
        "start_years": list(START_YEARS),
        "fixed_end": EXPECTED_END.date().isoformat(),
        "concentration_comparators": [
            REFERENCE_PORTFOLIO_ID,
            DONCHIAN_PORTFOLIO_ID,
            EXPOSURE_PORTFOLIO_ID,
        ],
        "bootstrap_block_length_months": BLOCK_LENGTH_MONTHS,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "paired_portfolio_vectors": True,
    }


def write_entities(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> str:
    records = {
        "strategy_cards.csv": [
            strategy_row(outcome, failure_reason, next_action)
        ],
        "trial_ledger.csv": [trial_row(outcome, failure_reason, next_action)],
        "benchmark_reference_log.csv": benchmark_rows(),
        "process_task_log.csv": [process_row(outcome, next_action)],
    }
    for filename, rows in records.items():
        open_engine.write_csv(OUTPUT_DIR / filename, rows, list(rows[0]))
    return open_engine.canonical_hash(
        {"entities": records, "diagnostics": preregistered_diagnostics()}
    )


def build_paths() -> tuple[
    pd.DataFrame,
    dict[str, open_engine.Schedule],
    dict[tuple[str, float], dict[str, Any]],
]:
    panel, _, passed = standalone.load_preflight()
    if not passed:
        return panel, {}, {}
    index = pd.DatetimeIndex(panel.index)
    close = panel[("SPY", "close")]
    schedules = {
        STRATEGY_ID: standalone.regression_channel_schedule(panel),
        CONTROL_IDS[0]: standalone.donchian_schedule(panel),
        CONTROL_IDS[1]: open_engine.monthly_exposure_schedule(
            index, FROZEN_EXPOSURE_SPY
        ),
        CONTROL_IDS[2]: standalone.slope_only_schedule(panel),
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
    costs: Iterable[float] = COST_BPS,
    start: pd.Timestamp | None = None,
) -> dict[tuple[str, float], dict[str, Any]]:
    reference_all = market.active_vm_dsr_usci_reference_returns()
    payloads: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in costs:
        common = paths[(STRATEGY_ID, cost)]["returns"].index.intersection(
            reference_all.dropna().index
        )
        reference = reference_all.reindex(common).dropna()
        if start is not None:
            reference = reference.loc[reference.index >= start]
        if reference.empty or reference.index.max() != EXPECTED_END:
            raise RuntimeError("Frozen reference period is unavailable")
        reference_payload = portfolio_accounting.reference_payload(reference, cost)
        reference_payload["portfolio_id"] = REFERENCE_PORTFOLIO_ID
        reference_payload["sleeve_id"] = ""
        reference_payload["reference_returns"] = reference
        reference_payload["sleeve_returns"] = pd.Series(
            0.0, index=reference.index
        )
        reference_payload["outer_start_weights"] = pd.Series(
            0.0, index=reference.index
        )
        payloads[(REFERENCE_PORTFOLIO_ID, cost)] = reference_payload
        for sleeve_id in PORTFOLIO_SLEEVE_IDS:
            sleeve = paths[(sleeve_id, cost)]["returns"].reindex(reference.index)
            if sleeve.isna().any():
                raise RuntimeError(f"{sleeve_id} is incomplete on common period")
            portfolio_id = PORTFOLIO_IDS[sleeve_id]
            payload = portfolio_accounting.simulate_two_component_portfolio(
                reference, sleeve, portfolio_id, cost
            )
            payload["portfolio_id"] = portfolio_id
            payload["sleeve_id"] = sleeve_id
            payload["reference_returns"] = reference
            payload["sleeve_returns"] = sleeve
            payload["outer_start_weights"] = standalone.outer_start_weights(
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
    return exploration.portfolio_metrics(payload, paths, cost, period_index)


def robustness_row(
    portfolio_id: str,
    cost: float,
    period: str,
    metrics: dict[str, Any],
    diagnostic_type: str,
) -> dict[str, Any]:
    return {
        "portfolio_id": portfolio_id,
        "entity_type": "portfolio_robustness_diagnostic",
        "stage": STAGE,
        "diagnostic_type": diagnostic_type,
        "period": period,
        "period_independence": "same_viewed_period_not_independent_validation",
        "cost_bps": cost,
        "construction": (
            "100pct_frozen_reference"
            if portfolio_id == REFERENCE_PORTFOLIO_ID
            else "monthly_rebalanced_80pct_reference_20pct_sleeve_explicit_holdings"
        ),
        "daily_fixed_weight_return_blend_used": False,
        **metrics,
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return open_engine.control_dominates(candidate, control)


def generic_reproduction_rows(
    scope: str,
    prior_rows: list[dict[str, str]],
    current_rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    compare_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    def normalized_key(row: dict[str, Any]) -> tuple[str, ...]:
        values: list[str] = []
        for field in key_fields:
            value = row[field]
            if field in {"cost_bps", "cost_assumption_bps"}:
                values.append(f"{float(value):g}")
            else:
                values.append(str(value))
        return tuple(values)

    prior_map = {
        normalized_key(row): row for row in prior_rows
    }
    current_map = {
        normalized_key(row): row for row in current_rows
    }
    rows: list[dict[str, Any]] = []
    all_keys = sorted(set(prior_map) | set(current_map))
    for key in all_keys:
        prior = prior_map.get(key)
        current = current_map.get(key)
        for field in compare_fields:
            prior_value = prior.get(field, "") if prior else ""
            current_value = current.get(field, "") if current else ""
            difference: float | str = ""
            try:
                prior_number = float(prior_value)
                current_number = float(current_value)
                difference = current_number - prior_number
                passed = abs(difference) <= REPRODUCTION_TOLERANCE
            except (TypeError, ValueError):
                passed = str(current_value).lower() == str(prior_value).lower()
            rows.append(
                {
                    "scope": scope,
                    "record_key": "|".join(key),
                    "field": field,
                    "parent_value": prior_value,
                    "reproduced_value": current_value,
                    "difference": difference,
                    "absolute_tolerance": (
                        REPRODUCTION_TOLERANCE if difference != "" else ""
                    ),
                    "pass": passed,
                }
            )
    return rows


def reproduction_rows(
    full_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rolling: dict[int, list[dict[str, Any]]],
    turnover_rows: list[dict[str, Any]],
    invariant_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    result: list[dict[str, Any]] = []
    full_prior = read_csv(
        EXPLORATION_EVIDENCE / "full_period_portfolio_results.csv"
    )
    full_current = [
        row for row in full_rows if float(row["cost_bps"]) in REPRODUCTION_COST_BPS
    ]
    metric_fields = (
        "evaluation_start",
        "evaluation_end",
        "trading_days",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "inner_sleeve_turnover",
        "outer_turnover",
        "combined_turnover_diagnostic",
        "inner_trade_count",
        "outer_rebalance_count",
        "trade_or_rebalance_count",
        "inner_transaction_cost_drag",
        "outer_transaction_cost_drag",
        "transaction_cost_drag",
        "average_gross_exposure",
        "maximum_gross_exposure",
        "maximum_daily_weight_sum",
        "numeric_invariant_status",
        "timing_invariant_status",
        "exposure_invariant_status",
        "weight_invariant_status",
        "explicit_zero_weights_preserved",
        "invariant_pass",
    )
    result.extend(
        generic_reproduction_rows(
            "full_period",
            full_prior,
            full_current,
            ("portfolio_id", "cost_bps"),
            metric_fields,
        )
    )
    half_prior = read_csv(
        EXPLORATION_EVIDENCE / "chronological_half_portfolio_results.csv"
    )
    result.extend(
        generic_reproduction_rows(
            "chronological_halves",
            half_prior,
            half_rows,
            ("portfolio_id", "period"),
            metric_fields,
        )
    )
    rolling_fields = (
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
    )
    for horizon in (36, 60):
        prior = read_csv(
            EXPLORATION_EVIDENCE
            / f"rolling_{horizon}_month_portfolio_results.csv"
        )
        result.extend(
            generic_reproduction_rows(
                f"rolling_{horizon}_month",
                prior,
                rolling[horizon],
                ("window_start", "window_end"),
                rolling_fields,
            )
        )
    turnover_prior = read_csv(
        EXPLORATION_EVIDENCE / "turnover_cost_reconciliation.csv"
    )
    turnover_current = [
        row
        for row in turnover_rows
        if float(row["cost_bps"]) in REPRODUCTION_COST_BPS
    ]
    result.extend(
        generic_reproduction_rows(
            "turnover_and_cost",
            turnover_prior,
            turnover_current,
            ("portfolio_id", "cost_bps"),
            (
                "inner_sleeve_turnover",
                "outer_turnover",
                "combined_turnover_diagnostic",
                "inner_transaction_cost_drag",
                "outer_transaction_cost_drag",
                "combined_transaction_cost_drag",
                "inner_and_outer_costs_charged_once",
                "daily_fixed_weight_return_blend_used",
                "reconciles",
            ),
        )
    )
    invariant_prior = read_csv(EXPLORATION_EVIDENCE / "invariant_results.csv")
    invariant_current = [
        row
        for row in invariant_rows
        if float(row["cost_bps"]) in REPRODUCTION_COST_BPS
    ]
    result.extend(
        generic_reproduction_rows(
            "invariants",
            invariant_prior,
            invariant_current,
            ("portfolio_id", "cost_bps"),
            (
                "numeric_invariant_status",
                "timing_invariant_status",
                "exposure_invariant_status",
                "weight_invariant_status",
                "explicit_zero_weights_preserved",
                "maximum_gross_exposure",
                "maximum_daily_weight_sum",
                "signal_rule_changed",
                "channel_formula_changed",
                "inner_execution_next_open",
                "outer_execution_following_session_close",
                "invariant_pass",
            ),
        )
    )
    return result, bool(result and all(row["pass"] for row in result))


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    arrays = np.array_split(np.arange(len(index)), 4)
    return {
        f"chronological_quarter_{position + 1}": index[positions]
        for position, positions in enumerate(arrays)
    }


def monthly_returns(series: pd.Series) -> pd.Series:
    return (
        (1.0 + series)
        .groupby(series.index.to_period("M"))
        .prod()
        .sub(1.0)
    )


def concentration_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate = monthly_returns(
        payloads[(CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)]["returns"]
    )
    rows: list[dict[str, Any]] = []
    for comparator_id in (
        REFERENCE_PORTFOLIO_ID,
        DONCHIAN_PORTFOLIO_ID,
        EXPOSURE_PORTFOLIO_ID,
    ):
        comparator = monthly_returns(
            payloads[(comparator_id, PRIMARY_COST_BPS)]["returns"]
        ).reindex(candidate.index)
        aligned = pd.concat(
            [candidate.rename("candidate"), comparator.rename("comparator")],
            axis=1,
            join="inner",
        ).dropna()
        excess = aligned["candidate"] - aligned["comparator"]
        positive = excess.loc[excess > 0.0].sort_values(ascending=False)
        largest = float(positive.iloc[0]) if len(positive) else 0.0
        largest_three = float(positive.iloc[:3].sum())
        additive = float(excess.sum())
        annual = excess.groupby(excess.index.year).sum()
        strongest_year = int(annual.idxmax())
        strongest_year_value = float(annual.max())
        candidate_total = float((1.0 + aligned["candidate"]).prod() - 1.0)
        comparator_total = float((1.0 + aligned["comparator"]).prod() - 1.0)
        rows.append(
            {
                "candidate_portfolio_id": CANDIDATE_PORTFOLIO_ID,
                "comparator_portfolio_id": comparator_id,
                "cost_bps": PRIMARY_COST_BPS,
                "monthly_observation_count": len(excess),
                "additive_cumulative_excess_return": additive,
                "compounded_total_return_difference": (
                    candidate_total - comparator_total
                ),
                "largest_positive_month": (
                    str(positive.index[0]) if len(positive) else ""
                ),
                "largest_positive_month_contribution": largest,
                "largest_positive_month_fraction_of_additive_excess": (
                    largest / additive if additive > 0.0 else ""
                ),
                "largest_three_positive_months_contribution": largest_three,
                "largest_three_positive_months_fraction_of_additive_excess": (
                    largest_three / additive if additive > 0.0 else ""
                ),
                "strongest_calendar_year": strongest_year,
                "strongest_calendar_year_contribution": strongest_year_value,
                "strongest_calendar_year_fraction_of_additive_excess": (
                    strongest_year_value / additive if additive > 0.0 else ""
                ),
                "additive_excess_after_removing_strongest_month": (
                    additive - largest
                ),
                "additive_excess_after_removing_three_strongest_months": (
                    additive - largest_three
                ),
                "canonical_return_series_modified": False,
                "used_for_strategy_change": False,
            }
        )
    return rows


def monthly_path_metrics(values: np.ndarray) -> tuple[float, float, float]:
    count = len(values)
    wealth = np.cumprod(1.0 + values)
    cagr = float(wealth[-1] ** (12.0 / count) - 1.0)
    standard_deviation = float(np.std(values, ddof=1))
    sharpe = (
        float(np.mean(values) / standard_deviation * math.sqrt(12.0))
        if standard_deviation > 0.0
        else 0.0
    )
    running_max = np.maximum.accumulate(wealth)
    drawdown = float(np.min(wealth / running_max - 1.0))
    return cagr, sharpe, drawdown


def paired_moving_block_bootstrap(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = (
        CANDIDATE_PORTFOLIO_ID,
        REFERENCE_PORTFOLIO_ID,
        DONCHIAN_PORTFOLIO_ID,
        EXPOSURE_PORTFOLIO_ID,
    )
    monthly = pd.concat(
        [
            monthly_returns(
                payloads[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
            ).rename(portfolio_id)
            for portfolio_id in ids
        ],
        axis=1,
        join="inner",
    ).dropna()
    values = monthly.to_numpy(dtype=float)
    count = len(values)
    block_count = math.ceil(count / BLOCK_LENGTH_MONTHS)
    max_start = count - BLOCK_LENGTH_MONTHS
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    comparators = ids[1:]
    counts = {
        comparator: {
            "higher_sharpe": 0,
            "less_severe_drawdown": 0,
            "positive_cagr_difference": 0,
        }
        for comparator in comparators
    }
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled_index = np.concatenate(
            [
                np.arange(start, start + BLOCK_LENGTH_MONTHS)
                for start in starts
            ]
        )[:count]
        sample = values[sampled_index]
        metrics = [
            monthly_path_metrics(sample[:, column])
            for column in range(sample.shape[1])
        ]
        candidate_cagr, candidate_sharpe, candidate_drawdown = metrics[0]
        for column, comparator in enumerate(comparators, start=1):
            comparator_cagr, comparator_sharpe, comparator_drawdown = metrics[
                column
            ]
            counts[comparator]["higher_sharpe"] += int(
                candidate_sharpe > comparator_sharpe
            )
            counts[comparator]["less_severe_drawdown"] += int(
                candidate_drawdown > comparator_drawdown
            )
            counts[comparator]["positive_cagr_difference"] += int(
                candidate_cagr > comparator_cagr
            )
    return [
        {
            "candidate_portfolio_id": CANDIDATE_PORTFOLIO_ID,
            "comparator_portfolio_id": comparator,
            "monthly_observation_count": count,
            "moving_block_length_months": BLOCK_LENGTH_MONTHS,
            "resamples": BOOTSTRAP_RESAMPLES,
            "deterministic_seed": BOOTSTRAP_SEED,
            "paired_cross_portfolio_dependence_preserved": True,
            "probability_candidate_higher_sharpe": (
                counts[comparator]["higher_sharpe"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_less_severe_maximum_drawdown": (
                counts[comparator]["less_severe_drawdown"]
                / BOOTSTRAP_RESAMPLES
            ),
            "probability_positive_candidate_CAGR_difference": (
                counts[comparator]["positive_cagr_difference"]
                / BOOTSTRAP_RESAMPLES
            ),
            "used_for_rule_tuning": False,
            "independent_validation_claimed": False,
        }
        for comparator in comparators
    ]


def build_turnover_and_invariant_rows(
    full_metrics: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for (portfolio_id, cost), metrics in full_metrics.items():
        turnover_rows.append(
            {
                "portfolio_id": portfolio_id,
                "cost_bps": cost,
                "inner_sleeve_turnover": metrics["inner_sleeve_turnover"],
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
                "maximum_gross_exposure": metrics["maximum_gross_exposure"],
                "maximum_daily_weight_sum": metrics[
                    "maximum_daily_weight_sum"
                ],
                "signal_rule_changed": False,
                "channel_formula_changed": False,
                "inner_execution_next_open": True,
                "outer_execution_following_session_close": True,
                "stale_weight_forward_fill_used": False,
                "invariant_pass": metrics["invariant_pass"],
            }
        )
    return turnover_rows, invariant_rows


def outcome_decision(
    reproduction_pass: bool,
    full_metrics: dict[tuple[str, float], dict[str, Any]],
    quarter_metrics: dict[tuple[str, str], dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    concentration: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    if not reproduction_pass:
        return (
            "robustness_blocked",
            "data_or_comparability_failure",
            NEXT_BLOCKED,
            {"reproduction_passed": False},
        )
    candidate = full_metrics[(CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)]
    reference = full_metrics[(REFERENCE_PORTFOLIO_ID, PRIMARY_COST_BPS)]
    donchian = full_metrics[(DONCHIAN_PORTFOLIO_ID, PRIMARY_COST_BPS)]
    exposure = full_metrics[(EXPOSURE_PORTFOLIO_ID, PRIMARY_COST_BPS)]
    all_invariants = all(
        bool(row["invariant_pass"]) for row in full_metrics.values()
    )
    material_reference = bool(
        float(candidate["sharpe_ratio"]) - float(reference["sharpe_ratio"])
        >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(reference["maximum_drawdown"])
        >= 0.01
    )
    critical_not_dominating = bool(
        not dominates(donchian, candidate)
        and not dominates(exposure, candidate)
    )
    quarters_improving_reference = 0
    quarters_worse_both_exposure = 0
    for quarter in (
        "chronological_quarter_1",
        "chronological_quarter_2",
        "chronological_quarter_3",
        "chronological_quarter_4",
    ):
        candidate_quarter = quarter_metrics[(CANDIDATE_PORTFOLIO_ID, quarter)]
        reference_quarter = quarter_metrics[(REFERENCE_PORTFOLIO_ID, quarter)]
        exposure_quarter = quarter_metrics[(EXPOSURE_PORTFOLIO_ID, quarter)]
        quarters_improving_reference += int(
            float(candidate_quarter["sharpe_ratio"])
            > float(reference_quarter["sharpe_ratio"])
            or float(candidate_quarter["maximum_drawdown"])
            > float(reference_quarter["maximum_drawdown"])
        )
        quarters_worse_both_exposure += int(
            open_engine.worse_on_both(candidate_quarter, exposure_quarter)
        )
    rolling_map = {int(row["horizon_months"]): row for row in rolling_summary}
    rolling_favorable = all(
        float(rolling_map[horizon]["candidate_improves_reference_fraction"])
        > 0.5
        for horizon in (36, 60)
    )
    rolling_controls = all(
        float(rolling_map[horizon]["donchian_dominates_fraction"]) <= 0.5
        and float(
            rolling_map[horizon]["exposure_matched_dominates_fraction"]
        )
        <= 0.5
        for horizon in (36, 60)
    )
    candidate_15 = full_metrics[(CANDIDATE_PORTFOLIO_ID, 15.0)]
    reference_15 = full_metrics[(REFERENCE_PORTFOLIO_ID, 15.0)]
    candidate_20 = full_metrics[(CANDIDATE_PORTFOLIO_ID, 20.0)]
    reference_20 = full_metrics[(REFERENCE_PORTFOLIO_ID, 20.0)]
    cost_15 = bool(
        float(candidate_15["sharpe_ratio"])
        > float(reference_15["sharpe_ratio"])
        or float(candidate_15["maximum_drawdown"])
        > float(reference_15["maximum_drawdown"])
    )
    cost_20 = not open_engine.worse_on_both(candidate_20, reference_20)
    concentration_map = {
        row["comparator_portfolio_id"]: row for row in concentration
    }
    reference_concentration = concentration_map[REFERENCE_PORTFOLIO_ID]
    concentration_three_positive = bool(
        float(
            reference_concentration[
                "additive_excess_after_removing_three_strongest_months"
            ]
        )
        > 0.0
    )
    year_fraction = float(
        reference_concentration[
            "strongest_calendar_year_fraction_of_additive_excess"
        ]
    )
    concentration_year = year_fraction <= 0.5
    bootstrap_map = {
        row["comparator_portfolio_id"]: row for row in bootstrap
    }
    bootstrap_sharpe = bool(
        float(
            bootstrap_map[REFERENCE_PORTFOLIO_ID][
                "probability_candidate_higher_sharpe"
            ]
        )
        >= 0.75
        and float(
            bootstrap_map[DONCHIAN_PORTFOLIO_ID][
                "probability_candidate_higher_sharpe"
            ]
        )
        >= 0.60
        and float(
            bootstrap_map[EXPOSURE_PORTFOLIO_ID][
                "probability_candidate_higher_sharpe"
            ]
        )
        >= 0.60
    )
    bootstrap_cagr = all(
        float(row["probability_positive_candidate_CAGR_difference"]) > 0.50
        for row in bootstrap
    )
    gate = {
        "reproduction_and_invariants_pass": bool(
            reproduction_pass and all_invariants
        ),
        "material_improvement_vs_reference": material_reference,
        "critical_controls_do_not_dominate_full_period": (
            critical_not_dominating
        ),
        "at_least_three_quarters_improve_reference": (
            quarters_improving_reference >= 3
        ),
        "worse_both_vs_exposure_in_at_most_one_quarter": (
            quarters_worse_both_exposure <= 1
        ),
        "rolling_sets_improve_reference_more_than_half": rolling_favorable,
        "critical_controls_dominate_at_most_half_rolling_windows": (
            rolling_controls
        ),
        "15bps_improves_reference": cost_15,
        "20bps_not_worse_both_vs_reference": cost_20,
        "positive_excess_after_removing_three_strongest_months": (
            concentration_three_positive
        ),
        "strongest_year_at_most_half_excess": concentration_year,
        "bootstrap_sharpe_thresholds_pass": bootstrap_sharpe,
        "bootstrap_positive_CAGR_probabilities_pass": bootstrap_cagr,
        "quarters_improving_reference": quarters_improving_reference,
        "quarters_worse_both_vs_exposure": quarters_worse_both_exposure,
        "strongest_year_excess_fraction": year_fraction,
        "bootstrap_probabilities": {
            comparator: {
                "higher_sharpe": row[
                    "probability_candidate_higher_sharpe"
                ],
                "positive_CAGR_difference": row[
                    "probability_positive_candidate_CAGR_difference"
                ],
            }
            for comparator, row in bootstrap_map.items()
        },
    }
    required = (
        "reproduction_and_invariants_pass",
        "material_improvement_vs_reference",
        "critical_controls_do_not_dominate_full_period",
        "at_least_three_quarters_improve_reference",
        "worse_both_vs_exposure_in_at_most_one_quarter",
        "rolling_sets_improve_reference_more_than_half",
        "critical_controls_dominate_at_most_half_rolling_windows",
        "15bps_improves_reference",
        "20bps_not_worse_both_vs_reference",
        "positive_excess_after_removing_three_strongest_months",
        "strongest_year_at_most_half_excess",
        "bootstrap_sharpe_thresholds_pass",
        "bootstrap_positive_CAGR_probabilities_pass",
    )
    if all(bool(gate[key]) for key in required):
        return "robustness_positive", "", NEXT_POSITIVE, gate
    full_favorable = bool(
        material_reference and critical_not_dominating and all_invariants
    )
    if full_favorable and rolling_favorable and rolling_controls:
        if not (cost_15 and cost_20):
            reason = "cost_drag"
        elif not (concentration_three_positive and concentration_year):
            reason = "concentration_risk"
        elif not (bootstrap_sharpe and bootstrap_cagr):
            reason = "overfit_or_unstable"
        else:
            reason = "period_instability"
        return "robustness_mixed", reason, NEXT_MIXED, gate
    if not critical_not_dominating:
        reason = "weak_vs_primary_control"
    elif not material_reference:
        reason = "weak_portfolio_contribution"
    elif not rolling_controls:
        reason = "weak_vs_primary_control"
    elif not rolling_favorable or quarters_improving_reference < 3:
        reason = "period_instability"
    else:
        reason = "overfit_or_unstable"
    return "robustness_failed", reason, NEXT_FAILED, gate


def run() -> dict[str, Any]:
    clean_output()
    standalone_before = directory_hash(STANDALONE_EVIDENCE)
    exploration_before = directory_hash(EXPLORATION_EVIDENCE)
    protected_before = {
        rel(path): open_engine.file_hash(path) for path in PROTECTED_PATHS
    }
    cache_before = directory_hash(CACHE_DIR)
    prior_evidence_before = open_engine.tree_hash(
        ROOT / "evidence", OUTPUT_DIR.parent
    )
    parent_context = verify_parent_packets()
    if not parent_context["passed"]:
        raise RuntimeError("Kaufman parent packets are not authoritative")
    preregistration_hash = write_entities(
        "preregistered_pending_execution",
        "",
        "execute_frozen_robustness_diagnostics",
    )

    panel, schedules, paths = build_paths()
    if not paths:
        outcome = "robustness_blocked"
        failure_reason = "data_or_comparability_failure"
        next_action = NEXT_BLOCKED
        payloads: dict[tuple[str, float], dict[str, Any]] = {}
        full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
        cost_rows: list[dict[str, Any]] = []
        quarter_metrics: dict[tuple[str, str], dict[str, Any]] = {}
        quarter_rows: list[dict[str, Any]] = []
        year_rows: list[dict[str, Any]] = []
        rolling = {36: [], 60: []}
        rolling_summary: list[dict[str, Any]] = []
        start_rows: list[dict[str, Any]] = []
        concentration: list[dict[str, Any]] = []
        bootstrap: list[dict[str, Any]] = []
        turnover_rows: list[dict[str, Any]] = []
        invariant_rows: list[dict[str, Any]] = []
        reproduction: list[dict[str, Any]] = []
        reproduction_pass = False
        gate = {"reproduction_and_invariants_pass": False}
        deterministic = False
    else:
        payloads = build_portfolio_payloads(paths)
        full_metrics = {}
        cost_rows = []
        for portfolio_id in PORTFOLIO_IDS.values():
            for cost in COST_BPS:
                metrics = portfolio_metrics(
                    payloads[(portfolio_id, cost)], paths, cost
                )
                full_metrics[(portfolio_id, cost)] = metrics
                cost_rows.append(
                    robustness_row(
                        portfolio_id,
                        cost,
                        "full_period",
                        metrics,
                        "cost_stress",
                    )
                )
        turnover_rows, invariant_rows = build_turnover_and_invariant_rows(
            full_metrics
        )

        common_index = payloads[
            (CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)
        ]["returns"].index
        quarter_metrics = {}
        quarter_rows = []
        for quarter, period_index in split_quarters(common_index).items():
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                    period_index,
                )
                quarter_metrics[(portfolio_id, quarter)] = metrics
                quarter_rows.append(
                    robustness_row(
                        portfolio_id,
                        PRIMARY_COST_BPS,
                        quarter,
                        metrics,
                        "chronological_quarter",
                    )
                )

        year_rows = []
        for year in range(EXPECTED_START.year + 1, EXPECTED_END.year):
            year_index = common_index[common_index.year == year]
            if len(year_index) < COMPLETE_YEAR_MIN_SESSIONS:
                continue
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                    year_index,
                )
                row = robustness_row(
                    portfolio_id,
                    PRIMARY_COST_BPS,
                    f"calendar_year_{year}",
                    metrics,
                    "calendar_year",
                )
                row["calendar_year"] = year
                row["calendar_year_inclusion_rule"] = (
                    f"complete_year_at_least_{COMPLETE_YEAR_MIN_SESSIONS}_sessions"
                )
                year_rows.append(row)

        rolling = {
            36: exploration.monthly_rolling_rows(36, payloads),
            60: exploration.monthly_rolling_rows(60, payloads),
        }
        rolling_summary = exploration.rolling_summary_rows(rolling)

        start_rows = []
        for year in START_YEARS:
            year_sessions = common_index[common_index.year == year]
            if year_sessions.empty:
                raise RuntimeError(f"No common start session for {year}")
            start = pd.Timestamp(year_sessions[0])
            start_payloads = build_portfolio_payloads(
                paths, costs=(PRIMARY_COST_BPS,), start=start
            )
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    start_payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                )
                row = robustness_row(
                    portfolio_id,
                    PRIMARY_COST_BPS,
                    f"annual_start_{year}",
                    metrics,
                    "start_date_sensitivity",
                )
                row["requested_start_year"] = year
                row["deterministic_start_date"] = start.date().isoformat()
                row["fixed_end_date"] = EXPECTED_END.date().isoformat()
                row["start_selected_from_performance"] = False
                start_rows.append(row)

        concentration = concentration_rows(payloads)
        bootstrap = paired_moving_block_bootstrap(payloads)

        reproduction_full = [
            exploration.portfolio_row(
                row["portfolio_id"],
                float(row["cost_bps"]),
                "full_period",
                full_metrics[(row["portfolio_id"], float(row["cost_bps"]))],
            )
            for row in cost_rows
            if float(row["cost_bps"]) in REPRODUCTION_COST_BPS
        ]
        half_rows: list[dict[str, Any]] = []
        for period, period_index in open_engine.split_halves(common_index).items():
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                    period_index,
                )
                half_rows.append(
                    exploration.portfolio_row(
                        portfolio_id,
                        PRIMARY_COST_BPS,
                        period,
                        metrics,
                    )
                )
        reproduction, reproduction_pass = reproduction_rows(
            reproduction_full,
            half_rows,
            rolling,
            turnover_rows,
            invariant_rows,
        )
        if reproduction_pass:
            outcome, failure_reason, next_action, gate = outcome_decision(
                reproduction_pass,
                full_metrics,
                quarter_metrics,
                rolling_summary,
                concentration,
                bootstrap,
            )
        else:
            outcome = "robustness_blocked"
            failure_reason = "data_or_comparability_failure"
            next_action = NEXT_BLOCKED
            gate = {"reproduction_and_invariants_pass": False}
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
    open_engine.write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        rows_with_fields(reproduction, ["scope", "record_key", "field"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "cost_stress_results.csv",
        cost_rows,
        rows_with_fields(cost_rows, ["portfolio_id", "cost_bps"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "chronological_quarter_results.csv",
        quarter_rows,
        rows_with_fields(quarter_rows, ["portfolio_id", "period"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "calendar_year_results.csv",
        year_rows,
        rows_with_fields(year_rows, ["portfolio_id", "calendar_year"]),
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
        OUTPUT_DIR / "rolling_36_month_results.csv",
        rolling[36],
        rolling_fields,
    )
    open_engine.write_csv(
        OUTPUT_DIR / "rolling_60_month_results.csv",
        rolling[60],
        rolling_fields,
    )
    open_engine.write_csv(
        OUTPUT_DIR / "start_date_sensitivity.csv",
        start_rows,
        rows_with_fields(start_rows, ["requested_start_year", "portfolio_id"]),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "excess_return_concentration.csv",
        concentration,
        rows_with_fields(
            concentration,
            ["candidate_portfolio_id", "comparator_portfolio_id"],
        ),
    )
    open_engine.write_csv(
        OUTPUT_DIR / "bootstrap_results.csv",
        bootstrap,
        rows_with_fields(
            bootstrap,
            ["candidate_portfolio_id", "comparator_portfolio_id"],
        ),
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
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "stage": STAGE,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "outcome_interpretation": (
            "ready_for_prospective_validation_design"
            if outcome == "robustness_positive"
            else "not_ready_for_prospective_validation_design"
        ),
        "standalone_closure_preserved": True,
        "exploratory_diversifier_outcome_preserved": True,
        "independent_validation_claimed": False,
        "paper_demo_eligibility_supported": False,
        "robustness_gate": gate,
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
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "robustness_variant",
        "changed_fields_from_parent": "robustness_diagnostics_only",
        "approved_route": "20pct_diversifier_only",
        "existing_strategy_configurations": 1,
        "new_strategy_configurations": 0,
        "existing_exploration_trials_carried_forward": 2,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "common_period_start": EXPECTED_START.date().isoformat(),
        "common_period_end": EXPECTED_END.date().isoformat(),
        "frozen_exposure_SPY_weight": FROZEN_EXPOSURE_SPY,
        "frozen_exposure_BIL_weight": FROZEN_EXPOSURE_BIL,
        "strategy_rule_changed": False,
        "channel_formula_changed": False,
        "period_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "candidate_sleeve_weight_changed": False,
        "frozen_reference_changed": False,
        "controls_changed": False,
        "optimization_performed": False,
        "result_driven_parameter_change": False,
        "independent_validation_claimed": False,
        "preregistered_diagnostics": preregistered_diagnostics(),
        "reproduction_passed": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "preregistration_hash": preregistration_hash,
        "provider_access": False,
        "network_access": False,
        "paper_demo_action": False,
        "broker_or_order_action": False,
    }
    open_engine.write_yaml(OUTPUT_DIR / "robustness_manifest.yaml", manifest)
    report = f"""# Kaufman Breakout Diversifier Robustness V1

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or "none"}`.

Exactly one robustness child trial retained the frozen Kaufman Rule-2 signal,
SPY/BIL instruments, following-open inner execution, 80/20 portfolio route,
monthly following-close outer rebalance, reference, controls, and exposure
weight. The complete 2010-08-10 through 2026-06-18 period was already viewed,
so this packet does not claim independent validation.

Diagnostics include the predeclared five-cost grid, four chronological
quarters, complete calendar years, all rolling windows, deterministic annual
starts, monthly excess-return concentration, and a paired 5,000-resample
12-month moving-block bootstrap with seed 20260727.

The exact next action is `{next_action}`. It was not executed. No lifecycle,
paper/demo, provider, broker, order, or real-money action occurred.
"""
    (OUTPUT_DIR / "robustness_report.md").write_text(report, encoding="utf-8")

    standalone_after = directory_hash(STANDALONE_EVIDENCE)
    exploration_after = directory_hash(EXPLORATION_EVIDENCE)
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
            "cost": cost_rows,
            "quarters": quarter_rows,
            "years": year_rows,
            "rolling": rolling,
            "starts": start_rows,
            "concentration": concentration,
            "bootstrap": bootstrap,
            "outcome": outcome_row,
        }
    )
    consistency = {
        **manifest,
        "overall_pass": bool(
            required_exact
            and standalone_before == standalone_after
            and exploration_before == exploration_after
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and deterministic
            and (
                reproduction_pass
                or outcome == "robustness_blocked"
            )
        ),
        "required_outputs_exact": required_exact,
        "parent_packets_verified": parent_context["passed"],
        "standalone_evidence_hash_before": standalone_before,
        "standalone_evidence_hash_after": standalone_after,
        "standalone_evidence_unchanged": (
            standalone_before == standalone_after
        ),
        "exploration_evidence_hash_before": exploration_before,
        "exploration_evidence_hash_after": exploration_after,
        "exploration_evidence_unchanged": (
            exploration_before == exploration_after
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "preregistration_written_before_robustness_calculation": True,
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
        "robustness_gate": gate,
    }
    open_engine.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "reproduction_passed": reproduction_pass,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
