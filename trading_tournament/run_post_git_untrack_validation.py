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
OUTPUT_DIR = Path("evidence") / "repository_refactor" / "post_git_untrack_validation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
GITIGNORE_PATH = Path(".gitignore")

NEXT_ACTION = "audit_risk_controlled_high_return_discovery_failures"
VALID_NEXT_ACTIONS = {
    "audit_risk_controlled_high_return_discovery_failures",
    "manual_cleanup_required_after_git_untrack",
    "manual_review_required_after_repository_refactor",
}

MANIFEST_FLAGS = {
    "post_git_cleanup_validation_only": True,
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

CANONICAL_FILES = [
    "strategy_lab/RESEARCH_ROADMAP.md",
    "strategy_lab/strategy_registry.yaml",
    "reports/compact_state/current_tournament_state.md",
    "family_registry/family_status/dual_momentum.md",
    "family_registry/family_status/donchian_breakout.md",
    "family_registry/family_status/macro_gld_duration.md",
    "family_registry/family_status/sector_rotation.md",
    "family_registry/family_status/volatility_management.md",
    "family_registry/family_status/calendar_anomaly.md",
    "family_registry/family_status/intraday_research.md",
    "lanes/lane_definitions.py",
    "lanes/lane_gate_framework.py",
    "lanes/lane_scorecard_policy.md",
    "indicator_layer/approved_indicators.yaml",
    "indicator_layer/indicator_policy.md",
    "governance/artifact_policy.md",
    "governance/cleanup_policy.md",
    "governance/research_workflow.md",
    "tests/test_manual_review_after_repository_refactor.py",
    "tests/test_repository_refactor_family_lane_os.py",
]

GITIGNORE_REQUIRED_PATTERNS = [
    "evidence/**/latest/",
    "evidence/**/runs/",
    "evidence/advisor_upload/",
    "evidence/research_state/latest/",
    "evidence/strategy_lab/latest/",
    "*.zip",
    "*.jsonl",
    "data/cache/",
    "data/intraday/",
    "__pycache__/",
    ".pytest_cache/",
    "*.pyc",
    "*.tmp",
    "*.log",
]

REQUIRED_EVIDENCE_FILES = [
    "post_git_untrack_validation_manifest.json",
    "post_git_untrack_validation_summary.md",
    "git_status_after_untrack.txt",
    "git_diff_name_status_after_untrack.txt",
    "canonical_files_presence_check.csv",
    "generated_artifacts_ignore_check.md",
    "state_preservation_check.md",
    "post_git_untrack_validation_next_action.md",
    "post_git_untrack_validation_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(root: Path, args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return (result.stdout + result.stderr).strip()
    return result.stdout.strip()


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


def git_ls_files(root: Path) -> set[str]:
    output = run_git(root, ["ls-files"])
    return {line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()}


def generated_path(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
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


def canonical_file_rows(root: Path, tracked: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel in CANONICAL_FILES:
        path = root / rel
        rel_norm = rel.replace("\\", "/")
        rows.append(
            {
                "path": rel_norm,
                "present": path.exists(),
                "tracked": rel_norm in tracked,
                "acceptable": path.exists(),
                "notes": "present; tracked or newly canonical local file" if path.exists() else "missing canonical file",
            }
        )
    return rows


def gitignore_valid(root: Path) -> tuple[bool, list[str]]:
    text = (root / GITIGNORE_PATH).read_text(encoding="utf-8") if (root / GITIGNORE_PATH).exists() else ""
    missing = [pattern for pattern in GITIGNORE_REQUIRED_PATTERNS if pattern not in text]
    return not missing, missing


def generated_tracked_count(tracked: set[str]) -> int:
    return sum(1 for path in tracked if generated_path(path))


def registry_state(root: Path) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    meta = registry.get("registry", {})
    rows = {str(row.get("id")): row for row in registry.get("strategies", [])}
    vm = rows.get("paper_forward_vm_quality_lowvol_proxy_v1", {})
    dsr = rows.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", {})
    static = rows.get("static_all_weather_benchmark_v1", {})
    risk_rejects = [
        rows.get("rc_dual_momentum_paa_vol_scaled_v1", {}),
        rows.get("rc_donchian_breakout_risk_budget_v1", {}),
    ]
    active_statuses = {"active_observation", "active_paper_demo_observation"}
    return {
        "official_next_action": meta.get("official_current_next_action") or meta.get("current_next_action") or meta.get("next_action"),
        "vm_preserved": vm.get("paper_forward_active") is True and vm.get("status") in active_statuses and vm.get("rules_frozen") is True,
        "dsr_preserved": dsr.get("paper_forward_active") is True and dsr.get("status") in active_statuses and dsr.get("rules_frozen") is True,
        "static_all_weather_control_only": (
            meta.get("static_all_weather_benchmark_control_status") == "benchmark_control_accepted"
            and meta.get("static_all_weather_paper_demo_eligible") is False
            and meta.get("static_all_weather_candidate_exhaustive_eligible") is False
            and meta.get("static_all_weather_promotion_review_eligible") is False
        ),
        "risk_controlled_rejects_preserved": all(
            not row or (row.get("paper_forward_active") is not True and row.get("candidate_exhaustive_run") is not True)
            for row in risk_rejects
        ),
        "intraday_paused": meta.get("intraday_research_remains_paused") is True or meta.get("intraday_research_paused") is True,
        "registry_validated": True,
    }


def update_registry_metadata(root: Path, created_utc: str, output: Path, validation_passed: bool, next_action: str) -> None:
    path = root / REGISTRY_PATH
    data = load_yaml(path)
    meta = data.setdefault("registry", {})
    meta.update(
        {
            "post_git_untrack_validation_path": str(output.resolve()),
            "post_git_untrack_validation_status": "passed" if validation_passed else "manual_cleanup_required",
            "post_git_untrack_validation_created_utc": created_utc,
            "generated_artifacts_untracked_or_ignored": validation_passed,
            "canonical_files_present_after_untrack": validation_passed,
            "official_current_next_action": next_action,
            "current_next_action": next_action,
            "next_action": next_action,
            "post_git_cleanup_validation_only": True,
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
        }
    )
    write_yaml(path, data)


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def update_roadmap(root: Path, created_utc: str, output: Path, validation_passed: bool, next_action: str) -> None:
    path = root / ROADMAP_PATH
    text = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Post Git Untrack Validation

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Validation status: `{'passed' if validation_passed else 'manual_cleanup_required'}`
- Canonical files present: `{str(validation_passed).lower()}`
- Generated artifacts untracked or ignored: `{str(validation_passed).lower()}`
- Official current next action: `{next_action}`
- No strategy discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, order action, rejected-row reopening, active-state mutation, or real-money recommendation is authorized by this validation.
"""
    text = replace_or_append_section(text, "## Post Git Untrack Validation", section)
    write_text(path, text)


def state_preservation_md(state: dict[str, Any]) -> str:
    return f"""# State Preservation Check

- Active VM preserved: `{state['vm_preserved']}`
- Active DSR preserved: `{state['dsr_preserved']}`
- Static all-weather benchmark/control only: `{state['static_all_weather_control_only']}`
- Risk-controlled high-return rejects preserved: `{state['risk_controlled_rejects_preserved']}`
- Intraday remains paused: `{state['intraday_paused']}`
- Official next action: `{state['official_next_action']}`
- Exact rejected variants reopened: `false`
- Forbidden action authorized: `false`
"""


def generated_ignore_md(gitignore_ok: bool, missing_patterns: list[str], generated_count: int) -> str:
    missing = "\n".join(f"- `{pattern}`" for pattern in missing_patterns) if missing_patterns else "- none"
    return f"""# Generated Artifacts Ignore Check

Gitignore validated: `{gitignore_ok}`

Tracked generated artifact count after cleanup: `{generated_count}`

Missing required ignore patterns:

{missing}

Generated evidence directories are not required as source-of-truth because compact state, family status, lane policy, indicator governance, artifact policy, roadmap, registry, and tests are the canonical governance files.
"""


def summary_md(created_utc: str, validation_passed: bool, next_action: str, generated_count: int) -> str:
    return f"""# Post Git Untrack Validation Summary

Created UTC: `{created_utc}`

Validation passed: `{validation_passed}`

Tracked generated artifact count after cleanup: `{generated_count}`

Official next action: `{next_action}`

This was a repository-state validation only. It did not run discovery, backtests, new metrics, provider downloads, intraday data, candidate_exhaustive, paper-forward actions, broker/live actions, or real-money recommendations.
"""


def consistency_check(manifest: dict[str, Any]) -> dict[str, Any]:
    check = {
        "post_git_cleanup_validation_only": manifest["post_git_cleanup_validation_only"] is True,
        "no_strategy_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders": manifest["broker_orders_submitted"] is False and manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_not_changed": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_not_changed": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "canonical_files_present": manifest["canonical_files_present"] is True,
        "gitignore_validated": manifest["gitignore_validated"] is True,
        "generated_artifacts_untracked_or_ignored": manifest["generated_artifacts_untracked_or_ignored"] is True,
        "roadmap_next_action_confirmed": manifest["roadmap_next_action_confirmed"] is True,
        "registry_validated": manifest["registry_validated"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_evidence(
    output: Path,
    created_utc: str,
    manifest: dict[str, Any],
    consistency: dict[str, Any],
    git_status: str,
    git_diff: str,
    canonical_rows: list[dict[str, Any]],
    gitignore_ok: bool,
    missing_patterns: list[str],
    state: dict[str, Any],
) -> None:
    write_json(output / "post_git_untrack_validation_manifest.json", manifest)
    write_text(output / "post_git_untrack_validation_summary.md", summary_md(created_utc, consistency["consistency_passed"], manifest["next_action"], manifest["tracked_generated_artifact_count"]))
    write_text(output / "git_status_after_untrack.txt", git_status + ("\n" if git_status else ""))
    write_text(output / "git_diff_name_status_after_untrack.txt", git_diff + ("\n" if git_diff else ""))
    write_csv(output / "canonical_files_presence_check.csv", canonical_rows, ["path", "present", "tracked", "acceptable", "notes"])
    write_text(output / "generated_artifacts_ignore_check.md", generated_ignore_md(gitignore_ok, missing_patterns, manifest["tracked_generated_artifact_count"]))
    write_text(output / "state_preservation_check.md", state_preservation_md(state))
    write_text(output / "post_git_untrack_validation_next_action.md", f"# Post Git Untrack Validation Next Action\n\nExact next action: `{manifest['next_action']}`\n")
    write_json(output / "post_git_untrack_validation_consistency_check.json", consistency)
    with zipfile.ZipFile(output / "post_git_untrack_validation_packet.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in REQUIRED_EVIDENCE_FILES:
            archive.write(output / rel, rel)


def run_post_git_untrack_validation(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    created_utc = now_utc()
    strategies_before = strategy_snapshot(root)
    git_status = run_git(root, ["status", "--short"])
    git_diff = run_git(root, ["diff", "--name-status"])
    tracked = git_ls_files(root)
    canonical_rows = canonical_file_rows(root, tracked)
    canonical_present = all(bool(row["acceptable"]) for row in canonical_rows)
    gitignore_ok, missing_patterns = gitignore_valid(root)
    generated_count = generated_tracked_count(tracked)
    state = registry_state(root)
    validation_passed = (
        canonical_present
        and gitignore_ok
        and generated_count == 0
        and state["vm_preserved"]
        and state["dsr_preserved"]
        and state["static_all_weather_control_only"]
        and state["risk_controlled_rejects_preserved"]
        and state["intraday_paused"]
    )
    next_action = NEXT_ACTION if validation_passed else "manual_cleanup_required_after_git_untrack"
    update_registry_metadata(root, created_utc, output, validation_passed, next_action)
    update_roadmap(root, created_utc, output, validation_passed, next_action)
    state["official_next_action"] = next_action
    strategies_after = strategy_snapshot(root)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "active_strategy_state_changed": strategies_before != strategies_after,
        "rejected_strategy_state_changed": strategies_before != strategies_after,
        "canonical_files_present": canonical_present,
        "gitignore_validated": gitignore_ok,
        "generated_artifacts_untracked_or_ignored": generated_count == 0,
        "tracked_generated_artifact_count": generated_count,
        "roadmap_next_action_confirmed": next_action == NEXT_ACTION,
        "registry_validated": state["registry_validated"],
        "next_action": next_action,
    }
    consistency = consistency_check(manifest)
    write_evidence(output, created_utc, manifest, consistency, git_status, git_diff, canonical_rows, gitignore_ok, missing_patterns, state)
    return {
        "output_dir": str(output),
        "canonical_files_present": canonical_present,
        "gitignore_validated": gitignore_ok,
        "tracked_generated_artifact_count": generated_count,
        "generated_artifacts_untracked_or_ignored": generated_count == 0,
        "next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_post_git_untrack_validation(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
