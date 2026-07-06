from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv
from strategy_lab.research_os.research.public_source_preregistration_bridge import (
    CONSTRAINT_FILTER_PATH,
    DECISION_CONSTRAINT_BLOCKED,
    DECISION_DUPLICATE,
    DECISION_ELIGIBLE,
    DECISION_INCOMPLETE,
    DECISION_REVIEW,
    FAMILY_MAP_PATH,
    INTAKE_TEMPLATE_PATH,
    SOURCE_DIR,
    VALID_ELIGIBILITY_DECISIONS,
    as_list,
    dotted_get,
    evaluate_intake,
    is_missing,
    read_yaml,
)


OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_intake_validation" / "latest"
CANDIDATE_DIR = SOURCE_DIR / "intake_candidates"

NEXT_ACTION_MANUAL_SOURCE_REQUIRED = "manual_public_source_intake_required"
NEXT_ACTION_BLOCKED_BY_CONSTRAINTS = "source_intake_blocked_by_project_constraints"
NEXT_ACTION_DUPLICATE_NO_DESIGN = "public_source_duplicate_or_do_not_retest_no_design"
NEXT_ACTION_REVIEW_REQUIRED = "direction_owner_review_required_for_public_source_intake"

VALID_NEXT_ACTIONS = {
    NEXT_ACTION_MANUAL_SOURCE_REQUIRED,
    NEXT_ACTION_BLOCKED_BY_CONSTRAINTS,
    NEXT_ACTION_DUPLICATE_NO_DESIGN,
    NEXT_ACTION_REVIEW_REQUIRED,
}

REQUIRED_FILES = (
    "public_source_intake_validation_manifest.json",
    "candidate_file_inventory.csv",
    "source_summary.md",
    "required_field_validation_report.md",
    "constraint_filter_report.md",
    "family_similarity_do_not_retest_report.md",
    "local_cache_availability_report.csv",
    "local_cache_availability_report.md",
    "eligibility_decision.md",
    "guardrail_checklist.json",
    "public_source_intake_validation_next_action.md",
    "public_source_intake_validation_consistency_check.json",
)

INVENTORY_FIELDS = ("path", "filename", "status")
CACHE_AVAILABILITY_FIELDS = ("symbol", "cache_status", "cache_path", "first_date", "last_date", "notes")

CLEAR_RULE_VALUES = {"clear", "clear_and_testable", "fully_clear", "clear_enough_to_freeze", "explicit", "yes"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_files(root: Path) -> list[Path]:
    candidate_dir = root / CANDIDATE_DIR
    if not candidate_dir.exists():
        return []
    return sorted([*candidate_dir.glob("*.yaml"), *candidate_dir.glob("*.yml")])


def selected_candidate_files(files: list[Path]) -> list[Path]:
    selected: list[tuple[int, str, Path]] = []
    for path in files:
        intake, parse_error = safe_load_candidate(path)
        if parse_error:
            continue
        if dotted_get(intake, "project_screening.single_source_validation_selected") is True:
            try:
                priority = int(dotted_get(intake, "project_screening.single_source_validation_priority") or 0)
            except (TypeError, ValueError):
                priority = 0
            selected.append((priority, source_id_for(path, intake), path))
    if selected:
        return [max(selected, key=lambda item: (item[0], item[1]))[2]]
    return files


def sanitize_source_id(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "manual_public_source"


def safe_load_candidate(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact parser errors are library-specific
        return {}, f"yaml_parse_error:{exc}"
    if not isinstance(data, dict):
        return {}, "candidate_yaml_root_not_mapping"
    return data, None


def source_id_for(candidate_path: Path | None, intake: dict[str, Any]) -> str:
    explicit = dotted_get(intake, "source.source_id")
    name = dotted_get(intake, "source.source_name")
    raw = str(explicit or name or (candidate_path.stem if candidate_path else "not_supplied"))
    return sanitize_source_id(raw)


def next_action_for(decision: str, source_id: str) -> str:
    if decision == DECISION_ELIGIBLE:
        return f"design_public_source_{source_id}_bounded_bt_lane"
    if decision == DECISION_CONSTRAINT_BLOCKED:
        return NEXT_ACTION_BLOCKED_BY_CONSTRAINTS
    if decision == DECISION_DUPLICATE:
        return NEXT_ACTION_DUPLICATE_NO_DESIGN
    if decision == DECISION_REVIEW:
        return NEXT_ACTION_REVIEW_REQUIRED
    return NEXT_ACTION_MANUAL_SOURCE_REQUIRED


def candidate_inventory_rows(files: list[Path], root: Path) -> list[dict[str, str]]:
    if not files:
        return [
            {
                "path": str((root / CANDIDATE_DIR).resolve()),
                "filename": "not_supplied",
                "status": "no_candidate_intake_file_found",
            }
        ]
    return [
        {
            "path": str(path.resolve()),
            "filename": path.name,
            "status": "candidate_intake_file_found",
        }
        for path in files
    ]


def cache_lookup(root: Path) -> dict[str, dict[str, Any]]:
    return {str(row["symbol"]).upper(): row for row in cache_inventory(root)}


def local_cache_rows(root: Path, intake: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    symbols = [
        str(symbol).upper()
        for symbol in (dotted_get(intake, "strategy_description.instruments") or [])
        if not is_missing(symbol)
    ]
    if not symbols:
        return [], False
    available = cache_lookup(root)
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        row = available.get(symbol)
        if row and row.get("status") == "cache_ready":
            rows.append(
                {
                    "symbol": symbol,
                    "cache_status": "cache_ready",
                    "cache_path": row.get("path", ""),
                    "first_date": row.get("first_date", ""),
                    "last_date": row.get("last_date", ""),
                    "notes": "local_cache_price_history_available",
                }
            )
        else:
            rows.append(
                {
                    "symbol": symbol,
                    "cache_status": "missing",
                    "cache_path": "",
                    "first_date": "",
                    "last_date": "",
                    "notes": "required_symbol_not_found_in_current_local_cache",
                }
            )
    return rows, True


def rule_clarity_value(intake: dict[str, Any]) -> str:
    return str(dotted_get(intake, "strategy_description.rule_clarity") or "").strip().lower()


def governance_blocks(intake: dict[str, Any]) -> list[str]:
    blocks: list[str] = []
    if dotted_get(intake, "governance.source_scraped_by_codex") is True:
        blocks.append("source_scraped_by_codex_not_allowed")
    if dotted_get(intake, "governance.strategy_implemented") is True:
        blocks.append("strategy_implemented_during_intake_not_allowed")
    if dotted_get(intake, "governance.backtest_run") is True:
        blocks.append("backtest_run_during_intake_not_allowed")
    if dotted_get(intake, "governance.promotion_or_paper_forward_allowed") is True:
        blocks.append("promotion_or_paper_forward_allowed_not_permitted")
    return blocks


def evaluate_candidate(
    root: Path,
    candidate_path: Path | None,
    candidate_count: int,
    intake: dict[str, Any],
    parse_error: str | None,
    constraint_filter: dict[str, Any],
    family_map: dict[str, Any],
) -> dict[str, Any]:
    if candidate_count == 0:
        required = constraint_filter.get("required_complete_intake_fields", [])
        return {
            "eligibility_decision": DECISION_INCOMPLETE,
            "source_id": "not_supplied",
            "intake_candidate_path": "not_supplied",
            "manual_source_supplied": False,
            "candidate_file_count": 0,
            "exact_missing_fields": ["intake_candidate_file", *required],
            "constraint_blocks": [],
            "family_similarity_hits": [],
            "family_similarity_hit_count": 0,
            "rule_clarity_status": "not_supplied",
            "parse_error": None,
            "reason": "No manually supplied public-source intake file exists.",
        }
    if candidate_count > 1:
        return {
            "eligibility_decision": DECISION_REVIEW,
            "source_id": "ambiguous_multiple_sources",
            "intake_candidate_path": "multiple",
            "manual_source_supplied": True,
            "candidate_file_count": candidate_count,
            "exact_missing_fields": ["exactly_one_candidate_intake_file"],
            "constraint_blocks": [],
            "family_similarity_hits": [],
            "family_similarity_hit_count": 0,
            "rule_clarity_status": "not_evaluated_multiple_candidates",
            "parse_error": None,
            "reason": "More than one candidate intake file was found; this task may validate exactly one.",
        }
    if parse_error:
        return {
            "eligibility_decision": DECISION_INCOMPLETE,
            "source_id": source_id_for(candidate_path, intake),
            "intake_candidate_path": str(candidate_path.resolve()) if candidate_path else "not_supplied",
            "manual_source_supplied": True,
            "candidate_file_count": 1,
            "exact_missing_fields": ["valid_yaml_candidate_intake"],
            "constraint_blocks": [],
            "family_similarity_hits": [],
            "family_similarity_hit_count": 0,
            "rule_clarity_status": "not_evaluated_parse_error",
            "parse_error": parse_error,
            "reason": "The candidate intake file could not be parsed as a YAML mapping.",
        }

    evaluation = evaluate_intake(intake, constraint_filter, family_map, root)
    governance = governance_blocks(intake)
    decision = evaluation["eligibility_decision"]
    rule_status = "clear" if rule_clarity_value(intake) in CLEAR_RULE_VALUES else "unclear_or_not_freezable"
    manual_similarity_hits = [
        str(item)
        for item in as_list(dotted_get(intake, "project_screening.similar_already_tested_project_families"))
        if not is_missing(item)
    ]
    do_not_retest_match = dotted_get(intake, "project_screening.do_not_retest_match")
    if not is_missing(do_not_retest_match):
        manual_similarity_hits.append(str(do_not_retest_match))
    combined_similarity_hits = list(
        dict.fromkeys([*evaluation.get("family_similarity_hits", []), *manual_similarity_hits])
    )
    if governance and decision == DECISION_ELIGIBLE:
        decision = DECISION_CONSTRAINT_BLOCKED
    if decision == DECISION_ELIGIBLE and rule_status != "clear":
        decision = DECISION_REVIEW
    if (
        decision == DECISION_REVIEW
        and dotted_get(intake, "project_screening.direction_owner_similarity_review_completed") is True
        and rule_status == "clear"
        and not evaluation.get("blank_required_fields", [])
        and not evaluation.get("constraint_blocks", [])
        and not governance
        and is_missing(dotted_get(intake, "project_screening.do_not_retest_match"))
    ):
        decision = DECISION_ELIGIBLE

    return {
        **evaluation,
        "eligibility_decision": decision,
        "source_id": source_id_for(candidate_path, intake),
        "intake_candidate_path": str(candidate_path.resolve()) if candidate_path else "not_supplied",
        "manual_source_supplied": True,
        "candidate_file_count": 1,
        "exact_missing_fields": evaluation.get("blank_required_fields", []),
        "constraint_blocks": [*evaluation.get("constraint_blocks", []), *governance],
        "family_similarity_hits": combined_similarity_hits,
        "family_similarity_hit_count": len(combined_similarity_hits),
        "rule_clarity_status": rule_status,
        "parse_error": None,
        "reason": "Exactly one manually supplied intake file was evaluated.",
    }


def source_summary_md(result: dict[str, Any], intake: dict[str, Any]) -> str:
    if result["manual_source_supplied"] is not True:
        return """# Source Summary

Manual source supplied: `false`

No public strategy source, citation, or filled intake file was provided in this task.

Codex did not choose, browse, scrape, or infer a public strategy.
"""
    return f"""# Source Summary

Manual source supplied: `true`

Candidate path: `{result['intake_candidate_path']}`

Source ID: `{result['source_id']}`

Source name: `{dotted_get(intake, 'source.source_name') or 'unknown'}`

Source URL/citation: `{dotted_get(intake, 'source.source_url_or_citation') or 'unknown'}`

Source type: `{dotted_get(intake, 'source.source_type') or 'unknown'}`

Strategy family: `{dotted_get(intake, 'strategy_description.strategy_family') or 'unknown'}`

Hypothesis: `{dotted_get(intake, 'strategy_description.claimed_hypothesis') or 'unknown'}`

Rule clarity status: `{result['rule_clarity_status']}`
"""


def required_field_md(result: dict[str, Any]) -> str:
    missing = result.get("exact_missing_fields", [])
    missing_lines = "\n".join(f"- `{field}`" for field in missing) or "- none"
    return f"""# Required Field Validation Report

Eligibility decision: `{result['eligibility_decision']}`

Candidate file count: `{result['candidate_file_count']}`

Candidate path: `{result['intake_candidate_path']}`

Exact missing fields:

{missing_lines}

Parse error: `{result.get('parse_error') or 'none'}`
"""


def constraint_filter_md(result: dict[str, Any]) -> str:
    blocks = result.get("constraint_blocks", [])
    block_lines = "\n".join(f"- `{block}`" for block in blocks) or "- none"
    return f"""# Constraint Filter Report

Constraint-filter decision component: `{DECISION_CONSTRAINT_BLOCKED if blocks else 'no_constraint_block_found'}`

Blocked features checked include intraday data, options, futures, leverage, shorting, margin, forex, crypto, unavailable local-cache symbols, provider downloads, broker/live execution, and real-money recommendations.

Constraint blockers:

{block_lines}
"""


def similarity_md(result: dict[str, Any]) -> str:
    hits = result.get("family_similarity_hits", [])
    hit_lines = "\n".join(f"- `{hit}`" for hit in hits) or "- none"
    return f"""# Family Similarity And Do-Not-Retest Report

Family similarity hit count: `{result.get('family_similarity_hit_count', 0)}`

Do-not-retest / similarity hits:

{hit_lines}

Duplicate/do-not-retest decision: `{result['eligibility_decision'] == DECISION_DUPLICATE}`
"""


def local_cache_md(rows: list[dict[str, Any]], checked: bool) -> str:
    if not checked:
        return """# Local Cache Availability Report

Local cache checked: `false`

No explicit instruments were supplied, so symbol-level local-cache validation could not be performed.
"""
    missing = [row["symbol"] for row in rows if row["cache_status"] != "cache_ready"]
    missing_lines = "\n".join(f"- `{symbol}`" for symbol in missing) or "- none"
    return f"""# Local Cache Availability Report

Local cache checked: `true`

Symbols reviewed: `{len(rows)}`

Missing symbols:

{missing_lines}
"""


def eligibility_md(result: dict[str, Any], next_action: str) -> str:
    return f"""# Eligibility Decision

Eligibility decision: `{result['eligibility_decision']}`

Reason: {result['reason']}

Allowed decisions:

{chr(10).join(f'- `{decision}`' for decision in sorted(VALID_ELIGIBILITY_DECISIONS))}

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Intake Validation Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_intake_validation_only",
        "public_strategy_selected_by_codex",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "public_strategy_implemented",
        "bounded_bt_design_created",
        "strategy_backtest_run",
        "strategy_discovery_run",
        "broad_research_batch_run",
        "new_packages_installed",
        "provider_download",
        "intraday_data_used",
        "leverage_short_options_futures_forex_margin_derivatives_crypto_used",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
        "current_backtester_replaced",
        "public_source_presence_is_profitability_proof",
    ]
    return {key: manifest[key] for key in keys}


def manifest_payload(
    *,
    created: str,
    output: Path,
    result: dict[str, Any],
    next_action: str,
    local_cache_checked: bool,
) -> dict[str, Any]:
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_intake_validation_only": True,
        "intake_template_path": str((ROOT / INTAKE_TEMPLATE_PATH).resolve()),
        "constraint_filter_path": str((ROOT / CONSTRAINT_FILTER_PATH).resolve()),
        "family_similarity_map_path": str((ROOT / FAMILY_MAP_PATH).resolve()),
        "intake_candidate_dir": str((ROOT / CANDIDATE_DIR).resolve()),
        "intake_candidate_path": result["intake_candidate_path"],
        "candidate_file_count": result["candidate_file_count"],
        "manual_source_supplied": result["manual_source_supplied"],
        "source_id": result["source_id"],
        "eligibility_decision": result["eligibility_decision"],
        "valid_eligibility_decisions": sorted(VALID_ELIGIBILITY_DECISIONS),
        "exact_missing_fields": result.get("exact_missing_fields", []),
        "constraint_blockers": result.get("constraint_blocks", []),
        "family_similarity_hits": result.get("family_similarity_hits", []),
        "family_similarity_hit_count": result.get("family_similarity_hit_count", 0),
        "rule_clarity_status": result.get("rule_clarity_status", "not_evaluated"),
        "local_cache_checked": local_cache_checked,
        "bounded_bt_design_created": False,
        "public_strategy_selected_by_codex": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "public_strategy_implemented": False,
        "strategy_backtest_run": False,
        "strategy_discovery_run": False,
        "new_strategy_discovery_run": False,
        "broad_research_batch_run": False,
        "new_research_batch_run": False,
        "new_packages_installed": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_short_options_futures_forex_margin_derivatives_crypto_used": False,
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
        "current_backtester_replaced": False,
        "public_source_presence_is_profitability_proof": False,
        "outputs_diagnostic_only": True,
        "next_action": next_action,
    }


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_intake_validation_consistency_check.json"] = True
    design_action_valid = (
        manifest["next_action"].startswith(f"design_public_source_{manifest['source_id']}_bounded_bt_lane")
        and manifest["eligibility_decision"] == DECISION_ELIGIBLE
    )
    checks = {
        "validation_only": manifest["public_source_intake_validation_only"] is True,
        "decision_valid": manifest["eligibility_decision"] in VALID_ELIGIBILITY_DECISIONS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS or design_action_valid,
        "incomplete_when_no_candidate": (
            manifest["candidate_file_count"] != 0 or manifest["eligibility_decision"] == DECISION_INCOMPLETE
        ),
        "manual_source_not_invented": (
            manifest["candidate_file_count"] != 0 or manifest["manual_source_supplied"] is False
        ),
        "no_public_source_scrape_or_selection": manifest["public_strategy_selected_by_codex"] is False
        and manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False,
        "no_strategy_design_run_or_discovery": manifest["public_strategy_implemented"] is False
        and manifest["bounded_bt_design_created"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_discovery_run"] is False
        and manifest["broad_research_batch_run"] is False,
        "no_provider_intraday_or_packages": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["new_packages_installed"] is False,
        "no_forbidden_instruments": manifest["leverage_short_options_futures_forex_margin_derivatives_crypto_used"] is False,
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
        "current_backtester_not_replaced": manifest["current_backtester_replaced"] is False,
        "public_source_not_profitability_proof": manifest["public_source_presence_is_profitability_proof"] is False,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    (root / CANDIDATE_DIR).mkdir(parents=True, exist_ok=True)

    constraint_filter = read_yaml(root / CONSTRAINT_FILTER_PATH)
    family_map = read_yaml(root / FAMILY_MAP_PATH)
    files = selected_candidate_files(candidate_files(root))
    candidate_path = files[0] if len(files) == 1 else None
    intake: dict[str, Any] = {}
    parse_error: str | None = None
    if candidate_path:
        intake, parse_error = safe_load_candidate(candidate_path)

    result = evaluate_candidate(
        root,
        candidate_path,
        len(files),
        intake,
        parse_error,
        constraint_filter,
        family_map,
    )
    next_action = next_action_for(result["eligibility_decision"], result["source_id"])
    cache_rows, local_cache_checked = local_cache_rows(root, intake)
    manifest = manifest_payload(
        created=created,
        output=output,
        result=result,
        next_action=next_action,
        local_cache_checked=local_cache_checked,
    )

    write_json(output / "public_source_intake_validation_manifest.json", manifest)
    write_csv(output / "candidate_file_inventory.csv", candidate_inventory_rows(files, root), list(INVENTORY_FIELDS))
    write_text(output / "source_summary.md", source_summary_md(result, intake))
    write_text(output / "required_field_validation_report.md", required_field_md(result))
    write_text(output / "constraint_filter_report.md", constraint_filter_md(result))
    write_text(output / "family_similarity_do_not_retest_report.md", similarity_md(result))
    write_csv(output / "local_cache_availability_report.csv", cache_rows, list(CACHE_AVAILABILITY_FIELDS))
    write_text(output / "local_cache_availability_report.md", local_cache_md(cache_rows, local_cache_checked))
    write_text(output / "eligibility_decision.md", eligibility_md(result, next_action))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "public_source_intake_validation_next_action.md", next_action_md(next_action))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_intake_validation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
