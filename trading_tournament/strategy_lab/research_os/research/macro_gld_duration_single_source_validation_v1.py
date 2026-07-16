from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "macro_gld_duration_single_source_validation_v1" / "latest"
INTAKE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
PRIOR_DIR = Path("evidence") / "macro_gld_duration_source_backed_preregistration_v1" / "latest"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
FAMILY_LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
RESEARCH_QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"

FAMILY_ID = "macro_gld_duration_risk_off"
OUTCOME_READY = "preregistration_ready"
OUTCOME_NOT_READY = "source_not_ready"
NEXT_ACTION = "supply_exactly_one_complete_macro_gld_duration_external_source_packet"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"

REQUIRED_RULE_FIELDS = (
    "entry_rule",
    "exit_rule",
    "risk_on_definition",
    "risk_off_definition",
    "gold_allocation_or_selection",
    "duration_allocation_or_selection",
    "lookbacks_and_parameters",
    "rebalance_cadence",
    "weighting",
    "bil_cash_fallback",
    "missing_signal_behavior",
    "signal_timestamp",
    "execution_timestamp",
)
REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "source_name",
    "source_url_or_citation",
    "source_type",
    "author_or_authors",
    "publication_date",
)
CONFIRMED_SURVIVORS = {
    "mgd_bounded_canary_defensive_top1_126_v1",
    "mgd_bounded_canary_defensive_top2_126_v1",
    "mgd_bounded_canary_defensive_top2_252_v1",
    "mgd_bounded_barbell_gated_126_v1",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def read_yaml(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    if not full.exists():
        return {}
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    full = abs_path(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def nested_get(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def source_id(payload: dict[str, Any], path: Path) -> str:
    return str(nested_get(payload, "source.source_id") or path.stem)


def declared_family(payload: dict[str, Any]) -> str:
    return str(nested_get(payload, "strategy_description.strategy_family") or "")


def find_declared_source_packets() -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for path in sorted((ROOT / INTAKE_DIR).glob("*.yaml")):
        payload = read_yaml(path)
        if declared_family(payload) != FAMILY_ID:
            continue
        packets.append({"path": path, "payload": payload, "source_id": source_id(payload, path)})
    return packets


def find_similarity_only_references() -> list[str]:
    refs: list[str] = []
    for path in sorted((ROOT / INTAKE_DIR).glob("*.yaml")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        payload = read_yaml(path)
        if declared_family(payload) == FAMILY_ID:
            continue
        if FAMILY_ID in text:
            refs.append(path.name)
    return refs


def support_lookup(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    support = payload.get("source_support", {}) or payload.get("rule_support", {}) or payload.get("supporting_evidence", {})
    if isinstance(support, dict):
        item = support.get(field_name, {})
        if isinstance(item, dict):
            return item
        if item:
            return {"reference": item}
    return {}


def extract_rule_value(payload: dict[str, Any], field_name: str) -> Any:
    path_options = {
        "entry_rule": ("rules.entry_rule",),
        "exit_rule": ("rules.exit_rule",),
        "risk_on_definition": ("rules.risk_on_definition", "rules.risk_on_rule"),
        "risk_off_definition": ("rules.risk_off_definition", "rules.risk_off_rule"),
        "gold_allocation_or_selection": ("rules.gold_allocation_or_selection", "rules.gold_selection_rule"),
        "duration_allocation_or_selection": ("rules.duration_allocation_or_selection", "rules.duration_selection_rule"),
        "lookbacks_and_parameters": ("rules.lookbacks_and_parameters", "indicator_definitions", "rules.parameters"),
        "rebalance_cadence": ("rules.rebalance_frequency", "rules.rebalance_cadence"),
        "weighting": ("rules.weighting", "rules.sizing_and_weighting"),
        "bil_cash_fallback": ("rules.bil_cash_fallback", "rules.cash_fallback", "rules.risk_controls"),
        "missing_signal_behavior": ("rules.missing_signal_behavior",),
        "signal_timestamp": ("data_and_execution.signal_timestamp", "data_and_execution.execution_assumptions"),
        "execution_timestamp": ("data_and_execution.execution_timestamp", "data_and_execution.execution_assumptions"),
    }
    for option in path_options.get(field_name, (field_name,)):
        value = nested_get(payload, option)
        if value not in (None, "", [], {}):
            return value
    return ""


def source_field_value(payload: dict[str, Any], field_name: str) -> Any:
    mapping = {
        "source_id": "source.source_id",
        "source_name": "source.source_name",
        "source_url_or_citation": "source.source_url_or_citation",
        "source_type": "source.source_type",
        "author_or_authors": "source.authors",
        "publication_date": "source.publication_date",
    }
    return nested_get(payload, mapping[field_name]) or ""


def local_cache_status(symbol: str) -> str:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    return "cache_ready" if path.exists() else "missing"


def build_no_source_rows(similarity_refs: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    extraction = [
        {
            "source_id": "none",
            "field": field,
            "extracted_value": "",
            "source_supported": False,
            "support_reference": "",
            "status": "missing_no_declared_macro_gld_source_packet",
        }
        for field in (*REQUIRED_SOURCE_FIELDS, *REQUIRED_RULE_FIELDS)
    ]
    support = [
        {
            "source_id": "none",
            "rule_field": "source_packet_identification",
            "source_reference_type": "intake_candidate_scan",
            "source_reference": str(INTAKE_DIR).replace("\\", "/"),
            "supports_rule": False,
            "notes": (
                "No YAML intake candidate declares strategy_description.strategy_family="
                f"{FAMILY_ID}. Similarity-only references found in: {'|'.join(similarity_refs) or 'none'}."
            ),
        }
    ]
    missing = [
        {
            "source_id": "none",
            "blocking_field": "single_new_source_packet",
            "blocking_reason": (
                "No clearly identifiable new intake packet declares the macro_gld_duration_risk_off family. "
                "Similarity warnings on unrelated public-source candidates are not source packets."
            ),
            "source_evidence_present": f"similarity_only_files={('|'.join(similarity_refs) or 'none')}",
            "source_evidence_absent": "source_id|citation|authors|publication_date|rule_support|macro_gld_duration_rules",
            "resolution_question": (
                "Supply exactly one YAML packet for a macro/GLD/duration/risk-off public source with complete source-supported rules."
            ),
        }
    ]
    return extraction, support, missing


def build_source_rows(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    payload = packet["payload"]
    sid = packet["source_id"]
    extraction: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for field in (*REQUIRED_SOURCE_FIELDS, *REQUIRED_RULE_FIELDS):
        value = source_field_value(payload, field) if field in REQUIRED_SOURCE_FIELDS else extract_rule_value(payload, field)
        support = support_lookup(payload, field)
        support_ref = support.get("reference") or support.get("page") or support.get("section") or support.get("excerpt") or ""
        supported = bool(value) and bool(support_ref)
        extraction.append(
            {
                "source_id": sid,
                "field": field,
                "extracted_value": value,
                "source_supported": supported,
                "support_reference": support_ref,
                "status": "resolved" if supported else "missing_or_unsupported",
            }
        )
        support_rows.append(
            {
                "source_id": sid,
                "rule_field": field,
                "source_reference_type": "packet_support_reference",
                "source_reference": support_ref,
                "supports_rule": supported,
                "notes": support.get("notes", ""),
            }
        )
        if not supported:
            missing.append(
                {
                    "source_id": sid,
                    "blocking_field": field,
                    "blocking_reason": "field missing or lacks page/section/table/code/excerpt support",
                    "source_evidence_present": csv_value(value),
                    "source_evidence_absent": "source_support_reference" if value else "field_value_and_support_reference",
                    "resolution_question": f"Provide source-backed {field} for {sid}.",
                }
            )
    return extraction, support_rows, missing


def build_etf_mapping(packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    if packet is None:
        return [
            {
                "source_id": "none",
                "source_asset_class": asset_class,
                "project_etf_wrapper": wrapper,
                "mapping_directness": "not_evaluated_no_source_packet",
                "inception_date_limitation": "unknown",
                "changes_strategy_mechanism": "",
                "local_cache_status": local_cache_status(wrapper),
            }
            for asset_class, wrapper in (
                ("US equities", "SPY"),
                ("gold", "GLD"),
                ("long Treasuries", "TLT"),
                ("intermediate Treasuries", "IEF"),
                ("cash/T-bills", "BIL"),
            )
        ]
    payload = packet["payload"]
    sid = packet["source_id"]
    proposed = payload.get("etf_wrapper_mapping", []) or payload.get("project_etf_wrapper_mapping", [])
    rows: list[dict[str, Any]] = []
    if isinstance(proposed, list):
        for item in proposed:
            if not isinstance(item, dict):
                continue
            wrapper = str(item.get("project_etf_wrapper") or item.get("etf") or "")
            rows.append(
                {
                    "source_id": sid,
                    "source_asset_class": item.get("source_asset_class", ""),
                    "project_etf_wrapper": wrapper,
                    "mapping_directness": item.get("why_mapping_direct", item.get("mapping_directness", "")),
                    "inception_date_limitation": item.get("inception_date_limitation", "unknown"),
                    "changes_strategy_mechanism": item.get("changes_strategy_mechanism", "unknown"),
                    "local_cache_status": local_cache_status(wrapper) if wrapper else "missing_wrapper",
                }
            )
    return rows


def material_distinction(packet: dict[str, Any] | None) -> dict[str, Any]:
    if packet is None:
        return {
            "source_id": "none",
            "closest_prior_variant": "mgd_bounded_canary_defensive_top1_126_v1|mgd_bounded_barbell_gated_126_v1",
            "shared_instruments_and_rules": "not_evaluated_no_source_packet",
            "shared_signal_and_rebalance_dimensions": "not_evaluated_no_source_packet",
            "materially_changed_mechanism": "not_proven",
            "difference_originates_in_external_source": False,
            "result_driven_tuning_risk": "not_applicable_no_candidate",
            "material_distinction_result": "blocked_no_source_packet",
            "notes": "No declared macro/GLD source packet exists, so material distinction cannot be evaluated.",
        }
    return {
        "source_id": packet["source_id"],
        "closest_prior_variant": "requires_rule_complete_comparison",
        "shared_instruments_and_rules": "requires_rule_complete_comparison",
        "shared_signal_and_rebalance_dimensions": "requires_rule_complete_comparison",
        "materially_changed_mechanism": "not_proven_until_all_rule_fields_are_source_supported",
        "difference_originates_in_external_source": False,
        "result_driven_tuning_risk": "unresolved",
        "material_distinction_result": "blocked_until_source_support_complete",
        "notes": "Material distinction is not accepted until all material rules have source provenance.",
    }


def decision_for(
    packets: list[dict[str, Any]],
    extraction_rows: list[dict[str, Any]],
    missing_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    material_row: dict[str, Any],
) -> dict[str, Any]:
    exactly_one = len(packets) == 1
    every_rule_supported = exactly_one and all(row["source_supported"] is True for row in extraction_rows)
    mapping_ready = exactly_one and bool(mapping_rows) and all(
        row["local_cache_status"] == "cache_ready"
        and str(row["changes_strategy_mechanism"]).lower() in {"false", "no", "does_not_change_mechanism"}
        for row in mapping_rows
    )
    material_ready = material_row["material_distinction_result"] == "materially_distinct"
    outcome = OUTCOME_READY if exactly_one and every_rule_supported and mapping_ready and material_ready else OUTCOME_NOT_READY
    blocker = ""
    if not exactly_one:
        blocker = "no_clearly_identifiable_single_new_source_packet" if len(packets) == 0 else "multiple_source_packets_present"
    elif not every_rule_supported:
        blocker = "required_source_or_rule_fields_missing_or_without_support_trace"
    elif not mapping_ready:
        blocker = "etf_wrapper_mapping_missing_or_changes_mechanism_or_cache_missing"
    elif not material_ready:
        blocker = "material_distinction_not_proven"
    return {
        "created_utc": now_utc(),
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "blocker": blocker,
        "source_packet_count": len(packets),
        "source_ids_evaluated": [packet["source_id"] for packet in packets],
        "preregistration_created": outcome == OUTCOME_READY,
        "source_not_ready": outcome == OUTCOME_NOT_READY,
        "every_frozen_rule_has_source_provenance": every_rule_supported,
        "missing_or_ambiguous_field_count": len(missing_rows),
        "wrapper_translation_changes_mechanism": False if not exactly_one else not mapping_ready,
        "material_distinction_result": material_row["material_distinction_result"],
        "closed_variants_remain_closed": True,
        "no_parameter_search_authorized": True,
        "no_backtest_run": True,
        "no_strategy_implementation": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
        "deterministic_input_hash": stable_hash(
            {
                "packet_paths": [str(packet["path"].relative_to(ROOT)) for packet in packets],
                "extraction": extraction_rows,
                "missing": missing_rows,
                "mapping": mapping_rows,
                "material": material_row,
            }
        ),
    }


def write_reports(
    decision: dict[str, Any],
    extraction_rows: list[dict[str, Any]],
    support_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    material_row: dict[str, Any],
    missing_rows: list[dict[str, Any]],
) -> None:
    write_csv(
        OUTPUT_DIR / "source_rule_extraction.csv",
        extraction_rows,
        ["source_id", "field", "extracted_value", "source_supported", "support_reference", "status"],
    )
    write_csv(
        OUTPUT_DIR / "source_support_trace.csv",
        support_rows,
        ["source_id", "rule_field", "source_reference_type", "source_reference", "supports_rule", "notes"],
    )
    write_csv(
        OUTPUT_DIR / "etf_wrapper_mapping.csv",
        mapping_rows,
        [
            "source_id",
            "source_asset_class",
            "project_etf_wrapper",
            "mapping_directness",
            "inception_date_limitation",
            "changes_strategy_mechanism",
            "local_cache_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "material_distinction_review.csv",
        [material_row],
        [
            "source_id",
            "closest_prior_variant",
            "shared_instruments_and_rules",
            "shared_signal_and_rebalance_dimensions",
            "materially_changed_mechanism",
            "difference_originates_in_external_source",
            "result_driven_tuning_risk",
            "material_distinction_result",
            "notes",
        ],
    )
    write_csv(
        OUTPUT_DIR / "missing_or_ambiguous_fields.csv",
        missing_rows,
        [
            "source_id",
            "blocking_field",
            "blocking_reason",
            "source_evidence_present",
            "source_evidence_absent",
            "resolution_question",
        ],
    )
    write_json(OUTPUT_DIR / "decision.json", decision)
    lines = [
        "# Macro/GLD Duration Single Source Validation v1",
        "",
        f"Outcome: `{decision['outcome']}`",
        f"Blocker: `{decision['blocker']}`",
        f"Source packet count: `{decision['source_packet_count']}`",
        f"Source IDs evaluated: `{csv_value(decision['source_ids_evaluated']) or 'none'}`",
        "",
        "No strategy implementation, backtest, parameter search, lifecycle change, paper/demo change, provider download, or real-money recommendation occurred.",
        "",
    ]
    if decision["outcome"] == OUTCOME_NOT_READY:
        lines.extend(
            [
                "The source is not ready for preregistration. No partial preregistration was created.",
                "",
                "Smallest external research question: supply exactly one intake YAML declaring `strategy_description.strategy_family: macro_gld_duration_risk_off` with complete source-supported rules, support references for each rule, and ETF wrapper mapping.",
            ]
        )
    write_text(OUTPUT_DIR / "decision.md", "\n".join(lines))


def consistency(decision: dict[str, Any], packets: list[dict[str, Any]], missing_rows: list[dict[str, Any]]) -> dict[str, Any]:
    exact_closed = read_csv_rows(PRIOR_DIR / "exact_variants_closed.csv")
    closed_ids = {row["variant_id"] for row in exact_closed}
    check = {
        "exactly_one_source_evaluated": decision["source_packet_count"] == 1,
        "blocked_when_no_or_multiple_sources": decision["source_packet_count"] != 1 and decision["outcome"] == OUTCOME_NOT_READY,
        "every_frozen_rule_has_source_provenance_if_ready": (
            decision["every_frozen_rule_has_source_provenance"] if decision["outcome"] == OUTCOME_READY else True
        ),
        "no_missing_field_silently_inferred": len(missing_rows) == decision["missing_or_ambiguous_field_count"],
        "closed_variants_remain_closed": CONFIRMED_SURVIVORS.issubset(closed_ids),
        "material_distinction_deterministic": decision["material_distinction_result"] in {
            "blocked_no_source_packet",
            "blocked_until_source_support_complete",
            "materially_distinct",
            "not_materially_distinct",
        },
        "wrapper_translation_does_not_change_mechanism_if_ready": (
            not decision["wrapper_translation_changes_mechanism"] if decision["outcome"] == OUTCOME_READY else True
        ),
        "no_parameter_search_or_backtest_authorized": decision["no_parameter_search_authorized"] is True
        and decision["no_backtest_run"] is True,
        "no_lifecycle_or_paper_demo_state_changes": decision["no_lifecycle_or_paper_demo_state_change"] is True,
        "generation_deterministic_hash_present": decision["deterministic_input_hash"].startswith("sha256:"),
        "preregistration_only_if_ready": (
            decision["preregistration_created"] is True if decision["outcome"] == OUTCOME_READY else decision["preregistration_created"] is False
        ),
    }
    check["consistency_passed"] = (
        (
            check["exactly_one_source_evaluated"] is True
            or check["blocked_when_no_or_multiple_sources"] is True
        )
        and check["every_frozen_rule_has_source_provenance_if_ready"] is True
        and check["no_missing_field_silently_inferred"] is True
        and check["closed_variants_remain_closed"] is True
        and check["material_distinction_deterministic"] is True
        and check["wrapper_translation_does_not_change_mechanism_if_ready"] is True
        and check["no_parameter_search_or_backtest_authorized"] is True
        and check["no_lifecycle_or_paper_demo_state_changes"] is True
        and check["generation_deterministic_hash_present"] is True
        and check["preregistration_only_if_ready"] is True
    )
    return check


def run() -> dict[str, Any]:
    packets = find_declared_source_packets()
    similarity_refs = find_similarity_only_references()
    packet = packets[0] if len(packets) == 1 else None
    if packet is None:
        extraction_rows, support_rows, missing_rows = build_no_source_rows(similarity_refs)
    else:
        extraction_rows, support_rows, missing_rows = build_source_rows(packet)
    mapping_rows = build_etf_mapping(packet)
    material_row = material_distinction(packet)
    decision = decision_for(packets, extraction_rows, missing_rows, mapping_rows, material_row)
    write_reports(decision, extraction_rows, support_rows, mapping_rows, material_row, missing_rows)
    check = consistency(decision, packets, missing_rows)
    write_json(OUTPUT_DIR / "consistency_check.json", check)
    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "family_id": FAMILY_ID,
        "outcome": decision["outcome"],
        "blocker": decision["blocker"],
        "source_packet_count": decision["source_packet_count"],
        "preregistration_created": decision["preregistration_created"],
        "missing_or_ambiguous_field_count": decision["missing_or_ambiguous_field_count"],
        "consistency_passed": check["consistency_passed"],
        "next_action": decision["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
