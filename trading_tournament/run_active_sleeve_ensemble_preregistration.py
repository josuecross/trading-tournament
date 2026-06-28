from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "active_sleeve_ensemble" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
LANE_ID = "active_sleeve_ensemble_lane"
NEXT_ACTION_SUCCESS = "run_active_sleeve_ensemble_discovery_batch"
NEXT_ACTION_REPAIR = "repair_active_sleeve_ensemble_inputs_before_discovery"
NEXT_ACTION_ARCHIVE = "archive_active_sleeve_ensemble_lane_preregistration"
VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
BIL_ID = "BIL_cash_proxy"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"


FUTURE_ROWS: list[dict[str, Any]] = [
    {
        "row_id": "ase_vm_dsr_equal_weight_v1",
        "role": "benchmark_control",
        "vm_weight": 0.50,
        "dsr_weight": 0.50,
        "bil_weight": 0.00,
        "trigger_rule": "none",
        "purpose": "baseline active combo, already represented by active combo benchmark",
    },
    {
        "row_id": "ase_dsr_tilt_60_40_v1",
        "role": "future_test_candidate",
        "vm_weight": 0.40,
        "dsr_weight": 0.60,
        "bil_weight": 0.00,
        "trigger_rule": "none",
        "purpose": "test whether mild DSR tilt improves median equity without too much drawdown",
    },
    {
        "row_id": "ase_vm_tilt_60_40_v1",
        "role": "future_test_candidate",
        "vm_weight": 0.60,
        "dsr_weight": 0.40,
        "bil_weight": 0.00,
        "trigger_rule": "none",
        "purpose": "test whether mild VM tilt preserves most target rates with lower drawdown",
    },
    {
        "row_id": "ase_risk_budget_static_45_45_10_bil_v1",
        "role": "future_test_candidate",
        "vm_weight": 0.45,
        "dsr_weight": 0.45,
        "bil_weight": 0.10,
        "trigger_rule": "none",
        "purpose": "test whether small cash floor improves drawdown while keeping target rates useful",
    },
    {
        "row_id": "ase_spy200d_canary_vm_dsr_v1",
        "role": "future_test_candidate",
        "vm_weight": "0.50 if SPY above 200d else 0.50",
        "dsr_weight": "0.50 if SPY above 200d else 0.25",
        "bil_weight": "0.00 if SPY above 200d else 0.25",
        "trigger_rule": "SPY 200d SMA canary",
        "purpose": "predefined canary risk reduction without tuning",
    },
    {
        "row_id": "ase_drawdown_guard_reference_v1",
        "role": "future_test_candidate",
        "vm_weight": "0.50 default; 0.50 when SPY 63d drawdown < -10%",
        "dsr_weight": "0.50 default; 0.25 when SPY 63d drawdown < -10%",
        "bil_weight": "0.00 default; 0.25 when SPY 63d drawdown < -10%",
        "trigger_rule": "pre-registered SPY trailing 63-trading-day drawdown worse than -10%",
        "purpose": "predefined risk guard benchmark; threshold must not be tuned after results",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_paths(root: Path) -> dict[str, Path]:
    return {
        VM_ID: root / "paper_forward_observations" / VM_ID / "active_observation.yaml",
        DSR_ID: root / "paper_forward_observations" / DSR_ID / "active_observation.yaml",
    }


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    rows = rows_by_id(registry)
    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    combo = root / "evidence" / "active_combo_benchmark" / "latest"
    combo_manifest = load_yaml(combo / "active_combo_manifest.json") if False else {}
    if (combo / "active_combo_manifest.json").exists():
        combo_manifest = json.loads((combo / "active_combo_manifest.json").read_text(encoding="utf-8"))
    if registry.get("registry", {}).get("etf_discovery_status") != "paused":
        mismatches.append("ETF discovery is not paused")
    if not checkpoint.exists():
        mismatches.append("current checkpoint path missing")
    if not combo.exists():
        mismatches.append("active combo benchmark path missing")
    if combo_manifest.get("benchmark_id") != ACTIVE_COMBO_ID:
        mismatches.append("active combo benchmark manifest missing or has unexpected id")
    if combo_manifest.get("active_combo_is_reference_not_active_strategy") is not True:
        mismatches.append("active combo is not marked reference-only")
    if combo_manifest.get("next_action") != "pre_register_active_sleeve_ensemble_lane":
        mismatches.append("active combo next action is not pre_register_active_sleeve_ensemble_lane")
    pipeline = {row.get("stage", ""): row for row in read_csv_rows(checkpoint / "candidate_pipeline_status.csv")}
    if pipeline.get("candidate_exhaustive_queue", {}).get("count") not in {"0", 0}:
        mismatches.append("candidate_exhaustive_queue is not empty")
    if pipeline.get("promotion_review_candidates", {}).get("count") not in {"0", 0}:
        mismatches.append("promotion_review_candidates is not empty")
    for strategy_id in [VM_ID, DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
        if not active_observation_paths(root)[strategy_id].exists():
            mismatches.append(f"{strategy_id} active observation file missing")
    return mismatches


def future_row_outputs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in FUTURE_ROWS:
        rows.append(
            {
                **row,
                "lane_id": LANE_ID,
                "lane_status": "pre_registered_not_run",
                "rebalance": "monthly",
                "allowed_inputs": f"{VM_ID};{DSR_ID};{BIL_ID};{SPY_200D_ID}",
                "excluded_first_pass_inputs": "lvq_lowvol_quality_spy_regime_v1",
                "metrics_computed": False,
                "research_sample_run": False,
                "candidate_exhaustive_run": False,
                "paper_forward_active": False,
                "real_money_recommendation": False,
            }
        )
    return rows


def lane_definition() -> dict[str, Any]:
    return {
        "lane_id": LANE_ID,
        "lane_status": "pre_registered_not_run",
        "goal": "Test whether fixed combinations of the two active sleeves can improve the profit/risk tradeoff versus active references.",
        "scope": "future research lane definition only",
        "sleeves_allowed": [VM_ID, DSR_ID, BIL_ID],
        "benchmark_controls": [ACTIVE_COMBO_ID, SPY_200D_ID, "SPY_buy_hold", "QQQ_buy_hold", BIL_ID],
        "excluded_first_pass_sleeves": ["lvq_lowvol_quality_spy_regime_v1"],
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "forbidden": [
            "strategy_discovery_now",
            "research_sample_now",
            "candidate_exhaustive",
            "paper_forward_activation",
            "provider_download",
            "broker_integration",
            "live_orders",
            "real_money_recommendation",
            "parameter_optimization",
            "grid_search",
        ],
    }


def evaluation_plan_text() -> str:
    return f"""# Active Sleeve Ensemble Evaluation Plan

This is a future evaluation plan only. No strategy metrics were computed during pre-registration.

Future rows must be compared against:

- active VM
- active DSR
- active combo 50/50
- SPY_200d
- SPY buy-hold
- QQQ buy-hold
- BIL

Future metrics:

- 90d median final equity
- 180d median final equity
- 180d mean final equity
- 180d p75 final equity
- 180d p90 final equity
- best final equity
- worst final equity
- +300 target-before-stop rate
- +400 target-before-stop rate
- 180d worst drawdown
- stop-hit rate
- risk buffer vs -600
- simple cost stress if supported
- correlation vs VM
- correlation vs DSR
- correlation vs active combo
- delta vs active combo
- delta vs DSR
- delta vs SPY_200d

Future promotion-review candidate rules:

- A row must beat active combo on either median equity or drawdown-adjusted profile.
- It must not materially worsen risk buffer.
- It must have stop-hit rate 0.
- It must improve enough versus VM/DSR to justify extra complexity.
- It must not merely duplicate active combo with no benefit.
- It must not depend on tuned thresholds.
"""


def risk_policy_text() -> str:
    return """# Active Sleeve Ensemble Risk Policy

- No ensemble row may move to candidate_exhaustive directly from pre-registration.
- No ensemble row may move to paper-forward directly.
- Any row with base or stressed risk buffer below 25 should fail promotion review unless the user explicitly overrides.
- Any row that worsens drawdown versus active combo without improving target rates should fail.
- Any row that only marginally improves median equity but adds complexity should stay watchlist.
- Active combo 50/50 remains benchmark/reference unless separately reviewed later.
"""


def do_not_run_text() -> str:
    return """# Do Not Run Now

Do not run active sleeve ensemble discovery, research_sample, candidate_exhaustive, paper-forward review, paper-forward activation, paper-forward checkpoint, provider download, broker integration, live orders, order placement, or real-money recommendation from this pre-registration packet.

The six future rows are fixed before results and must not be tuned after results.
"""


def update_roadmap(root: Path) -> bool:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Pre-registered Active Sleeve Ensemble Lane

- Lane id: `{LANE_ID}`
- Purpose: test fixed combinations of existing active VM and active DSR sleeves, plus optional BIL, against active combo and market benchmarks.
- Future rows: `{', '.join(row['row_id'] for row in FUTURE_ROWS)}`
- Status: pre-registered, not yet run.
- No candidate_exhaustive, promotion, paper-forward, broker, live-order, provider-download, or real-money permission.
- Next action after pre-registration: `{NEXT_ACTION_SUCCESS}`.
"""
    marker = "## Pre-registered Active Sleeve Ensemble Lane"
    if marker in existing:
        updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section
    else:
        updated = existing.rstrip() + "\n\n" + section
    path.write_text(updated, encoding="utf-8")
    return True


def update_registry_metadata(root: Path) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    meta = registry.setdefault("registry", {})
    meta["lane_id"] = LANE_ID
    meta["lane_status"] = "pre_registered_not_run"
    meta["future_rows"] = [row["row_id"] for row in FUTURE_ROWS]
    meta["candidate_exhaustive_run"] = False
    meta["paper_forward_active"] = False
    meta["real_money_recommendation"] = False
    meta["latest_preregistration_path"] = str(root / OUTPUT_DIR)
    meta["current_next_action"] = NEXT_ACTION_SUCCESS
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")
    return True


def create_packet(output: Path) -> Path:
    packet = output / "active_sleeve_ensemble_preregistration_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, consistency: dict[str, Any], next_action: str, state_notes: list[str]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    future_rows = future_row_outputs()
    (output / "active_sleeve_ensemble_lane_definition.yaml").write_text(yaml.safe_dump(lane_definition(), sort_keys=False), encoding="utf-8")
    write_csv(
        output / "active_sleeve_ensemble_future_rows.csv",
        future_rows,
        [
            "row_id",
            "lane_id",
            "lane_status",
            "role",
            "vm_weight",
            "dsr_weight",
            "bil_weight",
            "trigger_rule",
            "rebalance",
            "purpose",
            "allowed_inputs",
            "excluded_first_pass_inputs",
            "metrics_computed",
            "research_sample_run",
            "candidate_exhaustive_run",
            "paper_forward_active",
            "real_money_recommendation",
        ],
    )
    (output / "active_sleeve_ensemble_evaluation_plan.md").write_text(evaluation_plan_text(), encoding="utf-8")
    (output / "active_sleeve_ensemble_risk_policy.md").write_text(risk_policy_text(), encoding="utf-8")
    (output / "active_sleeve_ensemble_do_not_run_now.md").write_text(do_not_run_text(), encoding="utf-8")
    (output / "active_sleeve_ensemble_next_action.md").write_text(f"# Active Sleeve Ensemble Next Action\n\n`{next_action}`\n\nDo not recommend candidate_exhaustive or paper-forward from pre-registration.\n", encoding="utf-8")
    summary = f"""# Active Sleeve Ensemble Preregistration

Created at UTC: `{now_utc()}`

Lane id: `{LANE_ID}`

Status: `pre_registered_not_run`

Future rows defined: `{len(future_rows)}`

This packet defines a structurally different future lane based on existing active VM and active DSR sleeves. It does not compute strategy results, run discovery, run candidate validation, activate paper-forward, download data, or recommend real-money trading.

Next action: `{next_action}`
"""
    (output / "active_sleeve_ensemble_preregistration_summary.md").write_text(summary, encoding="utf-8")
    manifest = {
        "created_at_utc": now_utc(),
        "lane_id": LANE_ID,
        "lane_status": "pre_registered_not_run",
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "state_notes": state_notes,
        "next_action": next_action,
        "strategy_metrics_computed": False,
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
    write_json(output / "active_sleeve_ensemble_manifest.json", manifest)
    write_json(output / "active_sleeve_ensemble_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest}


def run_active_sleeve_ensemble_preregistration(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    obs_before = {strategy_id: file_hash(path) for strategy_id, path in active_observation_paths(root).items()}
    mismatches = state_mismatches(root, registry)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    next_action = NEXT_ACTION_SUCCESS if not mismatches else NEXT_ACTION_REPAIR
    update_roadmap(root)
    update_registry_metadata(root)
    obs_after = {strategy_id: file_hash(path) for strategy_id, path in active_observation_paths(root).items()}
    consistency = {
        "preregistration_completed": True,
        "lane_status_pre_registered_not_run": True,
        "future_rows_defined": len(FUTURE_ROWS) == 6,
        "no_strategy_metrics_computed": True,
        "no_strategy_discovery_run": True,
        "no_research_sample_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_review": True,
        "no_paper_forward_activation": True,
        "no_paper_forward_checkpoint": True,
        "no_provider_download": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "active_observations_unchanged": obs_before == obs_after,
        "active_combo_remains_reference_only": True,
        "next_action_explicit": bool(next_action),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, consistency, next_action, mismatches)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "lane_id": LANE_ID,
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "next_action": next_action,
        "consistency": consistency,
        "state_mismatches": mismatches,
    }


def main() -> None:
    print(json.dumps(run_active_sleeve_ensemble_preregistration(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
