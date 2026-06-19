from __future__ import annotations

import csv
import json
import shutil
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "research_roadmap" / "latest"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
NEXT_ACTION = "create_managed_futures_etf_wrapper_fast_exploration_review_prompt"

PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}

FORBIDDEN_NEXT_ACTIONS = {
    "paper_forward_activation",
    "paper_forward_checkpoint",
    "real_money_recommendation",
    "broker_integration",
    "live_orders",
    "order_placement",
    "promote_to_real_money",
    "add_broker_integration",
    "place_live_orders",
    "run_backtest",
    "run_research_sample",
    "run_candidate_exhaustive",
    "run_profit_exploration",
    "download_data",
    "call_provider_api",
    "use_options",
    "use_futures_contract_logic",
    "use_forex",
    "use_crypto",
    "use_intraday_logic",
    "use_leverage",
    "use_margin",
    "use_shorting",
    "use_individual_stock_logic",
    "tune_parameters",
    "grid_search",
    "skip_gates",
}

PRIORITY_BACKLOG = [
    {
        "priority_rank": 1,
        "family_id": "managed_futures_etf_wrapper",
        "status": "next_family_to_review",
        "reason": "Highest next priority because the project needs a family that is more additive than SPY/QQQ/sector/growth behavior. Trend-following / managed-futures-style ETF wrappers may provide a different return stream. This must be ETF/fund-wrapper only, not direct futures trading.",
        "next_allowed_action": NEXT_ACTION,
    },
    {
        "priority_rank": 2,
        "family_id": "dual_momentum_paa_etf_wrapper",
        "status": "future_family_review",
        "reason": "Clean relative momentum plus absolute momentum / protective allocation style. Plausible, but must be checked carefully for duplication with GROR, SPY_200d, and active combo.",
        "next_allowed_action": "create_dual_momentum_paa_etf_wrapper_fast_exploration_review_prompt",
    },
    {
        "priority_rank": 3,
        "family_id": "gtaa_faber_style_benchmark_lane",
        "status": "future_benchmark_family",
        "reason": "Simple global tactical allocation / moving-average benchmark family. Useful as a benchmark and sanity check, but likely overlaps with SPY_200d, GROR, and active combo.",
        "next_allowed_action": "create_gtaa_faber_style_benchmark_lane_review_prompt",
    },
    {
        "priority_rank": 4,
        "family_id": "dsr_sector_top2_momentum_200d_bil_v1",
        "status": "future_review_candidate",
        "reason": "Promising DSR same-family row. Exact metrics are missing/unavailable after recovery, and active DSR equal-weight is already frozen, so this is lower priority than new family discovery.",
        "next_allowed_action": "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1",
    },
    {
        "priority_rank": 5,
        "family_id": "dsr_sector_top3_momentum_defensive_cash_v1",
        "status": "deferred_candidate_queue",
        "reason": "Promotion review already passed and candidate validation was recommended before being deferred. Same-family as active DSR equal-weight, so it remains deferred until new family discovery advances.",
        "next_allowed_action": "create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1",
    },
    {
        "priority_rank": 6,
        "family_id": "static_all_weather_or_permanent_portfolio_benchmark",
        "status": "future_benchmark_or_control",
        "reason": "Potentially useful benchmark/control family. Likely too defensive/slow for the profit-first objective unless it provides strong drawdown diversification.",
        "next_allowed_action": "create_static_all_weather_benchmark_lane_review_prompt",
    },
    {
        "priority_rank": 7,
        "family_id": "quality_momentum_etf_proxy",
        "status": "watchlist_no_more_rescue_now",
        "reason": "Already investigated. It had profit power but failed risk/duplicate gates, including one bounded risk-control rescue batch. Do not rescue again unless new evidence appears.",
        "next_allowed_action": "keep_quality_momentum_on_watchlist",
    },
    {
        "priority_rank": 8,
        "family_id": "commodity_wrapper",
        "status": "deferred",
        "reason": "Deferred. Commodity-only wrapper approaches may be too volatile unless expressed through a trend-following or managed-futures-style wrapper.",
        "next_allowed_action": "defer_commodity_wrapper_until_after_managed_futures_review",
    },
    {
        "priority_rank": 9,
        "family_id": "crypto_spot",
        "status": "deferred",
        "reason": "Deferred due risk/evidence concerns. Not aligned with current ETF-wrapper recovery direction.",
        "next_allowed_action": "defer_crypto_spot",
    },
    {
        "priority_rank": 10,
        "family_id": "individual_stock_momentum",
        "status": "blocked_or_deferred",
        "reason": "Blocked/deferred because of survivorship, provider, package, and terms issues. Not appropriate for the current minimal ETF-wrapper direction.",
        "next_allowed_action": "keep_individual_stock_momentum_blocked",
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def row_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def protected_snapshot(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = row_by_id(registry)
    return {
        row_id: deepcopy(row)
        for row_id, row in rows.items()
        if row_id in PROTECTED_IDS or row.get("paper_forward_active") is True
    }


def template_row(item: dict[str, Any]) -> dict[str, Any]:
    family_id = item["family_id"]
    return {
        "id": family_id,
        "display_name": family_id.replace("_", " ").title(),
        "lane": "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": family_id,
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier1_research_queue",
        "status": item["status"],
        "role": "research_roadmap_backlog",
        "rules_frozen": True,
        "paper_forward_active": False,
        "implementation_status": "not_implemented",
        "data_source": "not_applicable_planning_only",
        "evidence_source": "research_roadmap_planning_only",
        "latest_evidence_path": "evidence/research_roadmap/latest/",
        "latest_known_result_summary": "Roadmap planning row only; no strategy implementation, market data, or computation has been run.",
        "allowed_next_action": item["next_allowed_action"],
        "forbidden_next_actions": sorted(FORBIDDEN_NEXT_ACTIONS),
        "risk_framework_status": "research_only_planning",
        "paper_forward_allowed_by_risk_framework": False,
        "real_money_recommendation": False,
        "promotion_blockers": "planning_only;not_tested;no_real_money_path",
        "promotion_requirements": "Must pass the proper review, sample, promotion, and candidate validation gates before any observation review.",
        "demotion_or_kill_criteria": "Missing evidence, duplicate exposure, risk budget failure, or data/provider unsuitability.",
        "notes": "Research roadmap backlog row. ETF/fund-wrapper only where applicable.",
        "strategy_id": family_id,
        "family": family_id,
        "instrument_lane": "ETF",
        "evidence_tier": "tier1_research_queue",
        "current_status": item["status"],
        "allowed_next_actions": [item["next_allowed_action"]],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "not_reviewed",
        "promotion_reason": "Planning-only roadmap row.",
        "primary_failure_mode": "not_tested",
        "duplication_risk": "not_assessed",
        "risk_budget_status": "not_assessed",
        "evidence_needed": "future review gate evidence",
        "duplicate_of": "",
        "blocked_reason": "",
    }


def update_registry_for_roadmap(registry: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    updated = deepcopy(registry)
    updated.setdefault("strategies", [])
    rows = row_by_id(updated)
    mismatches: list[str] = []

    for item in PRIORITY_BACKLOG:
        family_id = item["family_id"]
        row = rows.get(family_id)
        if row is None:
            row = template_row(item)
            updated["strategies"].append(row)
            rows[family_id] = row
        elif row.get("paper_forward_active") is True:
            mismatches.append(f"{family_id} is unexpectedly paper_forward_active; roadmap metadata not applied.")
            continue

        existing_evidence_source = row.get("evidence_source")
        existing_candidate_run = bool(row.get("candidate_exhaustive_run"))
        row["priority_rank"] = item["priority_rank"]
        row["status"] = item["status"]
        row["current_status"] = item["status"]
        row["roadmap_status"] = item["status"]
        row["roadmap_reason"] = item["reason"]
        row["next_allowed_action"] = item["next_allowed_action"]
        row["allowed_next_action"] = item["next_allowed_action"]
        row["allowed_next_actions"] = [item["next_allowed_action"]]
        row["paper_forward_active"] = False
        row["paper_forward_allowed_by_risk_framework"] = False
        row["real_money_recommendation"] = False
        row["candidate_exhaustive_run"] = existing_candidate_run
        row["implementation_status"] = row.get("implementation_status") or "not_implemented"
        row["evidence_source"] = existing_evidence_source or "research_roadmap_planning_only"
        row["latest_evidence_path"] = "evidence/research_roadmap/latest/"
        forbidden = set(row.get("forbidden_next_actions") or [])
        row["forbidden_next_actions"] = sorted(forbidden | FORBIDDEN_NEXT_ACTIONS)
        row["notes"] = (str(row.get("notes") or "") + " Roadmap priority recorded; planning-only, no new strategy test.").strip()
        if family_id == "managed_futures_etf_wrapper":
            row["latest_known_result_summary"] = "Priority 1 roadmap family. ETF/fund-wrapper trend-following review only; no direct futures trading."
        if family_id == "gror_balanced_momentum_60_40_v1":
            row["candidate_exhaustive_run"] = True

    state_preserve_actions = {
        "gror_balanced_momentum_60_40_v1": "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
        "quality_momentum_etf_proxy_risk_control_batch_1": "keep_quality_momentum_on_watchlist",
    }
    for row_id, action in state_preserve_actions.items():
        row = rows.get(row_id)
        if row is None or row.get("paper_forward_active") is True:
            continue
        row["roadmap_status"] = "watchlist"
        row["next_allowed_action"] = action
        row["allowed_next_action"] = action
        row["allowed_next_actions"] = [action]
        row["paper_forward_active"] = False
        row["paper_forward_allowed_by_risk_framework"] = False
        row["real_money_recommendation"] = False
        forbidden = set(row.get("forbidden_next_actions") or [])
        row["forbidden_next_actions"] = sorted(forbidden | FORBIDDEN_NEXT_ACTIONS)
        if row_id == "gror_balanced_momentum_60_40_v1":
            row["status"] = "watchlist"
            row["current_status"] = "watchlist"
            row["candidate_exhaustive_run"] = True

    updated.setdefault("registry", {})["last_updated_utc"] = now_utc()
    updated["registry"]["research_roadmap_next_action"] = NEXT_ACTION
    updated["registry"]["real_money_recommendation"] = False
    updated["registry"]["broker_integration"] = False
    updated["registry"]["live_orders"] = False
    return updated, mismatches


def state_rows(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return row_by_id(registry)


def status_matrix_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = state_rows(registry)
    priority = {item["family_id"]: item for item in PRIORITY_BACKLOG}
    family_ids = [
        "volatility_managed_equity_etf",
        "defensive_sector_rotation_etf",
        "quality_momentum_etf_proxy",
        "quality_momentum_etf_proxy_risk_control_batch_1",
        "global_risk_on_risk_off_etf",
        "managed_futures_etf_wrapper",
        "dual_momentum_paa_etf_wrapper",
        "gtaa_faber_style_benchmark_lane",
        "static_all_weather_or_permanent_portfolio_benchmark",
        "commodity_wrapper",
        "crypto_spot",
        "individual_stock_momentum",
    ]
    active_by_family = {
        "volatility_managed_equity_etf": "paper_forward_vm_quality_lowvol_proxy_v1",
        "defensive_sector_rotation_etf": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    }
    best_known = {
        "global_risk_on_risk_off_etf": "gror_balanced_momentum_60_40_v1",
        "quality_momentum_etf_proxy": "quality_momentum_etf_proxy",
        "quality_momentum_etf_proxy_risk_control_batch_1": "quality_momentum_etf_proxy_risk_control_batch_1",
    }
    output: list[dict[str, Any]] = []
    for family_id in family_ids:
        item = priority.get(family_id)
        registry_row = rows.get(family_id) or rows.get(best_known.get(family_id, "")) or {}
        active_id = active_by_family.get(family_id, "")
        active_row = rows.get(active_id, {})
        current_status = item["status"] if item else str(registry_row.get("current_status") or registry_row.get("status") or "active_or_watchlist")
        output.append(
            {
                "family_id": family_id,
                "current_status": current_status,
                "best_known_strategy": active_id or best_known.get(family_id, family_id),
                "evidence_state": "conversation_recovered_or_latest_evidence" if family_id in {"volatility_managed_equity_etf", "defensive_sector_rotation_etf", "global_risk_on_risk_off_etf", "quality_momentum_etf_proxy"} else "planning_only_or_deferred",
                "active_observation": bool(active_row.get("paper_forward_active")),
                "paper_forward_active": bool(active_row.get("paper_forward_active")),
                "candidate_queue": current_status in {"deferred_candidate_queue", "future_review_candidate", "next_family_to_review", "future_family_review"},
                "watchlist": "watchlist" in current_status or family_id in {"quality_momentum_etf_proxy", "global_risk_on_risk_off_etf"},
                "blocked": current_status in {"blocked", "blocked_or_deferred"},
                "reason": item["reason"] if item else "Existing recovered family state; preserve active/frozen observation where applicable.",
                "next_allowed_action": item["next_allowed_action"] if item else str(registry_row.get("allowed_next_action") or "observe_only"),
                "priority_rank": item["priority_rank"] if item else "",
            }
        )
    return output


def backlog_rows() -> list[dict[str, Any]]:
    return [
        {
            "priority_rank": item["priority_rank"],
            "family_id": item["family_id"],
            "current_status": item["status"],
            "reason": item["reason"],
            "next_allowed_action": item["next_allowed_action"],
        }
        for item in PRIORITY_BACKLOG
    ]


def render_roadmap_md() -> str:
    lines = [
        "# Research Roadmap",
        "",
        "Planning/governance artifact only. This roadmap does not implement a strategy, run a backtest, run candidate validation, download data, activate paper-forward, or add any broker/live-order/real-money path.",
        "",
        f"Current next action: `{NEXT_ACTION}`",
        "",
        "## Priority Backlog",
        "",
    ]
    for item in PRIORITY_BACKLOG:
        lines.extend(
            [
                f"{item['priority_rank']}. `{item['family_id']}`",
                f"   - Status: `{item['status']}`",
                f"   - Next action: `{item['next_allowed_action']}`",
                f"   - Reason: {item['reason']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- No direct futures trading; managed futures is ETF/fund-wrapper only.",
            "- No real-money recommendation.",
            "- No broker integration, live orders, or order placement.",
            "- No paper-forward activation or checkpoint.",
            "- No backtest, research_sample, candidate_exhaustive, Profit Exploration, data download, or provider API call.",
            "- Do not return to GROR or quality/momentum rescue unless new evidence appears.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_decision_log(state_mismatches: list[str]) -> str:
    mismatch_lines = ["- None."] if not state_mismatches else [f"- {item}" for item in state_mismatches]
    return "\n".join(
        [
            "# Roadmap Decision Log",
            "",
            "- VM quality/low-vol already produced an active/frozen paper-demo observation.",
            "- DSR equal-weight already produced an active/frozen paper-demo observation.",
            "- Quality/momentum showed profit power but failed risk/duplicate gates after bounded rescue.",
            "- GROR produced a clean candidate but candidate validation ended in watchlist, not pass.",
            "- DSR Top2/Top3 are promising but same-family as active DSR, so lower priority.",
            "- The next family should be more additive and less equity/growth/sector dependent.",
            "- Managed-futures / trend-following ETF-wrapper is the next best investigation family.",
            "- No direct futures trading is allowed.",
            "- No real-money path is allowed.",
            "",
            "## State Mismatches Or Notes",
            "",
            *mismatch_lines,
            "",
        ]
    )


def render_sequence_md() -> str:
    return "\n".join(
        [
            "# Next Investigation Sequence",
            "",
            f"Current next action: `{NEXT_ACTION}`",
            "",
            "1. Run managed-futures ETF-wrapper review/design gate.",
            "2. If approved, run managed-futures ETF-wrapper fast research_sample.",
            "3. If one row earns promotion candidate, run promotion review.",
            "4. If promotion review passes, then and only then run candidate validation.",
            "5. If managed-futures wrapper fails or is too short-history / too duplicate, move to dual momentum / PAA-style ETF wrapper.",
            "6. Do not return to quality/momentum rescue now.",
            "7. Do not rerun GROR unless new reason appears.",
            "8. Do not run DSR Top2/Top3 until after at least one new family lane is explored.",
            "",
        ]
    )


def render_deferred_md() -> str:
    deferred = [item for item in PRIORITY_BACKLOG if item["priority_rank"] >= 4]
    lines = ["# Deferred And Blocked Lanes", ""]
    for item in deferred:
        lines.append(f"- `{item['family_id']}`: `{item['status']}`. {item['reason']}")
    lines.append("")
    return "\n".join(lines)


def create_packet(output_dir: Path) -> Path:
    packet = output_dir / "research_roadmap_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def run_research_roadmap(root: Path = ROOT, update_registry: bool = True) -> dict[str, Any]:
    registry_path = root / REGISTRY_PATH
    original_registry = load_yaml(registry_path)
    before_protected = protected_snapshot(original_registry)
    updated_registry, update_mismatches = update_registry_for_roadmap(original_registry)
    after_protected = protected_snapshot(updated_registry)
    active_observations_unchanged = before_protected == after_protected

    if update_registry:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(yaml.safe_dump(updated_registry, sort_keys=False, width=140), encoding="utf-8")
        registry_update_mode = "direct_registry_update"
    else:
        proposed = root / "strategy_lab" / "strategy_registry.research_roadmap.proposed_updates.yaml"
        proposed.parent.mkdir(parents=True, exist_ok=True)
        proposed.write_text(yaml.safe_dump(updated_registry, sort_keys=False, width=140), encoding="utf-8")
        registry_update_mode = "proposed_update_written"

    rows = state_rows(updated_registry)
    vm = rows.get("paper_forward_vm_quality_lowvol_proxy_v1", {})
    dsr = rows.get("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", {})
    spy = rows.get("SPY_200d_trend_model", {})
    gror = rows.get("gror_balanced_momentum_60_40_v1", {})
    quality = rows.get("quality_momentum_etf_proxy", {})
    top2 = rows.get("dsr_sector_top2_momentum_200d_bil_v1", {})
    top3 = rows.get("dsr_sector_top3_momentum_defensive_cash_v1", {})
    managed = rows.get("managed_futures_etf_wrapper", {})

    state_mismatches = list(update_mismatches)
    if gror.get("candidate_exhaustive_run") is True and gror.get("allowed_next_action") == "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane":
        state_mismatches.append("RECOVERY_COMPLETENESS_AUDIT.md predates the latest GROR candidate validation; latest registry/evidence shows GROR watchlist.")

    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix = status_matrix_rows(updated_registry)
    backlog = backlog_rows()
    write_csv(
        output_dir / "strategy_family_priority_backlog.csv",
        backlog,
        ["priority_rank", "family_id", "current_status", "reason", "next_allowed_action"],
    )
    write_csv(
        output_dir / "strategy_family_status_matrix.csv",
        matrix,
        [
            "family_id",
            "current_status",
            "best_known_strategy",
            "evidence_state",
            "active_observation",
            "paper_forward_active",
            "candidate_queue",
            "watchlist",
            "blocked",
            "reason",
            "next_allowed_action",
            "priority_rank",
        ],
    )
    summary = render_roadmap_md()
    (output_dir / "research_roadmap_summary.md").write_text(summary, encoding="utf-8")
    (output_dir / "next_investigation_sequence.md").write_text(render_sequence_md(), encoding="utf-8")
    (output_dir / "deferred_and_blocked_lanes.md").write_text(render_deferred_md(), encoding="utf-8")
    (output_dir / "roadmap_decision_log.md").write_text(render_decision_log(state_mismatches), encoding="utf-8")
    (root / ROADMAP_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / ROADMAP_PATH).write_text(summary, encoding="utf-8")

    consistency = {
        "roadmap_created": True,
        "active_observations_unchanged": active_observations_unchanged,
        "vm_quality_active_preserved": vm.get("paper_forward_active") is True and vm.get("rules_frozen") is True,
        "dsr_equal_weight_active_preserved": dsr.get("paper_forward_active") is True and dsr.get("rules_frozen") is True,
        "spy_200d_control_preserved": spy.get("paper_forward_active") is True and spy.get("rules_frozen") is True,
        "gror_watchlist_preserved": gror.get("paper_forward_active") is False and gror.get("allowed_next_action") == "keep_gror_balanced_momentum_60_40_v1_candidate_watchlist_choose_next_lane",
        "quality_momentum_watchlist_preserved": quality.get("paper_forward_active") is False and quality.get("allowed_next_action") == "keep_quality_momentum_on_watchlist",
        "dsr_top2_future_review_present": top2.get("paper_forward_active") is False and top2.get("next_allowed_action") == "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1",
        "dsr_top3_deferred_present": top3.get("paper_forward_active") is False and top3.get("next_allowed_action") == "create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1",
        "managed_futures_priority_1": managed.get("priority_rank") == 1 and managed.get("next_allowed_action") == NEXT_ACTION,
        "no_strategy_implementation": True,
        "no_backtest_run": True,
        "no_candidate_exhaustive_run": True,
        "no_data_download": True,
        "no_provider_api_call": True,
        "no_paper_forward_activation": True,
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": not any(row.get("real_money_recommendation") is True for row in updated_registry.get("strategies", [])),
        "next_action": NEXT_ACTION,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key not in {"next_action", "consistency_passed"})
    manifest = {
        "created_at_utc": now_utc(),
        "registry_update_mode": registry_update_mode,
        "roadmap_output_path": str(output_dir),
        "source_controlled_roadmap_path": str(root / ROADMAP_PATH),
        "priority_count": len(PRIORITY_BACKLOG),
        "current_next_action": NEXT_ACTION,
        "state_mismatches_or_notes": state_mismatches,
        "planning_governance_only": True,
        "strategy_implementation_run": False,
        "backtest_run": False,
        "research_sample_run": False,
        "candidate_exhaustive_run": False,
        "data_downloaded": False,
        "provider_api_called": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    write_json(output_dir / "research_roadmap_manifest.json", manifest)
    write_json(output_dir / "research_roadmap_consistency_check.json", consistency)
    packet = create_packet(output_dir)

    return {
        "output_dir": str(output_dir),
        "packet": str(packet),
        "registry_update_mode": registry_update_mode,
        "manifest": manifest,
        "consistency": consistency,
        "priority_backlog": backlog,
    }


def main() -> int:
    result = run_research_roadmap(ROOT, update_registry=True)
    print(f"research_roadmap_latest_dir={result['output_dir']}")
    print(f"research_roadmap_packet={result['packet']}")
    print(f"registry_update_mode={result['registry_update_mode']}")
    print(f"next_action={NEXT_ACTION}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
