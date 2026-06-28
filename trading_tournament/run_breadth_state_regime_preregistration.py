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
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "breadth_state_regime" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
APPROVED_POLICY_PATH = Path("strategy_lab") / "APPROVED_ETF_CACHE_POLICY.md"
APPROVED_SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"

LANE_ID = "breadth_state_regime_lane"
LANE_STATUS = "pre_registered_not_run"
NEXT_ACTION_SUCCESS = "run_breadth_state_regime_discovery_batch"
NEXT_ACTION_REPAIR = "repair_breadth_state_regime_inputs_before_discovery"
NEXT_ACTION_ARCHIVE = "archive_current_etf_wrapper_track_summary"
FINAL_DECISION = "pre_register_one_final_breadth_state_regime_lane_then_stop_if_no_candidate"
REQUIRED_PREVIOUS_NEXT_ACTION = "pre_register_breadth_state_regime_lane"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
LVQ_ID = "lvq_lowvol_quality_spy_regime_v1"

RISK_BREADTH_BASKET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ", "EWU", "EWG", "EWY", "INDA", "SCHG", "MTUM"]
DEFENSIVE_STABILIZER_BASKET = ["BIL", "IEF", "TLT", "AGG", "GLD", "SPLV", "USMV", "EFAV", "EEMV"]
OPTIONAL_QUALITY_VALUE_SUPPORT = ["QUAL", "VTV"]
DEFERRED_SYMBOLS = ["IEFA", "VEA", "VWO", "IWF", "IWD", "SCHV", "ACWV"]
ACTIVE_SLEEVE_IDS = [VM_ID, DSR_ID, ACTIVE_COMBO_ID]
ACTIVE_OBSERVATION_PATHS = {
    VM_ID: Path("paper_forward_observations") / VM_ID / "active_observation.yaml",
    DSR_ID: Path("paper_forward_observations") / DSR_ID / "active_observation.yaml",
}

FUTURE_ROWS: list[dict[str, Any]] = [
    {
        "row_id": "bsr_breadth_state_top_assets_v1",
        "role": "future_test_candidate",
        "risk_on_rule": "top 4 risk assets by 126d return / 60d volatility, equal weighted",
        "neutral_rule": "50% top 2 risk assets, 30% top 1 defensive asset from GLD/IEF/TLT/AGG/USMV/EFAV/EEMV, 20% BIL",
        "risk_off_rule": "40% GLD, 40% best of IEF/TLT/AGG by 126d return / 60d volatility, 20% BIL",
        "fallback_rule": "unused allocation goes to BIL",
    },
    {
        "row_id": "bsr_breadth_state_defensive_shift_v1",
        "role": "future_test_candidate",
        "risk_on_rule": "70% top 3 risk assets by 126d return / 60d volatility, 30% top 1 defensive asset from GLD/IEF/TLT/AGG",
        "neutral_rule": "40% top 2 risk assets, 30% top 1 low-vol asset from SPLV/USMV/EFAV/EEMV, 30% BIL",
        "risk_off_rule": "60% BIL, 40% top 1 defensive asset from GLD/IEF/TLT/AGG",
        "fallback_rule": "unavailable or ineligible sleeve allocation goes to BIL",
    },
    {
        "row_id": "bsr_breadth_state_lowvol_overlay_v1",
        "role": "future_test_candidate",
        "risk_on_rule": "50% top 2 risk assets by 126d return / 60d volatility, 30% top 1 low-vol/quality asset from SPLV/USMV/QUAL/EFAV/EEMV, 20% BIL",
        "neutral_rule": "30% top 1 risk asset, 40% top 2 low-vol/quality assets, 30% BIL",
        "risk_off_rule": "50% BIL, 30% best of IEF/TLT/AGG, 20% best of GLD/USMV/EFAV",
        "fallback_rule": "unavailable or ineligible sleeve allocation goes to BIL",
    },
    {
        "row_id": "bsr_breadth_state_active_combo_overlay_v1",
        "role": "future_test_candidate",
        "risk_on_rule": "50% active combo benchmark sleeve, 30% top 1 risk asset from QQQ/SCHG/MTUM/SPY, 20% BIL",
        "neutral_rule": "50% active combo benchmark sleeve, 25% top 1 defensive asset from GLD/IEF/TLT/AGG, 25% BIL",
        "risk_off_rule": "50% VM sleeve, 50% BIL",
        "fallback_rule": "active combo is an input benchmark sleeve only; row is not active and not paper-forward",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def active_observation_hashes(root: Path) -> dict[str, str]:
    return {strategy_id: file_hash(root / rel_path) for strategy_id, rel_path in ACTIVE_OBSERVATION_PATHS.items()}


def protected_rows_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = rows_by_id(registry)
    return {strategy_id: deepcopy(rows.get(strategy_id, {})) for strategy_id in [VM_ID, DSR_ID, SPY_200D_ID]}


def approved_symbols(root: Path) -> set[str]:
    symbol_map = load_yaml(root / APPROVED_SYMBOL_MAP_PATH)
    return {
        str(row.get("symbol"))
        for row in symbol_map.get("symbols", [])
        if row.get("allowed_for_strategy") is True and row.get("cache_ready", True) is not False
    }


def referenced_symbols() -> set[str]:
    return set(RISK_BREADTH_BASKET + DEFENSIVE_STABILIZER_BASKET + OPTIONAL_QUALITY_VALUE_SUPPORT)


def state_mismatches(root: Path, registry: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    final_decision = (root / "evidence" / "final_etf_track_stop_go" / "latest" / "final_etf_track_decision.md").read_text(encoding="utf-8") if (root / "evidence" / "final_etf_track_stop_go" / "latest" / "final_etf_track_decision.md").exists() else ""
    final_next = (root / "evidence" / "final_etf_track_stop_go" / "latest" / "recommended_final_next_action.md").read_text(encoding="utf-8") if (root / "evidence" / "final_etf_track_stop_go" / "latest" / "recommended_final_next_action.md").exists() else ""
    pipeline = {row.get("stage", ""): row for row in read_csv_rows(root / "evidence" / "final_etf_track_stop_go" / "latest" / "final_candidate_pipeline_status.csv")}
    combo_manifest = read_json(root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json")
    rows = rows_by_id(registry)
    if FINAL_DECISION not in final_decision:
        mismatches.append("final stop/go decision does not authorize the one final breadth-state lane")
    if REQUIRED_PREVIOUS_NEXT_ACTION not in final_next:
        mismatches.append("recommended final next action is not pre_register_breadth_state_regime_lane")
    if pipeline.get("surviving_promotion_candidates", {}).get("count") not in {"0", 0}:
        mismatches.append("surviving promotion candidate count is not zero")
    if pipeline.get("candidate_exhaustive_queue", {}).get("count") not in {"0", 0}:
        mismatches.append("candidate_exhaustive queue count is not zero")
    if pipeline.get("paper_forward_new_actions", {}).get("count") not in {"0", 0}:
        mismatches.append("paper-forward new action count is not zero")
    if combo_manifest.get("active_combo_is_reference_not_active_strategy") is not True:
        mismatches.append("active combo is not reference-only")
    for strategy_id in [VM_ID, DSR_ID]:
        row = rows.get(strategy_id, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{strategy_id} is not active/frozen")
        if not (root / ACTIVE_OBSERVATION_PATHS[strategy_id]).exists():
            mismatches.append(f"{strategy_id} active observation file missing")
    if rows.get(SPY_200D_ID, {}).get("rules_frozen") is not True:
        mismatches.append(f"{SPY_200D_ID} is not frozen")
    missing_symbols = sorted(referenced_symbols() - approved_symbols(root))
    if missing_symbols:
        mismatches.append("referenced symbols are not approved/cache-ready: " + ",".join(missing_symbols))
    if referenced_symbols() & set(DEFERRED_SYMBOLS):
        mismatches.append("deferred symbols are referenced")
    return mismatches


def future_row_outputs() -> list[dict[str, Any]]:
    all_symbols = ";".join(sorted(referenced_symbols()))
    active_sleeves = ";".join(ACTIVE_SLEEVE_IDS)
    rows: list[dict[str, Any]] = []
    for row in FUTURE_ROWS:
        rows.append(
            {
                **row,
                "lane_id": LANE_ID,
                "lane_status": LANE_STATUS,
                "rebalance": "monthly",
                "state_signal": "pre_registered_risk_breadth_count_with_spy_qqq_canary_override",
                "risk_breadth_thresholds": "risk_on>=8;neutral=5_to_7;risk_off<=4;force_risk_off_if_SPY_and_QQQ_below_200d",
                "allowed_symbols": all_symbols,
                "active_sleeves_allowed": active_sleeves if row["row_id"] == "bsr_breadth_state_active_combo_overlay_v1" else "",
                "deferred_symbols_excluded": ";".join(DEFERRED_SYMBOLS),
                "metrics_computed": False,
                "strategy_discovery_run": False,
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
        "lane_status": LANE_STATUS,
        "purpose": "Test whether a predefined market-breadth/state machine adds value beyond simple top-N momentum, DSR, VM, QVM/LVQ, regional expansion, and active-sleeve ensembles.",
        "structurally_different_because": [
            "starts_with_breadth_state_classification",
            "allocation_depends_on_market_state",
            "not_just_top_n_etf_ranking",
            "etf_fund_wrapper_only",
            "no_leverage_shorting_derivatives_or_intraday_logic",
        ],
        "risk_breadth_basket": RISK_BREADTH_BASKET,
        "defensive_stabilizer_basket": DEFENSIVE_STABILIZER_BASKET,
        "optional_quality_value_support": OPTIONAL_QUALITY_VALUE_SUPPORT,
        "active_sleeves_allowed": ACTIVE_SLEEVE_IDS,
        "deferred_symbols_excluded": DEFERRED_SYMBOLS,
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "stop_condition": "If the future breadth-state discovery batch produces no promotion-review candidate, archive/stop the ETF-wrapper track.",
        "forbidden": [
            "strategy_discovery_now",
            "research_sample_now",
            "backtest_now",
            "performance_computation_now",
            "candidate_exhaustive",
            "paper_forward_review",
            "paper_forward_activation",
            "paper_forward_checkpoint",
            "provider_download",
            "broker_integration",
            "live_orders",
            "real_money_recommendation",
            "parameter_optimization",
            "grid_search",
            "threshold_variants",
        ],
    }


def state_definitions_text() -> str:
    return """# Breadth-State Regime State Definitions

These definitions are pre-registered before any breadth-state results are computed. They must not be tuned after results.

## Signal Timing

- Monthly rebalance.
- Use prior trading day signals only.
- Use per-asset availability.
- Assets without enough history are not counted until they have enough data for the relevant signal.
- Future runs must record available-count denominator each month.
- No common-start forcing.

## Breadth Signal

Risk-breadth count: count how many risk/breadth basket assets are above their 200-day SMA.

Risk-breadth universe: SPY, QQQ, IWM, EFA, EEM, EWJ, EWU, EWG, EWY, INDA, SCHG, MTUM.

## State Classification

- `risk_on`: risk_breadth_count >= 8
- `neutral`: risk_breadth_count between 5 and 7 inclusive
- `risk_off`: risk_breadth_count <= 4

Additional canary override: if both SPY and QQQ are below their 200-day SMA, state is forced to `risk_off`.
"""


def evaluation_plan_text() -> str:
    return f"""# Breadth-State Regime Evaluation Plan

This is a future evaluation plan only. No strategy metrics were computed during pre-registration.

Future evaluation must compare each row against:

- active VM: `{VM_ID}`
- active DSR: `{DSR_ID}`
- active combo: `{ACTIVE_COMBO_ID}`
- SPY_200d: `{SPY_200D_ID}`
- SPY buy-hold
- QQQ buy-hold
- BIL
- LVQ watchlist row if available as diagnostic only: `{LVQ_ID}`

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
- risk buffer vs `-600`
- simple cost stress if supported
- correlation vs active VM
- correlation vs active DSR
- correlation vs active combo
- correlation vs SPY_200d
- delta vs active combo
- delta vs DSR
- delta vs SPY_200d
- breadth-state exposure frequency
- risk_on / neutral / risk_off frequency
- BIL allocation frequency

Promotion-review candidate rules:

- Beat active combo on median equity or have a clearly better drawdown-adjusted profile.
- Do not materially worsen risk buffer.
- Stop-hit rate must remain 0.
- +300/+400 rates must remain useful.
- Improve enough versus active VM/DSR/SPY_200d to justify extra complexity.
- Do not merely duplicate active combo or SPY_200d.
- Do not rely on tuned thresholds.
- Use no forbidden mechanics.
"""


def risk_policy_text() -> str:
    return """# Breadth-State Regime Risk Policy

- No breadth-state row may move to candidate_exhaustive directly from pre-registration.
- No breadth-state row may move to paper-forward directly.
- Any row with base or stressed risk buffer below 25 should fail promotion review unless user explicitly overrides.
- Any row with stop-hit rate above 0 should fail promotion review.
- Any row that improves median equity only marginally but adds state-machine complexity should stay watchlist.
- Any row that duplicates active combo or SPY_200d should be archived/diagnostic.
- If the future breadth-state discovery batch produces no promotion-review candidate, the ETF-wrapper track should be archived/stopped.
"""


def do_not_run_text() -> str:
    return """# Do Not Run Now

Do not run strategy discovery, research samples, backtests, performance computation, candidate_exhaustive, paper-forward review, paper-forward activation, paper-forward checkpoint, provider download, broker integration, live orders, order placement, or real-money recommendation from this pre-registration packet.

The four future rows and state thresholds are fixed before results and must not be tuned after results.
"""


def update_roadmap(root: Path) -> bool:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{NEXT_ACTION_SUCCESS}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, f"Current next action: `{NEXT_ACTION_SUCCESS}`")
    base = "\n".join(lines)
    section = f"""## Pre-registered Breadth-State Regime Lane

- Lane id: `{LANE_ID}`
- Purpose: test whether a predefined market-breadth/state machine adds value beyond simple top-N momentum, DSR, VM, QVM/LVQ, regional expansion, and active-sleeve ensembles.
- Fixed state definitions: `risk_on` when breadth count >= 8, `neutral` when 5-7, `risk_off` when <= 4, with SPY+QQQ below 200d forcing `risk_off`.
- Future rows: `{', '.join(row['row_id'] for row in FUTURE_ROWS)}`
- Status: pre-registered, not yet run.
- No candidate_exhaustive, promotion, paper-forward, broker, live-order, provider-download, or real-money permission.
- Stop condition: if the future breadth-state discovery batch produces no promotion-review candidate, run `{NEXT_ACTION_ARCHIVE}` and stop new ETF-wrapper discovery.
- Next action after pre-registration: `{NEXT_ACTION_SUCCESS}`.
"""
    marker = "## Pre-registered Breadth-State Regime Lane"
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True


def update_registry_metadata(root: Path) -> bool:
    path = root / REGISTRY_PATH
    registry = load_yaml(path)
    meta = registry.setdefault("registry", {})
    meta["lane_id"] = LANE_ID
    meta["lane_status"] = LANE_STATUS
    meta["future_rows"] = [row["row_id"] for row in FUTURE_ROWS]
    meta["candidate_exhaustive_run"] = False
    meta["paper_forward_active"] = False
    meta["real_money_recommendation"] = False
    meta["latest_preregistration_path"] = str(root / OUTPUT_DIR)
    meta["current_next_action"] = NEXT_ACTION_SUCCESS
    meta["no_candidate_exhaustive_run"] = True
    meta["no_paper_forward_action"] = True
    meta["no_real_money_recommendation"] = True
    path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")
    return True


def create_packet(output: Path) -> Path:
    packet = output / "breadth_state_regime_preregistration_packet.zip"
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
    (output / "breadth_state_regime_lane_definition.yaml").write_text(yaml.safe_dump(lane_definition(), sort_keys=False), encoding="utf-8")
    write_csv(
        output / "breadth_state_regime_future_rows.csv",
        future_rows,
        [
            "row_id",
            "lane_id",
            "lane_status",
            "role",
            "rebalance",
            "state_signal",
            "risk_breadth_thresholds",
            "risk_on_rule",
            "neutral_rule",
            "risk_off_rule",
            "fallback_rule",
            "allowed_symbols",
            "active_sleeves_allowed",
            "deferred_symbols_excluded",
            "metrics_computed",
            "strategy_discovery_run",
            "research_sample_run",
            "candidate_exhaustive_run",
            "paper_forward_active",
            "real_money_recommendation",
        ],
    )
    (output / "breadth_state_regime_state_definitions.md").write_text(state_definitions_text(), encoding="utf-8")
    (output / "breadth_state_regime_evaluation_plan.md").write_text(evaluation_plan_text(), encoding="utf-8")
    (output / "breadth_state_regime_risk_policy.md").write_text(risk_policy_text(), encoding="utf-8")
    (output / "breadth_state_regime_do_not_run_now.md").write_text(do_not_run_text(), encoding="utf-8")
    (output / "breadth_state_regime_next_action.md").write_text(
        f"# Breadth-State Regime Next Action\n\n`{next_action}`\n\nDo not recommend candidate_exhaustive or paper-forward from pre-registration.\n",
        encoding="utf-8",
    )
    summary = f"""# Breadth-State Regime Preregistration

Created at UTC: `{now_utc()}`

Lane id: `{LANE_ID}`

Status: `{LANE_STATUS}`

Future rows defined: `{len(future_rows)}`

This packet defines the final structurally different ETF-wrapper lane before any breadth-state results are known. It does not run discovery, research samples, backtests, performance computation, candidate validation, paper-forward workflows, provider downloads, broker/live-order paths, or real-money recommendation logic.

Next action: `{next_action}`
"""
    (output / "breadth_state_regime_preregistration_summary.md").write_text(summary, encoding="utf-8")
    manifest = {
        "created_at_utc": now_utc(),
        "lane_id": LANE_ID,
        "lane_status": LANE_STATUS,
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "risk_breadth_basket": RISK_BREADTH_BASKET,
        "defensive_stabilizer_basket": DEFENSIVE_STABILIZER_BASKET,
        "optional_quality_value_support": OPTIONAL_QUALITY_VALUE_SUPPORT,
        "deferred_symbols_excluded": DEFERRED_SYMBOLS,
        "state_definitions": {
            "risk_on": "risk_breadth_count >= 8",
            "neutral": "risk_breadth_count between 5 and 7 inclusive",
            "risk_off": "risk_breadth_count <= 4",
            "canary_override": "if both SPY and QQQ are below 200-day SMA, force risk_off",
            "data_history_rule": "per_asset_availability_no_common_start_forcing",
        },
        "state_notes": state_notes,
        "next_action": next_action,
        "strategy_metrics_computed": False,
        "strategy_discovery_run": False,
        "research_sample_run": False,
        "backtest_run": False,
        "performance_computation_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "provider_download": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "stop_condition": "If the future breadth-state discovery batch produces no promotion-review candidate, archive/stop the ETF-wrapper track.",
    }
    write_json(output / "breadth_state_regime_manifest.json", manifest)
    write_json(output / "breadth_state_regime_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest}


def run_breadth_state_regime_preregistration(root: Path = ROOT, strict_state: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    registry_before = load_yaml(registry_path)
    protected_before = protected_rows_snapshot(registry_before)
    obs_before = active_observation_hashes(root)
    mismatches = state_mismatches(root, registry_before)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    approved_only = referenced_symbols() <= approved_symbols(root)
    deferred_excluded = not bool(referenced_symbols() & set(DEFERRED_SYMBOLS))
    next_action = NEXT_ACTION_SUCCESS if approved_only and deferred_excluded else NEXT_ACTION_REPAIR

    roadmap_updated = update_roadmap(root)
    registry_updated = update_registry_metadata(root)
    registry_after = load_yaml(registry_path)
    protected_after = protected_rows_snapshot(registry_after)
    obs_after = active_observation_hashes(root)
    consistency = {
        "preregistration_completed": True,
        "lane_status_pre_registered_not_run": True,
        "future_rows_defined": len(FUTURE_ROWS) == 4,
        "fixed_state_definitions_created": True,
        "no_threshold_variants_created": True,
        "approved_symbols_only": approved_only,
        "deferred_symbols_excluded": deferred_excluded,
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
        "active_observations_unchanged": obs_before == obs_after and protected_before == protected_after,
        "stop_condition_recorded": True,
        "next_action_explicit": next_action in {NEXT_ACTION_SUCCESS, NEXT_ACTION_REPAIR, NEXT_ACTION_ARCHIVE},
        "roadmap_updated": roadmap_updated,
        "registry_updated": registry_updated,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    outputs = write_outputs(root, consistency, next_action, mismatches)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "lane_id": LANE_ID,
        "future_rows": [row["row_id"] for row in FUTURE_ROWS],
        "next_action": next_action,
        "state_mismatches": mismatches,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_breadth_state_regime_preregistration(ROOT, strict_state=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
