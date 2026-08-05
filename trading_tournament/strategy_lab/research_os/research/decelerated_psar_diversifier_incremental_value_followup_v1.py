from __future__ import annotations

import csv
import hashlib
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
    fast_price_volume_preregistered_batch_v1 as parent,
)
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)


TASK_ID = "decelerated_psar_diversifier_incremental_value_followup_v1"
MODE = "fast-progress"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
PARENT_EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "fast_price_volume_preregistered_batch_v1"
    / "latest"
)
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\303e9e0a-661f-410c-a100-e5cfbe918901\pasted-text.txt"
)

STRATEGY_ID = "barbara_decelerated_psar_spy_bil_v1"
FAMILY_ID = "decelerated_parabolic_trend_state"
DISPLAY_NAME = "Decelerated PSAR SPY/BIL Timing"
ARCHITECTURE = "long_only_adaptive_parabolic_stop_and_reverse_state"
SOURCE_LINEAGE = "barbara_2021_decelerated_psar_appendix"
PARENT_TRIAL_ID = "fast_pv_v1__decelerated_psar__canonical"
TRIAL_ID = "decelerated_psar_diversifier_incremental_value_followup_v1__child"
PREREGISTRATION_TIMESTAMP = "2026-07-29T00:00:00-06:00"

START_DATE = pd.Timestamp("2010-08-10")
END_DATE = pd.Timestamp("2026-06-18")
FROZEN_EXPOSURE_SPY_WEIGHT = 0.753493
FROZEN_EXPOSURE_BIL_WEIGHT = 0.246507
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-9

NEXT_ADVANCE = "direction_owner_review_decelerated_psar_diversifier_followup_v1"
NEXT_CLOSE = "direction_owner_review_discovery_yield_after_fast_price_volume_v1"
NEXT_BLOCK = (
    "direction_owner_review_decelerated_psar_diversifier_reproduction_block_v1"
)

PORTFOLIO_IDS = (
    "100pct_frozen_reference",
    "80pct_reference_20pct_decelerated_psar_candidate",
    "80pct_reference_20pct_original_psar_control",
    "80pct_reference_20pct_decelerated_psar_exposure_matched_control",
    "80pct_reference_20pct_SPY_200_day_trend_control",
    "80pct_reference_20pct_BIL",
    "80pct_reference_20pct_SPY_buy_and_hold",
)

CONTROL_IDS = (
    "frozen_current_active_vm_dsr_usci_combo",
    "original_psar_spy_bil_control",
    "decelerated_psar_exposure_matched_spy_bil_control",
    "SPY_200_day_trend_control",
    "BIL_buy_and_hold",
    "SPY_buy_and_hold",
)

PROTECTED_STATE_PATHS = parent.PROTECTED_STATE_PATHS

ALLOWED_OUTCOMES = {
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "blocked_feasibility",
}

ALLOWED_FAILURE_REASONS = {
    "",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "period_instability",
    "cost_drag",
    "turnover_drag",
    "weak_portfolio_contribution",
    "data_or_comparability_failure",
    "methodology_failure",
    "overfit_or_unstable",
}

FORBIDDEN_FLAGS = {
    "validation_or_robustness": False,
    "paper_demo_eligibility": False,
    "lifecycle_reconciliation": False,
    "source_completion": False,
    "parameter_optimization": False,
    "provider_or_network_access": False,
    "broker_account_order_or_real_money_action": False,
    "other_price_volume_candidates_reopened": False,
    "control_promoted": False,
}


def rel(path: str | Path) -> str:
    return parent.rel(path)


def file_hash(path: Path) -> str:
    return parent.file_hash(path)


def csv_value(value: Any) -> str:
    return parent.csv_value(value)


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
        expected = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths}


def parent_evidence_paths() -> list[Path]:
    return sorted(path for path in PARENT_EVIDENCE_DIR.rglob("*") if path.is_file())


def cache_inventory_files() -> list[Path]:
    return parent.cache_inventory_files()


def aggregate_hash(hashes: dict[str, str]) -> str:
    material = "\n".join(f"{key}|{value}" for key, value in sorted(hashes.items()))
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parent_trial_row() -> dict[str, str]:
    rows = read_csv_rows(PARENT_EVIDENCE_DIR / "trial_ledger.csv")
    matches = [row for row in rows if row["trial_id"] == PARENT_TRIAL_ID]
    if len(matches) != 1:
        raise RuntimeError("Parent trial identity is not unique")
    return matches[0]


def frozen_parameters() -> dict[str, Any]:
    return {
        "AF_min": 0.02,
        "AF_max": 0.20,
        "AF_forward_step": 0.02,
        "AF_backward_step": 0.05,
        "change_period_sessions": 3,
        "change_threshold": 0.02,
        "candidate_route": "diversifier_only",
        "outer_sleeve_weight": 0.20,
        "outer_reference_weight": 0.80,
        "outer_rebalance": "monthly_following_regular_session_close",
        "execution": "following_regular_session_close",
    }


def strategy_row(
    outcome: str, failure_reason: str, next_action: str
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": ARCHITECTURE,
        "source_or_research_lineage": SOURCE_LINEAGE,
        "instrument_universe": "SPY|BIL",
        "parameters": frozen_parameters(),
        "benchmark_or_control": "|".join(CONTROL_IDS),
        "stage": STAGE,
        "route_evaluated_in_child": "diversifier_only",
        "existing_strategy_configuration_carried_forward": True,
        "new_strategy_configuration_created": False,
        "exact_source_replication_claimed": False,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "exploratory_variant",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "parent_standalone_outcome": "closed_exploration",
        "parent_standalone_failure_reason": "benchmark_like_behavior",
        "parent_standalone_outcome_changed": False,
        "authoritative_registry_record_created": False,
    }


def trial_row(
    outcome: str, failure_reason: str, next_action: str
) -> dict[str, Any]:
    return {
        **strategy_row(outcome, failure_reason, next_action),
        "entity_type": "experiment_trial",
        "changed_fields_from_parent": "evaluation_route_and_portfolio_controls_only",
        "PSAR_formula_changed": False,
        "AF_parameters_changed": False,
        "instruments_changed": False,
        "signal_timing_changed": False,
        "execution_changed": False,
        "costs_changed": False,
        "standalone_outcome_changed": False,
        "route_changed_to_diversifier_only": True,
        "result_driven_route_review": True,
        "optimization_performed": False,
        "post_result_parameter_change_allowed": False,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
    }


def write_preregistration_checkpoint() -> str:
    strategy = strategy_row(
        "preregistered_pending_reproduction_gate",
        "",
        "execute_parent_reproduction_gate",
    )
    trial = trial_row(
        "preregistered_pending_reproduction_gate",
        "",
        "execute_parent_reproduction_gate",
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [strategy], list(strategy))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", [trial], list(trial))
    material = (
        (OUTPUT_DIR / "strategy_cards.csv").read_bytes()
        + (OUTPUT_DIR / "trial_ledger.csv").read_bytes()
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


def benchmark_rows() -> list[dict[str, Any]]:
    roles = {
        "frozen_current_active_vm_dsr_usci_combo": "frozen_reference",
        "original_psar_spy_bil_control": "critical_same_mechanism_control",
        "decelerated_psar_exposure_matched_spy_bil_control": (
            "critical_frozen_exposure_control"
        ),
        "SPY_200_day_trend_control": "additional_trend_control",
        "BIL_buy_and_hold": "additional_defensive_control",
        "SPY_buy_and_hold": "additional_risk_asset_control",
    }
    return [
        {
            "benchmark_or_control_id": control_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "control_role": roles[control_id],
            "critical_control": control_id
            in {
                "original_psar_spy_bil_control",
                "decelerated_psar_exposure_matched_spy_bil_control",
            },
            "frozen_before_route_results": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
            "promotion_allowed_in_this_task": False,
        }
        for control_id in CONTROL_IDS
    ]


def control_definition_rows(parent_exposure: float) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "frozen_current_active_vm_dsr_usci_combo",
            "definition": "100pct frozen active reference return path",
            "SPY_weight": "",
            "BIL_weight": "",
            "rebalance": "frozen_reference_convention",
            "parent_archived_weight": "",
            "route_frozen_weight": "",
            "weight_recalculated": False,
        },
        {
            "control_id": "original_psar_spy_bil_control",
            "definition": (
                "identical PSAR state machine without three-session AF deceleration; "
                "AF increases only on a new extreme"
            ),
            "SPY_weight": "state_dependent",
            "BIL_weight": "state_dependent",
            "rebalance": "following_session_close_on_state_change",
            "parent_archived_weight": "",
            "route_frozen_weight": "",
            "weight_recalculated": False,
        },
        {
            "control_id": "decelerated_psar_exposure_matched_spy_bil_control",
            "definition": (
                "direction-owner-frozen monthly static SPY/BIL control; distinct "
                "from the archived parent target-weight control used only for reproduction"
            ),
            "SPY_weight": FROZEN_EXPOSURE_SPY_WEIGHT,
            "BIL_weight": FROZEN_EXPOSURE_BIL_WEIGHT,
            "rebalance": "monthly_following_session_close",
            "parent_archived_weight": parent_exposure,
            "route_frozen_weight": FROZEN_EXPOSURE_SPY_WEIGHT,
            "weight_recalculated": False,
        },
        {
            "control_id": "SPY_200_day_trend_control",
            "definition": "SPY when adjusted close exceeds SMA200, otherwise BIL",
            "SPY_weight": "state_dependent",
            "BIL_weight": "state_dependent",
            "rebalance": "following_session_close_on_state_change",
            "parent_archived_weight": "",
            "route_frozen_weight": "",
            "weight_recalculated": False,
        },
        {
            "control_id": "BIL_buy_and_hold",
            "definition": "100pct BIL",
            "SPY_weight": 0.0,
            "BIL_weight": 1.0,
            "rebalance": "initial_only",
            "parent_archived_weight": "",
            "route_frozen_weight": "",
            "weight_recalculated": False,
        },
        {
            "control_id": "SPY_buy_and_hold",
            "definition": "100pct SPY",
            "SPY_weight": 1.0,
            "BIL_weight": 0.0,
            "rebalance": "initial_only",
            "parent_archived_weight": "",
            "route_frozen_weight": "",
            "weight_recalculated": False,
        },
    ]


def parent_card() -> parent.CandidateCard:
    matches = [card for card in parent.CARDS if card.strategy_id == STRATEGY_ID]
    if len(matches) != 1:
        raise RuntimeError("Parent strategy card is not unique")
    return matches[0]


def reconstruct_inner_paths() -> dict[str, Any]:
    card = parent_card()
    prepared = parent.prepare_candidate(card)
    prices = prepared["prices"]
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    frozen_exposure_events = parent.monthly_static_events(
        prices.index, FROZEN_EXPOSURE_SPY_WEIGHT
    )
    for cost in COST_BPS:
        paths[("candidate", cost)] = accounting.simulate_path(
            prices,
            prepared["candidate_events"],
            cost,
            prepared["timing_convention"],
        )
        for control_id in (
            "original_psar_spy_bil_control",
            "SPY_200_day_trend_control",
            "BIL_buy_and_hold",
            "SPY_buy_and_hold",
        ):
            paths[(control_id, cost)] = accounting.simulate_path(
                prices,
                prepared["control_events"][control_id],
                cost,
                prepared["timing_convention"],
            )
        paths[("parent_archived_exposure_control", cost)] = accounting.simulate_path(
            prices,
            prepared["control_events"][
                "decelerated_psar_exposure_matched_spy_bil_control"
            ],
            cost,
            prepared["timing_convention"],
        )
        paths[
            ("decelerated_psar_exposure_matched_spy_bil_control", cost)
        ] = accounting.simulate_path(
            prices,
            frozen_exposure_events,
            cost,
            prepared["timing_convention"],
        )
    return {
        "card": card,
        "prepared": prepared,
        "paths": paths,
        "parent_archived_exposure_weight": prepared[
            "mechanical_average_target_SPY_weight"
        ],
    }


def common_period(
    reference: pd.Series, inner_paths: dict[tuple[str, float], dict[str, Any]]
) -> pd.DatetimeIndex:
    common = reference.dropna().index
    for key in (
        "candidate",
        "original_psar_spy_bil_control",
        "decelerated_psar_exposure_matched_spy_bil_control",
        "SPY_200_day_trend_control",
        "BIL_buy_and_hold",
        "SPY_buy_and_hold",
    ):
        common = common.intersection(inner_paths[(key, PRIMARY_COST_BPS)]["returns"].dropna().index)
    common = common[(common >= START_DATE) & (common <= END_DATE)].sort_values()
    return common


def augment_portfolio_path(
    base: dict[str, Any],
    reference: pd.Series,
    sleeve_path: dict[str, Any] | None,
) -> dict[str, Any]:
    if sleeve_path is None:
        daily = base["daily_df"].copy()
        daily["inner_turnover"] = 0.0
        daily["outer_turnover"] = daily["one_way_turnover"]
        daily["inner_transaction_cost_drag"] = 0.0
        daily["outer_transaction_cost_drag"] = daily["transaction_cost_drag"]
        daily["total_transaction_cost_drag"] = daily["transaction_cost_drag"]
        daily["average_gross_exposure"] = 1.0
        return {
            **base,
            "daily_df": daily,
            "inner_turnover": pd.Series(0.0, index=base["returns"].index),
            "outer_turnover": base["turnover"],
            "inner_cost": pd.Series(0.0, index=base["returns"].index),
            "outer_cost": base["cost"],
            "total_cost": base["cost"],
        }
    index = base["returns"].index
    sleeve_returns = sleeve_path["returns"].reindex(index)
    inner_turnover = sleeve_path["turnover"].reindex(index).fillna(0.0)
    inner_cost = sleeve_path["cost"].reindex(index).fillna(0.0)
    combined = pd.concat(
        [reference.reindex(index).rename("reference"), sleeve_returns.rename("sleeve")],
        axis=1,
    ).dropna()
    trade_positions = {0}
    for pos in range(1, len(combined)):
        if combined.index[pos - 1].to_period("M") != combined.index[pos].to_period("M"):
            trade_positions.add(pos)
    weights = np.array([0.0, 0.0], dtype=float)
    target = np.array([0.8, 0.2], dtype=float)
    inner_turnover_contribution = np.zeros(len(combined))
    inner_cost_contribution = np.zeros(len(combined))
    gross_exposure = np.zeros(len(combined))
    values = combined.to_numpy(dtype=float)
    for pos in range(len(combined)):
        held = weights.copy()
        daily_return = values[pos]
        pretrade_values = held * (1.0 + daily_return)
        denominator = float(pretrade_values.sum())
        pretrade = (
            pretrade_values / denominator if denominator > 0.0 else held.copy()
        )
        inner_turnover_contribution[pos] = float(
            (target[1] if pos == 0 else pretrade[1])
            * inner_turnover.reindex(combined.index).iloc[pos]
        )
        inner_cost_contribution[pos] = float(
            held[1] * inner_cost.reindex(combined.index).iloc[pos]
        )
        weights = target.copy() if pos in trade_positions else pretrade
        gross_exposure[pos] = float(np.abs(weights).sum())
    daily = base["daily_df"].reindex(combined.index).copy()
    daily["inner_turnover"] = inner_turnover_contribution
    daily["outer_turnover"] = daily["one_way_turnover"]
    daily["inner_transaction_cost_drag"] = inner_cost_contribution
    daily["outer_transaction_cost_drag"] = daily["transaction_cost_drag"]
    daily["total_transaction_cost_drag"] = (
        daily["inner_transaction_cost_drag"]
        + daily["outer_transaction_cost_drag"]
    )
    daily["average_gross_exposure"] = gross_exposure
    return {
        **base,
        "daily_df": daily,
        "inner_turnover": daily["inner_turnover"],
        "outer_turnover": daily["outer_turnover"],
        "inner_cost": daily["inner_transaction_cost_drag"],
        "outer_cost": daily["outer_transaction_cost_drag"],
        "total_cost": daily["total_transaction_cost_drag"],
    }


def simulate_portfolio(
    reference: pd.Series,
    sleeve_path: dict[str, Any] | None,
    portfolio_id: str,
    cost_bps: float,
) -> dict[str, Any]:
    if sleeve_path is None:
        base = portfolio_accounting.reference_payload(reference, cost_bps)
        return augment_portfolio_path(base, reference, None)
    sleeve = sleeve_path["returns"].reindex(reference.index).dropna()
    aligned_reference = reference.reindex(sleeve.index)
    base = portfolio_accounting.simulate_two_component_portfolio(
        aligned_reference, sleeve, portfolio_id, cost_bps
    )
    return augment_portfolio_path(base, aligned_reference, sleeve_path)


def portfolio_metric_payload(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    metrics = dict(parent.portfolio_metrics(path, period_index))
    daily = path["daily_df"]
    if period_index is not None:
        daily = daily.reindex(period_index).dropna(how="all")
    metrics.update(
        {
            "inner_turnover": float(daily["inner_turnover"].sum()),
            "outer_turnover": float(daily["outer_turnover"].sum()),
            "inner_transaction_cost_drag": float(
                daily["inner_transaction_cost_drag"].sum()
            ),
            "outer_transaction_cost_drag": float(
                daily["outer_transaction_cost_drag"].sum()
            ),
            "total_transaction_cost_drag": float(
                daily["total_transaction_cost_drag"].sum()
            ),
            "average_gross_exposure": float(
                daily["average_gross_exposure"].mean()
            ),
            "maximum_gross_exposure": float(
                daily["max_daily_exposure"].max()
            ),
            "maximum_daily_weight_sum": float(
                daily["max_daily_weight_sum"].max()
            ),
        }
    )
    return metrics


def build_current_portfolios(
    reference: pd.Series,
    inner: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
) -> dict[tuple[str, float], dict[str, Any]]:
    mapping = {
        "80pct_reference_20pct_decelerated_psar_candidate": "candidate",
        "80pct_reference_20pct_original_psar_control": (
            "original_psar_spy_bil_control"
        ),
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control": (
            "decelerated_psar_exposure_matched_spy_bil_control"
        ),
        "80pct_reference_20pct_SPY_200_day_trend_control": (
            "SPY_200_day_trend_control"
        ),
        "80pct_reference_20pct_BIL": "BIL_buy_and_hold",
        "80pct_reference_20pct_SPY_buy_and_hold": "SPY_buy_and_hold",
    }
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    aligned_reference = reference.reindex(index)
    for cost in COST_BPS:
        paths[("100pct_frozen_reference", cost)] = simulate_portfolio(
            aligned_reference, None, "100pct_frozen_reference", cost
        )
        for portfolio_id, inner_id in mapping.items():
            paths[(portfolio_id, cost)] = simulate_portfolio(
                aligned_reference,
                inner[(inner_id, cost)],
                portfolio_id,
                cost,
            )
    return paths


def build_parent_reproduction_portfolios(
    reference: pd.Series,
    inner: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
) -> dict[tuple[str, float], dict[str, Any]]:
    mapping = {
        "100pct_frozen_reference": None,
        "80pct_reference_20pct_candidate": "candidate",
        "80pct_reference_20pct_original_psar_spy_bil_control": (
            "original_psar_spy_bil_control"
        ),
        "80pct_reference_20pct_decelerated_psar_exposure_matched_spy_bil_control": (
            "parent_archived_exposure_control"
        ),
    }
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    aligned_reference = reference.reindex(index)
    for cost in COST_BPS:
        for portfolio_id, inner_id in mapping.items():
            paths[(portfolio_id, cost)] = simulate_portfolio(
                aligned_reference,
                None if inner_id is None else inner[(inner_id, cost)],
                portfolio_id,
                cost,
            )
    return paths


REPRODUCTION_METRICS = (
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


def reproduction_rows(
    reproduction_paths: dict[tuple[str, float], dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    archived = read_csv_rows(
        PARENT_EVIDENCE_DIR / "portfolio_contribution_results.csv"
    )
    lookup = {
        (row["portfolio_id"], float(row["cost_assumption_bps"])): row
        for row in archived
        if row["strategy_id"] == STRATEGY_ID
    }
    rows: list[dict[str, Any]] = []
    all_pass = True
    for key, path in sorted(reproduction_paths.items(), key=lambda item: (item[0][1], item[0][0])):
        expected = lookup.get(key)
        actual = portfolio_metric_payload(path)
        if expected is None:
            all_pass = False
            continue
        for metric in REPRODUCTION_METRICS:
            expected_value = float(expected[metric])
            actual_value = float(actual[metric])
            difference = actual_value - expected_value
            passed = abs(difference) <= REPRODUCTION_TOLERANCE
            all_pass = bool(all_pass and passed)
            rows.append(
                {
                    "portfolio_id": key[0],
                    "cost_assumption_bps": key[1],
                    "metric": metric,
                    "parent_recorded_value": expected_value,
                    "reproduced_value": actual_value,
                    "difference": difference,
                    "absolute_difference": abs(difference),
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "reproduction_pass": passed,
                }
            )
    return rows, all_pass


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return accounting.dominates(control, candidate)


def worse_on_both(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(control["sharpe_ratio"])
        and float(candidate["maximum_drawdown"])
        < float(control["maximum_drawdown"])
    )


def material_advantage(
    candidate: dict[str, Any], control: dict[str, Any]
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(control["maximum_drawdown"])
        >= 0.01
    )


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


METRIC_FIELDS = (
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "inner_turnover",
    "outer_turnover",
    "inner_transaction_cost_drag",
    "outer_transaction_cost_drag",
    "total_transaction_cost_drag",
    "trade_or_rebalance_count",
    "average_gross_exposure",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
)


def portfolio_result_row(
    portfolio_id: str,
    cost: float,
    period_label: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "entity_type": "portfolio_diagnostic",
        "stage": STAGE,
        "route": "diversifier_only",
        "portfolio_id": portfolio_id,
        "cost_assumption_bps": cost,
        "period_label": period_label,
        "period_role": (
            "full_period_route_exploration"
            if period_label == "full_period"
            else "deterministic_chronological_half_not_validation_sealed_untouched_or_independent"
        ),
        **metrics,
    }


def full_and_half_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    full: list[dict[str, Any]] = []
    halves: list[dict[str, Any]] = []
    for cost in COST_BPS:
        for portfolio_id in PORTFOLIO_IDS:
            full.append(
                portfolio_result_row(
                    portfolio_id,
                    cost,
                    "full_period",
                    portfolio_metric_payload(paths[(portfolio_id, cost)]),
                )
            )
    for period_label, period in split_halves(index):
        for portfolio_id in PORTFOLIO_IDS:
            halves.append(
                portfolio_result_row(
                    portfolio_id,
                    PRIMARY_COST_BPS,
                    period_label,
                    portfolio_metric_payload(
                        paths[(portfolio_id, PRIMARY_COST_BPS)], period
                    ),
                )
            )
    return full, halves


def rolling_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
    months: int,
) -> list[dict[str, Any]]:
    month_ends = parent.last_dates_by_period(index, "M")
    candidate_id = "80pct_reference_20pct_decelerated_psar_candidate"
    comparisons = (
        "100pct_frozen_reference",
        "80pct_reference_20pct_original_psar_control",
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control",
    )
    rows: list[dict[str, Any]] = []
    sequence = 0
    for end in month_ends:
        boundary = end - pd.DateOffset(months=months)
        if boundary < index[0]:
            continue
        period = index[(index > boundary) & (index <= end)]
        if not len(period):
            continue
        sequence += 1
        candidate = portfolio_metric_payload(
            paths[(candidate_id, PRIMARY_COST_BPS)], period
        )
        for control_id in comparisons:
            control = portfolio_metric_payload(
                paths[(control_id, PRIMARY_COST_BPS)], period
            )
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "window_months": months,
                    "window_sequence": sequence,
                    "window_start": period[0].date().isoformat(),
                    "window_end": period[-1].date().isoformat(),
                    "comparison_portfolio_id": control_id,
                    "candidate_cagr": candidate["cagr"],
                    "control_cagr": control["cagr"],
                    "cagr_difference": float(candidate["cagr"])
                    - float(control["cagr"]),
                    "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                    "control_sharpe_ratio": control["sharpe_ratio"],
                    "sharpe_difference": float(candidate["sharpe_ratio"])
                    - float(control["sharpe_ratio"]),
                    "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                    "control_maximum_drawdown": control["maximum_drawdown"],
                    "maximum_drawdown_difference": float(
                        candidate["maximum_drawdown"]
                    )
                    - float(control["maximum_drawdown"]),
                    "control_dominates_candidate": dominates(control, candidate),
                    "candidate_improves_reference_sharpe_or_drawdown": (
                        control_id == "100pct_frozen_reference"
                        and (
                            float(candidate["sharpe_ratio"])
                            > float(control["sharpe_ratio"])
                            or float(candidate["maximum_drawdown"])
                            > float(control["maximum_drawdown"])
                        )
                    ),
                    "validation_claimed": False,
                }
            )
    return rows


def rolling_summary_rows(
    rows36: list[dict[str, Any]], rows60: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for months, rows in ((36, rows36), (60, rows60)):
        for comparison in (
            "100pct_frozen_reference",
            "80pct_reference_20pct_original_psar_control",
            "80pct_reference_20pct_decelerated_psar_exposure_matched_control",
        ):
            subset = [row for row in rows if row["comparison_portfolio_id"] == comparison]
            summaries.append(
                {
                    "window_months": months,
                    "comparison_portfolio_id": comparison,
                    "eligible_window_count": len(subset),
                    "median_cagr_difference": float(
                        np.median([row["cagr_difference"] for row in subset])
                    ),
                    "median_sharpe_difference": float(
                        np.median([row["sharpe_difference"] for row in subset])
                    ),
                    "median_maximum_drawdown_difference": float(
                        np.median(
                            [row["maximum_drawdown_difference"] for row in subset]
                        )
                    ),
                    "control_domination_fraction": float(
                        np.mean(
                            [row["control_dominates_candidate"] for row in subset]
                        )
                    ),
                    "candidate_improves_reference_fraction": (
                        float(
                            np.mean(
                                [
                                    row[
                                        "candidate_improves_reference_sharpe_or_drawdown"
                                    ]
                                    for row in subset
                                ]
                            )
                        )
                        if comparison == "100pct_frozen_reference"
                        else ""
                    ),
                    "unfavorable_windows_retained": True,
                }
            )
    return summaries


def monthly_returns(series: pd.Series) -> pd.Series:
    return series.groupby(series.index.to_period("M")).apply(
        lambda values: float(np.prod(1.0 + values.to_numpy(dtype=float)) - 1.0)
    )


def downside_rows(
    paths: dict[tuple[str, float], dict[str, Any]]
) -> list[dict[str, Any]]:
    monthly = {
        portfolio_id: monthly_returns(
            paths[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
        )
        for portfolio_id in PORTFOLIO_IDS
    }
    reference = monthly["100pct_frozen_reference"]
    negative_months = reference[reference < 0.0].index
    rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        values = monthly[portfolio_id].reindex(negative_months).dropna()
        aligned_reference = reference.reindex(values.index)
        difference = values - aligned_reference
        rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "portfolio_id": portfolio_id,
                "cost_assumption_bps": PRIMARY_COST_BPS,
                "reference_negative_month_count": len(values),
                "cumulative_return_in_reference_negative_months": float(
                    np.prod(1.0 + values.to_numpy(dtype=float)) - 1.0
                ),
                "mean_monthly_return": float(values.mean()),
                "worst_month": float(values.min()),
                "percentage_months_outperforming_reference": float(
                    (difference > 0.0).mean()
                ),
                "average_portfolio_minus_reference_return": float(
                    difference.mean()
                ),
                "diagnostic_only": True,
            }
        )
    return rows


def mechanism_rows(
    prepared: dict[str, Any],
    paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    diagnostics = pd.DataFrame(prepared["diagnostics"])
    diagnostics["signal_date"] = pd.to_datetime(diagnostics["signal_date"])
    diagnostics = diagnostics.set_index("signal_date").reindex(index)
    candidate_monthly = monthly_returns(
        paths[
            (
                "80pct_reference_20pct_decelerated_psar_candidate",
                PRIMARY_COST_BPS,
            )
        ]["returns"]
    )
    reference_monthly = monthly_returns(
        paths[("100pct_frozen_reference", PRIMARY_COST_BPS)]["returns"]
    )
    rows: list[dict[str, Any]] = []
    for period, dates in pd.Series(index, index=index).groupby(index.to_period("M")):
        month_index = pd.DatetimeIndex(dates.to_numpy())
        month_diag = diagnostics.reindex(month_index)
        candidate_return = candidate_monthly.get(period, float("nan"))
        reference_return = reference_monthly.get(period, float("nan"))
        rows.append(
            {
                "month": str(period),
                "month_start": month_index[0].date().isoformat(),
                "month_end": month_index[-1].date().isoformat(),
                "SPY_target_session_fraction": float(
                    (month_diag["target_state"] == "SPY").mean()
                ),
                "BIL_target_session_fraction": float(
                    (month_diag["target_state"] == "BIL").mean()
                ),
                "PSAR_reversal_count": int(
                    month_diag["reversal"].fillna(False).astype(bool).sum()
                ),
                "state_transition_count": int(
                    month_diag["state_transition"].fillna(False).astype(bool).sum()
                ),
                "candidate_portfolio_return_5bps": candidate_return,
                "reference_return": reference_return,
                "candidate_minus_reference_return": float(
                    candidate_return - reference_return
                ),
                "PSAR_formula_changed": False,
                "AF_parameters_changed": False,
                "diagnostic_only": True,
            }
        )
    return rows


def invariant_rows(
    reproduction_pass: bool,
    paths: dict[tuple[str, float], dict[str, Any]],
    parent_hash_unchanged: bool,
    cache_unchanged: bool,
    protected_unchanged: bool,
) -> list[dict[str, Any]]:
    rows = [
        {
            "invariant_name": "parent_portfolio_reproduction_within_1e_9",
            "invariant_pass": reproduction_pass,
            "detail": "all archived 0/5/10-bps parent portfolio metrics reproduced",
        },
        {
            "invariant_name": "PSAR_formula_and_parameters_unchanged",
            "invariant_pass": True,
            "detail": "parent prepare_candidate and frozen PSAR event path reused",
        },
        {
            "invariant_name": "following_session_close_execution_unchanged",
            "invariant_pass": True,
            "detail": "parent timing convention reused without adaptation",
        },
        {
            "invariant_name": "parent_evidence_unchanged",
            "invariant_pass": parent_hash_unchanged,
            "detail": "all parent packet file hashes match before and after",
        },
        {
            "invariant_name": "canonical_caches_unchanged",
            "invariant_pass": cache_unchanged,
            "detail": "cache inventory hashes match before and after",
        },
        {
            "invariant_name": "protected_state_unchanged",
            "invariant_pass": protected_unchanged,
            "detail": "registry, roadmap, queue, family ledger and observations unchanged",
        },
    ]
    for cost in COST_BPS:
        for portfolio_id in PORTFOLIO_IDS:
            metrics = portfolio_metric_payload(paths[(portfolio_id, cost)])
            rows.append(
                {
                    "invariant_name": f"{portfolio_id}_{cost:g}bps_accounting",
                    "invariant_pass": bool(
                        metrics["invariant_pass"]
                        and float(metrics["maximum_gross_exposure"])
                        <= 1.0 + WEIGHT_TOLERANCE
                        and float(metrics["maximum_daily_weight_sum"])
                        <= 1.0 + WEIGHT_TOLERANCE
                    ),
                    "detail": (
                        "explicit monthly holdings; inner and outer turnover separate; "
                        "nonnegative weights; no fixed daily blend"
                    ),
                }
            )
    for row in rows:
        row.update(
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "negative_weights_present": False,
                "leverage_used": False,
                "daily_fixed_weight_return_blend_used": False,
                "validation_claimed": False,
            }
        )
    return rows


def summary_lookup(
    summaries: list[dict[str, Any]], months: int, comparison: str
) -> dict[str, Any]:
    matches = [
        row
        for row in summaries
        if row["window_months"] == months
        and row["comparison_portfolio_id"] == comparison
    ]
    if len(matches) != 1:
        raise RuntimeError("Rolling summary identity is not unique")
    return matches[0]


def classify(
    reproduction_pass: bool,
    all_invariants_pass: bool,
    paths: dict[tuple[str, float], dict[str, Any]],
    inner_paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
    summaries: list[dict[str, Any]],
    downside: list[dict[str, Any]],
) -> tuple[str, str, str]:
    if not reproduction_pass:
        return (
            "blocked_feasibility",
            "data_or_comparability_failure",
            "parent portfolio reproduction failed the frozen 1e-9 tolerance",
        )
    if not all_invariants_pass:
        return (
            "blocked_feasibility",
            "methodology_failure",
            "one or more accounting, timing, weight, or exposure invariants failed",
        )
    standalone = parent.strategy_metrics(
        inner_paths[("candidate", PRIMARY_COST_BPS)]
    )
    if float(standalone["total_return"]) <= 0.0:
        return (
            "closed_exploration",
            "weak_portfolio_contribution",
            "parent candidate standalone full-period return is not positive",
        )
    candidate_id = "80pct_reference_20pct_decelerated_psar_candidate"
    original_id = "80pct_reference_20pct_original_psar_control"
    exposure_id = (
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control"
    )
    reference_id = "100pct_frozen_reference"
    candidate = portfolio_metric_payload(
        paths[(candidate_id, PRIMARY_COST_BPS)]
    )
    reference = portfolio_metric_payload(
        paths[(reference_id, PRIMARY_COST_BPS)]
    )
    critical = {
        original_id: portfolio_metric_payload(
            paths[(original_id, PRIMARY_COST_BPS)]
        ),
        exposure_id: portfolio_metric_payload(
            paths[(exposure_id, PRIMARY_COST_BPS)]
        ),
    }
    if not material_advantage(candidate, reference) or worse_on_both(
        candidate, reference
    ):
        return (
            "closed_exploration",
            "weak_portfolio_contribution",
            "candidate does not add frozen Sharpe/drawdown materiality versus reference",
        )
    dominating = [
        control_id
        for control_id, metrics in critical.items()
        if dominates(metrics, candidate)
    ]
    if dominating:
        return (
            "closed_exploration",
            "weak_vs_primary_control",
            "critical control dominates full-period candidate: "
            + ",".join(dominating),
        )
    lacking_materiality = [
        control_id
        for control_id, metrics in critical.items()
        if not material_advantage(candidate, metrics)
    ]
    if lacking_materiality:
        return (
            "closed_exploration",
            "benchmark_like_behavior",
            "candidate lacks frozen materiality versus: "
            + ",".join(lacking_materiality),
        )
    for period_label, period in split_halves(index):
        candidate_half = portfolio_metric_payload(
            paths[(candidate_id, PRIMARY_COST_BPS)], period
        )
        for control_id in (reference_id, original_id, exposure_id):
            control_half = portfolio_metric_payload(
                paths[(control_id, PRIMARY_COST_BPS)], period
            )
            if worse_on_both(candidate_half, control_half):
                return (
                    "closed_exploration",
                    "period_instability",
                    f"candidate worse on Sharpe and drawdown in {period_label} versus {control_id}",
                )
    for months in (36, 60):
        reference_summary = summary_lookup(summaries, months, reference_id)
        if float(reference_summary["candidate_improves_reference_fraction"]) <= 0.50:
            return (
                "closed_exploration",
                "overfit_or_unstable",
                f"candidate improves reference in no more than half of rolling {months}-month windows",
            )
        for control_id in (original_id, exposure_id):
            control_summary = summary_lookup(summaries, months, control_id)
            if float(control_summary["control_domination_fraction"]) > 0.50:
                return (
                    "closed_exploration",
                    "weak_vs_primary_control",
                    f"{control_id} dominates in more than half of rolling {months}-month windows",
                )
    candidate_downside = next(
        row for row in downside if row["portfolio_id"] == candidate_id
    )
    if (
        float(candidate_downside["average_portfolio_minus_reference_return"])
        < 0.0
    ):
        return (
            "closed_exploration",
            "weak_portfolio_contribution",
            "average incremental return is negative in reference-negative months",
        )
    candidate_10 = portfolio_metric_payload(paths[(candidate_id, 10.0)])
    reference_10 = portfolio_metric_payload(paths[(reference_id, 10.0)])
    critical_10 = {
        control_id: portfolio_metric_payload(paths[(control_id, 10.0)])
        for control_id in (original_id, exposure_id)
    }
    if worse_on_both(candidate_10, reference_10):
        return (
            "closed_exploration",
            "cost_drag",
            "candidate is worse than reference on Sharpe and drawdown at 10 bps",
        )
    if any(dominates(metrics, candidate_10) for metrics in critical_10.values()):
        return (
            "closed_exploration",
            "cost_drag",
            "a critical control dominates the candidate at 10 bps",
        )
    if all(
        worse_on_both(candidate_10, metrics) for metrics in critical_10.values()
    ):
        return (
            "closed_exploration",
            "cost_drag",
            "candidate is worse than both critical controls on Sharpe and drawdown at 10 bps",
        )
    return (
        "exploratory_followup_candidate_diversifier",
        "",
        "all frozen route-specific incremental-value exploration gates passed",
    )


def next_action_for_outcome(outcome: str) -> str:
    if outcome == "exploratory_followup_candidate_diversifier":
        return NEXT_ADVANCE
    if outcome == "closed_exploration":
        return NEXT_CLOSE
    return NEXT_BLOCK


def build_report(
    outcome: str,
    failure_reason: str,
    decision_reason: str,
    next_action: str,
    full_rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    reproduction_pass: bool,
) -> str:
    primary = {
        row["portfolio_id"]: row
        for row in full_rows
        if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
    }
    lines = [
        "# Decelerated PSAR Diversifier Incremental-Value Follow-up V1",
        "",
        "## Scope",
        "",
        (
            "Exactly one route-specific exploration child trial was evaluated. "
            "The parent standalone closure remains unchanged, and the frozen PSAR "
            "formula, parameters, instruments, timing, execution, costs, and 20% sleeve were not altered."
        ),
        "",
        "## Reproduction",
        "",
        f"Parent portfolio reproduction within `1e-9`: `{str(reproduction_pass).lower()}`.",
        "",
        (
            "The archived parent exposure control used `0.75370177268`, while this "
            "direction-owner-frozen route review uses `0.753493`. The archived value "
            "is used only for parent reproduction; the frozen route value is not recalculated."
        ),
        "",
        "## Full-Period Results",
        "",
        "| Portfolio | CAGR | Sharpe | Max drawdown | Inner turnover | Outer turnover |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for portfolio_id in PORTFOLIO_IDS:
        row = primary[portfolio_id]
        lines.append(
            f"| {portfolio_id} | {float(row['cagr']):.4%} | "
            f"{float(row['sharpe_ratio']):.3f} | "
            f"{float(row['maximum_drawdown']):.4%} | "
            f"{float(row['inner_turnover']):.3f} | "
            f"{float(row['outer_turnover']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Rolling Stability",
            "",
            "| Window | Comparison | Candidate improves reference | Control domination |",
            "|---:|---|---:|---:|",
        ]
    )
    for row in summaries:
        improves = row["candidate_improves_reference_fraction"]
        lines.append(
            f"| {row['window_months']}m | {row['comparison_portfolio_id']} | "
            f"{'' if improves == '' else f'{float(improves):.1%}'} | "
            f"{float(row['control_domination_fraction']):.1%} |"
        )
    lines.extend(
        [
            "",
            "## Outcome",
            "",
            f"* Outcome: `{outcome}`",
            f"* Failure reason: `{failure_reason}`" if failure_reason else "* Failure reason: none",
            f"* Decision: {decision_reason}",
            "",
            "This remains route-specific exploration evidence, not validation or paper/demo eligibility.",
            "",
            "## Next Action",
            "",
            f"`{next_action}`",
            "",
            "The next action is recorded only and was not executed.",
        ]
    )
    return "\n".join(lines)


def empty_diagnostic_files() -> None:
    write_csv(
        OUTPUT_DIR / "full_period_portfolio_results.csv",
        [],
        [
            "strategy_id",
            "trial_id",
            "portfolio_id",
            "cost_assumption_bps",
            *METRIC_FIELDS,
        ],
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_portfolio_results.csv",
        [],
        [
            "strategy_id",
            "trial_id",
            "portfolio_id",
            "cost_assumption_bps",
            "period_label",
            *METRIC_FIELDS,
        ],
    )
    rolling_fields = [
        "strategy_id",
        "trial_id",
        "window_months",
        "window_sequence",
        "window_start",
        "window_end",
        "comparison_portfolio_id",
        "cagr_difference",
        "sharpe_difference",
        "maximum_drawdown_difference",
        "control_dominates_candidate",
        "candidate_improves_reference_sharpe_or_drawdown",
    ]
    write_csv(OUTPUT_DIR / "rolling_36_month_portfolio_results.csv", [], rolling_fields)
    write_csv(OUTPUT_DIR / "rolling_60_month_portfolio_results.csv", [], rolling_fields)
    write_csv(OUTPUT_DIR / "rolling_window_summary.csv", [], rolling_fields)
    write_csv(
        OUTPUT_DIR / "reference_negative_month_results.csv",
        [],
        ["strategy_id", "trial_id", "portfolio_id"],
    )
    write_csv(
        OUTPUT_DIR / "candidate_mechanism_diagnostics.csv",
        [],
        ["month", "month_start", "month_end"],
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        [],
        ["strategy_id", "trial_id", "portfolio_id", "cost_assumption_bps"],
    )


def run() -> dict[str, Any]:
    if not PARENT_EVIDENCE_DIR.exists():
        raise RuntimeError("Required parent evidence packet is missing")
    parent_trial = parent_trial_row()
    if (
        parent_trial["outcome"] != "closed_exploration"
        or parent_trial["failure_reason"] != "benchmark_like_behavior"
    ):
        raise RuntimeError("Parent standalone closure no longer matches authority")

    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_before = map_hashes(cache_inventory_files())
    parent_before = map_hashes(parent_evidence_paths())
    source_hash_before = file_hash(SOURCE_PACKET)
    clean_output()
    preregistration_hash = write_preregistration_checkpoint()

    reconstructed = reconstruct_inner_paths()
    reference = parent.market.active_vm_dsr_usci_reference_returns()
    index = common_period(reference, reconstructed["paths"])
    period_pass = bool(
        len(index)
        and index[0] == START_DATE
        and index[-1] == END_DATE
    )
    parent_reproduction_paths = build_parent_reproduction_portfolios(
        reference, reconstructed["paths"], index
    )
    reproduction, reproduction_pass = reproduction_rows(
        parent_reproduction_paths
    )
    reproduction_pass = bool(reproduction_pass and period_pass)

    current_paths: dict[tuple[str, float], dict[str, Any]] = {}
    full_rows: list[dict[str, Any]] = []
    half_rows: list[dict[str, Any]] = []
    rolling36: list[dict[str, Any]] = []
    rolling60: list[dict[str, Any]] = []
    rolling_summary: list[dict[str, Any]] = []
    downside: list[dict[str, Any]] = []
    mechanism: list[dict[str, Any]] = []
    if reproduction_pass:
        current_paths = build_current_portfolios(
            reference, reconstructed["paths"], index
        )
        full_rows, half_rows = full_and_half_rows(current_paths, index)
        rolling36 = rolling_rows(current_paths, index, 36)
        rolling60 = rolling_rows(current_paths, index, 60)
        rolling_summary = rolling_summary_rows(rolling36, rolling60)
        downside = downside_rows(current_paths)
        mechanism = mechanism_rows(
            reconstructed["prepared"], current_paths, index
        )

    protected_mid = map_hashes(PROTECTED_STATE_PATHS)
    cache_mid = map_hashes(cache_inventory_files())
    parent_mid = map_hashes(parent_evidence_paths())
    preliminary_invariants = bool(
        protected_before == protected_mid
        and cache_before == cache_mid
        and parent_before == parent_mid
    )
    if reproduction_pass:
        invariants = invariant_rows(
            reproduction_pass,
            current_paths,
            parent_before == parent_mid,
            cache_before == cache_mid,
            protected_before == protected_mid,
        )
        all_invariants_pass = all(row["invariant_pass"] for row in invariants)
        outcome, failure_reason, decision_reason = classify(
            reproduction_pass,
            all_invariants_pass,
            current_paths,
            reconstructed["paths"],
            index,
            rolling_summary,
            downside,
        )
    else:
        invariants = [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "invariant_name": "parent_portfolio_reproduction_within_1e_9",
                "invariant_pass": False,
                "detail": (
                    "reproduction or exact frozen evaluation-period check failed"
                ),
                "negative_weights_present": False,
                "leverage_used": False,
                "daily_fixed_weight_return_blend_used": False,
                "validation_claimed": False,
            }
        ]
        all_invariants_pass = False
        outcome = "blocked_feasibility"
        failure_reason = "data_or_comparability_failure"
        decision_reason = (
            "parent portfolio reproduction or exact evaluation-period gate failed"
        )
    next_action = next_action_for_outcome(outcome)

    strategies = [strategy_row(outcome, failure_reason, next_action)]
    trials = [trial_row(outcome, failure_reason, next_action)]
    benchmarks = benchmark_rows()
    controls = control_definition_rows(
        reconstructed["parent_archived_exposure_weight"]
    )
    process = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "outcome": "task_completed",
            "exact_next_action": next_action,
            "strategy_counted": False,
            "trial_counted": False,
            "execute_next_action_now": False,
        }
    ]

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "child_trial_id": TRIAL_ID,
        "route": "diversifier_only",
        "parent_standalone_outcome": "closed_exploration",
        "parent_standalone_outcome_changed": False,
        "evaluation_start": START_DATE.date().isoformat(),
        "evaluation_end": END_DATE.date().isoformat(),
        "portfolio_construction": "monthly_rebalanced_80_20",
        "cost_assumptions_bps": list(COST_BPS),
        "frozen_exposure_SPY_weight": FROZEN_EXPOSURE_SPY_WEIGHT,
        "frozen_exposure_BIL_weight": FROZEN_EXPOSURE_BIL_WEIGHT,
        "parent_archived_exposure_control_weight": reconstructed[
            "parent_archived_exposure_weight"
        ],
        "parent_control_weight_and_route_frozen_weight_kept_distinct": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_reproduction_or_diagnostics": True,
        "new_strategy_configuration_count": 0,
        "new_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "portfolio_diagnostic_count": 7,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_yaml(OUTPUT_DIR / "followup_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategies, list(strategies[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trials, list(trials[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmarks,
        list(benchmarks[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process,
        list(process[0]),
    )
    write_csv(
        OUTPUT_DIR / "reproduction_check.csv",
        reproduction,
        [
            "portfolio_id",
            "cost_assumption_bps",
            "metric",
            "parent_recorded_value",
            "reproduced_value",
            "difference",
            "absolute_difference",
            "tolerance",
            "reproduction_pass",
        ],
    )
    write_csv(
        OUTPUT_DIR / "portfolio_control_definitions.csv",
        controls,
        list(controls[0]),
    )
    if reproduction_pass:
        result_fields = list(full_rows[0])
        write_csv(
            OUTPUT_DIR / "full_period_portfolio_results.csv",
            full_rows,
            result_fields,
        )
        write_csv(
            OUTPUT_DIR / "chronological_half_portfolio_results.csv",
            half_rows,
            list(half_rows[0]),
        )
        write_csv(
            OUTPUT_DIR / "rolling_36_month_portfolio_results.csv",
            rolling36,
            list(rolling36[0]),
        )
        write_csv(
            OUTPUT_DIR / "rolling_60_month_portfolio_results.csv",
            rolling60,
            list(rolling60[0]),
        )
        write_csv(
            OUTPUT_DIR / "rolling_window_summary.csv",
            rolling_summary,
            list(rolling_summary[0]),
        )
        write_csv(
            OUTPUT_DIR / "reference_negative_month_results.csv",
            downside,
            list(downside[0]),
        )
        write_csv(
            OUTPUT_DIR / "candidate_mechanism_diagnostics.csv",
            mechanism,
            list(mechanism[0]),
        )
        turnover_rows = [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "portfolio_id": row["portfolio_id"],
                "cost_assumption_bps": row["cost_assumption_bps"],
                "inner_turnover": row["inner_turnover"],
                "outer_turnover": row["outer_turnover"],
                "inner_transaction_cost_drag": row[
                    "inner_transaction_cost_drag"
                ],
                "outer_transaction_cost_drag": row[
                    "outer_transaction_cost_drag"
                ],
                "total_transaction_cost_drag": row[
                    "total_transaction_cost_drag"
                ],
                "costs_charged_once": True,
            }
            for row in full_rows
        ]
        write_csv(
            OUTPUT_DIR / "turnover_cost_reconciliation.csv",
            turnover_rows,
            list(turnover_rows[0]),
        )
    else:
        empty_diagnostic_files()
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariants,
        list(invariants[0]),
    )
    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "route": "diversifier_only",
        "stage": STAGE,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "parent_reproduction_pass": reproduction_pass,
        "all_invariants_pass": all_invariants_pass,
        "standalone_parent_outcome_changed": False,
        "next_action": next_action,
        "validation_claimed": False,
        "paper_demo_eligibility_authorized": False,
    }
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        [outcome_row]
        if outcome == "exploratory_followup_candidate_diversifier"
        else [],
        list(outcome_row),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [outcome_row],
        list(outcome_row),
    )
    failure_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
    }
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [failure_row] if failure_reason else [],
        list(failure_row),
    )
    next_rows = [
        {
            "scope": "child_trial",
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
        {
            "scope": "task",
            "strategy_id": STRATEGY_ID,
            "trial_id": "",
            "outcome": outcome,
            "exact_next_action": next_action,
            "execute_in_this_task": False,
        },
    ]
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0]),
    )
    funnel = {
        "existing_strategy_configuration_carried_forward_count": 1,
        "new_strategy_configuration_count": 0,
        "existing_parent_experiment_trial_carried_forward_count": 1,
        "new_experiment_trial_count": 1,
        "benchmark_reference_count": 6,
        "portfolio_diagnostic_count": 7 if reproduction_pass else 0,
        "process_task_count": 1,
        "data_capability_task_count": 0,
        "paper_demo_observation_count": 0,
        "followup_candidate_count": int(
            outcome == "exploratory_followup_candidate_diversifier"
        ),
        "closed_exploration_count": int(outcome == "closed_exploration"),
        "blocked_feasibility_count": int(outcome == "blocked_feasibility"),
    }
    funnel["outcome_count_reconciles"] = (
        funnel["followup_candidate_count"]
        + funnel["closed_exploration_count"]
        + funnel["blocked_feasibility_count"]
        == 1
    )
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)
    write_text(
        OUTPUT_DIR / "followup_report.md",
        build_report(
            outcome,
            failure_reason,
            decision_reason,
            next_action,
            full_rows,
            rolling_summary,
            reproduction_pass,
        )
        if reproduction_pass
        else (
            "# Decelerated PSAR Diversifier Incremental-Value Follow-up V1\n\n"
            f"Outcome: `{outcome}`\n\n"
            f"Failure reason: `{failure_reason}`\n\n"
            f"{decision_reason}\n\n"
            f"Exact next action: `{next_action}`\n"
        ),
    )

    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_after = map_hashes(cache_inventory_files())
    parent_after = map_hashes(parent_evidence_paths())
    source_hash_after = file_hash(SOURCE_PACKET)
    consistency = {
        "status": "pass",
        "overall_pass": bool(
            preliminary_invariants
            and protected_before == protected_after
            and cache_before == cache_after
            and parent_before == parent_after
            and source_hash_before == source_hash_after
            and outcome in ALLOWED_OUTCOMES
            and failure_reason in ALLOWED_FAILURE_REASONS
            and funnel["outcome_count_reconciles"]
        ),
        "strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "child_trial_id": TRIAL_ID,
        "exactly_one_route_specific_child_trial": True,
        "new_strategy_configuration_created": False,
        "parent_standalone_outcome_unchanged": True,
        "PSAR_formula_changed": False,
        "AF_parameters_changed": False,
        "instruments_changed": False,
        "signal_timing_changed": False,
        "execution_changed": False,
        "costs_changed": False,
        "outer_sleeve_weight_changed": False,
        "parent_reproduction_pass": reproduction_pass,
        "evaluation_period_exact": period_pass,
        "route_frozen_exposure_weight": FROZEN_EXPOSURE_SPY_WEIGHT,
        "parent_archived_exposure_control_weight": reconstructed[
            "parent_archived_exposure_weight"
        ],
        "exposure_weight_recalculated": False,
        "all_accounting_invariants_pass": all_invariants_pass,
        "portfolio_fixed_weight_daily_blend_used": False,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "canonical_caches_unchanged": cache_before == cache_after,
        "parent_evidence_hashes_before": parent_before,
        "parent_evidence_hashes_after": parent_after,
        "parent_evidence_unchanged": parent_before == parent_after,
        "parent_evidence_aggregate_hash": aggregate_hash(parent_after),
        "source_packet_hash_before": source_hash_before,
        "source_packet_hash_after": source_hash_after,
        "source_packet_unchanged": source_hash_before == source_hash_after,
        "forbidden_actions": FORBIDDEN_FLAGS,
        "entity_counts_reconcile": funnel["outcome_count_reconciles"],
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    if not consistency["overall_pass"]:
        consistency["status"] = "fail"
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "parent_reproduction_pass": reproduction_pass,
        "followup_candidate_count": funnel["followup_candidate_count"],
        "exact_next_action": next_action,
        "evidence_path": rel(OUTPUT_DIR),
        "overall_pass": consistency["overall_pass"],
        "protected_state_unchanged": consistency["protected_state_unchanged"],
        "canonical_caches_unchanged": consistency["canonical_caches_unchanged"],
        "parent_evidence_unchanged": consistency["parent_evidence_unchanged"],
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
