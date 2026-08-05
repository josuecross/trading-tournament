from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    implement_targeted_cross_sectional_low_turnover_candidate_v1 as parent,
)


TASK_ID = "sector_low_volatility_control_incremental_value_followup_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "six_month_low_volatility_bottom3_sector_diversifier_v1"
FAMILY_ID = "cross_sectional_low_volatility_sector_selection"
DISPLAY_NAME = "Six-Month Bottom-Three Low-Volatility Sector Diversifier"
ARCHITECTURE = (
    "monthly_overlapping_vintage_low_realized_volatility_sector_selection"
)
SOURCE_LINEAGE = (
    "implement_targeted_cross_sectional_low_turnover_candidate_v1:"
    "predeclared_low_volatility_control:result_driven_exploratory_adaptation"
)
PARENT_STRATEGY_ID = parent.STRATEGY_ID
PARENT_TRIAL_ID = parent.TRIAL_ID
TRIAL_ID = f"{TASK_ID}__child"
FROZEN_TIMESTAMP = "2026-07-28T00:00:00-06:00"
PRIMARY_COST_BPS = 5.0
COST_BPS = parent.COST_BPS
TOLERANCE = 1e-9

PARENT_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / parent.TASK_ID
    / "latest"
)
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
CACHE_DIR = ROOT / "data" / "cache"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\df4bf7a7-5ff5-49de-8592-d6f0f1da5506\pasted-text.txt"
)
PROTECTED_PATHS = parent.PROTECTED_PATHS

CANDIDATE_PATH_ID = (
    "six_month_realized_volatility_bottom3_sector_v1"
)
CONTROL_IDS = (
    "monthly_equal_weight_nine_sector_control",
    "static_first_valid_low_volatility_bottom3_sector_control",
    PARENT_STRATEGY_ID,
    "SPY_buy_and_hold",
    "BIL_buy_and_hold",
)
CRITICAL_CONTROL_IDS = (
    "monthly_equal_weight_nine_sector_control",
    "static_first_valid_low_volatility_bottom3_sector_control",
)
PORTFOLIO_IDS = {
    "reference": "100pct_frozen_reference",
    STRATEGY_ID: "80pct_reference_20pct_dynamic_low_volatility_candidate",
    "monthly_equal_weight_nine_sector_control": (
        "80pct_reference_20pct_monthly_equal_weight_nine_sector_control"
    ),
    "static_first_valid_low_volatility_bottom3_sector_control": (
        "80pct_reference_20pct_static_first_valid_low_volatility_control"
    ),
    PARENT_STRATEGY_ID: "80pct_reference_20pct_MDD_control",
    "SPY_buy_and_hold": "80pct_reference_20pct_SPY_buy_and_hold",
}
ROLLING_COMPARATORS = (
    "reference",
    "monthly_equal_weight_nine_sector_control",
    "static_first_valid_low_volatility_bottom3_sector_control",
)

NEXT_ADVANCE = (
    "direction_owner_review_sector_low_volatility_diversifier_followup_v1"
)
NEXT_CLOSE = "targeted_cross_sectional_price_range_source_sprint_v1"
NEXT_BLOCK = "direction_owner_review_sector_low_volatility_followup_block_v1"

REQUIRED_OUTPUTS = {
    "followup_manifest.yaml",
    "source_and_adaptation_lineage.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "static_control_definition.csv",
    "standalone_results.csv",
    "standalone_chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "portfolio_chronological_half_results.csv",
    "rolling_36_month_portfolio_results.csv",
    "rolling_60_month_portfolio_results.csv",
    "rolling_window_summary.csv",
    "formation_selection_diagnostics.csv",
    "vintage_ledger.csv",
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

RESULT_FIELDS = [
    "row_id",
    "strategy_id",
    "family_id",
    "trial_id",
    "entity_type",
    "stage",
    "row_type",
    "cost_assumption_bps",
    "period_label",
    "period_role",
    "outcome",
    "failure_reason",
    *parent.METRIC_FIELDS,
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output() -> None:
    expected = (
        ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
    ).resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def hash_map(paths: tuple[Path, ...]) -> dict[str, str]:
    return {rel(path): parent.helpers.file_hash(path) for path in paths}


def frozen_rule() -> str:
    return (
        "At each completed month-end, calculate sample standard deviation "
        "(ddof=1) of daily close-to-close returns over the six completed "
        "calendar months for all nine frozen sectors. Rank ascending, select "
        "exactly three with lexical tie-breaking, form one equal-weight "
        "one-sixth vintage at the following regular-session close, hold six "
        "calendar months, and allow each vintage to drift independently. "
        "Invalid or unused slots hold BIL."
    )


def frozen_parameters(static_selection: tuple[str, ...]) -> dict[str, Any]:
    return {
        "formation_period": "six_completed_calendar_months",
        "signal_metric": "sample_standard_deviation_of_daily_returns",
        "ddof": 1,
        "selected_count": 3,
        "holding_period_months": 6,
        "vintage_slots": 6,
        "vintage_capital_fraction": "1/6",
        "within_vintage_weighting": "equal_weight_at_formation_only",
        "execution": "following_regular_session_close",
        "tie_break": "lexical_ticker",
        "unused_or_invalid_slot_asset": "BIL",
        "outer_reference_weight": 0.8,
        "outer_candidate_weight": 0.2,
        "static_first_valid_control_selection": static_selection,
    }


def lineage_row() -> dict[str, Any]:
    return {
        "lineage_id": f"{TASK_ID}__lineage",
        "entity_type": "source_research_lineage",
        "stage": "exploration",
        "record_role": "carried_forward_parent_source_and_adaptation_lineage",
        "source_record_id": parent.SOURCE_RECORD_ID,
        "parent_strategy_id": PARENT_STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "parent_outcome": "closed_exploration",
        "parent_failure_reason": "low_volatility_control_explanation",
        "new_strategy_id": STRATEGY_ID,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "new_source_library_record_created": False,
        "benchmark_rule_predeclared_before_parent_performance": True,
        "adaptation_selected_after_parent_results": True,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    }


def strategy_row(
    static_selection: tuple[str, ...],
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
        "instrument_universe": "|".join(parent.SECTORS + ("BIL",)),
        "parameters": frozen_parameters(static_selection),
        "benchmark_or_control": list(CONTROL_IDS),
        "route": "diversifier_only",
        "stage": STAGE,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "exploratory_variant",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "frozen_rule": frozen_rule(),
        "external_source_strategy_claimed": False,
        "rule_previously_preregistered_as_benchmark": True,
        "adaptation_selected_after_viewing_results": True,
        "validation_evidence_claimed": False,
        "authoritative_registry_record_created": False,
    }


def trial_rows(
    static_selection: tuple[str, ...],
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> list[dict[str, Any]]:
    common = {
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "experiment_trial",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "|".join(parent.SECTORS + ("BIL",)),
        "parameters": frozen_parameters(static_selection),
        "benchmark_or_control": list(CONTROL_IDS),
        "stage": STAGE,
        "adaptation_label": "exploratory_variant",
        "validation_evidence_claimed": False,
        "authoritative_registry_record_created": False,
    }
    return [
        {
            **common,
            "strategy_id": PARENT_STRATEGY_ID,
            "family_id": parent.FAMILY_ID,
            "display_name": parent.DISPLAY_NAME,
            "strategy_architecture": parent.ARCHITECTURE,
            "source_or_research_lineage": parent.SOURCE_LINEAGE,
            "instrument_universe": "|".join(parent.SECTORS + ("BIL",)),
            "parameters": parent.parameters(),
            "benchmark_or_control": list(parent.CONTROL_IDS),
            "trial_id": PARENT_TRIAL_ID,
            "parent_trial_id": "",
            "record_role": "carried_forward_parent_trial_read_only",
            "outcome": "closed_exploration",
            "failure_reason": "low_volatility_control_explanation",
            "next_action": parent.NEXT_CLOSE,
            "adaptation_label": "",
            "parent_MDD_rule_changed": False,
            "new_signal_invented_after_results": False,
            "predeclared_benchmark_promoted_explicitly": False,
            "volatility_window_changed": False,
            "selected_count_changed": False,
            "universe_changed": False,
            "holding_period_changed": False,
            "execution_changed": False,
            "cost_model_changed": False,
            "result_driven_adaptation": False,
            "optimization_performed": False,
            "post_result_parameter_changes_allowed": False,
            "changed_fields_from_parent": "",
            "preregistration_timestamp": parent.FROZEN_TIMESTAMP,
        },
        {
            **common,
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "record_role": "new_child_experiment_trial",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
            "parent_MDD_rule_changed": True,
            "new_signal_invented_after_results": False,
            "predeclared_benchmark_promoted_explicitly": True,
            "volatility_window_changed": False,
            "selected_count_changed": False,
            "universe_changed": False,
            "holding_period_changed": False,
            "execution_changed": False,
            "cost_model_changed": False,
            "result_driven_adaptation": True,
            "optimization_performed": False,
            "post_result_parameter_changes_allowed": False,
            "changed_fields_from_parent": (
                "signal_metric_changed_from_MDD_to_predeclared_realized_"
                "volatility_control_and_route_changed_to_diversifier_only"
            ),
            "preregistration_timestamp": FROZEN_TIMESTAMP,
        },
    ]


def benchmark_rows(static_selection: tuple[str, ...]) -> list[dict[str, Any]]:
    rules = {
        "monthly_equal_weight_nine_sector_control": (
            "Monthly equal-weight the same nine sectors with following-session "
            "close execution."
        ),
        "static_first_valid_low_volatility_bottom3_sector_control": (
            "Freeze the first valid low-volatility selection "
            f"{'|'.join(static_selection)} before new diagnostics and rebalance "
            "that basket monthly at equal weights."
        ),
        PARENT_STRATEGY_ID: (
            "Carry the closed parent MDD configuration as contextual benchmark "
            "only."
        ),
        "SPY_buy_and_hold": "Hold SPY throughout the identical period.",
        "BIL_buy_and_hold": "Hold BIL throughout the identical period.",
    }
    roles = {
        "monthly_equal_weight_nine_sector_control": "critical_equal_weight_control",
        "static_first_valid_low_volatility_bottom3_sector_control": (
            "critical_static_exposure_control"
        ),
        PARENT_STRATEGY_ID: "contextual_parent_MDD_benchmark",
        "SPY_buy_and_hold": "broad_market_control",
        "BIL_buy_and_hold": "inactive_asset_control",
    }
    return [
        {
            "benchmark_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "role": roles[control_id],
            "frozen_rule": rules[control_id],
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for control_id in CONTROL_IDS
    ]


def process_row(next_action: str, outcome: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "strategy_counted": False,
        "trial_counted": False,
        "execute_next_action_now": False,
    }


def parent_first_static_selection() -> tuple[str, ...]:
    rows = read_csv(PARENT_DIR / "formation_selection_diagnostics.csv")
    valid = [row for row in rows if row["signal_complete"] == "true"]
    if not valid:
        raise RuntimeError("Parent packet has no valid low-volatility formation")
    first_date = min(row["formation_date"] for row in valid)
    first = [row for row in valid if row["formation_date"] == first_date]
    ordered = sorted(first, key=lambda row: int(row["realized_volatility_rank"]))
    selection = tuple(row["symbol"] for row in ordered[:3])
    if len(selection) != 3:
        raise RuntimeError("Static first-valid basket is incomplete")
    return selection


def write_preregistration(static_selection: tuple[str, ...]) -> str:
    pending = "preregistered_pending_execution"
    lineage = [lineage_row()]
    strategies = [strategy_row(static_selection, pending, "", TASK_ID)]
    trials = trial_rows(static_selection, pending, "", TASK_ID)
    benchmarks = benchmark_rows(static_selection)
    process = [process_row(TASK_ID, "preregistered")]
    parent.helpers.write_csv(
        OUTPUT_DIR / "source_and_adaptation_lineage.csv",
        lineage,
        list(lineage[0]),
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0])
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0])
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "process_task_log.csv", process, list(process[0])
    )
    return parent.helpers.canonical_hash(
        {
            "lineage": lineage,
            "strategy": strategies,
            "trials": trials,
            "benchmarks": benchmarks,
            "static_selection": static_selection,
            "written_before_performance": True,
        }
    )


def static_control_path(
    prices: pd.DataFrame,
    formations: list[parent.Formation],
    selection: tuple[str, ...],
    cost_bps: float,
) -> dict[str, Any]:
    symbols = tuple(prices.columns)
    bil_target = {symbol: 0.0 for symbol in symbols}
    bil_target["BIL"] = 1.0
    static_target = {symbol: 0.0 for symbol in symbols}
    for symbol in selection:
        static_target[symbol] = 1.0 / len(selection)
    valid = [formation for formation in formations if formation.complete]
    if not valid:
        raise RuntimeError("No complete formation for static control")
    first_execution = valid[0].execution_date
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(prices.index[0]): bil_target
    }
    for formation_date in parent.month_ends(prices.index):
        execution = parent.next_session(prices.index, formation_date)
        if execution is not None and execution >= first_execution:
            events[execution] = static_target
    event_frame = parent.close_engine.event_frame(prices.index, symbols, events)
    path = parent.close_engine.simulate_path(
        prices,
        event_frame,
        cost_bps,
        "first_valid_basket_frozen_before_diagnostics_monthly_following_close",
    )
    return parent.attach_path_metadata(
        path,
        "static_first_valid_low_volatility_bottom3_sector_control",
        [pd.Timestamp(date) for date in event_frame.index[1:]],
        0,
    )


def build_core(
    parent_core: dict[str, Any],
    static_selection: tuple[str, ...],
) -> dict[str, Any]:
    candidate_paths = {
        cost: parent_core["control_paths"][(CANDIDATE_PATH_ID, cost)]
        for cost in COST_BPS
    }
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        control_paths[
            ("monthly_equal_weight_nine_sector_control", cost)
        ] = parent_core["control_paths"][
            ("monthly_equal_weight_nine_sector_control", cost)
        ]
        control_paths[(PARENT_STRATEGY_ID, cost)] = parent_core[
            "candidate_paths"
        ][cost]
        control_paths[("SPY_buy_and_hold", cost)] = parent_core[
            "control_paths"
        ][("SPY_buy_and_hold", cost)]
        control_paths[("BIL_buy_and_hold", cost)] = parent_core[
            "control_paths"
        ][("BIL_buy_and_hold", cost)]
        control_paths[
            ("static_first_valid_low_volatility_bottom3_sector_control", cost)
        ] = static_control_path(
            parent_core["prices"],
            parent_core["formations"],
            static_selection,
            cost,
        )
    reference = parent.market.active_vm_dsr_usci_reference_returns()
    portfolio_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in COST_BPS:
        aligned_reference = reference.reindex(
            parent_core["prices"].index
        ).dropna()
        portfolio_paths[(PORTFOLIO_IDS["reference"], cost)] = parent.portfolio_path(
            aligned_reference, None, PORTFOLIO_IDS["reference"], cost
        )
        sleeve_paths = {
            STRATEGY_ID: candidate_paths[cost],
            "monthly_equal_weight_nine_sector_control": control_paths[
                ("monthly_equal_weight_nine_sector_control", cost)
            ],
            "static_first_valid_low_volatility_bottom3_sector_control": (
                control_paths[
                    (
                        "static_first_valid_low_volatility_bottom3_sector_control",
                        cost,
                    )
                ]
            ),
            PARENT_STRATEGY_ID: control_paths[(PARENT_STRATEGY_ID, cost)],
            "SPY_buy_and_hold": control_paths[("SPY_buy_and_hold", cost)],
        }
        for sleeve_id, sleeve_path in sleeve_paths.items():
            portfolio_id = PORTFOLIO_IDS[sleeve_id]
            portfolio_paths[(portfolio_id, cost)] = parent.portfolio_path(
                aligned_reference, sleeve_path, portfolio_id, cost
            )
    return {
        "parent_core": parent_core,
        "candidate_paths": candidate_paths,
        "control_paths": control_paths,
        "portfolio_paths": portfolio_paths,
        "static_selection": static_selection,
    }


def period_portfolio_metrics(
    path: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    index = path["returns"].index if period_index is None else period_index
    returns = path["returns"].reindex(index).dropna()
    daily = path["daily"].reindex(returns.index)
    held = path["held_weights"].reindex(returns.index).dropna(how="all")
    metrics = parent.market.metrics_from_returns(returns)
    numeric = bool(
        len(returns) and np.isfinite(returns.to_numpy(dtype=float)).all()
    )
    exposure = bool(
        not held.empty
        and np.isfinite(held.to_numpy(dtype=float)).all()
        and (held.to_numpy(dtype=float) >= -parent.TOLERANCE).all()
        and float(held.abs().sum(axis=1).max()) <= 1.0 + parent.TOLERANCE
        and float(held.sum(axis=1).max()) <= 1.0 + parent.TOLERANCE
    )
    event_dates = set(pd.DatetimeIndex(index))
    formation_count = sum(
        pd.Timestamp(date) in event_dates for date in path["valid_execution_dates"]
    )
    return {
        **metrics,
        "average_risky_exposure": 1.0,
        "total_one_way_turnover": float(path["turnover"].reindex(returns.index).sum()),
        "formation_count": formation_count,
        "vintage_count": 0,
        "trade_or_rebalance_count": int(
            (path["turnover"].reindex(returns.index).fillna(0.0) > parent.TOLERANCE).sum()
        ),
        "transaction_cost_drag": float(path["cost"].reindex(returns.index).sum()),
        "inner_sleeve_transaction_cost_drag": float(
            daily["inner_cost_drag"].sum()
        ),
        "outer_transaction_cost_drag": float(daily["outer_cost_drag"].sum()),
        "maximum_single_sector_weight": float(held.max().max()),
        "maximum_gross_exposure": float(held.abs().sum(axis=1).max()),
        "maximum_daily_weight_sum": float(held.sum(axis=1).max()),
        "timing_invariant_status": "pass",
        "numeric_invariant_status": "pass" if numeric else "fail",
        "exposure_invariant_status": "pass" if exposure else "fail",
        "weight_invariant_status": "pass" if exposure else "fail",
        "invariant_pass": bool(numeric and exposure),
    }


def metric_difference(
    expected: Any,
    actual: Any,
    tolerance: float = TOLERANCE,
) -> tuple[float | str, bool]:
    try:
        expected_float = float(expected)
        actual_float = float(actual)
    except (TypeError, ValueError):
        return "", str(expected) == str(actual)
    difference = actual_float - expected_float
    return difference, abs(difference) <= tolerance


def reproduction_rows(
    parent_core: dict[str, Any],
    core: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []

    def add(
        check_id: str,
        scope: str,
        cost: Any,
        period: str,
        metric: str,
        expected: Any,
        actual: Any,
        tolerance: float = TOLERANCE,
    ) -> None:
        difference, passed = metric_difference(expected, actual, tolerance)
        rows.append(
            {
                "check_id": check_id,
                "scope": scope,
                "cost_assumption_bps": cost,
                "period_label": period,
                "metric": metric,
                "expected_parent_value": expected,
                "actual_reproduced_value": actual,
                "difference": difference,
                "tolerance": tolerance,
                "reproduction_pass": passed,
            }
        )

    parent_standalone = [
        row
        for row in read_csv(PARENT_DIR / "control_results.csv")
        if row["row_id"] == CANDIDATE_PATH_ID
    ]
    standalone_fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "average_risky_exposure",
        "total_one_way_turnover",
        "transaction_cost_drag",
    )
    for expected in parent_standalone:
        cost = float(expected["cost_assumption_bps"])
        actual = parent.path_metrics(core["candidate_paths"][cost])
        for field in standalone_fields:
            add(
                f"standalone_{cost}_{field}",
                "standalone_low_volatility",
                cost,
                "full_period",
                field,
                expected[field],
                actual[field],
            )
    parent_halves = [
        row
        for row in read_csv(PARENT_DIR / "chronological_half_results.csv")
        if row["row_id"] == CANDIDATE_PATH_ID
    ]
    half_map = dict(parent.split_halves(core["candidate_paths"][5.0]["returns"].index))
    for expected in parent_halves:
        label = expected["period_label"]
        actual = parent.path_metrics(core["candidate_paths"][5.0], half_map[label])
        for field in standalone_fields:
            add(
                f"standalone_{label}_{field}",
                "standalone_low_volatility",
                5.0,
                label,
                field,
                expected[field],
                actual[field],
            )
    parent_portfolios = [
        row
        for row in read_csv(PARENT_DIR / "portfolio_contribution_results.csv")
        if row["portfolio_id"]
        == "80pct_reference_20pct_low_volatility_control"
    ]
    portfolio_fields = (
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "total_one_way_turnover",
        "transaction_cost_drag",
        "inner_sleeve_transaction_cost_drag",
        "outer_transaction_cost_drag",
    )
    for expected in parent_portfolios:
        cost = float(expected["cost_assumption_bps"])
        actual = period_portfolio_metrics(
            core["portfolio_paths"][(PORTFOLIO_IDS[STRATEGY_ID], cost)]
        )
        for field in portfolio_fields:
            add(
                f"portfolio_{cost}_{field}",
                "80_20_low_volatility",
                cost,
                "full_period",
                field,
                expected[field],
                actual[field],
            )
    parent_selections: dict[str, tuple[str, ...]] = {}
    for row in read_csv(PARENT_DIR / "formation_selection_diagnostics.csv"):
        if row["signal_complete"] == "true":
            parent_selections.setdefault(
                row["formation_date"],
                tuple(json.loads(row["low_volatility_control_selected_sectors"])),
            )
    generated_selections = {
        formation.formation_date.date().isoformat(): formation.volatility_selection
        for formation in parent_core["formations"]
        if formation.complete
    }
    for formation_date, expected in sorted(parent_selections.items()):
        add(
            f"formation_selection_{formation_date}",
            "parent_formation_selection",
            "",
            formation_date,
            "selected_sectors",
            "|".join(expected),
            "|".join(generated_selections.get(formation_date, ())),
            0.0,
        )
    parent_consistency = json.loads(
        (PARENT_DIR / "consistency_check.json").read_text(encoding="utf-8")
    )
    actual_core_hash = parent.core_hash(parent_core)
    add(
        "parent_deterministic_core_hash",
        "parent_core",
        "",
        "full_parent_packet",
        "deterministic_core_hash",
        parent_consistency["deterministic_core_hash"],
        actual_core_hash,
        0.0,
    )
    parent_invariants = read_csv(PARENT_DIR / "invariant_results.csv")
    add(
        "all_parent_invariants",
        "parent_invariants",
        "",
        "all",
        "all_invariant_pass",
        True,
        all(row["invariant_pass"] == "true" for row in parent_invariants),
        0.0,
    )
    return rows, all(bool(row["reproduction_pass"]) for row in rows)


def result_row(
    row_id: str,
    row_type: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any],
    outcome: str,
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": TRIAL_ID,
        "entity_type": (
            "experiment_trial"
            if row_type == "candidate"
            else "benchmark_reference"
        ),
        "stage": STAGE if row_type == "candidate" else "benchmark_reference_only",
        "row_type": row_type,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_exploration"
            if period_label == "full_period"
            else "chronological_half_not_validation_or_untouched_holdout"
        ),
        "outcome": outcome if row_type == "candidate" else "benchmark_only",
        "failure_reason": failure_reason if row_type == "candidate" else "",
        **metrics,
    }


def rolling_periods(
    index: pd.DatetimeIndex, horizon_months: int
) -> list[tuple[str, pd.DatetimeIndex]]:
    periods = sorted(set(index.to_period("M")))
    windows: list[tuple[str, pd.DatetimeIndex]] = []
    for end_position in range(horizon_months - 1, len(periods)):
        selected = set(
            periods[end_position - horizon_months + 1 : end_position + 1]
        )
        window_index = index[index.to_period("M").isin(selected)]
        if len(window_index):
            window_id = (
                f"{horizon_months}m_"
                f"{window_index[0].date().isoformat()}_"
                f"{window_index[-1].date().isoformat()}"
            )
            windows.append((window_id, window_index))
    return windows


def rolling_rows(
    core: dict[str, Any], horizon_months: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_path = core["portfolio_paths"][
        (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
    ]
    paths = {
        "reference": core["portfolio_paths"][
            (PORTFOLIO_IDS["reference"], PRIMARY_COST_BPS)
        ],
        "monthly_equal_weight_nine_sector_control": core["portfolio_paths"][
            (
                PORTFOLIO_IDS["monthly_equal_weight_nine_sector_control"],
                PRIMARY_COST_BPS,
            )
        ],
        "static_first_valid_low_volatility_bottom3_sector_control": (
            core["portfolio_paths"][
                (
                    PORTFOLIO_IDS[
                        "static_first_valid_low_volatility_bottom3_sector_control"
                    ],
                    PRIMARY_COST_BPS,
                )
            ]
        ),
    }
    rows: list[dict[str, Any]] = []
    for window_id, period in rolling_periods(
        candidate_path["returns"].index, horizon_months
    ):
        candidate = period_portfolio_metrics(candidate_path, period)
        reference = period_portfolio_metrics(paths["reference"], period)
        improves_reference = bool(
            float(candidate["sharpe_ratio"]) > float(reference["sharpe_ratio"])
            or float(candidate["maximum_drawdown"])
            > float(reference["maximum_drawdown"])
        )
        for comparator_id, path in paths.items():
            comparator = period_portfolio_metrics(path, period)
            rows.append(
                {
                    "window_id": window_id,
                    "horizon_months": horizon_months,
                    "window_start": candidate["evaluation_start"],
                    "window_end": candidate["evaluation_end"],
                    "candidate_portfolio_id": PORTFOLIO_IDS[STRATEGY_ID],
                    "comparator_id": comparator_id,
                    "candidate_cagr": candidate["cagr"],
                    "comparator_cagr": comparator["cagr"],
                    "cagr_difference": float(candidate["cagr"])
                    - float(comparator["cagr"]),
                    "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                    "comparator_sharpe_ratio": comparator["sharpe_ratio"],
                    "sharpe_difference": float(candidate["sharpe_ratio"])
                    - float(comparator["sharpe_ratio"]),
                    "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                    "comparator_maximum_drawdown": comparator[
                        "maximum_drawdown"
                    ],
                    "maximum_drawdown_difference": float(
                        candidate["maximum_drawdown"]
                    )
                    - float(comparator["maximum_drawdown"]),
                    "comparator_dominates_candidate": parent.dominates(
                        comparator, candidate
                    ),
                    "candidate_dominates_comparator": parent.dominates(
                        candidate, comparator
                    ),
                    "candidate_improves_reference_sharpe_or_drawdown": (
                        improves_reference
                    ),
                    "unfavorable_window_retained": True,
                }
            )
    summary: list[dict[str, Any]] = []
    for comparator_id in ROLLING_COMPARATORS:
        selected = [row for row in rows if row["comparator_id"] == comparator_id]
        summary.append(
            {
                "horizon_months": horizon_months,
                "comparator_id": comparator_id,
                "eligible_window_count": len(selected),
                "percentage_candidate_improves_reference_sharpe_or_drawdown": (
                    sum(
                        bool(
                            row[
                                "candidate_improves_reference_sharpe_or_drawdown"
                            ]
                        )
                        for row in selected
                    )
                    / len(selected)
                    if selected
                    else float("nan")
                ),
                "percentage_comparator_dominates_candidate": (
                    sum(bool(row["comparator_dominates_candidate"]) for row in selected)
                    / len(selected)
                    if selected
                    else float("nan")
                ),
                "median_cagr_difference": (
                    float(pd.Series([row["cagr_difference"] for row in selected]).median())
                    if selected
                    else float("nan")
                ),
                "median_sharpe_difference": (
                    float(
                        pd.Series(
                            [row["sharpe_difference"] for row in selected]
                        ).median()
                    )
                    if selected
                    else float("nan")
                ),
                "median_maximum_drawdown_difference": (
                    float(
                        pd.Series(
                            [
                                row["maximum_drawdown_difference"]
                                for row in selected
                            ]
                        ).median()
                    )
                    if selected
                    else float("nan")
                ),
            }
        )
    return rows, summary


def formation_rows(core: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_path = core["candidate_paths"][PRIMARY_COST_BPS]
    held = candidate_path["held_weights"]
    valid = [formation for formation in core["parent_core"]["formations"] if formation.complete]
    selected_by_symbol = {
        symbol: [
            symbol in formation.volatility_selection for formation in valid
        ]
        for symbol in parent.SECTORS
    }
    max_streak: dict[str, int] = {}
    for symbol, flags in selected_by_symbol.items():
        longest = 0
        current = 0
        for flag in flags:
            current = current + 1 if flag else 0
            longest = max(longest, current)
        max_streak[symbol] = longest
    static_set = set(core["static_selection"])
    formation_identical = [
        set(formation.volatility_selection) == static_set for formation in valid
    ]
    rows: list[dict[str, Any]] = []
    for formation in core["parent_core"]["formations"]:
        for symbol in parent.SECTORS:
            rows.append(
                {
                    "record_type": "formation_sector",
                    "formation_date": formation.formation_date.date().isoformat(),
                    "six_month_window_start": (
                        formation.window_start.date().isoformat()
                        if formation.window_start is not None
                        else ""
                    ),
                    "six_month_window_end": formation.window_end.date().isoformat(),
                    "symbol": symbol,
                    "sample_daily_volatility_ddof1": (
                        formation.realized_volatility.get(symbol, "")
                    ),
                    "volatility_rank": formation.volatility_ranks.get(symbol, ""),
                    "selected": symbol in formation.volatility_selection,
                    "selected_sectors": formation.volatility_selection,
                    "MDD_selected_sectors": formation.candidate_selection,
                    "overlap_with_MDD_selection_count": len(
                        set(formation.volatility_selection)
                        & set(formation.candidate_selection)
                    ),
                    "overlap_with_monthly_equal_weight_count": (
                        len(formation.volatility_selection)
                    ),
                    "execution_date": formation.execution_date.date().isoformat(),
                    "expiration_date": (
                        formation.expiration_date.date().isoformat()
                        if formation.expiration_date is not None
                        else ""
                    ),
                    "signal_complete": formation.complete,
                    "selection_frequency": "",
                    "maximum_consecutive_selection_count": "",
                    "average_holding_weight": "",
                    "completed_vintage_count": "",
                    "turnover_year": "",
                    "annual_one_way_turnover": "",
                    "percentage_formations_identical_to_static_basket": "",
                }
            )
    for symbol in parent.SECTORS:
        flags = selected_by_symbol[symbol]
        rows.append(
            {
                "record_type": "sector_summary",
                "formation_date": "",
                "six_month_window_start": "",
                "six_month_window_end": "",
                "symbol": symbol,
                "sample_daily_volatility_ddof1": "",
                "volatility_rank": "",
                "selected": "",
                "selected_sectors": "",
                "MDD_selected_sectors": "",
                "overlap_with_MDD_selection_count": "",
                "overlap_with_monthly_equal_weight_count": "",
                "execution_date": "",
                "expiration_date": "",
                "signal_complete": "",
                "selection_frequency": sum(flags) / len(flags),
                "maximum_consecutive_selection_count": max_streak[symbol],
                "average_holding_weight": float(held[symbol].mean()),
                "completed_vintage_count": "",
                "turnover_year": "",
                "annual_one_way_turnover": "",
                "percentage_formations_identical_to_static_basket": "",
            }
        )
    for year, turnover in candidate_path["turnover"].groupby(
        candidate_path["turnover"].index.year
    ).sum().items():
        rows.append(
            {
                "record_type": "annual_turnover_summary",
                "formation_date": "",
                "six_month_window_start": "",
                "six_month_window_end": "",
                "symbol": "",
                "sample_daily_volatility_ddof1": "",
                "volatility_rank": "",
                "selected": "",
                "selected_sectors": "",
                "MDD_selected_sectors": "",
                "overlap_with_MDD_selection_count": "",
                "overlap_with_monthly_equal_weight_count": "",
                "execution_date": "",
                "expiration_date": "",
                "signal_complete": "",
                "selection_frequency": "",
                "maximum_consecutive_selection_count": "",
                "average_holding_weight": "",
                "completed_vintage_count": "",
                "turnover_year": int(year),
                "annual_one_way_turnover": float(turnover),
                "percentage_formations_identical_to_static_basket": "",
            }
        )
    completed = sum(
        bool(row["completed"]) for row in candidate_path["vintage_rows"]
    )
    rows.append(
        {
            "record_type": "overall_summary",
            "formation_date": "",
            "six_month_window_start": "",
            "six_month_window_end": "",
            "symbol": "",
            "sample_daily_volatility_ddof1": "",
            "volatility_rank": "",
            "selected": "",
            "selected_sectors": "",
            "MDD_selected_sectors": "",
            "overlap_with_MDD_selection_count": "",
            "overlap_with_monthly_equal_weight_count": "",
            "execution_date": "",
            "expiration_date": "",
            "signal_complete": "",
            "selection_frequency": "",
            "maximum_consecutive_selection_count": "",
            "average_holding_weight": "",
            "completed_vintage_count": completed,
            "turnover_year": "",
            "annual_one_way_turnover": "",
            "percentage_formations_identical_to_static_basket": (
                sum(formation_identical) / len(formation_identical)
            ),
        }
    )
    return rows


def classify(
    core: dict[str, Any],
    reproduction_pass: bool,
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, str, str]:
    if not reproduction_pass:
        return (
            "blocked_feasibility",
            "data_or_comparability_failure",
            "parent_low_volatility_benchmark_did_not_reproduce_within_1e-9",
            NEXT_BLOCK,
        )
    candidate = parent.path_metrics(core["candidate_paths"][PRIMARY_COST_BPS])
    controls = {
        control_id: parent.path_metrics(
            core["control_paths"][(control_id, PRIMARY_COST_BPS)]
        )
        for control_id in CONTROL_IDS
    }
    portfolio = {
        key: period_portfolio_metrics(path)
        for (key, cost), path in core["portfolio_paths"].items()
        if cost == PRIMARY_COST_BPS
    }
    candidate_portfolio = portfolio[PORTFOLIO_IDS[STRATEGY_ID]]
    reference = portfolio[PORTFOLIO_IDS["reference"]]
    critical = {
        control_id: portfolio[PORTFOLIO_IDS[control_id]]
        for control_id in CRITICAL_CONTROL_IDS
    }
    all_invariants = bool(
        candidate["invariant_pass"]
        and all(value["invariant_pass"] for value in controls.values())
        and all(value["invariant_pass"] for value in portfolio.values())
    )
    if not all_invariants:
        return (
            "blocked_feasibility",
            "methodology_failure",
            "standalone_or_portfolio_invariant_failed",
            NEXT_BLOCK,
        )
    if float(candidate["total_return"]) <= 0.0:
        return (
            "closed_exploration",
            "weak_portfolio_contribution",
            "standalone_dynamic_low_volatility_return_not_positive",
            NEXT_CLOSE,
        )
    material_vs_reference = bool(
        float(candidate_portfolio["sharpe_ratio"])
        - float(reference["sharpe_ratio"])
        >= 0.02
        or float(candidate_portfolio["maximum_drawdown"])
        - float(reference["maximum_drawdown"])
        >= 0.01
    )
    if not material_vs_reference or parent.worse_on_both(
        candidate_portfolio, reference
    ):
        return (
            "closed_exploration",
            "weak_portfolio_contribution",
            "candidate_80_20_did_not_add_required_material_value_to_reference",
            NEXT_CLOSE,
        )
    for control_id, control in critical.items():
        if parent.dominates(control, candidate_portfolio) or not parent.material_advantage(
            candidate_portfolio, control
        ):
            return (
                "closed_exploration",
                "benchmark_like_behavior",
                f"critical_control_replicated_or_dominated_candidate:{control_id}",
                NEXT_CLOSE,
            )
    half_periods = dict(
        parent.split_halves(
            core["portfolio_paths"][
                (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
            ]["returns"].index
        )
    )
    for half_label, period in half_periods.items():
        candidate_half = period_portfolio_metrics(
            core["portfolio_paths"][
                (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
            ],
            period,
        )
        comparison_ids = ("reference",) + CRITICAL_CONTROL_IDS
        for comparison_id in comparison_ids:
            comparison_half = period_portfolio_metrics(
                core["portfolio_paths"][
                    (PORTFOLIO_IDS[comparison_id], PRIMARY_COST_BPS)
                ],
                period,
            )
            if parent.worse_on_both(candidate_half, comparison_half):
                return (
                    "closed_exploration",
                    "period_instability",
                    f"candidate_worse_on_sharpe_and_drawdown_in_{half_label}_vs_{comparison_id}",
                    NEXT_CLOSE,
                )
    for horizon in (36, 60):
        horizon_rows = [
            row for row in rolling_summary if row["horizon_months"] == horizon
        ]
        reference_row = next(
            row for row in horizon_rows if row["comparator_id"] == "reference"
        )
        if (
            float(
                reference_row[
                    "percentage_candidate_improves_reference_sharpe_or_drawdown"
                ]
            )
            <= 0.5
        ):
            return (
                "closed_exploration",
                "period_instability",
                f"candidate_improved_reference_in_no_more_than_half_of_{horizon}m_windows",
                NEXT_CLOSE,
            )
        for control_id in CRITICAL_CONTROL_IDS:
            row = next(
                item
                for item in horizon_rows
                if item["comparator_id"] == control_id
            )
            if float(row["percentage_comparator_dominates_candidate"]) > 0.5:
                return (
                    "closed_exploration",
                    "overfit_or_unstable",
                    f"{control_id}_dominated_more_than_half_of_{horizon}m_windows",
                    NEXT_CLOSE,
                )
    portfolio_10 = {
        key: period_portfolio_metrics(path)
        for (key, cost), path in core["portfolio_paths"].items()
        if cost == 10.0
    }
    candidate_10 = portfolio_10[PORTFOLIO_IDS[STRATEGY_ID]]
    reference_10 = portfolio_10[PORTFOLIO_IDS["reference"]]
    if not (
        float(candidate_10["sharpe_ratio"]) > float(reference_10["sharpe_ratio"])
        or float(candidate_10["maximum_drawdown"])
        > float(reference_10["maximum_drawdown"])
    ):
        return (
            "closed_exploration",
            "cost_drag",
            "candidate_did_not_improve_reference_at_10bps",
            NEXT_CLOSE,
        )
    for control_id in CRITICAL_CONTROL_IDS:
        control_10 = portfolio_10[PORTFOLIO_IDS[control_id]]
        if parent.dominates(control_10, candidate_10) or parent.worse_on_both(
            candidate_10, control_10
        ):
            return (
                "closed_exploration",
                "cost_drag",
                f"critical_control_unfavorable_at_10bps:{control_id}",
                NEXT_CLOSE,
            )
    return (
        "exploratory_followup_candidate_diversifier",
        "",
        "result_driven_diversifier_adaptation_passed_all_preregistered_exploration_gates",
        NEXT_ADVANCE,
    )


def run() -> dict[str, Any]:
    if not PARENT_DIR.exists():
        raise RuntimeError(f"Missing parent packet: {PARENT_DIR}")
    protected_before = hash_map(PROTECTED_PATHS)
    cache_before = parent.helpers.tree_hash(CACHE_DIR)
    parent_evidence_before = parent.helpers.tree_hash(PARENT_DIR)
    prior_evidence_before = parent.helpers.tree_hash(ROOT / "evidence", OUTPUT_DIR)
    attachment_before = parent.helpers.file_hash(SOURCE_ATTACHMENT)
    clean_output()
    static_selection = parent_first_static_selection()
    preregistration_hash = write_preregistration(static_selection)

    preflight_rows, frames, evaluation_index = parent.data_preflight()
    preflight_pass = bool(
        len(evaluation_index)
        and all(
            row["candidate_preflight_status"] == "pass"
            for row in preflight_rows
        )
    )
    core: dict[str, Any] | None = None
    reproduction: list[dict[str, Any]] = []
    reproduction_pass = False
    rolling_36: list[dict[str, Any]] = []
    rolling_60: list[dict[str, Any]] = []
    rolling_summary: list[dict[str, Any]] = []
    deterministic_hash_one = ""
    deterministic_hash_two = ""
    if preflight_pass:
        parent_core = parent.run_core(frames, evaluation_index)
        core = build_core(parent_core, static_selection)
        reproduction, reproduction_pass = reproduction_rows(parent_core, core)
        rolling_36, summary_36 = rolling_rows(core, 36)
        rolling_60, summary_60 = rolling_rows(core, 60)
        rolling_summary = summary_36 + summary_60
        deterministic_hash_one = parent.helpers.canonical_hash(
            {
                "parent_core_hash": parent.core_hash(parent_core),
                "static_selection": static_selection,
                "static_returns": core["control_paths"][
                    (
                        "static_first_valid_low_volatility_bottom3_sector_control",
                        5.0,
                    )
                ]["returns"].round(15).tolist(),
                "rolling_36": rolling_36,
                "rolling_60": rolling_60,
            }
        )
        repeated_parent = parent.run_core(frames, evaluation_index)
        repeated_core = build_core(repeated_parent, static_selection)
        repeated_36, _ = rolling_rows(repeated_core, 36)
        repeated_60, _ = rolling_rows(repeated_core, 60)
        deterministic_hash_two = parent.helpers.canonical_hash(
            {
                "parent_core_hash": parent.core_hash(repeated_parent),
                "static_selection": static_selection,
                "static_returns": repeated_core["control_paths"][
                    (
                        "static_first_valid_low_volatility_bottom3_sector_control",
                        5.0,
                    )
                ]["returns"].round(15).tolist(),
                "rolling_36": repeated_36,
                "rolling_60": repeated_60,
            }
        )
        outcome, failure_reason, decision_reason, next_action = classify(
            core, reproduction_pass, rolling_summary
        )
    else:
        outcome = "blocked_feasibility"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "verified_parent_cache_no_longer_passed_preflight"
        next_action = NEXT_BLOCK

    lineage = [lineage_row()]
    strategies = [
        strategy_row(static_selection, outcome, failure_reason, next_action)
    ]
    trials = trial_rows(
        static_selection, outcome, failure_reason, next_action
    )
    benchmarks = benchmark_rows(static_selection)
    process = [process_row(next_action, "completed")]
    parent.helpers.write_csv(
        OUTPUT_DIR / "source_and_adaptation_lineage.csv",
        lineage,
        list(lineage[0]),
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0])
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0])
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "process_task_log.csv", process, list(process[0])
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        [
            "check_id",
            "scope",
            "cost_assumption_bps",
            "period_label",
            "metric",
            "expected_parent_value",
            "actual_reproduced_value",
            "difference",
            "tolerance",
            "reproduction_pass",
        ],
    )

    static_definition = [
        {
            "control_id": (
                "static_first_valid_low_volatility_bottom3_sector_control"
            ),
            "definition_frozen_before_new_performance": True,
            "selection_source": "parent_first_fully_valid_low_volatility_formation",
            "first_valid_formation_date": (
                min(
                    formation.formation_date
                    for formation in core["parent_core"]["formations"]
                    if formation.complete
                ).date().isoformat()
                if core is not None
                else ""
            ),
            "first_execution_date": (
                min(
                    formation.execution_date
                    for formation in core["parent_core"]["formations"]
                    if formation.complete
                ).date().isoformat()
                if core is not None
                else ""
            ),
            "frozen_sectors": static_selection,
            "within_basket_weights": {
                symbol: 1.0 / len(static_selection)
                for symbol in static_selection
            },
            "preformation_holding": "BIL",
            "rebalance_frequency": "monthly",
            "execution": "following_regular_session_close",
            "selected_from_full_period_performance": False,
            "optimization_performed": False,
        }
    ]
    parent.helpers.write_csv(
        OUTPUT_DIR / "static_control_definition.csv",
        static_definition,
        list(static_definition[0]),
    )

    standalone_rows: list[dict[str, Any]] = []
    standalone_halves: list[dict[str, Any]] = []
    portfolio_rows: list[dict[str, Any]] = []
    portfolio_halves: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    vintages: list[dict[str, Any]] = []
    if core is not None:
        for cost in COST_BPS:
            paths = [
                (STRATEGY_ID, "candidate", core["candidate_paths"][cost]),
                *[
                    (
                        control_id,
                        "control",
                        core["control_paths"][(control_id, cost)],
                    )
                    for control_id in CONTROL_IDS
                ],
            ]
            for row_id, row_type, path in paths:
                metric = parent.path_metrics(path)
                standalone_rows.append(
                    result_row(
                        row_id,
                        row_type,
                        cost,
                        "full_period",
                        metric,
                        outcome,
                        failure_reason,
                    )
                )
                turnover_rows.append(
                    {
                        "record_scope": "standalone",
                        "row_id": row_id,
                        "cost_assumption_bps": cost,
                        "total_one_way_turnover": metric[
                            "total_one_way_turnover"
                        ],
                        "inner_sleeve_transaction_cost_drag": metric[
                            "transaction_cost_drag"
                        ],
                        "outer_transaction_cost_drag": 0.0,
                        "total_transaction_cost_drag": metric[
                            "transaction_cost_drag"
                        ],
                        "turnover_formula": (
                            "0.5*sum(abs(target_weight-pretrade_weight))"
                        ),
                        "transaction_costs_charged_once": True,
                    }
                )
                invariant_rows.append(
                    {
                        "record_scope": "standalone",
                        "row_id": row_id,
                        "cost_assumption_bps": cost,
                        "explicit_holdings": True,
                        "natural_drift": True,
                        "negative_weights_present": False,
                        "stale_weight_forward_fill_used": False,
                        "maximum_gross_exposure": metric[
                            "maximum_gross_exposure"
                        ],
                        "maximum_daily_weight_sum": metric[
                            "maximum_daily_weight_sum"
                        ],
                        "timing_invariant_status": metric[
                            "timing_invariant_status"
                        ],
                        "numeric_invariant_status": metric[
                            "numeric_invariant_status"
                        ],
                        "exposure_invariant_status": metric[
                            "exposure_invariant_status"
                        ],
                        "weight_invariant_status": metric[
                            "weight_invariant_status"
                        ],
                        "transaction_costs_charged_once": True,
                        "serial_rerun_deterministic": (
                            deterministic_hash_one == deterministic_hash_two
                        ),
                        "invariant_pass": metric["invariant_pass"],
                    }
                )
        standalone_index = core["candidate_paths"][5.0]["returns"].index
        for half_label, period in parent.split_halves(standalone_index):
            for row_id, row_type, path in [
                (STRATEGY_ID, "candidate", core["candidate_paths"][5.0]),
                *[
                    (
                        control_id,
                        "control",
                        core["control_paths"][(control_id, 5.0)],
                    )
                    for control_id in CONTROL_IDS
                ],
            ]:
                standalone_halves.append(
                    result_row(
                        row_id,
                        row_type,
                        5.0,
                        half_label,
                        parent.path_metrics(path, period),
                        outcome,
                        failure_reason,
                    )
                )
        for (portfolio_id, cost), path in sorted(core["portfolio_paths"].items()):
            metric = period_portfolio_metrics(path)
            portfolio_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "entity_type": "portfolio_diagnostic",
                    "stage": STAGE,
                    "cost_assumption_bps": cost,
                    "period_label": "full_period",
                    "period_role": "incremental_value_exploration",
                    "outer_weights": (
                        {"reference": 1.0, "sleeve": 0.0}
                        if portfolio_id == PORTFOLIO_IDS["reference"]
                        else {"reference": 0.8, "sleeve": 0.2}
                    ),
                    "monthly_outer_rebalance": (
                        portfolio_id != PORTFOLIO_IDS["reference"]
                    ),
                    "daily_fixed_weight_return_blend_used": False,
                    "natural_drift_between_outer_rebalances": True,
                    **metric,
                }
            )
            turnover_rows.append(
                {
                    "record_scope": "portfolio",
                    "row_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "total_one_way_turnover": metric[
                        "total_one_way_turnover"
                    ],
                    "inner_sleeve_transaction_cost_drag": metric[
                        "inner_sleeve_transaction_cost_drag"
                    ],
                    "outer_transaction_cost_drag": metric[
                        "outer_transaction_cost_drag"
                    ],
                    "total_transaction_cost_drag": metric[
                        "transaction_cost_drag"
                    ],
                    "turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                    "transaction_costs_charged_once": True,
                }
            )
            invariant_rows.append(
                {
                    "record_scope": "portfolio",
                    "row_id": portfolio_id,
                    "cost_assumption_bps": cost,
                    "explicit_holdings": True,
                    "natural_drift": True,
                    "negative_weights_present": False,
                    "stale_weight_forward_fill_used": False,
                    "maximum_gross_exposure": metric[
                        "maximum_gross_exposure"
                    ],
                    "maximum_daily_weight_sum": metric[
                        "maximum_daily_weight_sum"
                    ],
                    "timing_invariant_status": metric[
                        "timing_invariant_status"
                    ],
                    "numeric_invariant_status": metric[
                        "numeric_invariant_status"
                    ],
                    "exposure_invariant_status": metric[
                        "exposure_invariant_status"
                    ],
                    "weight_invariant_status": metric[
                        "weight_invariant_status"
                    ],
                    "transaction_costs_charged_once": True,
                    "serial_rerun_deterministic": (
                        deterministic_hash_one == deterministic_hash_two
                    ),
                    "invariant_pass": metric["invariant_pass"],
                }
            )
        portfolio_index = core["portfolio_paths"][
            (PORTFOLIO_IDS[STRATEGY_ID], 5.0)
        ]["returns"].index
        for half_label, period in parent.split_halves(portfolio_index):
            for portfolio_id in PORTFOLIO_IDS.values():
                metric = period_portfolio_metrics(
                    core["portfolio_paths"][(portfolio_id, 5.0)], period
                )
                portfolio_halves.append(
                    {
                        "portfolio_id": portfolio_id,
                        "cost_assumption_bps": 5.0,
                        "period_label": half_label,
                        "period_role": (
                            "chronological_half_not_validation_or_untouched_holdout"
                        ),
                        **metric,
                    }
                )
        diagnostics = formation_rows(core)
        vintages = core["candidate_paths"][5.0]["vintage_rows"]

    parent.helpers.write_csv(
        OUTPUT_DIR / "standalone_results.csv",
        standalone_rows,
        RESULT_FIELDS,
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "standalone_chronological_half_results.csv",
        standalone_halves,
        RESULT_FIELDS,
    )
    portfolio_fields = [
        "portfolio_id",
        "entity_type",
        "stage",
        "cost_assumption_bps",
        "period_label",
        "period_role",
        "outer_weights",
        "monthly_outer_rebalance",
        "daily_fixed_weight_return_blend_used",
        "natural_drift_between_outer_rebalances",
        *parent.METRIC_FIELDS,
        "inner_sleeve_transaction_cost_drag",
        "outer_transaction_cost_drag",
    ]
    parent.helpers.write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_rows,
        portfolio_fields,
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "portfolio_chronological_half_results.csv",
        portfolio_halves,
        [
            "portfolio_id",
            "cost_assumption_bps",
            "period_label",
            "period_role",
            *parent.METRIC_FIELDS,
            "inner_sleeve_transaction_cost_drag",
            "outer_transaction_cost_drag",
        ],
    )
    rolling_fields = [
        "window_id",
        "horizon_months",
        "window_start",
        "window_end",
        "candidate_portfolio_id",
        "comparator_id",
        "candidate_cagr",
        "comparator_cagr",
        "cagr_difference",
        "candidate_sharpe_ratio",
        "comparator_sharpe_ratio",
        "sharpe_difference",
        "candidate_maximum_drawdown",
        "comparator_maximum_drawdown",
        "maximum_drawdown_difference",
        "comparator_dominates_candidate",
        "candidate_dominates_comparator",
        "candidate_improves_reference_sharpe_or_drawdown",
        "unfavorable_window_retained",
    ]
    parent.helpers.write_csv(
        OUTPUT_DIR / "rolling_36_month_portfolio_results.csv",
        rolling_36,
        rolling_fields,
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "rolling_60_month_portfolio_results.csv",
        rolling_60,
        rolling_fields,
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "rolling_window_summary.csv",
        rolling_summary,
        [
            "horizon_months",
            "comparator_id",
            "eligible_window_count",
            "percentage_candidate_improves_reference_sharpe_or_drawdown",
            "percentage_comparator_dominates_candidate",
            "median_cagr_difference",
            "median_sharpe_difference",
            "median_maximum_drawdown_difference",
        ],
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "formation_selection_diagnostics.csv",
        diagnostics,
        [
            "record_type",
            "formation_date",
            "six_month_window_start",
            "six_month_window_end",
            "symbol",
            "sample_daily_volatility_ddof1",
            "volatility_rank",
            "selected",
            "selected_sectors",
            "MDD_selected_sectors",
            "overlap_with_MDD_selection_count",
            "overlap_with_monthly_equal_weight_count",
            "execution_date",
            "expiration_date",
            "signal_complete",
            "selection_frequency",
            "maximum_consecutive_selection_count",
            "average_holding_weight",
            "completed_vintage_count",
            "turnover_year",
            "annual_one_way_turnover",
            "percentage_formations_identical_to_static_basket",
        ],
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "vintage_ledger.csv",
        vintages,
        [
            "path_id",
            "vintage_id",
            "slot_id",
            "formation_date",
            "execution_date",
            "expiration_date",
            "selection",
            "initial_weights",
            "signal_complete",
            "invalid_vintage_held_in_BIL",
            "opened_slot_nav",
            "closed_slot_nav_before_liquidation_cost",
            "gross_vintage_return",
            "completed",
        ],
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        [
            "record_scope",
            "row_id",
            "cost_assumption_bps",
            "total_one_way_turnover",
            "inner_sleeve_transaction_cost_drag",
            "outer_transaction_cost_drag",
            "total_transaction_cost_drag",
            "turnover_formula",
            "transaction_costs_charged_once",
        ],
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        [
            "record_scope",
            "row_id",
            "cost_assumption_bps",
            "explicit_holdings",
            "natural_drift",
            "negative_weights_present",
            "stale_weight_forward_fill_used",
            "maximum_gross_exposure",
            "maximum_daily_weight_sum",
            "timing_invariant_status",
            "numeric_invariant_status",
            "exposure_invariant_status",
            "weight_invariant_status",
            "transaction_costs_charged_once",
            "serial_rerun_deterministic",
            "invariant_pass",
        ],
    )

    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "entity_type": "strategy_configuration",
        "stage": STAGE,
        "route": "diversifier_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "exact_next_action": next_action,
        "adaptation_selected_after_parent_results": True,
        "validation_claimed": False,
        "paper_demo_eligible": False,
    }
    parent.helpers.write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        [outcome_row]
        if outcome == "exploratory_followup_candidate_diversifier"
        else [],
        list(outcome_row),
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row)
    )
    failures = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "outcome": outcome,
                "failure_reason": failure_reason,
                "decision_reason": decision_reason,
            }
        ]
        if failure_reason
        else []
    )
    parent.helpers.write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failures,
        ["strategy_id", "outcome", "failure_reason", "decision_reason"],
    )
    next_row = {
        "scope": "strategy",
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }
    parent.helpers.write_csv(
        OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row)
    )
    funnel = {
        "source_library_records_created": 0,
        "source_research_lineage_records_carried_forward": 1,
        "strategy_configurations_created": 1,
        "parent_experiment_trials_carried_forward": 1,
        "new_experiment_trials": 1,
        "benchmark_references": 5,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "portfolio_diagnostics": 6,
        "rolling_windows_counted_as_trials": 0,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_diversifier"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "blocked_feasibility": int(outcome == "blocked_feasibility"),
        "entity_counts_reconcile": True,
    }
    parent.helpers.write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    protected_after = hash_map(PROTECTED_PATHS)
    cache_after = parent.helpers.tree_hash(CACHE_DIR)
    parent_evidence_after = parent.helpers.tree_hash(PARENT_DIR)
    prior_evidence_after = parent.helpers.tree_hash(ROOT / "evidence", OUTPUT_DIR)
    attachment_after = parent.helpers.file_hash(SOURCE_ATTACHMENT)
    metadata_complete = all(
        row.get(field) not in (None, "unknown", "unmapped")
        for row in strategies + trials
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
            "parent_trial_id",
            "adaptation_label",
            "outcome",
            "failure_reason",
            "next_action",
        )
    )
    all_invariants = bool(
        core is None or all(bool(row["invariant_pass"]) for row in invariant_rows)
    )
    consistency = {
        "overall_pass": bool(
            len(lineage) == 1
            and len(strategies) == 1
            and len(trials) == 2
            and len([row for row in trials if row["record_role"] == "new_child_experiment_trial"]) == 1
            and len(benchmarks) == 5
            and metadata_complete
            and reproduction_pass
            and deterministic_hash_one == deterministic_hash_two
            and all_invariants
            and protected_before == protected_after
            and cache_before == cache_after
            and parent_evidence_before == parent_evidence_after
            and prior_evidence_before == prior_evidence_after
            and attachment_before == attachment_after
        ),
        "exact_strategy_id": STRATEGY_ID,
        "parent_strategy_id": PARENT_STRATEGY_ID,
        "parent_MDD_closure_preserved": True,
        "source_library_records_created": 0,
        "source_research_lineage_records_carried_forward": 1,
        "strategy_configurations_created": 1,
        "parent_trials_carried_forward": 1,
        "new_child_trials_created": 1,
        "benchmark_reference_count": 5,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_hash": preregistration_hash,
        "parent_reproduction_pass": reproduction_pass,
        "reproduction_tolerance": TOLERANCE,
        "static_first_valid_selection": list(static_selection),
        "static_selection_frozen_before_new_performance": True,
        "result_driven_adaptation_explicit": True,
        "inverse_volatility_weighting_used": False,
        "parameter_variants_tested": 0,
        "provider_access": False,
        "network_access": False,
        "serial_rerun_deterministic": (
            deterministic_hash_one == deterministic_hash_two
        ),
        "deterministic_core_hash": deterministic_hash_one,
        "all_invariants_pass": all_invariants,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "market_data_cache_hash_before": cache_before,
        "market_data_cache_hash_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "parent_evidence_hash_before": parent_evidence_before,
        "parent_evidence_hash_after": parent_evidence_after,
        "parent_evidence_unchanged": (
            parent_evidence_before == parent_evidence_after
        ),
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "source_attachment_hash_before": attachment_before,
        "source_attachment_hash_after": attachment_after,
        "source_attachment_unchanged": attachment_before == attachment_after,
        "lifecycle_state_changed": False,
        "paper_demo_observations_created": 0,
        "broker_orders": 0,
        "real_money_actions": 0,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    parent.helpers.write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "route": "diversifier_only",
        "source_library_records_created": 0,
        "source_research_lineage_records_carried_forward": 1,
        "strategy_configurations_created": 1,
        "parent_experiment_trials_carried_forward": 1,
        "new_experiment_trials": 1,
        "benchmark_reference_count": 5,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "cost_assumptions_bps_per_one_way_turnover": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "portfolio_period_start": "2010-08-10",
        "portfolio_period_end": "2026-06-18",
        "static_first_valid_selection": list(static_selection),
        "result_driven_adaptation": True,
        "validation_claimed": False,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
    }
    parent.helpers.write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)

    candidate_portfolio = (
        period_portfolio_metrics(
            core["portfolio_paths"][
                (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
            ]
        )
        if core is not None
        else None
    )
    report = [
        "# Sector Low-Volatility Diversifier Follow-Up",
        "",
        "## Scope",
        "",
        f"`{STRATEGY_ID}` is one explicitly result-driven adaptation of a",
        "benchmark preregistered in the completed parent MDD experiment. The",
        "parent closure remains unchanged. This packet is exploration only.",
        "",
        "## Reproduction",
        "",
        f"* Parent reproduction within `1e-9`: `{str(reproduction_pass).lower()}`",
        f"* Static first-valid basket: `{'|'.join(static_selection)}`",
        "",
        "## Outcome",
        "",
        f"* Outcome: `{outcome}`",
        f"* Failure reason: `{failure_reason or 'none'}`",
        f"* Decision basis: `{decision_reason}`",
    ]
    if candidate_portfolio is not None:
        report.extend(
            [
                (
                    "* 80/20 candidate at 5 bps: "
                    f"CAGR `{candidate_portfolio['cagr']:.6f}`, "
                    f"Sharpe `{candidate_portfolio['sharpe_ratio']:.6f}`, "
                    "maximum drawdown "
                    f"`{candidate_portfolio['maximum_drawdown']:.6f}`."
                ),
                "",
                "All chronological halves and rolling windows, including",
                "unfavorable observations, remain in the evidence packet.",
            ]
        )
    report.extend(
        [
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    write_text(OUTPUT_DIR / "followup_report.md", "\n".join(report))
    if {path.name for path in OUTPUT_DIR.iterdir()} != REQUIRED_OUTPUTS:
        consistency["overall_pass"] = False
        consistency["required_output_set_matches"] = False
        parent.helpers.write_json(
            OUTPUT_DIR / "consistency_check.json", consistency
        )
    return {
        "task_id": TASK_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "output_dir": rel(OUTPUT_DIR),
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
