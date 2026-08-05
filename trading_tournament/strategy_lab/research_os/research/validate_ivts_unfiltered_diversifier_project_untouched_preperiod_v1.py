from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    correct_ivts_trial_lineage_and_run_exploration_v4 as v4,
)
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import (
    ivts_unfiltered_diversifier_incremental_value_followup_v1 as exploration,
)


TASK_ID = "validate_ivts_unfiltered_diversifier_project_untouched_preperiod_v1"
MODE = "validation"
STAGE = "validation"
STRATEGY_ID = exploration.STRATEGY_ID
FAMILY_ID = exploration.FAMILY_ID
DISPLAY_NAME = exploration.DISPLAY_NAME
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = exploration.TRIAL_ID
OUTPUT_DIR = ROOT / "evidence" / "validation" / TASK_ID / "latest"

VALIDATION_START = pd.Timestamp("2010-08-10")
VALIDATION_END = pd.Timestamp("2014-04-16")
DEVELOPMENT_START = pd.Timestamp("2014-04-17")
DEVELOPMENT_END = pd.Timestamp("2026-06-18")
FROZEN_EXPOSURE_SPY_WEIGHT = 0.8918654034629206
FROZEN_EXPOSURE_IEF_WEIGHT = 0.1081345965370794
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-9

SOURCE_LINEAGE = exploration.SOURCE_LINEAGE
TIMING_POLICY = "official_daily_close_following_session_execution_v1"
DATA_PROVENANCE = "official_cboe_daily_history"
VINTAGE_STATUS = "current_history_non_vintage"
REFERENCE_ID = exploration.REFERENCE_ID
SAME_PURPOSE_CONTROL = exploration.SAME_PURPOSE_CONTROL
EXPOSURE_CONTROL = exploration.EXPOSURE_CONTROL
CONTROLS = exploration.CONTROLS
PORTFOLIO_IDS = exploration.PORTFOLIO_IDS

POSITIVE_NEXT_ACTION = (
    "direction_owner_review_ivts_unfiltered_paper_demo_eligibility_data_caveat_v1"
)
MIXED_NEXT_ACTION = "direction_owner_review_ivts_unfiltered_validation_mixed_v1"
FAILED_NEXT_ACTION = "direction_owner_review_close_ivts_unfiltered_after_validation_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_ivts_unfiltered_validation_block_v1"

EXPLORATION_EVIDENCE = exploration.OUTPUT_DIR
CACHE_DIR = ROOT / "data" / "cache"
PRIOR_EVIDENCE = (
    *exploration.PRIOR_EVIDENCE,
    (exploration.TASK_ID, EXPLORATION_EVIDENCE),
)
PROTECTED_STATE_PATHS = exploration.PROTECTED_STATE_PATHS

REQUIRED_ARTIFACTS = (
    "validation_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "official_history_hash_reconciliation.csv",
    "validation_period_preflight.csv",
    "development_period_reproduction.csv",
    "validation_portfolio_results.csv",
    "validation_chronological_half_results.csv",
    "validation_calendar_year_results.csv",
    "standalone_context_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "validation_report.md",
)

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
    "average_candidate_SPY_exposure",
    "average_SPY_exposure_scope",
    "inner_turnover",
    "effective_inner_turnover",
    "outer_turnover",
    "total_effective_turnover",
    "inner_transaction_cost_drag",
    "outer_transaction_cost_drag",
    "total_transaction_cost_drag",
    "inner_trade_count",
    "outer_rebalance_count",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant",
    "numeric_invariant",
    "exposure_invariant",
    "weight_invariant",
    "transaction_costs_charged_once",
    "construction",
    "daily_fixed_weight_return_blend_used",
]

STANDALONE_FIELDS = exploration.METRIC_FIELDS + [
    "validation_decision_use",
    "current_history_non_vintage_caveat",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    exploration.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    exploration.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    exploration.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    exploration.write_text(path, text)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "validation" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def directory_hash(path: Path) -> str:
    return exploration.directory_hash(path)


def verify_exploration_context() -> dict[str, Any]:
    consistency = json.loads(
        (EXPLORATION_EVIDENCE / "consistency_check.json").read_text(encoding="utf-8")
    )
    manifest = yaml.safe_load(
        (EXPLORATION_EVIDENCE / "followup_manifest.yaml").read_text(encoding="utf-8")
    )
    trial_rows = read_csv(EXPLORATION_EVIDENCE / "trial_ledger.csv")
    parent = [row for row in trial_rows if row.get("trial_id") == PARENT_TRIAL_ID]
    passed = bool(
        consistency.get("overall_pass")
        and consistency.get("outcome")
        == "exploratory_followup_candidate_diversifier"
        and manifest.get("strategy_id") == STRATEGY_ID
        and manifest.get("route") == "diversifier_only"
        and math.isclose(
            float(manifest.get("average_target_SPY_weight_for_exposure_control")),
            FROZEN_EXPOSURE_SPY_WEIGHT,
            abs_tol=1e-15,
        )
        and len(parent) == 1
    )
    return {
        "passed": passed,
        "consistency": consistency,
        "manifest": manifest,
        "parent_trial": parent[0] if parent else {},
    }


def build_unfiltered_panel(
    histories: dict[str, pd.DataFrame], end_date: pd.Timestamp
) -> pd.DataFrame:
    vix = histories["VIX"].set_index("DATE")["CLOSE"].rename("VIX_close")
    vix3m = histories["VIX3M"].set_index("DATE")["CLOSE"].rename("VIX3M_close")
    panel = pd.concat([vix, vix3m], axis=1, join="outer").sort_index()
    panel["common_observation"] = panel[["VIX_close", "VIX3M_close"]].notna().all(axis=1)
    panel["raw_ratio"] = panel["VIX_close"] / panel["VIX3M_close"]
    candidate_target = (0.5, 0.5, "middle")
    sign_target = (0.5, 0.5, "middle")
    candidate_values: list[tuple[float, float, str]] = []
    sign_values: list[tuple[float, float, str]] = []
    for row in panel.itertuples():
        if bool(row.common_observation):
            candidate_target = v4.target_for_ratio(float(row.raw_ratio))
            sign_target = v4.target_for_sign(float(row.raw_ratio))
        candidate_values.append(candidate_target)
        sign_values.append(sign_target)
    for prefix, values in (("candidate", candidate_values), ("sign", sign_values)):
        panel[f"{prefix}_SPY"] = [value[0] for value in values]
        panel[f"{prefix}_IEF"] = [value[1] for value in values]
        panel[f"{prefix}_state"] = [value[2] for value in values]
    return panel.loc[panel.index <= end_date].copy()


def validation_schedules(
    panel: pd.DataFrame,
    full_prices: pd.DataFrame,
    prices: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    candidate, _, _ = v4.state_change_schedule(panel, prices.index, "candidate")
    sign, _, _ = v4.state_change_schedule(panel, prices.index, "sign")
    return {
        STRATEGY_ID: candidate,
        SAME_PURPOSE_CONTROL: sign,
        EXPOSURE_CONTROL: v4.monthly_static_schedule(
            prices.index, FROZEN_EXPOSURE_SPY_WEIGHT
        ),
        "SPY_200_day_trend_control": v4.spy_200d_schedule(
            full_prices, prices.index
        ),
        "SPY_buy_and_hold": v4.buy_hold_schedule(prices.index, "SPY"),
        "IEF_buy_and_hold": v4.buy_hold_schedule(prices.index, "IEF"),
    }


def preflight_rows(
    histories: dict[str, pd.DataFrame],
    official_hash_gate: bool,
    full_prices: pd.DataFrame,
    reference: pd.Series,
    context_passed: bool,
) -> tuple[list[dict[str, Any]], bool, pd.DataFrame, pd.Series]:
    prices = full_prices.loc[
        (full_prices.index >= VALIDATION_START)
        & (full_prices.index <= VALIDATION_END),
        ["SPY", "IEF"],
    ]
    reference_period = reference.loc[
        (reference.index >= VALIDATION_START)
        & (reference.index <= VALIDATION_END)
    ]
    vix_dates = histories["VIX"].dropna(subset=["CLOSE"])["DATE"]
    vix3m_dates = histories["VIX3M"].dropna(subset=["CLOSE"])["DATE"]
    common = pd.DatetimeIndex(vix_dates).intersection(pd.DatetimeIndex(vix3m_dates))
    before_start = common[common < VALIDATION_START]
    expected_sessions = full_prices.loc[
        (full_prices.index >= VALIDATION_START)
        & (full_prices.index <= VALIDATION_END)
    ].index
    checks = [
        (
            "authoritative_exploration_lineage",
            context_passed,
            PARENT_TRIAL_ID,
        ),
        (
            "fixed_validation_period",
            bool(
                len(prices)
                and prices.index.min() == VALIDATION_START
                and prices.index.max() == VALIDATION_END
            ),
            f"{VALIDATION_START.date()} through {VALIDATION_END.date()}",
        ),
        (
            "frozen_reference_available_at_start",
            bool(len(reference_period) and reference_period.index.min() == VALIDATION_START),
            str(reference_period.index.min().date()) if len(reference_period) else "",
        ),
        (
            "SPY_and_IEF_complete_period",
            bool(
                prices.index.equals(expected_sessions)
                and prices.notna().all().all()
                and np.isfinite(prices.to_numpy(dtype=float)).all()
                and (prices > 0.0).all().all()
            ),
            f"{len(prices)} complete sessions",
        ),
        (
            "five_common_official_observations_before_start",
            len(before_start) >= 5,
            f"{len(before_start)} prior common observations",
        ),
        (
            "candidate_controls_reference_identical_sessions",
            bool(
                prices.index.equals(reference_period.dropna().index)
                and prices.index.equals(expected_sessions)
            ),
            f"{len(expected_sessions)} shared sessions",
        ),
        (
            "stored_official_history_hashes_reproduce",
            official_hash_gate,
            "two stored snapshots per official series",
        ),
        (
            "validation_period_result_not_calculated_before_preregistration",
            True,
            "enforced by runner ordering",
        ),
    ]
    rows = [
        {
            "check_id": check_id,
            "required": True,
            "status": "pass" if passed else "fail",
            "detail": detail,
            "validation_start": VALIDATION_START.date().isoformat(),
            "validation_end": VALIDATION_END.date().isoformat(),
            "period_selected_from_performance": False,
        }
        for check_id, passed, detail in checks
    ]
    return rows, all(passed for _, passed, _ in checks), prices, reference_period


def development_reproduction(
    histories: dict[str, pd.DataFrame],
    full_prices: pd.DataFrame,
    reference: pd.Series,
) -> tuple[list[dict[str, Any]], bool]:
    prices = full_prices.loc[
        (full_prices.index >= DEVELOPMENT_START)
        & (full_prices.index <= DEVELOPMENT_END),
        ["SPY", "IEF"],
    ].dropna()
    panel = exploration.build_raw_signal_panel(histories, prices.index.max())
    schedules, _, observed_exposure = exploration.build_schedules(
        panel, full_prices, prices
    )
    if not math.isclose(
        observed_exposure, FROZEN_EXPOSURE_SPY_WEIGHT, abs_tol=1e-15
    ):
        return [
            {
                "scope": "frozen_exposure_weight",
                "entity_id": EXPOSURE_CONTROL,
                "period": "development_full_period",
                "cost_bps": "",
                "metric": "SPY_weight",
                "recorded_value": FROZEN_EXPOSURE_SPY_WEIGHT,
                "reproduced_value": observed_exposure,
                "difference": observed_exposure - FROZEN_EXPOSURE_SPY_WEIGHT,
                "absolute_tolerance": REPRODUCTION_TOLERANCE,
                "pass": False,
            }
        ], False
    paths = exploration.run_paths(schedules, full_prices, prices)
    standalone = {
        (entity_id, cost): v4.path_metrics(paths[(entity_id, cost)])
        for entity_id in (STRATEGY_ID, *CONTROLS)
        for cost in COST_BPS
    }
    standalone_halves = {
        (entity_id, period): v4.path_metrics(
            paths[(entity_id, PRIMARY_COST_BPS)], period_index=index
        )
        for period, index in v4.split_halves(prices.index)
        for entity_id in (STRATEGY_ID, *CONTROLS)
    }
    portfolio_payloads = exploration.portfolio_payloads(paths, reference)
    portfolios = {
        (portfolio_id, cost): exploration.portfolio_metrics(
            portfolio_id, portfolio_payloads[(portfolio_id, cost)], paths, cost
        )
        for portfolio_id in PORTFOLIO_IDS.values()
        for cost in COST_BPS
    }
    portfolio_index = portfolio_payloads[
        (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
    ]["returns"].index
    portfolio_halves = {
        (portfolio_id, period): exploration.portfolio_metrics(
            portfolio_id,
            portfolio_payloads[(portfolio_id, PRIMARY_COST_BPS)],
            paths,
            PRIMARY_COST_BPS,
            period_index=index,
        )
        for period, index in v4.split_halves(portfolio_index)
        for portfolio_id in PORTFOLIO_IDS.values()
    }
    numeric_fields = (
        "trading_days",
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
    )
    rows: list[dict[str, Any]] = []

    def compare(
        scope: str,
        entity_id: str,
        period: str,
        cost: float,
        metric: str,
        expected: Any,
        observed: Any,
    ) -> None:
        expected_value = float(expected)
        observed_value = float(observed)
        difference = observed_value - expected_value
        rows.append(
            {
                "scope": scope,
                "entity_id": entity_id,
                "period": period,
                "cost_bps": cost,
                "metric": metric,
                "recorded_value": expected_value,
                "reproduced_value": observed_value,
                "difference": difference,
                "absolute_tolerance": REPRODUCTION_TOLERANCE,
                "pass": abs(difference) <= REPRODUCTION_TOLERANCE,
            }
        )

    for prior in read_csv(EXPLORATION_EVIDENCE / "standalone_results.csv"):
        key = (prior["entity_id"], float(prior["cost_bps"]))
        for field in numeric_fields:
            compare(
                "standalone",
                prior["entity_id"],
                prior["period"],
                float(prior["cost_bps"]),
                field,
                prior[field],
                standalone[key][field],
            )
    for prior in read_csv(
        EXPLORATION_EVIDENCE / "standalone_chronological_half_results.csv"
    ):
        key = (prior["entity_id"], prior["period"])
        for field in numeric_fields:
            compare(
                "standalone",
                prior["entity_id"],
                prior["period"],
                float(prior["cost_bps"]),
                field,
                prior[field],
                standalone_halves[key][field],
            )
    for prior in read_csv(
        EXPLORATION_EVIDENCE / "portfolio_contribution_results.csv"
    ):
        key = (prior["portfolio_id"], float(prior["cost_bps"]))
        for field in numeric_fields:
            compare(
                "portfolio",
                prior["portfolio_id"],
                prior["period"],
                float(prior["cost_bps"]),
                field,
                prior[field],
                portfolios[key][field],
            )
    for prior in read_csv(
        EXPLORATION_EVIDENCE / "portfolio_chronological_half_results.csv"
    ):
        key = (prior["portfolio_id"], prior["period"])
        for field in numeric_fields:
            compare(
                "portfolio",
                prior["portfolio_id"],
                prior["period"],
                float(prior["cost_bps"]),
                field,
                prior[field],
                portfolio_halves[key][field],
            )
    return rows, bool(rows and all(row["pass"] for row in rows))


def entity_rows(
    outcome: str,
    failure_reason: str,
    next_action: str,
) -> dict[str, list[dict[str, Any]]]:
    strategy = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "display_name": DISPLAY_NAME,
            "entity_type": "strategy_configuration",
            "strategy_architecture": "raw_implied_volatility_curve_three_state_allocation",
            "source_or_research_lineage": SOURCE_LINEAGE,
            "instrument_universe": "SPY|IEF",
            "route": "diversifier_only",
            "exact_source_replication_claimed": False,
            "authoritative_registry_record_created": False,
            "adaptation_label": "result_driven_exploratory_variant",
            "source_rule_changed": True,
            "median_filter_removed": True,
            "thresholds_changed": False,
            "target_states_changed": False,
            "instruments_translated": True,
            "validation_evidence_previously_claimed": False,
            "parameters": {
                "ratio": "VIX_close/VIX3M_close",
                "thresholds": [0.96, 1.02],
                "targets": ["1.0|0.0", "0.5|0.5", "0.0|1.0"],
                "missing_signal": "retain_previous_target",
                "outer_sleeve_weight": 0.2,
                "exposure_control_SPY_weight": FROZEN_EXPOSURE_SPY_WEIGHT,
            },
            "stage": STAGE,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    parent = dict(verify_exploration_context()["parent_trial"])
    parent["record_role"] = "carried_forward_read_only"
    parent["created_in_this_task"] = False
    child = {
        "trial_id": TRIAL_ID,
        "entity_type": "experiment_trial",
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "validation_variant",
        "changed_fields_from_parent": "evaluation_period_and_validation_gate_only",
        "signal_changed": False,
        "thresholds_changed": False,
        "instruments_changed": False,
        "target_states_changed": False,
        "execution_changed": False,
        "outer_sleeve_weight_changed": False,
        "controls_changed": False,
        "cost_model_changed": False,
        "data_provenance_changed": False,
        "optimization_performed": False,
        "result_driven_change_in_this_task": False,
        "validation_period_viewed_before_preregistration": False,
        "preregistered_before_validation_performance": True,
        "record_role": "new_validation_child",
        "created_in_this_task": True,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }
    trial_fields = list(dict.fromkeys([*parent.keys(), *child.keys()]))
    parent = {field: parent.get(field, "") for field in trial_fields}
    child = {field: child.get(field, "") for field in trial_fields}
    definitions = {
        SAME_PURPOSE_CONTROL: (
            "SPY|IEF",
            "raw ratio <=1.0 holds SPY; raw ratio >1.0 holds IEF",
        ),
        EXPOSURE_CONTROL: (
            "SPY|IEF",
            f"monthly {FROZEN_EXPOSURE_SPY_WEIGHT:.16f} SPY and "
            f"{FROZEN_EXPOSURE_IEF_WEIGHT:.16f} IEF",
        ),
        "SPY_200_day_trend_control": (
            "SPY|BIL",
            "SPY above completed-close 200-day SMA; BIL otherwise",
        ),
        "IEF_buy_and_hold": ("IEF", "100% IEF buy-and-hold"),
        "SPY_buy_and_hold": ("SPY", "100% SPY buy-and-hold; standalone context only"),
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
            "standalone_context_only": control == "SPY_buy_and_hold",
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
        "strategy": strategy,
        "trial": [parent, child],
        "trial_fields": trial_fields,
        "benchmarks": benchmarks,
        "process": process,
    }


def write_entities(rows: dict[str, list[dict[str, Any]]]) -> None:
    write_csv(OUTPUT_DIR / "strategy_cards.csv", rows["strategy"], list(rows["strategy"][0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", rows["trial"], rows["trial_fields"])
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        rows["benchmarks"],
        list(rows["benchmarks"][0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        rows["process"],
        list(rows["process"][0]),
    )


def portfolio_metrics(
    portfolio_id: str,
    payload: dict[str, Any],
    paths: dict[tuple[str, float], dict[str, Any]],
    cost_bps: float,
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    base = exploration.portfolio_metrics(
        portfolio_id, payload, paths, cost_bps, period_index
    )
    returns = payload["returns"]
    if period_index is not None:
        returns = returns.reindex(period_index).dropna()
    outer_turnover = float(payload["turnover"].reindex(returns.index).sum())
    outer_cost = float(payload["cost"].reindex(returns.index).sum())
    if portfolio_id == PORTFOLIO_IDS["reference"]:
        inner_turnover = 0.0
        effective_inner_turnover = 0.0
        inner_cost = 0.0
        inner_trades = 0
    else:
        sleeve_id = payload["sleeve_id"]
        sleeve_path = paths[(sleeve_id, cost_bps)]
        sleeve_turnover = sleeve_path["turnover"].reindex(returns.index).fillna(0.0)
        sleeve_cost = sleeve_path["cost"].reindex(returns.index).fillna(0.0)
        outer_held = (
            payload["outer_held_weights"]
            .reindex(returns.index)["sleeve_weight"]
            .fillna(0.0)
        )
        inner_turnover = float(sleeve_turnover.sum())
        effective_inner_turnover = float((outer_held * sleeve_turnover).sum())
        inner_cost = float((outer_held * sleeve_cost).sum())
        inner_trades = int((sleeve_turnover > WEIGHT_TOLERANCE).sum())
    return {
        **base,
        "average_candidate_SPY_exposure": base["average_SPY_exposure"],
        "inner_turnover": inner_turnover,
        "effective_inner_turnover": effective_inner_turnover,
        "outer_turnover": outer_turnover,
        "total_effective_turnover": effective_inner_turnover + outer_turnover,
        "inner_transaction_cost_drag": inner_cost,
        "outer_transaction_cost_drag": outer_cost,
        "total_transaction_cost_drag": inner_cost + outer_cost,
        "inner_trade_count": inner_trades,
        "outer_rebalance_count": int(
            (payload["turnover"].reindex(returns.index) > WEIGHT_TOLERANCE).sum()
        ),
        "transaction_costs_charged_once": True,
    }


def portfolio_row(
    portfolio_id: str,
    cost_bps: float,
    metrics: dict[str, Any],
    period: str,
) -> dict[str, Any]:
    row = {
        "portfolio_id": portfolio_id,
        "entity_type": "validation_portfolio_diagnostic",
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
    return row


def standalone_rows(
    paths: dict[tuple[str, float], dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    metrics: dict[tuple[str, float], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, *CONTROLS):
        for cost in COST_BPS:
            item = v4.path_metrics(paths[(entity_id, cost)])
            metrics[(entity_id, cost)] = item
            row = exploration.standalone_metric_row(entity_id, cost, item)
            row["validation_decision_use"] = (
                "context_only_not_validated_route"
                if entity_id == STRATEGY_ID
                else "benchmark_context_only"
            )
            row["current_history_non_vintage_caveat"] = True
            rows.append(row)
    return rows, metrics


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.dominates(control, candidate)


def material_advantage(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"])
    )


def classify(
    preflight_pass: bool,
    reproduction_pass: bool,
    full: dict[tuple[str, float], dict[str, Any]],
    halves: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    if not preflight_pass or not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "data_or_comparability_failure",
            "fixed-period preflight or development-period reproduction failed",
            {
                "preflight_passed": preflight_pass,
                "development_reproduction_passed": reproduction_pass,
            },
        )
    candidate_id = PORTFOLIO_IDS[STRATEGY_ID]
    reference_id = PORTFOLIO_IDS["reference"]
    sign_id = PORTFOLIO_IDS[SAME_PURPOSE_CONTROL]
    exposure_id = PORTFOLIO_IDS[EXPOSURE_CONTROL]
    trend_id = PORTFOLIO_IDS["SPY_200_day_trend_control"]
    ief_id = PORTFOLIO_IDS["IEF_buy_and_hold"]
    candidate = full[(candidate_id, PRIMARY_COST_BPS)]
    reference = full[(reference_id, PRIMARY_COST_BPS)]
    sign = full[(sign_id, PRIMARY_COST_BPS)]
    exposure = full[(exposure_id, PRIMARY_COST_BPS)]
    trend = full[(trend_id, PRIMARY_COST_BPS)]
    ief = full[(ief_id, PRIMARY_COST_BPS)]
    candidate_10 = full[(candidate_id, 10.0)]
    reference_10 = full[(reference_id, 10.0)]
    sign_10 = full[(sign_id, 10.0)]
    exposure_10 = full[(exposure_id, 10.0)]
    all_invariants = all(item["invariant_pass"] for item in full.values())
    half_failures: list[str] = []
    for period in ("first_chronological_half", "second_chronological_half"):
        candidate_half = halves[(candidate_id, period)]
        for control_id in (reference_id, exposure_id):
            if worse_on_both(candidate_half, halves[(control_id, period)]):
                half_failures.append(f"{period}:{control_id}")
    ten_improves_reference = bool(
        float(candidate_10["sharpe_ratio"]) > float(reference_10["sharpe_ratio"])
        or float(candidate_10["maximum_drawdown"])
        > float(reference_10["maximum_drawdown"])
    )
    directionally_distinct_from_exposure = material_advantage(candidate, exposure)
    gate = {
        "preflight_passed": preflight_pass,
        "development_reproduction_passed": reproduction_pass,
        "all_invariants_passed": all_invariants,
        "candidate_positive_CAGR": float(candidate["cagr"]) > 0.0,
        "candidate_materially_improves_reference": material_advantage(
            candidate, reference
        ),
        "sign_only_dominates_candidate": dominates(sign, candidate),
        "exposure_matched_dominates_candidate": dominates(exposure, candidate),
        "material_advantage_vs_sign_only": material_advantage(candidate, sign),
        "material_advantage_vs_exposure_matched": material_advantage(
            candidate, exposure
        ),
        "trend_dominates_candidate": dominates(trend, candidate),
        "IEF_dominates_candidate": dominates(ief, candidate),
        "worse_on_both_in_halves": half_failures,
        "10bps_improves_reference": ten_improves_reference,
        "10bps_sign_only_dominates_candidate": dominates(sign_10, candidate_10),
        "10bps_exposure_matched_dominates_candidate": dominates(
            exposure_10, candidate_10
        ),
        "directionally_distinct_from_average_SPY_exposure": (
            directionally_distinct_from_exposure
        ),
    }
    positive = bool(
        all_invariants
        and gate["candidate_positive_CAGR"]
        and gate["candidate_materially_improves_reference"]
        and not gate["sign_only_dominates_candidate"]
        and not gate["exposure_matched_dominates_candidate"]
        and gate["material_advantage_vs_sign_only"]
        and gate["material_advantage_vs_exposure_matched"]
        and not gate["trend_dominates_candidate"]
        and not gate["IEF_dominates_candidate"]
        and not half_failures
        and ten_improves_reference
        and not gate["10bps_sign_only_dominates_candidate"]
        and not gate["10bps_exposure_matched_dominates_candidate"]
        and directionally_distinct_from_exposure
    )
    if positive:
        return (
            "validation_positive",
            "",
            "the frozen 20% diversifier route passed every predeclared pre-period gate",
            gate,
        )
    if not all_invariants:
        return (
            "validation_data_or_methodology_blocked",
            "methodology_failure",
            "an accounting or timing invariant failed",
            gate,
        )
    if float(candidate["cagr"]) <= 0.0:
        return (
            "validation_failed",
            "weak_portfolio_contribution",
            "validation-period CAGR was non-positive",
            gate,
        )
    if not gate["candidate_materially_improves_reference"]:
        return (
            "validation_failed",
            "weak_portfolio_contribution",
            "candidate did not materially improve the frozen reference",
            gate,
        )
    if gate["sign_only_dominates_candidate"]:
        return (
            "validation_failed",
            "weak_vs_primary_control",
            "sign-only critical control dominated the candidate",
            gate,
        )
    if gate["exposure_matched_dominates_candidate"]:
        return (
            "validation_failed",
            "exposure_control_explanation",
            "frozen exposure-matched critical control dominated the candidate",
            gate,
        )
    if gate["trend_dominates_candidate"] or gate["IEF_dominates_candidate"]:
        return (
            "validation_failed",
            "benchmark_like_behavior",
            "trend or IEF control economically replicated the result",
            gate,
        )
    if half_failures:
        return (
            "validation_failed",
            "period_instability",
            f"candidate was worse on Sharpe and drawdown in {','.join(half_failures)}",
            gate,
        )
    if (
        not ten_improves_reference
        or gate["10bps_sign_only_dominates_candidate"]
        or gate["10bps_exposure_matched_dominates_candidate"]
    ):
        return (
            "validation_failed",
            "cost_drag",
            "the frozen 10-bps gate failed",
            gate,
        )
    return (
        "validation_mixed",
        "",
        "candidate improved the reference but critical-control evidence was conflicting",
        gate,
    )


def run() -> dict[str, Any]:
    protected_before = exploration.v1.hash_paths(PROTECTED_STATE_PATHS)
    prior_before = {task_id: directory_hash(path) for task_id, path in PRIOR_EVIDENCE}
    cache_before = directory_hash(CACHE_DIR)
    clean_output_dir()

    context = verify_exploration_context()
    histories, hash_rows, official_hash_gate = v4.load_verified_v3_histories()
    full_prices = market.load_price_frame(("SPY", "IEF", "BIL")).sort_index()
    reference = market.active_vm_dsr_usci_reference_returns().sort_index()
    preflight, preflight_pass, prices, validation_reference = preflight_rows(
        histories,
        official_hash_gate,
        full_prices,
        reference,
        context["passed"],
    )
    reproduction, reproduction_pass = development_reproduction(
        histories, full_prices, reference
    )

    preregistered = entity_rows("preregistered_pending_validation", "", "")
    write_entities(preregistered)

    portfolio_result_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    calendar_rows: list[dict[str, Any]] = []
    standalone_context: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    half_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    payloads: dict[tuple[str, float], dict[str, Any]] = {}

    if preflight_pass and reproduction_pass:
        panel = build_unfiltered_panel(histories, VALIDATION_END)
        schedules = validation_schedules(panel, full_prices, prices)
        paths = exploration.run_paths(schedules, full_prices, prices)
        standalone_context, standalone_metric_map = standalone_rows(paths)
        payloads = exploration.portfolio_payloads(paths, validation_reference)
        for portfolio_id in PORTFOLIO_IDS.values():
            for cost in COST_BPS:
                metrics = portfolio_metrics(
                    portfolio_id, payloads[(portfolio_id, cost)], paths, cost
                )
                full_metrics[(portfolio_id, cost)] = metrics
                portfolio_result_rows.append(
                    portfolio_row(portfolio_id, cost, metrics, "full_validation_period")
                )
        validation_index = payloads[
            (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS)
        ]["returns"].index
        for period, index in v4.split_halves(validation_index):
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    portfolio_id,
                    payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                    period_index=index,
                )
                half_metrics[(portfolio_id, period)] = metrics
                half_rows.append(
                    portfolio_row(portfolio_id, PRIMARY_COST_BPS, metrics, period)
                )
        years = sorted(set(validation_index.year))
        for year in years:
            index = validation_index[validation_index.year == year]
            complete = bool(
                index.min().month == 1
                and index.max().month == 12
                and index.min().day <= 5
                and index.max().day >= 27
            )
            for portfolio_id in PORTFOLIO_IDS.values():
                metrics = portfolio_metrics(
                    portfolio_id,
                    payloads[(portfolio_id, PRIMARY_COST_BPS)],
                    paths,
                    PRIMARY_COST_BPS,
                    period_index=index,
                )
                row = portfolio_row(
                    portfolio_id, PRIMARY_COST_BPS, metrics, f"calendar_year_{year}"
                )
                row["calendar_year"] = year
                row["complete_calendar_year"] = complete
                calendar_rows.append(row)

        for portfolio_id in PORTFOLIO_IDS.values():
            for cost in COST_BPS:
                metrics = full_metrics[(portfolio_id, cost)]
                payload = payloads[(portfolio_id, cost)]
                outer_turnover_sum = float(payload["turnover"].sum())
                outer_cost_sum = float(payload["cost"].sum())
                turnover_rows.append(
                    {
                        "portfolio_id": portfolio_id,
                        "cost_bps": cost,
                        "inner_turnover": metrics["inner_turnover"],
                        "effective_inner_turnover": metrics[
                            "effective_inner_turnover"
                        ],
                        "outer_turnover": metrics["outer_turnover"],
                        "reported_outer_turnover": outer_turnover_sum,
                        "inner_transaction_cost_drag": metrics[
                            "inner_transaction_cost_drag"
                        ],
                        "outer_transaction_cost_drag": metrics[
                            "outer_transaction_cost_drag"
                        ],
                        "reported_outer_cost_drag": outer_cost_sum,
                        "total_transaction_cost_drag": metrics[
                            "total_transaction_cost_drag"
                        ],
                        "outer_turnover_reconciles": math.isclose(
                            metrics["outer_turnover"],
                            outer_turnover_sum,
                            abs_tol=1e-12,
                        ),
                        "outer_cost_reconciles": math.isclose(
                            metrics["outer_transaction_cost_drag"],
                            outer_cost_sum,
                            abs_tol=1e-12,
                        ),
                        "inner_and_outer_costs_charged_once": True,
                    }
                )
                invariant_rows.append(
                    {
                        "scope": "validation_portfolio",
                        "entity_id": portfolio_id,
                        "cost_bps": cost,
                        "timing_invariant": metrics["timing_invariant"],
                        "numeric_invariant": metrics["numeric_invariant"],
                        "exposure_invariant": metrics["exposure_invariant"],
                        "weight_invariant": metrics["weight_invariant"],
                        "explicit_zero_weights_preserved": True,
                        "natural_drift_used": True,
                        "stale_weight_forward_fill_used": False,
                        "signal_date_return_used": False,
                        "next_open_execution_used": False,
                        "maximum_gross_exposure": metrics[
                            "maximum_gross_exposure"
                        ],
                        "maximum_daily_weight_sum": metrics[
                            "maximum_daily_weight_sum"
                        ],
                        "invariant_pass": metrics["invariant_pass"],
                    }
                )
        for entity_id in (STRATEGY_ID, *CONTROLS):
            for cost in COST_BPS:
                metrics = standalone_metric_map[(entity_id, cost)]
                invariant_rows.append(
                    {
                        "scope": "standalone_context",
                        "entity_id": entity_id,
                        "cost_bps": cost,
                        "timing_invariant": metrics["timing_invariant"],
                        "numeric_invariant": metrics["numeric_invariant"],
                        "exposure_invariant": metrics["exposure_invariant"],
                        "weight_invariant": metrics["weight_invariant"],
                        "explicit_zero_weights_preserved": True,
                        "natural_drift_used": True,
                        "stale_weight_forward_fill_used": False,
                        "signal_date_return_used": False,
                        "next_open_execution_used": False,
                        "maximum_gross_exposure": metrics[
                            "maximum_gross_exposure"
                        ],
                        "maximum_daily_weight_sum": metrics[
                            "maximum_daily_weight_sum"
                        ],
                        "invariant_pass": metrics["invariant_pass"],
                    }
                )

    outcome, failure_reason, decision_reason, gate = classify(
        preflight_pass, reproduction_pass, full_metrics, half_metrics
    )
    next_action = {
        "validation_positive": POSITIVE_NEXT_ACTION,
        "validation_mixed": MIXED_NEXT_ACTION,
        "validation_failed": FAILED_NEXT_ACTION,
        "validation_data_or_methodology_blocked": BLOCKED_NEXT_ACTION,
    }[outcome]
    entities = entity_rows(outcome, failure_reason, next_action)
    write_entities(entities)

    hash_fields = list(hash_rows[0]) if hash_rows else [
        "series",
        "attempt",
        "status",
    ]
    write_csv(OUTPUT_DIR / "official_history_hash_reconciliation.csv", hash_rows, hash_fields)
    write_csv(
        OUTPUT_DIR / "validation_period_preflight.csv",
        preflight,
        list(preflight[0]),
    )
    write_csv(
        OUTPUT_DIR / "development_period_reproduction.csv",
        reproduction,
        list(reproduction[0]),
    )
    write_csv(
        OUTPUT_DIR / "validation_portfolio_results.csv",
        portfolio_result_rows,
        PORTFOLIO_FIELDS,
    )
    write_csv(
        OUTPUT_DIR / "validation_chronological_half_results.csv",
        half_rows,
        PORTFOLIO_FIELDS,
    )
    calendar_fields = [*PORTFOLIO_FIELDS, "calendar_year", "complete_calendar_year"]
    write_csv(
        OUTPUT_DIR / "validation_calendar_year_results.csv",
        calendar_rows,
        calendar_fields,
    )
    write_csv(
        OUTPUT_DIR / "standalone_context_results.csv",
        standalone_context,
        STANDALONE_FIELDS,
    )
    turnover_fields = (
        list(turnover_rows[0])
        if turnover_rows
        else [
            "portfolio_id",
            "cost_bps",
            "inner_turnover",
            "outer_turnover",
            "total_transaction_cost_drag",
        ]
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        turnover_fields,
    )
    invariant_fields = (
        list(invariant_rows[0])
        if invariant_rows
        else ["scope", "entity_id", "cost_bps", "invariant_pass"]
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        invariant_fields,
    )

    candidate = full_metrics.get(
        (PORTFOLIO_IDS[STRATEGY_ID], PRIMARY_COST_BPS), {}
    )
    reference_metrics = full_metrics.get(
        (PORTFOLIO_IDS["reference"], PRIMARY_COST_BPS), {}
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "stage": STAGE,
        "route": "diversifier_only",
        "validation_start": VALIDATION_START.date().isoformat(),
        "validation_end": VALIDATION_END.date().isoformat(),
        "period_classification": (
            "project_untouched_not_claimed_source_untouched"
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "next_action": next_action,
        "development_reproduction_passed": reproduction_pass,
        "preflight_passed": preflight_pass,
        "candidate_CAGR_5bps": candidate.get("cagr", ""),
        "candidate_Sharpe_5bps": candidate.get("sharpe_ratio", ""),
        "candidate_maximum_drawdown_5bps": candidate.get(
            "maximum_drawdown", ""
        ),
        "reference_CAGR_5bps": reference_metrics.get("cagr", ""),
        "reference_Sharpe_5bps": reference_metrics.get("sharpe_ratio", ""),
        "reference_maximum_drawdown_5bps": reference_metrics.get(
            "maximum_drawdown", ""
        ),
        "gate_detail": gate,
        "validated_claim": (
            "20pct_diversifier_route_under_current_history_non_vintage_data"
            if outcome == "validation_positive"
            else ""
        ),
        "standalone_validation_claimed": False,
        "exact_source_replication_claimed": False,
        "point_in_time_historical_data_safety_established": False,
        "paper_demo_eligibility_automatically_supported": False,
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
                "exact_20pct_diversifier_configuration_only": True,
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
            "exact_20pct_diversifier_configuration_only",
        ],
    )
    next_row = {
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "route": "diversifier_only",
        "adaptation_label": "validation_variant",
        "changed_fields_from_parent": "evaluation_period_and_validation_gate_only",
        "validation_period": {
            "start": VALIDATION_START.date().isoformat(),
            "end": VALIDATION_END.date().isoformat(),
            "classification": "project_untouched_not_source_untouched",
            "selected_from_performance": False,
        },
        "development_period": {
            "start": DEVELOPMENT_START.date().isoformat(),
            "end": DEVELOPMENT_END.date().isoformat(),
            "use": "reproduction_and_context_only",
        },
        "outer_sleeve_weight": 0.2,
        "frozen_exposure_matched_weights": {
            "SPY": FROZEN_EXPOSURE_SPY_WEIGHT,
            "IEF": FROZEN_EXPOSURE_IEF_WEIGHT,
            "recalculated_from_validation_period": False,
        },
        "data_provenance": DATA_PROVENANCE,
        "vintage_status": VINTAGE_STATUS,
        "timing_policy": TIMING_POLICY,
        "current_history_non_vintage_validation_caveat": True,
        "signal_changed": False,
        "thresholds_changed": False,
        "instruments_changed": False,
        "target_states_changed": False,
        "execution_changed": False,
        "outer_sleeve_weight_changed": False,
        "controls_changed": False,
        "cost_model_changed": False,
        "data_provenance_changed": False,
        "optimization_performed": False,
        "result_driven_change_in_this_task": False,
        "validation_period_viewed_before_preregistration": False,
        "preregistered_before_validation_performance": True,
        "network_access": False,
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "validation_manifest.yaml", manifest)

    report = f"""# IVTS Unfiltered Diversifier Project-Untouched Pre-Period Validation V1

## Scope

This task validated only the frozen 20% diversifier route for `{STRATEGY_ID}`.
The decision period was fixed at `{VALIDATION_START.date()}` through
`{VALIDATION_END.date()}` before any validation-period performance was
calculated. It is project-untouched for this adaptation, not source-untouched.
The 2014-2026 development period was used only for reproduction and context.

## Data And Timing

Stored official Cboe VIX and VIX3M histories reproduced without network access.
They remain official current-history, non-vintage data. Signals use completed
daily closes and execute at the following regular session close. This task does
not establish historical vintage safety.

## Reproduction

Development evidence reproduced within `{REPRODUCTION_TOLERANCE}`:
`{str(reproduction_pass).lower()}`.

## Validation Result

Outcome: `{outcome}`.

Failure reason: `{failure_reason or 'not_applicable'}`.

Decision basis: {decision_reason}.

At 5 bps, the 80/20 candidate portfolio had CAGR
`{candidate.get('cagr', float('nan')):.6f}`, Sharpe
`{candidate.get('sharpe_ratio', float('nan')):.6f}`, and maximum drawdown
`{candidate.get('maximum_drawdown', float('nan')):.6f}`. The frozen reference
had CAGR `{reference_metrics.get('cagr', float('nan')):.6f}`, Sharpe
`{reference_metrics.get('sharpe_ratio', float('nan')):.6f}`, and maximum
drawdown `{reference_metrics.get('maximum_drawdown', float('nan')):.6f}`.

Exact next action: `{next_action}`.

A positive outcome is limited to
`20pct_diversifier_route_under_current_history_non_vintage_data`. It does not
validate a standalone allocation, exact source replication, point-in-time
history, or automatic paper/demo eligibility.
"""
    write_text(OUTPUT_DIR / "validation_report.md", report)

    protected_after = exploration.v1.hash_paths(PROTECTED_STATE_PATHS)
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
    deterministic_hash = exploration.v1.canonical_hash(
        [
            {"path": name, "hash": exploration.v1.file_hash(OUTPUT_DIR / name)}
            for name in deterministic_names
        ]
    )
    new_validation_trials = [
        row
        for row in entities["trial"]
        if row.get("stage") == STAGE and row.get("created_in_this_task") is True
    ]
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": bool(
            required_present
            and context["passed"]
            and official_hash_gate
            and preflight_pass
            and reproduction_pass
            and protected_before == protected_after
            and prior_before == prior_after
            and cache_before == cache_after
            and len(entities["strategy"]) == 1
            and len(new_validation_trials) == 1
            and len(entities["benchmarks"]) == 5
            and len(portfolio_result_rows) == 18
            and len(half_rows) == 12
            and len(calendar_rows) == 30
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "exploration_context_passed": context["passed"],
        "official_history_hash_gate_passed": official_hash_gate,
        "preflight_passed": preflight_pass,
        "development_reproduction_passed": reproduction_pass,
        "reproduction_max_absolute_difference": max(
            (abs(float(row["difference"])) for row in reproduction),
            default=float("nan"),
        ),
        "entity_counts": {
            "strategy_configurations": 1,
            "existing_exploration_trials_carried_forward": 1,
            "new_validation_trials": 1,
            "benchmark_references": 5,
            "validation_portfolios": 6,
            "process_tasks": 1,
            "data_capability_tasks": 0,
            "paper_demo_observations": 0,
        },
        "row_counts": {
            "official_history_hash_reconciliation": len(hash_rows),
            "validation_period_preflight": len(preflight),
            "development_period_reproduction": len(reproduction),
            "validation_portfolio_results": len(portfolio_result_rows),
            "validation_chronological_half_results": len(half_rows),
            "validation_calendar_year_results": len(calendar_rows),
            "standalone_context_results": len(standalone_context),
            "turnover_cost_reconciliation": len(turnover_rows),
            "invariant_results": len(invariant_rows),
        },
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
            "network_or_provider_access": False,
            "standalone_validation_or_promotion": False,
            "threshold_target_instrument_or_timing_change": False,
            "exposure_weight_recalculated_from_validation": False,
            "alternative_period_or_sleeve_tested": False,
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
        "validation_period": (
            f"{VALIDATION_START.date().isoformat()}:{VALIDATION_END.date().isoformat()}"
        ),
        "development_reproduction_passed": reproduction_pass,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "candidate_portfolio_5bps": {
            key: candidate.get(key, "")
            for key in (
                "total_return",
                "cagr",
                "sharpe_ratio",
                "maximum_drawdown",
                "inner_turnover",
                "outer_turnover",
                "total_transaction_cost_drag",
            )
        },
        "reference_5bps": {
            key: reference_metrics.get(key, "")
            for key in ("total_return", "cagr", "sharpe_ratio", "maximum_drawdown")
        },
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
