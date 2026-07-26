from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_source_library_batch_v6 as v6


TASK_ID = "verify_and_correct_high52_v6_followup_gate_v1"
MODE = "verify"
STAGE = "verification"
ADAPTATION_LABEL = "methodology_correction"
STRATEGY_ID = "george_hwang_52week_high_sector_v1"
FAMILY_ID = "industry_anchor_momentum"
TRIAL_ID = f"fast_source_v6__{STRATEGY_ID}__canonical"
SAME_PURPOSE_CONTROL = "six_month_total_return_top3_overlapping"
CONTROL_IDS = (
    SAME_PURPOSE_CONTROL,
    "monthly_equal_weight_nine_sector",
    "SPY_buy_and_hold",
)
PRIMARY_COST_BPS = 5.0
REPRODUCTION_TOLERANCE = 1e-9
CORRECTED_OUTCOME = "closed_exploration"
CORRECTED_STAGE = "closed"
FAILURE_REASON = "period_instability"
DECISION_REASON = (
    "candidate_worse_than_same_purpose_control_on_both_sharpe_and_drawdown_"
    "in_second_chronological_half"
)
STRATEGY_NEXT_ACTION = (
    "retain_exact_configuration_as_closed_exploration_no_parameter_changes"
)
PROJECT_NEXT_ACTION = "evaluate_deferred_v3_online_portfolio_candidates_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_high52_v6_reproduction_block_v1"

OUTPUT_DIR = (
    ROOT
    / "evidence"
    / "correction"
    / TASK_ID
    / "latest"
)
V6_EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "research_recovery"
    / v6.BATCH_ID
    / "latest"
)
FROZEN_SOURCE_PACKET = Path(
    r"C:\Users\te3442\.codex\attachments"
    r"\610a14bd-9271-4fd7-a886-c4334e04e773\pasted-text.txt"
)

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

REQUIRED_V6_FILES = (
    "batch_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "high52_vintage_diagnostics.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "consistency_check.json",
)

NUMERIC_METRIC_FIELDS = (
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
)
STATUS_METRIC_FIELDS = (
    "numeric_invariant_status",
    "timing_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


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
    files: list[Path] = []
    for path in sorted((ROOT / "evidence").rglob("*")):
        if not path.is_file():
            continue
        if OUTPUT_DIR.resolve() in path.resolve().parents:
            continue
        files.append(path)
    return files


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "correction" / TASK_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def cost_label(cost: float) -> str:
    return str(int(cost)) if float(cost).is_integer() else str(cost)


def high52_card() -> v6.CandidateCard:
    cards = [card for card in v6.CARDS if card.strategy_id == STRATEGY_ID]
    if len(cards) != 1:
        raise RuntimeError(f"Expected one frozen High52 card, found {len(cards)}")
    card = cards[0]
    if (
        card.family_id != FAMILY_ID
        or card.controls != CONTROL_IDS
        or card.route != "standalone"
        or card.parameters["high_lookback_sessions"] != 252
        or card.parameters["selected_count"] != 3
        or card.parameters["holding_months"] != 6
        or card.parameters["maximum_vintages"] != 6
    ):
        raise RuntimeError("Frozen High52 identity or strategy fields changed")
    return card


def recompute_paths(
    card: v6.CandidateCard,
) -> tuple[
    dict[float, dict[str, Any]],
    dict[tuple[str, float], dict[str, Any]],
]:
    prepared = v6.prepare_candidate(card)
    if tuple(prepared["control_events"]) != CONTROL_IDS:
        raise RuntimeError("Frozen High52 controls changed")
    candidate_paths: dict[float, dict[str, Any]] = {}
    control_paths: dict[tuple[str, float], dict[str, Any]] = {}
    for cost in v6.COST_BPS:
        candidate_paths[cost] = v6.accounting.simulate_path(
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            prepared["timing_convention"],
        )
        for control_id, events in prepared["control_events"].items():
            control_paths[(control_id, cost)] = v6.accounting.simulate_path(
                prepared["prices"],
                events,
                cost,
                prepared["timing_convention"],
            )
    return candidate_paths, control_paths


def source_metric_rows() -> dict[tuple[str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str], dict[str, str]] = {}
    sources = (
        ("all_trial_results.csv", "full_period"),
        ("control_results.csv", "full_period"),
        ("chronological_half_results.csv", ""),
    )
    for filename, forced_period in sources:
        for row in read_csv(V6_EVIDENCE_DIR / filename):
            if row["strategy_id"] != STRATEGY_ID:
                continue
            period = forced_period or row["period_label"]
            control_id = row.get("control_id", "")
            row_type = "control" if control_id else "candidate"
            key = (row_type, control_id, row["cost_assumption_bps"], period)
            row = dict(row)
            row["_source_file"] = filename
            lookup[key] = row
    return lookup


def metric_reproduction_rows(
    card: v6.CandidateCard,
    candidate_paths: dict[float, dict[str, Any]],
    control_paths: dict[tuple[str, float], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, float, str], dict[str, Any]]]:
    stored = source_metric_rows()
    output: list[dict[str, Any]] = []
    recomputed: dict[tuple[str, str, float, str], dict[str, Any]] = {}
    for cost in v6.COST_BPS:
        for row_type, control_id in [
            ("candidate", ""),
            *(("control", value) for value in CONTROL_IDS),
        ]:
            path = (
                candidate_paths[cost]
                if row_type == "candidate"
                else control_paths[(control_id, cost)]
            )
            periods: list[tuple[str, pd.DatetimeIndex | None]] = [
                ("full_period", None),
                *v6.split_periods(path["returns"].index),
            ]
            for period_label, period_index in periods:
                actual = v6.strategy_metrics(path, period_index)
                recomputed[(row_type, control_id, cost, period_label)] = actual
                source_key = (
                    row_type,
                    control_id,
                    cost_label(cost),
                    period_label,
                )
                expected = stored.get(source_key)
                if expected is None:
                    raise RuntimeError(f"Missing V6 metric row {source_key}")
                numeric_differences = {
                    field: abs(float(actual[field]) - float(expected[field]))
                    for field in NUMERIC_METRIC_FIELDS
                }
                date_mismatches = [
                    field
                    for field in ("evaluation_start", "evaluation_end")
                    if str(actual[field]) != expected[field]
                ]
                status_mismatches = [
                    field
                    for field in STATUS_METRIC_FIELDS
                    if csv_value(actual[field]) != expected[field]
                ]
                numeric_mismatches = [
                    field
                    for field, difference in numeric_differences.items()
                    if difference > REPRODUCTION_TOLERANCE
                ]
                mismatch_fields = (
                    date_mismatches + numeric_mismatches + status_mismatches
                )
                output.append(
                    {
                        "strategy_id": STRATEGY_ID,
                        "trial_id": TRIAL_ID,
                        "row_type": row_type,
                        "control_id": control_id,
                        "cost_assumption_bps": cost,
                        "period_label": period_label,
                        "source_evidence_file": expected["_source_file"],
                        "stored_evaluation_start": expected["evaluation_start"],
                        "recomputed_evaluation_start": actual["evaluation_start"],
                        "stored_evaluation_end": expected["evaluation_end"],
                        "recomputed_evaluation_end": actual["evaluation_end"],
                        "stored_total_return": expected["total_return"],
                        "recomputed_total_return": actual["total_return"],
                        "stored_cagr": expected["cagr"],
                        "recomputed_cagr": actual["cagr"],
                        "stored_annualized_volatility": expected[
                            "annualized_volatility"
                        ],
                        "recomputed_annualized_volatility": actual[
                            "annualized_volatility"
                        ],
                        "stored_sharpe_ratio": expected["sharpe_ratio"],
                        "recomputed_sharpe_ratio": actual["sharpe_ratio"],
                        "stored_maximum_drawdown": expected["maximum_drawdown"],
                        "recomputed_maximum_drawdown": actual["maximum_drawdown"],
                        "stored_turnover": expected["turnover"],
                        "recomputed_turnover": actual["turnover"],
                        "stored_transaction_cost_drag": expected[
                            "transaction_cost_drag"
                        ],
                        "recomputed_transaction_cost_drag": actual[
                            "transaction_cost_drag"
                        ],
                        "stored_maximum_gross_exposure": expected[
                            "maximum_gross_exposure"
                        ],
                        "recomputed_maximum_gross_exposure": actual[
                            "maximum_gross_exposure"
                        ],
                        "stored_maximum_daily_weight_sum": expected[
                            "maximum_daily_weight_sum"
                        ],
                        "recomputed_maximum_daily_weight_sum": actual[
                            "maximum_daily_weight_sum"
                        ],
                        "stored_invariant_pass": expected["invariant_pass"],
                        "recomputed_invariant_pass": actual["invariant_pass"],
                        "maximum_absolute_numeric_difference": max(
                            numeric_differences.values()
                        ),
                        "documented_reproduction_tolerance": (
                            REPRODUCTION_TOLERANCE
                        ),
                        "mismatch_fields": mismatch_fields,
                        "reproduction_pass": not mismatch_fields,
                    }
                )
    return output, recomputed


def gate_inputs(
    metrics: dict[tuple[str, str, float, str], dict[str, Any]],
    row_type: str,
    control_id: str,
    cost: float,
    period: str,
) -> dict[str, Any]:
    return metrics[(row_type, control_id, cost, period)]


def calculate_gate(
    metrics: dict[tuple[str, str, float, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_5 = gate_inputs(metrics, "candidate", "", 5.0, "full_period")
    control_5 = {
        control_id: gate_inputs(
            metrics, "control", control_id, 5.0, "full_period"
        )
        for control_id in CONTROL_IDS
    }
    candidate_10 = gate_inputs(metrics, "candidate", "", 10.0, "full_period")
    same_10 = gate_inputs(
        metrics, "control", SAME_PURPOSE_CONTROL, 10.0, "full_period"
    )

    half_rows: list[dict[str, Any]] = []
    for period in ("first_chronological_half", "second_chronological_half"):
        candidate_half = gate_inputs(metrics, "candidate", "", 5.0, period)
        control_half = gate_inputs(
            metrics, "control", SAME_PURPOSE_CONTROL, 5.0, period
        )
        worse_sharpe = (
            float(candidate_half["sharpe_ratio"])
            < float(control_half["sharpe_ratio"])
        )
        worse_drawdown = (
            float(candidate_half["maximum_drawdown"])
            < float(control_half["maximum_drawdown"])
        )
        half_rows.append(
            {
                "strategy_id": STRATEGY_ID,
                "period_label": period,
                "cost_assumption_bps": 5.0,
                "frozen_same_purpose_control": SAME_PURPOSE_CONTROL,
                "candidate_sharpe_ratio": candidate_half["sharpe_ratio"],
                "control_sharpe_ratio": control_half["sharpe_ratio"],
                "candidate_maximum_drawdown": candidate_half[
                    "maximum_drawdown"
                ],
                "control_maximum_drawdown": control_half["maximum_drawdown"],
                "candidate_worse_on_sharpe": worse_sharpe,
                "candidate_worse_on_drawdown": worse_drawdown,
                "and_operator_required": True,
                "half_period_gate_failed": worse_sharpe and worse_drawdown,
                "maximum_drawdown_direction": (
                    "more_negative_is_worse"
                ),
                "decision_tolerance_used": False,
            }
        )

    dominating_controls = [
        control_id
        for control_id, control in control_5.items()
        if v6.dominates(control, candidate_5)
    ]
    same_5 = control_5[SAME_PURPOSE_CONTROL]
    sharpe_advantage = float(candidate_5["sharpe_ratio"]) - float(
        same_5["sharpe_ratio"]
    )
    drawdown_advantage = float(candidate_5["maximum_drawdown"]) - float(
        same_5["maximum_drawdown"]
    )
    simpler_controls = (
        "monthly_equal_weight_nine_sector",
        "SPY_buy_and_hold",
    )
    simpler_reproducing = [
        control_id
        for control_id in simpler_controls
        if (
            float(control_5[control_id]["sharpe_ratio"])
            >= float(candidate_5["sharpe_ratio"])
            and float(control_5[control_id]["maximum_drawdown"])
            >= float(candidate_5["maximum_drawdown"])
        )
    ]
    invariant_failures = [
        key
        for key, row in metrics.items()
        if key[2] in (5.0, 10.0) and not bool(row["invariant_pass"])
    ]
    ten_bps_worse_both = v6.worse_on_both_sharpe_and_drawdown(
        candidate_10, same_10
    )
    second_half_failure = any(
        row["period_label"] == "second_chronological_half"
        and row["half_period_gate_failed"]
        for row in half_rows
    )
    requirements = [
        {
            "requirement_id": 1,
            "frozen_requirement": "positive_full_period_return_at_5_bps",
            "calculation": f"candidate_total_return={candidate_5['total_return']}",
            "requirement_pass": float(candidate_5["total_return"]) > 0.0,
            "failure_detail": "",
        },
        {
            "requirement_id": 2,
            "frozen_requirement": "all_invariants_pass",
            "calculation": f"invariant_failures={invariant_failures}",
            "requirement_pass": not invariant_failures,
            "failure_detail": "",
        },
        {
            "requirement_id": 3,
            "frozen_requirement": "no_principal_full_period_control_dominates",
            "calculation": f"dominating_controls={dominating_controls}",
            "requirement_pass": not dominating_controls,
            "failure_detail": "",
        },
        {
            "requirement_id": 4,
            "frozen_requirement": (
                "full_period_sharpe_advantage_at_least_0.02_or_absolute_"
                "drawdown_advantage_at_least_0.01_vs_same_purpose_control"
            ),
            "calculation": (
                f"sharpe_advantage={sharpe_advantage:.12g};"
                f"drawdown_advantage={drawdown_advantage:.12g};"
                f"control={SAME_PURPOSE_CONTROL}"
            ),
            "requirement_pass": (
                sharpe_advantage >= 0.02 or drawdown_advantage >= 0.01
            ),
            "failure_detail": "",
        },
        {
            "requirement_id": 5,
            "frozen_requirement": (
                "not_worse_on_both_sharpe_and_drawdown_vs_same_purpose_"
                "control_in_either_chronological_half"
            ),
            "calculation": (
                "first_half_failed="
                f"{half_rows[0]['half_period_gate_failed']};"
                "second_half_failed="
                f"{half_rows[1]['half_period_gate_failed']}"
            ),
            "requirement_pass": not any(
                row["half_period_gate_failed"] for row in half_rows
            ),
            "failure_detail": (
                DECISION_REASON if second_half_failure else ""
            ),
        },
        {
            "requirement_id": 6,
            "frozen_requirement": (
                "simpler_controls_do_not_reproduce_claimed_sharpe_and_"
                "drawdown_benefit"
            ),
            "calculation": (
                f"simpler_controls_equal_or_better_on_both={simpler_reproducing}"
            ),
            "requirement_pass": not simpler_reproducing,
            "failure_detail": "",
        },
        {
            "requirement_id": 7,
            "frozen_requirement": (
                "at_10_bps_advantage_not_unfavorable_on_both_sharpe_and_"
                "drawdown_vs_same_purpose_control"
            ),
            "calculation": (
                f"candidate_sharpe={candidate_10['sharpe_ratio']};"
                f"control_sharpe={same_10['sharpe_ratio']};"
                f"candidate_drawdown={candidate_10['maximum_drawdown']};"
                f"control_drawdown={same_10['maximum_drawdown']}"
            ),
            "requirement_pass": not ten_bps_worse_both,
            "failure_detail": "",
        },
    ]
    return half_rows, requirements


def frozen_gate_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": 1,
            "frozen_requirement": "positive_full_period_return",
            "operator_or_threshold": "total_return>0.0",
            "comparison_control": "",
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 2,
            "frozen_requirement": "all_invariants_pass",
            "operator_or_threshold": "all_true",
            "comparison_control": "candidate_and_controls",
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 3,
            "frozen_requirement": "no_principal_full_period_control_dominates",
            "operator_or_threshold": (
                "control_equal_or_better_on_cagr_sharpe_drawdown_and_strictly_"
                "better_on_at_least_one"
            ),
            "comparison_control": "all_frozen_principal_controls",
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 4,
            "frozen_requirement": "full_period_materiality",
            "operator_or_threshold": (
                "sharpe_difference>=0.02 OR drawdown_difference>=0.01"
            ),
            "comparison_control": SAME_PURPOSE_CONTROL,
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 5,
            "frozen_requirement": "chronological_half_stability",
            "operator_or_threshold": (
                "NOT(candidate_sharpe<control_sharpe AND "
                "candidate_drawdown<control_drawdown) in either half"
            ),
            "comparison_control": SAME_PURPOSE_CONTROL,
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 6,
            "frozen_requirement": "simpler_control_non_replication",
            "operator_or_threshold": (
                "no_simpler_control_equal_or_better_on_both_sharpe_and_drawdown"
            ),
            "comparison_control": (
                "monthly_equal_weight_nine_sector|SPY_buy_and_hold"
            ),
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
        {
            "requirement_id": 7,
            "frozen_requirement": "10_bps_cost_diagnostic",
            "operator_or_threshold": (
                "NOT(candidate_sharpe<control_sharpe AND "
                "candidate_drawdown<control_drawdown)"
            ),
            "comparison_control": SAME_PURPOSE_CONTROL,
            "source_authority": rel(FROZEN_SOURCE_PACKET),
            "post_result_exception_allowed": False,
        },
    ]


def root_cause_rows() -> list[dict[str, Any]]:
    return [
        {
            "check_id": "maximum_drawdown_sign",
            "defect_present": False,
            "finding": (
                "Original comparison correctly treated a more negative maximum "
                "drawdown as worse."
            ),
            "original_code_path": (
                "classify: candidate_half.maximum_drawdown < "
                "control_half.maximum_drawdown"
            ),
            "corrected_code_path": "worse_on_both_sharpe_and_drawdown",
            "causal": False,
        },
        {
            "check_id": "and_vs_or",
            "defect_present": False,
            "finding": "Original gate used AND as frozen.",
            "original_code_path": "classify: sharpe_worse AND drawdown_worse",
            "corrected_code_path": "worse_on_both_sharpe_and_drawdown",
            "causal": False,
        },
        {
            "check_id": "both_halves_checked",
            "defect_present": False,
            "finding": "Original split_periods loop evaluated both chronological halves.",
            "original_code_path": "classify: for label, period in split_periods(...)",
            "corrected_code_path": "same loop retained",
            "causal": False,
        },
        {
            "check_id": "comparison_control_selection",
            "defect_present": True,
            "finding": (
                "Original best_by_sharpe selection chose "
                "monthly_equal_weight_nine_sector from full-period controls; the "
                "frozen gate requires six_month_total_return_top3_overlapping."
            ),
            "original_code_path": (
                "classify: best_id,best=best_by_sharpe(controls); half rows use best_id"
            ),
            "corrected_code_path": (
                "followup_gate_control uses explicit frozen High52 control"
            ),
            "causal": True,
        },
        {
            "check_id": "row_pairing",
            "defect_present": False,
            "finding": "Candidate and selected-control rows shared exact dates and costs.",
            "original_code_path": "strategy_metrics(candidate_path,period) paired by period",
            "corrected_code_path": "pairing unchanged",
            "causal": False,
        },
        {
            "check_id": "rounded_values",
            "defect_present": False,
            "finding": "Gate operated on full-precision in-memory metrics.",
            "original_code_path": "float(candidate_half[metric])",
            "corrected_code_path": "full-precision values retained",
            "causal": False,
        },
        {
            "check_id": "full_period_substitution",
            "defect_present": False,
            "finding": "Half-period metrics were recomputed on each half index.",
            "original_code_path": "strategy_metrics(path,period)",
            "corrected_code_path": "period calculation unchanged",
            "causal": False,
        },
        {
            "check_id": "hidden_decision_tolerance",
            "defect_present": True,
            "finding": (
                "Original half gate included a 1e-12 comparison tolerance not "
                "stated in the frozen gate. It was not causal here and was removed."
            ),
            "original_code_path": "classify: metric < control_metric - 1e-12",
            "corrected_code_path": "strict direct comparison without tolerance",
            "causal": False,
        },
    ]


def unchanged_unrelated_control_selection() -> dict[str, bool]:
    control_rows = read_csv(V6_EVIDENCE_DIR / "control_results.csv")
    results: dict[str, bool] = {}
    for card in v6.CARDS:
        if card.strategy_id == STRATEGY_ID:
            continue
        rows = [
            row
            for row in control_rows
            if row["strategy_id"] == card.strategy_id
            and row["cost_assumption_bps"] == "5"
            and row["control_id"] in card.portfolio_controls
            and row["sharpe_ratio"]
            and row["maximum_drawdown"]
        ]
        if not rows:
            results[card.strategy_id] = True
            continue
        controls = {
            row["control_id"]: {
                "sharpe_ratio": float(row["sharpe_ratio"]),
                "maximum_drawdown": float(row["maximum_drawdown"]),
            }
            for row in rows
        }
        original_id, _ = v6.best_by_sharpe(controls)
        corrected_id, _ = v6.followup_gate_control(card, controls)
        results[card.strategy_id] = original_id == corrected_id
    return results


def build_report(
    reproduction_pass: bool,
    requirement_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    outcome: str,
    next_action: str,
) -> str:
    failed = [
        row["requirement_id"]
        for row in requirement_rows
        if not row["requirement_pass"]
    ]
    second = next(
        row
        for row in half_rows
        if row["period_label"] == "second_chronological_half"
    )
    return "\n".join(
        [
            "# High52 V6 Follow-up Gate Verification",
            "",
            "## Scope",
            "",
            "This packet verifies the existing High52 exploration decision only. "
            "No strategy return, strategy rule, instrument, cost, trial, lifecycle "
            "record, or original V6 artifact was changed.",
            "",
            "## Reproduction",
            "",
            f"- Metric reproduction passed: `{str(reproduction_pass).lower()}`",
            f"- Documented numerical tolerance: `{REPRODUCTION_TOLERANCE}`",
            (
                "- Candidate second-half Sharpe / drawdown: "
                f"`{second['candidate_sharpe_ratio']:.12g}` / "
                f"`{second['candidate_maximum_drawdown']:.12g}`"
            ),
            (
                "- Frozen same-purpose control second-half Sharpe / drawdown: "
                f"`{second['control_sharpe_ratio']:.12g}` / "
                f"`{second['control_maximum_drawdown']:.12g}`"
            ),
            "",
            "## Root Cause",
            "",
            "V6 selected the full-period best-Sharpe control for the half-period "
            "gate. That selected monthly equal weight instead of the frozen "
            "six-month top-three momentum control. The candidate therefore appeared "
            "to retain a drawdown advantage and incorrectly passed.",
            "",
            "The reusable decision helper now uses the explicit frozen High52 "
            "same-purpose control and applies strict Sharpe-and-drawdown comparisons "
            "without an unstated decision tolerance.",
            "",
            "## Decision",
            "",
            f"- Failed frozen gate requirements: `{failed}`",
            f"- Corrected outcome: `{outcome}`",
            f"- Failure reason: `{FAILURE_REASON if outcome == CORRECTED_OUTCOME else ''}`",
            f"- Exact project next action: `{next_action}`",
            "",
            "The next action is recorded only and was not executed. This verification "
            "does not perform validation, promotion, lifecycle reconciliation, "
            "paper/demo work, provider access, or broker action.",
        ]
    )


def run() -> dict[str, Any]:
    missing_required = [
        name for name in REQUIRED_V6_FILES if not (V6_EVIDENCE_DIR / name).exists()
    ]
    if missing_required:
        raise RuntimeError(f"Missing required V6 evidence: {missing_required}")
    card = high52_card()
    v6_before = map_hashes(
        path for path in sorted(V6_EVIDENCE_DIR.rglob("*")) if path.is_file()
    )
    protected_before = map_hashes(PROTECTED_STATE_PATHS)
    cache_before = map_hashes(cache_files())
    prior_files_before = prior_evidence_files()
    prior_before = map_hashes(prior_files_before)
    prior_aggregate_before = aggregate_hash(prior_before)
    source_packet_hash_before = file_hash(FROZEN_SOURCE_PACKET)

    clean_output()
    candidate_paths, control_paths = recompute_paths(card)
    reproduction, metrics = metric_reproduction_rows(
        card, candidate_paths, control_paths
    )
    reproduction_pass = bool(reproduction) and all(
        row["reproduction_pass"] for row in reproduction
    )
    half_rows, requirements = calculate_gate(metrics)
    gate_pass = all(row["requirement_pass"] for row in requirements)
    if not reproduction_pass:
        corrected_stage = "blocked"
        outcome = "blocked_feasibility"
        failure_reason = "data_or_comparability_failure"
        decision_reason = "stored_v6_metrics_did_not_reproduce_within_tolerance"
        strategy_next_action = BLOCKED_NEXT_ACTION
        project_next_action = BLOCKED_NEXT_ACTION
    elif gate_pass:
        corrected_stage = "exploratory_followup_standalone"
        outcome = "exploratory_followup_candidate_standalone"
        failure_reason = ""
        decision_reason = "all_frozen_followup_requirements_passed"
        strategy_next_action = "validate_george_hwang_52week_high_sector_v1"
        project_next_action = strategy_next_action
    else:
        corrected_stage = CORRECTED_STAGE
        outcome = CORRECTED_OUTCOME
        failure_reason = FAILURE_REASON
        decision_reason = DECISION_REASON
        strategy_next_action = STRATEGY_NEXT_ACTION
        project_next_action = PROJECT_NEXT_ACTION

    original_strategy = next(
        row
        for row in read_csv(V6_EVIDENCE_DIR / "strategy_cards.csv")
        if row["strategy_id"] == STRATEGY_ID
    )
    original_trial = next(
        row
        for row in read_csv(V6_EVIDENCE_DIR / "trial_ledger.csv")
        if row["trial_id"] == TRIAL_ID
    )
    original_benchmarks = [
        row
        for row in read_csv(V6_EVIDENCE_DIR / "benchmark_reference_log.csv")
        if row["strategy_id"] == STRATEGY_ID
    ]
    if len(original_benchmarks) != 3:
        raise RuntimeError("Expected exactly three carried High52 benchmark references")

    strategy_rows = [
        {
            **original_strategy,
            "original_stage": original_strategy["stage"],
            "stage": corrected_stage,
            "original_outcome": original_strategy["outcome"],
            "outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "next_action": strategy_next_action,
            "strategy_configuration_created_in_task": False,
            "strategy_configuration_carried_forward": True,
            "strategy_definition_changed": False,
            "lifecycle_registry_record_created": False,
        }
    ]
    trial_rows = [
        {
            **original_trial,
            "original_outcome": original_trial["outcome"],
            "authoritative_decision_override": outcome,
            "read_only": True,
            "existing_trial_carried_forward": True,
            "experiment_trial_created_in_task": False,
            "strategy_results_changed": False,
        }
    ]
    benchmark_rows = [
        {
            **row,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "read_only": True,
            "counted_as_strategy": False,
            "counted_as_trial": False,
        }
        for row in original_benchmarks
    ]
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "adaptation_label": ADAPTATION_LABEL,
            "outcome": "verification_completed",
            "strategy_counted": False,
            "trial_counted": False,
            "validation_trial_created": False,
            "lifecycle_record_changed": False,
            "exact_next_action": project_next_action,
            "next_action_executed": False,
        }
    ]
    decision_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "original_stage": original_strategy["stage"],
            "original_outcome": original_strategy["outcome"],
            "corrected_stage": corrected_stage,
            "corrected_outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "strategy_next_action": strategy_next_action,
            "project_next_action": project_next_action,
            "original_v6_evidence_rewritten": False,
            "new_experiment_trial_created": False,
            "lifecycle_record_changed": False,
            "decision_override_authority": rel(OUTPUT_DIR),
        }
    ]
    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "entity_type": "strategy_configuration",
            "stage": corrected_stage,
            "route": "standalone",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": decision_reason,
            "strategy_results_changed": False,
            "validation_claimed": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
        }
    ]
    failure_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "decision_reason": decision_reason,
        }
    ] if failure_reason else []
    next_rows = [
        {
            "scope": "strategy",
            "strategy_id": STRATEGY_ID,
            "outcome": outcome,
            "exact_next_action": strategy_next_action,
            "execute_in_this_task": False,
        },
        {
            "scope": "project",
            "strategy_id": "",
            "outcome": "verification_completed",
            "exact_next_action": project_next_action,
            "execute_in_this_task": False,
        },
    ]
    root_causes = root_cause_rows()
    code_changes = [
        {
            "path": (
                "strategy_lab/research_os/research/"
                "fast_source_library_batch_v6.py"
            ),
            "change_type": "methodology_correction",
            "change_scope": (
                "explicit_high52_gate_control_and_strict_reusable_gate_helpers"
            ),
            "strategy_rule_changed": False,
            "performance_calculation_changed": False,
        },
        {
            "path": (
                "strategy_lab/research_os/research/"
                f"{TASK_ID}.py"
            ),
            "change_type": "verification_module",
            "change_scope": "targeted_reproduction_and_decision_override_evidence",
            "strategy_rule_changed": False,
            "performance_calculation_changed": False,
        },
        {
            "path": f"run_{TASK_ID}.py",
            "change_type": "verification_runner",
            "change_scope": "serial_entry_point",
            "strategy_rule_changed": False,
            "performance_calculation_changed": False,
        },
        {
            "path": f"tests/test_{TASK_ID}.py",
            "change_type": "focused_regression_tests",
            "change_scope": (
                "reproduction_gate_regression_entities_and_hash_reconciliation"
            ),
            "strategy_rule_changed": False,
            "performance_calculation_changed": False,
        },
    ]

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "adaptation_label": ADAPTATION_LABEL,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "canonical_trial_id": TRIAL_ID,
        "frozen_same_purpose_control": SAME_PURPOSE_CONTROL,
        "primary_cost_bps": PRIMARY_COST_BPS,
        "reproduction_tolerance": REPRODUCTION_TOLERANCE,
        "strategy_configurations_created": 0,
        "strategy_configurations_carried_forward": 1,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": 1,
        "benchmark_references": 3,
        "process_tasks": 1,
        "validation_trials_created": 0,
        "lifecycle_records_changed": 0,
        "corrected_stage": corrected_stage,
        "corrected_outcome": outcome,
        "exact_next_action": project_next_action,
        "next_action_executed": False,
        "validation_executed": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
    }

    write_yaml(OUTPUT_DIR / "verification_manifest.yaml", manifest)
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy_rows, list(strategy_rows[0]))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial_rows, list(trial_rows[0]))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        list(benchmark_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0]),
    )
    frozen_rows = frozen_gate_rows()
    write_csv(
        OUTPUT_DIR / "frozen_gate_specification.csv",
        frozen_rows,
        list(frozen_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "metric_reproduction.csv",
        reproduction,
        list(reproduction[0]),
    )
    write_csv(
        OUTPUT_DIR / "chronological_half_gate_check.csv",
        half_rows,
        list(half_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "full_gate_recalculation.csv",
        requirements,
        list(requirements[0]),
    )
    write_csv(
        OUTPUT_DIR / "gate_logic_root_cause.csv",
        root_causes,
        list(root_causes[0]),
    )
    write_csv(
        OUTPUT_DIR / "decision_override.csv",
        decision_rows,
        list(decision_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "code_change_manifest.csv",
        code_changes,
        list(code_changes[0]),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0]),
    )
    failure_fields = [
        "strategy_id",
        "family_id",
        "outcome",
        "failure_reason",
        "decision_reason",
    ]
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows, failure_fields)
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0]),
    )
    write_text(
        OUTPUT_DIR / "verification_report.md",
        build_report(
            reproduction_pass,
            requirements,
            half_rows,
            outcome,
            project_next_action,
        ),
    )

    v6_after = map_hashes(
        path for path in sorted(V6_EVIDENCE_DIR.rglob("*")) if path.is_file()
    )
    protected_after = map_hashes(PROTECTED_STATE_PATHS)
    cache_after = map_hashes(cache_files())
    prior_after = map_hashes(prior_files_before)
    prior_aggregate_after = aggregate_hash(prior_after)
    source_packet_hash_after = file_hash(FROZEN_SOURCE_PACKET)
    unrelated_selection = unchanged_unrelated_control_selection()
    second_half = next(
        row
        for row in half_rows
        if row["period_label"] == "second_chronological_half"
    )
    counts_pass = (
        len(strategy_rows) == 1
        and len(trial_rows) == 1
        and len(benchmark_rows) == 3
        and len(process_rows) == 1
        and manifest["strategy_configurations_created"] == 0
        and manifest["experiment_trials_created"] == 0
        and manifest["validation_trials_created"] == 0
        and manifest["lifecycle_records_changed"] == 0
    )
    consistency_passed = bool(
        reproduction_pass
        and not gate_pass
        and second_half["half_period_gate_failed"]
        and outcome == CORRECTED_OUTCOME
        and failure_reason == FAILURE_REASON
        and project_next_action == PROJECT_NEXT_ACTION
        and v6_before == v6_after
        and protected_before == protected_after
        and cache_before == cache_after
        and prior_aggregate_before == prior_aggregate_after
        and source_packet_hash_before == source_packet_hash_after
        and all(unrelated_selection.values())
        and counts_pass
    )
    consistency = {
        "status": "pass" if consistency_passed else "fail",
        "consistency_passed": consistency_passed,
        "metric_reproduction_passed": reproduction_pass,
        "metric_reproduction_row_count": len(reproduction),
        "documented_reproduction_tolerance": REPRODUCTION_TOLERANCE,
        "all_frozen_gates_reconstructed": len(requirements) == 7,
        "failed_gate_requirement_ids": [
            row["requirement_id"]
            for row in requirements
            if not row["requirement_pass"]
        ],
        "second_half_same_purpose_gate_failed": second_half[
            "half_period_gate_failed"
        ],
        "maximum_drawdown_more_negative_is_worse": True,
        "decision_tolerance_used": False,
        "root_cause": "wrong_comparison_control_selected_for_half_period_gate",
        "strategy_results_changed": False,
        "strategy_definition_changed": False,
        "original_v6_evidence_hashes_before": v6_before,
        "original_v6_evidence_hashes_after": v6_after,
        "original_v6_evidence_unchanged": v6_before == v6_after,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "cache_aggregate_hash_before": aggregate_hash(cache_before),
        "cache_aggregate_hash_after": aggregate_hash(cache_after),
        "cache_unchanged": cache_before == cache_after,
        "prior_evidence_file_count": len(prior_files_before),
        "prior_evidence_aggregate_hash_before": prior_aggregate_before,
        "prior_evidence_aggregate_hash_after": prior_aggregate_after,
        "prior_evidence_unchanged": (
            prior_aggregate_before == prior_aggregate_after
        ),
        "frozen_source_packet_hash_before": source_packet_hash_before,
        "frozen_source_packet_hash_after": source_packet_hash_after,
        "frozen_source_packet_unchanged": (
            source_packet_hash_before == source_packet_hash_after
        ),
        "unrelated_v6_gate_control_selection_unchanged": unrelated_selection,
        "unrelated_v6_strategy_outcomes_unchanged": all(
            unrelated_selection.values()
        ) and v6_before == v6_after,
        "required_counts_pass": counts_pass,
        "strategy_configurations_created": 0,
        "strategy_configurations_carried_forward": 1,
        "experiment_trials_created": 0,
        "existing_trials_carried_forward": 1,
        "benchmark_references": 3,
        "process_tasks": 1,
        "validation_trials_created": 0,
        "lifecycle_records_changed": 0,
        "validation_executed": False,
        "provider_accessed": False,
        "paper_demo_action_taken": False,
        "broker_or_order_action_taken": False,
        "exact_next_action": project_next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "output_dir": rel(OUTPUT_DIR),
        "reproduction_passed": reproduction_pass,
        "failed_gate_requirement_ids": consistency[
            "failed_gate_requirement_ids"
        ],
        "corrected_outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": project_next_action,
        "consistency_passed": consistency_passed,
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
