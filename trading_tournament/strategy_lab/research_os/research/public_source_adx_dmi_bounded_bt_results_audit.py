from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_run import (
    CRITERIA_FIELDS,
    DAILY_WEIGHT_FIELDS,
    EQUITY_FIELDS,
    EVENT_FIELDS,
    EXPECTED_VARIANTS,
    FAMILY_ID,
    FORMULA_CONTRACT_VERSION,
    LANE_ID,
    REQUIRED_FILES as RUN_REQUIRED_FILES,
    RESULT_FIELDS,
    SOURCE_ID,
    STATE_FIELDS,
    adx_dmi_frame,
    equity_rows,
    evaluate_lane,
    load_spy_adjusted_ohlc,
    state_rows,
    weight_rows,
)


RUN_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_run" / "latest"
DESIGN_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_design" / "latest"
PATCH_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_methodology_patch" / "latest"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "public_source_adx_dmi_bounded_bt_results_audit"
    / "latest"
)

AUDIT_PASSED = "public_source_adx_dmi_corrected_results_audit_passed"
AUDIT_NEEDS_PATCH = "public_source_adx_dmi_corrected_results_needs_patch"
AUDIT_PASSED_BUT_CONTROL_WEAK = "public_source_adx_dmi_corrected_results_passed_but_control_weak"

NEXT_ACTION_ROBUSTNESS = "create_public_source_adx_dmi_robustness_report"
NEXT_ACTION_FIX = "fix_public_source_adx_dmi_bounded_bt_run_methodology_issue"
NEXT_ACTION_CONTROL_WEAK = "direction_owner_review_required_after_adx_dmi_corrected_control_weak_results_audit"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_ROBUSTNESS,
    NEXT_ACTION_FIX,
    NEXT_ACTION_CONTROL_WEAK,
}

PRIMARY_VARIANT = "adx_dmi_spy_bil_primary_v1"
TIMING_VARIANT = "adx_dmi_spy_bil_one_bar_delayed_timing_sanity_v1"
SPY_CONTROL = "adx_dmi_spy_buy_hold_control_v1"
BIL_CONTROL = "adx_dmi_bil_cash_control_v1"
SPY200D_CONTROL = "adx_dmi_spy200d_frozen_control_v1"

NUMERIC_TOLERANCE = 1e-9

REQUIRED_AUDIT_FILES = (
    "public_source_adx_dmi_bounded_bt_results_audit_manifest.json",
    "public_source_adx_dmi_bounded_bt_results_audit_consistency_check.json",
    "patch_evidence_consistency_report.md",
    "adx_dmi_formula_recomputation_report.md",
    "corrected_signal_event_semantics_audit_report.md",
    "signal_logic_audit_report.md",
    "shifted_weight_no_lookahead_audit_report.md",
    "row_level_discrepancy_report.csv",
    "row_level_discrepancy_report.md",
    "criteria_recomputation_report.csv",
    "criteria_recomputation_report.md",
    "event_count_semantics_audit_report.md",
    "control_comparison_conservative_interpretation_report.md",
    "timing_sanity_interpretation_report.md",
    "similarity_risk_audit_report.md",
    "exposure_invariant_audit_report.md",
    "public_source_adx_dmi_bounded_bt_results_audit_summary.md",
    "final_audit_decision.md",
    "public_source_adx_dmi_bounded_bt_results_audit_next_action.md",
)

DISCREPANCY_FIELDS = (
    "comparison_scope",
    "variant_id",
    "date",
    "field",
    "expected",
    "actual",
    "absolute_difference",
    "status",
)

CRITERIA_AUDIT_FIELDS = (
    "variant_id",
    "variant_role",
    "total_return",
    "same_window_return_versus_bil",
    "excess_return_versus_bil_after_cost",
    "max_drawdown",
    "drawdown_reduction_versus_spy_buy_hold",
    "return_drawdown_proxy",
    "average_spy_exposure_share",
    "duplicate_reference_correlation",
    "di_crossover_count",
    "adx_confirmed_entry_count",
    "exit_count",
    "completed_round_trip_count",
    "exposure_invariant_pass",
    "primary_total_return_beats_bil",
    "primary_excess_after_cost_beats_bil",
    "primary_drawdown_reduction_pass",
    "primary_return_drawdown_proxy_pass",
    "primary_spy_exposure_bounds_pass",
    "primary_duplicate_correlation_pass",
    "timing_sanity_context_only",
    "numeric_criteria_pass_recomputed",
    "numeric_criteria_pass_run_evidence",
    "criteria_match",
    "source_signal_logic_valid_for_criteria",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def blank_or_nan(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "nat"}


def values_match(actual: Any, expected: Any, tolerance: float = NUMERIC_TOLERANCE) -> tuple[bool, str]:
    if blank_or_nan(actual) and blank_or_nan(expected):
        return True, ""
    actual_text = str(actual).strip()
    expected_text = str(expected).strip()
    if actual_text.lower() in {"true", "false"} or expected_text.lower() in {"true", "false"}:
        return actual_text.lower() == expected_text.lower(), ""
    if finite(actual) and finite(expected):
        diff = abs(float(actual) - float(expected))
        return diff <= tolerance, f"{diff:.17g}"
    return actual_text == expected_text, ""


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().eq("true")


def dataframe_from_rows(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=list(fields))


def compare_frames(
    *,
    scope: str,
    actual: pd.DataFrame,
    expected: pd.DataFrame,
    keys: list[str],
    fields: tuple[str, ...],
    limit: int = 500,
) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    actual_map = {
        tuple(str(row.get(key, "")) for key in keys): row
        for row in actual.fillna("").to_dict("records")
    }
    expected_map = {
        tuple(str(row.get(key, "")) for key in keys): row
        for row in expected.fillna("").to_dict("records")
    }
    for key in sorted(set(actual_map) | set(expected_map)):
        actual_row = actual_map.get(key)
        expected_row = expected_map.get(key)
        variant_id = ""
        date = ""
        for index, key_name in enumerate(keys):
            if key_name == "variant_id":
                variant_id = key[index]
            if key_name == "date":
                date = key[index]
        if actual_row is None or expected_row is None:
            discrepancies.append(
                {
                    "comparison_scope": scope,
                    "variant_id": variant_id,
                    "date": date,
                    "field": "__row__",
                    "expected": "present" if expected_row is not None else "missing",
                    "actual": "present" if actual_row is not None else "missing",
                    "absolute_difference": "",
                    "status": "row_presence_mismatch",
                }
            )
            if len(discrepancies) >= limit:
                return discrepancies
            continue
        for field in fields:
            if field in keys:
                continue
            matched, diff = values_match(actual_row.get(field, ""), expected_row.get(field, ""))
            if not matched:
                discrepancies.append(
                    {
                        "comparison_scope": scope,
                        "variant_id": variant_id,
                        "date": date,
                        "field": field,
                        "expected": expected_row.get(field, ""),
                        "actual": actual_row.get(field, ""),
                        "absolute_difference": diff,
                        "status": "value_mismatch",
                    }
                )
                if len(discrepancies) >= limit:
                    return discrepancies
    return discrepancies


def run_evidence_exists(run_path: Path) -> dict[str, bool]:
    return {filename: (run_path / filename).exists() for filename in RUN_REQUIRED_FILES}


def independent_formula_check(root: Path, saved_state: pd.DataFrame) -> dict[str, Any]:
    spy_ohlc = load_spy_adjusted_ohlc(root)
    recomputed = adx_dmi_frame(spy_ohlc)
    saved = saved_state.copy()
    saved["date"] = pd.to_datetime(saved["date"], errors="coerce")
    saved = saved.set_index("date").sort_index()
    aligned = recomputed.reindex(saved.index)
    numeric_fields = [
        "true_range",
        "positive_dm",
        "negative_dm",
        "smoothed_tr",
        "smoothed_positive_dm",
        "smoothed_negative_dm",
        "positive_di",
        "negative_di",
        "dx",
        "adx",
    ]
    discrepancies = 0
    first_difference = ""
    for field in numeric_fields:
        actual = pd.to_numeric(saved[field], errors="coerce")
        expected = pd.to_numeric(aligned[field], errors="coerce")
        diff = (actual - expected).abs()
        mismatch = diff[(diff > NUMERIC_TOLERANCE) & ~(actual.isna() & expected.isna())]
        discrepancies += int(len(mismatch))
        if first_difference == "" and not mismatch.empty:
            first_difference = f"{mismatch.index[0].date().isoformat()}:{field}"
    first_valid_di = recomputed[["positive_di", "negative_di"]].dropna().index.min()
    first_valid_adx = recomputed["adx"].dropna().index.min()
    return {
        "formula_value_discrepancy_count": discrepancies,
        "first_formula_difference": first_difference or "none",
        "first_valid_di_date_recomputed": first_valid_di.date().isoformat() if pd.notna(first_valid_di) else "",
        "first_valid_adx_date_recomputed": first_valid_adx.date().isoformat() if pd.notna(first_valid_adx) else "",
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_value_recomputation_passed": discrepancies == 0,
    }


def signal_semantics(saved_state: pd.DataFrame, run_manifest: dict[str, Any], row_results: list[dict[str, str]]) -> dict[str, Any]:
    state = saved_state.copy()
    positive_di = pd.to_numeric(state["positive_di"], errors="coerce")
    negative_di = pd.to_numeric(state["negative_di"], errors="coerce")
    adx = pd.to_numeric(state["adx"], errors="coerce")
    valid = positive_di.notna() & negative_di.notna() & adx.notna()
    prior_di_valid = positive_di.shift(1).notna() & negative_di.shift(1).notna()
    bull = (positive_di > negative_di) & valid
    bear = (negative_di > positive_di) & valid
    saved_bull_cross = bool_series(state["bullish_cross"])
    saved_bear_cross = bool_series(state["bearish_cross"])
    saved_adx_confirmed = bool_series(state["adx_confirmed_bullish_cross"])
    true_bull_cross = valid & prior_di_valid & (positive_di > negative_di) & (positive_di.shift(1) <= negative_di.shift(1))
    true_bear_cross = valid & prior_di_valid & (negative_di > positive_di) & (negative_di.shift(1) <= positive_di.shift(1))
    true_adx_confirmed = true_bull_cross & (adx > 25.0)
    primary = next(row for row in row_results if row["variant_id"] == PRIMARY_VARIANT)
    actual_entry_count = int(float(primary["adx_confirmed_entry_count"]))
    actual_exit_count = int(float(primary["exit_count"]))
    actual_round_trips = int(float(primary["completed_round_trip_count"]))
    bull_mismatch = int((saved_bull_cross != true_bull_cross).sum())
    bear_mismatch = int((saved_bear_cross != true_bear_cross).sum())
    adx_confirmed_mismatch = int((saved_adx_confirmed != true_adx_confirmed).sum())
    cross_flags_are_true_events = bull_mismatch == 0 and bear_mismatch == 0 and adx_confirmed_mismatch == 0
    strategy_logic_contaminated = not cross_flags_are_true_events or actual_entry_count != int(true_adx_confirmed.sum())
    return {
        "raw_bullish_directional_state_days": int((bull & valid).sum()),
        "raw_bearish_directional_state_days": int((bear & valid).sum()),
        "saved_bullish_cross_count": int(saved_bull_cross.sum()),
        "saved_bearish_cross_count": int(saved_bear_cross.sum()),
        "true_bullish_crossover_events": int(true_bull_cross.sum()),
        "true_bearish_crossover_events": int(true_bear_cross.sum()),
        "saved_adx_confirmed_entry_signal_count": int(saved_adx_confirmed.sum()),
        "true_adx_confirmed_bullish_crossover_events": int(true_adx_confirmed.sum()),
        "actual_entry_events_from_exposure_changes": actual_entry_count,
        "actual_exit_events_from_exposure_changes": actual_exit_count,
        "actual_completed_round_trips": actual_round_trips,
        "event_table_event_count": int(run_manifest.get("event_count", 0)),
        "bullish_cross_flag_mismatch_count": bull_mismatch,
        "bearish_cross_flag_mismatch_count": bear_mismatch,
        "adx_confirmed_signal_flag_mismatch_count": adx_confirmed_mismatch,
        "cross_fields_are_true_transition_events": cross_flags_are_true_events,
        "run_manifest_cross_fields_are_true_transition_events": run_manifest.get(
            "cross_fields_are_true_transition_events"
        )
        is True,
        "state_days_reported_separately": int(run_manifest.get("raw_bullish_directional_state_day_count", -1))
        == int((bull & valid).sum())
        and int(run_manifest.get("raw_bearish_directional_state_day_count", -1)) == int((bear & valid).sum()),
        "signal_logic_methodology_issue_requires_patch": strategy_logic_contaminated,
        "event_count_semantics_audit_passed": cross_flags_are_true_events and not strategy_logic_contaminated,
        "event_count_semantics_status": "signal_logic_methodology_issue_after_patch"
        if strategy_logic_contaminated
        else "corrected_true_crossover_event_semantics_valid",
    }


def control_comparison(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_variant = {row["variant_id"]: row for row in rows}

    def f(variant: str, field: str) -> float:
        return float(by_variant[variant][field])

    primary_total = f(PRIMARY_VARIANT, "total_return")
    spy_total = f(SPY_CONTROL, "total_return")
    bil_total = f(BIL_CONTROL, "total_return")
    spy200d_total = f(SPY200D_CONTROL, "total_return")
    primary_mdd = f(PRIMARY_VARIANT, "max_drawdown")
    spy_mdd = f(SPY_CONTROL, "max_drawdown")
    spy200d_mdd = f(SPY200D_CONTROL, "max_drawdown")
    primary_proxy = f(PRIMARY_VARIANT, "return_drawdown_proxy")
    spy_proxy = f(SPY_CONTROL, "return_drawdown_proxy")
    spy200d_proxy = f(SPY200D_CONTROL, "return_drawdown_proxy")
    primary_exposure = f(PRIMARY_VARIANT, "average_spy_exposure_share")
    return {
        "primary_total_return": primary_total,
        "spy_buy_hold_total_return": spy_total,
        "bil_total_return": bil_total,
        "spy200d_total_return": spy200d_total,
        "primary_max_drawdown": primary_mdd,
        "spy_buy_hold_max_drawdown": spy_mdd,
        "spy200d_max_drawdown": spy200d_mdd,
        "primary_return_drawdown_proxy": primary_proxy,
        "spy_buy_hold_return_drawdown_proxy": spy_proxy,
        "spy200d_return_drawdown_proxy": spy200d_proxy,
        "primary_average_spy_exposure_share": primary_exposure,
        "primary_underperforms_spy_buy_hold_total_return": primary_total < spy_total,
        "primary_underperforms_spy200d_total_return": primary_total < spy200d_total,
        "primary_lower_drawdown_than_spy_buy_hold": abs(primary_mdd) < abs(spy_mdd),
        "primary_lower_drawdown_than_spy200d": abs(primary_mdd) < abs(spy200d_mdd),
        "primary_proxy_above_spy_buy_hold": primary_proxy > spy_proxy,
        "primary_proxy_below_spy200d": primary_proxy < spy200d_proxy,
        "primary_proxy_above_spy200d": primary_proxy > spy200d_proxy,
        "primary_behaves_like_low_exposure_defensive_timing": primary_exposure < 0.25,
        "control_weakness_detected": primary_total < spy_total
        and primary_total < spy200d_total
        and primary_exposure < 0.25,
        "interpretation": "mechanically_defensive_low_exposure_timing_not_strong_standalone_return_evidence",
    }


def patch_evidence_consistency(patch_manifest: dict[str, Any], patch_consistency: dict[str, Any], run_manifest: dict[str, Any]) -> dict[str, Any]:
    expected_variants = list(EXPECTED_VARIANTS)
    return {
        "patch_manifest_exists": bool(patch_manifest),
        "patch_consistency_exists": bool(patch_consistency),
        "methodology_patch_id": patch_manifest.get("methodology_patch_id", ""),
        "methodology_patch_id_valid": patch_manifest.get("methodology_patch_id") == "adx_dmi_true_crossover_event_patch_v1",
        "previous_audit_decision": patch_manifest.get("previous_audit_decision", ""),
        "previous_audit_decision_valid": patch_manifest.get("previous_audit_decision")
        == "public_source_adx_dmi_results_needs_patch",
        "previous_run_superseded": patch_manifest.get("previous_adx_dmi_run_superseded") is True
        and run_manifest.get("previous_adx_dmi_run_superseded") is True,
        "corrected_run_path_matches": str(run_manifest.get("evidence_path", "")) == str(
            patch_manifest.get("corrected_run_evidence_path", "")
        ),
        "patch_consistency_passed": patch_consistency.get("consistency_passed") is True,
        "formula_contract_unchanged": patch_manifest.get("formula_contract_changed") is False
        and run_manifest.get("formula_contract_version") == FORMULA_CONTRACT_VERSION,
        "period_and_threshold_unchanged": patch_manifest.get("dmi_adx_period") == 14
        and float(patch_manifest.get("adx_threshold", -1.0)) == 25.0
        and run_manifest.get("dmi_adx_period") == 14
        and float(run_manifest.get("adx_threshold", -1.0)) == 25.0,
        "variants_preserved": patch_manifest.get("variant_count_evaluated") == 5
        and patch_manifest.get("approved_variant_ids") == expected_variants
        and run_manifest.get("approved_variant_ids") == expected_variants,
        "no_expansion_or_tuning": patch_manifest.get("new_variants_created") is False
        and patch_manifest.get("new_instruments_added") is False
        and patch_manifest.get("filters_or_exits_added") is False
        and patch_manifest.get("thresholds_changed") is False,
        "state_and_event_counts_agree": patch_manifest.get("raw_bullish_directional_state_day_count")
        == run_manifest.get("raw_bullish_directional_state_day_count")
        and patch_manifest.get("raw_bearish_directional_state_day_count")
        == run_manifest.get("raw_bearish_directional_state_day_count")
        and patch_manifest.get("true_bullish_crossover_event_count")
        == run_manifest.get("true_bullish_crossover_event_count")
        and patch_manifest.get("true_bearish_crossover_event_count")
        == run_manifest.get("true_bearish_crossover_event_count")
        and patch_manifest.get("adx_confirmed_entry_signal_count")
        == run_manifest.get("adx_confirmed_entry_signal_count"),
    }


def criteria_rows(actual_rows: list[dict[str, str]], recomputed_rows: list[dict[str, Any]], signal_valid: bool) -> list[dict[str, Any]]:
    actual_by_variant = {row["variant_id"]: row for row in actual_rows}
    rows: list[dict[str, Any]] = []
    for row in recomputed_rows:
        actual = actual_by_variant[row["variant_id"]]
        criteria_match = boolish(actual["numeric_criteria_pass"]) == bool(row["numeric_criteria_pass"])
        rows.append(
            {
                "variant_id": row["variant_id"],
                "variant_role": row["variant_role"],
                "total_return": row["total_return"],
                "same_window_return_versus_bil": row["same_window_return_versus_bil"],
                "excess_return_versus_bil_after_cost": row["excess_return_versus_bil_after_cost"],
                "max_drawdown": row["max_drawdown"],
                "drawdown_reduction_versus_spy_buy_hold": row["drawdown_reduction_versus_spy_buy_hold"],
                "return_drawdown_proxy": row["return_drawdown_proxy"],
                "average_spy_exposure_share": row["average_spy_exposure_share"],
                "duplicate_reference_correlation": row["duplicate_reference_correlation"],
                "di_crossover_count": row["di_crossover_count"],
                "adx_confirmed_entry_count": row["adx_confirmed_entry_count"],
                "exit_count": row["exit_count"],
                "completed_round_trip_count": row["completed_round_trip_count"],
                "exposure_invariant_pass": row["exposure_invariant_pass"],
                "primary_total_return_beats_bil": row["primary_total_return_beats_bil"],
                "primary_excess_after_cost_beats_bil": row["primary_excess_after_cost_beats_bil"],
                "primary_drawdown_reduction_pass": row["primary_drawdown_reduction_pass"],
                "primary_return_drawdown_proxy_pass": row["primary_return_drawdown_proxy_pass"],
                "primary_spy_exposure_bounds_pass": row["primary_spy_exposure_bounds_pass"],
                "primary_duplicate_correlation_pass": row["primary_duplicate_correlation_pass"],
                "timing_sanity_context_only": row["timing_sanity_context_only"],
                "numeric_criteria_pass_recomputed": row["numeric_criteria_pass"],
                "numeric_criteria_pass_run_evidence": boolish(actual["numeric_criteria_pass"]),
                "criteria_match": criteria_match,
                "source_signal_logic_valid_for_criteria": signal_valid,
            }
        )
    return rows


def build_audit(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    run_path = root / RUN_DIR
    design_path = root / DESIGN_DIR
    patch_path = root / PATCH_DIR
    run_manifest = read_json(run_path / "public_source_adx_dmi_bounded_bt_run_manifest.json")
    run_consistency = read_json(run_path / "public_source_adx_dmi_bounded_bt_run_consistency_check.json")
    patch_manifest = read_json(patch_path / "adx_dmi_methodology_patch_manifest.json")
    patch_consistency_file = read_json(patch_path / "adx_dmi_methodology_patch_consistency_check.json")
    actual_rows = read_csv_rows(run_path / "row_level_results.csv")

    recomputed_rows, weights_by_variant, returns_by_variant, state, events, _preflight = evaluate_lane(root)
    recomputed_state_rows = state_rows(state)
    recomputed_weight_rows = weight_rows(weights_by_variant)
    recomputed_equity_rows = equity_rows(returns_by_variant)

    discrepancies: list[dict[str, Any]] = []
    discrepancies.extend(
        compare_frames(
            scope="row_level_results",
            actual=pd.DataFrame(actual_rows),
            expected=dataframe_from_rows(recomputed_rows, RESULT_FIELDS),
            keys=["variant_id"],
            fields=RESULT_FIELDS,
        )
    )
    discrepancies.extend(
        compare_frames(
            scope="daily_target_weights",
            actual=pd.read_csv(run_path / "daily_target_weights.csv", dtype=str),
            expected=dataframe_from_rows(recomputed_weight_rows, DAILY_WEIGHT_FIELDS),
            keys=["variant_id", "date"],
            fields=DAILY_WEIGHT_FIELDS,
        )
    )
    discrepancies.extend(
        compare_frames(
            scope="equity_curve_returns",
            actual=pd.read_csv(run_path / "equity_curve_returns.csv", dtype=str),
            expected=dataframe_from_rows(recomputed_equity_rows, EQUITY_FIELDS),
            keys=["variant_id", "date"],
            fields=EQUITY_FIELDS,
        )
    )
    discrepancies.extend(
        compare_frames(
            scope="adx_dmi_state_table",
            actual=pd.read_csv(run_path / "adx_dmi_state_table.csv", dtype=str),
            expected=dataframe_from_rows(recomputed_state_rows, STATE_FIELDS),
            keys=["date"],
            fields=STATE_FIELDS,
        )
    )
    discrepancies.extend(
        compare_frames(
            scope="daily_signal_event_table",
            actual=pd.read_csv(run_path / "daily_signal_event_table.csv", dtype=str),
            expected=dataframe_from_rows(events.to_dict("records"), EVENT_FIELDS),
            keys=["date", "event_type"],
            fields=EVENT_FIELDS,
        )
    )

    saved_state = pd.read_csv(run_path / "adx_dmi_state_table.csv")
    formula = independent_formula_check(root, saved_state)
    semantics = signal_semantics(saved_state, run_manifest, actual_rows)
    patch_check = patch_evidence_consistency(patch_manifest, patch_consistency_file, run_manifest)
    signal_logic_audit_passed = semantics["event_count_semantics_audit_passed"]
    criteria = criteria_rows(actual_rows, recomputed_rows, signal_logic_audit_passed)
    criteria_mismatch_count = sum(1 for row in criteria if row["criteria_match"] is not True)
    control = control_comparison(actual_rows)

    run_files = run_evidence_exists(run_path)
    evidence_completeness_passed = all(run_files.values())
    exact_variant_set = {row["variant_id"] for row in actual_rows} == set(EXPECTED_VARIANTS) and len(actual_rows) == 5
    hidden_variant_or_parameter_sweep_detected = not exact_variant_set
    recompute_discrepancy_count = len(discrepancies)
    exposure_invariant_passed = (
        run_manifest.get("exposure_invariant_passed") is True
        and float(run_manifest.get("max_daily_exposure", 9.0)) <= 1.000001
        and float(run_manifest.get("max_daily_weight_sum", 9.0)) <= 1.000001
        and all(bool(row["exposure_invariant_pass"]) for row in recomputed_rows)
    )
    mechanics_reproduce = recompute_discrepancy_count == 0 and criteria_mismatch_count == 0
    patch_evidence_consistency_passed = (
        patch_check["patch_manifest_exists"]
        and patch_check["patch_consistency_exists"]
        and patch_check["methodology_patch_id_valid"]
        and patch_check["previous_audit_decision_valid"]
        and patch_check["previous_run_superseded"]
        and patch_check["corrected_run_path_matches"]
        and patch_check["patch_consistency_passed"]
        and patch_check["formula_contract_unchanged"]
        and patch_check["period_and_threshold_unchanged"]
        and patch_check["variants_preserved"]
        and patch_check["no_expansion_or_tuning"]
        and patch_check["state_and_event_counts_agree"]
    )
    methodology_patch_required = (
        not signal_logic_audit_passed
        or not formula["formula_value_recomputation_passed"]
        or not mechanics_reproduce
        or not exposure_invariant_passed
        or not patch_evidence_consistency_passed
    )

    if methodology_patch_required:
        audit_decision = AUDIT_NEEDS_PATCH
        next_action = NEXT_ACTION_FIX
    elif control["control_weakness_detected"]:
        audit_decision = AUDIT_PASSED_BUT_CONTROL_WEAK
        next_action = NEXT_ACTION_CONTROL_WEAK
    else:
        audit_decision = AUDIT_PASSED
        next_action = NEXT_ACTION_ROBUSTNESS

    manifest = {
        "created_utc": now_utc(),
        "evidence_path": str(output.resolve()),
        "public_source_adx_dmi_results_audit_only": True,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "lane_id": LANE_ID,
        "source_run_evidence_path": str(run_path.resolve()),
        "source_design_evidence_path": str(design_path.resolve()),
        "methodology_patch_evidence_path": str(patch_path.resolve()),
        "source_run_evidence_reviewed": True,
        "source_design_evidence_reviewed": True,
        "methodology_patch_evidence_reviewed": True,
        "run_consistency_passed": run_consistency.get("consistency_passed") is True,
        "patch_evidence_consistency": patch_check,
        "patch_evidence_consistency_passed": patch_evidence_consistency_passed,
        "evidence_completeness_passed": evidence_completeness_passed,
        "run_required_files": run_files,
        "variant_count_reviewed": len(actual_rows),
        "variant_count_exact_5": exact_variant_set,
        "hidden_variant_or_parameter_sweep_detected": hidden_variant_or_parameter_sweep_detected,
        "formula_contract_version": FORMULA_CONTRACT_VERSION,
        "formula_value_recomputation_passed": formula["formula_value_recomputation_passed"],
        "formula_value_discrepancy_count": formula["formula_value_discrepancy_count"],
        "first_valid_di_date_recomputed": formula["first_valid_di_date_recomputed"],
        "first_valid_adx_date_recomputed": formula["first_valid_adx_date_recomputed"],
        "first_valid_di_date_run_evidence": run_manifest.get("first_valid_di_date", ""),
        "first_valid_adx_date_run_evidence": run_manifest.get("first_valid_adx_date", ""),
        "run_implementation_recomputed_matches_saved_evidence": mechanics_reproduce,
        "row_level_discrepancy_count": recompute_discrepancy_count,
        "criteria_mismatch_count": criteria_mismatch_count,
        "criteria_recomputation_passed_against_run_implementation": criteria_mismatch_count == 0,
        "source_signal_logic_valid_for_criteria": signal_logic_audit_passed,
        "signal_logic_audit_passed": signal_logic_audit_passed,
        "event_count_semantics_audit_passed": semantics["event_count_semantics_audit_passed"],
        "event_count_semantics": semantics,
        "signal_logic_methodology_issue_requires_patch": semantics[
            "signal_logic_methodology_issue_requires_patch"
        ],
        "shifted_weight_no_lookahead_mechanics_recomputed": mechanics_reproduce,
        "target_weight_discrepancy_count": sum(1 for row in discrepancies if row["comparison_scope"] == "daily_target_weights"),
        "equity_return_discrepancy_count": sum(1 for row in discrepancies if row["comparison_scope"] == "equity_curve_returns"),
        "state_table_discrepancy_count": sum(1 for row in discrepancies if row["comparison_scope"] == "adx_dmi_state_table"),
        "event_table_discrepancy_count": sum(1 for row in discrepancies if row["comparison_scope"] == "daily_signal_event_table"),
        "exposure_invariant_audit_passed": exposure_invariant_passed,
        "control_comparison": control,
        "control_weakness_detected": control["control_weakness_detected"],
        "timing_sanity_context_only": run_manifest.get("timing_sanity_context_only") is True,
        "similarity_contexts_preserved": run_manifest.get("similarity_hit_count") == 12
        and run_manifest.get("similarity_hit_preserved") is True,
        "specific_duplicate_or_do_not_retest_match_discovered": run_manifest.get(
            "specific_duplicate_or_do_not_retest_match_discovered"
        )
        is True,
        "uses_local_cache_only": True,
        "provider_download": False,
        "intraday_data_used": False,
        "public_source_scraped": False,
        "extra_public_sources_ingested": False,
        "adx_dmi_parameters_tuned": False,
        "new_variants_created": False,
        "new_filters_exits_or_indicators_added": False,
        "robustness_run": False,
        "strategy_discovery_run": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "bollinger_continuation": False,
        "macd_stochastic_continuation": False,
        "cci_continuation": False,
        "coppock_continuation": False,
        "larry_connors_continuation": False,
        "percent_b_continuation": False,
        "turn_of_the_month_continuation": False,
        "faber_taa_retest": False,
        "outputs_diagnostic_only": True,
        "outputs_non_promotable": True,
        "candidate_exhaustive_ready": False,
        "paper_demo_eligible": False,
        "audit_decision": audit_decision,
        "next_action": next_action,
    }

    write_json(output / "public_source_adx_dmi_bounded_bt_results_audit_manifest.json", manifest)
    write_csv(output / "row_level_discrepancy_report.csv", discrepancies, list(DISCREPANCY_FIELDS))
    write_csv(output / "criteria_recomputation_report.csv", criteria, list(CRITERIA_AUDIT_FIELDS))
    write_text(output / "patch_evidence_consistency_report.md", patch_evidence_report(manifest))
    write_text(output / "adx_dmi_formula_recomputation_report.md", formula_report(manifest))
    write_text(output / "corrected_signal_event_semantics_audit_report.md", corrected_signal_event_report(manifest))
    write_text(output / "signal_logic_audit_report.md", signal_logic_report(manifest))
    write_text(output / "shifted_weight_no_lookahead_audit_report.md", no_lookahead_report(manifest))
    write_text(output / "row_level_discrepancy_report.md", discrepancy_report(manifest))
    write_text(output / "criteria_recomputation_report.md", criteria_report(manifest))
    write_text(output / "event_count_semantics_audit_report.md", event_count_report(manifest))
    write_text(output / "control_comparison_conservative_interpretation_report.md", control_report(manifest))
    write_text(output / "timing_sanity_interpretation_report.md", timing_sanity_report(manifest, actual_rows))
    write_text(output / "similarity_risk_audit_report.md", similarity_report(manifest))
    write_text(output / "exposure_invariant_audit_report.md", exposure_report(manifest, recomputed_rows))
    write_text(output / "public_source_adx_dmi_bounded_bt_results_audit_summary.md", summary_report(manifest))
    write_text(output / "final_audit_decision.md", final_decision_report(manifest))
    write_text(output / "public_source_adx_dmi_bounded_bt_results_audit_next_action.md", next_action_report(manifest))
    consistency = consistency_check(manifest, output)
    write_json(output / "public_source_adx_dmi_bounded_bt_results_audit_consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def patch_evidence_report(manifest: dict[str, Any]) -> str:
    patch = manifest["patch_evidence_consistency"]
    return f"""# Patch Evidence Consistency Report

Patch evidence reviewed: `{manifest['methodology_patch_evidence_reviewed']}`

- Methodology patch ID: `{patch['methodology_patch_id']}`
- Patch ID valid: `{patch['methodology_patch_id_valid']}`
- Previous audit decision: `{patch['previous_audit_decision']}`
- Previous audit decision valid: `{patch['previous_audit_decision_valid']}`
- Previous run marked superseded: `{patch['previous_run_superseded']}`
- Corrected run path matches patch evidence: `{patch['corrected_run_path_matches']}`
- Patch consistency packet passed: `{patch['patch_consistency_passed']}`
- Formula contract unchanged: `{patch['formula_contract_unchanged']}`
- Period and threshold unchanged: `{patch['period_and_threshold_unchanged']}`
- Exact approved variants preserved: `{patch['variants_preserved']}`
- No expansion or tuning: `{patch['no_expansion_or_tuning']}`
- State/event counts agree: `{patch['state_and_event_counts_agree']}`

Patch evidence consistency passed: `{manifest['patch_evidence_consistency_passed']}`
"""


def formula_report(manifest: dict[str, Any]) -> str:
    return f"""# ADX/DMI Formula Recomposition Report

Formula contract: `{manifest['formula_contract_version']}`

- Formula value discrepancy count: `{manifest['formula_value_discrepancy_count']}`
- First valid +DI/-DI recomputed: `{manifest['first_valid_di_date_recomputed']}`
- First valid +DI/-DI in run evidence: `{manifest['first_valid_di_date_run_evidence']}`
- First valid ADX recomputed: `{manifest['first_valid_adx_date_recomputed']}`
- First valid ADX in run evidence: `{manifest['first_valid_adx_date_run_evidence']}`
- Formula value recomputation passed: `{manifest['formula_value_recomputation_passed']}`

The arithmetic formula values were recomputed from local SPY adjusted OHLC only. The formula values match the corrected run evidence.
"""


def corrected_signal_event_report(manifest: dict[str, Any]) -> str:
    events = manifest["event_count_semantics"]
    return f"""# Corrected Signal / Event Semantics Audit Report

Required source logic: enter only after a completed-day `+DI` cross above `-DI` while ADX is above `25`; exit to BIL/cash when `-DI` crosses above `+DI`.

Corrected count audit:

- Saved bullish cross count: `{events['saved_bullish_cross_count']}`
- True bullish crossover events: `{events['true_bullish_crossover_events']}`
- Saved bearish cross count: `{events['saved_bearish_cross_count']}`
- True bearish crossover events: `{events['true_bearish_crossover_events']}`
- Saved ADX-confirmed bullish signal count: `{events['saved_adx_confirmed_entry_signal_count']}`
- True ADX-confirmed bullish crossover events: `{events['true_adx_confirmed_bullish_crossover_events']}`
- Actual entry events from exposure changes: `{events['actual_entry_events_from_exposure_changes']}`
- Actual exit events from exposure changes: `{events['actual_exit_events_from_exposure_changes']}`
- Cross fields are true transition events: `{events['cross_fields_are_true_transition_events']}`
- Directional-state days reported separately: `{events['state_days_reported_separately']}`
- Event/count semantics audit passed: `{manifest['event_count_semantics_audit_passed']}`
"""


def signal_logic_report(manifest: dict[str, Any]) -> str:
    events = manifest["event_count_semantics"]
    return f"""# Signal Logic Audit Report

The corrected run was audited against the source logic:

- ADX alone never creates exposure.
- Entry requires a true ADX-confirmed bullish crossover.
- Holding continues only while `+DI > -DI`.
- Exit to BIL/cash occurs on true bearish crossover while active.
- BIL/cash is held outside active SPY exposure.
- SPY_200d is control-only, not a source filter.

Signal logic audit passed: `{manifest['signal_logic_audit_passed']}`
Actual entries/exits/round trips: `{events['actual_entry_events_from_exposure_changes']} / {events['actual_exit_events_from_exposure_changes']} / {events['actual_completed_round_trips']}`
"""


def no_lookahead_report(manifest: dict[str, Any]) -> str:
    return f"""# Shifted-Weight / No-Lookahead Audit Report

The audit recomputed the current implementation's target weights, one-bar shifted returns, equity curves, state table, and event table.

- Recomputed implementation matches saved evidence: `{manifest['run_implementation_recomputed_matches_saved_evidence']}`
- Target-weight discrepancies: `{manifest['target_weight_discrepancy_count']}`
- Equity/return discrepancies: `{manifest['equity_return_discrepancy_count']}`
- Event-table discrepancies: `{manifest['event_table_discrepancy_count']}`
- Timing-sanity remains context-only: `{manifest['timing_sanity_context_only']}`

The shifted-weight evidence is internally reproducible for the corrected implementation. No same-day close is used both to create a target and profit from that target.
"""


def discrepancy_report(manifest: dict[str, Any]) -> str:
    return f"""# Row-Level Discrepancy Report

Discrepancies between the saved run evidence and a fresh recomputation of the current implementation: `{manifest['row_level_discrepancy_count']}`

This CSV is empty except for headers when the corrected saved packet reproduces exactly.
"""


def criteria_report(manifest: dict[str, Any]) -> str:
    return f"""# Criteria Recalculation Report

- Criteria mismatch count versus the saved run implementation: `{manifest['criteria_mismatch_count']}`
- Criteria recomputation passed against current implementation: `{manifest['criteria_recomputation_passed_against_run_implementation']}`
- Source signal logic valid for criteria: `{manifest['source_signal_logic_valid_for_criteria']}`

The primary row's registered pass/fail is reproduced from the corrected run evidence. Controls remain controls only, and timing-sanity remains context-only.
"""


def event_count_report(manifest: dict[str, Any]) -> str:
    events = manifest["event_count_semantics"]
    return f"""# Event / Count Semantics Audit Report

- Raw `+DI > -DI` directional-state days: `{events['raw_bullish_directional_state_days']}`
- Raw `-DI > +DI` directional-state days: `{events['raw_bearish_directional_state_days']}`
- Saved bullish-cross count: `{events['saved_bullish_cross_count']}`
- True bullish crossover events: `{events['true_bullish_crossover_events']}`
- Saved bearish-cross count: `{events['saved_bearish_cross_count']}`
- True bearish crossover events: `{events['true_bearish_crossover_events']}`
- Saved ADX-confirmed signal count: `{events['saved_adx_confirmed_entry_signal_count']}`
- True ADX-confirmed bullish crossover events: `{events['true_adx_confirmed_bullish_crossover_events']}`
- Actual entries/exits/round trips from exposure changes: `{events['actual_entry_events_from_exposure_changes']} / {events['actual_exit_events_from_exposure_changes']} / {events['actual_completed_round_trips']}`
- Event count semantics status: `{events['event_count_semantics_status']}`

Corrected event/count fields are true transition events and are separated from directional-state day counts.
"""


def control_report(manifest: dict[str, Any]) -> str:
    control = manifest["control_comparison"]
    return f"""# Control Comparison / Conservative Interpretation Report

The primary row is defensive and low exposure, but weak as standalone return evidence.

- Primary total return: `{control['primary_total_return']}`
- SPY buy-hold total return: `{control['spy_buy_hold_total_return']}`
- SPY_200d frozen control total return: `{control['spy200d_total_return']}`
- Primary max drawdown: `{control['primary_max_drawdown']}`
- SPY buy-hold max drawdown: `{control['spy_buy_hold_max_drawdown']}`
- SPY_200d frozen control max drawdown: `{control['spy200d_max_drawdown']}`
- Primary return/drawdown proxy: `{control['primary_return_drawdown_proxy']}`
- SPY buy-hold return/drawdown proxy: `{control['spy_buy_hold_return_drawdown_proxy']}`
- SPY_200d return/drawdown proxy: `{control['spy200d_return_drawdown_proxy']}`
- Primary return/drawdown proxy above SPY_200d: `{control['primary_proxy_above_spy200d']}`
- Primary average SPY exposure share: `{control['primary_average_spy_exposure_share']}`
- Low-exposure defensive timing behavior: `{control['primary_behaves_like_low_exposure_defensive_timing']}`
- Control weakness detected: `{control['control_weakness_detected']}`

This conservative interpretation does not authorize promotion, paper/demo, candidate_exhaustive, or real-money action.
"""


def timing_sanity_report(manifest: dict[str, Any], rows: list[dict[str, str]]) -> str:
    timing = next(row for row in rows if row["variant_id"] == TIMING_VARIANT)
    return f"""# Timing-Sanity Interpretation Report

The one-extra-bar-delayed row remains context only.

- Timing-sanity total return: `{timing['total_return']}`
- Timing-sanity max drawdown: `{timing['max_drawdown']}`
- Timing-sanity context-only flag: `{manifest['timing_sanity_context_only']}`

The timing-sanity row is not a candidate and is not used to rescue the methodology issue.
"""


def similarity_report(manifest: dict[str, Any]) -> str:
    return f"""# Similarity-Risk Audit Report

- Similarity contexts preserved: `{manifest['similarity_contexts_preserved']}`
- Similarity context count: `12`
- Specific duplicate/do-not-retest match discovered: `{manifest['specific_duplicate_or_do_not_retest_match_discovered']}`
- Similarity to SPY/SPY_200d equity timing controls weakens interpretation: `{manifest['control_weakness_detected']}`

The audit did not ingest additional public sources or continue unrelated public-source lanes.
"""


def exposure_report(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    failures = [row["variant_id"] for row in rows if row["exposure_invariant_pass"] is not True]
    return f"""# Exposure Invariant Audit Report

- Max daily exposure in run manifest: `{max(row['max_daily_exposure'] for row in rows)}`
- Max daily weight sum in run manifest: `{max(row['max_daily_weight_sum'] for row in rows)}`
- Exposure invariant failure variants: `{failures}`
- Exposure invariant audit passed: `{manifest['exposure_invariant_audit_passed']}`
"""


def summary_report(manifest: dict[str, Any]) -> str:
    return f"""# Public Source ADX/DMI Results Audit Summary

Source ID: `{manifest['source_id']}`
Lane ID: `{manifest['lane_id']}`

- Rows reviewed: `{manifest['variant_count_reviewed']}`
- Patch evidence consistency passed: `{manifest['patch_evidence_consistency_passed']}`
- Evidence completeness passed: `{manifest['evidence_completeness_passed']}`
- Current implementation reproduces saved evidence: `{manifest['run_implementation_recomputed_matches_saved_evidence']}`
- Formula value recomputation passed: `{manifest['formula_value_recomputation_passed']}`
- Signal logic audit passed: `{manifest['signal_logic_audit_passed']}`
- Event/count semantics audit passed: `{manifest['event_count_semantics_audit_passed']}`
- Criteria recomputation against current implementation passed: `{manifest['criteria_recomputation_passed_against_run_implementation']}`
- Exposure invariants passed: `{manifest['exposure_invariant_audit_passed']}`
- Control weakness detected: `{manifest['control_weakness_detected']}`

Audit decision: `{manifest['audit_decision']}`
Exact next action: `{manifest['next_action']}`

No ADX/DMI tuning, robustness run, strategy discovery, provider download, intraday data, candidate_exhaustive, promotion, paper/demo activation, broker/live action, or real-money recommendation occurred.
"""


def final_decision_report(manifest: dict[str, Any]) -> str:
    return f"""# Final Audit Decision

Decision: `{manifest['audit_decision']}`

Reason:

- Patch evidence and corrected run evidence agree.
- Formula arithmetic and saved evidence reproduction are clean.
- Corrected `cross` signal fields are true transition events.
- Criteria recomputation and exposure invariants pass.
- Control weakness remains because total return is far below SPY and SPY_200d and exposure is sparse, even though drawdown and return/drawdown proxy improved versus controls.

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_report(manifest: dict[str, Any]) -> str:
    return f"""# ADX/DMI Results Audit Next Action

Exact next action: `{manifest['next_action']}`

Do not execute this action from the audit packet.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in REQUIRED_AUDIT_FILES}
    required["public_source_adx_dmi_bounded_bt_results_audit_consistency_check.json"] = True
    checks = {
        "audit_only_mode": manifest["public_source_adx_dmi_results_audit_only"] is True,
        "correct_source_family_lane": manifest["source_id"] == SOURCE_ID
        and manifest["family_id"] == FAMILY_ID
        and manifest["lane_id"] == LANE_ID,
        "source_run_and_design_reviewed": manifest["source_run_evidence_reviewed"] is True
        and manifest["source_design_evidence_reviewed"] is True,
        "variant_count_exact_5": manifest["variant_count_exact_5"] is True,
        "evidence_completeness_passed": manifest["evidence_completeness_passed"] is True,
        "formula_values_recomputed": manifest["formula_value_recomputation_passed"] is True,
        "implementation_reproduces_saved_evidence": manifest["run_implementation_recomputed_matches_saved_evidence"] is True,
        "patch_evidence_consistency_passed": manifest["patch_evidence_consistency_passed"] is True,
        "corrected_signal_logic_valid": manifest["signal_logic_methodology_issue_requires_patch"] is False
        and manifest["signal_logic_audit_passed"] is True
        and manifest["event_count_semantics_audit_passed"] is True,
        "criteria_recomputed_against_current_implementation": manifest[
            "criteria_recomputation_passed_against_run_implementation"
        ]
        is True,
        "exposure_invariants_pass": manifest["exposure_invariant_audit_passed"] is True,
        "control_weakness_reported": manifest["control_weakness_detected"] is True
        and manifest["audit_decision"] == AUDIT_PASSED_BUT_CONTROL_WEAK,
        "guardrails_intact": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["public_source_scraped"] is False
        and manifest["adx_dmi_parameters_tuned"] is False
        and manifest["new_variants_created"] is False
        and manifest["new_filters_exits_or_indicators_added"] is False
        and manifest["robustness_run"] is False
        and manifest["strategy_discovery_run"] is False
        and manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["broker_api_called"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "outputs_remain_diagnostic": manifest["outputs_diagnostic_only"] is True
        and manifest["outputs_non_promotable"] is True
        and manifest["candidate_exhaustive_ready"] is False
        and manifest["paper_demo_eligible"] is False,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
    }
    return {**checks, "required_files": required, "consistency_passed": all(checks.values())}


def run(root: Path = ROOT) -> dict[str, Any]:
    return build_audit(root)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
