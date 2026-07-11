from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.research.public_source_intake_validation import (
    CANDIDATE_DIR,
    CACHE_AVAILABILITY_FIELDS,
    DECISION_CONSTRAINT_BLOCKED,
    DECISION_DUPLICATE,
    DECISION_ELIGIBLE,
    DECISION_INCOMPLETE,
    DECISION_REVIEW,
    VALID_ELIGIBILITY_DECISIONS,
    candidate_files,
    local_cache_rows,
    next_action_for,
    read_yaml,
    safe_load_candidate,
    source_id_for,
    evaluate_candidate,
)
from strategy_lab.research_os.research.public_source_preregistration_bridge import (
    CONSTRAINT_FILTER_PATH,
    FAMILY_MAP_PATH,
    dotted_get,
)


OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
NEXT_ACTION = "direction_owner_review_required_for_public_source_batch_intake"
VALID_NEXT_ACTIONS = {NEXT_ACTION}
EXPECTED_CANDIDATE_COUNT = 12

REQUIRED_FILES = (
    "public_source_batch_intake_validation_manifest.json",
    "candidate_batch_inventory.csv",
    "batch_source_summary.md",
    "required_field_validation_table.csv",
    "constraint_filter_table.csv",
    "similarity_do_not_retest_table.csv",
    "local_cache_availability_table.csv",
    "eligibility_decisions.csv",
    "ranked_batch_intake_report.md",
    "top_candidates_for_direction_owner_review.md",
    "guardrail_checklist.json",
    "public_source_batch_intake_validation_next_action.md",
    "public_source_batch_intake_validation_consistency_check.json",
)

INVENTORY_FIELDS = ("rank", "source_id", "filename", "candidate_path", "source_name", "strategy_family", "status")
REQUIRED_FIELD_FIELDS = (
    "source_id",
    "source_name",
    "eligibility_decision",
    "missing_required_field_count",
    "missing_required_fields",
    "rule_clarity_status",
    "parse_error",
)
CONSTRAINT_FIELDS = ("source_id", "source_name", "eligibility_decision", "constraint_block_count", "constraint_blocks")
SIMILARITY_FIELDS = (
    "source_id",
    "source_name",
    "eligibility_decision",
    "family_similarity_hit_count",
    "family_similarity_hits",
)
ELIGIBILITY_FIELDS = (
    "rank",
    "source_id",
    "source_name",
    "strategy_family",
    "eligibility_decision",
    "next_action",
    "constraint_blocks",
    "family_similarity_hits",
    "missing_required_fields",
    "local_cache_complete",
    "notes",
)
BATCH_CACHE_FIELDS = ("source_id", "source_name", *CACHE_AVAILABILITY_FIELDS)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def decision_rank(decision: str) -> int:
    return {
        DECISION_ELIGIBLE: 1,
        DECISION_REVIEW: 2,
        DECISION_DUPLICATE: 3,
        DECISION_CONSTRAINT_BLOCKED: 4,
        DECISION_INCOMPLETE: 5,
    }.get(decision, 9)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize_notes(result: dict[str, Any], intake: dict[str, Any]) -> str:
    notes = dotted_get(intake, "project_notes.similarity_notes") or dotted_get(intake, "notes") or ""
    if isinstance(notes, list):
        return " | ".join(str(item) for item in notes)
    return str(notes)


def evaluate_batch(root: Path) -> dict[str, Any]:
    constraint_filter = read_yaml(root / CONSTRAINT_FILTER_PATH)
    family_map = read_yaml(root / FAMILY_MAP_PATH)
    files = candidate_files(root)
    results: list[dict[str, Any]] = []
    cache_rows_all: list[dict[str, Any]] = []
    for path in files:
        intake, parse_error = safe_load_candidate(path)
        result = evaluate_candidate(root, path, 1, intake, parse_error, constraint_filter, family_map)
        next_action = next_action_for(result["eligibility_decision"], result["source_id"])
        cache_rows, cache_checked = local_cache_rows(root, intake)
        cache_complete = bool(cache_checked) and bool(cache_rows) and all(row["cache_status"] == "cache_ready" for row in cache_rows)
        source_name = str(dotted_get(intake, "source.source_name") or path.stem)
        strategy_family = str(dotted_get(intake, "strategy_description.strategy_family") or "")
        payload = {
            **result,
            "candidate_path": str(path.resolve()),
            "filename": path.name,
            "source_name": source_name,
            "strategy_family": strategy_family,
            "next_action": next_action,
            "local_cache_complete": cache_complete,
            "notes": summarize_notes(result, intake),
        }
        results.append(payload)
        for row in cache_rows:
            cache_rows_all.append({"source_id": result["source_id"], "source_name": source_name, **row})
    results = sorted(results, key=lambda row: (decision_rank(row["eligibility_decision"]), row["source_id"]))
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank
    return {
        "candidate_count": len(files),
        "results": results,
        "cache_rows": cache_rows_all,
    }


def inventory_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": row["rank"],
            "source_id": row["source_id"],
            "filename": row["filename"],
            "candidate_path": row["candidate_path"],
            "source_name": row["source_name"],
            "strategy_family": row["strategy_family"],
            "status": "candidate_intake_file_found",
        }
        for row in results
    ]


def required_field_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "eligibility_decision": row["eligibility_decision"],
            "missing_required_field_count": len(row.get("exact_missing_fields", [])),
            "missing_required_fields": "|".join(row.get("exact_missing_fields", [])),
            "rule_clarity_status": row.get("rule_clarity_status", ""),
            "parse_error": row.get("parse_error") or "",
        }
        for row in results
    ]


def constraint_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "eligibility_decision": row["eligibility_decision"],
            "constraint_block_count": len(row.get("constraint_blocks", [])),
            "constraint_blocks": "|".join(row.get("constraint_blocks", [])),
        }
        for row in results
    ]


def similarity_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "eligibility_decision": row["eligibility_decision"],
            "family_similarity_hit_count": row.get("family_similarity_hit_count", 0),
            "family_similarity_hits": "|".join(row.get("family_similarity_hits", [])),
        }
        for row in results
    ]


def eligibility_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": row["rank"],
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "strategy_family": row["strategy_family"],
            "eligibility_decision": row["eligibility_decision"],
            "next_action": row["next_action"],
            "constraint_blocks": "|".join(row.get("constraint_blocks", [])),
            "family_similarity_hits": "|".join(row.get("family_similarity_hits", [])),
            "missing_required_fields": "|".join(row.get("exact_missing_fields", [])),
            "local_cache_complete": row["local_cache_complete"],
            "notes": row["notes"],
        }
        for row in results
    ]


def decision_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    return {decision: sum(1 for row in results if row["eligibility_decision"] == decision) for decision in sorted(VALID_ELIGIBILITY_DECISIONS)}


def batch_summary_md(results: list[dict[str, Any]]) -> str:
    counts = decision_counts(results)
    lines = ["# Public-Source Batch Intake Summary", ""]
    lines.append(f"Candidates evaluated: `{len(results)}`")
    lines.append("")
    for decision, count in counts.items():
        lines.append(f"- `{decision}`: `{count}`")
    lines.append("")
    lines.append("This is intake validation only. No bounded design, implementation, backtest, provider download, promotion, paper-forward activation, or broker/live action occurred.")
    return "\n".join(lines) + "\n"


def ranked_report_md(results: list[dict[str, Any]]) -> str:
    lines = ["# Ranked Batch Intake Report", ""]
    for row in results:
        lines.append(
            f"{row['rank']}. `{row['source_id']}` - `{row['eligibility_decision']}` "
            f"(family `{row['strategy_family']}`, cache complete `{row['local_cache_complete']}`)"
        )
    lines.append("")
    lines.append("Ranking is mechanical by eligibility category only: eligible, review, duplicate, blocked, incomplete. It is not a strategic recommendation.")
    return "\n".join(lines) + "\n"


def top_review_md(results: list[dict[str, Any]]) -> str:
    reviewable = [row for row in results if row["eligibility_decision"] in {DECISION_ELIGIBLE, DECISION_REVIEW}]
    lines = ["# Top Candidates For Later Direction-Owner Review", ""]
    if not reviewable:
        lines.append("No candidates reached eligible or review-required status.")
    for row in reviewable:
        lines.append(f"- `{row['source_id']}`: `{row['eligibility_decision']}`; next action `{row['next_action']}`")
    lines.append("")
    lines.append("This file does not authorize bounded design. It only lists candidates that survived hard intake blocks or require owner review.")
    return "\n".join(lines) + "\n"


def next_action_md() -> str:
    return f"""# Batch Intake Next Action

Exact next action:

`{NEXT_ACTION}`

Do not execute the next action in this task.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_batch_intake_validation_only",
        "bounded_bt_design_created",
        "strategy_backtest_run",
        "strategy_discovery_run",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "provider_download",
        "intraday_data_used",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return {key: manifest[key] for key in keys}


def manifest_payload(created: str, output: Path, batch: dict[str, Any]) -> dict[str, Any]:
    results = batch["results"]
    counts = decision_counts(results)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_batch_intake_validation_only": True,
        "candidate_count": len(results),
        "expected_candidate_count": EXPECTED_CANDIDATE_COUNT,
        "candidate_count_matches_manual_batch": len(results) == EXPECTED_CANDIDATE_COUNT,
        "eligibility_counts": counts,
        "eligible_candidate_count": counts.get(DECISION_ELIGIBLE, 0),
        "needs_direction_review_candidate_count": counts.get(DECISION_REVIEW, 0),
        "duplicate_or_do_not_retest_candidate_count": counts.get(DECISION_DUPLICATE, 0),
        "blocked_candidate_count": counts.get(DECISION_CONSTRAINT_BLOCKED, 0),
        "incomplete_candidate_count": counts.get(DECISION_INCOMPLETE, 0),
        "eligible_source_ids": [row["source_id"] for row in results if row["eligibility_decision"] == DECISION_ELIGIBLE],
        "needs_direction_review_source_ids": [row["source_id"] for row in results if row["eligibility_decision"] == DECISION_REVIEW],
        "duplicate_source_ids": [row["source_id"] for row in results if row["eligibility_decision"] == DECISION_DUPLICATE],
        "blocked_source_ids": [row["source_id"] for row in results if row["eligibility_decision"] == DECISION_CONSTRAINT_BLOCKED],
        "incomplete_source_ids": [row["source_id"] for row in results if row["eligibility_decision"] == DECISION_INCOMPLETE],
        "all_candidates_local_cache_checked": all(row["local_cache_complete"] or row["eligibility_decision"] == DECISION_INCOMPLETE for row in results),
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
        "next_action": NEXT_ACTION,
    }


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["public_source_batch_intake_validation_consistency_check.json"] = True
    checks = {
        "batch_validation_only": manifest["public_source_batch_intake_validation_only"] is True,
        "candidate_count_expected": manifest["candidate_count_matches_manual_batch"] is True,
        "decisions_sum_to_candidate_count": sum(manifest["eligibility_counts"].values()) == manifest["candidate_count"],
        "no_design_or_backtest": manifest["bounded_bt_design_created"] is False
        and manifest["strategy_backtest_run"] is False
        and manifest["strategy_discovery_run"] is False
        and manifest["broad_research_batch_run"] is False,
        "no_scrape_or_extra_ingestion": manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False,
        "no_provider_intraday_packages": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["new_packages_installed"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "public_source_not_profitability_proof": manifest["public_source_presence_is_profitability_proof"] is False,
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
    batch = evaluate_batch(root)
    manifest = manifest_payload(created, output, batch)

    write_json(output / "public_source_batch_intake_validation_manifest.json", manifest)
    write_csv(output / "candidate_batch_inventory.csv", inventory_rows(batch["results"]), list(INVENTORY_FIELDS))
    write_text(output / "batch_source_summary.md", batch_summary_md(batch["results"]))
    write_csv(output / "required_field_validation_table.csv", required_field_rows(batch["results"]), list(REQUIRED_FIELD_FIELDS))
    write_csv(output / "constraint_filter_table.csv", constraint_rows(batch["results"]), list(CONSTRAINT_FIELDS))
    write_csv(output / "similarity_do_not_retest_table.csv", similarity_rows(batch["results"]), list(SIMILARITY_FIELDS))
    write_csv(output / "local_cache_availability_table.csv", batch["cache_rows"], list(BATCH_CACHE_FIELDS))
    write_csv(output / "eligibility_decisions.csv", eligibility_rows(batch["results"]), list(ELIGIBILITY_FIELDS))
    write_text(output / "ranked_batch_intake_report.md", ranked_report_md(batch["results"]))
    write_text(output / "top_candidates_for_direction_owner_review.md", top_review_md(batch["results"]))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "public_source_batch_intake_validation_next_action.md", next_action_md())
    check = consistency_check(manifest, output)
    write_json(output / "public_source_batch_intake_validation_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
