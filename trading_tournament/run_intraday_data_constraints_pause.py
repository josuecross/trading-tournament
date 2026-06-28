from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "intraday_readiness" / "intraday_data_constraints_pause" / "latest"
READINESS_AUDIT_DIR = Path("evidence") / "intraday_readiness" / "intraday_research_readiness_audit" / "latest"
BLOCKER_FIX_DIR = Path("evidence") / "intraday_readiness" / "fix_intraday_readiness_blockers" / "latest"
DATA_SOURCE_REVIEW_DIR = Path("evidence") / "intraday_readiness" / "manual_intraday_data_source_review" / "latest"
THIRD_FAILURE_DIR = Path("evidence") / "tournament_failure_synthesis" / "third_expansion_failure_audit" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

NEXT_ACTION = "pre_register_risk_controlled_high_return_family_review"

MANIFEST_FLAGS = {
    "governance_checkpoint_only": True,
    "intraday_research_paused": True,
    "approved_intraday_data_source_found": False,
    "local_intraday_data_present": False,
    "manual_terms_review_required": True,
    "intraday_backtests_run": False,
    "new_discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "provider_api_called": False,
    "intraday_cache_bootstrapped": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "strategy_rules_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
}

REQUIRED_FILES = [
    "intraday_data_constraints_pause_manifest.json",
    "intraday_data_constraints_pause_summary.md",
    "intraday_source_blocker_status.md",
    "intraday_preserved_infrastructure.md",
    "intraday_forbidden_next_steps.md",
    "non_intraday_research_pivot_recommendation.md",
    "intraday_data_constraints_pause_next_action.md",
    "intraday_data_constraints_pause_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def strategy_state_map(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in strategies:
        row_id = row.get("id") or row.get("strategy_id")
        if not row_id:
            continue
        state[row_id] = {
            "status": row.get("status") or row.get("current_status"),
            "current_status": row.get("current_status"),
            "paper_forward_active": row.get("paper_forward_active"),
            "candidate_exhaustive_run": row.get("candidate_exhaustive_run"),
            "candidate_exhaustive_recommended": row.get("candidate_exhaustive_recommended"),
            "promotion_review_required": row.get("promotion_review_required"),
        }
    return state


def prior_evidence(root: Path) -> dict[str, Any]:
    readiness = load_json(root / READINESS_AUDIT_DIR / "intraday_readiness_manifest.json")
    blocker_fix = load_json(root / BLOCKER_FIX_DIR / "intraday_blocker_fix_manifest.json")
    source_review = load_json(root / DATA_SOURCE_REVIEW_DIR / "intraday_data_source_review_manifest.json")
    third_failure = load_json(root / THIRD_FAILURE_DIR / "third_expansion_failure_audit_manifest.json")
    return {
        "readiness_audit_found": bool(readiness),
        "readiness_verdict": readiness.get("readiness_verdict"),
        "blocker_fix_found": bool(blocker_fix),
        "blockers_fixed_count": blocker_fix.get("blockers_fixed_count"),
        "blockers_partially_fixed_count": blocker_fix.get("blockers_partially_fixed_count"),
        "critical_blockers_remaining_count": blocker_fix.get("critical_blockers_remaining_count"),
        "contracts_added": [
            "intraday_data_schema",
            "intraday_cache",
            "session_timing",
            "fill_slippage_no_fill",
            "risk_engine",
            "kill_switch",
            "event_logging",
            "candidate_readiness_gates",
        ],
        "data_source_review_found": bool(source_review),
        "source_candidate_count": source_review.get("source_candidate_count"),
        "approved_intraday_data_source_found": source_review.get("approved_intraday_data_source_found"),
        "manual_terms_review_required": source_review.get("manual_terms_review_required"),
        "local_intraday_data_present": source_review.get("local_intraday_data_present"),
        "recommended_data_source_path": source_review.get("recommended_data_source_path"),
        "third_expansion_failure_audit_found": bool(third_failure),
        "exact_rejected_variants_closed": third_failure.get("exact_rejected_variants_closed"),
        "daily_weekly_expansion_should_pause": third_failure.get("daily_weekly_expansion_should_pause"),
        "families_remaining_open_count": third_failure.get("families_remaining_open_count"),
    }


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Intraday Data Constraints Pause

Created UTC: `{created_utc}`

Evidence path: `{output}`

Intraday research paused: `{manifest["intraday_research_paused"]}`

Next action: `{manifest["next_action"]}`

## Decision

Intraday research is paused because approved source terms and local 1Min/5Min SPY/QQQ data are still missing. The blocker is now a human/source-terms decision, not an engineering task for Codex.

The intraday infrastructure contracts remain preserved for future use, but they do not authorize data download, cache bootstrap, strategy testing, candidate validation, paper-forward activation, broker integration, live orders, or real-money recommendations.
"""


def source_blocker_md(prior: dict[str, Any]) -> str:
    return f"""# Intraday Source Blocker Status

Manual data-source review found candidate paths but no approved intraday source.

- Candidate source count: `{prior.get("source_candidate_count")}`
- Approved intraday data source found: `{prior.get("approved_intraday_data_source_found")}`
- Manual terms review required: `{prior.get("manual_terms_review_required")}`
- Local intraday data present: `{prior.get("local_intraday_data_present")}`
- Recommended data-source path: `{prior.get("recommended_data_source_path")}`

Remaining blockers:

- data-source terms/licensing remain unresolved,
- reproducible SPY/QQQ 1Min or 5Min history is not approved,
- no local intraday cache exists,
- no controlled intraday cache bootstrap is authorized.
"""


def preserved_infrastructure_md() -> str:
    return """# Preserved Intraday Infrastructure

The following research-only infrastructure remains preserved:

- intraday data schema contract,
- intraday cache contract,
- session/timing contract,
- fill/slippage/no-fill model interface,
- intraday risk engine contract,
- kill-switch contract,
- event logging contract,
- candidate readiness gates.

These pieces are reusable if a source is later approved, but they do not make ORB, gap-fade, VWAP, or any other intraday candidate research-ready today.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Intraday Next Steps

Do not proceed to:

- intraday provider download,
- provider API calls,
- intraday cache bootstrap,
- ORB, gap-fade, VWAP, or other intraday strategy tests,
- daily/weekly strategy tests in this checkpoint,
- new performance metrics,
- strategy discovery,
- candidate_exhaustive,
- paper-forward review or activation,
- broker order submission or cancellation,
- live-order paths,
- real-money recommendations.

Exact rejected daily/weekly variants also remain closed.
"""


def pivot_md() -> str:
    return f"""# Non-Intraday Research Pivot Recommendation

Recommended non-intraday pivot: `{NEXT_ACTION}`

Rationale:

Recent daily/weekly research found high-return behavior in families such as dual momentum and Donchian-style breakouts, but rejected rows failed drawdown or risk-buffer gates. The exact rejected variants must remain closed. The only acceptable continuation is a fresh pre-registration focused on new risk-control hypotheses for high-return families, before any future testing.

This is a recommendation to pre-register, not to run discovery.
"""


def next_action_md() -> str:
    return f"""# Intraday Data Constraints Pause Next Action

`{NEXT_ACTION}`

Do not run the next action in this task. This checkpoint does not authorize discovery, backtesting, new performance metrics, provider downloads, cache bootstrap, candidate_exhaustive, paper-forward activation, broker orders, live orders, or real-money recommendations.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "intraday_data_constraints_pause_path": str(output),
                "intraday_data_constraints_pause_status": "completed",
                "intraday_data_constraints_pause_created_utc": created_utc,
                "intraday_research_paused": True,
                "intraday_pause_reason": "unresolved_data_source_terms_and_missing_local_intraday_data",
                "approved_intraday_data_source_found": False,
                "local_intraday_data_present": False,
                "manual_terms_review_required": True,
                "recommended_non_intraday_pivot": NEXT_ACTION,
                "current_next_action": NEXT_ACTION,
                "next_action": NEXT_ACTION,
                **MANIFEST_FLAGS,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    marker = "## Intraday Data Constraints Pause"
    section = f"""## Intraday Data Constraints Pause

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Governance checkpoint only: `true`
- Intraday research paused: `true`
- Approved intraday data source found: `false`
- Local intraday data present: `false`
- Manual terms review required: `true`
- Preserved infrastructure: intraday data schema, cache contract, session timing, fill/slippage/no-fill, risk engine, kill switch, event logging, and candidate readiness gates.
- Recommended non-intraday pivot: `{NEXT_ACTION}`
- No backtest, discovery, new performance metric, provider download, provider API call, cache bootstrap, candidate_exhaustive, paper-forward action, broker order, live order, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "intraday_data_constraints_pause_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    check = {
        "governance_checkpoint_only": manifest["governance_checkpoint_only"] is True,
        "intraday_research_paused": manifest["intraday_research_paused"] is True,
        "no_intraday_backtests": manifest["intraday_backtests_run"] is False,
        "no_new_discovery": manifest["new_discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_provider_api_call": manifest["provider_api_called"] is False,
        "no_intraday_cache_bootstrap": manifest["intraday_cache_bootstrapped"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "preserved_infrastructure_file_exists": required_present["intraday_preserved_infrastructure.md"],
        "forbidden_next_steps_file_exists": required_present["intraday_forbidden_next_steps.md"],
        "pivot_recommendation_exists": required_present["non_intraday_research_pivot_recommendation.md"],
        "next_action_is_pivot": manifest["next_action"] == NEXT_ACTION,
        "manifest_flags_match_strict_scope": flags_match,
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_intraday_data_constraints_pause(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    prior = prior_evidence(root)
    manifest: dict[str, Any] = {
        "artifact": "intraday_data_constraints_pause",
        "created_utc": created_utc,
        "output_dir": str(output),
        "prior_evidence": prior,
        **MANIFEST_FLAGS,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "intraday_data_constraints_pause_manifest.json", manifest)
    (output / "intraday_data_constraints_pause_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "intraday_source_blocker_status.md").write_text(source_blocker_md(prior), encoding="utf-8")
    (output / "intraday_preserved_infrastructure.md").write_text(preserved_infrastructure_md(), encoding="utf-8")
    (output / "intraday_forbidden_next_steps.md").write_text(forbidden_next_steps_md(), encoding="utf-8")
    (output / "non_intraday_research_pivot_recommendation.md").write_text(pivot_md(), encoding="utf-8")
    (output / "intraday_data_constraints_pause_next_action.md").write_text(next_action_md(), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "intraday_data_constraints_pause_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "intraday_data_constraints_pause_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_intraday_data_constraints_pause(ROOT)
    manifest = result["manifest"]
    check = result["consistency_check"]
    print(f"intraday data constraints pause written: {result['output_dir']}")
    print(f"intraday_research_paused: {manifest['intraday_research_paused']}")
    print(f"approved_intraday_data_source_found: {manifest['approved_intraday_data_source_found']}")
    print(f"local_intraday_data_present: {manifest['local_intraday_data_present']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
