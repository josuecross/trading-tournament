from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import dotted_get, is_missing, read_json, read_yaml


SOURCE_ID = "percent_b_money_flow"
LANE_ID = "public_source_percent_b_money_flow_bounded_bt_lane_v1"
FAMILY_ID = "price_band_money_flow_confirmation"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_percent_b_money_flow_bounded_bt_design" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "percent_b_money_flow.yaml"
)
BATCH_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
BATCH_MANIFEST_PATH = BATCH_EVIDENCE_DIR / "public_source_batch_intake_validation_manifest.json"
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

RUN_READY = "public_source_percent_b_money_flow_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_percent_b_money_flow_bounded_bt_design_blocked"
NEXT_ACTION_RUN = "run_public_source_percent_b_money_flow_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "manual_input_required_for_percent_b_money_flow_indicator_parameters"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
REQUIRED_INDICATOR_FIELDS = (
    "indicator_definitions.parameter_status",
    "indicator_definitions.bollinger_band_period",
    "indicator_definitions.bollinger_band_standard_deviation",
    "indicator_definitions.money_flow_index_period",
    "indicator_definitions.percent_b_upper_threshold",
    "indicator_definitions.percent_b_lower_threshold",
    "indicator_definitions.mfi_upper_threshold",
    "indicator_definitions.mfi_lower_threshold",
    "indicator_definitions.tuned_parameters",
)
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
    "indicator_parameters",
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
INDICATOR_FIELDS = ("indicator_field", "status", "value", "source_path", "notes")

REQUIRED_FILES = (
    "public_source_percent_b_money_flow_bounded_bt_design_manifest.json",
    "public_source_percent_b_money_flow_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "indicator_definition_completeness.csv",
    "indicator_definition_completeness.md",
    "source_backed_parameter_report.md",
    "planned_row_table.csv",
    "planned_row_table.md",
    "signal_timing_convention.md",
    "baseline_control_policy.md",
    "numeric_success_failure_criteria.md",
    "bt_adapter_readiness.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "run_readiness_decision.md",
    "public_source_percent_b_money_flow_bounded_bt_design_next_action.md",
    "public_source_percent_b_money_flow_bounded_bt_design_consistency_check.json",
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
    batch_manifest = read_json(root / BATCH_MANIFEST_PATH)
    eligibility_rows = read_csv_rows(root / BATCH_ELIGIBILITY_PATH)
    matched = next((row for row in eligibility_rows if row.get("source_id") == SOURCE_ID), {})
    return {
        "candidate_exists": (root / INTAKE_PATH).exists(),
        "batch_evidence_exists": bool(batch_manifest),
        "batch_candidate_count": batch_manifest.get("candidate_count", 0),
        "batch_consistency_source_path": str((root / BATCH_EVIDENCE_DIR).resolve()),
        "source_id": dotted_get(intake, "source.source_id") or "",
        "source_name": dotted_get(intake, "source.source_name") or "",
        "strategy_family": dotted_get(intake, "strategy_description.strategy_family") or "",
        "instruments": dotted_get(intake, "strategy_description.instruments") or [],
        "entry_rule": dotted_get(intake, "rules.entry_rule") or "",
        "exit_rule": dotted_get(intake, "rules.exit_rule") or "",
        "rule_clarity": dotted_get(intake, "strategy_description.rule_clarity") or "",
        "batch_eligibility_decision": matched.get("eligibility_decision", ""),
        "batch_next_action": matched.get("next_action", ""),
        "batch_constraint_blocks": matched.get("constraint_blocks", ""),
        "batch_similarity_hits": matched.get("family_similarity_hits", ""),
        "batch_missing_required_fields": matched.get("missing_required_fields", ""),
        "batch_local_cache_complete": str(matched.get("local_cache_complete", "")).lower() == "true",
        "bounded_design_already_created_by_batch": False,
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
                "data_requirement_status": "adjusted_ohlcv_ready" if cache_ready and symbol == "SPY" else (
                    "cash_proxy_adjusted_close_ready" if cache_ready else "missing_required_price_columns_or_cache"
                ),
                "notes": "local_raw_price_history_available_no_provider_download"
                if cache_ready
                else "required_local_price_history_not_ready",
            }
        )
    return rows


def indicator_definition_rows(intake: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in REQUIRED_INDICATOR_FIELDS:
        value = dotted_get(intake, field)
        missing = is_missing(value)
        rows.append(
            {
                "indicator_field": field,
                "status": "missing" if missing else "present",
                "value": "" if missing else value,
                "source_path": str(INTAKE_PATH),
                "notes": "required_before_executable_design; defaults_not_invented"
                if missing
                else "source_backed_parameter_supplied_by_direction_owner",
            }
        )
    return rows


def indicator_params(intake: dict[str, Any]) -> dict[str, Any]:
    return {
        "parameter_status": dotted_get(intake, "indicator_definitions.parameter_status"),
        "bollinger_band_period": dotted_get(intake, "indicator_definitions.bollinger_band_period"),
        "bollinger_band_standard_deviation": dotted_get(
            intake,
            "indicator_definitions.bollinger_band_standard_deviation",
        ),
        "money_flow_index_period": dotted_get(intake, "indicator_definitions.money_flow_index_period"),
        "percent_b_upper_threshold": dotted_get(intake, "indicator_definitions.percent_b_upper_threshold"),
        "percent_b_lower_threshold": dotted_get(intake, "indicator_definitions.percent_b_lower_threshold"),
        "mfi_upper_threshold": dotted_get(intake, "indicator_definitions.mfi_upper_threshold"),
        "mfi_lower_threshold": dotted_get(intake, "indicator_definitions.mfi_lower_threshold"),
        "source_basis": dotted_get(intake, "indicator_definitions.source_basis") or "",
        "tuned_parameters": dotted_get(intake, "indicator_definitions.tuned_parameters"),
    }


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


def planned_rows(indicators_complete: bool, params: dict[str, Any]) -> list[dict[str, Any]]:
    if not indicators_complete:
        return []
    bb_period = params["bollinger_band_period"]
    bb_sd = params["bollinger_band_standard_deviation"]
    mfi_period = params["money_flow_index_period"]
    pb_upper = params["percent_b_upper_threshold"]
    pb_lower = params["percent_b_lower_threshold"]
    mfi_upper = params["mfi_upper_threshold"]
    mfi_lower = params["mfi_lower_threshold"]
    indicator_param_text = (
        f"parameter_status=source_backed_parameters|bollinger_band_period={bb_period}|"
        f"bollinger_band_standard_deviation={bb_sd}|money_flow_index_period={mfi_period}|"
        f"percent_b_upper_threshold={pb_upper}|percent_b_lower_threshold={pb_lower}|"
        f"mfi_upper_threshold={mfi_upper}|mfi_lower_threshold={mfi_lower}"
    )
    return [
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "percent_b_mfi_spy_bil_primary_v1",
            "variant_role": "source_primary",
            "research_label": "public_source_percent_b_mfi_primary",
            "symbols": "SPY|BIL",
            "entry_rule": f"SPY weight 1.0 when Percent B({bb_period},{bb_sd}) > {pb_upper} and MFI({mfi_period}) > {mfi_upper}; BIL remainder",
            "exit_rule": f"Exit to BIL/cash when Percent B({bb_period},{bb_sd}) < {pb_lower} and MFI({mfi_period}) < {mfi_lower}",
            "indicator_parameters": indicator_param_text,
            "signal_timing": "daily close signal with project no-lookahead shifted-weight convention",
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
            "variant_id": "percent_b_mfi_spy_bil_one_bar_delayed_timing_sanity_v1",
            "variant_role": "timing_sanity",
            "research_label": "public_source_percent_b_mfi_timing_sanity",
            "symbols": "SPY|BIL",
            "entry_rule": "same source signal applied one bar later; timing-sanity only",
            "exit_rule": "same source exit applied one bar later; timing-sanity only",
            "indicator_parameters": indicator_param_text,
            "signal_timing": "one-bar-delayed target application sanity row, not a tuned variant",
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
            "variant_id": "percent_b_mfi_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "public_source_percent_b_mfi_control_only",
            "symbols": "SPY",
            "entry_rule": "SPY buy-and-hold same-window control",
            "exit_rule": "not_applicable_control",
            "indicator_parameters": "not_applicable_control",
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
            "variant_id": "percent_b_mfi_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "public_source_percent_b_mfi_control_only",
            "symbols": "BIL",
            "entry_rule": "BIL cash same-window control",
            "exit_rule": "not_applicable_control",
            "indicator_parameters": "not_applicable_control",
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
            "variant_id": "percent_b_mfi_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "public_source_percent_b_mfi_control_only",
            "symbols": "SPY|BIL",
            "entry_rule": "existing project SPY 200d frozen control where supported",
            "exit_rule": "existing project SPY 200d frozen control where supported",
            "indicator_parameters": "not_applicable_control",
            "signal_timing": "use already validated bt adapter SPY_200d control convention",
            "bt_adapter_contract": "control target weight frame; no bt run in design step",
            "baseline_or_control_role": "spy200d_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold_control|BIL_cash_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
    ]


def run_readiness(
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    indicators: list[dict[str, Any]],
    params: dict[str, Any],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[str, str, str]:
    blockers: list[str] = []
    missing_indicators = [row["indicator_field"] for row in indicators if row["status"] == "missing"]
    if review["source_id"] != SOURCE_ID or review["batch_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("percent_b_money_flow_not_cleanly_eligible_in_batch_intake")
    if review["batch_constraint_blocks"]:
        blockers.append("percent_b_money_flow_has_constraint_blocks")
    if review["batch_similarity_hits"]:
        blockers.append("percent_b_money_flow_has_similarity_or_do_not_retest_hits")
    if any(row["cache_status"] != "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache_or_price_columns")
    if missing_indicators:
        blockers.append("missing_indicator_parameters:" + "|".join(missing_indicators))
    if params.get("parameter_status") != "source_backed_parameters":
        blockers.append("indicator_parameters_not_marked_source_backed")
    if params.get("tuned_parameters") is not False:
        blockers.append("indicator_parameters_not_explicitly_marked_untuned")
    if rows and not (3 <= len(rows) <= 5 and len(rows) <= 6):
        blockers.append("planned_row_count_outside_declared_bounds")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_prerequisites_not_ready")
    if blockers:
        return RUN_BLOCKED, ";".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


def source_intake_review_md(review: dict[str, Any]) -> str:
    return f"""# Source Intake Review

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Strategy family: `{review['strategy_family']}`

Batch evidence path: `{review['batch_consistency_source_path']}`

Batch candidate count: `{review['batch_candidate_count']}`

Batch eligibility decision: `{review['batch_eligibility_decision']}`

Batch next action for this source: `{review['batch_next_action']}`

Constraint blockers: `{review['batch_constraint_blocks'] or 'none'}`

Similarity/do-not-retest hits: `{review['batch_similarity_hits'] or 'none'}`

Missing required intake fields: `{review['batch_missing_required_fields'] or 'none'}`

Local cache complete in batch intake: `{review['batch_local_cache_complete']}`

The source is manually supplied context only and is not proof of profitability.
"""


def local_cache_md(cache: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    for row in cache:
        lines.append(
            f"- `{row['symbol']}`: `{row['cache_status']}`, `{row['first_date']}` to `{row['last_date']}`, "
            f"rows `{row['rows']}`, data status `{row['data_requirement_status']}`"
        )
    lines.append("")
    lines.append("No provider download was run or authorized.")
    return "\n".join(lines) + "\n"


def indicator_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Indicator Definition Completeness", ""]
    for row in rows:
        lines.append(f"- `{row['indicator_field']}`: `{row['status']}`")
    lines.append("")
    if any(row["status"] == "missing" for row in rows):
        lines.append("Run-readiness is blocked because the intake did not supply all required indicator parameters.")
        lines.append("No Bollinger or MFI defaults were invented.")
    else:
        lines.append("All required indicator parameters were supplied by the manual intake.")
    return "\n".join(lines) + "\n"


def source_backed_parameter_md(params: dict[str, Any]) -> str:
    return f"""# Source-Backed Parameter Report

Parameter status: `{params['parameter_status']}`

Bollinger Band / Percent B period: `{params['bollinger_band_period']}`

Bollinger Band standard deviation: `{params['bollinger_band_standard_deviation']}`

Money Flow Index period: `{params['money_flow_index_period']}`

Percent B upper threshold: `{params['percent_b_upper_threshold']}`

Percent B lower threshold: `{params['percent_b_lower_threshold']}`

MFI upper threshold: `{params['mfi_upper_threshold']}`

MFI lower threshold: `{params['mfi_lower_threshold']}`

Tuned parameters: `{params['tuned_parameters']}`

Source basis: `{params['source_basis']}`

These values were supplied by the direction owner as source-backed parameters. This packet does not tune, optimize, sweep, or infer alternate settings.
"""


def planned_rows_md(rows: list[dict[str, Any]], indicators_complete: bool) -> str:
    lines = ["# Planned Row Table", ""]
    if not indicators_complete:
        lines.append("No executable rows were frozen because required indicator parameters are missing.")
        lines.append("")
        lines.append("Once parameters are supplied, the bounded design may contain only:")
        lines.append("- one primary source row")
        lines.append("- at most one one-bar-delayed timing-sanity row")
        lines.append("- SPY, BIL, and SPY_200d controls where supported")
        return "\n".join(lines) + "\n"
    for row in rows:
        lines.append(f"- `{row['variant_id']}`: role `{row['variant_role']}`, label `{row['research_label']}`")
    lines.append("")
    lines.append("All rows are diagnostic and non-promotable. Control rows are controls only.")
    return "\n".join(lines) + "\n"


def signal_timing_md() -> str:
    return """# Signal Timing Convention

Future Percent B Money Flow runs must freeze timing before execution:

- Use daily local-cache data only.
- Compute Percent B from Bollinger Bands `(20,2)` and MFI(10) using information available through the completed close.
- Produce target weights after the daily close.
- Apply target weights using the project's no-lookahead shifted-weight convention.
- Primary source row uses the source thresholds only: `%B > 0.80` and `MFI(10) > 80` for SPY exposure; `%B < 0.20` and `MFI(10) < 20` for BIL/cash.
- One-bar-delayed timing sanity may be included only as context, not as an optimized variant.
- No intraday data, provider download, threshold tuning, or additional indicators may be used.
"""


def baseline_policy_md() -> str:
    return """# Baseline / Control Policy

Diagnostic controls for any future bounded run:

- SPY buy-and-hold same-window control.
- BIL cash same-window control.
- SPY_200d frozen control where existing project conventions support it without adding new logic.

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
- Average SPY exposure share is `>= 0.0100` and `<= 0.4500`.
- Duplicate/reference correlation versus SPY buy-and-hold and SPY_200d control is `< 0.9000` where available.
- Exposure invariants pass.

Timing-sanity row is context only and cannot supersede the source-primary row.

Allowed labels:

- `public_source_percent_b_mfi_primary`
- `public_source_percent_b_mfi_timing_sanity`
- `public_source_percent_b_mfi_control_only`
- `public_source_percent_b_mfi_design_blocked`
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
        "public_source_percent_b_money_flow_bounded_bt_design_only",
        "bounded_bt_lane_run",
        "strategy_backtest_run",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "additional_public_sources_ingested",
        "threshold_sweep_created",
        "other_indicators_added",
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

Hard invariants for any future Percent B Money Flow bounded bt run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    indicators: list[dict[str, Any]],
    params: dict[str, Any],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_indicators = [row["indicator_field"] for row in indicators if row["status"] == "missing"]
    indicators_complete = not missing_indicators
    readiness, blocker, next_action = run_readiness(review, cache, indicators, params, bt, rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_percent_b_money_flow_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_intake_reviewed": review["candidate_exists"],
        "batch_intake_evidence_reviewed": review["batch_evidence_exists"],
        "source_intake_eligibility_decision": review["batch_eligibility_decision"],
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "uses_only_validated_percent_b_candidate": True,
        "planned_row_count": len(rows),
        "planned_row_count_target_3_to_5_if_unblocked": True,
        "planned_row_count_lte_6": len(rows) <= 6,
        "planned_rows_frozen": indicators_complete,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "indicator_definitions_complete": indicators_complete,
        "missing_indicator_parameters": missing_indicators,
        "source_backed_indicator_parameters": params.get("parameter_status") == "source_backed_parameters",
        "indicator_parameters_tuned": params.get("tuned_parameters") is True,
        "indicator_parameter_status": params.get("parameter_status") or "missing",
        "bollinger_band_period": params.get("bollinger_band_period"),
        "bollinger_band_standard_deviation": params.get("bollinger_band_standard_deviation"),
        "money_flow_index_period": params.get("money_flow_index_period"),
        "percent_b_upper_threshold": params.get("percent_b_upper_threshold"),
        "percent_b_lower_threshold": params.get("percent_b_lower_threshold"),
        "mfi_upper_threshold": params.get("mfi_upper_threshold"),
        "mfi_lower_threshold": params.get("mfi_lower_threshold"),
        "percent_b_thresholds_tuned": False,
        "mfi_thresholds_tuned": False,
        "bollinger_or_mfi_periods_tuned": False,
        "threshold_sweep_created": False,
        "other_indicators_added": False,
        "optimization_run": False,
        "uses_only_spy_and_bil": True,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
        "signal_timing_convention_documented": True,
        "no_lookahead_timing_documented": True,
        "bounded_bt_design_packet_created": True,
        "executable_bounded_bt_design_created": indicators_complete,
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

Missing indicator parameters: `{manifest['missing_indicator_parameters']}`

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Percent B Money Flow Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Percent B Money Flow Bounded bt Design

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake reviewed: `{manifest['source_intake_reviewed']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Indicator definitions complete: `{manifest['indicator_definitions_complete']}`

Missing indicator parameters: `{manifest['missing_indicator_parameters']}`

Source-backed indicator parameters: `{manifest['source_backed_indicator_parameters']}`

Indicator parameters tuned: `{manifest['indicator_parameters_tuned']}`

Planned rows frozen: `{manifest['planned_rows_frozen']}`

Planned rows: `{manifest['planned_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

bt adapter ready for design: `{manifest['bt_adapter_ready_for_design']}`

Signal timing convention documented: `{manifest['signal_timing_convention_documented']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No Percent B Money Flow backtest, bounded run implementation, source scraping, strategy discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live path, provider download, intraday data, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_percent_b_money_flow_bounded_bt_design_consistency_check.json"] = True
    blocked_expected = bool(manifest["missing_indicator_parameters"])
    ready_expected = (
        manifest["indicator_definitions_complete"] is True
        and manifest["source_backed_indicator_parameters"] is True
        and manifest["indicator_parameters_tuned"] is False
        and manifest["run_readiness_decision"] == RUN_READY
        and manifest["run_readiness_blocker"] == "none"
        and manifest["planned_rows_frozen"] is True
        and 3 <= manifest["planned_row_count"] <= 5
        and manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] <= 1
        and manifest["control_row_count"] == 3
    )
    checks = {
        "design_only": manifest["public_source_percent_b_money_flow_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "batch_intake_reviewed": manifest["batch_intake_evidence_reviewed"] is True,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "uses_only_validated_candidate": manifest["uses_only_validated_percent_b_candidate"] is True,
        "indicator_parameters_complete_or_precisely_blocked": ready_expected
        or (
            manifest["indicator_definitions_complete"] is False
            and blocked_expected
            and manifest["run_readiness_decision"] == RUN_BLOCKED
            and manifest["planned_rows_frozen"] is False
            and manifest["planned_row_count"] == 0
            and rows == []
        ),
        "source_backed_not_tuned": manifest["source_backed_indicator_parameters"] is True
        and manifest["indicator_parameters_tuned"] is False,
        "row_count_bounded": manifest["planned_row_count_lte_6"] is True
        and (manifest["planned_row_count"] == 0 or 3 <= manifest["planned_row_count"] <= 5),
        "row_roles_expected_if_ready": manifest["run_readiness_decision"] != RUN_READY
        or (
            manifest["primary_source_row_count"] == 1
            and manifest["timing_sanity_row_count"] == 1
            and manifest["control_row_count"] == 3
        ),
        "no_threshold_or_indicator_expansion": manifest["percent_b_thresholds_tuned"] is False
        and manifest["mfi_thresholds_tuned"] is False
        and manifest["bollinger_or_mfi_periods_tuned"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["other_indicators_added"] is False,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_control_poc_passed"] is True
        and manifest["bt_adapter_multasset_poc_passed"] is True
        and manifest["bt_adapter_ready_for_design"] is True,
        "timing_documented": manifest["signal_timing_convention_documented"] is True
        and manifest["no_lookahead_timing_documented"] is True,
        "no_run_or_backtest": manifest["bounded_bt_lane_run"] is False
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
    indicators = indicator_definition_rows(review["source_intake"])
    params = indicator_params(review["source_intake"])
    bt = bt_readiness(root)
    indicators_complete = all(row["status"] == "present" for row in indicators)
    rows = planned_rows(indicators_complete, params)
    manifest = manifest_payload(
        created=created,
        output=output,
        review=review,
        cache=cache,
        indicators=indicators,
        params=params,
        bt=bt,
        rows=rows,
    )

    write_json(output / "public_source_percent_b_money_flow_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_percent_b_money_flow_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "indicator_definition_completeness.csv", indicators, list(INDICATOR_FIELDS))
    write_text(output / "indicator_definition_completeness.md", indicator_md(indicators))
    write_text(output / "source_backed_parameter_report.md", source_backed_parameter_md(params))
    write_csv(output / "planned_row_table.csv", rows, list(PLANNED_ROW_FIELDS))
    write_text(output / "planned_row_table.md", planned_rows_md(rows, indicators_complete))
    write_text(output / "signal_timing_convention.md", signal_timing_md())
    write_text(output / "baseline_control_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "bt_adapter_readiness.md", bt_readiness_md(bt))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "public_source_percent_b_money_flow_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_percent_b_money_flow_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
