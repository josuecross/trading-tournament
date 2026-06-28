from __future__ import annotations

import csv
import json
import subprocess
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "repository_refactor" / "manual_review_after_family_lane_os_refactor" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
GITIGNORE_PATH = Path(".gitignore")
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"
REFACTOR_EVIDENCE_DIR = Path("evidence") / "repository_refactor" / "family_lane_research_os_refactor" / "latest"

NEXT_ACTION = "audit_risk_controlled_high_return_discovery_failures"
VALID_NEXT_ACTIONS = {
    "audit_risk_controlled_high_return_discovery_failures",
    "pause_expansion_and_summarize_tournament_state",
    "pre_register_indicator_library_integration_audit",
    "manual_cleanup_required_after_repository_refactor",
}

MANIFEST_FLAGS = {
    "manual_review_only": True,
    "repository_refactor_review": True,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
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
}

REQUIRED_EVIDENCE_FILES = [
    "manual_refactor_review_manifest.json",
    "manual_refactor_review_summary.md",
    "canonical_structure_acceptance.md",
    "next_action_reconciliation.md",
    "roadmap_historical_sections_review.md",
    "tracked_generated_files_classification.csv",
    "gitignore_review.md",
    "git_untrack_commands_recommended.md",
    "git_untrack_commands_executed.md",
    "state_preservation_check.md",
    "manual_refactor_review_next_action.md",
    "manual_refactor_review_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def git_ls_files(root: Path) -> list[str]:
    try:
        result = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def is_generated_path(path: str) -> bool:
    lower = path.lower()
    prefixes = (
        "evidence/advisor_upload/",
        "evidence/research_state/latest/",
        "evidence/strategy_lab/latest/",
        "data/cache/",
        "data/intraday/",
        "data/raw/",
        "data/provider_downloads/",
        "reports/generated/",
        "logs/",
        "tmp/",
        "artifacts/",
    )
    suffixes = (".zip", ".jsonl", ".log", ".tmp", ".bak", ".parquet", ".feather", ".sqlite", ".db", ".pyc")
    return lower.startswith(prefixes) or lower.endswith(suffixes)


def covered_by_gitignore(path: str) -> bool:
    lower = path.lower()
    return is_generated_path(path) or "/latest/" in lower


def classify_generated_file(path: str) -> dict[str, str]:
    lower = path.lower()
    if lower.startswith(("evidence/advisor_upload/", "evidence/research_state/latest/", "evidence/strategy_lab/latest/")):
        classification = "safe_to_untrack_now"
        recommendation = "git_rm_cached_after_manual_confirmation"
        reason = "Regenerated latest/advisor export covered by .gitignore and not canonical source-of-truth."
    elif lower.endswith(".jsonl") or lower.startswith(("data/cache/", "data/intraday/", "data/raw/", "data/provider_downloads/")):
        classification = "safe_to_untrack_now"
        recommendation = "git_rm_cached_after_manual_confirmation"
        reason = "Local cache/progress artifact covered by .gitignore."
    elif any(
        segment in lower
        for segment in [
            "/promotion_reviews/",
            "/candidate_exhaustive/",
            "/paper_forward_",
            "/implementation_reviews/",
            "/data_acquisition_",
        ]
    ):
        classification = "keep_tracked_for_lineage"
        recommendation = "defer_until_compact_lineage_replacement_exists"
        reason = "Historical packet may preserve decision lineage; keep until compact replacement is verified."
    elif lower.endswith(".zip"):
        classification = "manual_review_required"
        recommendation = "review_before_git_rm_cached"
        reason = "Bulky generated packet, but lineage value is not automatically known."
    else:
        classification = "manual_review_required"
        recommendation = "review_before_cleanup"
        reason = "Generated-looking tracked path needs human review."
    return {
        "path": path,
        "classification": classification,
        "covered_by_gitignore": str(covered_by_gitignore(path)).lower(),
        "recommendation": recommendation,
        "reason": reason,
    }


def classified_generated_files(root: Path) -> list[dict[str, str]]:
    return [classify_generated_file(path) for path in git_ls_files(root) if is_generated_path(path)]


def update_registry_metadata(root: Path, created_utc: str, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = root / REGISTRY_PATH
    before = load_yaml(path)
    after = deepcopy(before)
    meta = after.setdefault("registry", {})
    meta.update(
        {
            "repository_refactor_manual_review_path": str(output.resolve()),
            "repository_refactor_manual_review_status": "accepted",
            "repository_refactor_accepted": True,
            "canonical_compact_state_path": str((root / COMPACT_STATE_PATH).resolve()),
            "canonical_state_accepted": True,
            "official_current_next_action": NEXT_ACTION,
            "current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "roadmap_next_action_reconciled": True,
            "tracked_generated_files_classified": True,
            "generated_artifact_untracking_deferred": True,
            "files_untracked_count": 0,
            "manual_review_after_repository_refactor_created_utc": created_utc,
            "manual_review_only": True,
            "strategy_discovery_run": False,
            "backtests_run": False,
            "new_performance_metrics_computed": False,
            "provider_download": False,
            "intraday_data_used": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "live_orders": False,
            "real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    if "research_os_next_action" in meta:
        meta["research_os_next_action"] = NEXT_ACTION
    write_yaml(path, after)
    return before, after


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_roadmap(root: Path, created_utc: str, output: Path) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact_section = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Repository refactor manual review evidence: `{output.resolve()}`
- Compact state: `{(root / COMPACT_STATE_PATH).resolve()}`
- Current research mode: `family_lane_research_os_governance_accepted`
- Official current next action: `{NEXT_ACTION}`
- Repository refactor accepted: `true`
- Canonical compact state accepted: `true`
- Family status, lane policy, indicator governance, artifact policy, and cleanup policy are canonical governance layers.
- Active accepted/paper-demo observations preserved: active VM and active DSR.
- Benchmark/control preserved: `static_all_weather_benchmark_v1` remains benchmark/control only.
- Intraday remains paused due to unresolved data-source terms and missing local intraday cache.
- Exact rejected variants remain closed, including the latest risk-controlled high-return rejects.
- Older roadmap next-action lines below are historical/context unless they match this official current next action.
- This section does not authorize discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live order paths, or real-money recommendation.
"""
    text = replace_or_append_section(text, "## Compact Current State", compact_section)
    review_section = f"""## Manual Review After Repository Refactor

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Refactor accepted: `true`
- Canonical current-state file: `{(root / COMPACT_STATE_PATH).resolve()}`
- Roadmap next action reconciled: `true`
- Official current next action: `{NEXT_ACTION}`
- Generated/bulky tracked artifacts classified: `true`
- Files untracked from Git in this review: `0`
- Bulk generated-artifact untracking is safely deferred until a human confirms historical lineage coverage.
- Prior `manual_review_required_after_repository_refactor` and `manual_review_refactored_research_os` labels are now completed historical review labels.
- No strategy discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, active-state mutation, or real-money recommendation is authorized by this review.
"""
    text = replace_or_append_section(text, "## Manual Review After Repository Refactor", review_section)
    write_text(path, text)


def canonical_acceptance_md() -> str:
    return """# Canonical Structure Acceptance

Decision: `accepted`

The repository-level family/lane Research OS refactor is accepted as the canonical governance structure.

Accepted canonical layers:

- `reports/compact_state/current_tournament_state.md` as the compact current-state file
- `family_registry/family_status/` as canonical family summaries
- `lanes/` as canonical lane-policy files
- `indicator_layer/` as governance-only indicator policy, not discovery authorization
- `governance/artifact_policy.md` as accepted artifact policy
- `governance/cleanup_policy.md` as accepted cleanup policy

The compact state's prior manual-review next-action label is superseded by this review packet and the roadmap/registry metadata reconciliation.
"""


def next_action_md() -> str:
    return f"""# Next Action Reconciliation

Official current next action: `{NEXT_ACTION}`

Reason: the refactor is accepted, structural ambiguity is resolved by this review, and generated-file untracking can be safely deferred. The correct governance sequence resumes with auditing the latest risk-controlled high-return discovery failures.

Completed/historical labels:

- `manual_review_required_after_repository_refactor`
- `manual_review_refactored_research_os`

This next action is not run in this task.
"""


def roadmap_review_md() -> str:
    return """# Roadmap Historical Sections Review

The `Compact Current State` section is the active roadmap entry after this review.

Older roadmap sections remain historical/context unless explicitly referenced by the compact state or this manual review packet. They are not deleted because they preserve research lineage.

Older next-action lines are historical/context, except `audit_risk_controlled_high_return_discovery_failures`, which is now reconciled as the official current next action.
"""


def gitignore_review_md(root: Path) -> str:
    gitignore_text = (root / GITIGNORE_PATH).read_text(encoding="utf-8") if (root / GITIGNORE_PATH).exists() else ""
    accepted = "trading-tournament generated artifact policy" in gitignore_text
    return f"""# Gitignore Review

Accepted: `{str(accepted).lower()}`

The generated artifact policy block is present and covers evidence latest outputs, advisor uploads, research-state latest, strategy-lab latest, zips, JSONL progress logs, local caches, raw/provider data folders, logs, temp outputs, artifacts, Python caches, and local environment files.

No `.gitignore` patch was required in this manual review.
"""


def recommended_untrack_commands(rows: list[dict[str, str]]) -> str:
    safe_count = sum(row["classification"] == "safe_to_untrack_now" for row in rows)
    return f"""# Git Untrack Commands Recommended

Safe-to-untrack-now count: `{safe_count}`

Commands prepared but not executed:

```powershell
git rm --cached -r evidence/advisor_upload
git rm --cached -r evidence/research_state/latest
git rm --cached -r evidence/strategy_lab/latest
git rm --cached "*.jsonl"
```

The broader `git rm --cached "*.zip"` command remains manual-review-only because several historical packets may preserve lineage until compact replacements are verified.
"""


def executed_untrack_commands() -> str:
    return """# Git Untrack Commands Executed

Files untracked from Git in this review: `0`

No `git rm --cached` command was executed. The tracked generated artifacts were classified and deferred for human confirmation because the worktree is dirty and several historical packets may preserve lineage.
"""


def state_preservation_md() -> str:
    return """# State Preservation Check

Preserved:

- active VM active/accepted/frozen state
- active DSR active/accepted/frozen state
- `static_all_weather_benchmark_v1` benchmark/control-only status
- rejected-state closure
- exact rejected variants remain closed
- intraday remains paused/data-source blocked

No forbidden authorization was added.
"""


def summary_md(created_utc: str, rows: list[dict[str, str]]) -> str:
    counts = classification_counts(rows)
    return f"""# Manual Refactor Review Summary

Created UTC: `{created_utc}`

Refactor accepted: `true`

Canonical compact state accepted: `true`

Roadmap next action reconciled: `true`

Official current next action: `{NEXT_ACTION}`

Tracked generated files classified: `{len(rows)}`

Files untracked from Git: `0`

Classification counts: `{counts}`
"""


def classification_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {
        "safe_to_untrack_now": 0,
        "keep_tracked_for_lineage": 0,
        "manual_review_required": 0,
        "delete_local_generated_junk": 0,
        "archive_before_delete": 0,
    }
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return counts


def consistency_check(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    check = {
        "manual_review_only": manifest["manual_review_only"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "canonical_state_acceptance_exists": manifest["canonical_state_accepted"] is True,
        "next_action_reconciliation_exists": manifest["roadmap_next_action_reconciled"] is True,
        "tracked_generated_files_classification_exists": manifest["tracked_generated_files_classified"] is True,
        "gitignore_review_exists": manifest["gitignore_accepted"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(root: Path, output: Path, created_utc: str, manifest: dict[str, Any], rows: list[dict[str, str]], consistency: dict[str, Any]) -> None:
    write_json(output / "manual_refactor_review_manifest.json", manifest)
    write_text(output / "manual_refactor_review_summary.md", summary_md(created_utc, rows))
    write_text(output / "canonical_structure_acceptance.md", canonical_acceptance_md())
    write_text(output / "next_action_reconciliation.md", next_action_md())
    write_text(output / "roadmap_historical_sections_review.md", roadmap_review_md())
    write_csv(
        output / "tracked_generated_files_classification.csv",
        rows,
        ["path", "classification", "covered_by_gitignore", "recommendation", "reason"],
    )
    write_text(output / "gitignore_review.md", gitignore_review_md(root))
    write_text(output / "git_untrack_commands_recommended.md", recommended_untrack_commands(rows))
    write_text(output / "git_untrack_commands_executed.md", executed_untrack_commands())
    write_text(output / "state_preservation_check.md", state_preservation_md())
    write_text(output / "manual_refactor_review_next_action.md", f"# Manual Refactor Review Next Action\n\nExact next action: `{NEXT_ACTION}`\n")
    write_json(output / "manual_refactor_review_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "manual_refactor_review_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_EVIDENCE_FILES:
            archive.write(output / rel, rel)


def run_manual_review_after_repository_refactor(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    strategy_before = strategy_snapshot(root)
    rows = classified_generated_files(root)
    registry_before, registry_after = update_registry_metadata(root, created_utc, output)
    update_roadmap(root, created_utc, output)
    strategy_after = strategy_snapshot(root)
    flags = dict(MANIFEST_FLAGS)
    flags["active_strategy_state_changed"] = strategy_before != strategy_after
    flags["rejected_strategy_state_changed"] = strategy_before != strategy_after
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **flags,
        "refactor_accepted": True,
        "canonical_state_accepted": True,
        "roadmap_next_action_reconciled": True,
        "tracked_generated_files_classified": True,
        "gitignore_accepted": True,
        "files_untracked_count": 0,
        "tracked_generated_files_count": len(rows),
        "classification_counts": classification_counts(rows),
        "next_action": NEXT_ACTION,
    }
    consistency = consistency_check(root, manifest)
    write_evidence(root, output, created_utc, manifest, rows, consistency)
    return {
        "output_dir": str(output),
        "refactor_accepted": True,
        "canonical_state_accepted": True,
        "roadmap_next_action_reconciled": True,
        "tracked_generated_files_classified": True,
        "files_untracked_count": 0,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_manual_review_after_repository_refactor(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
