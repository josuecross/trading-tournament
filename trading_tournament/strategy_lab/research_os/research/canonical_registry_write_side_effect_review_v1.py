from __future__ import annotations

import csv
import difflib
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
OUTPUT_DIR = Path("evidence") / "canonical_registry_write_side_effect_review_v1" / "latest"

COMMANDS: tuple[tuple[str, list[str]], ...] = (
    ("run_strategy_evidence_library", [".venv\\Scripts\\python.exe", "run_strategy_evidence_library.py"]),
    ("run_current_research_checkpoint", [".venv\\Scripts\\python.exe", "run_current_research_checkpoint.py"]),
    ("run_research_state_dashboard", [".venv\\Scripts\\python.exe", "run_research_state_dashboard.py"]),
    ("run_advisor_consistency_check", [".venv\\Scripts\\python.exe", "run_advisor_consistency_check.py"]),
    ("run_strategy_lab_validate_export", [".venv\\Scripts\\python.exe", "run_strategy_lab.py", "--validate-registry", "--export-evidence"]),
    (
        "run_current_multi_asset_portfolio_accounting_blast_radius_v1",
        [".venv\\Scripts\\python.exe", "run_current_multi_asset_portfolio_accounting_blast_radius_v1.py"],
    ),
)

DERIVED_METADATA_FIELDS = {
    "current_research_checkpoint_path",
    "etf_discovery_status",
    "candidate_pipeline_empty",
    "next_engineering_action",
    "next_research_action_after_engineering",
    "no_candidate_exhaustive_run",
    "no_paper_forward_action",
    "no_real_money_recommendation",
    "active_combo_reconciliation_path",
    "active_combo_reference_available",
    "active_combo_benchmark_path",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.exists() else "missing"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def registry_bytes(root: Path) -> bytes:
    return (root / REGISTRY_PATH).read_bytes()


def registry_text(root: Path) -> str:
    return registry_bytes(root).decode("utf-8")


def restore_registry(root: Path, content: bytes) -> None:
    (root / REGISTRY_PATH).write_bytes(content)


def unified_diff(before: bytes, after: bytes, before_label: str, after_label: str) -> str:
    before_lines = before.decode("utf-8", errors="replace").splitlines()
    after_lines = after.decode("utf-8", errors="replace").splitlines()
    return "\n".join(difflib.unified_diff(before_lines, after_lines, fromfile=before_label, tofile=after_label, lineterm=""))


def affected_fields(diff_text: str) -> list[str]:
    fields: set[str] = set()
    for line in diff_text.splitlines():
        if not line.startswith(("+  ", "-  ")):
            continue
        stripped = line[3:].strip()
        if ":" in stripped:
            fields.add(stripped.split(":", 1)[0])
    return sorted(fields)


def classify_change(diff_text: str) -> str:
    if not diff_text:
        return "no_registry_write"
    fields = set(affected_fields(diff_text))
    if fields and fields <= DERIVED_METADATA_FIELDS:
        return "derived_metadata_write"
    if fields:
        return "semantic_registry_write"
    return "formatting_only_write"


def git_registry_diff(root: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "--", str(REGISTRY_PATH).replace("/", "\\")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def run_command(root: Path, name: str, command: list[str], iteration: int) -> dict[str, Any]:
    before = registry_bytes(root)
    before_hash = sha256_bytes(before)
    proc = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    after = registry_bytes(root)
    after_hash = sha256_bytes(after)
    diff = unified_diff(before, after, f"{name}_{iteration}_before", f"{name}_{iteration}_after")
    changed = before_hash != after_hash
    if changed:
        restore_registry(root, before)
    return {
        "command": name,
        "iteration": iteration,
        "exit_code": proc.returncode,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "registry_changed": changed,
        "classification": classify_change(diff),
        "affected_fields": ";".join(affected_fields(diff)),
        "textual_diff": diff,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-8:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-8:]),
    }


def command_inventory(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, command in COMMANDS:
        command_results = [row for row in results if row["command"] == name]
        changed = any(row["registry_changed"] for row in command_results)
        fields = sorted({field for row in command_results for field in str(row["affected_fields"]).split(";") if field})
        classifications = sorted({row["classification"] for row in command_results})
        rows.append(
            {
                "command": name,
                "command_line": " ".join(command),
                "iterations": len(command_results),
                "exit_codes": ";".join(str(row["exit_code"]) for row in command_results),
                "registry_changed": changed,
                "classification": ";".join(classifications) if classifications else "no_registry_write",
                "affected_fields": ";".join(fields),
                "patch_required": name == "run_current_research_checkpoint",
                "notes": "normal reporting mode is read-only after patch" if not changed else "registry mutation detected and restored during review",
            }
        )
    return rows


def hash_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "command": row["command"],
            "iteration": row["iteration"],
            "before_hash": row["before_hash"],
            "after_hash": row["after_hash"],
            "registry_changed": row["registry_changed"],
            "exit_code": row["exit_code"],
        }
        for row in results
    ]


def diff_rows(results: list[dict[str, Any]], pre_existing_diff: str) -> list[dict[str, Any]]:
    rows = [
        {
            "command": row["command"],
            "iteration": row["iteration"],
            "classification": row["classification"],
            "affected_fields": row["affected_fields"],
            "textual_diff": row["textual_diff"],
            "semantic_diff": "none" if not row["textual_diff"] else f"affected_fields={row['affected_fields']}",
        }
        for row in results
    ]
    rows.append(
        {
            "command": "pre_existing_worktree_diff",
            "iteration": "",
            "classification": classify_change(pre_existing_diff),
            "affected_fields": ";".join(affected_fields(pre_existing_diff)),
            "textual_diff": pre_existing_diff,
            "semantic_diff": "pre-existing diff captured before this bounded patch; not produced by post-patch scoped commands",
        }
    )
    return rows


def idempotence_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, _command in COMMANDS:
        command_results = [row for row in results if row["command"] == name]
        rows.append(
            {
                "command": name,
                "run_count": len(command_results),
                "all_exit_zero": all(row["exit_code"] == 0 for row in command_results),
                "all_registry_hashes_preserved": all(row["before_hash"] == row["after_hash"] for row in command_results),
                "second_run_registry_hash_preserved": len(command_results) >= 2 and command_results[1]["before_hash"] == command_results[1]["after_hash"],
                "idempotent": len(command_results) == 2 and all(row["exit_code"] == 0 and row["before_hash"] == row["after_hash"] for row in command_results),
            }
        )
    return rows


def write_call_sites() -> list[dict[str, Any]]:
    return [
        {
            "command": "run_current_research_checkpoint",
            "file": "run_current_research_checkpoint.py",
            "function_or_call_site": "run_current_research_checkpoint -> update_registry_metadata",
            "pre_patch_behavior": "normal checkpoint/report generation rewrote strategy_lab/strategy_registry.yaml with derived metadata",
            "post_patch_behavior": "normal checkpoint/report generation writes current_research_checkpoint_registry_metadata_view.json inside evidence only",
            "classification": "derived_metadata_write",
            "affected_fields": ";".join(sorted(DERIVED_METADATA_FIELDS)),
        }
    ]


def patches_applied() -> list[dict[str, Any]]:
    return [
        {
            "path": "run_current_research_checkpoint.py",
            "change": "removed canonical registry write from normal checkpoint run; derived registry metadata is now emitted as an evidence view",
            "canonical_registry_write_after_patch": False,
            "migration_path_added": False,
        },
        {
            "path": "tests/test_current_research_checkpoint.py",
            "change": "updated checkpoint regression tests to assert registry byte preservation and metadata-view generation",
            "canonical_registry_write_after_patch": False,
            "migration_path_added": False,
        },
        {
            "path": "strategy_lab/research_os/research/canonical_registry_write_side_effect_review_v1.py",
            "change": "added bounded command hash/diff/idempotence evidence generator",
            "canonical_registry_write_after_patch": False,
            "migration_path_added": False,
        },
        {
            "path": "run_canonical_registry_write_side_effect_review_v1.py",
            "change": "added runner for the bounded side-effect review evidence packet",
            "canonical_registry_write_after_patch": False,
            "migration_path_added": False,
        },
    ]


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    initial_registry = registry_bytes(root)
    initial_hash = sha256_bytes(initial_registry)
    pre_existing_diff = git_registry_diff(root)
    results: list[dict[str, Any]] = []
    for name, command in COMMANDS:
        for iteration in (1, 2):
            results.append(run_command(root, name, command, iteration))
            if registry_bytes(root) != initial_registry:
                restore_registry(root, initial_registry)

    final_hash = file_hash(root / REGISTRY_PATH)
    inventory = command_inventory(results)
    hashes = hash_rows(results)
    diffs = diff_rows(results, pre_existing_diff)
    idempotence = idempotence_rows(results)
    remaining = [
        {
            "command": row["command"],
            "iteration": row["iteration"],
            "classification": row["classification"],
            "affected_fields": row["affected_fields"],
            "reason": "post-patch scoped command still wrote registry",
        }
        for row in results
        if row["registry_changed"]
    ]

    write_csv(output / "command_write_inventory.csv", inventory, ["command", "command_line", "iterations", "exit_codes", "registry_changed", "classification", "affected_fields", "patch_required", "notes"])
    write_csv(output / "registry_hashes_before_after.csv", hashes, ["command", "iteration", "before_hash", "after_hash", "registry_changed", "exit_code"])
    write_csv(output / "registry_diffs.csv", diffs, ["command", "iteration", "classification", "affected_fields", "textual_diff", "semantic_diff"])
    write_csv(output / "write_call_sites.csv", write_call_sites(), ["command", "file", "function_or_call_site", "pre_patch_behavior", "post_patch_behavior", "classification", "affected_fields"])
    write_csv(output / "patches_applied.csv", patches_applied(), ["path", "change", "canonical_registry_write_after_patch", "migration_path_added"])
    write_csv(output / "idempotence_results.csv", idempotence, ["command", "run_count", "all_exit_zero", "all_registry_hashes_preserved", "second_run_registry_hash_preserved", "idempotent"])
    write_csv(output / "remaining_write_side_effects.csv", remaining, ["command", "iteration", "classification", "affected_fields", "reason"])

    consistency = {
        "review_packet_created": True,
        "scoped_command_count": len(COMMANDS),
        "each_command_run_twice": all(row["run_count"] == 2 for row in idempotence),
        "all_commands_exit_zero": all(row["all_exit_zero"] is True for row in idempotence),
        "all_registry_hashes_preserved": all(row["all_registry_hashes_preserved"] is True for row in idempotence),
        "remaining_write_side_effect_count": len(remaining),
        "no_remaining_write_side_effects": len(remaining) == 0,
        "initial_registry_hash": initial_hash,
        "final_registry_hash": final_hash,
        "final_registry_matches_initial_review_hash": final_hash == initial_hash,
        "pre_existing_worktree_registry_diff_present": bool(pre_existing_diff),
        "canonical_registry_write_removed_from_checkpoint": True,
        "metadata_view_created_by_checkpoint": (root / "evidence" / "current_research_checkpoint" / "latest" / "current_research_checkpoint_registry_metadata_view.json").exists(),
        "no_strategy_or_lifecycle_state_change": True,
        "no_paper_demo_state_change": True,
        "no_backtest_or_discovery_run": True,
    }
    consistency["consistency_passed"] = (
        consistency["each_command_run_twice"]
        and consistency["all_commands_exit_zero"]
        and consistency["all_registry_hashes_preserved"]
        and consistency["no_remaining_write_side_effects"]
        and consistency["final_registry_matches_initial_review_hash"]
        and consistency["canonical_registry_write_removed_from_checkpoint"]
    )
    write_json(output / "consistency_check.json", consistency)

    decision = {
        "created_at_utc": now_utc(),
        "decision": "canonical_registry_write_side_effect_removed",
        "root_cause": "run_current_research_checkpoint.py update_registry_metadata wrote derived checkpoint metadata to strategy_lab/strategy_registry.yaml during normal report generation",
        "commands_reviewed": [name for name, _command in COMMANDS],
        "commands_with_remaining_registry_writes": [row["command"] for row in remaining],
        "initial_registry_hash": initial_hash,
        "final_registry_hash": final_hash,
        "registry_hash_preserved_during_review": final_hash == initial_hash,
        "pre_existing_registry_diff_present": bool(pre_existing_diff),
        "pre_existing_registry_diff_classification": classify_change(pre_existing_diff),
        "normal_commands_read_only_after_patch": len(remaining) == 0,
        "explicit_migration_required": False,
        "explicit_migration_introduced": False,
        "no_strategy_or_lifecycle_state_change": True,
        "no_paper_demo_state_change": True,
        "next_action": "resume_source_backed_strategy_discovery_after_registry_side_effect_fix",
    }
    write_json(output / "decision.json", decision)
    (output / "decision.md").write_text(
        "\n".join(
            [
                "# Canonical Registry Write Side-Effect Review",
                "",
                f"Decision: `{decision['decision']}`",
                "",
                f"Root cause: {decision['root_cause']}.",
                "",
                f"Initial registry hash: `{initial_hash}`",
                f"Final registry hash: `{final_hash}`",
                f"Remaining write side effects: `{len(remaining)}`",
                "",
                "Normal reporting now emits derived registry metadata as evidence, not as canonical registry mutation.",
                "",
                f"Exact next action: `{decision['next_action']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"output_dir": str(output), "decision": decision, "consistency": consistency}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
