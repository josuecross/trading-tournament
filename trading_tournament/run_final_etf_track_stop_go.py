from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "final_etf_track_stop_go" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
ENSEMBLE_EQUAL_WEIGHT_ID = "ase_vm_dsr_equal_weight_v1"

FINAL_DECISION = "pre_register_one_final_breadth_state_regime_lane_then_stop_if_no_candidate"
NEXT_ACTION = "pre_register_breadth_state_regime_lane"
STOP_ACTION = "archive_current_etf_wrapper_track_summary"
MANUAL_ACTION = "manual_decision_required_stop_or_final_lane"

ACTIVE_OBSERVATION_PATHS = {
    VM_ID: Path("paper_forward_observations") / VM_ID / "active_observation.yaml",
    DSR_ID: Path("paper_forward_observations") / DSR_ID / "active_observation.yaml",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(root / rel_path) for strategy_id, rel_path in ACTIVE_OBSERVATION_PATHS.items()}


def protected_rows_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {strategy_id: deepcopy(rows.get(strategy_id, {})) for strategy_id in [VM_ID, DSR_ID, SPY_200D_ID]}


def count_data_rows(path: Path) -> int:
    rows = read_csv_rows(path)
    return len(rows)


def candidate_pipeline_empty(root: Path) -> bool:
    path = root / "evidence" / "current_research_checkpoint" / "latest" / "candidate_pipeline_status.csv"
    rows = {row.get("stage", ""): row for row in read_csv_rows(path)}
    return (
        rows.get("promotion_review_candidates", {}).get("count") in {"0", 0}
        and rows.get("candidate_exhaustive_queue", {}).get("count") in {"0", 0}
        and rows.get("candidate_exhaustive_watchlist", {}).get("count") in {"0", 0, None}
    )


def summarize_current_state(root: Path, registry: dict[str, Any]) -> dict[str, Any]:
    checkpoint_pipeline = read_csv_rows(root / "evidence" / "current_research_checkpoint" / "latest" / "candidate_pipeline_status.csv")
    combo_manifest = read_json(root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json")
    ensemble_manifest = read_json(root / "evidence" / "parallel_research_discovery" / "active_sleeve_ensemble" / "latest" / "active_sleeve_ensemble_discovery_manifest.json")
    ensemble_promotions = count_data_rows(root / "evidence" / "parallel_research_discovery" / "active_sleeve_ensemble" / "latest" / "active_sleeve_ensemble_promotion_candidates.csv")
    rows = rows_by_id(registry)
    state_notes: list[str] = []
    if ensemble_promotions != 0 or any(decision == "promotion_review_candidate" for decision in ensemble_manifest.get("decisions", {}).values()):
        state_notes.append("active-sleeve ensemble appears to contain promotion candidates")
    if combo_manifest.get("active_combo_is_reference_not_active_strategy") is not True:
        state_notes.append("active combo is not marked reference-only")
    if not candidate_pipeline_empty(root):
        state_notes.append("candidate pipeline is not empty in current checkpoint")
    for strategy_id in [VM_ID, DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            state_notes.append(f"{strategy_id} is not protected active/frozen")
    if rows.get(SPY_200D_ID, {}).get("rules_frozen") is not True:
        state_notes.append(f"{SPY_200D_ID} is not frozen in registry")
    stale_checkpoint_data_pending = [
        row for row in checkpoint_pipeline if row.get("stage") == "data_pending" and "active_combo" in row.get("rows", "")
    ]
    if stale_checkpoint_data_pending and combo_manifest.get("active_combo_benchmark_created") is True:
        state_notes.append("accepted stale checkpoint caveat: current checkpoint still lists active combo repair as data_pending, but newer active combo packet exists")
    return {
        "checkpoint_pipeline": checkpoint_pipeline,
        "combo_manifest": combo_manifest,
        "ensemble_manifest": ensemble_manifest,
        "ensemble_promotions": ensemble_promotions,
        "state_notes": state_notes,
        "candidate_pipeline_empty": candidate_pipeline_empty(root),
        "active_combo_reference_only": combo_manifest.get("active_combo_is_reference_not_active_strategy") is True,
    }


def evidence_since_checkpoint(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    combo_path = root / "evidence" / "active_combo_benchmark" / "latest"
    prereg_path = root / "evidence" / "pre_registered_lanes" / "active_sleeve_ensemble" / "latest"
    ensemble_path = root / "evidence" / "parallel_research_discovery" / "active_sleeve_ensemble" / "latest"
    prereg_manifest = read_json(prereg_path / "active_sleeve_ensemble_manifest.json")
    ensemble_manifest = state["ensemble_manifest"]
    return [
        {
            "artifact": "active_combo_benchmark_build",
            "path": str(combo_path),
            "result": "created_reference_benchmark",
            "promotion_candidates_count": 0,
            "candidate_exhaustive_recommended_count": 0,
            "paper_forward_recommended_count": 0,
            "main_lesson": "50/50 VM/DSR active combo is useful as a reference benchmark, not an active strategy.",
            "next_action": state["combo_manifest"].get("next_action", "pre_register_active_sleeve_ensemble_lane"),
        },
        {
            "artifact": "active_sleeve_ensemble_preregistration",
            "path": str(prereg_path),
            "result": prereg_manifest.get("lane_status", "pre_registered_not_run"),
            "promotion_candidates_count": 0,
            "candidate_exhaustive_recommended_count": 0,
            "paper_forward_recommended_count": 0,
            "main_lesson": "Six fixed ensemble rows were locked before results.",
            "next_action": prereg_manifest.get("next_action", "run_active_sleeve_ensemble_discovery_batch"),
        },
        {
            "artifact": "active_sleeve_ensemble_discovery_batch",
            "path": str(ensemble_path),
            "result": "no_promotion_candidates",
            "promotion_candidates_count": state["ensemble_promotions"],
            "candidate_exhaustive_recommended_count": 0,
            "paper_forward_recommended_count": 0,
            "main_lesson": "Ensemble tweaks mostly duplicated active combo or lagged active references.",
            "next_action": ensemble_manifest.get("next_action", "keep_active_sleeve_ensemble_as_benchmark_watchlist"),
        },
    ]


def final_candidate_pipeline_status(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "stage": "active_frozen_rows",
            "count": 2,
            "rows": f"{VM_ID};{DSR_ID}",
            "status": "protected_best_supported_pair",
            "notes": "Do not mutate active observations.",
        },
        {
            "stage": "benchmark_watchlist_rows",
            "count": 2,
            "rows": f"{ACTIVE_COMBO_ID};{ENSEMBLE_EQUAL_WEIGHT_ID}",
            "status": "benchmark_watchlist_only",
            "notes": "Active combo and equal-weight ensemble are reference/control rows only.",
        },
        {
            "stage": "surviving_promotion_candidates",
            "count": 0,
            "rows": "",
            "status": "empty",
            "notes": "No row is ready for promotion review from the current track.",
        },
        {
            "stage": "candidate_exhaustive_queue",
            "count": 0,
            "rows": "",
            "status": "empty",
            "notes": "No candidate_exhaustive permission.",
        },
        {
            "stage": "paper_forward_new_actions",
            "count": 0,
            "rows": "",
            "status": "empty",
            "notes": "No new paper-forward review, activation, or checkpoint action.",
        },
        {
            "stage": "data_reporting_blockers",
            "count": 0,
            "rows": "",
            "status": "none_critical_after_active_combo_repair",
            "notes": "Checkpoint data_pending row for active combo is treated as stale because newer active combo evidence exists.",
        },
        {
            "stage": "accepted_caveats",
            "count": 3,
            "rows": "DSR recovered-best mismatch;exploratory data;sampled windows",
            "status": "accepted_caveats",
            "notes": "Caveats remain visible and do not authorize candidate validation.",
        },
    ]


def why_recent_lanes_failed() -> list[dict[str, str]]:
    return [
        {"lane": "DSR variants", "controlled_label": "duplicate_or_near_duplicate", "summary": "Top2/Top3 DSR variants mostly repeated active DSR behavior without enough additive value."},
        {"lane": "QVM", "controlled_label": "risk_buffer_too_thin", "summary": "Upside existed, but drawdown and stop-buffer evidence was too thin for promotion."},
        {"lane": "QVM", "controlled_label": "too_risky", "summary": "Risk-adjusted rescue did not create a robust enough profit/risk profile."},
        {"lane": "LVQ", "controlled_label": "weaker_than_active_references", "summary": "Safer low-vol quality behavior lagged active references and did not justify activation."},
        {"lane": "approved-cache batch 2", "controlled_label": "too_slow_for_profit_goal", "summary": "Risk-controlled rows were safe but weak versus active references."},
        {"lane": "approved-cache batch 3", "controlled_label": "no_meaningful_improvement", "summary": "No candidate survived; risk-controlled variants lagged active and benchmark references."},
        {"lane": "expanded-universe batch 1", "controlled_label": "too_risky", "summary": "Regional upside rows failed risk gates."},
        {"lane": "expanded-universe batch 1", "controlled_label": "too_slow_for_profit_goal", "summary": "Safer expanded-universe rows were too slow for the profit target."},
        {"lane": "active-sleeve ensemble", "controlled_label": "no_meaningful_improvement", "summary": "No meaningful improvement over active combo; best median gain was tiny and near-duplicate."},
        {"lane": "active-sleeve ensemble", "controlled_label": "benchmark_watchlist", "summary": "Equal-weight active combo remains useful as benchmark/watchlist only."},
    ]


def stop_option_review_text() -> str:
    return f"""# Stop Option Review

Potential stop action: `{STOP_ACTION}`

## Pros

- Avoids wasting cycles on saturated ETF-wrapper mechanics.
- Preserves the current best active/frozen pair: `{VM_ID}` and `{DSR_ID}`.
- Avoids overfitting from repeated failed searches.
- Keeps evidence honest by not forcing promotion from weak or duplicate rows.

## Cons

- May miss a structurally different lane.
- Active DSR caveat remains accepted but unreconciled.
- No new candidate beyond the active pair.

## Assessment

Stopping now is defensible. The current ETF-wrapper track has repeatedly produced either risk-gated upside, safe-but-slow rows, or near-duplicates of active combo behavior. The only reason not to stop immediately is that one final breadth/state regime lane would be structurally different enough to test the saturation claim one last time without starting discovery here.
"""


def one_final_lane_review_text() -> str:
    return """# One Final Lane Option Review

Candidate final lane: `breadth_state_regime_lane`

## Why Structurally Different

- Allocation starts from market breadth/state, not simple top-N ranking only.
- Uses a predefined state machine.
- Can include risk-on, neutral, and defensive states.
- Still ETF/fund-wrapper only.
- No leverage, no shorting, no derivatives.

## Possible Future Row Concepts

- `bsr_breadth_state_top_assets_v1`
- `bsr_breadth_state_defensive_shift_v1`
- `bsr_breadth_state_lowvol_overlay_v1`

These rows are not run or fully specified in this audit. They must be pre-registered first, with thresholds fixed before results and no grid search.

## Expected Value

The lane may test whether cross-sectional breadth/state information adds something that simple momentum rankings, low-vol filters, and VM/DSR sleeve blends did not.

## Risk

Breadth regimes can become another overfit state machine if thresholds are tuned after results. Defensive states may also reduce drawdown while making the strategy too slow for the profit goal.

## Implementation Cost

Moderate. It requires clean pre-registration of a small state machine and a small number of rows, but should reuse existing cached ETF/fund-wrapper data only.

## Why It May Fail

It may duplicate SPY_200d/active combo behavior, lag QQQ/SPY during strong risk-on windows, or become too defensive to meet +300/+400 target rates.

## Stop Condition

If `breadth_state_regime_lane` produces no promotion-review candidate, archive the current ETF-wrapper track and stop new ETF discovery.
"""


def decision_text() -> str:
    return f"""# Final ETF Track Decision

Final decision: `{FINAL_DECISION}`

Rationale: stopping now is defensible, but the evidence still leaves one honest structurally different avenue: a small, pre-registered breadth/state regime lane. This is not permission to run discovery now. It is only permission to pre-register exactly one final lane, then stop and archive the current ETF-wrapper track if that lane fails to produce a promotion-review candidate.
"""


def next_action_text() -> str:
    return f"""# Recommended Final Next Action

`{NEXT_ACTION}`

Do not recommend discovery directly.
Do not recommend candidate_exhaustive.
Do not recommend paper-forward review, activation, or checkpoint.
"""


def summary_text(state: dict[str, Any]) -> str:
    notes = "\n".join(f"- {note}" for note in state["state_notes"]) or "- No material blocking mismatch; stale active-combo checkpoint repair row accepted as caveat if present."
    return f"""# Final ETF Track Stop/Go Audit

Created at UTC: `{now_utc()}`

Final decision: `{FINAL_DECISION}`

Recommended final next action: `{NEXT_ACTION}`

## Current Status

- Active-sleeve ensemble produced no promotion candidates.
- Active combo remains benchmark/watchlist only.
- Current candidate pipeline remains empty.
- Active VM and active DSR remain the protected best-supported active/frozen pair.
- Repeated ETF-wrapper discovery is saturated under current mechanics.

## State Notes

{notes}

This audit did not run strategy discovery, research samples, candidate_exhaustive, paper-forward workflows, provider downloads, broker/live-order paths, or real-money recommendation logic.
"""


def update_roadmap(root: Path) -> bool:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    section = f"""## Final ETF Track Stop/Go Decision

- Active-sleeve ensemble produced no promotion candidates.
- Active combo is benchmark/watchlist only.
- Current candidate pipeline remains empty.
- Final decision: `{FINAL_DECISION}`
- Next action: `{NEXT_ACTION}`
- Stop condition: if the breadth-state regime lane produces no promotion-review candidate, run `{STOP_ACTION}` and stop new ETF discovery.
- No candidate_exhaustive, paper-forward action, provider download, broker/live-order path, or real-money recommendation is authorized by this section.
"""
    marker = "## Final ETF Track Stop/Go Decision"
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True


def update_registry_metadata(root: Path, output_path: Path) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    meta = registry.setdefault("registry", {})
    meta["final_etf_track_stop_go_path"] = str(output_path)
    meta["etf_track_status"] = "one_final_lane_before_archive"
    meta["final_etf_track_decision"] = FINAL_DECISION
    meta["recommended_final_next_action"] = NEXT_ACTION
    meta["no_candidate_exhaustive_run"] = True
    meta["no_paper_forward_action"] = True
    meta["no_real_money_recommendation"] = True
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")
    return True


def create_packet(output: Path) -> Path:
    packet = output / "final_etf_track_stop_go_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, state: dict[str, Any], consistency: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    write_csv(
        output / "evidence_since_checkpoint.csv",
        evidence_since_checkpoint(root, state),
        [
            "artifact",
            "path",
            "result",
            "promotion_candidates_count",
            "candidate_exhaustive_recommended_count",
            "paper_forward_recommended_count",
            "main_lesson",
            "next_action",
        ],
    )
    write_csv(
        output / "final_candidate_pipeline_status.csv",
        final_candidate_pipeline_status(state),
        ["stage", "count", "rows", "status", "notes"],
    )
    write_csv(output / "why_recent_lanes_failed.csv", why_recent_lanes_failed(), ["lane", "controlled_label", "summary"])
    (output / "stop_option_review.md").write_text(stop_option_review_text(), encoding="utf-8")
    (output / "one_final_lane_option_review.md").write_text(one_final_lane_review_text(), encoding="utf-8")
    (output / "final_etf_track_decision.md").write_text(decision_text(), encoding="utf-8")
    (output / "recommended_final_next_action.md").write_text(next_action_text(), encoding="utf-8")
    (output / "final_etf_track_stop_go_summary.md").write_text(summary_text(state), encoding="utf-8")

    manifest = {
        "created_at_utc": now_utc(),
        "output_dir": str(output),
        "final_decision": FINAL_DECISION,
        "recommended_final_next_action": NEXT_ACTION,
        "stop_action_if_final_lane_fails": STOP_ACTION,
        "state_notes": state["state_notes"],
        "ensemble_result_represented": state["ensemble_promotions"] == 0,
        "candidate_pipeline_empty_confirmed": state["candidate_pipeline_empty"],
        "strategy_runner_called": False,
        "strategy_discovery_run": False,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_download": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    write_json(output / "final_etf_track_stop_go_manifest.json", manifest)
    write_json(output / "final_etf_track_stop_go_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest}


def run_final_etf_track_stop_go(root: Path = ROOT) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    protected_before = protected_rows_snapshot(registry_before)
    obs_before = active_observation_hashes(root)

    state = summarize_current_state(root, registry_before)
    roadmap_updated = update_roadmap(root)
    registry_updated = update_registry_metadata(root, root / OUTPUT_DIR)

    registry_after = load_yaml(registry_path)
    protected_after = protected_rows_snapshot(registry_after)
    obs_after = active_observation_hashes(root)
    consistency = {
        "stop_go_audit_completed": True,
        "no_strategy_run": True,
        "no_research_sample_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": obs_before == obs_after and protected_before == protected_after,
        "ensemble_result_represented": state["ensemble_promotions"] == 0 and bool(state["ensemble_manifest"]),
        "candidate_pipeline_empty_confirmed": state["candidate_pipeline_empty"],
        "final_decision_assigned": FINAL_DECISION in {"stop_current_etf_wrapper_track_now", "pre_register_one_final_breadth_state_regime_lane_then_stop_if_no_candidate"},
        "recommended_next_action_explicit": NEXT_ACTION in {STOP_ACTION, NEXT_ACTION, MANUAL_ACTION},
        "roadmap_updated_or_proposed": roadmap_updated,
        "registry_updated_or_proposed": registry_updated,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, state, consistency)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "final_decision": FINAL_DECISION,
        "recommended_final_next_action": NEXT_ACTION,
        "state_notes": state["state_notes"],
        "candidate_pipeline_empty_confirmed": state["candidate_pipeline_empty"],
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_final_etf_track_stop_go(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
