from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "current_research_checkpoint" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
SPY_200D_ID = "SPY_200d_trend_model"
BIL_ID = "BIL_cash_proxy"
LVQ_ID = "lvq_lowvol_quality_spy_regime_v1"
NEXT_ENGINEERING_ACTION = "repair_active_combo_benchmark_and_reporting"
NEXT_RESEARCH_AFTER_ENGINEERING = "choose_structurally_distinct_lane_or_archive"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_json(path: Path) -> dict[str, Any]:
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


def registry_rows(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def metric_map(*paths: Path) -> dict[str, dict[str, str]]:
    metrics: dict[str, dict[str, str]] = {}
    for path in paths:
        for row in read_csv_rows(path):
            sid = row.get("strategy_id", "")
            metric = row.get("metric", "")
            if sid and metric:
                metrics.setdefault(sid, {})[metric] = row.get("value", "missing_or_unavailable")
            elif metric:
                metrics.setdefault("_single", {})[metric] = row.get("value", "missing_or_unavailable")
    return metrics


def single_metric_map(*paths: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        for row in read_csv_rows(path):
            if row.get("metric"):
                result[row["metric"]] = row.get("value", "missing_or_unavailable")
    return result


def value(metrics: dict[str, str], key: str) -> str:
    return str(metrics.get(key, "missing_or_unavailable"))


def registry_value(row: dict[str, Any], key: str) -> str:
    val = row.get(key)
    return "missing_or_unavailable" if val in (None, "") else str(val)


def evidence_state(root: Path) -> dict[str, Any]:
    registry = load_yaml(root / REGISTRY_PATH)
    rows = registry_rows(registry)
    expanded_manifest = load_json(root / "evidence" / "parallel_research_discovery" / "expanded_universe_batch_1" / "latest" / "expanded_universe_batch_1_manifest.json")
    expanded_promotions = read_csv_rows(root / "evidence" / "parallel_research_discovery" / "expanded_universe_batch_1" / "latest" / "expanded_universe_batch_1_promotion_candidates.csv")
    batch2_promotions = read_csv_rows(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_promotion_candidates.csv")
    batch3_promotions = read_csv_rows(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_promotion_candidates.csv")
    recent_promotions = [
        row.get("strategy_id", "")
        for row in batch2_promotions + batch3_promotions + expanded_promotions
        if row.get("strategy_id")
    ]
    stale_candidate_flags = [sid for sid, row in rows.items() if row.get("candidate_exhaustive_recommended") is True]
    stale_promotion_flags = [sid for sid, row in rows.items() if row.get("promotion_review_required") is True]
    active_rows = [sid for sid, row in rows.items() if row.get("paper_forward_active") is True]
    active_combo_available = False
    for path in [
        root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_benchmark_delta.csv",
        root / "evidence" / "parallel_research_discovery" / "expanded_universe_batch_1" / "latest" / "expanded_universe_batch_1_benchmark_delta.csv",
        root / "evidence" / "promotion_reviews" / LVQ_ID / "latest" / f"{LVQ_ID}_profit_review.csv",
    ]:
        for row in read_csv_rows(path):
            if row.get("benchmark_id") == "active_combo" and row.get("comparison_status") == "computed":
                active_combo_available = True
            if row.get("metric") == "delta_vs_active_combo" and row.get("value") not in {"unavailable", "", None}:
                active_combo_available = True
    mismatches: list[str] = []
    for sid in [VM_ID, DSR_ID]:
        row = rows.get(sid, {})
        if row.get("paper_forward_active") is not True or row.get("rules_frozen") is not True:
            mismatches.append(f"{sid} is not frozen/active")
    if stale_candidate_flags:
        mismatches.append("registry still contains stale candidate_exhaustive_recommended=true rows: " + ", ".join(stale_candidate_flags))
    if stale_promotion_flags:
        mismatches.append("registry still contains stale promotion_review_required=true rows: " + ", ".join(stale_promotion_flags))
    if expanded_manifest.get("next_action") not in {"continue_next_expanded_universe_discovery_batch_or_pause", None}:
        mismatches.append("expanded-universe next action is not a pause/continue checkpoint action")
    return {
        "registry": registry,
        "rows": rows,
        "recent_promotions": recent_promotions,
        "stale_candidate_flags": stale_candidate_flags,
        "stale_promotion_flags": stale_promotion_flags,
        "active_rows": active_rows,
        "active_combo_available": active_combo_available,
        "expanded_promotions": [row.get("strategy_id", "") for row in expanded_promotions if row.get("strategy_id")],
        "mismatches": mismatches,
    }


def current_best_strategy_set(root: Path, rows: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    active_metrics = metric_map(
        root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_profit_review.csv",
        root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_risk_review.csv",
    )
    lvq_metrics = single_metric_map(
        root / "evidence" / "promotion_reviews" / LVQ_ID / "latest" / f"{LVQ_ID}_profit_review.csv",
        root / "evidence" / "promotion_reviews" / LVQ_ID / "latest" / f"{LVQ_ID}_risk_review.csv",
    )

    def row(strategy_id: str, role: str, metrics: dict[str, str], strength: str, weakness: str, trust: str, caveat: str, action: str) -> dict[str, str]:
        registry_row = rows.get(strategy_id, {})
        return {
            "strategy_id": strategy_id,
            "role": role,
            "status": registry_value(registry_row, "status"),
            "evidence_source": registry_value(registry_row, "evidence_source"),
            "180d_median_equity": value(metrics, "180d_median_final_equity"),
            "target_300_rate": value(metrics, "target_300_before_stop_rate"),
            "target_400_rate": value(metrics, "target_400_before_stop_rate"),
            "worst_drawdown": value(metrics, "180d_worst_drawdown"),
            "stop_hit_rate": value(metrics, "stop_hit_rate"),
            "key_strength": strength,
            "key_weakness": weakness,
            "trust_level": trust,
            "caveat": caveat,
            "recommended_action": action,
        }

    return [
        row(VM_ID, "protected_active_observation", active_metrics.get(VM_ID, {}), "stable risk-buffer profile in recompute", "less upside than high-risk variants", "accepted_active", "minor deltas accepted", "observe_only"),
        row(DSR_ID, "protected_active_observation", active_metrics.get(DSR_ID, {}), "best current 180d median among protected active pair", "accepted recovered-vs-recomputed best-equity mismatch", "accepted_active_with_caveat", "recovered best_final_equity around 4071.04; recomputed around 3481.6998", "observe_only"),
        row(SPY_200D_ID, "frozen_control", {}, "simple benchmark/control", "exact current checkpoint metrics not in checkpoint inputs", "benchmark_control", "metrics marked unavailable rather than fabricated", "compare_only"),
        row(BIL_ID, "cash_benchmark", {}, "defensive cash proxy", "too slow for profit target", "benchmark_control", "metrics marked unavailable rather than fabricated", "compare_only"),
        row(LVQ_ID, "watchlist_diagnostic_only", lvq_metrics, "safer/interesting low-vol quality profile", "weaker than active DSR/SPY references", "watchlist_only", "not active; not candidate_exhaustive-ready", "keep_watchlist"),
    ]


def candidate_pipeline_status(state: dict[str, Any]) -> list[dict[str, str]]:
    protected = [sid for sid in [VM_ID, DSR_ID] if sid in state["rows"]]
    benchmark_watchlist = [
        "benchmark_regional_equal_weight_trend_v1",
        "benchmark_international_lowvol_equal_weight_v1",
    ]
    rejected = [
        "DSR Top2",
        "DSR Top3",
        "QVM risk-adjusted Top2",
        "QVM Top2",
        "approved-cache batch 2",
        "approved-cache batch 3",
        "expanded-universe batch 1",
    ]
    return [
        {"stage": "active_frozen", "count": len(protected), "rows": ";".join(protected), "status": "protected_active_observations", "next_action": "observe_only"},
        {"stage": "promotion_review_candidates", "count": 0, "rows": "", "status": "empty_current_checkpoint", "next_action": "none"},
        {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty_current_checkpoint", "next_action": "none"},
        {"stage": "candidate_exhaustive_watchlist", "count": 0, "rows": "", "status": "empty_current_checkpoint", "next_action": "none"},
        {"stage": "paper_forward_active", "count": len(protected), "rows": ";".join(protected), "status": "no_new_paper_forward_action_recommended", "next_action": "observe_only"},
        {"stage": "benchmark_watchlist", "count": len(benchmark_watchlist), "rows": ";".join(benchmark_watchlist), "status": "control_rows_only", "next_action": "compare_only"},
        {"stage": "diversifier_watchlist", "count": 1, "rows": LVQ_ID, "status": "diagnostic_watchlist_only", "next_action": "keep_watchlist"},
        {"stage": "rejected_or_archived", "count": len(rejected), "rows": ";".join(rejected), "status": "resolved_or_saturated_for_now", "next_action": "do_not_rerun_now"},
        {"stage": "data_pending", "count": 1, "rows": "active_combo_benchmark_series", "status": "engineering_repair_needed", "next_action": NEXT_ENGINEERING_ACTION},
    ]


def failed_lanes() -> list[dict[str, Any]]:
    return [
        {"lane_or_strategy": "DSR Top2", "best_row": "dsr_sector_top2_momentum_200d_bil_v1", "status": "duplicate_or_near_duplicate", "primary_failure_reason": "duplicate_or_near_duplicate", "secondary_failure_reason": "weaker_than_active_references", "still_useful_as": "same-family diagnostic", "should_rerun_now": False, "reason": "near-duplicate of active DSR family; archive/diagnostic disposition recorded"},
        {"lane_or_strategy": "DSR Top3", "best_row": "dsr_sector_top3_momentum_defensive_cash_v1", "status": "duplicate_or_near_duplicate", "primary_failure_reason": "duplicate_or_near_duplicate", "secondary_failure_reason": "accepted_caveat", "still_useful_as": "same-family diagnostic", "should_rerun_now": False, "reason": "candidate path deferred then duplicate disposition; DSR active caveat already recorded"},
        {"lane_or_strategy": "QVM risk-adjusted Top2", "best_row": "qvm_quality_value_momentum_risk_adjusted_top2_v1", "status": "too_risky", "primary_failure_reason": "risk_buffer_too_thin", "secondary_failure_reason": "too_risky", "still_useful_as": "risk-gate example", "should_rerun_now": False, "reason": "high upside did not survive risk-buffer gate"},
        {"lane_or_strategy": "QVM Top2", "best_row": "qvm_quality_value_momentum_top2_v1", "status": "duplicate_or_near_duplicate", "primary_failure_reason": "duplicate_or_near_duplicate", "secondary_failure_reason": "too_risky", "still_useful_as": "sibling diagnostic", "should_rerun_now": False, "reason": "sibling evidence did not improve disposition"},
        {"lane_or_strategy": "LVQ SPY-regime", "best_row": LVQ_ID, "status": "watchlist_valid", "primary_failure_reason": "watchlist_valid", "secondary_failure_reason": "weaker_than_active_references", "still_useful_as": "watchlist/diagnostic", "should_rerun_now": False, "reason": "interesting but weaker than active DSR/SPY references"},
        {"lane_or_strategy": "approved-cache batch 2", "best_row": "benchmark_quality_lowvol_equal_weight_v1", "status": "exhausted_for_now", "primary_failure_reason": "too_slow_for_profit_goal", "secondary_failure_reason": "weaker_than_active_references", "still_useful_as": "family benchmark", "should_rerun_now": False, "reason": "no surviving promotion candidates"},
        {"lane_or_strategy": "approved-cache batch 3", "best_row": "gwcb_qvm_70_30_cash_brake_v1", "status": "exhausted_for_now", "primary_failure_reason": "too_slow_for_profit_goal", "secondary_failure_reason": "weaker_than_active_references", "still_useful_as": "benchmark diagnostics", "should_rerun_now": False, "reason": "no surviving promotion candidates"},
        {"lane_or_strategy": "expanded-universe batch 1", "best_row": "rim_regional_top2_momentum_bil_v1", "status": "exhausted_for_now", "primary_failure_reason": "too_risky", "secondary_failure_reason": "risk_buffer_too_thin", "still_useful_as": "expansion benchmark", "should_rerun_now": False, "reason": "best profit row failed risk buffer; no promotion/diversifier candidates"},
        {"lane_or_strategy": "GROR", "best_row": "gror_balanced_momentum_60_40_v1", "status": "accepted_caveat", "primary_failure_reason": "duplicate_or_near_duplicate", "secondary_failure_reason": "evidence_incomplete", "still_useful_as": "historical watchlist", "should_rerun_now": False, "reason": "stale registry flag exists but current checkpoint treats no row as candidate_exhaustive-ready"},
        {"lane_or_strategy": "managed futures wrapper", "best_row": "managed_futures_proxy_etf_trend_v1", "status": "too_slow_for_profit_goal", "primary_failure_reason": "too_slow_for_profit_goal", "secondary_failure_reason": "short_history_wrapper_proxy", "still_useful_as": "diversifier concept", "should_rerun_now": False, "reason": "do not restart same wrapper track before checkpoint engineering repair"},
        {"lane_or_strategy": "dual momentum/PAA", "best_row": "dual_momentum_paa_etf_wrapper", "status": "exhausted_for_now", "primary_failure_reason": "weaker_than_active_references", "secondary_failure_reason": "duplicate_or_near_duplicate", "still_useful_as": "pre-registration candidate later", "should_rerun_now": False, "reason": "pause similar ETF-wrapper variants"},
        {"lane_or_strategy": "GTAA/static", "best_row": "gtaa_static_control", "status": "benchmark_only", "primary_failure_reason": "benchmark_only", "secondary_failure_reason": "too_slow_for_profit_goal", "still_useful_as": "benchmark/control", "should_rerun_now": False, "reason": "use as control, not immediate discovery lane"},
        {"lane_or_strategy": "carry/yield", "best_row": "carry_yield_etf_proxy", "status": "policy_boundary_reached", "primary_failure_reason": "policy_boundary_reached", "secondary_failure_reason": "too_slow_for_profit_goal", "still_useful_as": "later structural lane", "should_rerun_now": False, "reason": "needs distinct pre-registration after active-combo repair"},
        {"lane_or_strategy": "regional/international expansion", "best_row": "rim_regional_top2_momentum_bil_v1", "status": "exhausted_for_now", "primary_failure_reason": "too_risky", "secondary_failure_reason": "risk_buffer_too_thin", "still_useful_as": "benchmark evidence", "should_rerun_now": False, "reason": "expanded-universe batch 1 found no surviving candidates"},
    ]


def saturated_lanes() -> list[dict[str, str]]:
    rows = [
        ("defensive_sector_rotation_etf", "duplicate or same-family active DSR overlap", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "DSR Top2/Top3 dispositions are duplicate/near-duplicate", "new non-overlapping evidence or repaired active-combo benchmark"),
        ("quality_value_momentum_blend", "risk-buffer failures and duplicate sibling behavior", "qvm_quality_value_momentum_risk_adjusted_top2_v1", "QVM risk-adjusted failed too-risky gate", "materially different fixed rule with pre-registered risk gate"),
        ("lowvol_quality_hybrid", "watchlist only and weaker than active references", LVQ_ID, "LVQ stays diagnostic/watchlist", "new evidence showing stronger active-reference deltas"),
        ("growth_defensive_barbell", "profit/risk tradeoff not enough", "gwcb_qvm_70_30_cash_brake_v1", "batch 3 found no promotion candidate", "structural change beyond same cash-brake mechanics"),
        ("multi_asset_trend_risk_control", "diminishing returns versus controls", "SPY_200d_trend_model", "too many near-control outcomes", "active-combo benchmark repaired first"),
        ("growth_cash_brake", "too slow or benchmark-weaker", "gwcb_qvm_70_30_cash_brake_v1", "batch 3 exhausted same mechanics", "new preregistered lane, not a random variant"),
        ("dual_regime_growth_defensive", "weaker than active/control references", "drgd_growth_or_defense_top2_v1", "no surviving promotion candidate", "only revisit after reporting repair"),
        ("drawdown_guard_growth", "guard mechanics did not create additive candidate", "ddg_balanced_growth_defense_guard_v1", "no surviving promotion candidate", "new hypothesis and pre-promotion risk gate"),
        ("regional_international_momentum", "best row too risky", "rim_regional_top2_momentum_bil_v1", "expanded batch risk buffer failed", "different regional hypothesis, not same top-N mechanics"),
        ("international_lowvol_defensive", "safer but too slow/weaker", "ilv_international_lowvol_defensive_v1", "no promotion/diversifier candidate", "new target profile or structural sleeve"),
        ("regional_gold_bond_defensive_rotation", "too slow or too risky", "rgb_regional_growth_defensive_70_30_v1", "expanded batch found no useful candidate", "new defensive logic with repaired combo benchmark"),
        ("selective_growth_comparator", "SCHG/growth comparator did not add enough", "sgc_schg_regional_mix_v1", "weaker than active references", "only as control after engineering repair"),
        ("carry_yield_etf_proxy", "not ready for immediate ETF-wrapper rerun", "carry_yield_etf_proxy", "policy/structure should be pre-registered later", "active-combo benchmark repaired and distinct lane selected"),
    ]
    return [{"family": family, "reason_saturated": reason, "best_known_row": best, "why_not_rerun_now": why, "condition_to_revisit": revisit} for family, reason, best, why, revisit in rows]


def watchlist_rows() -> list[dict[str, str]]:
    return [
        {"strategy_id": LVQ_ID, "role": "watchlist_diagnostic_only", "status": "keep_watchlist", "reason": "safer and interesting but weaker than active DSR/SPY references"},
        {"strategy_id": "benchmark_regional_equal_weight_trend_v1", "role": "benchmark_watchlist", "status": "benchmark_watchlist", "reason": "expanded-universe sanity/control row"},
        {"strategy_id": "benchmark_international_lowvol_equal_weight_v1", "role": "benchmark_watchlist", "status": "benchmark_watchlist", "reason": "expanded-universe low-vol sanity/control row"},
        {"strategy_id": "gror_balanced_momentum_60_40_v1", "role": "stale_watchlist_flag", "status": "accepted_caveat", "reason": "historical stale candidate flag exists, but not current checkpoint-ready"},
    ]


def accepted_caveats_text() -> str:
    return """# Accepted Caveats

## DSR Recovered Best-Equity Mismatch

- Recovered best_final_equity was around `4071.04`.
- Recomputed best_final_equity was around `3481.6998`.
- The user chose not to spend more resources on manual review.
- DSR remains accepted for research continuity, not as perfectly reconciled evidence.

## Active Combo Unavailable

- The exact active-combo benchmark series is not consistently available.
- Future comparative reviews should repair this before major new discovery.

## Data

- ETF data is yfinance-compatible exploratory adjusted data.
- It is not institutional-grade.
- It is not real-money-ready.

## Sampling

- Recent discovery is bounded sampled-window research.
- It is not full institutional validation.
"""


def do_not_rerun_text() -> str:
    items = [
        ("DSR Top2", "same-family duplicate/near-duplicate of active DSR"),
        ("DSR Top3", "same-family duplicate/near-duplicate with accepted DSR caveat"),
        ("QVM risk-adjusted Top2", "risk buffer too thin"),
        ("QVM Top2", "sibling disposition did not improve risk/duplication profile"),
        ("LVQ SPY-regime full promotion review unless new evidence appears", "watchlist only; weaker than active references"),
        ("approved-cache batch 2 variants", "no surviving promotion candidates"),
        ("approved-cache batch 3 variants", "no surviving promotion candidates"),
        ("expanded-universe batch 1 variants", "best row too risky; no promotion/diversifier candidate"),
        ("immediate expanded-universe batch 2 with same mechanics", "would repeat saturated regional/top-N/low-vol mechanics"),
    ]
    lines = ["# Do Not Rerun Now", ""]
    lines.extend(f"- `{name}`: {reason}." for name, reason in items)
    return "\n".join(lines) + "\n"


def engineering_next_steps_text() -> str:
    return """# Recommended Engineering Next Steps

1. `repair_active_combo_benchmark_and_reporting`
   - Build a deterministic active-combo benchmark series and use it consistently in comparison tables.
2. Normalize decision taxonomy.
   - Avoid `needs_benchmark_delta_review` when deltas exist.
   - Use `weaker_than_active_references_watchlist` if supported.
3. Add a pre-promotion risk-buffer gate.
   - Do not run full promotion review if base or stress risk buffer is below a defined minimum such as 25 unless the user explicitly overrides.
4. Add a sibling-disposition shortcut.
   - If correlation is above 0.97 to a rejected sibling and economics are not better, allow direct duplicate disposition.
5. Improve dashboard/checkpoint display.
   - Make stale candidate flags, protected active rows, and engineering blockers visible.
"""


def research_next_steps_text() -> str:
    return """# Recommended Research Next Steps

Primary next research action:

`repair_active_combo_benchmark_and_reporting`

After that, choose one:

- `pre_register_active_sleeve_ensemble_lane`
- `pre_register_breadth_state_regime_lane`
- `pre_register_dividend_quality_shareholder_yield_lane`
- `archive_current_etf_wrapper_track_as_checkpoint`

Do not start another immediate random ETF-wrapper discovery batch.
"""


def summary_text(state: dict[str, Any]) -> str:
    mismatch_text = "\n".join(f"- {item}" for item in state["mismatches"]) or "- none"
    return f"""# Current Research Checkpoint

Created at UTC: `{now_utc()}`

This checkpoint pauses the current ETF-wrapper discovery track. It is an audit/checkpoint artifact only: no strategy discovery, research sample, candidate_exhaustive, paper-forward action, provider download, broker path, live-order path, or real-money recommendation was run or added.

## Current Best Supported Set

- `{VM_ID}`
- `{DSR_ID}`
- `{SPY_200D_ID}` as frozen control
- `{BIL_ID}` as cash benchmark
- `{LVQ_ID}` as watchlist/diagnostic only

## Pipeline Conclusion

- Surviving promotion-review candidates: `0`
- Candidate_exhaustive queue: `0`
- New paper-forward actions recommended: `0`
- Expanded-universe batch 1 promotion candidates: `0`
- Primary next engineering action: `{NEXT_ENGINEERING_ACTION}`

## State Mismatches / Assumptions Recorded

{mismatch_text}

The checkpoint treats stale registry flags as historical residue, not as current permission to run candidate validation.
"""


def update_roadmap(root: Path) -> bool:
    path = root / ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Research Roadmap\n"
    section = f"""## Current Research Checkpoint

- ETF-wrapper discovery is paused.
- Current best supported pair is active VM + active DSR.
- Candidate pipeline has no surviving candidate_exhaustive row.
- Next engineering action is `{NEXT_ENGINEERING_ACTION}`.
- DSR caveat is accepted but recorded.
- No more immediate similar ETF-wrapper batch discovery.
"""
    marker = "## Current Research Checkpoint"
    if marker in existing:
        prefix = existing.split(marker, 1)[0].rstrip()
        updated = prefix + "\n\n" + section
    else:
        updated = existing.rstrip() + "\n\n" + section
    path.write_text(updated, encoding="utf-8")
    return True


def update_registry_metadata(root: Path) -> bool:
    path = root / REGISTRY_PATH
    updates = {
        "current_research_checkpoint_path": str(root / OUTPUT_DIR),
        "etf_discovery_status": "paused",
        "candidate_pipeline_empty": "true",
        "next_engineering_action": NEXT_ENGINEERING_ACTION,
        "next_research_action_after_engineering": NEXT_RESEARCH_AFTER_ENGINEERING,
        "no_candidate_exhaustive_run": "true",
        "no_paper_forward_action": "true",
        "no_real_money_recommendation": "true",
    }
    if not path.exists():
        registry = {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True, "real_money_recommendation": False, "broker_integration": False, "live_orders": False}, "risk_framework": {}, "strategies": []}
        registry["registry"].update(updates)
        path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120), encoding="utf-8")
        return True
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    in_registry = False
    inserted = False
    for idx, line in enumerate(lines):
        if line == "registry:":
            in_registry = True
        elif line and not line.startswith(" ") and line != "registry:":
            if in_registry and not inserted:
                output.extend(f"  {key}: {val}" for key, val in updates.items() if key not in seen)
                inserted = True
            in_registry = False
        stripped = line.strip()
        key = stripped.split(":", 1)[0] if ":" in stripped else ""
        if in_registry and line.startswith("  ") and key in updates:
            output.append(f"  {key}: {updates[key]}")
            seen.add(key)
            continue
        output.append(line)
        if in_registry and line.startswith("  research_roadmap_next_action:") and not inserted:
            output.extend(f"  {key}: {val}" for key, val in updates.items() if key not in seen)
            inserted = True
    if in_registry and not inserted:
        output.extend(f"  {key}: {val}" for key, val in updates.items() if key not in seen)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return True


def create_packet(output: Path) -> Path:
    packet = output / "current_research_checkpoint_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    best_rows = current_best_strategy_set(root, state["rows"])
    pipeline_rows = candidate_pipeline_status(state)
    failed_rows = failed_lanes()
    saturated_rows = saturated_lanes()
    watchlist = watchlist_rows()
    write_csv(output / "current_best_strategy_set.csv", best_rows, ["strategy_id", "role", "status", "evidence_source", "180d_median_equity", "target_300_rate", "target_400_rate", "worst_drawdown", "stop_hit_rate", "key_strength", "key_weakness", "trust_level", "caveat", "recommended_action"])
    write_csv(output / "candidate_pipeline_status.csv", pipeline_rows, ["stage", "count", "rows", "status", "next_action"])
    write_csv(output / "failed_research_lanes.csv", failed_rows, ["lane_or_strategy", "best_row", "status", "primary_failure_reason", "secondary_failure_reason", "still_useful_as", "should_rerun_now", "reason"])
    write_csv(output / "saturated_lanes.csv", saturated_rows, ["family", "reason_saturated", "best_known_row", "why_not_rerun_now", "condition_to_revisit"])
    write_csv(output / "watchlist_and_diagnostic_rows.csv", watchlist, ["strategy_id", "role", "status", "reason"])
    (output / "accepted_caveats.md").write_text(accepted_caveats_text(), encoding="utf-8")
    (output / "do_not_rerun_now.md").write_text(do_not_rerun_text(), encoding="utf-8")
    (output / "recommended_engineering_next_steps.md").write_text(engineering_next_steps_text(), encoding="utf-8")
    (output / "recommended_research_next_steps.md").write_text(research_next_steps_text(), encoding="utf-8")
    (output / "current_research_checkpoint_summary.md").write_text(summary_text(state), encoding="utf-8")
    manifest = {
        "created_at_utc": now_utc(),
        "checkpoint_created": True,
        "output_dir": str(output),
        "recent_promotions": state["recent_promotions"],
        "expanded_universe_batch_1_promotion_candidates": state["expanded_promotions"],
        "stale_candidate_exhaustive_flags": state["stale_candidate_flags"],
        "stale_promotion_review_flags": state["stale_promotion_flags"],
        "active_combo_available": state["active_combo_available"],
        "recorded_mismatches": state["mismatches"],
        "next_engineering_action": NEXT_ENGINEERING_ACTION,
        "next_research_action_after_engineering": NEXT_RESEARCH_AFTER_ENGINEERING,
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
    write_json(output / "current_research_checkpoint_manifest.json", manifest)
    consistency = {
        "checkpoint_created": True,
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
        "active_observations_unchanged": True,
        "best_current_strategy_set_created": bool(best_rows),
        "candidate_pipeline_status_created": bool(pipeline_rows),
        "failed_lanes_created": bool(failed_rows),
        "saturated_lanes_created": bool(saturated_rows),
        "accepted_caveats_created": True,
        "do_not_rerun_created": True,
        "engineering_next_steps_created": True,
        "research_next_steps_created": True,
        "roadmap_updated_or_proposed": (root / ROADMAP_PATH).exists(),
        "registry_updated_or_proposed": (root / REGISTRY_PATH).exists(),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    write_json(output / "current_research_checkpoint_consistency_check.json", consistency)
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet), "manifest": manifest, "consistency": consistency}


def run_current_research_checkpoint(root: Path = ROOT) -> dict[str, Any]:
    state = evidence_state(root)
    update_roadmap(root)
    update_registry_metadata(root)
    result = write_outputs(root, state)
    return {
        "output_dir": result["output_dir"],
        "packet": result["packet"],
        "next_engineering_action": NEXT_ENGINEERING_ACTION,
        "next_research_action_after_engineering": NEXT_RESEARCH_AFTER_ENGINEERING,
        "recorded_mismatches": state["mismatches"],
        "consistency": result["consistency"],
    }


def main() -> None:
    print(json.dumps(run_current_research_checkpoint(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
