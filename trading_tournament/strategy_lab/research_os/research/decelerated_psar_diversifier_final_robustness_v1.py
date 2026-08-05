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
    decelerated_psar_diversifier_incremental_value_followup_v1 as exploration,
)
from strategy_lab.research_os.research import (
    fast_price_volume_preregistered_batch_v1 as standalone,
)
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    implement_targeted_multiday_mean_reversion_candidate_v1 as evidence_tools,
)


TASK_ID = "decelerated_psar_diversifier_final_robustness_v1"
MODE = "validation"
STAGE = "robustness"
OUTPUT_DIR = ROOT / "evidence" / "robustness" / TASK_ID / "latest"
SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments\46819090-8ead-4684-b70e-5adc46c8f8cf\pasted-text.txt"
)

STANDALONE_EVIDENCE = standalone.OUTPUT_DIR
EXPLORATION_EVIDENCE = exploration.OUTPUT_DIR
STRATEGY_ID = exploration.STRATEGY_ID
FAMILY_ID = exploration.FAMILY_ID
DISPLAY_NAME = exploration.DISPLAY_NAME
ARCHITECTURE = exploration.ARCHITECTURE
SOURCE_LINEAGE = exploration.SOURCE_LINEAGE
PARENT_STANDALONE_TRIAL_ID = exploration.PARENT_TRIAL_ID
PARENT_TRIAL_ID = exploration.TRIAL_ID
TRIAL_ID = f"{TASK_ID}__child"
PREREGISTRATION_TIMESTAMP = "2026-07-29T00:00:00-06:00"

START_DATE = exploration.START_DATE
END_DATE = exploration.END_DATE
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0, 15.0, 20.0)
REPRODUCTION_COST_BPS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
APPROXIMATE_EXPOSURE_SPY = 0.753493
EXACT_EXPOSURE_SPY = 0.75370177268
EXACT_EXPOSURE_BIL = 0.24629822732
BLOCK_LENGTH_MONTHS = 12
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260729
START_YEARS = (2011, 2012, 2013, 2014, 2015, 2016)
WEIGHT_TOLERANCE = 1e-9

REFERENCE_ID = "100pct_frozen_reference"
CANDIDATE_ID = "80pct_reference_20pct_decelerated_psar_candidate"
ORIGINAL_ID = "80pct_reference_20pct_original_psar_control"
EXACT_EXPOSURE_ID = "80pct_reference_20pct_exact_exposure_matched_control"
TREND_ID = "80pct_reference_20pct_SPY_200_day_trend_control"
BIL_ID = "80pct_reference_20pct_BIL"
SPY_ID = "80pct_reference_20pct_SPY_buy_and_hold"
PORTFOLIO_IDS = (
    REFERENCE_ID,
    CANDIDATE_ID,
    ORIGINAL_ID,
    EXACT_EXPOSURE_ID,
    TREND_ID,
    BIL_ID,
    SPY_ID,
)
DECISION_PORTFOLIO_IDS = (
    REFERENCE_ID,
    CANDIDATE_ID,
    ORIGINAL_ID,
    EXACT_EXPOSURE_ID,
)
BENCHMARK_IDS = (
    "frozen_current_active_vm_dsr_usci_combo",
    "original_psar_spy_bil_control",
    "exact_exposure_matched_spy_bil_control",
    "SPY_200_day_trend_control",
    "BIL_buy_and_hold",
    "SPY_buy_and_hold",
)

NEXT_POSITIVE = "design_decelerated_psar_prospective_validation_v1"
NEXT_MIXED = "defer_decelerated_psar_and_review_discovery_yield_v1"
NEXT_FAILED = "direction_owner_review_close_decelerated_psar_routes_v1"
NEXT_BLOCKED = "direction_owner_review_decelerated_psar_robustness_block_v1"

ALLOWED_OUTCOMES = {
    "robustness_positive",
    "robustness_mixed",
    "robustness_failed",
    "robustness_blocked",
}
ALLOWED_FAILURE_REASONS = {
    "",
    "concentration_risk",
    "period_instability",
    "cost_drag",
    "weak_vs_primary_control",
    "benchmark_like_behavior",
    "weak_portfolio_contribution",
    "methodology_failure",
    "data_or_comparability_failure",
    "overfit_or_unstable",
}
REQUIRED_OUTPUTS = {
    "robustness_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "reproduction_check.csv",
    "exposure_control_weight_correction.csv",
    "corrected_control_results.csv",
    "cost_stress_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "rolling_36_month_results.csv",
    "rolling_60_month_results.csv",
    "rolling_window_summary.csv",
    "start_date_sensitivity.csv",
    "monthly_excess_concentration.csv",
    "month_and_year_neutralization_results.csv",
    "defensive_episode_inventory.csv",
    "leave_one_defensive_episode_out_results.csv",
    "leave_one_defensive_episode_out_summary.csv",
    "bootstrap_results.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "robustness_report.md",
}

PROTECTED_PATHS = exploration.PROTECTED_STATE_PATHS


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def file_hash(path: Path) -> str:
    return exploration.file_hash(path)


def tree_hash(path: Path) -> str:
    return evidence_tools.tree_hash(path)


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.exists()}


def packet_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if item.is_file())


def cache_files() -> list[Path]:
    return exploration.cache_inventory_files()


def clean_output() -> None:
    expected = (ROOT / "evidence" / "robustness" / TASK_ID / "latest").resolve()
    if OUTPUT_DIR.exists():
        if OUTPUT_DIR.resolve() != expected:
            raise RuntimeError(f"Refusing to remove unexpected output: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fields_for(rows: list[dict[str, Any]], leading: list[str]) -> list[str]:
    if not rows:
        return leading
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(
    name: str,
    rows: list[dict[str, Any]],
    leading: list[str],
) -> None:
    exploration.write_csv(OUTPUT_DIR / name, rows, fields_for(rows, leading))


def write_json(name: str, payload: dict[str, Any]) -> None:
    exploration.write_json(OUTPUT_DIR / name, payload)


def write_yaml(name: str, payload: dict[str, Any]) -> None:
    exploration.write_yaml(OUTPUT_DIR / name, payload)


def write_text(name: str, text: str) -> None:
    exploration.write_text(OUTPUT_DIR / name, text)


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
        "stage": STAGE,
        "existing_strategy_configuration": True,
        "new_strategy_configuration_created": False,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "robustness_variant",
        "parameters": {
            "AF_min": 0.02,
            "AF_max": 0.20,
            "AF_forward_step": 0.02,
            "AF_backward_step": 0.05,
            "change_period_sessions": 3,
            "change_threshold": 0.02,
            "strict_acceleration_comparison": "change3 > 0.02",
            "equality_branch": "deceleration",
            "active_asset": "SPY",
            "defensive_asset": "BIL",
            "outer_reference_weight": 0.80,
            "outer_candidate_weight": 0.20,
            "corrected_exposure_control_SPY_weight": EXACT_EXPOSURE_SPY,
            "corrected_exposure_control_BIL_weight": EXACT_EXPOSURE_BIL,
        },
        "benchmark_or_control": list(BENCHMARK_IDS),
        "standalone_outcome": "closed_exploration",
        "standalone_failure_reason": "benchmark_like_behavior",
        "diversifier_exploration_outcome": (
            "exploratory_followup_candidate_diversifier"
        ),
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "independent_validation_claimed": False,
        "paper_demo_eligibility_supported": False,
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
        "changed_fields_from_parent": (
            "exact_exposure_control_weight_correction_and_robustness_diagnostics_only"
        ),
        "PSAR_formula_changed": False,
        "AF_parameters_changed": False,
        "instruments_changed": False,
        "signal_timing_changed": False,
        "execution_changed": False,
        "candidate_sleeve_changed": False,
        "reference_portfolio_changed": False,
        "candidate_cost_model_changed": False,
        "critical_control_weight_corrected": True,
        "optimization_performed": False,
        "independent_validation_claimed": False,
        "result_driven_strategy_change": False,
        "preregistered_before_robustness_calculation": True,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    roles = {
        BENCHMARK_IDS[0]: "frozen_reference",
        BENCHMARK_IDS[1]: "critical_original_psar_control",
        BENCHMARK_IDS[2]: "critical_exact_exposure_control",
        BENCHMARK_IDS[3]: "additional_trend_control",
        BENCHMARK_IDS[4]: "additional_defensive_control",
        BENCHMARK_IDS[5]: "additional_risk_asset_control",
    }
    return [
        {
            "benchmark_reference_id": benchmark_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "control_role": roles[benchmark_id],
            "critical_control": benchmark_id
            in {BENCHMARK_IDS[1], BENCHMARK_IDS[2]},
            "SPY_weight": (
                EXACT_EXPOSURE_SPY
                if benchmark_id == BENCHMARK_IDS[2]
                else "state_or_control_defined"
            ),
            "BIL_weight": (
                EXACT_EXPOSURE_BIL
                if benchmark_id == BENCHMARK_IDS[2]
                else "state_or_control_defined"
            ),
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for benchmark_id in BENCHMARK_IDS
    ]


def process_row(outcome: str, next_action: str) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "entity_type": "process_task",
        "stage": STAGE,
        "mode": MODE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_next_action_now": False,
        "counted_as_strategy": False,
        "counted_as_trial": False,
    }


def preregistered_diagnostics() -> dict[str, Any]:
    return {
        "cost_bps": list(COST_BPS),
        "quarter_count": 4,
        "complete_calendar_years": list(range(2011, 2026)),
        "rolling_horizons_months": [36, 60],
        "fixed_start_years": list(START_YEARS),
        "fixed_end": END_DATE.date().isoformat(),
        "neutralization_scenarios": [
            "strongest_positive_month",
            "three_strongest_positive_months",
            "strongest_additive_excess_calendar_year",
        ],
        "leave_one_defensive_episode_out": True,
        "bootstrap_block_length_months": BLOCK_LENGTH_MONTHS,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "paired_cross_portfolio_dependence": True,
        "same_period_evidence_is_independent_validation": False,
    }


def write_preregistration() -> str:
    strategy = strategy_row(
        "preregistered_pending_reproduction_gate",
        "",
        "execute_frozen_robustness_diagnostics",
    )
    trial = trial_row(
        "preregistered_pending_reproduction_gate",
        "",
        "execute_frozen_robustness_diagnostics",
    )
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "preregistered_diagnostics": preregistered_diagnostics(),
        "outcome": "preregistered_pending_reproduction_gate",
    }
    write_csv("strategy_cards.csv", [strategy], ["strategy_id", "trial_id"])
    write_csv("trial_ledger.csv", [trial], ["trial_id", "parent_trial_id"])
    write_yaml("robustness_manifest.yaml", manifest)
    material = (
        (OUTPUT_DIR / "strategy_cards.csv").read_bytes()
        + (OUTPUT_DIR / "trial_ledger.csv").read_bytes()
        + (OUTPUT_DIR / "robustness_manifest.yaml").read_bytes()
    )
    return "sha256:" + hashlib.sha256(material).hexdigest()


def verify_parent_packets() -> bool:
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
    standalone_rows = read_csv(STANDALONE_EVIDENCE / "outcome_summary.csv")
    standalone_matches = [
        row for row in standalone_rows if row["strategy_id"] == STRATEGY_ID
    ]
    exploration_rows = read_csv(EXPLORATION_EVIDENCE / "trial_ledger.csv")
    child = [row for row in exploration_rows if row["trial_id"] == PARENT_TRIAL_ID]
    return bool(
        standalone_check.get("overall_pass")
        and exploration_check.get("overall_pass")
        and len(standalone_matches) == 1
        and standalone_matches[0]["outcome"] == "closed_exploration"
        and standalone_matches[0]["failure_reason"] == "benchmark_like_behavior"
        and len(child) == 1
        and child[0]["parent_trial_id"] == PARENT_STANDALONE_TRIAL_ID
        and child[0]["outcome"]
        == "exploratory_followup_candidate_diversifier"
    )


def build_inner_paths() -> dict[str, Any]:
    card = exploration.parent_card()
    prepared = standalone.prepare_candidate(card)
    prices = prepared["prices"]
    approximate_events = standalone.monthly_static_events(
        prices.index, APPROXIMATE_EXPOSURE_SPY
    )
    exact_events = standalone.monthly_static_events(
        prices.index, EXACT_EXPOSURE_SPY
    )
    paths: dict[tuple[str, float], dict[str, Any]] = {}
    mapping = {
        "candidate": prepared["candidate_events"],
        "original": prepared["control_events"]["original_psar_spy_bil_control"],
        "trend": prepared["control_events"]["SPY_200_day_trend_control"],
        "BIL": prepared["control_events"]["BIL_buy_and_hold"],
        "SPY": prepared["control_events"]["SPY_buy_and_hold"],
        "approximate_exposure": approximate_events,
        "exact_exposure": exact_events,
    }
    for cost in COST_BPS:
        for inner_id, events in mapping.items():
            paths[(inner_id, cost)] = accounting.simulate_path(
                prices,
                events,
                cost,
                prepared["timing_convention"],
            )
    return {
        "card": card,
        "prepared": prepared,
        "prices": prices,
        "paths": paths,
        "archived_exact_exposure": prepared[
            "mechanical_average_target_SPY_weight"
        ],
    }


def common_index(reference: pd.Series, inner: dict[str, Any]) -> pd.DatetimeIndex:
    index = reference.dropna().index
    for inner_id in (
        "candidate",
        "original",
        "trend",
        "BIL",
        "SPY",
        "approximate_exposure",
        "exact_exposure",
    ):
        index = index.intersection(
            inner[(inner_id, PRIMARY_COST_BPS)]["returns"].dropna().index
        )
    return index[(index >= START_DATE) & (index <= END_DATE)].sort_values()


def build_portfolios(
    reference: pd.Series,
    inner: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
    exposure_inner_id: str,
    exposure_portfolio_id: str,
    costs: tuple[float, ...],
) -> dict[tuple[str, float], dict[str, Any]]:
    mapping = {
        CANDIDATE_ID: "candidate",
        ORIGINAL_ID: "original",
        exposure_portfolio_id: exposure_inner_id,
        TREND_ID: "trend",
        BIL_ID: "BIL",
        SPY_ID: "SPY",
    }
    result: dict[tuple[str, float], dict[str, Any]] = {}
    aligned_reference = reference.reindex(index)
    for cost in costs:
        result[(REFERENCE_ID, cost)] = exploration.simulate_portfolio(
            aligned_reference,
            None,
            REFERENCE_ID,
            cost,
        )
        for portfolio_id, inner_id in mapping.items():
            result[(portfolio_id, cost)] = exploration.simulate_portfolio(
                aligned_reference,
                inner[(inner_id, cost)],
                portfolio_id,
                cost,
            )
    return result


def metrics(
    path: dict[str, Any],
    period: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    return exploration.portfolio_metric_payload(path, period)


def robustness_row(
    portfolio_id: str,
    cost: float,
    period: str,
    values: dict[str, Any],
    diagnostic_type: str,
) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "entity_type": "portfolio_robustness_diagnostic",
        "stage": STAGE,
        "approved_route": "20pct_diversifier_only",
        "portfolio_id": portfolio_id,
        "cost_bps": cost,
        "period": period,
        "diagnostic_type": diagnostic_type,
        "period_independence": "same_viewed_period_not_independent_validation",
        **values,
    }


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return exploration.dominates(control, candidate)


def worse_on_both(candidate: dict[str, Any], control: dict[str, Any]) -> bool:
    return exploration.worse_on_both(candidate, control)


def material_vs_reference(
    candidate: dict[str, Any],
    reference: dict[str, Any],
) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) - float(reference["sharpe_ratio"])
        >= 0.02
        or float(candidate["maximum_drawdown"])
        - float(reference["maximum_drawdown"])
        >= 0.01
    )


def split_quarters(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    return {
        f"chronological_quarter_{position + 1}": index[positions]
        for position, positions in enumerate(np.array_split(np.arange(len(index)), 4))
    }


def monthly_returns(series: pd.Series) -> pd.Series:
    return (1.0 + series).groupby(series.index.to_period("M")).prod().sub(1.0)


def monthly_metrics(series: pd.Series) -> dict[str, Any]:
    values = series.to_numpy(dtype=float)
    wealth = np.cumprod(1.0 + values)
    count = len(values)
    std = float(np.std(values, ddof=1))
    running_max = np.maximum.accumulate(wealth)
    return {
        "evaluation_start": str(series.index[0]),
        "evaluation_end": str(series.index[-1]),
        "monthly_observations": count,
        "total_return": float(wealth[-1] - 1.0),
        "cagr": float(wealth[-1] ** (12.0 / count) - 1.0),
        "annualized_volatility": std * math.sqrt(12.0),
        "sharpe_ratio": (
            float(np.mean(values) / std * math.sqrt(12.0)) if std > 0.0 else 0.0
        ),
        "maximum_drawdown": float(np.min(wealth / running_max - 1.0)),
    }


def comparable_value(value: str) -> tuple[str, Any]:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return "bool", lowered == "true"
    if value == "":
        return "empty", ""
    try:
        number = float(value)
    except ValueError:
        return "text", value
    return "number", number


def generic_reproduction_rows(
    scope: str,
    archived: list[dict[str, str]],
    current: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    current_normalized = [
        {field: exploration.csv_value(value) for field, value in row.items()}
        for row in current
    ]
    archived_map = {tuple(row.get(key, "") for key in keys): row for row in archived}
    current_map = {
        tuple(row.get(key, "") for key in keys): row for row in current_normalized
    }
    result: list[dict[str, Any]] = []
    for key in sorted(set(archived_map) | set(current_map)):
        expected = archived_map.get(key)
        actual = current_map.get(key)
        fields = sorted(set(expected or {}) & set(actual or {}))
        for field in fields:
            expected_value = expected[field] if expected is not None else ""
            actual_value = actual[field] if actual is not None else ""
            expected_kind, expected_parsed = comparable_value(expected_value)
            actual_kind, actual_parsed = comparable_value(actual_value)
            difference: float | str = ""
            if expected_kind == actual_kind == "number":
                difference = float(actual_parsed) - float(expected_parsed)
                passed = abs(float(difference)) <= REPRODUCTION_TOLERANCE
            else:
                passed = bool(
                    expected is not None
                    and actual is not None
                    and expected_value == actual_value
                )
            result.append(
                {
                    "scope": scope,
                    "record_key": "|".join(key),
                    "field": field,
                    "archived_value": expected_value,
                    "reproduced_value": actual_value,
                    "difference": difference,
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "pass": passed,
                }
            )
    return result


def reproduction_rows(
    approximate_paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
) -> tuple[list[dict[str, Any]], bool]:
    full, halves = exploration.full_and_half_rows(approximate_paths, index)
    rolling36 = exploration.rolling_rows(approximate_paths, index, 36)
    rolling60 = exploration.rolling_rows(approximate_paths, index, 60)
    rolling_summary = exploration.rolling_summary_rows(rolling36, rolling60)
    downside = exploration.downside_rows(approximate_paths)
    invariant = exploration.invariant_rows(
        True,
        approximate_paths,
        True,
        True,
        True,
    )
    turnover = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": PARENT_TRIAL_ID,
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
        for row in full
    ]
    comparisons = (
        (
            "full_period",
            "full_period_portfolio_results.csv",
            full,
            ("portfolio_id", "cost_assumption_bps"),
        ),
        (
            "chronological_halves",
            "chronological_half_portfolio_results.csv",
            halves,
            ("portfolio_id", "period_label"),
        ),
        (
            "rolling_36_and_60_month_summaries",
            "rolling_window_summary.csv",
            rolling_summary,
            ("window_months", "comparison_portfolio_id"),
        ),
        (
            "reference_negative_months",
            "reference_negative_month_results.csv",
            downside,
            ("portfolio_id",),
        ),
        (
            "turnover_and_cost",
            "turnover_cost_reconciliation.csv",
            turnover,
            ("portfolio_id", "cost_assumption_bps"),
        ),
        (
            "parent_invariants",
            "invariant_results.csv",
            invariant,
            ("invariant_name",),
        ),
    )
    rows: list[dict[str, Any]] = []
    for scope, filename, current, keys in comparisons:
        rows.extend(
            generic_reproduction_rows(
                scope,
                read_csv(EXPLORATION_EVIDENCE / filename),
                current,
                keys,
            )
        )
    period_pass = bool(
        len(index) and index[0] == START_DATE and index[-1] == END_DATE
    )
    rows.append(
        {
            "scope": "evaluation_period",
            "record_key": "common_period",
            "field": "start_and_end",
            "archived_value": f"{START_DATE.date()}|{END_DATE.date()}",
            "reproduced_value": (
                f"{index[0].date()}|{index[-1].date()}" if len(index) else ""
            ),
            "difference": "",
            "tolerance": REPRODUCTION_TOLERANCE,
            "pass": period_pass,
        }
    )
    return rows, bool(rows and all(row["pass"] for row in rows))


def corrected_control_rows(
    exact_paths: dict[tuple[str, float], dict[str, Any]],
    approximate_paths: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    correction: list[dict[str, Any]] = []
    corrected: list[dict[str, Any]] = []
    approximate_id = (
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control"
    )
    for cost in COST_BPS:
        exact = metrics(exact_paths[(EXACT_EXPOSURE_ID, cost)])
        approximate = metrics(approximate_paths[(approximate_id, cost)])
        corrected.append(
            robustness_row(
                EXACT_EXPOSURE_ID,
                cost,
                "full_period",
                exact,
                "corrected_exact_exposure_control",
            )
        )
        correction.append(
            {
                "methodology_correction": (
                    "methodology_correction_to_exact_parent_exposure"
                ),
                "cost_bps": cost,
                "approximate_SPY_weight": APPROXIMATE_EXPOSURE_SPY,
                "exact_SPY_weight": EXACT_EXPOSURE_SPY,
                "SPY_weight_difference": (
                    EXACT_EXPOSURE_SPY - APPROXIMATE_EXPOSURE_SPY
                ),
                "approximate_BIL_weight": 1.0 - APPROXIMATE_EXPOSURE_SPY,
                "exact_BIL_weight": EXACT_EXPOSURE_BIL,
                "approximate_cagr": approximate["cagr"],
                "exact_cagr": exact["cagr"],
                "cagr_difference": float(exact["cagr"])
                - float(approximate["cagr"]),
                "approximate_sharpe_ratio": approximate["sharpe_ratio"],
                "exact_sharpe_ratio": exact["sharpe_ratio"],
                "sharpe_difference": float(exact["sharpe_ratio"])
                - float(approximate["sharpe_ratio"]),
                "approximate_maximum_drawdown": approximate[
                    "maximum_drawdown"
                ],
                "exact_maximum_drawdown": exact["maximum_drawdown"],
                "maximum_drawdown_difference": float(
                    exact["maximum_drawdown"]
                )
                - float(approximate["maximum_drawdown"]),
                "exact_control_used_for_decision": True,
                "weight_selected_from_performance": False,
            }
        )
    return correction, corrected


def rolling_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    index: pd.DatetimeIndex,
    months: int,
) -> list[dict[str, Any]]:
    month_ends = standalone.last_dates_by_period(index, "M")
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
        candidate = metrics(paths[(CANDIDATE_ID, PRIMARY_COST_BPS)], period)
        for comparator_id in (REFERENCE_ID, ORIGINAL_ID, EXACT_EXPOSURE_ID):
            comparator = metrics(
                paths[(comparator_id, PRIMARY_COST_BPS)], period
            )
            rows.append(
                {
                    "strategy_id": STRATEGY_ID,
                    "trial_id": TRIAL_ID,
                    "window_months": months,
                    "window_sequence": sequence,
                    "window_start": period[0].date().isoformat(),
                    "window_end": period[-1].date().isoformat(),
                    "candidate_portfolio_id": CANDIDATE_ID,
                    "comparison_portfolio_id": comparator_id,
                    "candidate_cagr": candidate["cagr"],
                    "comparison_cagr": comparator["cagr"],
                    "cagr_difference": float(candidate["cagr"])
                    - float(comparator["cagr"]),
                    "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                    "comparison_sharpe_ratio": comparator["sharpe_ratio"],
                    "sharpe_difference": float(candidate["sharpe_ratio"])
                    - float(comparator["sharpe_ratio"]),
                    "candidate_maximum_drawdown": candidate[
                        "maximum_drawdown"
                    ],
                    "comparison_maximum_drawdown": comparator[
                        "maximum_drawdown"
                    ],
                    "maximum_drawdown_difference": float(
                        candidate["maximum_drawdown"]
                    )
                    - float(comparator["maximum_drawdown"]),
                    "comparison_dominates_candidate": dominates(
                        comparator, candidate
                    ),
                    "candidate_improves_comparison_sharpe_or_drawdown": bool(
                        float(candidate["sharpe_ratio"])
                        > float(comparator["sharpe_ratio"])
                        or float(candidate["maximum_drawdown"])
                        > float(comparator["maximum_drawdown"])
                    ),
                    "unfavorable_window_retained": True,
                    "independent_validation_claimed": False,
                }
            )
    return rows


def rolling_summary_rows(
    rows36: list[dict[str, Any]],
    rows60: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for months, rows in ((36, rows36), (60, rows60)):
        for comparator_id in (REFERENCE_ID, ORIGINAL_ID, EXACT_EXPOSURE_ID):
            subset = [
                row
                for row in rows
                if row["comparison_portfolio_id"] == comparator_id
            ]
            result.append(
                {
                    "window_months": months,
                    "comparison_portfolio_id": comparator_id,
                    "eligible_window_count": len(subset),
                    "median_cagr_difference": float(
                        np.median([row["cagr_difference"] for row in subset])
                    ),
                    "median_sharpe_difference": float(
                        np.median([row["sharpe_difference"] for row in subset])
                    ),
                    "median_maximum_drawdown_difference": float(
                        np.median(
                            [
                                row["maximum_drawdown_difference"]
                                for row in subset
                            ]
                        )
                    ),
                    "candidate_improves_comparison_fraction": float(
                        np.mean(
                            [
                                row[
                                    "candidate_improves_comparison_sharpe_or_drawdown"
                                ]
                                for row in subset
                            ]
                        )
                    ),
                    "comparison_dominates_fraction": float(
                        np.mean(
                            [
                                row["comparison_dominates_candidate"]
                                for row in subset
                            ]
                        )
                    ),
                    "unfavorable_windows_retained": True,
                }
            )
    return result


def concentration_and_neutralization_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = (CANDIDATE_ID, REFERENCE_ID, ORIGINAL_ID, EXACT_EXPOSURE_ID)
    monthly = {
        portfolio_id: monthly_returns(
            paths[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
        )
        for portfolio_id in ids
    }
    aligned = pd.concat(
        [monthly[portfolio_id].rename(portfolio_id) for portfolio_id in ids],
        axis=1,
        join="inner",
    ).dropna()
    excess = aligned[CANDIDATE_ID] - aligned[REFERENCE_ID]
    positive = excess[excess > 0.0].sort_values(ascending=False)
    strongest_months = list(positive.index[:3])
    strongest_month = strongest_months[0]
    annual_additive = excess.groupby(excess.index.year).sum()
    strongest_year = int(annual_additive.idxmax())
    rank = {period: position + 1 for position, period in enumerate(positive.index)}
    concentration = [
        {
            "month": str(period),
            "candidate_return_5bps": aligned.loc[period, CANDIDATE_ID],
            "reference_return_5bps": aligned.loc[period, REFERENCE_ID],
            "candidate_minus_reference_additive_excess": excess.loc[period],
            "positive_excess_rank": rank.get(period, ""),
            "strongest_positive_month": period == strongest_month,
            "among_three_strongest_positive_months": period
            in strongest_months,
            "strongest_additive_excess_calendar_year": period.year
            == strongest_year,
            "frozen_before_counterfactual_calculation": True,
            "canonical_observation_deleted": False,
            "canonical_return_series_modified": False,
        }
        for period in aligned.index
    ]
    scenarios = {
        "neutralize_strongest_positive_month": [strongest_month],
        "neutralize_three_strongest_positive_months": strongest_months,
        "neutralize_strongest_additive_excess_calendar_year": [
            period for period in aligned.index if period.year == strongest_year
        ],
    }
    neutralization: list[dict[str, Any]] = []
    reference_metrics = monthly_metrics(aligned[REFERENCE_ID])
    original_metrics = monthly_metrics(aligned[ORIGINAL_ID])
    exposure_metrics = monthly_metrics(aligned[EXACT_EXPOSURE_ID])
    for scenario, periods in scenarios.items():
        counterfactual = aligned[CANDIDATE_ID].copy()
        counterfactual.loc[periods] = aligned.loc[periods, REFERENCE_ID]
        candidate_metrics = monthly_metrics(counterfactual)
        neutralization.append(
            {
                "scenario": scenario,
                "neutralized_months": [str(period) for period in periods],
                "neutralized_month_count": len(periods),
                "strongest_calendar_year": strongest_year,
                **candidate_metrics,
                "reference_cagr": reference_metrics["cagr"],
                "reference_sharpe_ratio": reference_metrics["sharpe_ratio"],
                "reference_maximum_drawdown": reference_metrics[
                    "maximum_drawdown"
                ],
                "sharpe_difference_vs_reference": float(
                    candidate_metrics["sharpe_ratio"]
                )
                - float(reference_metrics["sharpe_ratio"]),
                "maximum_drawdown_difference_vs_reference": float(
                    candidate_metrics["maximum_drawdown"]
                )
                - float(reference_metrics["maximum_drawdown"]),
                "materiality_vs_reference": material_vs_reference(
                    candidate_metrics, reference_metrics
                ),
                "original_psar_dominates": dominates(
                    original_metrics, candidate_metrics
                ),
                "exact_exposure_control_dominates": dominates(
                    exposure_metrics, candidate_metrics
                ),
                "observations_deleted": False,
                "canonical_return_series_modified": False,
                "used_for_strategy_change": False,
            }
        )
    return concentration, neutralization


def defensive_episodes(
    events: pd.DataFrame,
    prices_index: pd.DatetimeIndex,
) -> list[dict[str, Any]]:
    ordered = events.sort_index()
    prior_state = ""
    active_start: pd.Timestamp | None = None
    rows: list[dict[str, Any]] = []
    sequence = 0
    for date, target in ordered.iterrows():
        date = pd.Timestamp(date)
        state = "SPY" if float(target["SPY"]) > 0.5 else "BIL"
        if prior_state == "SPY" and state == "BIL" and date >= START_DATE:
            active_start = date
        elif (
            prior_state == "BIL"
            and state == "SPY"
            and active_start is not None
            and date <= END_DATE
        ):
            sequence += 1
            start_pos = int(prices_index.get_loc(active_start))
            end_pos = int(prices_index.get_loc(date))
            rows.append(
                {
                    "episode_id": f"defensive_episode_{sequence:03d}",
                    "BIL_entry_execution_date": active_start.date().isoformat(),
                    "SPY_reentry_execution_date": date.date().isoformat(),
                    "BIL_entry_signal_date": (
                        prices_index[start_pos - 1].date().isoformat()
                        if start_pos > 0
                        else ""
                    ),
                    "SPY_reentry_signal_date": (
                        prices_index[end_pos - 1].date().isoformat()
                        if end_pos > 0
                        else ""
                    ),
                    "defensive_holding_sessions": end_pos - start_pos,
                    "completed_episode": True,
                    "within_frozen_common_period": True,
                }
            )
            active_start = None
        prior_state = state
    return rows


def leave_one_episode_out_rows(
    episodes: list[dict[str, Any]],
    prepared: dict[str, Any],
    reference: pd.Series,
    index: pd.DatetimeIndex,
    exact_paths: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline = metrics(exact_paths[(CANDIDATE_ID, PRIMARY_COST_BPS)])
    reference_metrics = metrics(exact_paths[(REFERENCE_ID, PRIMARY_COST_BPS)])
    original = metrics(exact_paths[(ORIGINAL_ID, PRIMARY_COST_BPS)])
    exposure = metrics(exact_paths[(EXACT_EXPOSURE_ID, PRIMARY_COST_BPS)])
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        modified = prepared["candidate_events"].copy()
        start = pd.Timestamp(episode["BIL_entry_execution_date"])
        modified.loc[start, ["SPY", "BIL"]] = [1.0, 0.0]
        inner_path = accounting.simulate_path(
            prepared["prices"],
            modified,
            PRIMARY_COST_BPS,
            prepared["timing_convention"],
        )
        portfolio = exploration.simulate_portfolio(
            reference.reindex(index),
            inner_path,
            f"{CANDIDATE_ID}__{episode['episode_id']}_removed",
            PRIMARY_COST_BPS,
        )
        candidate = metrics(portfolio)
        rows.append(
            {
                **episode,
                "candidate_cagr": candidate["cagr"],
                "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                "baseline_candidate_sharpe_ratio": baseline["sharpe_ratio"],
                "sharpe_change_vs_baseline": float(candidate["sharpe_ratio"])
                - float(baseline["sharpe_ratio"]),
                "reference_sharpe_ratio": reference_metrics["sharpe_ratio"],
                "reference_maximum_drawdown": reference_metrics[
                    "maximum_drawdown"
                ],
                "sharpe_difference_vs_reference": float(
                    candidate["sharpe_ratio"]
                )
                - float(reference_metrics["sharpe_ratio"]),
                "maximum_drawdown_difference_vs_reference": float(
                    candidate["maximum_drawdown"]
                )
                - float(reference_metrics["maximum_drawdown"]),
                "still_improves_reference_sharpe_or_drawdown": bool(
                    float(candidate["sharpe_ratio"])
                    > float(reference_metrics["sharpe_ratio"])
                    or float(candidate["maximum_drawdown"])
                    > float(reference_metrics["maximum_drawdown"])
                ),
                "original_psar_dominates": dominates(original, candidate),
                "exact_exposure_control_dominates": dominates(
                    exposure, candidate
                ),
                "all_other_states_preserved": True,
                "outer_portfolio_rebuilt": True,
                "cost_model_preserved": True,
                "used_for_strategy_change": False,
            }
        )
    if not rows:
        return rows, []
    sharpe = np.array([row["candidate_sharpe_ratio"] for row in rows], dtype=float)
    drawdown_improvement = np.array(
        [row["maximum_drawdown_difference_vs_reference"] for row in rows],
        dtype=float,
    )
    greatest_loss = min(rows, key=lambda row: row["sharpe_change_vs_baseline"])
    summary = [
        {
            "completed_episode_count": len(rows),
            "minimum_leave_one_out_sharpe": float(np.min(sharpe)),
            "median_leave_one_out_sharpe": float(np.median(sharpe)),
            "maximum_leave_one_out_sharpe": float(np.max(sharpe)),
            "minimum_drawdown_improvement_vs_reference": float(
                np.min(drawdown_improvement)
            ),
            "median_drawdown_improvement_vs_reference": float(
                np.median(drawdown_improvement)
            ),
            "maximum_drawdown_improvement_vs_reference": float(
                np.max(drawdown_improvement)
            ),
            "fraction_still_improving_reference_sharpe_or_drawdown": float(
                np.mean(
                    [
                        row["still_improves_reference_sharpe_or_drawdown"]
                        for row in rows
                    ]
                )
            ),
            "fraction_dominated_by_original_psar": float(
                np.mean([row["original_psar_dominates"] for row in rows])
            ),
            "fraction_dominated_by_exact_exposure_control": float(
                np.mean(
                    [row["exact_exposure_control_dominates"] for row in rows]
                )
            ),
            "episode_with_greatest_loss_of_candidate_benefit": greatest_loss[
                "episode_id"
            ],
            "greatest_sharpe_loss_vs_baseline": greatest_loss[
                "sharpe_change_vs_baseline"
            ],
            "combinations_of_episodes_removed": False,
        }
    ]
    return rows, summary


def monthly_path_metrics(values: np.ndarray) -> tuple[float, float]:
    standard_deviation = float(np.std(values, ddof=1))
    sharpe = (
        float(np.mean(values) / standard_deviation * math.sqrt(12.0))
        if standard_deviation > 0.0
        else 0.0
    )
    wealth = np.cumprod(1.0 + values)
    drawdown = float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0))
    return sharpe, drawdown


def paired_moving_block_bootstrap(
    paths: dict[tuple[str, float], dict[str, Any]],
) -> list[dict[str, Any]]:
    ids = (CANDIDATE_ID, REFERENCE_ID, ORIGINAL_ID, EXACT_EXPOSURE_ID)
    monthly = pd.concat(
        [
            monthly_returns(
                paths[(portfolio_id, PRIMARY_COST_BPS)]["returns"]
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
    counts = {
        comparator: {"sharpe": 0, "drawdown": 0, "either": 0}
        for comparator in ids[1:]
    }
    for _ in range(BOOTSTRAP_RESAMPLES):
        starts = rng.integers(0, max_start + 1, size=block_count)
        sampled = np.concatenate(
            [
                np.arange(start, start + BLOCK_LENGTH_MONTHS)
                for start in starts
            ]
        )[:count]
        sample = values[sampled]
        candidate_sharpe, candidate_drawdown = monthly_path_metrics(sample[:, 0])
        for column, comparator in enumerate(ids[1:], start=1):
            comparator_sharpe, comparator_drawdown = monthly_path_metrics(
                sample[:, column]
            )
            better_sharpe = candidate_sharpe > comparator_sharpe
            better_drawdown = candidate_drawdown > comparator_drawdown
            counts[comparator]["sharpe"] += int(better_sharpe)
            counts[comparator]["drawdown"] += int(better_drawdown)
            counts[comparator]["either"] += int(
                better_sharpe or better_drawdown
            )
    return [
        {
            "candidate_portfolio_id": CANDIDATE_ID,
            "comparison_portfolio_id": comparator,
            "monthly_observation_count": count,
            "moving_block_length_months": BLOCK_LENGTH_MONTHS,
            "resamples": BOOTSTRAP_RESAMPLES,
            "deterministic_seed": BOOTSTRAP_SEED,
            "paired_cross_portfolio_dependence_preserved": True,
            "probability_candidate_higher_sharpe": (
                counts[comparator]["sharpe"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_less_severe_maximum_drawdown": (
                counts[comparator]["drawdown"] / BOOTSTRAP_RESAMPLES
            ),
            "probability_candidate_higher_sharpe_or_less_severe_drawdown": (
                counts[comparator]["either"] / BOOTSTRAP_RESAMPLES
            ),
            "used_for_strategy_change": False,
            "independent_validation_claimed": False,
        }
        for comparator in ids[1:]
    ]


def build_turnover_and_invariant_rows(
    full_metrics: dict[tuple[str, float], dict[str, Any]],
    reproduction_pass: bool,
    correction_pass: bool,
    protected_unchanged: bool,
    cache_unchanged: bool,
    prior_evidence_unchanged: bool,
    bootstrap_deterministic: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    turnover: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = [
        {
            "invariant_name": "exploratory_child_reproduction_within_1e_9",
            "portfolio_id": "",
            "cost_bps": "",
            "invariant_pass": reproduction_pass,
            "detail": "full, halves, rolling summaries, negative months, costs and parent invariants reproduced",
        },
        {
            "invariant_name": "exact_exposure_control_weight_reconciled",
            "portfolio_id": EXACT_EXPOSURE_ID,
            "cost_bps": "",
            "invariant_pass": correction_pass,
            "detail": "exact 0.75370177268 SPY weight used for every new decision",
        },
        {
            "invariant_name": "protected_state_unchanged",
            "portfolio_id": "",
            "cost_bps": "",
            "invariant_pass": protected_unchanged,
            "detail": "registry, roadmap, queue, family ledger and active observations unchanged",
        },
        {
            "invariant_name": "canonical_cache_unchanged",
            "portfolio_id": "",
            "cost_bps": "",
            "invariant_pass": cache_unchanged,
            "detail": "canonical cache hashes unchanged",
        },
        {
            "invariant_name": "prior_evidence_unchanged",
            "portfolio_id": "",
            "cost_bps": "",
            "invariant_pass": prior_evidence_unchanged,
            "detail": "standalone and diversifier parent packet hashes unchanged",
        },
        {
            "invariant_name": "paired_bootstrap_deterministic",
            "portfolio_id": "",
            "cost_bps": "",
            "invariant_pass": bootstrap_deterministic,
            "detail": "second calculation with seed 20260729 matched exactly",
        },
    ]
    for (portfolio_id, cost), values in full_metrics.items():
        turnover.append(
            {
                "portfolio_id": portfolio_id,
                "cost_bps": cost,
                "inner_turnover": values["inner_turnover"],
                "outer_turnover": values["outer_turnover"],
                "combined_turnover_diagnostic": float(values["inner_turnover"])
                + float(values["outer_turnover"]),
                "inner_transaction_cost_drag": values[
                    "inner_transaction_cost_drag"
                ],
                "outer_transaction_cost_drag": values[
                    "outer_transaction_cost_drag"
                ],
                "total_transaction_cost_drag": values[
                    "total_transaction_cost_drag"
                ],
                "costs_charged_once": True,
                "daily_fixed_weight_return_blend_used": False,
            }
        )
        invariants.append(
            {
                "invariant_name": f"{portfolio_id}_{cost:g}bps_accounting",
                "portfolio_id": portfolio_id,
                "cost_bps": cost,
                "invariant_pass": bool(
                    values["invariant_pass"]
                    and float(values["maximum_gross_exposure"])
                    <= 1.0 + WEIGHT_TOLERANCE
                    and float(values["maximum_daily_weight_sum"])
                    <= 1.0 + WEIGHT_TOLERANCE
                ),
                "detail": "explicit holdings, natural drift, nonnegative weights, costs once, no stale fill",
                "maximum_gross_exposure": values["maximum_gross_exposure"],
                "maximum_daily_weight_sum": values[
                    "maximum_daily_weight_sum"
                ],
                "numeric_invariant_status": values[
                    "numeric_invariant_status"
                ],
                "timing_invariant_status": values[
                    "timing_invariant_status"
                ],
                "exposure_invariant_status": values[
                    "exposure_invariant_status"
                ],
                "weight_invariant_status": values["weight_invariant_status"],
                "PSAR_formula_changed": False,
                "AF_parameters_changed": False,
                "following_session_close_execution_changed": False,
                "negative_weights_present": False,
                "leverage_used": False,
                "stale_weight_forward_fill_used": False,
            }
        )
    return turnover, invariants


def rolling_lookup(
    rows: list[dict[str, Any]],
    months: int,
    comparator_id: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["window_months"] == months
        and row["comparison_portfolio_id"] == comparator_id
    ]
    if len(matches) != 1:
        raise RuntimeError("Rolling summary identity is not unique")
    return matches[0]


def decide(
    reproduction_pass: bool,
    all_invariants_pass: bool,
    full: dict[tuple[str, float], dict[str, Any]],
    quarters: dict[tuple[str, str], dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    neutralization: list[dict[str, Any]],
    episode_summary: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> tuple[str, str, str, str, dict[str, Any]]:
    if not reproduction_pass:
        return (
            "robustness_blocked",
            "data_or_comparability_failure",
            NEXT_BLOCKED,
            "historical_robustness_not_established",
            {"reproduction_and_invariants_pass": False},
        )
    if not all_invariants_pass:
        return (
            "robustness_blocked",
            "methodology_failure",
            NEXT_BLOCKED,
            "historical_robustness_not_established",
            {"reproduction_and_invariants_pass": False},
        )
    candidate = full[(CANDIDATE_ID, PRIMARY_COST_BPS)]
    reference = full[(REFERENCE_ID, PRIMARY_COST_BPS)]
    original = full[(ORIGINAL_ID, PRIMARY_COST_BPS)]
    exposure = full[(EXACT_EXPOSURE_ID, PRIMARY_COST_BPS)]
    full_material = material_vs_reference(candidate, reference)
    controls_not_dominating = bool(
        not dominates(original, candidate) and not dominates(exposure, candidate)
    )
    improving_quarters = 0
    worse_both_exposure_quarters = 0
    for quarter in (
        "chronological_quarter_1",
        "chronological_quarter_2",
        "chronological_quarter_3",
        "chronological_quarter_4",
    ):
        candidate_quarter = quarters[(CANDIDATE_ID, quarter)]
        reference_quarter = quarters[(REFERENCE_ID, quarter)]
        exposure_quarter = quarters[(EXACT_EXPOSURE_ID, quarter)]
        improving_quarters += int(
            float(candidate_quarter["sharpe_ratio"])
            > float(reference_quarter["sharpe_ratio"])
            or float(candidate_quarter["maximum_drawdown"])
            > float(reference_quarter["maximum_drawdown"])
        )
        worse_both_exposure_quarters += int(
            worse_on_both(candidate_quarter, exposure_quarter)
        )
    rolling_reference = all(
        float(
            rolling_lookup(
                rolling_summary, months, REFERENCE_ID
            )["candidate_improves_comparison_fraction"]
        )
        > 0.50
        for months in (36, 60)
    )
    rolling_controls = all(
        float(
            rolling_lookup(
                rolling_summary, months, comparator
            )["comparison_dominates_fraction"]
        )
        <= 0.50
        for months in (36, 60)
        for comparator in (ORIGINAL_ID, EXACT_EXPOSURE_ID)
    )
    cost15 = not worse_on_both(
        full[(CANDIDATE_ID, 15.0)], full[(REFERENCE_ID, 15.0)]
    )
    cost15_improves = bool(
        float(full[(CANDIDATE_ID, 15.0)]["sharpe_ratio"])
        > float(full[(REFERENCE_ID, 15.0)]["sharpe_ratio"])
        or float(full[(CANDIDATE_ID, 15.0)]["maximum_drawdown"])
        > float(full[(REFERENCE_ID, 15.0)]["maximum_drawdown"])
    )
    cost20 = not worse_on_both(
        full[(CANDIDATE_ID, 20.0)], full[(REFERENCE_ID, 20.0)]
    )
    neutral = {row["scenario"]: row for row in neutralization}
    concentration_three = bool(
        neutral["neutralize_three_strongest_positive_months"][
            "materiality_vs_reference"
        ]
    )
    concentration_year = bool(
        neutral["neutralize_strongest_additive_excess_calendar_year"][
            "materiality_vs_reference"
        ]
    )
    episodes = episode_summary[0]
    episode_reference = bool(
        float(
            episodes[
                "fraction_still_improving_reference_sharpe_or_drawdown"
            ]
        )
        >= 0.75
    )
    episode_controls = bool(
        float(episodes["fraction_dominated_by_original_psar"]) <= 0.50
        and float(
            episodes["fraction_dominated_by_exact_exposure_control"]
        )
        <= 0.50
    )
    bootstrap_map = {
        row["comparison_portfolio_id"]: row for row in bootstrap
    }
    bootstrap_reference = bool(
        float(
            bootstrap_map[REFERENCE_ID][
                "probability_candidate_higher_sharpe"
            ]
        )
        >= 0.75
        and float(
            bootstrap_map[REFERENCE_ID][
                "probability_candidate_less_severe_maximum_drawdown"
            ]
        )
        >= 0.75
    )
    bootstrap_controls = all(
        float(
            bootstrap_map[comparator][
                "probability_candidate_higher_sharpe_or_less_severe_drawdown"
            ]
        )
        >= 0.60
        for comparator in (ORIGINAL_ID, EXACT_EXPOSURE_ID)
    )
    gate = {
        "reproduction_and_invariants_pass": True,
        "material_improvement_vs_reference": full_material,
        "critical_controls_do_not_dominate_full_period": controls_not_dominating,
        "quarters_improving_reference": improving_quarters,
        "at_least_three_quarters_improve_reference": improving_quarters >= 3,
        "quarters_worse_both_vs_exact_exposure": (
            worse_both_exposure_quarters
        ),
        "worse_both_vs_exact_exposure_in_at_most_one_quarter": (
            worse_both_exposure_quarters <= 1
        ),
        "rolling_sets_improve_reference_more_than_half": rolling_reference,
        "critical_controls_dominate_at_most_half_rolling_windows": (
            rolling_controls
        ),
        "15bps_improves_reference": cost15_improves,
        "15bps_not_worse_both_vs_reference": cost15,
        "20bps_not_worse_both_vs_reference": cost20,
        "three_strongest_months_neutralized_materiality_pass": (
            concentration_three
        ),
        "strongest_year_neutralized_materiality_pass": concentration_year,
        "leave_one_episode_reference_fraction_pass": episode_reference,
        "leave_one_episode_control_dominance_pass": episode_controls,
        "bootstrap_reference_thresholds_pass": bootstrap_reference,
        "bootstrap_critical_control_thresholds_pass": bootstrap_controls,
        "bootstrap_probabilities": bootstrap_map,
    }
    required = (
        "material_improvement_vs_reference",
        "critical_controls_do_not_dominate_full_period",
        "at_least_three_quarters_improve_reference",
        "worse_both_vs_exact_exposure_in_at_most_one_quarter",
        "rolling_sets_improve_reference_more_than_half",
        "critical_controls_dominate_at_most_half_rolling_windows",
        "15bps_improves_reference",
        "20bps_not_worse_both_vs_reference",
        "three_strongest_months_neutralized_materiality_pass",
        "strongest_year_neutralized_materiality_pass",
        "leave_one_episode_reference_fraction_pass",
        "leave_one_episode_control_dominance_pass",
        "bootstrap_reference_thresholds_pass",
        "bootstrap_critical_control_thresholds_pass",
    )
    if all(bool(gate[key]) for key in required):
        return (
            "robustness_positive",
            "",
            NEXT_POSITIVE,
            "ready_for_prospective_validation_design",
            gate,
        )
    core_favorable = bool(
        full_material
        and controls_not_dominating
        and improving_quarters >= 3
        and worse_both_exposure_quarters <= 1
        and rolling_reference
        and rolling_controls
    )
    if core_favorable:
        if not (cost15_improves and cost20):
            reason = "cost_drag"
        elif not (concentration_three and concentration_year):
            reason = "concentration_risk"
        elif not (episode_reference and episode_controls):
            reason = "concentration_risk"
        else:
            reason = "overfit_or_unstable"
        return (
            "robustness_mixed",
            reason,
            NEXT_MIXED,
            "historically_promising_but_not_ready_for_prospective_validation",
            gate,
        )
    if not controls_not_dominating or not rolling_controls:
        reason = "weak_vs_primary_control"
    elif not full_material:
        reason = "weak_portfolio_contribution"
    elif improving_quarters < 3 or not rolling_reference:
        reason = "period_instability"
    elif not (cost15_improves and cost20):
        reason = "cost_drag"
    elif not (concentration_three and concentration_year):
        reason = "concentration_risk"
    else:
        reason = "overfit_or_unstable"
    return (
        "robustness_failed",
        reason,
        NEXT_FAILED,
        "historical_robustness_failed",
        gate,
    )


def build_report(
    outcome: str,
    failure_reason: str,
    interpretation: str,
    next_action: str,
    full: dict[tuple[str, float], dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
    episode_summary: list[dict[str, Any]],
    bootstrap: list[dict[str, Any]],
) -> str:
    primary = {
        portfolio_id: full[(portfolio_id, PRIMARY_COST_BPS)]
        for portfolio_id in DECISION_PORTFOLIO_IDS
    }
    lines = [
        "# Decelerated PSAR Diversifier Final Robustness V1",
        "",
        "## Scope",
        "",
        (
            "This packet evaluates the frozen 20% diversifier route over the "
            "already-viewed 2010-08-10 through 2026-06-18 period. It is final "
            "historical robustness evidence, not independent validation."
        ),
        "",
        "The standalone closure and exploratory diversifier outcome remain unchanged.",
        "",
        "## Exposure Correction",
        "",
        (
            "The exploratory `0.753493` SPY exposure control was reproduced first. "
            "All new decisions use the mechanically archived exact control weight "
            "`0.75370177268` under `methodology_correction_to_exact_parent_exposure`."
        ),
        "",
        "## Primary Results",
        "",
        "| Portfolio | CAGR | Sharpe | Maximum drawdown |",
        "|---|---:|---:|---:|",
    ]
    for portfolio_id in DECISION_PORTFOLIO_IDS:
        row = primary[portfolio_id]
        lines.append(
            f"| {portfolio_id} | {float(row['cagr']):.3%} | "
            f"{float(row['sharpe_ratio']):.3f} | "
            f"{float(row['maximum_drawdown']):.3%} |"
        )
    lines.extend(
        [
            "",
            "## Rolling Evidence",
            "",
            "| Window | Comparator | Improvement fraction | Domination fraction |",
            "|---:|---|---:|---:|",
        ]
    )
    for row in rolling_summary:
        lines.append(
            f"| {row['window_months']}m | {row['comparison_portfolio_id']} | "
            f"{float(row['candidate_improves_comparison_fraction']):.1%} | "
            f"{float(row['comparison_dominates_fraction']):.1%} |"
        )
    episode = episode_summary[0]
    lines.extend(
        [
            "",
            "## Episode And Bootstrap Diagnostics",
            "",
            (
                f"Completed defensive episodes: `{episode['completed_episode_count']}`. "
                "The fraction of leave-one-episode-out cases still improving reference "
                f"Sharpe or drawdown was "
                f"`{float(episode['fraction_still_improving_reference_sharpe_or_drawdown']):.1%}`."
            ),
            "",
            "| Comparator | P(higher Sharpe) | P(less severe drawdown) | P(either) |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in bootstrap:
        lines.append(
            f"| {row['comparison_portfolio_id']} | "
            f"{float(row['probability_candidate_higher_sharpe']):.1%} | "
            f"{float(row['probability_candidate_less_severe_maximum_drawdown']):.1%} | "
            f"{float(row['probability_candidate_higher_sharpe_or_less_severe_drawdown']):.1%} |"
        )
    lines.extend(
        [
            "",
            "## Outcome",
            "",
            f"* Outcome: `{outcome}`",
            f"* Interpretation: `{interpretation}`",
            (
                f"* Failure reason: `{failure_reason}`"
                if failure_reason
                else "* Failure reason: none"
            ),
            "",
            "No strategy rule, parameter, instrument, timing convention, reference, or sleeve weight changed.",
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
    if not verify_parent_packets():
        raise RuntimeError("Authoritative PSAR parent packets do not reconcile")
    standalone_before = map_hashes(packet_files(STANDALONE_EVIDENCE))
    exploration_before = map_hashes(packet_files(EXPLORATION_EVIDENCE))
    protected_before = map_hashes(PROTECTED_PATHS)
    cache_before = map_hashes(cache_files())
    source_before = file_hash(SOURCE_PACKET)

    clean_output()
    preregistration_hash = write_preregistration()

    reconstructed = build_inner_paths()
    reference = standalone.market.active_vm_dsr_usci_reference_returns()
    index = common_index(reference, reconstructed["paths"])
    approximate_paths = build_portfolios(
        reference,
        reconstructed["paths"],
        index,
        "approximate_exposure",
        "80pct_reference_20pct_decelerated_psar_exposure_matched_control",
        COST_BPS,
    )
    reproduction, reproduction_pass = reproduction_rows(
        approximate_paths, index
    )

    exact_paths = build_portfolios(
        reference,
        reconstructed["paths"],
        index,
        "exact_exposure",
        EXACT_EXPOSURE_ID,
        COST_BPS,
    )
    correction_rows, corrected_rows = corrected_control_rows(
        exact_paths, approximate_paths
    )
    correction_pass = bool(
        abs(
            float(reconstructed["archived_exact_exposure"])
            - EXACT_EXPOSURE_SPY
        )
        <= 1e-9
        and all(row["exact_control_used_for_decision"] for row in correction_rows)
    )

    full_metrics: dict[tuple[str, float], dict[str, Any]] = {}
    cost_rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        for cost in COST_BPS:
            value = metrics(exact_paths[(portfolio_id, cost)])
            full_metrics[(portfolio_id, cost)] = value
            cost_rows.append(
                robustness_row(
                    portfolio_id,
                    cost,
                    "full_period",
                    value,
                    "cost_stress",
                )
            )

    quarter_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    quarter_rows: list[dict[str, Any]] = []
    for quarter, period in split_quarters(index).items():
        for portfolio_id in PORTFOLIO_IDS:
            value = metrics(
                exact_paths[(portfolio_id, PRIMARY_COST_BPS)], period
            )
            quarter_metrics[(portfolio_id, quarter)] = value
            quarter_rows.append(
                robustness_row(
                    portfolio_id,
                    PRIMARY_COST_BPS,
                    quarter,
                    value,
                    "chronological_quarter",
                )
            )

    year_rows: list[dict[str, Any]] = []
    complete_years = range(index[0].year + 1, index[-1].year)
    for year in complete_years:
        period = index[index.year == year]
        for portfolio_id in PORTFOLIO_IDS:
            row = robustness_row(
                portfolio_id,
                PRIMARY_COST_BPS,
                f"calendar_year_{year}",
                metrics(
                    exact_paths[(portfolio_id, PRIMARY_COST_BPS)], period
                ),
                "complete_calendar_year",
            )
            row["calendar_year"] = year
            row["complete_calendar_year"] = True
            year_rows.append(row)

    rolling36 = rolling_rows(exact_paths, index, 36)
    rolling60 = rolling_rows(exact_paths, index, 60)
    rolling_summary = rolling_summary_rows(rolling36, rolling60)

    start_rows: list[dict[str, Any]] = []
    for year in START_YEARS:
        eligible = index[index.year >= year]
        start = eligible[0]
        period = index[index >= start]
        for portfolio_id in PORTFOLIO_IDS:
            row = robustness_row(
                portfolio_id,
                PRIMARY_COST_BPS,
                f"deterministic_start_{year}",
                metrics(
                    exact_paths[(portfolio_id, PRIMARY_COST_BPS)], period
                ),
                "start_date_sensitivity",
            )
            row.update(
                {
                    "requested_start_year": year,
                    "deterministic_start_date": start.date().isoformat(),
                    "fixed_end_date": END_DATE.date().isoformat(),
                    "start_selected_from_performance": False,
                }
            )
            start_rows.append(row)

    concentration, neutralization = concentration_and_neutralization_rows(
        exact_paths
    )
    episodes = defensive_episodes(
        reconstructed["prepared"]["candidate_events"],
        reconstructed["prices"].index,
    )
    leave_one_rows, leave_one_summary = leave_one_episode_out_rows(
        episodes,
        reconstructed["prepared"],
        reference,
        index,
        exact_paths,
    )
    bootstrap = paired_moving_block_bootstrap(exact_paths)
    bootstrap_repeat = paired_moving_block_bootstrap(exact_paths)
    bootstrap_deterministic = bootstrap == bootstrap_repeat

    protected_mid = map_hashes(PROTECTED_PATHS)
    cache_mid = map_hashes(cache_files())
    standalone_mid = map_hashes(packet_files(STANDALONE_EVIDENCE))
    exploration_mid = map_hashes(packet_files(EXPLORATION_EVIDENCE))
    turnover, invariant_rows = build_turnover_and_invariant_rows(
        full_metrics,
        reproduction_pass,
        correction_pass,
        protected_before == protected_mid,
        cache_before == cache_mid,
        standalone_before == standalone_mid
        and exploration_before == exploration_mid,
        bootstrap_deterministic,
    )
    all_invariants_pass = bool(
        invariant_rows and all(row["invariant_pass"] for row in invariant_rows)
    )
    outcome, failure_reason, next_action, interpretation, gate = decide(
        reproduction_pass,
        all_invariants_pass,
        full_metrics,
        quarter_metrics,
        rolling_summary,
        neutralization,
        leave_one_summary,
        bootstrap,
    )

    strategy = strategy_row(outcome, failure_reason, next_action)
    trial = trial_row(outcome, failure_reason, next_action)
    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "approved_route": "20pct_diversifier_only",
        "common_period_start": index[0].date().isoformat(),
        "common_period_end": index[-1].date().isoformat(),
        "approximate_parent_exposure_SPY_weight": APPROXIMATE_EXPOSURE_SPY,
        "corrected_exact_exposure_SPY_weight": EXACT_EXPOSURE_SPY,
        "corrected_exact_exposure_BIL_weight": EXACT_EXPOSURE_BIL,
        "exposure_methodology_correction": (
            "methodology_correction_to_exact_parent_exposure"
        ),
        "preregistered_diagnostics": preregistered_diagnostics(),
        "preregistration_checkpoint_hash": preregistration_hash,
        "preregistration_written_before_robustness_calculation": True,
        "existing_strategy_configurations": 1,
        "new_strategy_configurations": 0,
        "existing_exploration_trials_carried_forward": 2,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "counterfactual_diagnostics": 3,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations": 0,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "outcome_interpretation": interpretation,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }

    write_yaml("robustness_manifest.yaml", manifest)
    write_csv("strategy_cards.csv", [strategy], ["strategy_id", "trial_id"])
    write_csv("trial_ledger.csv", [trial], ["trial_id", "parent_trial_id"])
    write_csv(
        "benchmark_reference_log.csv",
        benchmark_rows(),
        ["benchmark_reference_id"],
    )
    write_csv(
        "process_task_log.csv",
        [process_row(outcome, next_action)],
        ["task_id"],
    )
    write_csv(
        "reproduction_check.csv",
        reproduction,
        ["scope", "record_key", "field"],
    )
    write_csv(
        "exposure_control_weight_correction.csv",
        correction_rows,
        ["methodology_correction", "cost_bps"],
    )
    write_csv(
        "corrected_control_results.csv",
        corrected_rows,
        ["portfolio_id", "cost_bps"],
    )
    write_csv(
        "cost_stress_results.csv",
        cost_rows,
        ["portfolio_id", "cost_bps"],
    )
    write_csv(
        "chronological_quarter_results.csv",
        quarter_rows,
        ["portfolio_id", "period"],
    )
    write_csv(
        "calendar_year_results.csv",
        year_rows,
        ["portfolio_id", "calendar_year"],
    )
    write_csv(
        "rolling_36_month_results.csv",
        rolling36,
        ["window_sequence", "comparison_portfolio_id"],
    )
    write_csv(
        "rolling_60_month_results.csv",
        rolling60,
        ["window_sequence", "comparison_portfolio_id"],
    )
    write_csv(
        "rolling_window_summary.csv",
        rolling_summary,
        ["window_months", "comparison_portfolio_id"],
    )
    write_csv(
        "start_date_sensitivity.csv",
        start_rows,
        ["requested_start_year", "portfolio_id"],
    )
    write_csv(
        "monthly_excess_concentration.csv",
        concentration,
        ["month"],
    )
    write_csv(
        "month_and_year_neutralization_results.csv",
        neutralization,
        ["scenario"],
    )
    write_csv(
        "defensive_episode_inventory.csv",
        episodes,
        ["episode_id"],
    )
    write_csv(
        "leave_one_defensive_episode_out_results.csv",
        leave_one_rows,
        ["episode_id"],
    )
    write_csv(
        "leave_one_defensive_episode_out_summary.csv",
        leave_one_summary,
        ["completed_episode_count"],
    )
    write_csv(
        "bootstrap_results.csv",
        bootstrap,
        ["comparison_portfolio_id"],
    )
    write_csv(
        "turnover_cost_reconciliation.csv",
        turnover,
        ["portfolio_id", "cost_bps"],
    )
    write_csv(
        "invariant_results.csv",
        invariant_rows,
        ["invariant_name", "portfolio_id", "cost_bps"],
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
        "standalone_closure_preserved": True,
        "exploratory_diversifier_outcome_preserved": True,
        "independent_validation_claimed": False,
        "paper_demo_eligibility_supported": False,
        "robustness_gate": gate,
    }
    write_csv("outcome_summary.csv", [outcome_row], ["strategy_id", "outcome"])
    failure_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "gate": gate,
    }
    write_csv(
        "failure_reasons.csv",
        [failure_row] if failure_reason else [],
        ["strategy_id", "trial_id", "outcome", "failure_reason", "gate"],
    )
    write_csv(
        "next_actions.csv",
        [
            {
                "scope": "robustness_trial",
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
        ],
        ["scope", "strategy_id", "trial_id"],
    )
    write_text(
        "robustness_report.md",
        build_report(
            outcome,
            failure_reason,
            interpretation,
            next_action,
            full_metrics,
            rolling_summary,
            leave_one_summary,
            bootstrap,
        ),
    )

    protected_after = map_hashes(PROTECTED_PATHS)
    cache_after = map_hashes(cache_files())
    standalone_after = map_hashes(packet_files(STANDALONE_EVIDENCE))
    exploration_after = map_hashes(packet_files(EXPLORATION_EVIDENCE))
    source_after = file_hash(SOURCE_PACKET)
    required_outputs_exact = {
        item.name for item in OUTPUT_DIR.iterdir() if item.is_file()
    } == REQUIRED_OUTPUTS - {"consistency_check.json"}
    consistency = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "overall_pass": bool(
            reproduction_pass
            and all_invariants_pass
            and outcome in ALLOWED_OUTCOMES
            and failure_reason in ALLOWED_FAILURE_REASONS
            and protected_before == protected_after
            and cache_before == cache_after
            and standalone_before == standalone_after
            and exploration_before == exploration_after
            and source_before == source_after
            and required_outputs_exact
        ),
        "required_outputs_exact": required_outputs_exact,
        "required_outputs_exact_before_consistency_write": (
            required_outputs_exact
        ),
        "parent_packets_verified": True,
        "reproduction_passed": reproduction_pass,
        "exposure_control_correction_passed": correction_pass,
        "all_invariants_passed": all_invariants_pass,
        "preregistration_written_before_robustness_calculation": True,
        "existing_strategy_configurations": 1,
        "new_strategy_configurations": 0,
        "existing_exploration_trials_carried_forward": 2,
        "new_robustness_trials": 1,
        "benchmark_references": 6,
        "process_tasks": 1,
        "data_capability_tasks": 0,
        "paper_demo_observations_created": 0,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_hashes_before": cache_before,
        "cache_hashes_after": cache_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "standalone_evidence_hashes_before": standalone_before,
        "standalone_evidence_hashes_after": standalone_after,
        "standalone_evidence_unchanged": standalone_before == standalone_after,
        "exploration_evidence_hashes_before": exploration_before,
        "exploration_evidence_hashes_after": exploration_after,
        "exploration_evidence_unchanged": (
            exploration_before == exploration_after
        ),
        "prior_evidence_unchanged": (
            standalone_before == standalone_after
            and exploration_before == exploration_after
        ),
        "source_packet_unchanged": source_before == source_after,
        "serial_rerun_deterministic": bootstrap_deterministic,
        "PSAR_formula_changed": False,
        "AF_parameters_changed": False,
        "candidate_sleeve_weight_changed": False,
        "reference_portfolio_changed": False,
        "provider_access": False,
        "network_access": False,
        "lifecycle_state_changed": False,
        "independent_validation_claimed": False,
        "paper_demo_action": False,
        "broker_orders": 0,
        "real_money_actions": 0,
        "next_action_executed": False,
        "no_further_same_period_PSAR_diagnostic_authorized": True,
    }
    write_json("consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "outcome_interpretation": interpretation,
        "exact_next_action": next_action,
        "reproduction_passed": reproduction_pass,
        "all_invariants_passed": all_invariants_pass,
        "overall_pass": consistency["overall_pass"],
        "evidence_path": rel(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
