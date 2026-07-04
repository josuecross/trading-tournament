from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv


OUTPUT_DIR = Path("evidence") / "research_recovery" / "public_source_preregistration_bridge" / "latest"
SOURCE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources"
INTAKE_TEMPLATE_PATH = SOURCE_DIR / "public_strategy_source_intake_template.yaml"
CONSTRAINT_FILTER_PATH = SOURCE_DIR / "public_strategy_constraint_filter.yaml"
FAMILY_MAP_PATH = SOURCE_DIR / "project_family_similarity_map.yaml"
CONTROL_POC_MANIFEST = (
    Path("evidence") / "research_recovery" / "bt_adapter_control_poc" / "latest" / "bt_adapter_control_poc_manifest.json"
)
MULTASSET_POC_MANIFEST = (
    Path("evidence")
    / "research_recovery"
    / "bt_adapter_multasset_control_poc"
    / "latest"
    / "bt_adapter_multasset_control_poc_manifest.json"
)

DECISION_INCOMPLETE = "source_intake_incomplete"
DECISION_CONSTRAINT_BLOCKED = "blocked_by_project_constraints"
DECISION_DUPLICATE = "duplicate_or_do_not_retest"
DECISION_ELIGIBLE = "eligible_for_bounded_bt_design"
DECISION_REVIEW = "needs_direction_owner_review"
VALID_ELIGIBILITY_DECISIONS = {
    DECISION_INCOMPLETE,
    DECISION_CONSTRAINT_BLOCKED,
    DECISION_DUPLICATE,
    DECISION_ELIGIBLE,
    DECISION_REVIEW,
}

NEXT_ACTION = "manual_public_source_intake_required"
VALID_NEXT_ACTIONS = {NEXT_ACTION}

REQUIRED_FILES = (
    "public_source_bridge_manifest.json",
    "public_source_bridge_summary.md",
    "intake_template_validation.md",
    "constraint_filter_validation.md",
    "family_similarity_mapping_report.md",
    "public_family_exclusion_map.csv",
    "preregistration_eligibility_report.md",
    "blank_intake_evaluation.json",
    "local_cache_symbol_inventory.csv",
    "adapter_readiness_report.md",
    "guardrail_checklist.json",
    "public_source_bridge_next_action.md",
    "public_source_bridge_consistency_check.json",
)

EXCLUSION_FIELDS = (
    "family_key",
    "current_project_status",
    "public_source_intake_action",
    "do_not_retest_rule",
    "aliases",
    "primary_evidence_paths",
)

CACHE_FIELDS = ("symbol", "path", "rows", "first_date", "last_date", "has_adj_close", "status")
MISSING_TEXT_MARKERS = {
    "",
    "manual_input_required",
    "none",
    "unknown",
    "not_available",
    "unspecified",
    "fill_me",
    "fill_me_or_not_applicable",
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower().replace("_", " "))


def feature_mentioned_without_negation(feature_blob: str, feature: str) -> bool:
    tokens = text_tokens(feature_blob)
    terms = [text_tokens(feature), text_tokens(feature.replace("_", " "))]
    for term in terms:
        if not term:
            continue
        width = len(term)
        for index in range(0, len(tokens) - width + 1):
            if tokens[index : index + width] != term:
                continue
            context = tokens[max(0, index - 3) : index]
            if any(marker in context for marker in {"no", "not", "without", "exclude", "excluded"}):
                continue
            return True
    return False


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def dotted_get(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_TEXT_MARKERS
    if isinstance(value, list):
        return len(value) == 0 or any(is_missing(item) for item in value)
    return False


def adapter_readiness(root: Path) -> dict[str, Any]:
    control = read_json(root / CONTROL_POC_MANIFEST)
    multasset = read_json(root / MULTASSET_POC_MANIFEST)
    return {
        "control_poc_manifest_exists": bool(control),
        "control_poc_passed": control.get("final_adapter_decision") == "bt_adapter_control_poc_passed",
        "control_poc_invariants_passed": control.get("exposure_invariant_passed") is True,
        "multasset_poc_manifest_exists": bool(multasset),
        "multasset_poc_passed": multasset.get("final_adapter_decision")
        == "bt_adapter_multasset_control_poc_passed",
        "multasset_poc_invariants_passed": multasset.get("exposure_invariant_passed") is True,
        "bt_package_available": control.get("bt_package_available") is True
        and multasset.get("bt_package_available") is True,
        "bt_package_version": multasset.get("bt_package_version") or control.get("bt_package_version") or "unknown",
        "adapter_target_weight_contract_validated": control.get("reference_comparison_performed") is True
        and multasset.get("reference_comparison_performed") is True,
    }


def validate_intake_template(intake: dict[str, Any], constraint_filter: dict[str, Any]) -> dict[str, Any]:
    required_fields = constraint_filter.get("required_complete_intake_fields", [])
    missing = [field for field in required_fields if is_missing(dotted_get(intake, field))]
    expected_top_level = {
        "schema_version",
        "intake_status",
        "source",
        "strategy_description",
        "rules",
        "data_and_execution",
        "project_screening",
        "governance",
        "notes",
    }
    return {
        "template_exists": bool(intake),
        "top_level_sections_present": expected_top_level.issubset(set(intake.keys())),
        "required_field_count": len(required_fields),
        "blank_required_field_count": len(missing),
        "blank_required_fields": missing,
        "blank_template_status": intake.get("intake_status") == "blank_template_manual_input_required",
        "public_strategy_selected_by_user": dotted_get(intake, "governance.public_strategy_selected_by_user") is True,
    }


def local_cache_symbols(root: Path) -> set[str]:
    return {str(row["symbol"]) for row in cache_inventory(root) if row.get("status") == "cache_ready"}


def find_constraint_blocks(intake: dict[str, Any], constraint_filter: dict[str, Any], root: Path) -> list[str]:
    blocks: list[str] = []
    feature_blob = " ".join(str(item).lower() for item in as_list(dotted_get(intake, "data_and_execution.data_requirements")))
    feature_blob += " " + str(dotted_get(intake, "data_and_execution.execution_assumptions") or "").lower()
    feature_blob += " " + str(dotted_get(intake, "rules.risk_controls") or "").lower()
    for feature in constraint_filter.get("hard_constraint_blocks", {}).get("prohibited_data_or_instrument_features", []):
        if feature_mentioned_without_negation(feature_blob, feature):
            blocks.append(feature)
    for feature in constraint_filter.get("hard_constraint_blocks", {}).get("prohibited_operational_features", []):
        if feature_mentioned_without_negation(feature_blob, feature):
            blocks.append(feature)

    instruments = [symbol for symbol in as_list(dotted_get(intake, "strategy_description.instruments")) if not is_missing(symbol)]
    if instruments:
        available = local_cache_symbols(root)
        missing = [str(symbol).upper() for symbol in instruments if str(symbol).upper() not in available]
        if missing:
            blocks.append("unavailable_symbols:" + "|".join(sorted(missing)))
    return blocks


def family_similarity_hits(intake: dict[str, Any], family_map: dict[str, Any]) -> list[dict[str, Any]]:
    text_parts = [
        dotted_get(intake, "strategy_description.strategy_family"),
        dotted_get(intake, "strategy_description.claimed_hypothesis"),
        dotted_get(intake, "rules.entry_rule"),
        dotted_get(intake, "rules.exit_rule"),
        dotted_get(intake, "rules.ranking_selection_rule"),
    ]
    haystack = " ".join(str(part).lower() for part in text_parts if part)
    hits: list[dict[str, Any]] = []
    if not haystack or "manual_input_required" in haystack:
        return hits
    for family in family_map.get("families", []):
        aliases = [family.get("family_key", ""), *family.get("aliases", [])]
        if any(alias and str(alias).lower() in haystack for alias in aliases):
            hits.append(family)
    return hits


def evaluate_intake(
    intake: dict[str, Any],
    constraint_filter: dict[str, Any],
    family_map: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    validation = validate_intake_template(intake, constraint_filter)
    constraint_blocks = find_constraint_blocks(intake, constraint_filter, root)
    hits = family_similarity_hits(intake, family_map)
    do_not_retest = dotted_get(intake, "project_screening.do_not_retest_match")
    review_hit = any(
        "review" in str(hit.get("public_source_intake_action", "")).lower()
        or "direction_owner" in str(hit.get("public_source_intake_action", "")).lower()
        for hit in hits
    )
    if validation["blank_required_field_count"] > 0 or not validation["public_strategy_selected_by_user"]:
        decision = DECISION_INCOMPLETE
    elif constraint_blocks:
        decision = DECISION_CONSTRAINT_BLOCKED
    elif hits or (isinstance(do_not_retest, str) and do_not_retest not in {"", "manual_input_required", "none"}):
        decision = DECISION_REVIEW if review_hit and is_missing(do_not_retest) else DECISION_DUPLICATE
    else:
        decision = DECISION_ELIGIBLE
    return {
        "eligibility_decision": decision,
        "constraint_blocks": constraint_blocks,
        "family_similarity_hit_count": len(hits),
        "family_similarity_hits": [hit.get("family_key") for hit in hits],
        **validation,
    }


def family_exclusion_rows(family_map: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for family in family_map.get("families", []):
        rows.append(
            {
                "family_key": family.get("family_key", ""),
                "current_project_status": family.get("current_project_status", ""),
                "public_source_intake_action": family.get("public_source_intake_action", ""),
                "do_not_retest_rule": family.get("do_not_retest_rule", ""),
                "aliases": "|".join(str(item) for item in family.get("aliases", [])),
                "primary_evidence_paths": "|".join(str(item) for item in family.get("primary_evidence_paths", [])),
            }
        )
    return rows


def template_validation_md(validation: dict[str, Any]) -> str:
    fields = "\n".join(f"- `{field}`" for field in validation["blank_required_fields"])
    return f"""# Intake Template Validation

Template exists: `{validation['template_exists']}`

Top-level sections present: `{validation['top_level_sections_present']}`

Blank template status valid: `{validation['blank_template_status']}`

Required fields: `{validation['required_field_count']}`

Blank/manual-input fields: `{validation['blank_required_field_count']}`

Blank fields:

{fields}
"""


def constraint_filter_md(constraint_filter: dict[str, Any]) -> str:
    prohibited = constraint_filter.get("hard_constraint_blocks", {}).get("prohibited_data_or_instrument_features", [])
    operations = constraint_filter.get("hard_constraint_blocks", {}).get("prohibited_operational_features", [])
    lines = ["# Constraint Filter Validation", ""]
    lines.append(f"Filter ID: `{constraint_filter.get('filter_id')}`")
    lines.append("")
    lines.append("Hard data/instrument blocks:")
    lines.extend(f"- `{item}`" for item in prohibited)
    lines.append("")
    lines.append("Hard operational blocks:")
    lines.extend(f"- `{item}`" for item in operations)
    lines.append("")
    lines.append("No public source can become eligible for bounded design until these filters pass.")
    return "\n".join(lines) + "\n"


def family_map_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Family Similarity Mapping Report", ""]
    lines.append(f"Mapped family groups: `{len(rows)}`")
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['family_key']}`: status `{row['current_project_status']}`, action `{row['public_source_intake_action']}`"
        )
    lines.append("")
    lines.append("This map is used to avoid retesting renamed failures or completed context-only lanes.")
    return "\n".join(lines) + "\n"


def eligibility_md(evaluation: dict[str, Any]) -> str:
    blocks = "\n".join(f"- `{item}`" for item in evaluation["constraint_blocks"]) or "- none"
    hits = "\n".join(f"- `{item}`" for item in evaluation["family_similarity_hits"]) or "- none"
    return f"""# Pre-Registration Eligibility Report

Current blank intake decision: `{evaluation['eligibility_decision']}`

Allowed future decisions:

- `{DECISION_INCOMPLETE}`
- `{DECISION_CONSTRAINT_BLOCKED}`
- `{DECISION_DUPLICATE}`
- `{DECISION_ELIGIBLE}`
- `{DECISION_REVIEW}`

Constraint blocks found:

{blocks}

Family similarity hits:

{hits}

A future manually selected source may reach `{DECISION_ELIGIBLE}` only after required fields are complete, hard constraints are absent, data are local-cache compatible, and no do-not-retest mapping applies.
"""


def adapter_readiness_md(readiness: dict[str, Any]) -> str:
    return f"""# Adapter Readiness Report

Simple control POC passed: `{readiness['control_poc_passed']}`

Simple control exposure invariants passed: `{readiness['control_poc_invariants_passed']}`

Multi-asset control POC passed: `{readiness['multasset_poc_passed']}`

Multi-asset exposure invariants passed: `{readiness['multasset_poc_invariants_passed']}`

bt package available: `{readiness['bt_package_available']}`

bt package version: `{readiness['bt_package_version']}`

Adapter target-weight contract validated: `{readiness['adapter_target_weight_contract_validated']}`

This bridge may route a future complete intake toward bounded `bt` design, but it does not create that design.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Public Source Pre-Registration Bridge

Bridge status: `created`

Intake template path: `{manifest['intake_template_path']}`

Constraint filter path: `{manifest['constraint_filter_path']}`

Family similarity map path: `{manifest['family_similarity_map_path']}`

Current blank intake eligibility decision: `{manifest['blank_intake_eligibility_decision']}`

Mapped project family groups: `{manifest['family_similarity_group_count']}`

bt adapter simple control POC passed: `{manifest['bt_control_poc_passed']}`

bt adapter multasset POC passed: `{manifest['bt_multasset_poc_passed']}`

No public strategy was selected, scraped, implemented, or run.

Exact next action: `{manifest['next_action']}`
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "public_source_preregistration_bridge_only",
        "public_strategy_selected",
        "public_source_scraped",
        "public_strategy_list_ingested",
        "public_strategy_implemented",
        "strategy_backtest_run",
        "strategy_discovery_run",
        "broad_research_batch_run",
        "provider_download",
        "intraday_data_used",
        "new_packages_installed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
        "current_backtester_replaced",
    ]
    return {key: manifest[key] for key in keys}


def next_action_md(next_action: str) -> str:
    return f"""# Public Source Bridge Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def manifest_payload(
    *,
    created: str,
    output: Path,
    intake_path: Path,
    filter_path: Path,
    map_path: Path,
    evaluation: dict[str, Any],
    readiness: dict[str, Any],
    family_count: int,
) -> dict[str, Any]:
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "public_source_preregistration_bridge_only": True,
        "intake_template_path": str(intake_path),
        "constraint_filter_path": str(filter_path),
        "family_similarity_map_path": str(map_path),
        "blank_example_intake_created": True,
        "blank_intake_eligibility_decision": evaluation["eligibility_decision"],
        "valid_eligibility_decisions": sorted(VALID_ELIGIBILITY_DECISIONS),
        "family_similarity_group_count": family_count,
        "bt_control_poc_passed": readiness["control_poc_passed"],
        "bt_multasset_poc_passed": readiness["multasset_poc_passed"],
        "bt_adapter_target_weight_contract_validated": readiness["adapter_target_weight_contract_validated"],
        "can_accept_manual_public_source_later": True,
        "can_route_to_future_bounded_bt_design_after_complete_intake": True,
        "bounded_bt_design_created": False,
        "public_strategy_selected": False,
        "public_source_scraped": False,
        "public_strategy_list_ingested": False,
        "public_strategy_implemented": False,
        "strategy_backtest_run": False,
        "strategy_discovery_run": False,
        "new_strategy_discovery_run": False,
        "broad_research_batch_run": False,
        "new_research_batch_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "new_packages_installed": False,
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
    required["public_source_bridge_consistency_check.json"] = True
    checks = {
        "bridge_only": manifest["public_source_preregistration_bridge_only"] is True,
        "template_filter_map_exist": Path(manifest["intake_template_path"]).exists()
        and Path(manifest["constraint_filter_path"]).exists()
        and Path(manifest["family_similarity_map_path"]).exists(),
        "blank_intake_incomplete": manifest["blank_intake_eligibility_decision"] == DECISION_INCOMPLETE,
        "adapter_prereqs_passed": manifest["bt_control_poc_passed"] is True
        and manifest["bt_multasset_poc_passed"] is True
        and manifest["bt_adapter_target_weight_contract_validated"] is True,
        "no_public_strategy_actions": manifest["public_strategy_selected"] is False
        and manifest["public_source_scraped"] is False
        and manifest["public_strategy_list_ingested"] is False
        and manifest["public_strategy_implemented"] is False
        and manifest["strategy_backtest_run"] is False,
        "no_discovery_or_batch": manifest["strategy_discovery_run"] is False
        and manifest["broad_research_batch_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_provider_intraday_packages": manifest["provider_download"] is False
        and manifest["intraday_data_used"] is False
        and manifest["new_packages_installed"] is False,
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

    intake = read_yaml(root / INTAKE_TEMPLATE_PATH)
    constraint_filter = read_yaml(root / CONSTRAINT_FILTER_PATH)
    family_map = read_yaml(root / FAMILY_MAP_PATH)
    readiness = adapter_readiness(root)
    validation = validate_intake_template(intake, constraint_filter)
    evaluation = evaluate_intake(intake, constraint_filter, family_map, root)
    family_rows = family_exclusion_rows(family_map)
    manifest = manifest_payload(
        created=created,
        output=output,
        intake_path=root / INTAKE_TEMPLATE_PATH,
        filter_path=root / CONSTRAINT_FILTER_PATH,
        map_path=root / FAMILY_MAP_PATH,
        evaluation=evaluation,
        readiness=readiness,
        family_count=len(family_rows),
    )

    write_json(output / "public_source_bridge_manifest.json", manifest)
    write_text(output / "public_source_bridge_summary.md", summary_md(manifest))
    write_text(output / "intake_template_validation.md", template_validation_md(validation))
    write_text(output / "constraint_filter_validation.md", constraint_filter_md(constraint_filter))
    write_text(output / "family_similarity_mapping_report.md", family_map_md(family_rows))
    write_csv(output / "public_family_exclusion_map.csv", family_rows, list(EXCLUSION_FIELDS))
    write_text(output / "preregistration_eligibility_report.md", eligibility_md(evaluation))
    write_json(output / "blank_intake_evaluation.json", evaluation)
    write_csv(output / "local_cache_symbol_inventory.csv", cache_inventory(root), list(CACHE_FIELDS))
    write_text(output / "adapter_readiness_report.md", adapter_readiness_md(readiness))
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "public_source_bridge_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, output)
    write_json(output / "public_source_bridge_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
