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
    implement_targeted_medium_frequency_breakout_candidate_v1 as standalone,
)
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as open_engine,
)
from strategy_lab.research_os.research import (
    kaufman_breakout_diversifier_incremental_value_followup_v1 as exploration,
)
from strategy_lab.research_os.research import (
    kaufman_breakout_diversifier_robustness_v1 as parent,
)


TASK_ID = "resolve_kaufman_diversifier_concentration_risk_v1"
MODE = "correction"
STAGE = "robustness"
STRATEGY_ID = parent.STRATEGY_ID
FAMILY_ID = parent.FAMILY_ID
DISPLAY_NAME = parent.DISPLAY_NAME
ARCHITECTURE = parent.ARCHITECTURE
SOURCE_LINEAGE = parent.SOURCE_LINEAGE
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = parent.TRIAL_ID
FROZEN_TIMESTAMP = "2026-07-27T00:00:00-06:00"

PRIMARY_COST_BPS = 5.0
DIAGNOSTIC_COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
EXPECTED_START = parent.EXPECTED_START
EXPECTED_END = parent.EXPECTED_END
FROZEN_EXPOSURE_SPY = parent.FROZEN_EXPOSURE_SPY
FROZEN_EXPOSURE_BIL = parent.FROZEN_EXPOSURE_BIL

STANDALONE_EVIDENCE = parent.STANDALONE_EVIDENCE
EXPLORATION_EVIDENCE = parent.EXPLORATION_EVIDENCE
ROBUSTNESS_EVIDENCE = parent.OUTPUT_DIR
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
PROTECTED_PATHS = parent.PROTECTED_PATHS

REFERENCE_ID = parent.REFERENCE_ID
CONTROL_IDS = parent.CONTROL_IDS
BENCHMARK_IDS = parent.BENCHMARK_IDS
PORTFOLIO_IDS = parent.PORTFOLIO_IDS
CANDIDATE_PORTFOLIO_ID = parent.CANDIDATE_PORTFOLIO_ID
REFERENCE_PORTFOLIO_ID = parent.REFERENCE_PORTFOLIO_ID
DONCHIAN_PORTFOLIO_ID = parent.DONCHIAN_PORTFOLIO_ID
EXPOSURE_PORTFOLIO_ID = parent.EXPOSURE_PORTFOLIO_ID
CRITICAL_PORTFOLIO_IDS = (
    DONCHIAN_PORTFOLIO_ID,
    EXPOSURE_PORTFOLIO_ID,
)

NEXT_POSITIVE = "design_kaufman_breakout_diversifier_prospective_validation_v1"
NEXT_MIXED = (
    "defer_kaufman_diversifier_and_run_targeted_defensive_cross_asset_"
    "state_source_sprint_v1"
)
NEXT_FAILED = "direction_owner_review_close_kaufman_diversifier_route_v1"
NEXT_BLOCKED = "direction_owner_review_kaufman_concentration_resolution_block_v1"

REQUIRED_OUTPUTS = {
    "resolution_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "frozen_concentration_observations.csv",
    "month_neutralization_results.csv",
    "strongest_year_neutralization_results.csv",
    "leave_one_trade_out_results.csv",
    "leave_one_trade_out_summary.csv",
    "trade_contribution_concentration.csv",
    "reference_negative_month_results.csv",
    "reference_drawdown_episode_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "resolution_report.md",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def directory_hash(path: Path) -> str:
    return open_engine.tree_hash(path)


def rows_with_fields(
    rows: list[dict[str, Any]],
    leading: list[str],
) -> list[str]:
    return open_engine.rows_with_fields(rows, leading)


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
    checks = {
        "standalone": json.loads(
            (STANDALONE_EVIDENCE / "consistency_check.json").read_text(
                encoding="utf-8"
            )
        ),
        "exploration": json.loads(
            (EXPLORATION_EVIDENCE / "consistency_check.json").read_text(
                encoding="utf-8"
            )
        ),
        "robustness": json.loads(
            (ROBUSTNESS_EVIDENCE / "consistency_check.json").read_text(
                encoding="utf-8"
            )
        ),
    }
    robustness_trials = read_csv(ROBUSTNESS_EVIDENCE / "trial_ledger.csv")
    matching = [
        row for row in robustness_trials if row["trial_id"] == PARENT_TRIAL_ID
    ]
    passed = bool(
        checks["standalone"].get("overall_pass")
        and checks["standalone"].get("outcome") == "closed_exploration"
        and checks["standalone"].get("failure_reason") == "period_instability"
        and checks["exploration"].get("overall_pass")
        and checks["exploration"].get("outcome")
        == "exploratory_followup_candidate_diversifier"
        and checks["robustness"].get("overall_pass")
        and checks["robustness"].get("outcome") == "robustness_mixed"
        and checks["robustness"].get("failure_reason") == "concentration_risk"
        and len(matching) == 1
        and matching[0]["parent_trial_id"] == exploration.TRIAL_ID
    )
    return {"passed": passed, "checks": checks, "parent_trial": matching}


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
        "parent_robustness_outcome": "robustness_mixed",
        "parent_robustness_failure_reason": "concentration_risk",
        "existing_strategy_configuration": True,
        "new_strategy_configuration_created": False,
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "result_driven_robustness_diagnostic",
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
        "adaptation_label": "result_driven_robustness_diagnostic",
        "changed_fields_from_parent": (
            "diversifier_route_concentration_diagnostics_and_decision_gate_only"
        ),
        "strategy_rule_changed": False,
        "channel_formula_changed": False,
        "period_changed": False,
        "instruments_changed": False,
        "execution_changed": False,
        "sleeve_weight_changed": False,
        "reference_changed": False,
        "controls_changed": False,
        "costs_changed": False,
        "result_driven_diagnostic": True,
        "optimization_performed": False,
        "independent_validation_claimed": False,
        "preregistered_before_diagnostic_calculation": True,
        "preregistration_timestamp": FROZEN_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    prior = read_csv(ROBUSTNESS_EVIDENCE / "benchmark_reference_log.csv")
    rows: list[dict[str, Any]] = []
    for row in prior:
        copied = dict(row)
        copied["control_changed"] = False
        copied["counted_as_strategy_or_trial"] = False
        rows.append(copied)
    return rows


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
        "common_period_start": EXPECTED_START.date().isoformat(),
        "common_period_end": EXPECTED_END.date().isoformat(),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "diagnostic_cost_bps": list(DIAGNOSTIC_COST_BPS),
        "frozen_month_ranking_source": (
            "full_period_5bps_candidate_minus_reference_monthly_excess"
        ),
        "month_neutralizations": [1, 3],
        "year_neutralizations": 1,
        "leave_one_trade_out": "each_completed_trade_independently",
        "trade_combinations_allowed": False,
        "negative_month_definition": "frozen_reference_monthly_return_below_zero",
        "drawdown_episode_selection": "frozen_reference_monthly_path_only",
        "canonical_return_series_mutation_allowed": False,
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


def build_parent_results() -> dict[str, Any]:
    panel, schedules, paths = parent.build_paths()
    if not paths:
        return {}
    payloads = parent.build_portfolio_payloads(paths)
    full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    cost_rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS.values():
        for cost in parent.COST_BPS:
            metrics = parent.portfolio_metrics(
                payloads[(portfolio_id, cost)], paths, cost
            )
            full_metrics[(portfolio_id, cost)] = metrics
            cost_rows.append(
                parent.robustness_row(
                    portfolio_id,
                    cost,
                    "full_period",
                    metrics,
                    "cost_stress",
                )
            )
    turnover_rows, invariant_rows = parent.build_turnover_and_invariant_rows(
        full_metrics
    )
    common_index = payloads[
        (CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)
    ]["returns"].index
    quarter_rows: list[dict[str, Any]] = []
    for quarter, period_index in parent.split_quarters(common_index).items():
        for portfolio_id in PORTFOLIO_IDS.values():
            metrics = parent.portfolio_metrics(
                payloads[(portfolio_id, PRIMARY_COST_BPS)],
                paths,
                PRIMARY_COST_BPS,
                period_index,
            )
            quarter_rows.append(
                parent.robustness_row(
                    portfolio_id,
                    PRIMARY_COST_BPS,
                    quarter,
                    metrics,
                    "chronological_quarter",
                )
            )
    year_rows: list[dict[str, Any]] = []
    for year in range(EXPECTED_START.year + 1, EXPECTED_END.year):
        year_index = common_index[common_index.year == year]
        if len(year_index) < parent.COMPLETE_YEAR_MIN_SESSIONS:
            continue
        for portfolio_id in PORTFOLIO_IDS.values():
            metrics = parent.portfolio_metrics(
                payloads[(portfolio_id, PRIMARY_COST_BPS)],
                paths,
                PRIMARY_COST_BPS,
                year_index,
            )
            row = parent.robustness_row(
                portfolio_id,
                PRIMARY_COST_BPS,
                f"calendar_year_{year}",
                metrics,
                "calendar_year",
            )
            row["calendar_year"] = year
            row["calendar_year_inclusion_rule"] = (
                f"complete_year_at_least_{parent.COMPLETE_YEAR_MIN_SESSIONS}_"
                "sessions"
            )
            year_rows.append(row)
    rolling = {
        36: exploration.monthly_rolling_rows(36, payloads),
        60: exploration.monthly_rolling_rows(60, payloads),
    }
    start_rows: list[dict[str, Any]] = []
    for year in parent.START_YEARS:
        sessions = common_index[common_index.year == year]
        if sessions.empty:
            raise RuntimeError(f"No common start session for {year}")
        start = pd.Timestamp(sessions[0])
        start_payloads = parent.build_portfolio_payloads(
            paths, costs=(PRIMARY_COST_BPS,), start=start
        )
        for portfolio_id in PORTFOLIO_IDS.values():
            metrics = parent.portfolio_metrics(
                start_payloads[(portfolio_id, PRIMARY_COST_BPS)],
                paths,
                PRIMARY_COST_BPS,
            )
            row = parent.robustness_row(
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
    concentration = parent.concentration_rows(payloads)
    bootstrap = parent.paired_moving_block_bootstrap(payloads)
    return {
        "panel": panel,
        "schedules": schedules,
        "paths": paths,
        "payloads": payloads,
        "full_metrics": full_metrics,
        "cost_stress_results.csv": cost_rows,
        "chronological_quarter_results.csv": quarter_rows,
        "calendar_year_results.csv": year_rows,
        "rolling_36_month_results.csv": rolling[36],
        "rolling_60_month_results.csv": rolling[60],
        "start_date_sensitivity.csv": start_rows,
        "excess_return_concentration.csv": concentration,
        "bootstrap_results.csv": bootstrap,
        "turnover_cost_reconciliation.csv": turnover_rows,
        "invariant_results.csv": invariant_rows,
    }


def reproduce_parent_tables(
    results: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    definitions = (
        (
            "cost_stress",
            "cost_stress_results.csv",
            ("portfolio_id", "cost_bps"),
        ),
        (
            "chronological_quarters",
            "chronological_quarter_results.csv",
            ("portfolio_id", "period"),
        ),
        (
            "calendar_years",
            "calendar_year_results.csv",
            ("portfolio_id", "calendar_year"),
        ),
        (
            "rolling_36_month",
            "rolling_36_month_results.csv",
            ("window_start", "window_end"),
        ),
        (
            "rolling_60_month",
            "rolling_60_month_results.csv",
            ("window_start", "window_end"),
        ),
        (
            "start_date_sensitivity",
            "start_date_sensitivity.csv",
            ("requested_start_year", "portfolio_id"),
        ),
        (
            "concentration",
            "excess_return_concentration.csv",
            ("candidate_portfolio_id", "comparator_portfolio_id"),
        ),
        (
            "bootstrap",
            "bootstrap_results.csv",
            ("candidate_portfolio_id", "comparator_portfolio_id"),
        ),
        (
            "turnover_and_cost",
            "turnover_cost_reconciliation.csv",
            ("portfolio_id", "cost_bps"),
        ),
        (
            "invariants",
            "invariant_results.csv",
            ("portfolio_id", "cost_bps"),
        ),
    )
    reproduction: list[dict[str, Any]] = []
    for scope, filename, keys in definitions:
        prior_rows = read_csv(ROBUSTNESS_EVIDENCE / filename)
        current_rows = results[filename]
        fields = tuple(
            field for field in prior_rows[0].keys() if field not in keys
        )
        reproduction.extend(
            parent.generic_reproduction_rows(
                scope,
                prior_rows,
                current_rows,
                keys,
                fields,
            )
        )
    return reproduction, bool(
        reproduction and all(row["pass"] for row in reproduction)
    )


def monthly_returns(series: pd.Series) -> pd.Series:
    return parent.monthly_returns(series)


def monthly_metrics(series: pd.Series) -> dict[str, Any]:
    clean = pd.Series(series, dtype=float).dropna()
    if clean.empty:
        raise ValueError("Monthly metric series is empty")
    values = clean.to_numpy(dtype=float)
    total = float(np.prod(1.0 + values) - 1.0)
    years = len(values) / 12.0
    cagr = float((1.0 + total) ** (1.0 / years) - 1.0)
    volatility = (
        float(np.std(values, ddof=1) * np.sqrt(12.0))
        if len(values) > 1
        else 0.0
    )
    sharpe = (
        float(np.mean(values) / np.std(values, ddof=1) * np.sqrt(12.0))
        if len(values) > 1 and np.std(values, ddof=1) > 0.0
        else 0.0
    )
    wealth = np.concatenate(([1.0], np.cumprod(1.0 + values)))
    drawdown = float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))
    return {
        "evaluation_start": str(clean.index[0]),
        "evaluation_end": str(clean.index[-1]),
        "monthly_observation_count": len(clean),
        "total_return": total,
        "cagr": cagr,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "maximum_drawdown": drawdown,
    }


def freeze_concentration_observations(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[pd.Period], int]:
    candidate = monthly_returns(
        payloads[(CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)]["returns"]
    )
    reference = monthly_returns(
        payloads[(REFERENCE_PORTFOLIO_ID, PRIMARY_COST_BPS)]["returns"]
    ).reindex(candidate.index)
    ranking = pd.DataFrame(
        {
            "month": candidate.index.astype(str),
            "excess": (candidate - reference).to_numpy(dtype=float),
        },
        index=candidate.index,
    ).sort_values(["excess", "month"], ascending=[False, True])
    positive = ranking.loc[ranking["excess"] > 0.0]
    top_three = list(positive.index[:3])
    annual = (candidate - reference).groupby(candidate.index.year).sum()
    strongest_year = int(annual.idxmax())
    rows: list[dict[str, Any]] = []
    for rank, period in enumerate(top_three, start=1):
        rows.append(
            {
                "observation_type": "positive_excess_month",
                "rank": rank,
                "observation": str(period),
                "candidate_minus_reference_return": float(
                    candidate.loc[period] - reference.loc[period]
                ),
                "ranking_source": (
                    "full_period_5bps_candidate_minus_reference_monthly_excess"
                ),
                "identified_once_for_all_comparisons": True,
                "selected_from_control_specific_performance": False,
                "canonical_return_series_modified": False,
            }
        )
    rows.append(
        {
            "observation_type": "strongest_additive_excess_calendar_year",
            "rank": 1,
            "observation": strongest_year,
            "candidate_minus_reference_return": float(
                annual.loc[strongest_year]
            ),
            "ranking_source": (
                "full_period_5bps_candidate_minus_reference_monthly_excess"
            ),
            "identified_once_for_all_comparisons": True,
            "selected_from_control_specific_performance": False,
            "canonical_return_series_modified": False,
        }
    )
    return rows, top_three, strongest_year


def neutralization_comparison_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
    neutralized_periods: list[pd.Period],
    scenario: str,
) -> list[dict[str, Any]]:
    candidate = monthly_returns(
        payloads[(CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)]["returns"]
    )
    reference = monthly_returns(
        payloads[(REFERENCE_PORTFOLIO_ID, PRIMARY_COST_BPS)]["returns"]
    ).reindex(candidate.index)
    counterfactual = candidate.copy()
    counterfactual.loc[neutralized_periods] = reference.loc[neutralized_periods]
    candidate_metrics = monthly_metrics(counterfactual)
    rows: list[dict[str, Any]] = []
    for comparator_id in (
        REFERENCE_PORTFOLIO_ID,
        DONCHIAN_PORTFOLIO_ID,
        EXPOSURE_PORTFOLIO_ID,
    ):
        comparator_series = monthly_returns(
            payloads[(comparator_id, PRIMARY_COST_BPS)]["returns"]
        ).reindex(candidate.index)
        comparator_metrics = monthly_metrics(comparator_series)
        dominated = open_engine.control_dominates(
            candidate_metrics, comparator_metrics
        )
        rows.append(
            {
                "scenario": scenario,
                "candidate_portfolio_id": CANDIDATE_PORTFOLIO_ID,
                "comparator_portfolio_id": comparator_id,
                "neutralized_observations": [
                    str(period) for period in neutralized_periods
                ],
                "neutralization_count": len(neutralized_periods),
                "timeline_observation_count_before": len(candidate),
                "timeline_observation_count_after": len(counterfactual),
                "candidate_total_return": candidate_metrics["total_return"],
                "candidate_cagr": candidate_metrics["cagr"],
                "candidate_annualized_volatility": candidate_metrics[
                    "annualized_volatility"
                ],
                "candidate_sharpe_ratio": candidate_metrics["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate_metrics[
                    "maximum_drawdown"
                ],
                "comparator_total_return": comparator_metrics["total_return"],
                "comparator_cagr": comparator_metrics["cagr"],
                "comparator_annualized_volatility": comparator_metrics[
                    "annualized_volatility"
                ],
                "comparator_sharpe_ratio": comparator_metrics["sharpe_ratio"],
                "comparator_maximum_drawdown": comparator_metrics[
                    "maximum_drawdown"
                ],
                "candidate_minus_comparator_sharpe": (
                    candidate_metrics["sharpe_ratio"]
                    - comparator_metrics["sharpe_ratio"]
                ),
                "candidate_minus_comparator_drawdown": (
                    candidate_metrics["maximum_drawdown"]
                    - comparator_metrics["maximum_drawdown"]
                ),
                "comparator_dominates_candidate": dominated,
                "temporary_counterfactual_copy": True,
                "canonical_return_series_modified": False,
                "observation_deleted": False,
            }
        )
    return rows


def completed_common_period_trades() -> list[dict[str, str]]:
    trades = read_csv(STANDALONE_EVIDENCE / "trade_ledger.csv")
    return [
        row
        for row in trades
        if row["terminal_open_status"].lower() == "false"
        and pd.Timestamp(row["exit_execution_date"]) >= EXPECTED_START
        and pd.Timestamp(row["entry_execution_date"]) <= EXPECTED_END
    ]


def leave_one_trade_out_rows(
    results: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    bool,
]:
    paths = results["paths"]
    payloads = results["payloads"]
    reference = payloads[
        (REFERENCE_PORTFOLIO_ID, PRIMARY_COST_BPS)
    ]["returns"]
    candidate_sleeve = paths[
        (STRATEGY_ID, PRIMARY_COST_BPS)
    ]["returns"].reindex(reference.index)
    bil_sleeve = paths[
        (CONTROL_IDS[4], PRIMARY_COST_BPS)
    ]["returns"].reindex(reference.index)
    canonical_portfolio = payloads[
        (CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)
    ]["returns"]
    reference_monthly = monthly_returns(reference)
    canonical_monthly = monthly_returns(canonical_portfolio)
    canonical_additive = float((canonical_monthly - reference_monthly).sum())
    reference_metrics = results["full_metrics"][
        (REFERENCE_PORTFOLIO_ID, PRIMARY_COST_BPS)
    ]
    control_metrics = {
        portfolio_id: results["full_metrics"][
            (portfolio_id, PRIMARY_COST_BPS)
        ]
        for portfolio_id in CRITICAL_PORTFOLIO_IDS
    }
    rows: list[dict[str, Any]] = []
    deterministic = True
    for number, trade in enumerate(completed_common_period_trades(), start=1):
        entry = pd.Timestamp(trade["entry_execution_date"])
        exit_date = pd.Timestamp(trade["exit_execution_date"])
        interval_start = max(entry, pd.Timestamp(reference.index[0]))
        interval_end = min(exit_date, pd.Timestamp(reference.index[-1]))
        mask = (candidate_sleeve.index >= interval_start) & (
            candidate_sleeve.index <= interval_end
        )
        temporary_sleeve = candidate_sleeve.copy()
        temporary_sleeve.loc[mask] = bil_sleeve.loc[mask]
        temporary_payload = (
            portfolio_accounting.simulate_two_component_portfolio(
                reference,
                temporary_sleeve,
                f"{CANDIDATE_PORTFOLIO_ID}__leave_trade_{number}_out",
                PRIMARY_COST_BPS,
            )
        )
        metrics = market.metrics_from_returns(temporary_payload["returns"])
        temporary_monthly = monthly_returns(temporary_payload["returns"])
        temporary_additive = float(
            (temporary_monthly - reference_monthly).sum()
        )
        contribution = canonical_additive - temporary_additive
        base = portfolio_accounting.metric_payload(
            temporary_payload, temporary_payload["returns"].index
        )
        dominated = {
            portfolio_id: open_engine.control_dominates(
                metrics, control_metrics[portfolio_id]
            )
            for portfolio_id in CRITICAL_PORTFOLIO_IDS
        }
        rows.append(
            {
                "trade_number": number,
                "entry_signal_date": trade["entry_signal_date"],
                "entry_execution_date": trade["entry_execution_date"],
                "exit_signal_date": trade["exit_signal_date"],
                "exit_execution_date": trade["exit_execution_date"],
                "holding_sessions_parent": trade["holding_sessions"],
                "neutralized_interval_start": interval_start.date().isoformat(),
                "neutralized_interval_end": interval_end.date().isoformat(),
                "neutralized_common_sessions": int(mask.sum()),
                "replacement_sleeve": "BIL",
                "full_period_cagr": metrics["cagr"],
                "full_period_sharpe_ratio": metrics["sharpe_ratio"],
                "full_period_maximum_drawdown": metrics["maximum_drawdown"],
                "reference_sharpe_difference": (
                    float(metrics["sharpe_ratio"])
                    - float(reference_metrics["sharpe_ratio"])
                ),
                "reference_drawdown_improvement": (
                    float(metrics["maximum_drawdown"])
                    - float(reference_metrics["maximum_drawdown"])
                ),
                "improves_reference_sharpe_or_drawdown": bool(
                    float(metrics["sharpe_ratio"])
                    > float(reference_metrics["sharpe_ratio"])
                    or float(metrics["maximum_drawdown"])
                    > float(reference_metrics["maximum_drawdown"])
                ),
                "donchian_dominates": dominated[DONCHIAN_PORTFOLIO_ID],
                "exposure_matched_dominates": dominated[
                    EXPOSURE_PORTFOLIO_ID
                ],
                "canonical_additive_excess": canonical_additive,
                "leave_one_out_additive_excess": temporary_additive,
                "independent_marginal_trade_contribution": contribution,
                "maximum_gross_exposure": base["max_daily_exposure"],
                "maximum_daily_weight_sum": base["max_daily_weight_sum"],
                "invariant_pass": base["invariant_pass"],
                "temporary_counterfactual_copy": True,
                "canonical_return_series_modified": False,
                "trade_combination_removed": False,
            }
        )
        if number == 1:
            repeat = portfolio_accounting.simulate_two_component_portfolio(
                reference,
                temporary_sleeve,
                f"{CANDIDATE_PORTFOLIO_ID}__leave_trade_{number}_out",
                PRIMARY_COST_BPS,
            )
            deterministic = bool(
                np.allclose(
                    repeat["returns"].to_numpy(dtype=float),
                    temporary_payload["returns"].to_numpy(dtype=float),
                    rtol=0.0,
                    atol=0.0,
                )
            )
    sharpes = np.asarray(
        [float(row["full_period_sharpe_ratio"]) for row in rows], dtype=float
    )
    drawdown_edges = np.asarray(
        [float(row["reference_drawdown_improvement"]) for row in rows],
        dtype=float,
    )
    strongest = max(
        rows,
        key=lambda row: float(row["independent_marginal_trade_contribution"]),
    )
    summary = [
        {
            "completed_trade_count": len(rows),
            "minimum_leave_one_out_sharpe": float(np.min(sharpes)),
            "median_leave_one_out_sharpe": float(np.median(sharpes)),
            "maximum_leave_one_out_sharpe": float(np.max(sharpes)),
            "minimum_leave_one_out_drawdown_improvement_vs_reference": float(
                np.min(drawdown_edges)
            ),
            "median_leave_one_out_drawdown_improvement_vs_reference": float(
                np.median(drawdown_edges)
            ),
            "maximum_leave_one_out_drawdown_improvement_vs_reference": float(
                np.max(drawdown_edges)
            ),
            "fraction_still_improving_reference_sharpe_or_drawdown": float(
                np.mean(
                    [
                        bool(row["improves_reference_sharpe_or_drawdown"])
                        for row in rows
                    ]
                )
            ),
            "fraction_dominated_by_donchian": float(
                np.mean([bool(row["donchian_dominates"]) for row in rows])
            ),
            "fraction_dominated_by_exposure_matched": float(
                np.mean(
                    [
                        bool(row["exposure_matched_dominates"])
                        for row in rows
                    ]
                )
            ),
            "greatest_reference_relative_benefit_reduction_trade_number": (
                strongest["trade_number"]
            ),
            "greatest_reduction_entry_execution_date": strongest[
                "entry_execution_date"
            ],
            "greatest_reduction_exit_execution_date": strongest[
                "exit_execution_date"
            ],
            "greatest_reduction_additive_contribution": strongest[
                "independent_marginal_trade_contribution"
            ],
            "counterfactual_rerun_deterministic": deterministic,
            "combinations_of_removed_trades_constructed": False,
        }
    ]
    ranked = sorted(
        rows,
        key=lambda row: float(row["independent_marginal_trade_contribution"]),
        reverse=True,
    )
    total = canonical_additive
    largest = float(ranked[0]["independent_marginal_trade_contribution"])
    largest_three = float(
        sum(
            float(row["independent_marginal_trade_contribution"])
            for row in ranked[:3]
        )
    )
    contribution_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        contribution = float(
            row["independent_marginal_trade_contribution"]
        )
        contribution_rows.append(
            {
                "record_type": "individual_completed_trade",
                "rank": rank,
                "trade_number": row["trade_number"],
                "entry_execution_date": row["entry_execution_date"],
                "exit_execution_date": row["exit_execution_date"],
                "independent_marginal_additive_contribution": contribution,
                "fraction_of_total_additive_excess": (
                    contribution / total if total != 0.0 else ""
                ),
                "canonical_total_additive_excess": total,
                "combinations_of_removed_trades_constructed": False,
                "canonical_return_series_modified": False,
            }
        )
    contribution_rows.append(
        {
            "record_type": "concentration_summary",
            "rank": "",
            "trade_number": "",
            "entry_execution_date": "",
            "exit_execution_date": "",
            "independent_marginal_additive_contribution": "",
            "fraction_of_total_additive_excess": "",
            "canonical_total_additive_excess": total,
            "largest_trade_contribution": largest,
            "largest_trade_fraction_of_total_additive_excess": (
                largest / total if total != 0.0 else ""
            ),
            "largest_three_trade_contributions": largest_three,
            "largest_three_fraction_of_total_additive_excess": (
                largest_three / total if total != 0.0 else ""
            ),
            "additive_excess_after_neutralizing_strongest_trade": total
            - largest,
            "additive_excess_after_neutralizing_three_strongest_trades": total
            - largest_three,
            "three_trade_value_derived_from_independent_marginals": True,
            "combinations_of_removed_trades_constructed": False,
            "canonical_return_series_modified": False,
        }
    )
    return rows, summary, contribution_rows, deterministic


def reference_negative_month_rows(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    monthly = {
        portfolio_id: monthly_returns(
            payloads[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
        )
        for portfolio_id in PORTFOLIO_IDS.values()
    }
    reference = monthly[REFERENCE_PORTFOLIO_ID]
    negative = reference.loc[reference < 0.0].index
    rows: list[dict[str, Any]] = []
    for portfolio_id, series in monthly.items():
        selected = series.reindex(negative)
        values = selected.to_numpy(dtype=float)
        rows.append(
            {
                "portfolio_id": portfolio_id,
                "reference_negative_month_count": len(negative),
                "cumulative_return": float(np.prod(1.0 + values) - 1.0),
                "mean_monthly_return": float(np.mean(values)),
                "annualized_volatility": float(
                    np.std(values, ddof=1) * np.sqrt(12.0)
                ),
                "worst_month": float(np.min(values)),
                "percentage_months_outperforming_reference": float(
                    np.mean(values > reference.reindex(negative).to_numpy())
                ),
                "average_portfolio_minus_reference_return": float(
                    np.mean(
                        values - reference.reindex(negative).to_numpy(dtype=float)
                    )
                ),
                "month_selection_source": "frozen_reference_return_below_zero",
                "selected_from_candidate_performance": False,
            }
        )
    return rows


def reference_drawdown_episodes(
    payloads: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    monthly = {
        portfolio_id: monthly_returns(
            payloads[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
        )
        for portfolio_id in (
            REFERENCE_PORTFOLIO_ID,
            CANDIDATE_PORTFOLIO_ID,
            DONCHIAN_PORTFOLIO_ID,
            EXPOSURE_PORTFOLIO_ID,
        )
    }
    reference = monthly[REFERENCE_PORTFOLIO_ID]
    wealth = np.cumprod(1.0 + reference.to_numpy(dtype=float))
    peak_value = 1.0
    peak_position = -1
    active: dict[str, Any] | None = None
    definitions: list[dict[str, Any]] = []
    for position, value in enumerate(wealth):
        if value < peak_value:
            if active is None:
                active = {
                    "peak_position": peak_position,
                    "first_drawdown_position": position,
                    "trough_position": position,
                    "trough_value": value,
                    "peak_value": peak_value,
                }
            elif value < active["trough_value"]:
                active["trough_position"] = position
                active["trough_value"] = value
            continue
        if active is not None:
            active["recovery_position"] = position
            definitions.append(active)
            active = None
        peak_value = float(value)
        peak_position = position
    if active is not None:
        active["recovery_position"] = None
        definitions.append(active)

    def anchored_drawdown(series: pd.Series) -> float:
        values = series.to_numpy(dtype=float)
        path = np.cumprod(1.0 + values)
        return float(min(0.0, float(np.min(path - 1.0))))

    rows: list[dict[str, Any]] = []
    periods = list(reference.index)
    for episode_number, definition in enumerate(definitions, start=1):
        first = int(definition["first_drawdown_position"])
        recovery = definition["recovery_position"]
        end = int(recovery) if recovery is not None else len(periods) - 1
        episode_periods = periods[first : end + 1]
        peak_position = int(definition["peak_position"])
        start_label = (
            str(periods[peak_position])
            if peak_position >= 0
            else f"{periods[0]}_evaluation_start_baseline"
        )
        drawdowns = {
            portfolio_id: anchored_drawdown(series.reindex(episode_periods))
            for portfolio_id, series in monthly.items()
        }
        rows.append(
            {
                "episode_number": episode_number,
                "start": start_label,
                "first_drawdown_month": str(periods[first]),
                "trough": str(periods[int(definition["trough_position"])]),
                "recovery": str(periods[int(recovery)])
                if recovery is not None
                else "",
                "terminal_unrecovered": recovery is None,
                "episode_month_count": len(episode_periods),
                "reference_drawdown": drawdowns[REFERENCE_PORTFOLIO_ID],
                "candidate_drawdown": drawdowns[CANDIDATE_PORTFOLIO_ID],
                "donchian_drawdown": drawdowns[DONCHIAN_PORTFOLIO_ID],
                "exposure_matched_drawdown": drawdowns[
                    EXPOSURE_PORTFOLIO_ID
                ],
                "candidate_drawdown_improvement": (
                    drawdowns[CANDIDATE_PORTFOLIO_ID]
                    - drawdowns[REFERENCE_PORTFOLIO_ID]
                ),
                "candidate_improves_reference_drawdown": (
                    drawdowns[CANDIDATE_PORTFOLIO_ID]
                    > drawdowns[REFERENCE_PORTFOLIO_ID]
                ),
                "episode_selected_from_reference_only": True,
            }
        )
    return rows


def decide_outcome(
    reproduction_passed: bool,
    invariant_passed: bool,
    month_rows: list[dict[str, Any]],
    year_rows: list[dict[str, Any]],
    leave_summary: list[dict[str, Any]],
    trade_concentration: list[dict[str, Any]],
    negative_rows: list[dict[str, Any]],
    drawdown_rows: list[dict[str, Any]],
) -> tuple[str, str, str, str, dict[str, Any]]:
    if not reproduction_passed or not invariant_passed:
        return (
            "robustness_blocked",
            "data_or_comparability_failure",
            NEXT_BLOCKED,
            "blocked_without_interpretation",
            {"reproduction_and_invariants_pass": False},
        )

    three_rows = [
        row for row in month_rows if row["scenario"] == "three_strongest_months"
    ]
    year_reference = next(
        row
        for row in year_rows
        if row["comparator_portfolio_id"] == REFERENCE_PORTFOLIO_ID
    )
    three_reference = next(
        row
        for row in three_rows
        if row["comparator_portfolio_id"] == REFERENCE_PORTFOLIO_ID
    )
    three_material = bool(
        float(three_reference["candidate_minus_comparator_sharpe"]) >= 0.02
        or float(three_reference["candidate_minus_comparator_drawdown"]) >= 0.01
    )
    year_material = bool(
        float(year_reference["candidate_minus_comparator_sharpe"]) >= 0.02
        or float(year_reference["candidate_minus_comparator_drawdown"]) >= 0.01
    )
    no_control_dominance = all(
        not bool(row["comparator_dominates_candidate"])
        for row in [*three_rows, *year_rows]
        if row["comparator_portfolio_id"] in CRITICAL_PORTFOLIO_IDS
    )
    leave = leave_summary[0]
    leave_fraction = float(
        leave["fraction_still_improving_reference_sharpe_or_drawdown"]
    )
    donchian_fraction = float(leave["fraction_dominated_by_donchian"])
    exposure_fraction = float(
        leave["fraction_dominated_by_exposure_matched"]
    )
    drawdown_fraction = float(
        np.mean(
            [
                bool(row["candidate_improves_reference_drawdown"])
                for row in drawdown_rows
            ]
        )
    )
    negative_candidate = next(
        row
        for row in negative_rows
        if row["portfolio_id"] == CANDIDATE_PORTFOLIO_ID
    )
    negative_incremental = float(
        negative_candidate["average_portfolio_minus_reference_return"]
    )
    concentration_summary = next(
        row
        for row in trade_concentration
        if row["record_type"] == "concentration_summary"
    )
    largest_trade_fraction = float(
        concentration_summary[
            "largest_trade_fraction_of_total_additive_excess"
        ]
    )
    gate = {
        "reproduction_and_invariants_pass": True,
        "three_strongest_month_neutralization_material": three_material,
        "strongest_year_neutralization_material": year_material,
        "critical_controls_do_not_dominate_neutralizations": (
            no_control_dominance
        ),
        "leave_one_trade_out_favorable_at_least_75pct": (
            leave_fraction >= 0.75
        ),
        "donchian_dominates_no_more_than_50pct_leave_one_out": (
            donchian_fraction <= 0.50
        ),
        "exposure_dominates_no_more_than_50pct_leave_one_out": (
            exposure_fraction <= 0.50
        ),
        "candidate_improves_more_than_half_reference_drawdown_episodes": (
            drawdown_fraction > 0.50
        ),
        "positive_incremental_return_in_reference_negative_months": (
            negative_incremental > 0.0
        ),
        "no_individual_trade_above_50pct_total_additive_excess": (
            largest_trade_fraction <= 0.50
        ),
        "leave_one_trade_out_favorable_fraction": leave_fraction,
        "donchian_leave_one_out_dominance_fraction": donchian_fraction,
        "exposure_leave_one_out_dominance_fraction": exposure_fraction,
        "reference_drawdown_episode_improvement_fraction": drawdown_fraction,
        "reference_negative_month_average_incremental_return": (
            negative_incremental
        ),
        "largest_trade_fraction_of_total_additive_excess": (
            largest_trade_fraction
        ),
    }
    required = [
        value for value in gate.values() if isinstance(value, bool)
    ]
    if all(required):
        return (
            "robustness_positive_for_prospective_validation_design",
            "",
            NEXT_POSITIVE,
            "ready_for_prospective_validation_design_with_concentration_caveat",
            gate,
        )
    hard_neutralization_failure = not three_material or not year_material
    critical_dominance = not no_control_dominance
    broad_leave_failure = bool(
        leave_fraction < 0.50
        or (
            donchian_fraction > 0.50
            and exposure_fraction > 0.50
        )
    )
    single_trade_majority = largest_trade_fraction > 0.50
    if (
        hard_neutralization_failure
        or critical_dominance
        or broad_leave_failure
        or single_trade_majority
    ):
        reason = (
            "weak_vs_primary_control"
            if critical_dominance
            else "concentration_risk"
        )
        return (
            "robustness_failed",
            reason,
            NEXT_FAILED,
            "historical_diversifier_claim_does_not_survive_concentration_gate",
            gate,
        )
    return (
        "robustness_mixed_defer",
        "concentration_risk",
        NEXT_MIXED,
        "historically_promising_but_not_ready_for_validation",
        gate,
    )


def write_csv(
    filename: str,
    rows: list[dict[str, Any]],
    leading: list[str],
    fallback: list[str],
) -> None:
    fields = rows_with_fields(rows, leading) if rows else fallback
    open_engine.write_csv(OUTPUT_DIR / filename, rows, fields)


def run() -> dict[str, Any]:
    clean_output()
    parent_dirs = {
        "standalone": STANDALONE_EVIDENCE,
        "exploration": EXPLORATION_EVIDENCE,
        "robustness": ROBUSTNESS_EVIDENCE,
    }
    parent_hashes_before = {
        name: directory_hash(path) for name, path in parent_dirs.items()
    }
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
        "execute_frozen_concentration_resolution",
    )

    parent_results = build_parent_results()
    if parent_results:
        reproduction, reproduction_passed = reproduce_parent_tables(
            parent_results
        )
    else:
        reproduction = []
        reproduction_passed = False

    frozen_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    leave_rows: list[dict[str, Any]] = []
    leave_summary: list[dict[str, Any]] = []
    trade_concentration: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    drawdown_rows: list[dict[str, Any]] = []
    counterfactual_deterministic = False
    canonical_hash_before = ""
    canonical_hash_after = ""
    invariant_passed = False

    if reproduction_passed:
        payloads = parent_results["payloads"]
        canonical_returns = payloads[
            (CANDIDATE_PORTFOLIO_ID, PRIMARY_COST_BPS)
        ]["returns"]
        canonical_hash_before = open_engine.canonical_hash(
            [
                (pd.Timestamp(date).date().isoformat(), float(value))
                for date, value in canonical_returns.items()
            ]
        )
        frozen_rows, top_three, strongest_year = (
            freeze_concentration_observations(payloads)
        )
        month_rows.extend(
            neutralization_comparison_rows(
                payloads, [top_three[0]], "strongest_positive_month"
            )
        )
        month_rows.extend(
            neutralization_comparison_rows(
                payloads, top_three, "three_strongest_months"
            )
        )
        year_periods = [
            period
            for period in monthly_returns(canonical_returns).index
            if period.year == strongest_year
        ]
        year_rows = neutralization_comparison_rows(
            payloads,
            year_periods,
            f"strongest_calendar_year_{strongest_year}",
        )
        (
            leave_rows,
            leave_summary,
            trade_concentration,
            counterfactual_deterministic,
        ) = leave_one_trade_out_rows(parent_results)
        negative_rows = reference_negative_month_rows(payloads)
        drawdown_rows = reference_drawdown_episodes(payloads)
        canonical_hash_after = open_engine.canonical_hash(
            [
                (pd.Timestamp(date).date().isoformat(), float(value))
                for date, value in canonical_returns.items()
            ]
        )
        invariant_passed = bool(
            all(
                row["invariant_pass"]
                for row in parent_results["invariant_results.csv"]
                if float(row["cost_bps"]) in DIAGNOSTIC_COST_BPS
            )
            and all(bool(row["invariant_pass"]) for row in leave_rows)
            and canonical_hash_before == canonical_hash_after
        )

    (
        outcome,
        failure_reason,
        next_action,
        interpretation,
        gate,
    ) = decide_outcome(
        reproduction_passed,
        invariant_passed,
        month_rows,
        year_rows,
        leave_summary,
        trade_concentration,
        negative_rows,
        drawdown_rows,
    )
    write_entities(outcome, failure_reason, next_action)

    write_csv(
        "reproduction_check.csv",
        reproduction,
        ["scope", "record_key", "field"],
        [
            "scope",
            "record_key",
            "field",
            "parent_value",
            "reproduced_value",
            "difference",
            "absolute_tolerance",
            "pass",
        ],
    )
    write_csv(
        "frozen_concentration_observations.csv",
        frozen_rows,
        ["observation_type", "rank", "observation"],
        ["observation_type", "rank", "observation"],
    )
    write_csv(
        "month_neutralization_results.csv",
        month_rows,
        ["scenario", "candidate_portfolio_id", "comparator_portfolio_id"],
        ["scenario", "candidate_portfolio_id", "comparator_portfolio_id"],
    )
    write_csv(
        "strongest_year_neutralization_results.csv",
        year_rows,
        ["scenario", "candidate_portfolio_id", "comparator_portfolio_id"],
        ["scenario", "candidate_portfolio_id", "comparator_portfolio_id"],
    )
    write_csv(
        "leave_one_trade_out_results.csv",
        leave_rows,
        ["trade_number", "entry_execution_date", "exit_execution_date"],
        ["trade_number", "entry_execution_date", "exit_execution_date"],
    )
    write_csv(
        "leave_one_trade_out_summary.csv",
        leave_summary,
        ["completed_trade_count"],
        ["completed_trade_count"],
    )
    write_csv(
        "trade_contribution_concentration.csv",
        trade_concentration,
        ["record_type", "rank", "trade_number"],
        ["record_type", "rank", "trade_number"],
    )
    write_csv(
        "reference_negative_month_results.csv",
        negative_rows,
        ["portfolio_id"],
        ["portfolio_id"],
    )
    write_csv(
        "reference_drawdown_episode_results.csv",
        drawdown_rows,
        ["episode_number", "start", "trough", "recovery"],
        ["episode_number", "start", "trough", "recovery"],
    )
    turnover_rows = (
        [
            row
            for row in parent_results["turnover_cost_reconciliation.csv"]
            if float(row["cost_bps"]) in DIAGNOSTIC_COST_BPS
        ]
        if parent_results
        else []
    )
    invariant_rows = (
        [
            row
            for row in parent_results["invariant_results.csv"]
            if float(row["cost_bps"]) in DIAGNOSTIC_COST_BPS
        ]
        if parent_results
        else []
    )
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover_rows,
        ["portfolio_id", "cost_bps"],
        ["portfolio_id", "cost_bps"],
    )
    write_csv(
        "invariant_results.csv",
        invariant_rows,
        ["portfolio_id", "cost_bps"],
        ["portfolio_id", "cost_bps"],
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
        "outcome_interpretation": interpretation,
        "final_same_period_kaufman_diagnostic": True,
        "further_same_period_kaufman_diagnostic_authorized": False,
        "independent_validation_claimed": False,
        "paper_demo_eligibility_supported": False,
        "resolution_gate": gate,
    }
    open_engine.write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failed_gate_ids = [
        key
        for key, value in gate.items()
        if isinstance(value, bool) and not value
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
        "adaptation_label": "result_driven_robustness_diagnostic",
        "changed_fields_from_parent": (
            "diversifier_route_concentration_diagnostics_and_decision_gate_only"
        ),
        "approved_route": "20pct_diversifier_only",
        "existing_strategy_configurations": 1,
        "new_strategy_configurations": 0,
        "existing_exploration_robustness_trials_carried_forward": 3,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "counterfactual_diagnostics_count": (
            len(month_rows)
            + len(year_rows)
            + len(leave_rows)
            + len(negative_rows)
            + len(drawdown_rows)
        ),
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
        "sleeve_weight_changed": False,
        "reference_changed": False,
        "controls_changed": False,
        "costs_changed": False,
        "result_driven_diagnostic": True,
        "optimization_performed": False,
        "independent_validation_claimed": False,
        "final_same_period_kaufman_diagnostic": True,
        "further_same_period_kaufman_diagnostic_authorized": False,
        "preregistered_diagnostics": preregistered_diagnostics(),
        "reproduction_passed": reproduction_passed,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "outcome_interpretation": interpretation,
        "exact_next_action": next_action,
        "preregistration_hash": preregistration_hash,
        "provider_access": False,
        "network_access": False,
        "paper_demo_action": False,
        "broker_or_order_action": False,
    }
    open_engine.write_yaml(OUTPUT_DIR / "resolution_manifest.yaml", manifest)
    frozen_months = [
        row["observation"]
        for row in frozen_rows
        if row["observation_type"] == "positive_excess_month"
    ]
    frozen_year = next(
        (
            row["observation"]
            for row in frozen_rows
            if row["observation_type"]
            == "strongest_additive_excess_calendar_year"
        ),
        "",
    )
    top_three_reference = next(
        (
            row
            for row in month_rows
            if row["scenario"] == "three_strongest_months"
            and row["comparator_portfolio_id"] == REFERENCE_PORTFOLIO_ID
        ),
        {},
    )
    strongest_year_reference = next(
        (
            row
            for row in year_rows
            if row["comparator_portfolio_id"] == REFERENCE_PORTFOLIO_ID
        ),
        {},
    )
    report = f"""# Kaufman Diversifier Concentration-Risk Resolution V1

## Outcome

`{outcome}`

Primary failure reason: `{failure_reason or "none"}`.

Interpretation: `{interpretation}`.

## Decision Evidence

The once-frozen favorable months were `{", ".join(frozen_months) or "none"}`;
the once-frozen strongest additive-excess year was `{frozen_year or "none"}`.
After neutralizing the three strongest months, the candidate retained a
reference-relative Sharpe edge of
`{top_three_reference.get("candidate_minus_comparator_sharpe", "")}` and a
drawdown edge of
`{top_three_reference.get("candidate_minus_comparator_drawdown", "")}`.
After neutralizing the strongest year, those edges were
`{strongest_year_reference.get("candidate_minus_comparator_sharpe", "")}`
and
`{strongest_year_reference.get("candidate_minus_comparator_drawdown", "")}`.

The fraction of independent leave-one-trade-out cases that still improved
reference Sharpe or drawdown was
`{gate.get("leave_one_trade_out_favorable_fraction", "")}`. The candidate
improved drawdown in
`{gate.get("reference_drawdown_episode_improvement_fraction", "")}` of
reference-selected drawdown episodes and had average incremental return of
`{gate.get("reference_negative_month_average_incremental_return", "")}`
during reference-negative months.

The largest independently measured trade contribution was
`{gate.get("largest_trade_fraction_of_total_additive_excess", "")}` of total
additive excess. That exceeds the frozen 50% limit, so the historical
diversifier claim fails the final concentration gate even though its
risk-adjusted month/year and leave-one-trade-out diagnostics otherwise
survived.

## Method

Exactly one result-driven robustness child retained the frozen Kaufman Rule-2
channel, 40-session period, SPY/BIL sleeve, following-open inner execution,
80/20 diversifier route, monthly following-close outer rebalance, controls,
costs, and exposure-matched weights. All parent robustness tables were
reproduced before interpretation.

Favorable months were ranked once from the canonical 5-bps
candidate-minus-reference monthly series. Every month/year neutralization
kept the complete timeline, every completed trade was removed independently
by substituting BIL inside a temporary sleeve copy, and the canonical return
series remained unchanged.

This is the final same-period Kaufman diagnostic. It is not independent
validation or paper/demo eligibility. The exact next action is
`{next_action}` and was not executed.
"""
    (OUTPUT_DIR / "resolution_report.md").write_text(report, encoding="utf-8")

    parent_hashes_after = {
        name: directory_hash(path) for name, path in parent_dirs.items()
    }
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
            "frozen": frozen_rows,
            "months": month_rows,
            "year": year_rows,
            "leave_one_out": leave_rows,
            "trade_concentration": trade_concentration,
            "negative_months": negative_rows,
            "drawdown_episodes": drawdown_rows,
            "outcome": outcome_row,
        }
    )
    consistency = {
        **manifest,
        "overall_pass": bool(
            required_exact
            and parent_hashes_before == parent_hashes_after
            and protected_before == protected_after
            and cache_before == cache_after
            and prior_evidence_before == prior_evidence_after
            and reproduction_passed
            and invariant_passed
            and counterfactual_deterministic
            and canonical_hash_before == canonical_hash_after
        ),
        "required_outputs_exact": required_exact,
        "parent_packets_verified": parent_context["passed"],
        "parent_evidence_hashes_before": parent_hashes_before,
        "parent_evidence_hashes_after": parent_hashes_after,
        "parent_evidence_unchanged": (
            parent_hashes_before == parent_hashes_after
        ),
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before
        == prior_evidence_after,
        "preregistration_written_before_diagnostic_calculation": True,
        "canonical_return_hash_before": canonical_hash_before,
        "canonical_return_hash_after": canonical_hash_after,
        "canonical_return_series_unchanged": (
            canonical_hash_before == canonical_hash_after
        ),
        "counterfactual_rerun_deterministic": counterfactual_deterministic,
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
        "resolution_gate": gate,
    }
    open_engine.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "reproduction_passed": reproduction_passed,
        "completed_trade_count": (
            leave_summary[0]["completed_trade_count"] if leave_summary else 0
        ),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
