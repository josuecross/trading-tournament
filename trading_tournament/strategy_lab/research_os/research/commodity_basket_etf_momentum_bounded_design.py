from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


LANE_ID = "commodity_basket_etf_momentum_bounded_lane_v1"
FAMILY_ID = "commodity_basket_etf_momentum_v1"
SELECTED_TASK = "design_commodity_basket_etf_momentum_bounded_lane"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "commodity_basket_etf_momentum_bounded_design" / "latest"

QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
RESEARCH_STATE = Path("evidence") / "research_state" / "latest" / "research_state_manifest.json"
QUEUE_BLOCKER_DIR = Path("evidence") / "research_recovery" / "profit_research_queue_next_task_selection" / "latest"
COMMODITY_EXPLORATORY_DIR = Path("evidence") / "commodity_exploratory" / "latest"
COMMODITY_DIAGNOSTICS_DIR = (
    Path("evidence") / "commodity_lab" / "risk_control_batch1_diagnostics_completion" / "latest"
)
LOCAL_CACHE = Path("data") / "cache"

RUN_READY = "commodity_basket_bounded_design_run_ready"
RUN_BLOCKED = "commodity_basket_bounded_design_blocked"
NEXT_ACTION_READY = "run_commodity_basket_etf_momentum_bounded_lane"
NEXT_ACTION_BLOCKED = "restore_or_revalidate_local_commodity_cache_before_bounded_run"
VALID_READINESS = {RUN_READY, RUN_BLOCKED}
VALID_NEXT_ACTIONS = {NEXT_ACTION_READY, NEXT_ACTION_BLOCKED}

REQUIRED_CACHE_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD")
COMMODITY_WRAPPER_SYMBOLS = ("DBC", "PDBC", "COMT", "GSG", "USCI")

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_registry_id",
    "concept",
    "universe_group",
    "universe",
    "lookback_days",
    "top_n",
    "rebalance_frequency",
    "rule_summary",
    "baseline_variant_id",
    "comparator_references",
    "source_evidence_path",
    "bil_cash_rule",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "zero_weight_policy",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

REQUIRED_OUTPUTS = (
    "commodity_basket_bounded_design_manifest.json",
    "commodity_basket_bounded_design_summary.md",
    "source_commodity_evidence_review.md",
    "commodity_basket_bounded_variant_design_table.csv",
    "commodity_basket_bounded_variant_design_table.md",
    "baseline_comparator_policy.md",
    "numeric_success_failure_criteria.md",
    "exposure_invariant_policy.md",
    "guardrail_checklist.md",
    "local_cache_preflight.md",
    "queue_source_of_truth_update.md",
    "do_not_promote_from_commodity_basket_design.md",
    "commodity_basket_bounded_design_next_action.md",
    "commodity_basket_bounded_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def build_design_rows() -> list[dict[str, Any]]:
    common = {
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "rebalance_frequency": "monthly",
        "comparator_references": "SPY|SPY_200d_frozen_control|BIL_cash_proxy|static_all_weather_benchmark_control|active_VM_DSR_combo_when_supported",
        "bil_cash_rule": "BIL/cash is replacement or remainder only; it must not accumulate above total exposure 1.0.",
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "zero_weight_policy": "zero target weights remain zero until the next explicit rebalance target; stale-forward-filling old nonzero allocations into zero targets is forbidden",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    return [
        {
            **common,
            "variant_id": "cbe_bounded_base_tsmom_top2_126_v1",
            "variant_role": "base_reference",
            "source_registry_id": "commodity_basket_tsmom_top2_v1",
            "concept": "commodity_tsmom_top2_126",
            "universe_group": "commodity_wrappers_plus_cash",
            "universe": "DBC|PDBC|COMT|GSG|USCI|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Rank DBC/PDBC/COMT/GSG/USCI by 126-day momentum monthly; hold top 2 wrappers only when selected wrapper 126-day return is positive; unused or failed weight goes to BIL.",
            "baseline_variant_id": "commodity_basket_tsmom_top2_v1",
            "source_evidence_path": "evidence/commodity_exploratory/latest",
        },
        {
            **common,
            "variant_id": "cbe_bounded_top2_200d_filter_126_v1",
            "variant_role": "risk_control_reference",
            "source_registry_id": "commodity_basket_tsmom_top2_200d_filter_v1",
            "concept": "commodity_tsmom_top2_126_200d_filter",
            "universe_group": "commodity_wrappers_plus_cash",
            "universe": "DBC|PDBC|COMT|GSG|USCI|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Use the same top-2 126-day commodity wrapper momentum rule, but require each selected wrapper close above its 200-day SMA; failed weight goes to BIL.",
            "baseline_variant_id": "commodity_basket_tsmom_top2_v1",
            "source_evidence_path": "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
        },
        {
            **common,
            "variant_id": "cbe_bounded_top2_half_bil_126_v1",
            "variant_role": "defensive_context",
            "source_registry_id": "commodity_basket_tsmom_top2_half_bil_v1",
            "concept": "commodity_tsmom_top2_126_half_bil",
            "universe_group": "commodity_wrappers_plus_cash",
            "universe": "DBC|PDBC|COMT|GSG|USCI|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Hold fixed 50% base commodity top-2 sleeve and 50% BIL. This is a defensive context row, not a tuned allocation.",
            "baseline_variant_id": "commodity_basket_tsmom_top2_v1",
            "source_evidence_path": "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
        },
        {
            **common,
            "variant_id": "cbe_bounded_combo_plus_commodity_80_20_v1",
            "variant_role": "portfolio_contribution_context",
            "source_registry_id": "combo_plus_commodity_basket_80_20_v1",
            "concept": "active_combo_plus_commodity_80_20",
            "universe_group": "active_combo_plus_commodity_wrappers",
            "universe": "SPY|GLD|BIL|DBC|PDBC|COMT|GSG|USCI",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Hold fixed 80% combo_SPY200d_GLD_50_50_v1 and 20% commodity_basket_tsmom_top2_v1 for contribution diagnostics only; do not alter active VM/DSR or combo rules.",
            "baseline_variant_id": "combo_SPY200d_GLD_50_50_v1",
            "source_evidence_path": "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
        },
        {
            **common,
            "variant_id": "cbe_bounded_gld_control_v1",
            "variant_role": "comparator_control",
            "source_registry_id": "GLD_buy_hold",
            "concept": "gld_buy_hold_control",
            "universe_group": "control",
            "universe": "GLD",
            "lookback_days": 0,
            "top_n": 1,
            "rule_summary": "Same-window GLD buy-and-hold control only; not a commodity-basket candidate row.",
            "baseline_variant_id": "GLD_buy_hold",
            "source_evidence_path": "strategy_lab/strategy_registry.yaml",
        },
        {
            **common,
            "variant_id": "cbe_bounded_bil_control_v1",
            "variant_role": "cash_control",
            "source_registry_id": "BIL_cash_proxy",
            "concept": "bil_cash_control",
            "universe_group": "control",
            "universe": "BIL",
            "lookback_days": 0,
            "top_n": 1,
            "rule_summary": "Same-window BIL cash-proxy control only; not a commodity-basket candidate row.",
            "baseline_variant_id": "BIL_cash_proxy",
            "source_evidence_path": "strategy_lab/strategy_registry.yaml",
        },
    ]


def source_inventory(root: Path) -> list[dict[str, Any]]:
    paths = [
        QUEUE,
        REGISTRY,
        ROADMAP,
        RESEARCH_STATE,
        QUEUE_BLOCKER_DIR / "queue_next_task_selection_manifest.json",
        COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_manifest.json",
        COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_results.csv",
        COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_risk_summary.csv",
        COMMODITY_DIAGNOSTICS_DIR / "risk_control_batch1_diagnostics_completion_manifest.json",
        COMMODITY_DIAGNOSTICS_DIR / "COMMODITY_80_20_INCREMENTAL_VALUE_AUDIT.md",
        COMMODITY_DIAGNOSTICS_DIR / "DIAGNOSTICS_COMPLETION_DECISION.md",
    ]
    return [{"path": str((root / path).resolve()), "exists": (root / path).exists()} for path in paths]


def local_cache_status(root: Path) -> dict[str, Any]:
    available = []
    missing = []
    for symbol in REQUIRED_CACHE_SYMBOLS:
        path = root / LOCAL_CACHE / f"{symbol}.csv"
        if path.exists():
            available.append(symbol)
        else:
            missing.append(symbol)
    return {
        "required_symbols": list(REQUIRED_CACHE_SYMBOLS),
        "commodity_wrapper_symbols": list(COMMODITY_WRAPPER_SYMBOLS),
        "available_symbols": available,
        "missing_symbols": missing,
        "missing_commodity_wrapper_symbols": [symbol for symbol in COMMODITY_WRAPPER_SYMBOLS if symbol in missing],
        "cache_complete": len(missing) == 0,
    }


def load_sources(root: Path) -> dict[str, Any]:
    return {
        "queue_text": read_text(root / QUEUE),
        "registry_text": read_text(root / REGISTRY),
        "roadmap_text": read_text(root / ROADMAP),
        "research_state": read_json(root / RESEARCH_STATE),
        "queue_blocker_manifest": read_json(
            root / QUEUE_BLOCKER_DIR / "queue_next_task_selection_manifest.json"
        ),
        "commodity_manifest": read_json(root / COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_manifest.json"),
        "commodity_results": read_csv(root / COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_results.csv"),
        "commodity_risk_summary": read_csv(
            root / COMMODITY_EXPLORATORY_DIR / "commodity_exploratory_risk_summary.csv"
        ),
        "diagnostics_manifest": read_json(
            root / COMMODITY_DIAGNOSTICS_DIR / "risk_control_batch1_diagnostics_completion_manifest.json"
        ),
        "diagnostics_decision": read_text(
            root / COMMODITY_DIAGNOSTICS_DIR / "DIAGNOSTICS_COMPLETION_DECISION.md"
        ),
        "incremental_value_audit": read_text(
            root / COMMODITY_DIAGNOSTICS_DIR / "COMMODITY_80_20_INCREMENTAL_VALUE_AUDIT.md"
        ),
    }


def readiness(rows: list[dict[str, Any]], inventory: list[dict[str, Any]], cache: dict[str, Any]) -> tuple[str, str, str]:
    blockers: list[str] = []
    variant_ids = [row["variant_id"] for row in rows]
    if len(rows) < 6 or len(rows) > 12:
        blockers.append("planned row count is outside 6 to 12")
    if len(set(variant_ids)) != len(variant_ids):
        blockers.append("variant IDs are not unique")
    if any(not item["exists"] for item in inventory):
        blockers.append("required source evidence is missing")
    if cache["missing_commodity_wrapper_symbols"]:
        blockers.append(
            "missing current local commodity wrapper cache for "
            + "|".join(cache["missing_commodity_wrapper_symbols"])
        )
    if blockers:
        return RUN_BLOCKED, NEXT_ACTION_BLOCKED, "; ".join(blockers)
    return RUN_READY, NEXT_ACTION_READY, "none"


def build_manifest(
    root: Path,
    created: str,
    output: Path,
    rows: list[dict[str, Any]],
    sources: dict[str, Any],
    inventory: list[dict[str, Any]],
    cache: dict[str, Any],
) -> dict[str, Any]:
    run_readiness, next_action, blocker = readiness(rows, inventory, cache)
    queue_text = sources["queue_text"]
    queue_entry_present = (
        "active_bounded_research_task:" in queue_text
        and f"id: {LANE_ID}" in queue_text
        and f"family_id: {FAMILY_ID}" in queue_text
        and f"selected_step: {SELECTED_TASK}" in queue_text
    )
    commodity_manifest = sources["commodity_manifest"]
    diagnostics_manifest = sources["diagnostics_manifest"]
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "commodity_basket_bounded_design_only": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "selected_task": SELECTED_TASK,
        "selected_from_existing_source_of_truth": True,
        "queue_source_of_truth_entry_updated": queue_entry_present,
        "source_evidence_inspected": [
            "evidence/commodity_exploratory/latest",
            "evidence/commodity_lab/risk_control_batch1_diagnostics_completion/latest",
            "evidence/research_recovery/profit_research_queue_next_task_selection/latest",
            "strategy_lab/research_os/research/research_queue.yaml",
            "strategy_lab/strategy_registry.yaml",
            "strategy_lab/RESEARCH_ROADMAP.md",
        ],
        "commodity_exploratory_verdict": commodity_manifest.get("verdict", "unknown"),
        "commodity_exploratory_prior_download_flag": commodity_manifest.get(
            "data_downloaded_by_acquisition_lane", False
        ),
        "diagnostics_decision": diagnostics_manifest.get("decision", "unknown"),
        "diagnostics_new_symbols_added": diagnostics_manifest.get("new_symbols_added", False),
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_family_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "commodity_lane_run": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "best_single_variant_promoted": False,
        "research_outputs_remain_non_promotable": True,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "managed_futures_reopened": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "planned_row_count": len(rows),
        "planned_row_count_between_6_and_12": 6 <= len(rows) <= 12,
        "concept_count": len({row["concept"] for row in rows}),
        "target_row_range": "6_to_12",
        "baseline_comparator_policy_defined": True,
        "numeric_success_failure_criteria_defined": True,
        "guardrails_defined": True,
        "exposure_invariants_defined": True,
        "max_daily_exposure_limit": 1.0,
        "max_daily_weight_sum_limit": 1.0,
        "zero_weight_stale_forward_fill_blocked": True,
        "local_cache_required_symbols": cache["required_symbols"],
        "local_cache_available_symbols": cache["available_symbols"],
        "local_cache_missing_symbols": cache["missing_symbols"],
        "local_cache_missing_commodity_wrapper_symbols": cache["missing_commodity_wrapper_symbols"],
        "uses_local_cache_only": True,
        "run_readiness_decision": run_readiness,
        "run_readiness_blocker": blocker,
        "usable_diagnostic_design_evidence": True,
        "usable_strategy_diagnostic_evidence_produced": False,
        "next_action": next_action,
    }


def design_table_md(rows: list[dict[str, Any]]) -> str:
    columns = ["variant_id", "variant_role", "concept", "universe", "lookback_days", "top_n"]
    lines = ["# Commodity Basket Bounded Variant Design Table", "", f"Planned rows: `{len(rows)}`", ""]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Basket ETF Momentum Bounded Design

Selected family: `{payload['family_id']}`

Selected task: `{payload['selected_task']}`

Lane ID: `{payload['lane_id']}`

Planned rows: `{payload['planned_row_count']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Run-readiness blocker: `{payload['run_readiness_blocker']}`

Current local cache missing commodity wrapper symbols: `{', '.join(payload['local_cache_missing_commodity_wrapper_symbols']) or 'none'}`

This packet resolves the queue into one bounded commodity-basket task. It does not run the lane, run a backtest, run strategy discovery, create variants for execution, download data, use intraday data, promote anything, activate paper-forward, or touch broker/live paths.

Exact next action: `{payload['next_action']}`
"""


def source_review_md(root: Path, payload: dict[str, Any], sources: dict[str, Any], inventory: list[dict[str, Any]]) -> str:
    blocker = sources["queue_blocker_manifest"]
    commodity = sources["commodity_manifest"]
    diagnostics = sources["diagnostics_manifest"]
    return f"""# Source Commodity Evidence Review

Selected task is based on existing source-of-truth state only.

Queue blocker next family: `{blocker.get('research_state_reprioritization_next_family')}`

Queue blocker next allowed action: `{blocker.get('research_state_reprioritization_next_allowed_action')}`

Commodity exploratory verdict: `{commodity.get('verdict')}`

Commodity exploratory prior acquisition/download flag: `{commodity.get('data_downloaded_by_acquisition_lane')}`

Risk-control diagnostics decision: `{diagnostics.get('decision')}`

Risk-control diagnostics candidate_exhaustive recommended: `{diagnostics.get('candidate_exhaustive_review_recommended')}`

Why this is the correct next executable item:

- The prior blocker explicitly pointed to `commodity_basket_etf_momentum_v1`.
- The registry contains commodity-basket rows with `research_sample_review` or umbrella review status.
- Existing commodity artifacts are exploratory/diagnostic and do not authorize promotion.
- A bounded design is the smallest valid next step because no current root runner or run-ready lane exists for this family.
- The lane is not runnable yet because the current local cache lacks DBC/PDBC/COMT/GSG/USCI.

Reviewed source files:

{chr(10).join(f"- `{item['path']}` exists `{item['exists']}`" for item in inventory)}
"""


def comparator_policy_md() -> str:
    return """# Baseline And Comparator Policy

Future run comparators are diagnostic only:

- `SPY`, same-window where applicable.
- `SPY_200d_frozen_control`, same-window where available.
- `BIL_cash_proxy`, same-window cash/reference control.
- `GLD_buy_hold`, same-window commodity-adjacent control.
- `static_all_weather_benchmark_v1`, benchmark/control only, never candidate.
- Active VM/DSR combo diagnostics only where already supported by repository conventions.

Primary baseline mappings:

- Base commodity rows compare against `commodity_basket_tsmom_top2_v1`.
- Risk-control rows compare against `commodity_basket_tsmom_top2_v1`.
- Combo-plus-commodity row compares against `combo_SPY200d_GLD_50_50_v1`.
- Control rows remain controls and cannot become candidate rows.

Old exploratory evidence is context only. It is not promotion evidence.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run labels are research-only and must not create promotion or paper-forward eligibility.

Standalone commodity diagnostic pass requires all of:

- Max daily exposure `<= 1.000001`.
- Max daily weight sum `<= 1.000001`.
- 180-day stop-hit rate `<= 0.0250`.
- Worst 180-day drawdown `>= -600.0000` in the project dollar-window convention.
- 180-day `p_target_400_before_stop >= 0.2500`, where target-window diagnostics are supported.
- Average BIL/cash share `<= 0.6000`.
- Score delta versus BIL `> 0.0000`, where same-window score is supported.

Portfolio-contribution diagnostic pass requires all of:

- Correlation to active combo or SPY_200d reference `< 0.9000`, where supported.
- Incremental 180-day `+300` target windows versus active combo `>= 5`, where supported.
- Score delta versus active combo `>= 25.0000`, where supported.
- Active combo total-return drag `>= -0.0200`, where supported.
- Active combo max-drawdown improvement `>= 0.0300`, where supported.

Failure labels:

- `commodity_signal_risk_budget_breach`: worst 180-day drawdown `< -600.0000` or stop-hit rate `> 0.0250`.
- `commodity_signal_too_cash_heavy`: average BIL/cash share `> 0.6000`.
- `commodity_signal_duplicate_combo`: correlation to active combo or SPY_200d reference `>= 0.9000`.
- `commodity_signal_contribution_too_small`: score delta versus active combo `< 25.0000`.
- `commodity_signal_data_blocked`: any required current local-cache commodity wrapper symbol is missing.

These criteria are interpretation rules only. They are not promotion gates.
"""


def exposure_policy_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future bounded commodity run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No negative weights below tolerance.
- No NaN final weights.
- BIL/cash is replacement/remainder only.
- BIL/cash must not accumulate on top of risky exposure.
- Zero target weights remain zero until the next explicit rebalance target.
- Zero target weights must not stale-forward-fill into old allocations.
- No leverage, shorting, margin, options, direct futures, or intraday logic.
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "new_research_batch_run",
        "new_strategy_discovery_run",
        "new_backtests_run",
        "new_performance_metrics_from_raw_data_computed",
        "new_family_created",
        "new_variants_created",
        "hidden_parameter_grid_created",
        "commodity_lane_run",
        "provider_download",
        "intraday_data_used",
        "broker_api_called",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "real_money_recommendation",
        "managed_futures_reopened",
        "macro_gld_continued",
        "volatility_throttle_continued",
    ]
    return "# Guardrail Checklist\n\n" + "\n".join(f"- `{key}`: `{payload[key]}`" for key in keys) + "\n"


def cache_preflight_md(payload: dict[str, Any]) -> str:
    return f"""# Local Cache Preflight

Required symbols: `{', '.join(payload['local_cache_required_symbols'])}`

Available current local-cache symbols: `{', '.join(payload['local_cache_available_symbols']) or 'none'}`

Missing current local-cache symbols: `{', '.join(payload['local_cache_missing_symbols']) or 'none'}`

Missing commodity wrapper symbols: `{', '.join(payload['local_cache_missing_commodity_wrapper_symbols']) or 'none'}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Provider download was not attempted. Intraday data was not used.
"""


def queue_update_md(payload: dict[str, Any]) -> str:
    return f"""# Queue Source-Of-Truth Update

Queue file: `strategy_lab/research_os/research/research_queue.yaml`

Active bounded research task entry present: `{payload['queue_source_of_truth_entry_updated']}`

Task ID: `{payload['lane_id']}`

Family ID: `{payload['family_id']}`

Selected step: `{payload['selected_task']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Next action: `{payload['next_action']}`

The queue now has one explicit commodity-basket next task. The task remains blocked from running until current local commodity cache availability is restored or revalidated.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Commodity Basket Bounded Design

This packet creates no promotion, candidate_exhaustive, paper-forward, live/demo, broker, or real-money eligibility.

All rows are bounded design rows or controls. Old exploratory commodity evidence remains context only.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Commodity Basket Bounded Design Next Action

Exact next action:

`{payload['next_action']}`

Do not execute it in this task.
"""


def consistency_check(payload: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUTS}
    required["commodity_basket_bounded_design_consistency_check.json"] = True
    checks: dict[str, Any] = {
        "design_only": payload["commodity_basket_bounded_design_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "correct_family_id": payload["family_id"] == FAMILY_ID,
        "correct_selected_task": payload["selected_task"] == SELECTED_TASK,
        "queue_entry_present": payload["queue_source_of_truth_entry_updated"] is True,
        "selected_from_existing_source": payload["selected_from_existing_source_of_truth"] is True,
        "no_research_batch_or_discovery": payload["new_research_batch_run"] is False
        and payload["new_strategy_discovery_run"] is False,
        "no_backtest_or_raw_metrics": payload["new_backtests_run"] is False
        and payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_family_or_variant_expansion": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["hidden_parameter_grid_created"] is False,
        "lane_not_run": payload["commodity_lane_run"] is False,
        "no_provider_or_intraday": payload["provider_download"] is False and payload["intraday_data_used"] is False,
        "no_broker_live_real_money": payload["broker_api_called"] is False
        and payload["broker_orders_submitted"] is False
        and payload["broker_orders_cancelled"] is False
        and payload["broker_orders_reconciled"] is False
        and payload["live_orders"] is False
        and payload["real_money_recommendation"] is False,
        "no_promotion_candidate_exhaustive_paper": payload["promotion_candidates_created"] is False
        and payload["candidate_exhaustive_run"] is False
        and payload["paper_forward_activation"] is False
        and payload["new_paper_forward_candidate_created"] is False
        and payload["best_single_variant_promoted"] is False,
        "outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "excluded_lanes_not_continued": payload["macro_gld_continued"] is False
        and payload["volatility_throttle_continued"] is False
        and payload["managed_futures_reopened"] is False,
        "planned_row_count_bounded": payload["planned_row_count_between_6_and_12"] is True
        and len(rows) == payload["planned_row_count"],
        "variant_ids_unique": len({row["variant_id"] for row in rows}) == len(rows),
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_paper": all(row["paper_forward_eligibility"] is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row["candidate_exhaustive_eligibility"] is False for row in rows),
        "baseline_policy_defined": payload["baseline_comparator_policy_defined"] is True,
        "criteria_defined": payload["numeric_success_failure_criteria_defined"] is True,
        "exposure_invariants_defined": payload["exposure_invariants_defined"] is True,
        "run_readiness_valid": payload["run_readiness_decision"] in VALID_READINESS,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "blocked_reason_specific_if_blocked": payload["run_readiness_decision"] != RUN_BLOCKED
        or "missing current local commodity wrapper cache" in payload["run_readiness_blocker"],
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, sources: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    inventory = source_inventory(root)
    cache = local_cache_status(root)
    payload = build_manifest(root, created, output, rows, sources, inventory, cache)

    write_json(output / "commodity_basket_bounded_design_manifest.json", payload)
    write_text(output / "commodity_basket_bounded_design_summary.md", summary_md(payload))
    write_text(output / "source_commodity_evidence_review.md", source_review_md(root, payload, sources, inventory))
    write_csv(output / "commodity_basket_bounded_variant_design_table.csv", rows, DESIGN_FIELDS)
    write_text(output / "commodity_basket_bounded_variant_design_table.md", design_table_md(rows))
    write_text(output / "baseline_comparator_policy.md", comparator_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "exposure_invariant_policy.md", exposure_policy_md())
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "local_cache_preflight.md", cache_preflight_md(payload))
    write_text(output / "queue_source_of_truth_update.md", queue_update_md(payload))
    write_text(output / "do_not_promote_from_commodity_basket_design.md", do_not_promote_md())
    write_text(output / "commodity_basket_bounded_design_next_action.md", next_action_md(payload))
    check = consistency_check(payload, rows, output)
    write_json(output / "commodity_basket_bounded_design_consistency_check.json", check)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    sources = load_sources(root)
    rows = build_design_rows()
    return write_outputs(root, created, sources, rows)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "selected_task": result["selected_task"],
                "planned_row_count": result["planned_row_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
