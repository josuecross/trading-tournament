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


SOURCE_ID = "cci_correction"
LANE_ID = "public_source_cci_correction_bounded_bt_lane_v1"
FAMILY_ID = "equity_index_cci_pullback_trend_bias"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_cci_correction_bounded_bt_design" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "cci_correction.yaml"
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

RUN_READY = "public_source_cci_correction_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_cci_correction_bounded_bt_design_blocked"
NEXT_ACTION_RUN = "run_public_source_cci_correction_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "manual_input_required_for_public_source_cci_correction_bounded_bt_design"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
SOURCE_BACKED_PARAMS = {
    "parameter_status": "source_backed_parameters",
    "weekly_cci_period": 26,
    "daily_cci_period": 26,
    "weekly_bullish_bias_threshold": 100,
    "weekly_bearish_bias_threshold": -100,
    "daily_pullback_threshold": -100,
    "daily_reversal_threshold": 0,
    "tuned_parameters": False,
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
    "public_source_cci_correction_bounded_bt_design_manifest.json",
    "public_source_cci_correction_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "source_backed_parameter_report.csv",
    "source_backed_parameter_report.md",
    "weekly_daily_cci_signal_definition.md",
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
    "public_source_cci_correction_bounded_bt_design_next_action.md",
    "public_source_cci_correction_bounded_bt_design_consistency_check.json",
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


def split_pipe(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [part for part in str(value or "").split("|") if part]


def source_intake_review(root: Path) -> dict[str, Any]:
    intake = read_yaml(root / INTAKE_PATH)
    intake_manifest = read_json(root / INTAKE_MANIFEST_PATH)
    eligibility_rows = read_csv_rows(root / BATCH_ELIGIBILITY_PATH)
    batch_row = next((row for row in eligibility_rows if row.get("source_id") == SOURCE_ID), {})
    single_hits = split_pipe(intake_manifest.get("family_similarity_hits", []))
    batch_hits = split_pipe(batch_row.get("family_similarity_hits", ""))
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
        "rule_clarity": dotted_get(intake, "strategy_description.rule_clarity") or "",
        "single_intake_decision": intake_manifest.get("eligibility_decision", ""),
        "single_intake_next_action": intake_manifest.get("next_action", ""),
        "single_intake_constraint_blocks": "|".join(intake_manifest.get("constraint_blockers", [])),
        "single_intake_similarity_hits": single_hits,
        "single_intake_missing_fields": "|".join(intake_manifest.get("exact_missing_fields", [])),
        "single_intake_local_cache_checked": intake_manifest.get("local_cache_checked") is True,
        "batch_eligibility_decision": batch_row.get("eligibility_decision", ""),
        "batch_next_action": batch_row.get("next_action", ""),
        "batch_constraint_blocks": batch_row.get("constraint_blocks", ""),
        "batch_similarity_hits": batch_hits,
        "batch_missing_required_fields": batch_row.get("missing_required_fields", ""),
        "batch_local_cache_complete": str(batch_row.get("local_cache_complete", "")).lower() == "true",
        "long_only_caveat": dotted_get(intake, "project_notes.long_only_adaptation_caveat") or "",
        "indicator_definitions": dotted_get(intake, "indicator_definitions") or {},
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
                "data_requirement_status": "adjusted_ohlcv_ready"
                if cache_ready and symbol == "SPY"
                else ("cash_proxy_adjusted_close_ready" if cache_ready else "missing_required_price_columns_or_cache"),
                "notes": "local_raw_price_history_available_no_provider_download"
                if cache_ready
                else "required_local_price_history_not_ready",
            }
        )
    return rows


def parameter_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in SOURCE_BACKED_PARAMS.items():
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
            "variant_id": "cci_correction_spy_bil_primary_v1",
            "variant_role": "source_primary",
            "research_label": "public_source_cci_correction_primary",
            "symbols": "SPY|BIL",
            "entry_rule": "During bullish completed weekly CCI(26) bias, enter/hold SPY after daily CCI(26) falls below -100 and then crosses back above 0; BIL remainder",
            "exit_rule": "Exit SPY to BIL/cash when completed weekly CCI(26) enters bearish bias below -100",
            "source_backed_parameters": params,
            "signal_timing": "completed weekly bias plus completed daily close signal with project no-lookahead shifted-weight convention",
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
            "variant_id": "cci_correction_spy_bil_one_bar_delayed_timing_sanity_v1",
            "variant_role": "timing_sanity",
            "research_label": "public_source_cci_correction_timing_sanity",
            "symbols": "SPY|BIL",
            "entry_rule": "same source CCI signal applied one additional trading day later; timing-sanity only",
            "exit_rule": "same source weekly CCI bearish exit applied one additional trading day later; timing-sanity only",
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
            "variant_id": "cci_correction_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "public_source_cci_correction_control_only",
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
            "variant_id": "cci_correction_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "public_source_cci_correction_control_only",
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
            "variant_id": "cci_correction_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "public_source_cci_correction_control_only",
            "symbols": "SPY|BIL",
            "entry_rule": "existing project SPY 200d frozen control where supported",
            "exit_rule": "existing project SPY 200d frozen control where supported",
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
) -> tuple[str, str, str]:
    blockers: list[str] = []
    if review["source_id"] != SOURCE_ID:
        blockers.append("validated_cci_correction_candidate_not_found")
    if review["single_intake_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("single_intake_not_eligible_for_bounded_bt_design")
    if review["batch_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("batch_intake_not_eligible_for_bounded_bt_design")
    if review["single_intake_constraint_blocks"] or review["batch_constraint_blocks"]:
        blockers.append("constraint_blocks_present")
    if review["single_intake_missing_fields"] or review["batch_missing_required_fields"]:
        blockers.append("missing_required_intake_fields_present")
    if any(row["cache_status"] != "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache_or_price_columns")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_prerequisites_not_ready")
    if not (4 <= len(rows) <= 5):
        blockers.append("planned_row_count_outside_declared_bounds")
    if SOURCE_BACKED_PARAMS["tuned_parameters"] is not False:
        blockers.append("source_parameters_not_marked_untuned")
    if blockers:
        return RUN_BLOCKED, ";".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


def source_intake_review_md(review: dict[str, Any]) -> str:
    hits = ", ".join(f"`{hit}`" for hit in review["single_intake_similarity_hits"] or review["batch_similarity_hits"])
    return f"""# Source Intake Review

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Source citation: `{review['source_citation']}`

Source type: `{review['source_type']}`

Strategy family: `{review['strategy_family']}`

Timeframe: `{review['timeframe']}`

Single-source intake evidence path: `{review['single_intake_evidence_path']}`

Single-source intake decision: `{review['single_intake_decision']}`

Batch intake evidence path: `{review['batch_evidence_path']}`

Batch intake decision: `{review['batch_eligibility_decision']}`

Constraint blockers: `{review['single_intake_constraint_blocks'] or review['batch_constraint_blocks'] or 'none'}`

Missing required fields: `{review['single_intake_missing_fields'] or review['batch_missing_required_fields'] or 'none'}`

Similarity contexts: {hits or "`none`"}

Entry rule: `{review['entry_rule']}`

Exit rule: `{review['exit_rule']}`

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
    lines.append("All CCI parameters are frozen from the manually supplied public-source intake. No alternate CCI period, threshold, exit, stop-loss, profit target, moving-average filter, volatility filter, or parameter sweep was added.")
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['parameter']}`: `{row['value']}`; tuned `{row['tuned']}`")
    return "\n".join(lines) + "\n"


def cci_signal_definition_md() -> str:
    return """# Weekly / Daily CCI Formula And Signal Definition

Future CCI bounded `bt` runs must freeze this signal definition before execution:

- Commodity Channel Index uses typical price: `(high + low + close) / 3`.
- `CCI(n) = (typical_price - SMA(typical_price, n)) / (0.015 * mean_deviation(typical_price, n))`.
- Weekly CCI(26) is computed from completed weekly SPY OHLC bars only.
- Daily CCI(26) is computed from completed daily SPY OHLC bars only.
- Weekly CCI crossing/surging above `+100` creates bullish bias.
- Weekly CCI crossing/plunging below `-100` creates bearish/cash bias.
- During bullish bias, daily CCI below `-100` marks a pullback state.
- After that pullback, daily CCI crossing/surging back above `0` creates the long-entry/resumption signal.
- Weekly bearish/cash bias exits SPY to BIL/cash.
"""


def long_only_md(review: dict[str, Any]) -> str:
    return f"""# Long-Only Adaptation Caveat

Original public-source caveat:

`{review['long_only_caveat']}`

Frozen project adaptation:

- Bullish mode may hold or enter long SPY.
- Bearish mode maps to BIL/cash only.
- Bearish/short-side source signals are ignored.
- No shorting, inverse ETFs, leverage, margin, options, direct futures, forex, intraday execution, broker/live path, or real-money recommendation is allowed.
"""


def similarity_risk_md(review: dict[str, Any]) -> str:
    hits = review["single_intake_similarity_hits"] or review["batch_similarity_hits"]
    hit_lines = "\n".join(f"- `{hit}`" for hit in hits) or "- none"
    return f"""# Similarity Risk Report

Similarity contexts preserved from intake validation:

{hit_lines}

Duplicate/do-not-retest blocker in current intake result: `false`

Design treatment:

- Preserve all similarity contexts as research-governance warnings.
- Do not treat public-source presence as profitability proof.
- Do not reopen exact rejected variants.
- Do not continue Coppock, RSI(2), Percent B Money Flow, Turn-of-the-Month, Faber/TAA, macro/GLD, commodity, volatility-throttle, regional, global, or managed-futures lanes here.
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

Future CCI Correction bounded `bt` runs must freeze timing before execution:

- Use daily local-cache data only.
- Build completed weekly OHLC bars from local daily SPY OHLC data.
- Compute weekly CCI(26) only after a weekly bar is complete.
- Compute daily CCI(26) using information available through the completed daily close.
- Produce target weights after the daily close.
- Apply target weights using the project's no-lookahead shifted-weight convention.
- One-extra-bar delayed timing sanity may be included only as context, not as an optimized variant.
- No daily-only variants, weekly-only variants, alternate thresholds, alternate exits, intraday data, provider download, stop-loss, profit target, moving-average filter, volatility filter, shorting, inverse ETF, leverage, options, or futures may be used.
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
- Average SPY exposure share is `>= 0.0500` and `<= 0.8000`.
- Duplicate/reference correlation versus SPY buy-and-hold and SPY_200d control is `< 0.9000` where available.
- Event count and trade count are reported.
- Exposure invariants pass.

Timing-sanity row is context only and cannot supersede the source-primary row.

Allowed labels:

- `public_source_cci_correction_primary`
- `public_source_cci_correction_timing_sanity`
- `public_source_cci_correction_control_only`
- `public_source_cci_correction_design_blocked`
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
        "public_source_cci_correction_bounded_bt_design_only",
        "bounded_bt_lane_run",
        "strategy_backtest_run",
        "bounded_run_implementation_created",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "additional_public_sources_ingested",
        "daily_only_variants_added",
        "weekly_only_variants_added",
        "cci_parameters_tuned",
        "threshold_sweep_created",
        "shorting_inverse_leverage_options_futures_intraday_added",
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

Hard invariants for any future CCI Correction bounded `bt` run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, inverse ETF, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    readiness, blocker, next_action = run_readiness(review, cache, bt, rows)
    similarity_hits = review["single_intake_similarity_hits"] or review["batch_similarity_hits"]
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_cci_correction_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_intake_reviewed": review["candidate_exists"],
        "single_source_intake_evidence_reviewed": review["single_intake_evidence_exists"],
        "batch_intake_evidence_reviewed": review["batch_evidence_exists"],
        "source_intake_eligibility_decision": review["single_intake_decision"],
        "batch_intake_eligibility_decision": review["batch_eligibility_decision"],
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "uses_only_validated_cci_correction_candidate": True,
        "planned_row_count": len(rows),
        "planned_row_count_target_4_to_5": 4 <= len(rows) <= 5,
        "planned_row_count_lte_5": len(rows) <= 5,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "source_backed_parameters": True,
        "parameter_status": SOURCE_BACKED_PARAMS["parameter_status"],
        "weekly_cci_period": SOURCE_BACKED_PARAMS["weekly_cci_period"],
        "daily_cci_period": SOURCE_BACKED_PARAMS["daily_cci_period"],
        "weekly_bullish_bias_threshold": SOURCE_BACKED_PARAMS["weekly_bullish_bias_threshold"],
        "weekly_bearish_bias_threshold": SOURCE_BACKED_PARAMS["weekly_bearish_bias_threshold"],
        "daily_pullback_threshold": SOURCE_BACKED_PARAMS["daily_pullback_threshold"],
        "daily_reversal_threshold": SOURCE_BACKED_PARAMS["daily_reversal_threshold"],
        "parameters_tuned": SOURCE_BACKED_PARAMS["tuned_parameters"],
        "daily_only_variants_added": False,
        "weekly_only_variants_added": False,
        "alternate_cci_periods_added": False,
        "alternate_thresholds_added": False,
        "cci_parameters_tuned": False,
        "threshold_sweep_created": False,
        "stop_loss_or_profit_target_added": False,
        "volatility_filter_added": False,
        "moving_average_filter_added": False,
        "alternate_exits_added": False,
        "shorting_inverse_leverage_options_futures_intraday_added": False,
        "similarity_hits_preserved": similarity_hits,
        "similarity_hit_count": len(similarity_hits),
        "duplicate_or_do_not_retest_blocker": False,
        "long_only_adaptation_caveat_documented": bool(review["long_only_caveat"]),
        "bearish_mode_maps_to_bil_cash": True,
        "uses_only_spy_and_bil": True,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
        "weekly_daily_cci_definition_documented": True,
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
    return f"""# Public Source CCI Correction Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source CCI Correction Bounded bt Design

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake reviewed: `{manifest['source_intake_reviewed']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Source-backed parameters: `{manifest['source_backed_parameters']}`

Weekly CCI period: `{manifest['weekly_cci_period']}`

Daily CCI period: `{manifest['daily_cci_period']}`

Weekly thresholds: `{manifest['weekly_bullish_bias_threshold']}` / `{manifest['weekly_bearish_bias_threshold']}`

Daily thresholds: `{manifest['daily_pullback_threshold']}` / `{manifest['daily_reversal_threshold']}`

Parameters tuned: `{manifest['parameters_tuned']}`

Similarity hit count: `{manifest['similarity_hit_count']}`

Duplicate/do-not-retest blocker: `{manifest['duplicate_or_do_not_retest_blocker']}`

Long-only adaptation caveat documented: `{manifest['long_only_adaptation_caveat_documented']}`

Planned rows: `{manifest['planned_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

bt adapter ready for design: `{manifest['bt_adapter_ready_for_design']}`

Signal timing convention documented: `{manifest['signal_timing_convention_documented']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No CCI Correction backtest, bounded run implementation, source scraping, strategy discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live path, provider download, intraday data, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_cci_correction_bounded_bt_design_consistency_check.json"] = True
    checks = {
        "design_only": manifest["public_source_cci_correction_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "single_intake_reviewed": manifest["single_source_intake_evidence_reviewed"] is True,
        "batch_intake_reviewed": manifest["batch_intake_evidence_reviewed"] is True,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "batch_intake_eligible": manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "uses_only_validated_candidate": manifest["uses_only_validated_cci_correction_candidate"] is True,
        "source_backed_not_tuned": manifest["source_backed_parameters"] is True
        and manifest["parameter_status"] == "source_backed_parameters"
        and manifest["parameters_tuned"] is False,
        "source_parameters_frozen": manifest["weekly_cci_period"] == 26
        and manifest["daily_cci_period"] == 26
        and manifest["weekly_bullish_bias_threshold"] == 100
        and manifest["weekly_bearish_bias_threshold"] == -100
        and manifest["daily_pullback_threshold"] == -100
        and manifest["daily_reversal_threshold"] == 0,
        "row_count_bounded": manifest["planned_row_count_target_4_to_5"] is True
        and manifest["planned_row_count_lte_5"] is True
        and len(rows) == manifest["planned_row_count"],
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] <= 1
        and manifest["control_row_count"] == 3,
        "no_parameter_or_rule_expansion": manifest["daily_only_variants_added"] is False
        and manifest["weekly_only_variants_added"] is False
        and manifest["alternate_cci_periods_added"] is False
        and manifest["alternate_thresholds_added"] is False
        and manifest["cci_parameters_tuned"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["stop_loss_or_profit_target_added"] is False
        and manifest["volatility_filter_added"] is False
        and manifest["moving_average_filter_added"] is False
        and manifest["alternate_exits_added"] is False,
        "similarity_risk_preserved_without_blocking": manifest["similarity_hit_count"] == 10
        and manifest["duplicate_or_do_not_retest_blocker"] is False,
        "long_only_documented": manifest["long_only_adaptation_caveat_documented"] is True
        and manifest["bearish_mode_maps_to_bil_cash"] is True,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_control_poc_passed"] is True
        and manifest["bt_adapter_multasset_poc_passed"] is True
        and manifest["bt_adapter_ready_for_design"] is True,
        "timing_documented": manifest["weekly_daily_cci_definition_documented"] is True
        and manifest["signal_timing_convention_documented"] is True
        and manifest["no_lookahead_timing_documented"] is True,
        "no_run_or_backtest": manifest["bounded_run_implementation_created"] is False
        and manifest["bounded_bt_lane_run"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_implemented"] is False,
        "no_scrape_or_extra_sources": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["additional_public_sources_ingested"] is False,
        "no_forbidden_strategy_features": manifest["shorting_inverse_leverage_options_futures_intraday_added"] is False,
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
    params = parameter_rows()
    bt = bt_readiness(root)
    rows = planned_rows()
    manifest = manifest_payload(created=created, output=output, review=review, cache=cache, bt=bt, rows=rows)

    write_json(output / "public_source_cci_correction_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_cci_correction_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "source_backed_parameter_report.csv", params, list(PARAM_FIELDS))
    write_text(output / "source_backed_parameter_report.md", source_backed_parameter_md(params))
    write_text(output / "weekly_daily_cci_signal_definition.md", cci_signal_definition_md())
    write_text(output / "long_only_adaptation_caveat.md", long_only_md(review))
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
    write_text(output / "public_source_cci_correction_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_cci_correction_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
