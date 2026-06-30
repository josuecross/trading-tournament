from __future__ import annotations

import csv
import hashlib
import json
import os
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .sandbox_batch_audit import BATCH_DIR, OUTPUT_DIR as AUDIT_OUTPUT_DIR
from .sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from .sandbox_status_taxonomy import FORBIDDEN_STATUSES


BATCH_ID = "batch_001"
OUTPUT_DIR = Path("evidence") / "exploratory_sandbox" / "batch_001_packet_fix" / "latest"
PACKET_NAME = "sandbox_batch_packet.zip"

NEXT_ACTION_MANUAL = "manual_review_after_sandbox_packet_fix"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
NEXT_ACTION_BATCH_002 = "run_exploratory_strategy_search_sandbox_batch_002"
VALID_NEXT_ACTIONS = {NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE, NEXT_ACTION_BATCH_002}

REQUIRED_PACKET_FILES = (
    "sandbox_batch_manifest.json",
    "sandbox_batch_summary.md",
    "sandbox_batch_preflight_report.md",
    "sandbox_variant_results.csv",
    "sandbox_family_summary.csv",
    "sandbox_family_summary.md",
    "sandbox_benchmark_comparison_summary.csv",
    "sandbox_risk_summary.csv",
    "sandbox_diversification_summary.csv",
    "sandbox_practicality_summary.csv",
    "sandbox_overfitting_risk_summary.md",
    "sandbox_research_only_leverage_summary.md",
    "sandbox_future_preregistration_candidates.md",
    "sandbox_discarded_or_weak_families.md",
    "sandbox_do_not_promote.md",
    "sandbox_batch_next_action.md",
    "sandbox_batch_consistency_check.json",
)

REQUIRED_FIX_FILES = (
    "sandbox_packet_fix_manifest.json",
    "sandbox_packet_fix_summary.md",
    "packet_rebuild_report.md",
    "packet_required_files_check.csv",
    "packet_consistency_comparison.md",
    "live_vs_packet_manifest_comparison.json",
    "packet_checksum_report.md",
    "packet_fix_do_not_rerun.md",
    "repaired_packet_path.md",
    "sandbox_packet_fix_next_action.md",
    "sandbox_packet_fix_consistency_check.json",
)

MANIFEST_FLAGS = {
    "packet_fix_only": True,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_computed": False,
    "sandbox_results_changed": False,
    "variant_statuses_changed": False,
    "family_audit_changed": False,
    "future_preregistration_candidates_created": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "sandbox_results_remain_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
}

CORE_MANIFEST_FIELDS = (
    "batch_id",
    "sandbox_batch_run",
    "sandbox_results_non_promotable",
    "sandbox_can_create_paper_candidates",
    "strategy_discovery_run",
    "formal_discovery_run",
    "candidate_exhaustive_run",
    "paper_forward_review",
    "paper_forward_activation",
    "provider_download",
    "intraday_data_used",
    "broker_orders_submitted",
    "broker_orders_cancelled",
    "live_orders",
    "real_money_recommendation",
    "variant_count_planned",
    "variant_count_evaluated",
    "families_evaluated_count",
    "sandbox_future_preregistration_candidate_count",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def live_file_hashes(batch_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(batch_dir.iterdir())
        if path.is_file() and path.name != PACKET_NAME and not path.name.endswith(".tmp")
    }


def audit_file_hashes(root: Path) -> dict[str, str]:
    audit_dir = root / AUDIT_OUTPUT_DIR
    if not audit_dir.exists():
        return {}
    return {
        path.name: sha256_file(path)
        for path in sorted(audit_dir.iterdir())
        if path.is_file() and path.suffix != ".zip"
    }


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def zip_entry_json(packet: Path, name: str) -> dict[str, Any]:
    if not packet.exists():
        return {}
    with zipfile.ZipFile(packet, "r") as archive:
        try:
            with archive.open(name) as handle:
                return json.loads(handle.read().decode("utf-8"))
        except KeyError:
            return {}


def zip_entry_hashes(packet: Path) -> dict[str, str]:
    if not packet.exists():
        return {}
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(packet, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            with archive.open(info) as handle:
                hashes[Path(info.filename).name] = sha256_bytes(handle.read())
    return hashes


def packet_names(packet: Path) -> set[str]:
    if not packet.exists():
        return set()
    with zipfile.ZipFile(packet, "r") as archive:
        return {Path(info.filename).name for info in archive.infolist() if not info.is_dir()}


def rebuild_packet(batch_dir: Path) -> Path:
    packet = batch_dir / PACKET_NAME
    tmp_packet = batch_dir / f"{PACKET_NAME}.tmp"
    if tmp_packet.exists():
        tmp_packet.unlink()
    with zipfile.ZipFile(tmp_packet, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(batch_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name == PACKET_NAME or path.name.endswith(".tmp") or path.suffix == ".zip":
                continue
            archive.write(path, path.name)
    os.replace(tmp_packet, packet)
    return packet


def no_promotable_rows(variant_rows: list[dict[str, str]]) -> bool:
    return all(row.get("promotable") == "false" for row in variant_rows)


def no_paper_candidate_rows(variant_rows: list[dict[str, str]]) -> bool:
    return all(row.get("paper_candidate_allowed") == "false" for row in variant_rows)


def forbidden_statuses_absent(variant_rows: list[dict[str, str]]) -> bool:
    return not ({row.get("status", "") for row in variant_rows} & set(FORBIDDEN_STATUSES))


def manifest_comparison(live_manifest: dict[str, Any], packet_manifest: dict[str, Any]) -> dict[str, Any]:
    rows = {}
    for field in CORE_MANIFEST_FIELDS:
        rows[field] = {
            "live": live_manifest.get(field),
            "packet": packet_manifest.get(field),
            "matches": live_manifest.get(field) == packet_manifest.get(field),
        }
    return {
        "core_fields": rows,
        "all_core_fields_match": all(item["matches"] for item in rows.values()),
    }


def required_file_rows(batch_dir: Path, packet: Path) -> list[dict[str, Any]]:
    names = packet_names(packet)
    return [
        {
            "file": name,
            "live_exists": (batch_dir / name).exists(),
            "packet_exists": name in names,
        }
        for name in REQUIRED_PACKET_FILES
    ]


def packet_consistency_passed(consistency: dict[str, Any]) -> bool:
    return (
        consistency.get("consistency_passed") is True
        and consistency.get("required_files_exist") is True
        and consistency.get("results_non_promotable") is True
        and consistency.get("sandbox_cannot_create_paper_candidates") is True
        and consistency.get("no_provider_download") is True
        and consistency.get("no_intraday_data_used") is True
        and consistency.get("no_candidate_exhaustive") is True
        and consistency.get("no_paper_forward_action") is True
        and consistency.get("no_broker_live_action") is True
        and consistency.get("no_real_money_recommendation") is True
    )


def checksum_report_md(live_hashes: dict[str, str], packet_hashes: dict[str, str]) -> str:
    lines = ["# Packet Checksum Report", "", "| file | live sha256 | packet sha256 | match |", "|---|---|---|---|"]
    for name in sorted(REQUIRED_PACKET_FILES):
        live = live_hashes.get(name, "")
        packet = packet_hashes.get(name, "")
        lines.append(f"| `{name}` | `{live}` | `{packet}` | `{live == packet}` |")
    return "\n".join(lines)


def rebuild_report_md(original_consistency: dict[str, Any], repaired_consistency: dict[str, Any], packet: Path) -> str:
    return f"""# Packet Rebuild Report

Repaired packet: `{packet.resolve()}`

Original packaged consistency:

- `consistency_passed`: `{original_consistency.get('consistency_passed')}`
- `required_files_exist`: `{original_consistency.get('required_files_exist')}`

Repaired packaged consistency:

- `consistency_passed`: `{repaired_consistency.get('consistency_passed')}`
- `required_files_exist`: `{repaired_consistency.get('required_files_exist')}`

Repair method: rebuilt the zip from final live evidence files only. No strategy result CSV/JSON was recomputed or modified.
"""


def consistency_comparison_md(live_consistency: dict[str, Any], original_packet: dict[str, Any], repaired_packet: dict[str, Any]) -> str:
    keys = [
        "consistency_passed",
        "required_files_exist",
        "results_non_promotable",
        "sandbox_cannot_create_paper_candidates",
        "no_provider_download",
        "no_intraday_data_used",
        "no_candidate_exhaustive",
        "no_paper_forward_action",
        "no_broker_live_action",
        "no_real_money_recommendation",
    ]
    lines = ["# Packet Consistency Comparison", "", "| field | live | original packet | repaired packet |", "|---|---:|---:|---:|"]
    for key in keys:
        lines.append(f"| `{key}` | `{live_consistency.get(key)}` | `{original_packet.get(key)}` | `{repaired_packet.get(key)}` |")
    return "\n".join(lines)


def do_not_rerun_md() -> str:
    return """# Packet Fix Do Not Rerun

This repair rebuilt the evidence packet only.

Not run:

- sandbox batch
- strategy discovery
- backtests
- new strategy performance metrics
- provider downloads
- intraday data
- candidate_exhaustive
- paper-forward review or activation
- broker/live-order paths
- real-money recommendations
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Exploratory Sandbox Batch 001 Packet Fix

Packet-fix-only: `{manifest['packet_fix_only']}`

Audited batch: `{manifest['audited_batch_id']}`

Original packet consistency passed: `{manifest['original_packet_consistency_passed']}`

Repaired packet consistency passed: `{manifest['repaired_packet_consistency_passed']}`

Required packet files exist after fix: `{manifest['packet_required_files_exist_after_fix']}`

Sandbox results changed: `{manifest['sandbox_results_changed']}`

Future preregistration candidates created: `{manifest['future_preregistration_candidates_created']}`

Next action: `{manifest['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Sandbox Packet Fix Next Action

Exact next action: `{next_action}`

Do not run the next action in this packet-fix task.
"""


def repaired_packet_path_md(packet: Path) -> str:
    return f"""# Repaired Packet Path

`{packet.resolve()}`
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before = deepcopy(metadata)
    metadata.update(
        {
            "exploratory_sandbox_batch_001_packet_fix_path": str(output.resolve()),
            "exploratory_sandbox_batch_001_packet_fix_status": "completed_packet_repaired",
            "exploratory_sandbox_batch_001_packet_fix_created_utc": created_utc,
            "current_research_mode": "exploratory_sandbox_batch_packet_fixed",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_packet_fix_only": True,
            "sandbox_packet_original_consistency_passed": manifest["original_packet_consistency_passed"],
            "sandbox_packet_repaired_consistency_passed": manifest["repaired_packet_consistency_passed"],
            "sandbox_packet_required_files_exist_after_fix": manifest["packet_required_files_exist_after_fix"],
            "sandbox_packet_fix_no_new_batch_run": True,
            "sandbox_packet_fix_no_backtests": True,
            "sandbox_packet_fix_no_provider_download": True,
            "sandbox_packet_fix_no_intraday_data": True,
            "sandbox_packet_fix_no_candidate_exhaustive": True,
            "sandbox_packet_fix_no_paper_forward_action": True,
            "sandbox_packet_fix_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    before_text = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `exploratory_sandbox_batch_packet_fixed`
- Official current next action: `{manifest['next_action']}`
- Exploratory sandbox packet-fix evidence: `{output.resolve()}`
- Packet-fix-only: `true`
- Original packet consistency passed: `{manifest['original_packet_consistency_passed']}`
- Repaired packet consistency passed: `{manifest['repaired_packet_consistency_passed']}`
- Required packet files exist after fix: `{manifest['packet_required_files_exist_after_fix']}`
- Sandbox results changed: `false`
- Future preregistration candidates created: `false`
- Sandbox results remain non-promotable: `true`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This packet fix did not run a new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Exploratory Sandbox Batch 001 Packet Fix

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Repaired packet path: `{manifest['repaired_packet_path']}`
- Original packet consistency passed: `{manifest['original_packet_consistency_passed']}`
- Repaired packet consistency passed: `{manifest['repaired_packet_consistency_passed']}`
- Required packet files exist after fix: `{manifest['packet_required_files_exist_after_fix']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this packet-fix task.
- No new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""
    after = replace_or_append_section(before_text, "## Compact Current State", compact)
    after = replace_or_append_section(after, "## Exploratory Sandbox Batch 001 Packet Fix", section)
    write_text(roadmap_path, after)
    return before != metadata, before_text != after


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "packet_fix_only": manifest["packet_fix_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "sandbox_results_unchanged": manifest["sandbox_results_changed"] is False,
        "variant_statuses_unchanged": manifest["variant_statuses_changed"] is False,
        "family_audit_unchanged": manifest["family_audit_changed"] is False,
        "no_future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "sandbox_results_remain_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "repaired_packet_consistency_passed": manifest["repaired_packet_consistency_passed"] is True,
        "repaired_packet_required_files_exist": manifest["packet_required_files_exist_after_fix"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FIX_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_packet_fix(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    batch_dir = root / BATCH_DIR
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    packet = batch_dir / PACKET_NAME
    before_strategies = strategy_snapshot(root)
    live_hashes_before = live_file_hashes(batch_dir)
    audit_hashes_before = audit_file_hashes(root)
    original_packet_consistency = zip_entry_json(packet, "sandbox_batch_consistency_check.json")
    live_consistency = read_json(batch_dir / "sandbox_batch_consistency_check.json")
    live_manifest = read_json(batch_dir / "sandbox_batch_manifest.json")
    variants = read_csv(batch_dir / "sandbox_variant_results.csv")
    family_rows = read_csv(batch_dir / "sandbox_family_summary.csv")
    required_live_rows = required_file_rows(batch_dir, packet)
    rebuilt_packet = rebuild_packet(batch_dir)
    repaired_packet_consistency = zip_entry_json(rebuilt_packet, "sandbox_batch_consistency_check.json")
    repaired_packet_manifest = zip_entry_json(rebuilt_packet, "sandbox_batch_manifest.json")
    required_rows_after = required_file_rows(batch_dir, rebuilt_packet)
    packet_hashes = zip_entry_hashes(rebuilt_packet)
    live_hashes_after = live_file_hashes(batch_dir)
    audit_hashes_after = audit_file_hashes(root)
    comparison = manifest_comparison(live_manifest, repaired_packet_manifest)
    next_action = NEXT_ACTION_MANUAL
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "audited_batch_id": BATCH_ID,
        "source_variant_count": int(live_manifest.get("variant_count_evaluated", len(variants)) or 0),
        "source_family_count": int(live_manifest.get("families_evaluated_count", len(family_rows)) or 0),
        "source_future_preregistration_candidate_count": int(live_manifest.get("sandbox_future_preregistration_candidate_count", 0) or 0),
        "original_packet_consistency_passed": original_packet_consistency.get("consistency_passed") is True,
        "repaired_packet_consistency_passed": packet_consistency_passed(repaired_packet_consistency),
        "packet_required_files_exist_after_fix": all(row["packet_exists"] for row in required_rows_after),
        "live_required_files_exist": all(row["live_exists"] for row in required_rows_after),
        "packet_consistency_file_is_not_stale": repaired_packet_consistency == live_consistency,
        "packet_manifest_core_fields_match_live": comparison["all_core_fields_match"],
        "packet_variant_count_matches_live": int(repaired_packet_manifest.get("variant_count_evaluated", -1)) == int(live_manifest.get("variant_count_evaluated", -2)),
        "packet_family_count_matches_live": int(repaired_packet_manifest.get("families_evaluated_count", -1)) == int(live_manifest.get("families_evaluated_count", -2)),
        "no_promotable_results": no_promotable_rows(variants),
        "no_paper_candidates_allowed": no_paper_candidate_rows(variants),
        "forbidden_statuses_absent": forbidden_statuses_absent(variants),
        "repaired_packet_path": str(rebuilt_packet.resolve()),
        "next_action": next_action,
    }
    manifest["sandbox_results_changed"] = live_hashes_before != live_hashes_after
    manifest["variant_statuses_changed"] = False
    manifest["family_audit_changed"] = audit_hashes_before != audit_hashes_after
    after_strategies = strategy_snapshot(root)
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_json(output / "sandbox_packet_fix_manifest.json", manifest)
    write_text(output / "sandbox_packet_fix_summary.md", summary_md(manifest))
    write_text(output / "packet_rebuild_report.md", rebuild_report_md(original_packet_consistency, repaired_packet_consistency, rebuilt_packet))
    write_csv(output / "packet_required_files_check.csv", required_rows_after, ["file", "live_exists", "packet_exists"])
    write_text(output / "packet_consistency_comparison.md", consistency_comparison_md(live_consistency, original_packet_consistency, repaired_packet_consistency))
    write_json(output / "live_vs_packet_manifest_comparison.json", comparison)
    write_text(output / "packet_checksum_report.md", checksum_report_md(live_hashes_after, packet_hashes))
    write_text(output / "packet_fix_do_not_rerun.md", do_not_rerun_md())
    write_text(output / "repaired_packet_path.md", repaired_packet_path_md(rebuilt_packet))
    write_text(output / "sandbox_packet_fix_next_action.md", next_action_md(next_action))
    write_json(output / "sandbox_packet_fix_consistency_check.json", {"consistency_passed": False})

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "sandbox_packet_fix_manifest.json", manifest)
    write_json(output / "sandbox_packet_fix_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "audited_batch_id": BATCH_ID,
        "original_packet_consistency_passed": manifest["original_packet_consistency_passed"],
        "repaired_packet_consistency_passed": manifest["repaired_packet_consistency_passed"],
        "packet_required_files_exist_after_fix": manifest["packet_required_files_exist_after_fix"],
        "sandbox_results_changed": manifest["sandbox_results_changed"],
        "future_preregistration_candidates_created": manifest["future_preregistration_candidates_created"],
        "repaired_packet_path": manifest["repaired_packet_path"],
        "next_action": manifest["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }
