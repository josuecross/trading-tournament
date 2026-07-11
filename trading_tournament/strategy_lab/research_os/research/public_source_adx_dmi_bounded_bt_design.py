from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import dotted_get, read_json, read_yaml


SOURCE_ID = "adx_dmi_trend_strength_crossover"
LANE_ID = "public_source_adx_dmi_bounded_bt_lane_v1"
FAMILY_ID = "equity_index_adx_dmi_trend_strength"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_adx_dmi_bounded_bt_design" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "adx_dmi_trend_strength_crossover.yaml"
)
INTAKE_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
INTAKE_MANIFEST_PATH = INTAKE_EVIDENCE_DIR / "public_source_intake_validation_manifest.json"
BATCH_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
BATCH_ELIGIBILITY_PATH = BATCH_EVIDENCE_DIR / "eligibility_decisions.csv"
BT_CONTROL_MANIFEST_PATH = (
    Path("evidence") / "research_recovery" / "bt_adapter_control_poc" / "latest" / "bt_adapter_control_poc_manifest.json"
)
BT_MULTIASSET_MANIFEST_PATH = (
    Path("evidence")
    / "research_recovery"
    / "bt_adapter_multasset_control_poc"
    / "latest"
    / "bt_adapter_multasset_control_poc_manifest.json"
)

RUN_READY = "public_source_adx_dmi_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_adx_dmi_bounded_bt_design_blocked_formula_contract_incomplete"
NEXT_ACTION_RUN = "run_public_source_adx_dmi_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "manual_input_required_for_public_source_adx_dmi_bounded_bt_design"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
SOURCE_BACKED_PARAMS = {
    "parameter_status": "source_backed_parameters",
    "dmi_adx_period": 14,
    "adx_trend_strength_threshold": 25,
    "bullish_direction_state": "+DI above -DI",
    "bearish_or_cash_direction_state": "-DI above +DI",
    "entry_confirmation": "+DI(14) crosses above -DI(14) with ADX(14) above 25",
    "exit_confirmation": "-DI(14) crosses above +DI(14)",
    "adx_direction_caveat": "ADX measures trend strength, not direction; +DI and -DI provide direction.",
    "tuned_parameters": False,
}

FORMULA_CONTRACT = {
    "formula_contract_version": "adx_dmi_wilder_contract_v1",
    "canonical_repo_utility_found": False,
    "price_input": "completed daily adjusted SPY OHLC; previous close is prior completed adjusted close",
    "true_range": "TR = max(high - low, abs(high - previous_close), abs(low - previous_close))",
    "up_move": "up_move = high - previous_high",
    "down_move": "down_move = previous_low - low",
    "positive_dm": "+DM = up_move if up_move > down_move and up_move > 0 else 0",
    "negative_dm": "-DM = down_move if down_move > up_move and down_move > 0 else 0",
    "wilder_period": 14,
    "smoothed_seed": "initial smoothed TR, +DM, and -DM use rolling sum of first 14 raw components",
    "smoothed_update": "next_smoothed = prior_smoothed - (prior_smoothed / 14) + current_raw_component",
    "di_formula": "+DI = 100 * smoothed(+DM) / smoothed(TR); -DI = 100 * smoothed(-DM) / smoothed(TR)",
    "dx_formula": "DX = 100 * abs(+DI - -DI) / (+DI + -DI)",
    "adx_seed": "initial ADX is the arithmetic mean of the first 14 valid DX values",
    "adx_update": "ADX_t = ((ADX_{t-1} * 13) + DX_t) / 14",
    "divide_by_zero": "zero denominators produce NaN, not inf; invalid ADX/+DI/-DI rows are never signal-active",
    "first_valid_di_rule": "first valid +DI/-DI occurs on the date of the 14th raw TR/+DM/-DM component if smoothed TR is nonzero",
    "first_valid_adx_rule": "first valid ADX occurs on the date of the 14th valid DX value",
    "invalid_signal_rule": "hold BIL/cash until +DI, -DI, and ADX are all valid",
}

PLANNED_ROW_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "symbols",
    "entry_rule",
    "exit_rule",
    "source_backed_parameters",
    "signal_timing",
    "bt_adapter_contract",
    "baseline_or_control_role",
    "comparator_references",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)
CACHE_FIELDS = (
    "symbol",
    "required",
    "cache_status",
    "cache_path",
    "first_date",
    "last_date",
    "rows",
    "required_columns",
    "columns_present",
    "data_requirement_status",
    "notes",
)
PARAM_FIELDS = ("parameter", "value", "source_status", "tuned", "notes")

REQUIRED_FILES = (
    "public_source_adx_dmi_bounded_bt_design_manifest.json",
    "public_source_adx_dmi_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "source_backed_parameter_report.csv",
    "source_backed_parameter_report.md",
    "formula_contract_patch_report.md",
    "existing_utility_discovery_report.md",
    "adx_dmi_formula_signal_definition.md",
    "warmup_effective_start_requirements.md",
    "long_only_adaptation_caveat.md",
    "similarity_risk_report.md",
    "planned_row_table.csv",
    "planned_row_table.md",
    "signal_timing_convention.md",
    "baseline_control_policy.md",
    "numeric_success_failure_criteria.md",
    "bt_adapter_readiness.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "run_readiness_decision.md",
    "public_source_adx_dmi_bounded_bt_design_next_action.md",
    "public_source_adx_dmi_bounded_bt_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def source_intake_review(root: Path) -> dict[str, Any]:
    intake = read_yaml(root / INTAKE_PATH)
    intake_manifest = read_json(root / INTAKE_MANIFEST_PATH)
    eligibility_rows = read_csv_rows(root / BATCH_ELIGIBILITY_PATH)
    batch_row = next((row for row in eligibility_rows if row.get("source_id") == SOURCE_ID), {})
    return {
        "candidate_exists": (root / INTAKE_PATH).exists(),
        "single_intake_evidence_exists": bool(intake_manifest),
        "single_intake_evidence_path": str((root / INTAKE_EVIDENCE_DIR).resolve()),
        "batch_evidence_exists": (root / BATCH_ELIGIBILITY_PATH).exists(),
        "batch_evidence_path": str((root / BATCH_EVIDENCE_DIR).resolve()),
        "source_id": dotted_get(intake, "source.source_id") or "",
        "source_name": dotted_get(intake, "source.source_name") or "",
        "source_citation": dotted_get(intake, "source.source_url_or_citation") or "",
        "source_type": dotted_get(intake, "source.source_type") or "",
        "strategy_family": dotted_get(intake, "strategy_description.strategy_family") or "",
        "instruments": dotted_get(intake, "strategy_description.instruments") or [],
        "timeframe": dotted_get(intake, "strategy_description.timeframe") or "",
        "entry_rule": dotted_get(intake, "rules.entry_rule") or "",
        "exit_rule": dotted_get(intake, "rules.exit_rule") or "",
        "risk_controls": dotted_get(intake, "rules.risk_controls") or "",
        "rule_clarity": dotted_get(intake, "strategy_description.rule_clarity") or "",
        "single_intake_decision": intake_manifest.get("eligibility_decision", ""),
        "single_intake_next_action": intake_manifest.get("next_action", ""),
        "single_intake_constraint_blocks": "|".join(intake_manifest.get("constraint_blockers", [])),
        "single_intake_similarity_hits": "|".join(intake_manifest.get("family_similarity_hits", [])),
        "single_intake_similarity_hit_count": intake_manifest.get("family_similarity_hit_count", 0),
        "single_intake_missing_fields": "|".join(intake_manifest.get("exact_missing_fields", [])),
        "single_intake_local_cache_checked": intake_manifest.get("local_cache_checked") is True,
        "formula_parameter_status": intake_manifest.get("indicator_formula_parameter_completeness_status", ""),
        "entry_rule_status": intake_manifest.get("entry_rule_completeness_status", ""),
        "exit_rule_status": intake_manifest.get("exit_rule_completeness_status", ""),
        "indicator_defaults_status": intake_manifest.get("indicator_defaults_completeness_status", ""),
        "batch_eligibility_decision": batch_row.get("eligibility_decision", ""),
        "batch_next_action": batch_row.get("next_action", ""),
        "batch_constraint_blocks": batch_row.get("constraint_blocks", ""),
        "batch_similarity_hits": batch_row.get("family_similarity_hits", ""),
        "batch_missing_required_fields": batch_row.get("missing_required_fields", ""),
        "batch_local_cache_complete": str(batch_row.get("local_cache_complete", "")).lower() == "true",
        "source_intake": intake,
    }


def cache_rows(root: Path) -> list[dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    required_by_symbol = {
        "SPY": ("date", "open", "high", "low", "close", "adj_close", "volume"),
        "BIL": ("date", "adj_close", "close"),
    }
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        info = inventory.get(symbol, {})
        cache_path = Path(str(info.get("path", "")))
        if cache_path and not cache_path.is_absolute():
            cache_path = root / cache_path
        columns = csv_header(cache_path) if cache_path else []
        required_columns = required_by_symbol[symbol]
        missing_columns = [column for column in required_columns if column not in columns]
        cache_ready = info.get("status") == "cache_ready" and not missing_columns
        if cache_ready and symbol == "SPY":
            data_status = "daily_adjusted_ohlc_ready_for_adx_dmi"
        elif cache_ready:
            data_status = "cash_proxy_adjusted_close_ready"
        else:
            data_status = "missing_required_local_price_columns_or_cache"
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_status": "cache_ready" if cache_ready else info.get("status", "missing"),
                "cache_path": info.get("path", ""),
                "first_date": info.get("first_date", ""),
                "last_date": info.get("last_date", ""),
                "rows": info.get("rows", 0),
                "required_columns": "|".join(required_columns),
                "columns_present": "|".join(columns),
                "data_requirement_status": data_status,
                "notes": "local_raw_price_history_available_no_provider_download"
                if cache_ready
                else "required_local_price_history_not_ready",
            }
        )
    return rows


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def read_price_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            parsed = {
                "date": row.get("date", ""),
                "high": _safe_float(row.get("high")),
                "low": _safe_float(row.get("low")),
                "close": _safe_float(row.get("close") or row.get("adj_close")),
                "adj_close": _safe_float(row.get("adj_close") or row.get("close")),
            }
            if parsed["date"] and parsed["high"] is not None and parsed["low"] is not None and parsed["adj_close"] is not None:
                rows.append(parsed)
    return rows


def existing_utility_discovery_rows() -> list[dict[str, Any]]:
    return [
        {
            "location": "strategy_lab/research_os/exploratory_sandbox/sandbox_indicators.py",
            "finding": "indicator registry/specification only; no ADX/DMI formula implementation found",
            "canonical_adx_dmi_utility": False,
        },
        {
            "location": "indicator_layer/approved_indicators.yaml",
            "finding": "ADX appears as an approved category, not as executable formula code",
            "canonical_adx_dmi_utility": False,
        },
        {
            "location": "strategy_lab/research_os/indicator_governance.yaml",
            "finding": "ADX is marked only-after-validation; no callable ADX/DMI utility is defined",
            "canonical_adx_dmi_utility": False,
        },
        {
            "location": "repository rg search",
            "finding": "no canonical function for TR, +DM, -DM, +DI, -DI, DX, or ADX was found",
            "canonical_adx_dmi_utility": False,
        },
    ]


def formula_contract_complete() -> bool:
    required_keys = (
        "true_range",
        "up_move",
        "down_move",
        "positive_dm",
        "negative_dm",
        "wilder_period",
        "smoothed_seed",
        "smoothed_update",
        "di_formula",
        "dx_formula",
        "adx_seed",
        "adx_update",
        "divide_by_zero",
        "first_valid_di_rule",
        "first_valid_adx_rule",
        "invalid_signal_rule",
    )
    return all(bool(FORMULA_CONTRACT.get(key)) for key in required_keys) and FORMULA_CONTRACT["wilder_period"] == 14


def warmup_requirements(root: Path) -> dict[str, Any]:
    spy_rows = read_price_rows(root / "data" / "cache" / "SPY.csv")
    bil_rows = read_price_rows(root / "data" / "cache" / "BIL.csv")
    n = int(FORMULA_CONTRACT["wilder_period"])
    valid_dx_dates: list[str] = []
    first_di_date = ""
    first_adx_date = ""
    smoothed_tr: float | None = None
    smoothed_plus_dm: float | None = None
    smoothed_minus_dm: float | None = None
    raw_components: list[dict[str, Any]] = []

    for index in range(1, len(spy_rows)):
        current = spy_rows[index]
        previous = spy_rows[index - 1]
        high = current["high"]
        low = current["low"]
        previous_high = previous["high"]
        previous_low = previous["low"]
        previous_close = previous["adj_close"]
        if None in (high, low, previous_high, previous_low, previous_close):
            continue
        tr = max(high - low, abs(high - previous_close), abs(low - previous_close))
        up_move = high - previous_high
        down_move = previous_low - low
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
        raw_components.append({"date": current["date"], "tr": tr, "plus_dm": plus_dm, "minus_dm": minus_dm})
        if len(raw_components) < n:
            continue
        if len(raw_components) == n:
            seed = raw_components[-n:]
            smoothed_tr = sum(item["tr"] for item in seed)
            smoothed_plus_dm = sum(item["plus_dm"] for item in seed)
            smoothed_minus_dm = sum(item["minus_dm"] for item in seed)
        else:
            assert smoothed_tr is not None
            assert smoothed_plus_dm is not None
            assert smoothed_minus_dm is not None
            smoothed_tr = smoothed_tr - (smoothed_tr / n) + tr
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / n) + plus_dm
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / n) + minus_dm
        if not smoothed_tr:
            continue
        plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
        minus_di = 100.0 * smoothed_minus_dm / smoothed_tr
        denominator = plus_di + minus_di
        if denominator == 0:
            continue
        if not first_di_date:
            first_di_date = current["date"]
        valid_dx_dates.append(current["date"])
        if len(valid_dx_dates) == n and not first_adx_date:
            first_adx_date = current["date"]

    spy_first = spy_rows[0]["date"] if spy_rows else ""
    spy_last = spy_rows[-1]["date"] if spy_rows else ""
    bil_first = bil_rows[0]["date"] if bil_rows else ""
    bil_last = bil_rows[-1]["date"] if bil_rows else ""
    aligned_first = max([date for date in (spy_first, bil_first) if date], default="")
    aligned_last = min([date for date in (spy_last, bil_last) if date], default="")
    effective_start = max([date for date in (aligned_first, first_adx_date) if date], default="")
    return {
        "warmup_contract_complete": bool(first_di_date and first_adx_date and effective_start),
        "spy_first_date": spy_first,
        "spy_last_date": spy_last,
        "bil_first_date": bil_first,
        "bil_last_date": bil_last,
        "aligned_first_date": aligned_first,
        "aligned_last_date": aligned_last,
        "first_valid_di_date": first_di_date,
        "first_valid_adx_date": first_adx_date,
        "effective_start_date_after_alignment_and_warmup": effective_start,
        "raw_component_periods_for_first_di": n,
        "valid_dx_periods_for_first_adx": n,
        "warmup_notes": "dates are derived from local cache and formula warmup only; no strategy performance or backtest was computed",
    }


def parameter_rows(intake: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, fallback in SOURCE_BACKED_PARAMS.items():
        value = dotted_get(intake, f"indicator_definitions.{key}")
        if value in (None, ""):
            value = fallback
        rows.append(
            {
                "parameter": key,
                "value": value,
                "source_status": "source_backed_parameters",
                "tuned": False,
                "notes": "frozen_from_manual_public_source_intake_no_optimization",
            }
        )
    return rows


def parameter_text() -> str:
    return "|".join(f"{key}={value}" for key, value in SOURCE_BACKED_PARAMS.items())


def planned_rows() -> list[dict[str, Any]]:
    params = parameter_text()
    return [
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "adx_dmi_spy_bil_primary_v1",
            "variant_role": "source_primary",
            "research_label": "public_source_adx_dmi_primary",
            "symbols": "SPY|BIL",
            "entry_rule": "+DI(14) crosses above -DI(14) and ADX(14) > 25 on completed daily close; enter/hold SPY while +DI remains above -DI",
            "exit_rule": "Exit SPY to BIL/cash when -DI(14) crosses above +DI(14), or hold BIL/cash when no valid bullish state exists",
            "source_backed_parameters": params,
            "signal_timing": "daily completed OHLC signal with project no-lookahead shifted-weight convention",
            "bt_adapter_contract": "daily target weight frame with SPY and BIL columns; no bt run in design step",
            "baseline_or_control_role": "primary_source_interpretation",
            "comparator_references": "SPY_buy_hold_control|BIL_cash_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "adx_dmi_spy_bil_one_bar_delayed_timing_sanity_v1",
            "variant_role": "timing_sanity",
            "research_label": "public_source_adx_dmi_timing_sanity",
            "symbols": "SPY|BIL",
            "entry_rule": "same source ADX/DMI entry state applied one extra trading day later; timing-sanity only",
            "exit_rule": "same source ADX/DMI exit/cash state applied one extra trading day later; timing-sanity only",
            "source_backed_parameters": params,
            "signal_timing": "one-extra-bar delayed target application sanity row; not an optimized variant",
            "bt_adapter_contract": "daily target weight frame with SPY and BIL columns; no bt run in design step",
            "baseline_or_control_role": "timing_sanity_not_parameter_sweep",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|BIL_cash_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "adx_dmi_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "public_source_adx_dmi_control_only",
            "symbols": "SPY",
            "entry_rule": "SPY buy-and-hold same-window control",
            "exit_rule": "not_applicable_control",
            "source_backed_parameters": "not_applicable_control",
            "signal_timing": "control-only benchmark convention documented by future run",
            "bt_adapter_contract": "control target weight frame; no bt run in design step",
            "baseline_or_control_role": "buy_hold_control_only",
            "comparator_references": "primary_source_row|BIL_cash_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "adx_dmi_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "public_source_adx_dmi_control_only",
            "symbols": "BIL",
            "entry_rule": "BIL cash same-window control",
            "exit_rule": "not_applicable_control",
            "source_backed_parameters": "not_applicable_control",
            "signal_timing": "control-only benchmark convention documented by future run",
            "bt_adapter_contract": "control target weight frame; no bt run in design step",
            "baseline_or_control_role": "cash_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "adx_dmi_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "public_source_adx_dmi_control_only",
            "symbols": "SPY|BIL",
            "entry_rule": "existing project SPY 200d frozen control where supported; control only, not ADX/DMI filter",
            "exit_rule": "existing project SPY 200d frozen control where supported; control only, not ADX/DMI filter",
            "source_backed_parameters": "not_applicable_control",
            "signal_timing": "use already validated bt adapter SPY_200d control convention",
            "bt_adapter_contract": "control target weight frame; no bt run in design step",
            "baseline_or_control_role": "spy200d_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|BIL_cash_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
    ]


def bt_readiness(root: Path) -> dict[str, Any]:
    control = read_json(root / BT_CONTROL_MANIFEST_PATH)
    multasset = read_json(root / BT_MULTIASSET_MANIFEST_PATH)
    return {
        "bt_control_manifest_exists": bool(control),
        "bt_control_poc_passed": control.get("final_adapter_decision") == "bt_adapter_control_poc_passed",
        "bt_control_exposure_invariant_passed": control.get("exposure_invariant_passed") is True,
        "bt_multasset_manifest_exists": bool(multasset),
        "bt_multasset_poc_passed": multasset.get("final_adapter_decision")
        == "bt_adapter_multasset_control_poc_passed",
        "bt_multasset_exposure_invariant_passed": multasset.get("exposure_invariant_passed") is True,
        "bt_adapter_ready_for_design": control.get("final_adapter_decision") == "bt_adapter_control_poc_passed"
        and multasset.get("final_adapter_decision") == "bt_adapter_multasset_control_poc_passed",
        "bt_package_version": multasset.get("bt_package_version") or control.get("bt_package_version") or "unknown",
    }


def run_readiness(
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
    warmup: dict[str, Any],
) -> tuple[str, str, str]:
    blockers: list[str] = []
    if review["source_id"] != SOURCE_ID:
        blockers.append("validated_adx_dmi_candidate_not_found")
    if review["single_intake_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("single_intake_not_eligible_for_bounded_bt_design")
    if review["batch_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("batch_intake_not_eligible_for_bounded_bt_design")
    if review["single_intake_constraint_blocks"] or review["batch_constraint_blocks"]:
        blockers.append("constraint_blocks_present")
    if review["single_intake_missing_fields"] or review["batch_missing_required_fields"]:
        blockers.append("missing_required_intake_fields_present")
    if review["formula_parameter_status"] != "adx_dmi_period_threshold_and_direction_rules_source_backed_complete":
        blockers.append("adx_dmi_formula_parameters_not_complete")
    if review["entry_rule_status"] != "adx_dmi_entry_rule_source_backed_complete":
        blockers.append("adx_dmi_entry_rule_not_complete")
    if review["exit_rule_status"] != "adx_dmi_exit_cash_rule_source_backed_complete":
        blockers.append("adx_dmi_exit_cash_rule_not_complete")
    if any(row["cache_status"] != "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache_or_ohlc_columns")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_prerequisites_not_ready")
    if not (4 <= len(rows) <= 5):
        blockers.append("planned_row_count_outside_declared_bounds")
    if SOURCE_BACKED_PARAMS["tuned_parameters"] is not False:
        blockers.append("source_parameters_not_marked_untuned")
    if not formula_contract_complete():
        blockers.append("adx_dmi_formula_contract_incomplete")
    if not warmup.get("warmup_contract_complete"):
        blockers.append("adx_dmi_warmup_effective_start_contract_incomplete")
    if blockers:
        return RUN_BLOCKED, ";".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


def source_intake_review_md(review: dict[str, Any]) -> str:
    return f"""# Source Intake Review

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Source citation: `{review['source_citation']}`

Source type: `{review['source_type']}`

Strategy family: `{review['strategy_family']}`

Timeframe: `{review['timeframe']}`

Single-source intake evidence path: `{review['single_intake_evidence_path']}`

Single-source intake decision: `{review['single_intake_decision']}`

Single-source next action: `{review['single_intake_next_action']}`

Batch intake evidence path: `{review['batch_evidence_path']}`

Batch intake decision: `{review['batch_eligibility_decision']}`

Constraint blockers: `{review['single_intake_constraint_blocks'] or review['batch_constraint_blocks'] or 'none'}`

Missing required fields: `{review['single_intake_missing_fields'] or review['batch_missing_required_fields'] or 'none'}`

Entry rule: `{review['entry_rule']}`

Exit rule: `{review['exit_rule']}`

Risk controls: `{review['risk_controls']}`

The source is manually supplied context only and is not proof of profitability.
"""


def local_cache_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    for row in rows:
        lines.append(
            f"- `{row['symbol']}`: `{row['cache_status']}`, first `{row['first_date']}`, "
            f"last `{row['last_date']}`, requirement `{row['data_requirement_status']}`"
        )
    lines.append("")
    lines.append("No provider download was used or authorized.")
    return "\n".join(lines) + "\n"


def source_backed_parameter_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Source-Backed Parameter Report", ""]
    lines.append(
        "All frozen ADX/DMI values come from the manually supplied public-source intake. "
        "No ADX threshold sweep, DMI-period sweep, SPY_200d filter, stop-loss, profit target, "
        "volatility filter, or additional indicator was added."
    )
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['parameter']}`: `{row['value']}`; tuned `{row['tuned']}`")
    return "\n".join(lines) + "\n"


def utility_discovery_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Existing Utility Discovery Report", ""]
    lines.append("Repository search did not identify a canonical callable ADX/DMI implementation.")
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['location']}`: {row['finding']} "
            f"(canonical utility: `{row['canonical_adx_dmi_utility']}`)"
        )
    lines.append("")
    lines.append("Because no canonical utility was found, this design freezes the Wilder-style contract in this evidence packet for the future bounded run.")
    return "\n".join(lines) + "\n"


def formula_contract_patch_md(warmup: dict[str, Any]) -> str:
    return f"""# Formula Contract Patch Report

Patch objective: freeze the ADX/DMI calculation contract for reproducible future execution.

Canonical repository ADX/DMI utility found: `{FORMULA_CONTRACT['canonical_repo_utility_found']}`

Formula contract version: `{FORMULA_CONTRACT['formula_contract_version']}`

Formula contract complete: `{formula_contract_complete()}`

Wilder smoothing period: `{FORMULA_CONTRACT['wilder_period']}`

Smoothed seed convention: `{FORMULA_CONTRACT['smoothed_seed']}`

Smoothed update convention: `{FORMULA_CONTRACT['smoothed_update']}`

Initial ADX seed: `{FORMULA_CONTRACT['adx_seed']}`

First valid +DI/-DI date from local cache: `{warmup['first_valid_di_date']}`

First valid ADX date from local cache: `{warmup['first_valid_adx_date']}`

Effective start date after SPY/BIL alignment and indicator warmup: `{warmup['effective_start_date_after_alignment_and_warmup']}`

This patch does not change rows, thresholds, instruments, entry/exit rules, controls, or run logic. no strategy performance or backtest was computed.
"""


def formula_signal_md() -> str:
    return f"""# ADX / DMI Formula And Signal Definition

Frozen signal semantics for a future bounded run:

- Use daily SPY OHLC data from local cache only.
- Price input: `{FORMULA_CONTRACT['price_input']}`.
- Compute ADX(14), +DI(14), and -DI(14) using completed daily bars.
- ADX measures trend strength, not direction.
- +DI and -DI provide the directional state.
- Source-backed ADX trend-strength threshold is `25`.
- True Range: `{FORMULA_CONTRACT['true_range']}`.
- Positive directional movement:
  - `{FORMULA_CONTRACT['up_move']}`
  - `{FORMULA_CONTRACT['positive_dm']}`
- Negative directional movement:
  - `{FORMULA_CONTRACT['down_move']}`
  - `{FORMULA_CONTRACT['negative_dm']}`
- Wilder smoothing period: `{FORMULA_CONTRACT['wilder_period']}`.
- Smoothed TR, +DM, and -DM seed: `{FORMULA_CONTRACT['smoothed_seed']}`.
- Smoothed TR, +DM, and -DM update: `{FORMULA_CONTRACT['smoothed_update']}`.
- Directional indicators: `{FORMULA_CONTRACT['di_formula']}`.
- DX: `{FORMULA_CONTRACT['dx_formula']}`.
- ADX seed: `{FORMULA_CONTRACT['adx_seed']}`.
- ADX update: `{FORMULA_CONTRACT['adx_update']}`.
- Divide-by-zero behavior: `{FORMULA_CONTRACT['divide_by_zero']}`.
- Warmup:
  - `{FORMULA_CONTRACT['first_valid_di_rule']}`
  - `{FORMULA_CONTRACT['first_valid_adx_rule']}`
- Invalid signal rows: `{FORMULA_CONTRACT['invalid_signal_rule']}`.
- Enter or hold SPY only after `+DI(14)` crosses above `-DI(14)` while `ADX(14) > 25` on the completed daily close.
- Continue holding SPY while `+DI` remains above `-DI`.
- Exit SPY to BIL/cash when `-DI(14)` crosses above `+DI(14)`.
- If no valid bullish state exists, hold BIL/cash.

No alternate ADX thresholds, DMI periods, moving-average filters, RSI, MACD, CCI, Bollinger, volume filters, volatility filters, stop-losses, profit targets, alternate exits, leverage, shorting, inverse ETFs, options, futures, intraday data, or broker/live logic are part of this design.
"""


def warmup_md(warmup: dict[str, Any]) -> str:
    return f"""# Warmup / Effective Start Requirements

The future bounded run must report these fields before evaluating labels or criteria:

- First valid +DI/-DI date: `{warmup['first_valid_di_date']}`
- First valid ADX date: `{warmup['first_valid_adx_date']}`
- SPY local-cache date window: `{warmup['spy_first_date']}` to `{warmup['spy_last_date']}`
- BIL local-cache date window: `{warmup['bil_first_date']}` to `{warmup['bil_last_date']}`
- SPY/BIL aligned date window: `{warmup['aligned_first_date']}` to `{warmup['aligned_last_date']}`
- Effective start date after alignment and warmup: `{warmup['effective_start_date_after_alignment_and_warmup']}`

Warmup contract:

- Raw TR/+DM/-DM components require the prior completed adjusted close, prior adjusted high, and prior adjusted low.
- The first valid +DI/-DI date follows the 14th raw TR/+DM/-DM component if smoothed TR is nonzero.
- The first valid ADX date follows the 14th valid DX value.
- Rows before valid +DI, -DI, and ADX must hold BIL/cash and must not create entry, exit, or crossover events.
- Denominator-zero cases produce NaN and are excluded from signal activation.

This report is derived from local-cache dates and formula warmup only. It is not a strategy backtest and does not compute performance metrics.
"""


def long_only_adaptation_md() -> str:
    return """# Long-Only Adaptation Caveat

Public ADX/DMI materials can discuss bullish and bearish directional interpretation. This repository design freezes a long-only SPY/BIL adaptation only.

- Bullish +DI/-DI confirmation can map to SPY exposure.
- Bearish -DI dominance, missing confirmation, or inactive state maps to BIL/cash.
- Bearish interpretation never maps to short SPY, inverse ETFs, options, futures, margin, leverage, intraday execution, paper orders, live orders, broker/API calls, or real-money recommendations.

This adaptation is a bounded research design, not evidence of profitability.
"""


def similarity_risk_md(review: dict[str, Any]) -> str:
    hits = review["single_intake_similarity_hits"] or review["batch_similarity_hits"] or "none"
    return f"""# Similarity Risk Report

Preserved similarity hits: `{hits}`

Similarity hit count: `{review['single_intake_similarity_hit_count']}`

Duplicate/do-not-retest blocker in current intake result: `false`

Design treatment:

- Similarity context is recorded because this is still SPY/BIL timing.
- The source is not treated as profitability proof.
- The ADX/DMI concept remains distinct from SPY_200d, calendar timing, RSI mean reversion, CCI, MACD/Stochastic, Coppock, Bollinger/Percent B, global allocation, Macro/GLD, high-return tactical, and volatility-throttle lanes.
- No exact rejected variant is reopened.
- No SPY_200d filter or additional confirmation filter is added to the source row.
- Route only to a future bounded `bt` run if this design packet is accepted.
"""


def planned_rows_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Row Table", ""]
    for row in rows:
        lines.append(f"- `{row['variant_id']}`: role `{row['variant_role']}`, label `{row['research_label']}`")
    lines.append("")
    lines.append("All rows are diagnostic and non-promotable. Control rows are controls only.")
    return "\n".join(lines) + "\n"


def signal_timing_md() -> str:
    return """# Signal Timing Convention

Future ADX/DMI bounded `bt` runs must freeze timing before execution:

- Use daily local-cache OHLC data only.
- Compute ADX(14), +DI(14), and -DI(14) using information available through the completed daily close.
- Produce target weights after the daily close.
- Apply target weights using the project's no-lookahead shifted-weight convention.
- Primary row enters or holds SPY only when the source-backed bullish ADX/DMI state is active.
- Primary row exits to BIL/cash when the source-backed bearish/cash ADX/DMI state occurs.
- Rows before first valid +DI, -DI, and ADX, or rows with NaN indicator values, must hold BIL/cash and must not be stale-forward-filled into old SPY allocations.
- One-extra-bar delayed timing sanity may be included only as context, not as an optimized variant.
- No same-day lookahead, intraday data, provider download, parameter tuning, SPY_200d source filter, stop-losses, profit targets, volatility filters, alternate exits, or additional indicators may be used.
"""


def baseline_policy_md() -> str:
    return """# Baseline / Control Policy

Diagnostic controls for any future bounded run:

- SPY buy-and-hold same-window control.
- BIL cash same-window control.
- SPY_200d frozen control where existing project conventions support it without adding new strategy logic.

Controls are benchmark/control rows only. They cannot become promotion candidates, candidate_exhaustive rows, paper-forward candidates, broker/live rows, or real-money recommendations.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run criteria are research-only and not promotion gates.

The primary source row can be considered diagnostically useful only if all applicable criteria are true:

- Total return beats BIL by `> 0.0000`.
- If a standard project public-source cost model exists at run time, excess return versus BIL after that cost model remains `> 0.0000`.
- Max drawdown reduction versus SPY buy-and-hold is `>= 0.2000` relative improvement.
- Return/drawdown proxy beats SPY buy-and-hold by `> 0.0000`.
- Average SPY exposure share is `>= 0.0500` and `<= 0.8500`.
- Duplicate/reference correlation versus SPY buy-and-hold and SPY_200d control is `< 0.9000` where available.
- Entry count, exit count, and completed round trips are reported.
- Exposure invariants pass.

Timing-sanity row is context only and cannot supersede the source-primary row.

Allowed labels:

- `public_source_adx_dmi_primary`
- `public_source_adx_dmi_timing_sanity`
- `public_source_adx_dmi_control_only`
- `public_source_adx_dmi_design_blocked`
"""


def bt_readiness_md(bt: dict[str, Any]) -> str:
    return f"""# bt Adapter Readiness

Control POC passed: `{bt['bt_control_poc_passed']}`

Control POC exposure invariant passed: `{bt['bt_control_exposure_invariant_passed']}`

Multasset POC passed: `{bt['bt_multasset_poc_passed']}`

Multasset POC exposure invariant passed: `{bt['bt_multasset_exposure_invariant_passed']}`

bt adapter ready for design: `{bt['bt_adapter_ready_for_design']}`

bt package version: `{bt['bt_package_version']}`

No bt run is executed by this design packet.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_adx_dmi_bounded_bt_design_only",
        "bounded_bt_lane_run",
        "strategy_backtest_run",
        "bounded_run_implementation_created",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "additional_public_sources_ingested",
        "alternative_adx_thresholds_added",
        "alternative_dmi_periods_added",
        "spy200d_added_as_source_filter",
        "other_indicators_added",
        "stop_loss_or_profit_target_added",
        "optimization_run",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "current_backtester_replaced",
        "strategy_discovery_run",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return {key: manifest[key] for key in keys}


def exposure_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future ADX/DMI bounded `bt` run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, inverse ETFs, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
    warmup: dict[str, Any],
    utility_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    readiness, blocker, next_action = run_readiness(review, cache, bt, rows, warmup)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_adx_dmi_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_intake_reviewed": review["candidate_exists"],
        "single_source_intake_evidence_reviewed": review["single_intake_evidence_exists"],
        "batch_intake_evidence_reviewed": review["batch_evidence_exists"],
        "source_intake_eligibility_decision": review["single_intake_decision"],
        "batch_intake_eligibility_decision": review["batch_eligibility_decision"],
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "uses_only_validated_adx_dmi_candidate": True,
        "planned_row_count": len(rows),
        "planned_row_count_target_4_to_5": 4 <= len(rows) <= 5,
        "planned_row_count_lte_5": len(rows) <= 5,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "source_backed_parameters": True,
        "parameter_status": SOURCE_BACKED_PARAMS["parameter_status"],
        "dmi_adx_period": SOURCE_BACKED_PARAMS["dmi_adx_period"],
        "adx_trend_strength_threshold": SOURCE_BACKED_PARAMS["adx_trend_strength_threshold"],
        "bullish_direction_state": SOURCE_BACKED_PARAMS["bullish_direction_state"],
        "bearish_or_cash_direction_state": SOURCE_BACKED_PARAMS["bearish_or_cash_direction_state"],
        "parameters_tuned": SOURCE_BACKED_PARAMS["tuned_parameters"],
        "formula_contract_version": FORMULA_CONTRACT["formula_contract_version"],
        "formula_contract_complete": formula_contract_complete(),
        "canonical_adx_dmi_utility_found": any(row["canonical_adx_dmi_utility"] is True for row in utility_rows),
        "wilder_formula_contract_frozen": True,
        "uses_completed_daily_adjusted_ohlc": True,
        "previous_close_is_prior_completed_adjusted_close": True,
        "true_range_definition_documented": bool(FORMULA_CONTRACT["true_range"]),
        "positive_dm_definition_documented": bool(FORMULA_CONTRACT["positive_dm"]),
        "negative_dm_definition_documented": bool(FORMULA_CONTRACT["negative_dm"]),
        "wilder_smoothing_seed_documented": bool(FORMULA_CONTRACT["smoothed_seed"]),
        "wilder_smoothing_update_documented": bool(FORMULA_CONTRACT["smoothed_update"]),
        "di_definition_documented": bool(FORMULA_CONTRACT["di_formula"]),
        "dx_definition_documented": bool(FORMULA_CONTRACT["dx_formula"]),
        "adx_seed_documented": bool(FORMULA_CONTRACT["adx_seed"]),
        "adx_update_documented": bool(FORMULA_CONTRACT["adx_update"]),
        "divide_by_zero_behavior_documented": bool(FORMULA_CONTRACT["divide_by_zero"]),
        "invalid_indicator_rows_signal_blocked": True,
        "warmup_effective_start_documented": warmup["warmup_contract_complete"],
        "first_valid_di_date": warmup["first_valid_di_date"],
        "first_valid_adx_date": warmup["first_valid_adx_date"],
        "effective_start_date_after_alignment_and_warmup": warmup[
            "effective_start_date_after_alignment_and_warmup"
        ],
        "alternative_adx_thresholds_added": False,
        "alternative_dmi_periods_added": False,
        "threshold_sweep_created": False,
        "spy200d_added_as_source_filter": False,
        "moving_average_filters_added": False,
        "rsi_macd_cci_bollinger_volume_filters_added": False,
        "volatility_filters_added": False,
        "other_indicators_added": False,
        "stop_loss_or_profit_target_added": False,
        "alternate_exits_added": False,
        "optimization_run": False,
        "similarity_hit_preserved": bool(review["single_intake_similarity_hits"] or review["batch_similarity_hits"]),
        "similarity_hit_count": review["single_intake_similarity_hit_count"],
        "duplicate_or_do_not_retest_blocker": False,
        "uses_only_spy_and_bil": True,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "spy_ohlc_cache_ready": any(
            row["symbol"] == "SPY"
            and row["data_requirement_status"] == "daily_adjusted_ohlc_ready_for_adx_dmi"
            for row in cache
        ),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
        "formula_signal_definition_documented": True,
        "long_only_adaptation_caveat_documented": True,
        "similarity_risk_documented": True,
        "signal_timing_convention_documented": True,
        "no_lookahead_timing_documented": True,
        "bounded_bt_design_packet_created": True,
        "executable_bounded_bt_design_created": readiness == RUN_READY,
        "bounded_run_implementation_created": False,
        "bounded_bt_lane_run": False,
        "strategy_backtest_run": False,
        "strategy_implemented": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "additional_public_sources_ingested": False,
        "new_instruments_added": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
        "current_backtester_replaced": False,
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
        "public_source_presence_is_profitability_proof": False,
        "outputs_non_promotable": True,
        "run_readiness_decision": readiness,
        "run_readiness_blocker": blocker,
        "next_action": next_action,
    }


def run_readiness_md(manifest: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source ADX/DMI Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source ADX/DMI Bounded bt Design

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake reviewed: `{manifest['source_intake_reviewed']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Source-backed parameters: `{manifest['source_backed_parameters']}`

DMI/ADX period: `{manifest['dmi_adx_period']}`

ADX trend-strength threshold: `{manifest['adx_trend_strength_threshold']}`

Bullish direction state: `{manifest['bullish_direction_state']}`

Bearish/cash direction state: `{manifest['bearish_or_cash_direction_state']}`

Parameters tuned: `{manifest['parameters_tuned']}`

Similarity hit count: `{manifest['similarity_hit_count']}`

Duplicate/do-not-retest blocker: `{manifest['duplicate_or_do_not_retest_blocker']}`

Planned rows: `{manifest['planned_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

SPY OHLC cache ready: `{manifest['spy_ohlc_cache_ready']}`

bt adapter ready for design: `{manifest['bt_adapter_ready_for_design']}`

Formula/signal definition documented: `{manifest['formula_signal_definition_documented']}`

Long-only adaptation caveat documented: `{manifest['long_only_adaptation_caveat_documented']}`

Formula contract complete: `{manifest['formula_contract_complete']}`

Canonical ADX/DMI utility found: `{manifest['canonical_adx_dmi_utility_found']}`

First valid +DI/-DI date: `{manifest['first_valid_di_date']}`

First valid ADX date: `{manifest['first_valid_adx_date']}`

Effective start date after alignment and warmup: `{manifest['effective_start_date_after_alignment_and_warmup']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No ADX/DMI backtest, bounded run implementation, source scraping, strategy discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live path, provider download, intraday data, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_adx_dmi_bounded_bt_design_consistency_check.json"] = True
    checks = {
        "design_only": manifest["public_source_adx_dmi_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "single_intake_reviewed": manifest["single_source_intake_evidence_reviewed"] is True,
        "batch_intake_reviewed": manifest["batch_intake_evidence_reviewed"] is True,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "batch_intake_eligible": manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "uses_only_validated_candidate": manifest["uses_only_validated_adx_dmi_candidate"] is True,
        "source_backed_not_tuned": manifest["source_backed_parameters"] is True
        and manifest["parameter_status"] == "source_backed_parameters"
        and manifest["parameters_tuned"] is False,
        "formula_contract_complete": manifest["formula_contract_complete"] is True
        and manifest["formula_contract_version"] == "adx_dmi_wilder_contract_v1"
        and manifest["wilder_formula_contract_frozen"] is True
        and manifest["canonical_adx_dmi_utility_found"] is False,
        "formula_components_documented": manifest["uses_completed_daily_adjusted_ohlc"] is True
        and manifest["previous_close_is_prior_completed_adjusted_close"] is True
        and manifest["true_range_definition_documented"] is True
        and manifest["positive_dm_definition_documented"] is True
        and manifest["negative_dm_definition_documented"] is True
        and manifest["wilder_smoothing_seed_documented"] is True
        and manifest["wilder_smoothing_update_documented"] is True
        and manifest["di_definition_documented"] is True
        and manifest["dx_definition_documented"] is True
        and manifest["adx_seed_documented"] is True
        and manifest["adx_update_documented"] is True
        and manifest["divide_by_zero_behavior_documented"] is True
        and manifest["invalid_indicator_rows_signal_blocked"] is True,
        "warmup_documented": manifest["warmup_effective_start_documented"] is True
        and bool(manifest["first_valid_di_date"])
        and bool(manifest["first_valid_adx_date"])
        and bool(manifest["effective_start_date_after_alignment_and_warmup"]),
        "source_parameters_frozen": manifest["dmi_adx_period"] == 14
        and manifest["adx_trend_strength_threshold"] == 25
        and manifest["bullish_direction_state"] == "+DI above -DI"
        and manifest["bearish_or_cash_direction_state"] == "-DI above +DI",
        "row_count_bounded": manifest["planned_row_count_target_4_to_5"] is True
        and manifest["planned_row_count_lte_5"] is True
        and len(rows) == manifest["planned_row_count"],
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] <= 1
        and manifest["control_row_count"] == 3,
        "no_threshold_or_indicator_expansion": manifest["alternative_adx_thresholds_added"] is False
        and manifest["alternative_dmi_periods_added"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["spy200d_added_as_source_filter"] is False
        and manifest["moving_average_filters_added"] is False
        and manifest["rsi_macd_cci_bollinger_volume_filters_added"] is False
        and manifest["volatility_filters_added"] is False
        and manifest["other_indicators_added"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["alternate_exits_added"] is False,
        "similarity_risk_preserved_without_blocking": manifest["similarity_hit_preserved"] is True
        and manifest["similarity_hit_count"] == 12
        and manifest["duplicate_or_do_not_retest_blocker"] is False,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["spy_ohlc_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_control_poc_passed"] is True
        and manifest["bt_adapter_multasset_poc_passed"] is True
        and manifest["bt_adapter_ready_for_design"] is True,
        "reports_documented": manifest["formula_signal_definition_documented"] is True
        and manifest["long_only_adaptation_caveat_documented"] is True
        and manifest["similarity_risk_documented"] is True,
        "timing_documented": manifest["signal_timing_convention_documented"] is True
        and manifest["no_lookahead_timing_documented"] is True,
        "no_run_or_backtest": manifest["bounded_run_implementation_created"] is False
        and manifest["bounded_bt_lane_run"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_implemented"] is False,
        "no_scrape_or_extra_sources": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["additional_public_sources_ingested"] is False,
        "no_provider_intraday_packages": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["new_packages_installed"] is False,
        "no_backtester_replacement_or_discovery": manifest["current_backtester_replaced"] is False
        and manifest["strategy_discovery_run"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "not_profitability_proof": manifest["public_source_presence_is_profitability_proof"] is False,
        "outputs_non_promotable": manifest["outputs_non_promotable"] is True,
        "run_readiness_valid": manifest["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "run_ready_next_action": manifest["run_readiness_decision"] != RUN_READY
        or manifest["next_action"] == NEXT_ACTION_RUN,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    review = source_intake_review(root)
    cache = cache_rows(root)
    params = parameter_rows(review["source_intake"])
    bt = bt_readiness(root)
    rows = planned_rows()
    warmup = warmup_requirements(root)
    utility_rows = existing_utility_discovery_rows()
    manifest = manifest_payload(
        created=created,
        output=output,
        review=review,
        cache=cache,
        bt=bt,
        rows=rows,
        warmup=warmup,
        utility_rows=utility_rows,
    )

    write_json(output / "public_source_adx_dmi_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_adx_dmi_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "source_backed_parameter_report.csv", params, list(PARAM_FIELDS))
    write_text(output / "source_backed_parameter_report.md", source_backed_parameter_md(params))
    write_text(output / "formula_contract_patch_report.md", formula_contract_patch_md(warmup))
    write_text(output / "existing_utility_discovery_report.md", utility_discovery_md(utility_rows))
    write_text(output / "adx_dmi_formula_signal_definition.md", formula_signal_md())
    write_text(output / "warmup_effective_start_requirements.md", warmup_md(warmup))
    write_text(output / "long_only_adaptation_caveat.md", long_only_adaptation_md())
    write_text(output / "similarity_risk_report.md", similarity_risk_md(review))
    write_csv(output / "planned_row_table.csv", rows, list(PLANNED_ROW_FIELDS))
    write_text(output / "planned_row_table.md", planned_rows_md(rows))
    write_text(output / "signal_timing_convention.md", signal_timing_md())
    write_text(output / "baseline_control_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "bt_adapter_readiness.md", bt_readiness_md(bt))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "public_source_adx_dmi_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_adx_dmi_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
