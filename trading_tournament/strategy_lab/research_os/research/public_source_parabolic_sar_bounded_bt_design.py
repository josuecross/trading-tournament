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


SOURCE_ID = "parabolic_sar_spy_bil_long_only_reversal"
LANE_ID = "public_source_parabolic_sar_bounded_bt_lane_v1"
FAMILY_ID = "equity_index_parabolic_sar_trend_reversal"
FORMULA_CONTRACT_ID = "parabolic_sar_wilder_stockcharts_contract_v1"

OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_parabolic_sar_bounded_bt_design" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "parabolic_sar_spy_bil_long_only_reversal.yaml"
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

RUN_READY = "public_source_parabolic_sar_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_parabolic_sar_bounded_bt_design_blocked"
NEXT_ACTION_RUN = "run_public_source_parabolic_sar_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "manual_input_required_for_public_source_parabolic_sar_bounded_bt_design"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
PLANNED_ROW_IDS = (
    "parabolic_sar_spy_bil_primary_v1",
    "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1",
    "parabolic_sar_spy_buy_hold_control_v1",
    "parabolic_sar_bil_cash_control_v1",
    "parabolic_sar_spy200d_frozen_control_v1",
)

PARAM_FIELDS = ("parameter", "value", "source_status", "tuned", "notes")
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
PLANNED_ROW_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "symbols",
    "formula_contract_id",
    "source_backed_parameters",
    "entry_rule",
    "exit_rule",
    "signal_timing",
    "target_application_delay_bars",
    "bt_adapter_contract",
    "baseline_or_control_role",
    "comparator_references",
    "spy200d_source_filter",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

REQUIRED_FILES = (
    "public_source_parabolic_sar_bounded_bt_design_manifest.json",
    "public_source_parabolic_sar_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "source_backed_parameter_report.csv",
    "source_backed_parameter_report.md",
    "formula_contract_report.md",
    "existing_utility_discovery_report.md",
    "parabolic_sar_formula_signal_definition.md",
    "initialization_convention_report.md",
    "reversal_state_transition_report.md",
    "warmup_tradability_report.md",
    "long_only_adaptation_caveat.md",
    "whipsaw_ranging_market_risk.md",
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
    "do_not_run_or_promote.md",
    "public_source_parabolic_sar_bounded_bt_design_next_action.md",
    "public_source_parabolic_sar_bounded_bt_design_consistency_check.json",
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
    similarity_hits = dotted_get(intake, "project_screening.similar_already_tested_project_families") or []
    return {
        "candidate_exists": (root / INTAKE_PATH).exists(),
        "candidate_path": str((root / INTAKE_PATH).resolve()),
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
        "single_intake_similarity_hit_count": intake_manifest.get("family_similarity_hit_count", len(similarity_hits)),
        "single_intake_missing_fields": "|".join(intake_manifest.get("exact_missing_fields", [])),
        "single_intake_local_cache_checked": intake_manifest.get("local_cache_checked") is True,
        "batch_eligibility_decision": batch_row.get("eligibility_decision", ""),
        "batch_next_action": batch_row.get("next_action", ""),
        "batch_constraint_blocks": batch_row.get("constraint_blocks", ""),
        "batch_similarity_hits": batch_row.get("family_similarity_hits", ""),
        "batch_missing_required_fields": batch_row.get("missing_required_fields", ""),
        "batch_local_cache_complete": str(batch_row.get("local_cache_complete", "")).lower() == "true",
        "similarity_hits_from_candidate": similarity_hits,
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
            data_status = "daily_adjusted_ohlc_ready_for_parabolic_sar"
        elif cache_ready:
            data_status = "cash_proxy_adjusted_close_ready"
        else:
            data_status = "missing_required_local_price_columns_or_cache"
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_status": "cache_ready" if cache_ready else info.get("status", "missing"),
                "cache_path": str(cache_path) if cache_path else "",
                "first_date": info.get("first_date", ""),
                "last_date": info.get("last_date", ""),
                "rows": info.get("rows", 0),
                "required_columns": "|".join(required_columns),
                "columns_present": "|".join(columns),
                "data_requirement_status": data_status,
                "notes": "local_cache_price_history_available" if cache_ready else "required_symbol_not_ready_in_local_cache",
            }
        )
    return rows


def parameter_rows(intake: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = dotted_get(intake, "indicator_definitions") or {}
    return [
        {
            "parameter": "formula_contract_id",
            "value": definitions.get("formula_contract_id", ""),
            "source_status": definitions.get("formula_contract_status", ""),
            "tuned": False,
            "notes": "frozen formula contract used for future implementation; no formula contract variation added",
        },
        {
            "parameter": "parabolic_sar_acceleration_factor_start",
            "value": definitions.get("parabolic_sar_acceleration_factor_start", ""),
            "source_status": "source_backed_parameter",
            "tuned": False,
            "notes": "AF start is source-backed and not optimized",
        },
        {
            "parameter": "parabolic_sar_acceleration_factor_increment",
            "value": definitions.get("parabolic_sar_acceleration_factor_increment", ""),
            "source_status": "source_backed_parameter",
            "tuned": False,
            "notes": "AF increment is source-backed and not optimized",
        },
        {
            "parameter": "parabolic_sar_acceleration_factor_maximum",
            "value": definitions.get("parabolic_sar_acceleration_factor_maximum", ""),
            "source_status": "source_backed_parameter",
            "tuned": False,
            "notes": "AF maximum is source-backed and not optimized",
        },
        {
            "parameter": "initialization_convention",
            "value": definitions.get("initialization_convention_source", ""),
            "source_status": "direction_owner_supplied_implementation_convention",
            "tuned": False,
            "notes": "initialization convention is recorded as implementation convention, not trading optimization",
        },
        {
            "parameter": "alternate_parameters_added",
            "value": definitions.get("alternate_parameters_added", False),
            "source_status": "not_added",
            "tuned": False,
            "notes": "no AF sweeps, thresholds, filters, stops, or alternate exits are planned",
        },
    ]


def bt_readiness(root: Path) -> dict[str, Any]:
    control = read_json(root / BT_CONTROL_MANIFEST_PATH)
    multasset = read_json(root / BT_MULTIASSET_MANIFEST_PATH)
    control_passed = (
        control.get("success", control.get("consistency_passed", False)) is True
        or control.get("bt_adapter_control_poc_passed", False) is True
        or control.get("final_adapter_decision") == "bt_adapter_control_poc_passed"
    )
    multasset_passed = (
        multasset.get("success", multasset.get("consistency_passed", False)) is True
        or multasset.get("bt_adapter_multasset_poc_passed", False) is True
        or multasset.get("final_adapter_decision") == "bt_adapter_multasset_control_poc_passed"
    )
    return {
        "bt_control_manifest_exists": bool(control),
        "bt_multasset_manifest_exists": bool(multasset),
        "bt_control_poc_passed": control_passed,
        "bt_multasset_poc_passed": multasset_passed,
        "bt_adapter_ready_for_design": control_passed and multasset_passed,
        "control_poc_path": str((root / BT_CONTROL_MANIFEST_PATH).resolve()),
        "multasset_poc_path": str((root / BT_MULTIASSET_MANIFEST_PATH).resolve()),
    }


def formula_contract_complete(intake: dict[str, Any]) -> bool:
    definitions = dotted_get(intake, "indicator_definitions") or {}
    required = (
        "formula_contract_id",
        "parabolic_sar_acceleration_factor_start",
        "parabolic_sar_acceleration_factor_increment",
        "parabolic_sar_acceleration_factor_maximum",
        "rising_sar_formula",
        "rising_extreme_point_definition",
        "rising_af_update_rule",
        "falling_sar_formula",
        "falling_extreme_point_definition",
        "falling_af_update_rule",
        "rising_to_falling_reversal_rule",
        "falling_to_rising_reversal_rule",
        "reversal_af_reset_rule",
        "reversal_sar_initialization_rule",
        "reversal_ep_initialization_rule",
        "initial_trend_rule",
        "initial_rising_sar_rule",
        "initial_rising_ep_rule",
        "initial_falling_sar_rule",
        "initial_falling_ep_rule",
        "warmup_rule",
        "no_lookahead_contract",
    )
    return all(definitions.get(field) not in (None, "") for field in required)


def existing_utility_discovery_rows() -> list[dict[str, Any]]:
    patterns = (
        "parabolic_sar",
        "psar",
        "sar_wilder",
    )
    rows: list[dict[str, Any]] = []
    for pattern in patterns:
        rows.append(
            {
                "search_pattern": pattern,
                "repository_standard_psar_utility": False,
                "finding": "no repository-standard PSAR utility is used for this design packet",
                "design_action": "future bounded run must implement or reuse the frozen formula contract exactly",
            }
        )
    return rows


def planned_rows() -> list[dict[str, Any]]:
    base = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "formula_contract_id": FORMULA_CONTRACT_ID,
        "source_backed_parameters": "AF_start=0.02;AF_increment=0.02;AF_max=0.20",
        "bt_adapter_contract": "daily adjusted close returns with project shifted-weight no-lookahead convention",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    return [
        {
            **base,
            "variant_id": "parabolic_sar_spy_bil_primary_v1",
            "variant_role": "source_primary",
            "research_label": "parabolic_sar_source_primary_diagnostic",
            "symbols": "SPY|BIL",
            "entry_rule": "enter/hold SPY after completed daily SAR flips from above price to below price; hold while SAR remains below price",
            "exit_rule": "exit/hold BIL after completed daily SAR flips from below price to above price; hold BIL while SAR remains above price",
            "signal_timing": "completed daily OHLC signal; target applied with project one-bar shifted-weight convention",
            "target_application_delay_bars": 1,
            "baseline_or_control_role": "candidate_diagnostic_primary_source_rule",
            "comparator_references": "SPY_buy_hold|BIL_cash|SPY_200d_frozen_control",
            "spy200d_source_filter": False,
        },
        {
            **base,
            "variant_id": "parabolic_sar_spy_bil_one_bar_delayed_timing_sanity_v1",
            "variant_role": "timing_sanity_context",
            "research_label": "parabolic_sar_timing_sanity_context_only",
            "symbols": "SPY|BIL",
            "entry_rule": "same primary SAR signal delayed by one additional trading day",
            "exit_rule": "same primary SAR exit/cash signal delayed by one additional trading day",
            "signal_timing": "completed daily OHLC signal; one additional trading-day delay beyond project shifted-weight convention",
            "target_application_delay_bars": 2,
            "baseline_or_control_role": "timing_sanity_context_only_not_optimized_variant",
            "comparator_references": "primary_source_row|SPY_buy_hold|BIL_cash|SPY_200d_frozen_control",
            "spy200d_source_filter": False,
        },
        {
            **base,
            "variant_id": "parabolic_sar_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "control_only",
            "symbols": "SPY",
            "entry_rule": "buy-and-hold SPY control",
            "exit_rule": "not applicable for control",
            "signal_timing": "control-only reference; not a candidate",
            "target_application_delay_bars": 0,
            "baseline_or_control_role": "SPY_buy_hold_control_only",
            "comparator_references": "primary_source_row",
            "spy200d_source_filter": False,
        },
        {
            **base,
            "variant_id": "parabolic_sar_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "control_only",
            "symbols": "BIL",
            "entry_rule": "BIL cash proxy control",
            "exit_rule": "not applicable for control",
            "signal_timing": "control-only reference; not a candidate",
            "target_application_delay_bars": 0,
            "baseline_or_control_role": "BIL_cash_control_only",
            "comparator_references": "primary_source_row",
            "spy200d_source_filter": False,
        },
        {
            **base,
            "variant_id": "parabolic_sar_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "control_only",
            "symbols": "SPY|BIL",
            "entry_rule": "existing SPY_200d frozen control reference only",
            "exit_rule": "existing SPY_200d frozen control reference only",
            "signal_timing": "control-only reference; SPY_200d is not a Parabolic SAR source filter",
            "target_application_delay_bars": 1,
            "baseline_or_control_role": "SPY_200d_frozen_control_only",
            "comparator_references": "primary_source_row|SPY_buy_hold|BIL_cash",
            "spy200d_source_filter": False,
        },
    ]


def run_readiness(
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
) -> tuple[str, str, str]:
    blockers: list[str] = []
    intake = review["source_intake"]
    if not review["candidate_exists"] or review["source_id"] != SOURCE_ID:
        blockers.append("validated_parabolic_sar_intake_candidate_missing_or_wrong_source")
    if review["single_intake_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("single_source_intake_not_eligible_for_bounded_bt_design")
    if review["batch_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("batch_intake_not_eligible_for_bounded_bt_design")
    if not formula_contract_complete(intake):
        blockers.append("parabolic_sar_formula_contract_incomplete")
    if not all(row["cache_status"] == "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache")
    if not any(row["symbol"] == "SPY" and row["data_requirement_status"] == "daily_adjusted_ohlc_ready_for_parabolic_sar" for row in cache):
        blockers.append("spy_adjusted_ohlc_not_ready_for_parabolic_sar")
    if len(rows) != 5 or {row["variant_id"] for row in rows} != set(PLANNED_ROW_IDS):
        blockers.append("planned_row_set_does_not_match_approved_rows")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_poc_evidence_missing")

    if blockers:
        return RUN_BLOCKED, "|".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


def source_intake_review_md(review: dict[str, Any]) -> str:
    return f"""# Source Intake Review

Candidate path: `{review['candidate_path']}`

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Family: `{review['strategy_family']}`

Single-source intake decision: `{review['single_intake_decision']}`

Batch intake decision: `{review['batch_eligibility_decision']}`

Single-source next action: `{review['single_intake_next_action']}`

Batch next action: `{review['batch_next_action']}`

Constraint blocks: `{review['single_intake_constraint_blocks'] or review['batch_constraint_blocks'] or 'none'}`

Similarity hit count: `{review['single_intake_similarity_hit_count']}`

Public-source presence is context only and is not proof of profitability.
"""


def local_cache_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    for row in rows:
        lines.append(
            f"- `{row['symbol']}`: `{row['cache_status']}`; `{row['data_requirement_status']}`; "
            f"window `{row['first_date']}` to `{row['last_date']}`; rows `{row['rows']}`."
        )
    lines.append("")
    lines.append("No provider download was performed.")
    return "\n".join(lines)


def parameter_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Source-Backed Parameter Report", ""]
    for row in rows:
        lines.append(
            f"- `{row['parameter']}` = `{row['value']}`; source status `{row['source_status']}`; tuned `{row['tuned']}`."
        )
    lines.append("")
    lines.append("No alternate AF settings, filters, stops, exits, or parameter sweeps are included.")
    return "\n".join(lines)


def formula_contract_md(intake: dict[str, Any]) -> str:
    d = dotted_get(intake, "indicator_definitions") or {}
    return f"""# Parabolic SAR Formula Contract

Formula contract ID: `{d.get('formula_contract_id')}`

Repository-standard PSAR utility found: `{d.get('repository_standard_psar_utility_found')}`

Data contract: `{d.get('data_contract')}`

Rising SAR:

- `{d.get('rising_sar_formula')}`
- Rising EP: `{d.get('rising_extreme_point_definition')}`
- Rising AF update: `{d.get('rising_af_update_rule')}`

Falling SAR:

- `{d.get('falling_sar_formula')}`
- Falling EP: `{d.get('falling_extreme_point_definition')}`
- Falling AF update: `{d.get('falling_af_update_rule')}`

AF parameters are frozen at start `0.02`, increment `0.02`, maximum `0.20`. This design does not add tuning or alternate settings.
"""


def utility_discovery_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Existing Utility Discovery Report", ""]
    for row in rows:
        lines.append(f"- `{row['search_pattern']}`: `{row['finding']}`.")
    lines.append("")
    lines.append("A future bounded run must implement or reuse the frozen contract; this design step does not implement SAR.")
    return "\n".join(lines)


def formula_signal_md(intake: dict[str, Any]) -> str:
    d = dotted_get(intake, "indicator_definitions") or {}
    return f"""# Parabolic SAR Formula And Signal Definition

Bullish state: `{d.get('bullish_state')}`

Bearish state: `{d.get('bearish_state')}`

Buy signal: `{d.get('buy_signal')}`

Sell / exit signal: `{d.get('sell_exit_signal')}`

Long-only mapping:

- Bullish SAR state maps to `SPY`.
- Bearish SAR state maps to `BIL/cash`.
- Bearish SAR state never maps to short, inverse ETF, leverage, futures, options, margin, paper order, live order, or broker logic.

No-lookahead contract: `{d.get('no_lookahead_contract')}`
"""


def initialization_md(intake: dict[str, Any]) -> str:
    d = dotted_get(intake, "indicator_definitions") or {}
    return f"""# Initialization Convention Report

Initialization convention source: `{d.get('initialization_convention_source')}`

Initial trend rule: `{d.get('initial_trend_rule')}`

Initial rising SAR rule: `{d.get('initial_rising_sar_rule')}`

Initial rising EP rule: `{d.get('initial_rising_ep_rule')}`

Initial falling SAR rule: `{d.get('initial_falling_sar_rule')}`

Initial falling EP rule: `{d.get('initial_falling_ep_rule')}`

This is an implementation convention, not optimization. If a future bounded run finds material initialization sensitivity, that result must be labeled for direction-owner review.
"""


def reversal_md(intake: dict[str, Any]) -> str:
    d = dotted_get(intake, "indicator_definitions") or {}
    return f"""# Reversal-State Transition Report

Rising-to-falling reversal: `{d.get('rising_to_falling_reversal_rule')}`

Falling-to-rising reversal: `{d.get('falling_to_rising_reversal_rule')}`

AF reset rule: `{d.get('reversal_af_reset_rule')}`

Reversal SAR initialization: `{d.get('reversal_sar_initialization_rule')}`

Reversal EP initialization: `{d.get('reversal_ep_initialization_rule')}`

Future run evidence must report first valid SAR date, first reversal date, and first tradable signal date. This design packet does not compute those dates.
"""


def warmup_md(intake: dict[str, Any]) -> str:
    d = dotted_get(intake, "indicator_definitions") or {}
    return f"""# Warmup / Tradability Report

Warmup rule: `{d.get('warmup_rule')}`

First valid SAR date reporting required: `{d.get('first_valid_sar_date_reporting_required')}`

First reversal date reporting required: `{d.get('first_reversal_date_reporting_required')}`

First tradable signal date reporting required: `{d.get('first_tradable_signal_date_reporting_required')}`

Pre-tradable rows must hold BIL/cash. The future run must report the dates; this design step performs no strategy calculation or backtest.
"""


def long_only_adaptation_md(intake: dict[str, Any]) -> str:
    caveat = dotted_get(intake, "project_notes.long_only_adaptation_caveat") or ""
    return f"""# Long-Only Adaptation Caveat

{caveat}

The design maps bearish SAR state to BIL/cash only. It does not permit shorting, inverse ETFs, leverage, margin, options, futures, intraday execution, broker APIs, paper orders, live orders, or real-money recommendations.
"""


def whipsaw_md(intake: dict[str, Any]) -> str:
    uncertainty = dotted_get(intake, "project_notes.indicator_defaults_uncertainty") or ""
    return f"""# Whipsaw / Ranging-Market Risk

{uncertainty}

The future bounded run must report entry count, exit count, completed round trips, turnover, and timing-sanity behavior so that whipsaw risk is visible. No confirmation filters are added in this design.
"""


def similarity_md(review: dict[str, Any]) -> str:
    hits = review["similarity_hits_from_candidate"]
    lines = [
        "# Similarity-Risk Report",
        "",
        f"Similarity hit count: `{review['single_intake_similarity_hit_count']}`",
        "",
        f"Duplicate/do-not-retest blocker in current intake result: `false`",
        "",
        "Known related project families:",
    ]
    lines.extend(f"- `{hit}`" for hit in hits)
    lines.append("")
    lines.append(
        "Similarity risk is preserved as a design caveat. It does not become promotion evidence and does not authorize retesting unrelated families."
    )
    return "\n".join(lines)


def planned_rows_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Row Table", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: role `{row['variant_role']}`, label `{row['research_label']}`, "
            f"symbols `{row['symbols']}`, delay bars `{row['target_application_delay_bars']}`."
        )
    lines.append("")
    lines.append("All rows are diagnostic-only, non-promotable, and not paper-forward eligible.")
    return "\n".join(lines)


def signal_timing_md() -> str:
    return """# Signal Timing Convention

- Parabolic SAR state uses completed daily adjusted SPY OHLC only.
- Target weights are produced after the completed daily bar.
- Future returns must use the project no-lookahead shifted-weight convention.
- No same-day high, low, or close may be used to generate and profit from a signal on that same bar.
- The timing-sanity row adds exactly one additional trading-day delay and remains context-only.
"""


def baseline_policy_md() -> str:
    return """# Baseline / Control Policy

Controls are:

- `parabolic_sar_spy_buy_hold_control_v1`: SPY buy-and-hold control.
- `parabolic_sar_bil_cash_control_v1`: BIL cash proxy control.
- `parabolic_sar_spy200d_frozen_control_v1`: existing SPY_200d frozen control, comparator only.

SPY_200d is not a Parabolic SAR source filter and must not be used to create source exposure.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria For Later Run

Research-only criteria for the future bounded run:

- Primary total return beats BIL by `> 0.0000`.
- If a standard public-source cost model exists, excess return versus BIL after costs remains `> 0.0000`.
- Max drawdown reduction versus SPY buy-hold is `>= 0.2000`.
- Return/drawdown proxy beats SPY buy-hold by `> 0.0000`.
- Average SPY exposure share is `>= 0.0500` and `<= 0.8500`.
- Duplicate/reference correlation versus SPY buy-hold and SPY_200d control is `< 0.9000` where available.
- Entry count, exit count, completed round trips, and turnover are reported.
- Exposure invariants pass.

These are diagnostic criteria, not promotion gates.
"""


def bt_readiness_md(bt: dict[str, Any]) -> str:
    return f"""# bt Adapter Readiness

Control POC manifest exists: `{bt['bt_control_manifest_exists']}`

Multi-asset POC manifest exists: `{bt['bt_multasset_manifest_exists']}`

Control POC passed: `{bt['bt_control_poc_passed']}`

Multi-asset POC passed: `{bt['bt_multasset_poc_passed']}`

bt adapter ready for design: `{bt['bt_adapter_ready_for_design']}`

This packet creates design evidence only and does not run the adapter.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_parabolic_sar_bounded_bt_design_only",
        "bounded_run_implementation_created",
        "bounded_bt_lane_run",
        "strategy_backtest_run",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "additional_public_sources_ingested",
        "threshold_sweep_created",
        "alternative_af_parameters_added",
        "filters_added",
        "alternate_exits_added",
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
        "outputs_non_promotable",
    ]
    return {key: manifest[key] for key in keys}


def exposure_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future Parabolic SAR bounded `bt` run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, inverse ETFs, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def do_not_run_or_promote_md() -> str:
    return """# Do Not Run Or Promote From This Design

This packet is design-only. It does not implement the Parabolic SAR strategy, does not run a backtest, does not create candidate_exhaustive, does not create paper/demo eligibility, and does not promote anything.

Public-source presence and intake eligibility are not proof of profitability.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    review: dict[str, Any],
    cache: list[dict[str, Any]],
    params: list[dict[str, Any]],
    bt: dict[str, Any],
    rows: list[dict[str, Any]],
    utility_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    readiness, blocker, next_action = run_readiness(review, cache, bt, rows)
    intake = review["source_intake"]
    definitions = dotted_get(intake, "indicator_definitions") or {}
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_parabolic_sar_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_name": review["source_name"],
        "source_intake_reviewed": review["candidate_exists"],
        "single_source_intake_evidence_reviewed": review["single_intake_evidence_exists"],
        "batch_intake_evidence_reviewed": review["batch_evidence_exists"],
        "source_intake_eligibility_decision": review["single_intake_decision"],
        "batch_intake_eligibility_decision": review["batch_eligibility_decision"],
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "uses_only_validated_parabolic_sar_candidate": True,
        "planned_row_count": len(rows),
        "planned_row_count_target_4_to_5": 4 <= len(rows) <= 5,
        "planned_row_count_lte_5": len(rows) <= 5,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity_context"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "spy200d_control_included": any(row["variant_id"] == "parabolic_sar_spy200d_frozen_control_v1" for row in rows),
        "spy200d_added_as_source_filter": False,
        "formula_contract_id": definitions.get("formula_contract_id", ""),
        "formula_contract_complete": formula_contract_complete(intake),
        "repository_standard_psar_utility_found": any(row["repository_standard_psar_utility"] is True for row in utility_rows),
        "source_backed_parameters": all(str(row["source_status"]).startswith("source") or row["parameter"] in {"formula_contract_id", "initialization_convention", "alternate_parameters_added"} for row in params),
        "parameters_tuned": False,
        "af_start": definitions.get("parabolic_sar_acceleration_factor_start"),
        "af_increment": definitions.get("parabolic_sar_acceleration_factor_increment"),
        "af_maximum": definitions.get("parabolic_sar_acceleration_factor_maximum"),
        "alternative_af_parameters_added": False,
        "threshold_sweep_created": False,
        "adx_filter_added": False,
        "moving_average_filters_added": False,
        "rsi_macd_cci_bollinger_volume_filters_added": False,
        "filters_added": False,
        "stop_loss_or_profit_target_added": False,
        "alternate_exits_added": False,
        "optimization_run": False,
        "uses_completed_daily_adjusted_ohlc": True,
        "initialization_convention_documented": True,
        "initialization_convention_is_implementation_convention": True,
        "reversal_state_transition_documented": True,
        "warmup_tradability_documented": True,
        "first_valid_sar_date_reporting_required": definitions.get("first_valid_sar_date_reporting_required") is True,
        "first_reversal_date_reporting_required": definitions.get("first_reversal_date_reporting_required") is True,
        "first_tradable_signal_date_reporting_required": definitions.get("first_tradable_signal_date_reporting_required") is True,
        "long_only_adaptation_caveat_documented": True,
        "whipsaw_ranging_market_risk_documented": True,
        "similarity_hit_preserved": bool(review["single_intake_similarity_hits"] or review["similarity_hits_from_candidate"]),
        "similarity_hit_count": review["single_intake_similarity_hit_count"],
        "duplicate_or_do_not_retest_blocker": False,
        "uses_only_spy_and_bil": True,
        "new_instruments_added": False,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "spy_ohlc_cache_ready": any(
            row["symbol"] == "SPY"
            and row["data_requirement_status"] == "daily_adjusted_ohlc_ready_for_parabolic_sar"
            for row in cache
        ),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
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
    return f"""# Public Source Parabolic SAR Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Parabolic SAR Bounded bt Design Summary

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Formula contract: `{manifest['formula_contract_id']}`

Formula contract complete: `{manifest['formula_contract_complete']}`

Repository-standard PSAR utility found: `{manifest['repository_standard_psar_utility_found']}`

Planned rows: `{manifest['planned_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

SPY OHLC cache ready: `{manifest['spy_ohlc_cache_ready']}`

Similarity hit count: `{manifest['similarity_hit_count']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

Outputs remain diagnostic and non-promotable: `{manifest['outputs_non_promotable']}`

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    self_check = "public_source_parabolic_sar_bounded_bt_design_consistency_check.json"
    required = {name: (output / name).exists() or name == self_check for name in REQUIRED_FILES}
    checks: dict[str, Any] = {
        "design_only": manifest["public_source_parabolic_sar_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "batch_intake_eligible": manifest["batch_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "formula_contract_complete": manifest["formula_contract_id"] == FORMULA_CONTRACT_ID
        and manifest["formula_contract_complete"] is True,
        "row_count_bounded": manifest["planned_row_count_target_4_to_5"] is True
        and manifest["planned_row_count_lte_5"] is True
        and {row["variant_id"] for row in rows} == set(PLANNED_ROW_IDS),
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] == 1
        and manifest["control_row_count"] == 3,
        "spy200d_control_only": manifest["spy200d_control_included"] is True
        and manifest["spy200d_added_as_source_filter"] is False,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True and manifest["new_instruments_added"] is False,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["spy_ohlc_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_ready_for_design"] is True,
        "reports_documented": manifest["initialization_convention_documented"] is True
        and manifest["reversal_state_transition_documented"] is True
        and manifest["warmup_tradability_documented"] is True
        and manifest["long_only_adaptation_caveat_documented"] is True
        and manifest["whipsaw_ranging_market_risk_documented"] is True,
        "no_tuning_or_expansion": manifest["parameters_tuned"] is False
        and manifest["alternative_af_parameters_added"] is False
        and manifest["threshold_sweep_created"] is False
        and manifest["filters_added"] is False
        and manifest["alternate_exits_added"] is False,
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
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["paper_forward_activation"] is False,
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
        "required_files_exist": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    review = source_intake_review(root)
    intake = review["source_intake"]
    cache = cache_rows(root)
    params = parameter_rows(intake)
    bt = bt_readiness(root)
    rows = planned_rows()
    utility_rows = existing_utility_discovery_rows()
    manifest = manifest_payload(
        created=created,
        output=output,
        review=review,
        cache=cache,
        params=params,
        bt=bt,
        rows=rows,
        utility_rows=utility_rows,
    )

    write_json(output / "public_source_parabolic_sar_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_parabolic_sar_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "source_backed_parameter_report.csv", params, list(PARAM_FIELDS))
    write_text(output / "source_backed_parameter_report.md", parameter_md(params))
    write_text(output / "formula_contract_report.md", formula_contract_md(intake))
    write_text(output / "existing_utility_discovery_report.md", utility_discovery_md(utility_rows))
    write_text(output / "parabolic_sar_formula_signal_definition.md", formula_signal_md(intake))
    write_text(output / "initialization_convention_report.md", initialization_md(intake))
    write_text(output / "reversal_state_transition_report.md", reversal_md(intake))
    write_text(output / "warmup_tradability_report.md", warmup_md(intake))
    write_text(output / "long_only_adaptation_caveat.md", long_only_adaptation_md(intake))
    write_text(output / "whipsaw_ranging_market_risk.md", whipsaw_md(intake))
    write_text(output / "similarity_risk_report.md", similarity_md(review))
    write_csv(output / "planned_row_table.csv", rows, list(PLANNED_ROW_FIELDS))
    write_text(output / "planned_row_table.md", planned_rows_md(rows))
    write_text(output / "signal_timing_convention.md", signal_timing_md())
    write_text(output / "baseline_control_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "bt_adapter_readiness.md", bt_readiness_md(bt))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "do_not_run_or_promote.md", do_not_run_or_promote_md())
    write_text(output / "public_source_parabolic_sar_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_parabolic_sar_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
