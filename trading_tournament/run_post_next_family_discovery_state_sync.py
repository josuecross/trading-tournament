from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "tournament_checkpoints" / "post_next_family_discovery_state_sync" / "latest"
DISCOVERY_DIR = Path("evidence") / "parallel_research_discovery" / "next_family_after_indicator_validation" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"

CANDIDATE_ID = "mfv_equal_weight_trend_filter_v1"
SELECTED_FAMILY = "managed_futures_etf_wrapper"
CANDIDATE_OUTCOME = "discovery_reject"
PROMOTION_CANDIDATES_COUNT = 0
LIMITED_HISTORY_LABEL = "limited_history_common_window_short"
DECISION_LABEL = "weaker_than_active_references"
NEXT_ACTION = "pause_expansion_and_wait_for_manual_direction"

MANIFEST_FLAGS = {
    "state_sync_only": True,
    "strategy_discovery_run": False,
    "backtests_run": False,
    "new_performance_metrics_computed": False,
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
}

REQUIRED_FILES = [
    "post_discovery_state_sync_manifest.json",
    "post_discovery_state_sync_summary.md",
    "compact_state_update_report.md",
    "registry_roadmap_sync_report.md",
    "post_discovery_decision_summary.md",
    "forbidden_next_steps_after_reject.md",
    "manual_direction_options.md",
    "post_discovery_state_sync_next_action.md",
    "post_discovery_state_sync_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def validate_discovery_manifest(root: Path) -> list[str]:
    manifest = load_json(root / DISCOVERY_DIR / "next_family_discovery_manifest.json")
    mismatches: list[str] = []
    expected = {
        "candidate_id": CANDIDATE_ID,
        "selected_family": SELECTED_FAMILY,
        "candidate_outcome": CANDIDATE_OUTCOME,
        "promotion_candidates_count": PROMOTION_CANDIDATES_COUNT,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "decision_label": DECISION_LABEL,
        "next_action": NEXT_ACTION,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "provider_download": False,
        "intraday_data_used": False,
        "indicator_library_dependency_added": False,
        "real_money_recommendation": False,
        "intraday_research_remains_paused": True,
    }
    if not manifest:
        return ["next-family discovery manifest missing"]
    for key, value in expected.items():
        if manifest.get(key) != value:
            mismatches.append(f"discovery manifest {key} expected {value!r}, found {manifest.get(key)!r}")
    return mismatches


def compact_state_text(created_utc: str, discovery_path: Path) -> str:
    return f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `next_family_discovery_after_indicator_validation_completed`

Current next action: `{NEXT_ACTION}`

Selected family: `{SELECTED_FAMILY}`

Candidate evaluated: `{CANDIDATE_ID}`

Candidate outcome: `{CANDIDATE_OUTCOME}`

Promotion candidates count: `{PROMOTION_CANDIDATES_COUNT}`

Limited-history label: `{LIMITED_HISTORY_LABEL}`

Decision label: `{DECISION_LABEL}`

Discovery evidence: `{discovery_path.resolve()}`

## Active Accepted / Paper-Demo Observations

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.

## Benchmark Controls

- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Active combo, active VM, active DSR, SPY, QQQ, BIL, GLD, TLT, AGG, and static all-weather remain references/controls, not new promotions.

## Rejected / Paused State

- `mfv_equal_weight_trend_filter_v1` is a discovery reject.
- Promotion candidates count remains `0`.
- Exact rejected variants remain closed.
- Old managed-futures top1/top2 rows remain historical context only and are not replayed.
- Intraday research remains paused.

## Forbidden Actions

- No strategy discovery is authorized by this state sync.
- No backtest or new strategy performance metric computation is authorized by this state sync.
- No new candidates, variants, tuning, or rejected-row rescue.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path activation or order action.
- No real-money recommendation.
"""


def update_compact_state(root: Path, created_utc: str) -> bool:
    path = root / COMPACT_STATE_PATH
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    after = compact_state_text(created_utc, root / DISCOVERY_DIR)
    write_text(path, after)
    return before != after


def update_roadmap(root: Path, output: Path, created_utc: str) -> bool:
    path = root / ROADMAP_PATH
    before = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `next_family_discovery_after_indicator_validation_completed`
- Official current next action: `{NEXT_ACTION}`
- Post-discovery state-sync evidence: `{output.resolve()}`
- Next-family discovery evidence: `{(root / DISCOVERY_DIR).resolve()}`
- Selected family: `{SELECTED_FAMILY}`
- Candidate evaluated: `{CANDIDATE_ID}`
- Candidate outcome: `{CANDIDATE_OUTCOME}`
- Promotion candidates count: `{PROMOTION_CANDIDATES_COUNT}`
- Limited-history label: `{LIMITED_HISTORY_LABEL}`
- Decision label: `{DECISION_LABEL}`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed; old managed-futures top1/top2 rows remain historical context only.
- Intraday remains paused: `true`
- This sync did not run discovery, backtests, new metrics, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Post Next-Family Discovery State Sync

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- State-sync-only: `true`
- Candidate: `{CANDIDATE_ID}`
- Candidate outcome: `{CANDIDATE_OUTCOME}`
- Promotion candidates count: `{PROMOTION_CANDIDATES_COUNT}`
- Limited-history label: `{LIMITED_HISTORY_LABEL}`
- Next action: `{NEXT_ACTION}`
- No strategy discovery, backtest, new metric, provider download, intraday data, indicator dependency install, candidate_exhaustive, paper-forward, broker/live, or real-money action occurred in this sync.
"""
    after = replace_or_append_section(before, "## Compact Current State", compact)
    after = replace_or_append_section(after, "## Post Next-Family Discovery State Sync", section)
    write_text(path, after)
    return before != after


def update_registry_metadata(root: Path, output: Path, created_utc: str) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    before = deepcopy(registry.get("registry", {}))
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "post_next_family_discovery_state_sync_path": str(output.resolve()),
            "post_next_family_discovery_state_sync_status": "completed",
            "post_next_family_discovery_state_sync_created_utc": created_utc,
            "current_research_mode": "next_family_discovery_after_indicator_validation_completed",
            "current_next_action": NEXT_ACTION,
            "official_current_next_action": NEXT_ACTION,
            "next_action": NEXT_ACTION,
            "next_family_discovery_candidate_id": CANDIDATE_ID,
            "next_family_discovery_candidate_outcome": CANDIDATE_OUTCOME,
            "next_family_discovery_promotion_candidates_count": PROMOTION_CANDIDATES_COUNT,
            "next_family_discovery_limited_history_label": LIMITED_HISTORY_LABEL,
            "next_family_discovery_decision_label": DECISION_LABEL,
            "post_discovery_candidate_pipeline_empty": True,
            "state_sync_only": True,
            "state_sync_strategy_discovery_run": False,
            "state_sync_backtests_run": False,
            "state_sync_new_performance_metrics_computed": False,
            "state_sync_provider_download": False,
            "state_sync_intraday_data_used": False,
            "state_sync_candidate_exhaustive_run": False,
            "state_sync_paper_forward_review": False,
            "state_sync_paper_forward_activation": False,
            "state_sync_broker_orders_submitted": False,
            "state_sync_broker_orders_cancelled": False,
            "state_sync_live_orders": False,
            "state_sync_real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        }
    )
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    return before != metadata


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Post Next-Family Discovery State Sync

Created UTC: `{created_utc}`

Evidence path: `{output.resolve()}`

Candidate: `{CANDIDATE_ID}`

Candidate outcome: `{manifest['candidate_outcome']}`

Promotion candidates count: `{manifest['promotion_candidates_count']}`

Limited-history label: `{manifest['limited_history_label']}`

Next action: `{manifest['next_action']}`

This is a state synchronization checkpoint only. It did not run discovery, backtests, new strategy metrics, provider download, intraday data, candidate_exhaustive, paper-forward, broker/live actions, or real-money recommendation.
"""


def compact_update_report_md(compact_updated: bool) -> str:
    return f"""# Compact State Update Report

Compact state path: `{(ROOT / COMPACT_STATE_PATH).resolve()}`

Compact state updated: `{compact_updated}`

Recorded current research mode: `next_family_discovery_after_indicator_validation_completed`

Recorded current next action: `{NEXT_ACTION}`

The compact state now records the managed-futures ETF-wrapper candidate as a discovery reject with zero promotion candidates.
"""


def registry_roadmap_sync_report_md(registry_updated: bool, roadmap_updated: bool) -> str:
    return f"""# Registry Roadmap Sync Report

Registry metadata updated: `{registry_updated}`

Roadmap updated: `{roadmap_updated}`

Metadata-only update:

- Current next action: `{NEXT_ACTION}`
- Candidate outcome: `{CANDIDATE_OUTCOME}`
- Promotion candidates count: `{PROMOTION_CANDIDATES_COUNT}`
- State-sync-only flags recorded under `state_sync_*`

No strategy rows were intentionally changed.
"""


def decision_summary_md() -> str:
    return f"""# Post Discovery Decision Summary

Selected family: `{SELECTED_FAMILY}`

Candidate evaluated: `{CANDIDATE_ID}`

Candidate outcome: `{CANDIDATE_OUTCOME}`

Decision label: `{DECISION_LABEL}`

Promotion candidates count: `{PROMOTION_CANDIDATES_COUNT}`

Limited-history label: `{LIMITED_HISTORY_LABEL}`

Reason: the candidate had acceptable drawdown but lagged active combo, active VM, active DSR, SPY, QQQ, and static all-weather on same-window 180d median final equity. Diversification without objective progress was insufficient.
"""


def forbidden_next_steps_md() -> str:
    return """# Forbidden Next Steps After Reject

- Do not rescue or tune `mfv_equal_weight_trend_filter_v1`.
- Do not reopen old managed-futures top1/top2 variants.
- Do not run candidate_exhaustive.
- Do not activate paper-forward.
- Do not add indicator libraries.
- Do not download provider data.
- Do not use intraday data.
- Do not touch broker/live-order paths.
- Do not make real-money recommendations.
"""


def manual_options_md() -> str:
    return f"""# Manual Direction Options

The only current next action is `{NEXT_ACTION}`.

Reasonable manual choices later may include:

- Archive/pause expansion after the managed-futures reject.
- Reassess whether any family remains worth preregistration under the Research OS.
- Preserve active VM and active DSR as the active/frozen pair and static all-weather as benchmark/control only.

This packet does not authorize any of those follow-up actions.
"""


def next_action_md() -> str:
    return f"""# Post Discovery State Sync Next Action

Exact next action: `{NEXT_ACTION}`

Do not run the next action from this state-sync task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "state_sync_only": manifest["state_sync_only"] is True,
        "no_discovery": manifest["strategy_discovery_run"] is False,
        "no_backtests": manifest["backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
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
        "compact_state_updated": manifest["compact_state_updated"] is True,
        "candidate_outcome_is_reject": manifest["candidate_outcome"] == CANDIDATE_OUTCOME,
        "promotion_candidates_count_zero": manifest["promotion_candidates_count"] == 0,
        "next_action_is_pause": manifest["next_action"] == NEXT_ACTION,
        "required_files_exist": all((output / name).exists() for name in REQUIRED_FILES),
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def write_outputs(
    output: Path,
    created_utc: str,
    manifest: dict[str, Any],
    compact_updated: bool,
    registry_updated: bool,
    roadmap_updated: bool,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "post_discovery_state_sync_manifest.json", manifest)
    write_text(output / "post_discovery_state_sync_summary.md", summary_md(created_utc, output, manifest))
    write_text(output / "compact_state_update_report.md", compact_update_report_md(compact_updated))
    write_text(output / "registry_roadmap_sync_report.md", registry_roadmap_sync_report_md(registry_updated, roadmap_updated))
    write_text(output / "post_discovery_decision_summary.md", decision_summary_md())
    write_text(output / "forbidden_next_steps_after_reject.md", forbidden_next_steps_md())
    write_text(output / "manual_direction_options.md", manual_options_md())
    write_text(output / "post_discovery_state_sync_next_action.md", next_action_md())
    write_json(output / "post_discovery_state_sync_consistency_check.json", {"consistency_passed": False})


def run_post_next_family_discovery_state_sync(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    strategies_before = strategy_snapshot(root)
    mismatches = validate_discovery_manifest(root)
    if mismatches:
        raise RuntimeError("Cannot sync post-discovery state: " + "; ".join(mismatches))

    compact_updated = update_compact_state(root, created_utc)
    roadmap_updated = update_roadmap(root, output, created_utc)
    registry_updated = update_registry_metadata(root, output, created_utc)
    strategies_after = strategy_snapshot(root)

    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "compact_state_updated": compact_updated,
        "registry_metadata_updated": registry_updated,
        "roadmap_updated": roadmap_updated,
        "candidate_id": CANDIDATE_ID,
        "selected_family": SELECTED_FAMILY,
        "candidate_outcome": CANDIDATE_OUTCOME,
        "promotion_candidates_count": PROMOTION_CANDIDATES_COUNT,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "decision_label": DECISION_LABEL,
        "next_action": NEXT_ACTION,
    }
    if strategies_before != strategies_after:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True

    write_outputs(output, created_utc, manifest, compact_updated, registry_updated, roadmap_updated)
    consistency = consistency_check(manifest, output)
    write_json(output / "post_discovery_state_sync_consistency_check.json", consistency)
    write_json(output / "post_discovery_state_sync_manifest.json", manifest)
    return {
        "output_dir": str(output),
        "compact_state_updated": compact_updated,
        "candidate_outcome": CANDIDATE_OUTCOME,
        "promotion_candidates_count": PROMOTION_CANDIDATES_COUNT,
        "limited_history_label": LIMITED_HISTORY_LABEL,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


def main() -> None:
    print(json.dumps(run_post_next_family_discovery_state_sync(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
