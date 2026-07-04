from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import read_json, read_yaml


SOURCE_ID = "turn_of_month_equity_indexes"
LANE_ID = "public_source_turn_of_month_bounded_bt_lane_v1"
FAMILY_ID = "calendar_effect_turn_of_month_equity_index"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_turn_of_month_bounded_bt_design" / "latest"
INTAKE_PATH = (
    Path("strategy_lab")
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / "turn_of_month_equity_indexes.yaml"
)
INTAKE_EVIDENCE_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
INTAKE_MANIFEST_PATH = INTAKE_EVIDENCE_DIR / "public_source_intake_validation_manifest.json"
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

RUN_READY = "public_source_turn_of_month_bounded_bt_design_run_ready"
RUN_BLOCKED = "public_source_turn_of_month_bounded_bt_design_blocked"
NEXT_ACTION_RUN = "run_public_source_turn_of_month_bounded_bt_lane"
NEXT_ACTION_BLOCKED = "repair_public_source_turn_of_month_bounded_bt_design_blocker"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

REQUIRED_SYMBOLS = ("SPY", "BIL")
PLANNED_ROW_MIN = 3
PLANNED_ROW_MAX = 5

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "source_id",
    "variant_id",
    "variant_role",
    "research_label",
    "concept",
    "symbols",
    "calendar_window",
    "entry_decision_date",
    "entry_execution_target",
    "exit_decision_date",
    "exit_execution_target",
    "weight_shift_convention",
    "bt_adapter_contract",
    "baseline_or_control_role",
    "comparator_references",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)
CACHE_FIELDS = ("symbol", "required", "cache_status", "cache_path", "first_date", "last_date", "rows", "notes")

REQUIRED_FILES = (
    "public_source_turn_of_month_bounded_bt_design_manifest.json",
    "public_source_turn_of_month_bounded_bt_design_summary.md",
    "source_intake_review.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "planned_row_table.csv",
    "planned_row_table.md",
    "calendar_timing_convention.md",
    "baseline_control_policy.md",
    "numeric_success_failure_criteria.md",
    "bt_adapter_readiness.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "run_readiness_decision.md",
    "public_source_turn_of_month_bounded_bt_design_next_action.md",
    "public_source_turn_of_month_bounded_bt_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def cache_rows(root: Path) -> list[dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        info = inventory.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_status": info.get("status", "missing"),
                "cache_path": info.get("path", ""),
                "first_date": info.get("first_date", ""),
                "last_date": info.get("last_date", ""),
                "rows": info.get("rows", 0),
                "notes": "local_cache_price_history_available"
                if info.get("status") == "cache_ready"
                else "required_symbol_missing_from_current_local_cache",
            }
        )
    return rows


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


def planned_rows() -> list[dict[str, Any]]:
    comparator_refs = "SPY_buy_hold_control|BIL_cash_control|SPY_200d_frozen_control|same_window_cost_diagnostic"
    return [
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "totm_spy_bil_primary_close_m1_to_plus3_v1",
            "variant_role": "source_primary",
            "research_label": "public_source_calendar_totm_primary",
            "concept": "turn_of_month_spy_bil_calendar_window",
            "symbols": "SPY|BIL",
            "calendar_window": "SPY from close one trading day before month-end through close of third trading day of the next month; BIL otherwise",
            "entry_decision_date": "one trading day before the last available SPY/BIL trading day of each calendar month",
            "entry_execution_target": "set SPY weight to 1.0 at the entry decision close; with shifted close-to-close returns this applies from the next close",
            "exit_decision_date": "third available SPY/BIL trading day of the following calendar month",
            "exit_execution_target": "set BIL weight to 1.0 at the exit decision close; with shifted close-to-close returns this applies after the third trading-day close",
            "weight_shift_convention": "project/bt target weights are decision-close targets and are shifted one bar for close-to-close return application",
            "bt_adapter_contract": "daily target weight frame with SPY and BIL columns; no bt run in design step",
            "baseline_or_control_role": "primary_source_interpretation",
            "comparator_references": comparator_refs,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "totm_spy_bil_timing_sanity_one_bar_delayed_v1",
            "variant_role": "timing_sanity",
            "research_label": "public_source_calendar_totm_timing_sanity",
            "concept": "one_bar_delayed_turn_of_month_spy_bil_calendar_window",
            "symbols": "SPY|BIL",
            "calendar_window": "same source calendar idea with entry and exit targets delayed by one trading day; timing-sanity only, not a tuned variant",
            "entry_decision_date": "last available SPY/BIL trading day of each calendar month",
            "entry_execution_target": "set SPY weight to 1.0 at month-end close, one trading day later than primary",
            "exit_decision_date": "fourth available SPY/BIL trading day of the following calendar month",
            "exit_execution_target": "set BIL weight to 1.0 at fourth trading-day close, one trading day later than primary",
            "weight_shift_convention": "project/bt target weights are decision-close targets and are shifted one bar for close-to-close return application",
            "bt_adapter_contract": "daily target weight frame with SPY and BIL columns; no bt run in design step",
            "baseline_or_control_role": "timing_sanity_not_parameter_sweep",
            "comparator_references": comparator_refs,
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "totm_spy_buy_hold_control_v1",
            "variant_role": "control",
            "research_label": "public_source_calendar_control_only",
            "concept": "spy_buy_hold_control",
            "symbols": "SPY",
            "calendar_window": "SPY 100% same-window buy-and-hold control",
            "entry_decision_date": "not_applicable_control",
            "entry_execution_target": "SPY weight 1.0 for full same-window period",
            "exit_decision_date": "not_applicable_control",
            "exit_execution_target": "not_applicable_control",
            "weight_shift_convention": "control-only benchmark convention documented by future run",
            "bt_adapter_contract": "control-only target weight frame; no bt run in design step",
            "baseline_or_control_role": "buy_hold_control_only",
            "comparator_references": "primary_source_row|timing_sanity_row|BIL_cash_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "totm_bil_cash_control_v1",
            "variant_role": "control",
            "research_label": "public_source_calendar_control_only",
            "concept": "bil_cash_control",
            "symbols": "BIL",
            "calendar_window": "BIL 100% same-window cash control",
            "entry_decision_date": "not_applicable_control",
            "entry_execution_target": "BIL weight 1.0 for full same-window period",
            "exit_decision_date": "not_applicable_control",
            "exit_execution_target": "not_applicable_control",
            "weight_shift_convention": "control-only benchmark convention documented by future run",
            "bt_adapter_contract": "control-only target weight frame; no bt run in design step",
            "baseline_or_control_role": "cash_control_only",
            "comparator_references": "primary_source_row|timing_sanity_row|SPY_buy_hold_control|SPY_200d_frozen_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
        {
            "lane_id": LANE_ID,
            "family_id": FAMILY_ID,
            "source_id": SOURCE_ID,
            "variant_id": "totm_spy200d_frozen_control_v1",
            "variant_role": "control",
            "research_label": "public_source_calendar_control_only",
            "concept": "spy200d_frozen_control",
            "symbols": "SPY|BIL",
            "calendar_window": "existing project SPY 200d frozen control where supported; benchmark/control only",
            "entry_decision_date": "existing project SPY_200d control convention",
            "entry_execution_target": "SPY if existing prior-close 200d rule is risk-on, otherwise BIL",
            "exit_decision_date": "existing project SPY_200d control convention",
            "exit_execution_target": "SPY/BIL per existing frozen control",
            "weight_shift_convention": "use already validated bt adapter SPY_200d control convention",
            "bt_adapter_contract": "control-only target weight frame; no bt run in design step",
            "baseline_or_control_role": "spy200d_control_only",
            "comparator_references": "primary_source_row|timing_sanity_row|SPY_buy_hold_control|BIL_cash_control",
            "promotion_eligibility": False,
            "paper_forward_eligibility": False,
            "candidate_exhaustive_eligibility": False,
        },
    ]


def source_intake_review(root: Path) -> dict[str, Any]:
    intake = read_yaml(root / INTAKE_PATH)
    manifest = read_json(root / INTAKE_MANIFEST_PATH)
    return {
        "candidate_exists": (root / INTAKE_PATH).exists(),
        "source_id": intake.get("source", {}).get("source_id", ""),
        "source_name": intake.get("source", {}).get("source_name", ""),
        "strategy_family": intake.get("strategy_description", {}).get("strategy_family", ""),
        "intake_eligibility_decision": manifest.get("eligibility_decision", ""),
        "intake_constraint_blockers": manifest.get("constraint_blockers", []),
        "intake_similarity_hits": manifest.get("family_similarity_hits", []),
        "intake_missing_fields": manifest.get("exact_missing_fields", []),
        "intake_local_cache_checked": manifest.get("local_cache_checked") is True,
        "bounded_bt_design_already_created_by_intake": manifest.get("bounded_bt_design_created") is True,
    }


def run_readiness(review: dict[str, Any], cache: list[dict[str, Any]], bt: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    blockers: list[str] = []
    if review["source_id"] != SOURCE_ID or review["intake_eligibility_decision"] != "eligible_for_bounded_bt_design":
        blockers.append("public_source_intake_not_eligible")
    if review["intake_constraint_blockers"]:
        blockers.append("public_source_intake_has_constraint_blockers")
    if review["intake_similarity_hits"]:
        blockers.append("public_source_intake_has_similarity_or_do_not_retest_hits")
    if any(row["cache_status"] != "cache_ready" for row in cache):
        blockers.append("missing_required_spy_bil_local_cache")
    if not bt["bt_adapter_ready_for_design"]:
        blockers.append("bt_adapter_prerequisites_not_ready")
    if not PLANNED_ROW_MIN <= len(rows) <= PLANNED_ROW_MAX:
        blockers.append("planned_row_count_outside_bounds")
    if blockers:
        return RUN_BLOCKED, "|".join(blockers), NEXT_ACTION_BLOCKED
    return RUN_READY, "none", NEXT_ACTION_RUN


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
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_turn_of_month_bounded_bt_design_only": True,
        "source_id": SOURCE_ID,
        "source_intake_reviewed": review["candidate_exists"],
        "source_intake_eligibility_decision": review["intake_eligibility_decision"],
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "planned_row_count": len(rows),
        "planned_row_count_between_3_and_5": PLANNED_ROW_MIN <= len(rows) <= PLANNED_ROW_MAX,
        "planned_row_count_lte_6": len(rows) <= 6,
        "primary_source_row_count": sum(1 for row in rows if row["variant_role"] == "source_primary"),
        "timing_sanity_row_count": sum(1 for row in rows if row["variant_role"] == "timing_sanity"),
        "control_row_count": sum(1 for row in rows if row["variant_role"] == "control"),
        "uses_only_spy_and_bil": True,
        "spy_cache_ready": any(row["symbol"] == "SPY" and row["cache_status"] == "cache_ready" for row in cache),
        "bil_cache_ready": any(row["symbol"] == "BIL" and row["cache_status"] == "cache_ready" for row in cache),
        "local_cache_complete": all(row["cache_status"] == "cache_ready" for row in cache),
        "bt_adapter_control_poc_passed": bt["bt_control_poc_passed"],
        "bt_adapter_multasset_poc_passed": bt["bt_multasset_poc_passed"],
        "bt_adapter_ready_for_design": bt["bt_adapter_ready_for_design"],
        "calendar_timing_convention_frozen": True,
        "no_lookahead_timing_documented": True,
        "one_timing_sanity_row_only": True,
        "calendar_parameter_sweep_created": False,
        "optimization_run": False,
        "bounded_bt_design_created": True,
        "bounded_bt_lane_run": False,
        "strategy_backtest_run": False,
        "strategy_implemented": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "faber_taa_designed_or_retested": False,
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


def source_intake_review_md(review: dict[str, Any]) -> str:
    return f"""# Source Intake Review

Source ID: `{review['source_id']}`

Source name: `{review['source_name']}`

Strategy family: `{review['strategy_family']}`

Intake eligibility decision: `{review['intake_eligibility_decision']}`

Constraint blockers: `{review['intake_constraint_blockers']}`

Similarity/do-not-retest hits: `{review['intake_similarity_hits']}`

Missing fields: `{review['intake_missing_fields']}`

Local cache checked by intake: `{review['intake_local_cache_checked']}`

The source is manually supplied context only and is not proof of profitability.
"""


def local_cache_md(cache: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    for row in cache:
        lines.append(
            f"- `{row['symbol']}`: `{row['cache_status']}`, `{row['first_date']}` to `{row['last_date']}`, rows `{row['rows']}`"
        )
    lines.append("")
    lines.append("No provider download was run or authorized.")
    return "\n".join(lines) + "\n"


def planned_rows_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Row Table", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: role `{row['variant_role']}`, label `{row['research_label']}`, symbols `{row['symbols']}`"
        )
    lines.append("")
    lines.append("All rows are diagnostic and non-promotable. Control rows are controls only.")
    return "\n".join(lines) + "\n"


def timing_md() -> str:
    return """# Calendar Timing Convention

This design freezes timing before any run:

- Trading days are the common local-cache dates where `SPY` and `BIL` both have adjusted-close data.
- Month-end is the last available common trading day of each calendar month.
- Primary entry decision date is one common trading day before month-end.
- Primary entry target is set at that entry decision close: `SPY=1.0`, `BIL=0.0`.
- Project/bt convention applies target weights to close-to-close returns with a one-bar shift, so the entry target captures returns beginning after the entry close.
- Primary exit decision date is the third available common trading day of the next calendar month.
- Primary exit target is set at that exit decision close: `SPY=0.0`, `BIL=1.0`.
- This keeps SPY exposure through the third trading day close and BIL exposure after exit.
- Timing-sanity row delays both entry and exit targets by one common trading day. It is a no-lookahead sensitivity check, not parameter tuning.
- No intraday data, same-day future close, calendar-day filling, or non-local provider data may be used.
"""


def baseline_policy_md() -> str:
    return """# Baseline / Control Policy

Diagnostic controls:

- `totm_spy_buy_hold_control_v1`: same-window SPY buy-and-hold control.
- `totm_bil_cash_control_v1`: same-window BIL cash control.
- `totm_spy200d_frozen_control_v1`: existing project SPY 200d frozen control where supported.

Controls are benchmark/control rows only. They cannot become promotion candidates, candidate_exhaustive rows, paper-forward candidates, broker/live rows, or real-money recommendations.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run criteria are research-only and not promotion gates.

Primary row is interesting only if all are true:

- Same-window total return beats BIL by `> 0.0000`.
- Same-window excess return versus BIL remains `> 0.0000` after any standard project cost assumption used for bounded public-source runs.
- Max drawdown reduction versus SPY buy-and-hold is `>= 0.2500` relative improvement.
- Return/drawdown proxy is better than SPY buy-and-hold by `> 0.0000`.
- Average SPY exposure share is between `0.1200` and `0.3000`.
- Duplicate/reference correlation versus SPY buy-and-hold and SPY_200d control is `< 0.8500` where available.
- Exposure invariants pass.

Timing-sanity row is supportive only if:

- It is not a higher-scoring tuned variant.
- It preserves the sign of excess return versus BIL.
- It does not violate exposure invariants.

Control rows are always `public_source_calendar_control_only`.

Allowed labels:

- `public_source_calendar_totm_primary`
- `public_source_calendar_totm_timing_sanity`
- `public_source_calendar_control_only`
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
        "public_source_turn_of_month_bounded_bt_design_only",
        "bounded_bt_lane_run",
        "strategy_backtest_run",
        "strategy_implemented",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "faber_taa_designed_or_retested",
        "calendar_parameter_sweep_created",
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

Hard invariants for any future Turn-of-the-Month bounded bt run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- SPY plus BIL must not accumulate above total weight `1.0`.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.
- No leverage, shorting, margin, options, direct futures, forex, broker/live, or intraday logic.
"""


def run_readiness_md(manifest: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Turn-of-the-Month Bounded bt Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Turn-of-the-Month Bounded bt Design

Source ID: `{manifest['source_id']}`

Lane ID: `{manifest['lane_id']}`

Family ID: `{manifest['family_id']}`

Source intake reviewed: `{manifest['source_intake_reviewed']}`

Source intake decision: `{manifest['source_intake_eligibility_decision']}`

Planned rows: `{manifest['planned_row_count']}`

Primary rows: `{manifest['primary_source_row_count']}`

Timing-sanity rows: `{manifest['timing_sanity_row_count']}`

Control rows: `{manifest['control_row_count']}`

Local cache complete: `{manifest['local_cache_complete']}`

bt adapter ready for design: `{manifest['bt_adapter_ready_for_design']}`

Calendar timing convention frozen: `{manifest['calendar_timing_convention_frozen']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No Turn-of-the-Month backtest, bounded run implementation, source scraping, strategy discovery, candidate_exhaustive, promotion, paper-forward activation, broker/live path, provider download, intraday data, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_turn_of_month_bounded_bt_design_consistency_check.json"] = True
    checks = {
        "design_only": manifest["public_source_turn_of_month_bounded_bt_design_only"] is True,
        "correct_source": manifest["source_id"] == SOURCE_ID,
        "correct_lane": manifest["lane_id"] == LANE_ID,
        "source_intake_reviewed": manifest["source_intake_reviewed"] is True,
        "source_intake_eligible": manifest["source_intake_eligibility_decision"] == "eligible_for_bounded_bt_design",
        "row_count_bounded": manifest["planned_row_count_between_3_and_5"] is True
        and manifest["planned_row_count_lte_6"] is True,
        "row_roles_expected": manifest["primary_source_row_count"] == 1
        and manifest["timing_sanity_row_count"] == 1
        and manifest["control_row_count"] == 3,
        "uses_only_spy_bil": manifest["uses_only_spy_and_bil"] is True,
        "cache_ready": manifest["spy_cache_ready"] is True
        and manifest["bil_cache_ready"] is True
        and manifest["local_cache_complete"] is True,
        "bt_ready": manifest["bt_adapter_control_poc_passed"] is True
        and manifest["bt_adapter_multasset_poc_passed"] is True
        and manifest["bt_adapter_ready_for_design"] is True,
        "timing_frozen": manifest["calendar_timing_convention_frozen"] is True
        and manifest["no_lookahead_timing_documented"] is True,
        "one_timing_sanity_only": manifest["one_timing_sanity_row_only"] is True,
        "no_sweep_or_optimization": manifest["calendar_parameter_sweep_created"] is False
        and manifest["optimization_run"] is False,
        "no_run_or_backtest": manifest["bounded_bt_lane_run"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_implemented"] is False,
        "no_scrape_or_other_public_source": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["faber_taa_designed_or_retested"] is False,
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
        "row_labels_allowed": {row["research_label"] for row in rows}
        <= {
            "public_source_calendar_totm_primary",
            "public_source_calendar_totm_timing_sanity",
            "public_source_calendar_control_only",
        },
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
    bt = bt_readiness(root)
    rows = planned_rows()
    manifest = manifest_payload(created=created, output=output, review=review, cache=cache, bt=bt, rows=rows)

    write_json(output / "public_source_turn_of_month_bounded_bt_design_manifest.json", manifest)
    write_text(output / "public_source_turn_of_month_bounded_bt_design_summary.md", summary_md(manifest))
    write_text(output / "source_intake_review.md", source_intake_review_md(review))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", local_cache_md(cache))
    write_csv(output / "planned_row_table.csv", rows, list(DESIGN_FIELDS))
    write_text(output / "planned_row_table.md", planned_rows_md(rows))
    write_text(output / "calendar_timing_convention.md", timing_md())
    write_text(output / "baseline_control_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "bt_adapter_readiness.md", bt_readiness_md(bt))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "public_source_turn_of_month_bounded_bt_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "public_source_turn_of_month_bounded_bt_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
