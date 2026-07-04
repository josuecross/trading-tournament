from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv


FAMILY_ID = "regional_international_momentum"
LANE_ID = "regional_international_momentum_bounded_lane_v1"
SOURCE_CANDIDATES = (
    "rim_regional_momentum_with_spy_gate_v1",
    "rim_regional_top2_momentum_bil_v1",
)
OUTPUT_DIR = Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_design" / "latest"
TIE_EVIDENCE_DIR = (
    Path("evidence")
    / "research_recovery"
    / "next_registry_candidate_bounded_design_after_global_multi_asset"
    / "latest"
)
TRIAGE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_registry_research_sample_triage" / "latest"
SOURCE_EVIDENCE_DIR = Path("evidence") / "parallel_research_discovery" / "expanded_universe_batch_1" / "latest"
SOURCE_RESULTS = SOURCE_EVIDENCE_DIR / "expanded_universe_batch_1_results.csv"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"

REQUIRED_SYMBOLS = ("SPY", "EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM", "BIL")
REGIONAL_SYMBOLS = ("EWJ", "EWU", "EWG", "EWY", "INDA", "EFA", "EEM")

RUN_READY = "regional_international_momentum_bounded_design_run_ready"
RUN_BLOCKED = "regional_international_momentum_bounded_design_blocked"
NEXT_ACTION_RUN = "run_regional_international_momentum_bounded_lane"
NEXT_ACTION_CACHE = "restore_or_revalidate_regional_international_momentum_local_cache_before_bounded_run"
NEXT_ACTION_SOURCE = "repair_regional_international_momentum_source_lineage_before_bounded_run"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_CACHE, NEXT_ACTION_SOURCE}

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_registry_id",
    "source_evidence_path",
    "source_context_status",
    "concept",
    "universe_group",
    "universe",
    "lookback_days",
    "top_n",
    "rebalance_frequency",
    "rule_summary",
    "baseline_variant_id",
    "comparator_references",
    "bil_cash_rule",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "zero_weight_policy",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

CACHE_FIELDS = ("symbol", "required", "cache_path", "available", "first_date", "last_date", "rows", "status")
SOURCE_FIELDS = (
    "source_registry_id",
    "family",
    "source_row_found",
    "registry_entry_found",
    "source_decision",
    "source_decision_reason",
    "source_metric_csv",
    "source_context_status",
    "source_candidate_exhaustive_run",
    "source_paper_forward_active",
    "source_real_money_recommendation",
)

REQUIRED_FILES = (
    "regional_international_momentum_bounded_design_manifest.json",
    "regional_international_momentum_bounded_design_summary.md",
    "tie_resolution_co_seeded_design.md",
    "source_lineage_assessment.csv",
    "source_lineage_assessment.md",
    "local_cache_availability.csv",
    "local_cache_preflight.md",
    "eligibility_decision.md",
    "planned_variant_design_table.csv",
    "planned_variant_design_table.md",
    "variant_roles.md",
    "baseline_comparator_policy.md",
    "numeric_success_failure_criteria.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "rejected_closed_variant_exclusion_rule.md",
    "run_readiness_decision.md",
    "regional_international_momentum_bounded_design_next_action.md",
    "regional_international_momentum_bounded_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def source_rows(root: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(root / SOURCE_RESULTS) if (root / SOURCE_RESULTS).exists() else []
    return {row.get("strategy_id", ""): row for row in rows}


def registry_text(root: Path) -> str:
    path = root / REGISTRY
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_source_lineage(root: Path) -> list[dict[str, Any]]:
    sources = source_rows(root)
    registry = registry_text(root)
    out: list[dict[str, Any]] = []
    source_path = str((root / SOURCE_RESULTS).resolve())
    for strategy_id in SOURCE_CANDIDATES:
        row = sources.get(strategy_id, {})
        out.append(
            {
                "source_registry_id": strategy_id,
                "family": row.get("family_group", FAMILY_ID),
                "source_row_found": bool(row),
                "registry_entry_found": strategy_id in registry,
                "source_decision": row.get("decision", ""),
                "source_decision_reason": row.get("decision_reason", ""),
                "source_metric_csv": source_path,
                "source_context_status": "expanded_universe_source_context_only_not_promotion_evidence",
                "source_candidate_exhaustive_run": row.get("candidate_exhaustive_run", ""),
                "source_paper_forward_active": row.get("paper_forward_active", ""),
                "source_real_money_recommendation": row.get("real_money_recommendation", ""),
            }
        )
    return out


def cache_rows(root: Path) -> list[dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    rows: list[dict[str, Any]] = []
    for symbol in REQUIRED_SYMBOLS:
        info = inventory.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "required": True,
                "cache_path": info.get("path", ""),
                "available": info.get("status") == "cache_ready",
                "first_date": info.get("first_date", ""),
                "last_date": info.get("last_date", ""),
                "rows": info.get("rows", 0),
                "status": info.get("status", "missing"),
            }
        )
    return rows


def planned_rows(root: Path) -> list[dict[str, Any]]:
    source_path = str((root / SOURCE_RESULTS).resolve())
    comparators = (
        "SPY|SPY_200d_frozen_control|BIL_cash_proxy|EFA|EEM|"
        "static_all_weather_benchmark_control_only|active_VM_DSR_diagnostics_where_supported|"
        "both_tied_source_rows_context_only"
    )
    bil_rule = "BIL/cash is replacement or remainder only; it must not accumulate above total exposure 1.0."
    zero_rule = "zero target weights remain zero until the next explicit rebalance target; stale-forward-filling old nonzero allocations into zero targets is forbidden"
    rows = [
        {
            "variant_id": "rim_bounded_source_spy_gate_top2_126_v1",
            "variant_role": "source_context_spy_gate",
            "source_registry_id": "rim_regional_momentum_with_spy_gate_v1",
            "concept": "regional_top2_momentum_with_spy_gate_context",
            "universe_group": "regional_international_plus_spy_bil",
            "universe": "SPY|EWJ|EWU|EWG|EWY|INDA|EFA|EEM|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Context row for tied source: if SPY is eligible under the source expanded-universe rule, allocate to regional top-2 momentum; otherwise hold BIL.",
            "baseline_variant_id": "rim_regional_momentum_with_spy_gate_v1",
        },
        {
            "variant_id": "rim_bounded_source_top2_bil_126_v1",
            "variant_role": "source_context_top2_bil",
            "source_registry_id": "rim_regional_top2_momentum_bil_v1",
            "concept": "regional_top2_momentum_bil_context",
            "universe_group": "regional_international_plus_bil",
            "universe": "EWJ|EWU|EWG|EWY|INDA|EFA|EEM|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Context row for tied source: allocate to regional top-2 momentum using BIL fallback for ineligible or unused slots.",
            "baseline_variant_id": "rim_regional_top2_momentum_bil_v1",
        },
        {
            "variant_id": "rim_bounded_spy_gate_top2_half_bil_126_v1",
            "variant_role": "risk_control_half_bil_spy_gate",
            "source_registry_id": "rim_regional_momentum_with_spy_gate_v1",
            "concept": "regional_top2_spy_gate_50pct_bil_risk_control",
            "universe_group": "regional_international_plus_spy_bil",
            "universe": "SPY|EWJ|EWU|EWG|EWY|INDA|EFA|EEM|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Bounded risk-control check: run the tied SPY-gated regional top-2 source logic as a 50% sleeve and hold 50% BIL cash proxy.",
            "baseline_variant_id": "rim_regional_momentum_with_spy_gate_v1",
        },
        {
            "variant_id": "rim_bounded_top2_half_bil_126_v1",
            "variant_role": "risk_control_half_bil_top2",
            "source_registry_id": "rim_regional_top2_momentum_bil_v1",
            "concept": "regional_top2_50pct_bil_risk_control",
            "universe_group": "regional_international_plus_bil",
            "universe": "EWJ|EWU|EWG|EWY|INDA|EFA|EEM|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "Bounded risk-control check: run the tied regional top-2 source logic as a 50% sleeve and hold 50% BIL cash proxy.",
            "baseline_variant_id": "rim_regional_top2_momentum_bil_v1",
        },
        {
            "variant_id": "rim_bounded_spy200d_control_v1",
            "variant_role": "comparator_control",
            "source_registry_id": "SPY_200d_trend_model",
            "concept": "spy200d_frozen_control",
            "universe_group": "control",
            "universe": "SPY|BIL",
            "lookback_days": 200,
            "top_n": 1,
            "rule_summary": "Same-window SPY 200-day trend-model frozen control; benchmark/control only and not a candidate row.",
            "baseline_variant_id": "SPY_200d_trend_model",
        },
        {
            "variant_id": "rim_bounded_bil_cash_control_v1",
            "variant_role": "cash_control",
            "source_registry_id": "BIL_cash_proxy",
            "concept": "bil_cash_proxy_control",
            "universe_group": "control",
            "universe": "BIL",
            "lookback_days": 0,
            "top_n": 1,
            "rule_summary": "Same-window BIL cash proxy control only; not a candidate row.",
            "baseline_variant_id": "BIL_cash_proxy",
        },
        {
            "variant_id": "rim_bounded_efa_eem_equal_weight_control_v1",
            "variant_role": "regional_passive_context_control",
            "source_registry_id": "EFA_EEM_equal_weight_passive_context",
            "concept": "efa_eem_equal_weight_passive_context",
            "universe_group": "regional_passive_context",
            "universe": "EFA|EEM",
            "lookback_days": 0,
            "top_n": 2,
            "rule_summary": "Same-window 50/50 EFA/EEM passive regional context control; benchmark/control only and not a candidate row.",
            "baseline_variant_id": "EFA_EEM_equal_weight_passive_context",
        },
    ]
    for row in rows:
        row.update(
            {
                "lane_id": LANE_ID,
                "family_id": FAMILY_ID,
                "source_evidence_path": source_path,
                "source_context_status": "expanded_universe_source_context_only_not_promotion_evidence",
                "rebalance_frequency": "monthly",
                "comparator_references": comparators,
                "bil_cash_rule": bil_rule,
                "max_daily_exposure": 1.0,
                "max_daily_weight_sum": 1.0,
                "zero_weight_policy": zero_rule,
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
                "candidate_exhaustive_eligibility": False,
            }
        )
    return rows


def run_readiness(lineage: list[dict[str, Any]], cache: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    lineage_ok = all(
        row["source_row_found"]
        and row["registry_entry_found"]
        and row["source_decision"] == "too_risky"
        and str(row["source_candidate_exhaustive_run"]).lower() == "false"
        and str(row["source_paper_forward_active"]).lower() == "false"
        and str(row["source_real_money_recommendation"]).lower() == "false"
        for row in lineage
    )
    cache_ok = all(row["available"] for row in cache)
    row_count_ok = 6 <= len(rows) <= 10
    if lineage_ok and cache_ok and row_count_ok:
        return RUN_READY, "none", NEXT_ACTION_RUN
    if not lineage_ok:
        return RUN_BLOCKED, "source_lineage_missing_or_inconsistent", NEXT_ACTION_SOURCE
    return RUN_BLOCKED, "missing_required_local_cache_symbols", NEXT_ACTION_CACHE


def build_manifest(
    root: Path,
    created: str,
    output: Path,
    lineage: list[dict[str, Any]],
    cache: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    readiness, blocker, next_action = run_readiness(lineage, cache, rows)
    tie_manifest = read_json(root / TIE_EVIDENCE_DIR / "next_registry_candidate_bounded_design_manifest.json")
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "regional_international_momentum_bounded_design_only": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "tie_resolution_evidence_reviewed": bool(tie_manifest),
        "tie_resolution_method": "co_seeded_family_design_using_both_tied_candidates",
        "co_seed_source_candidate_ids": list(SOURCE_CANDIDATES),
        "source_lineage_verified": all(row["source_row_found"] and row["registry_entry_found"] for row in lineage),
        "source_evidence_context_only": True,
        "source_evidence_promotion_evidence": False,
        "local_cache_complete": all(row["available"] for row in cache),
        "local_cache_missing_symbols": [row["symbol"] for row in cache if not row["available"]],
        "eligibility_decision": "regional_international_momentum_bounded_design_eligible"
        if readiness == RUN_READY
        else "regional_international_momentum_bounded_design_blocked",
        "run_readiness_decision": readiness,
        "run_readiness_blocker": blocker,
        "planned_row_count": len(rows),
        "planned_row_count_between_6_and_8": 6 <= len(rows) <= 8,
        "planned_row_count_lte_10": len(rows) <= 10,
        "source_context_row_count": sum(1 for row in rows if str(row["variant_role"]).startswith("source_context")),
        "risk_control_row_count": sum(1 for row in rows if str(row["variant_role"]).startswith("risk_control")),
        "control_row_count": sum(
            1
            for row in rows
            if row["variant_role"]
            in {"comparator_control", "cash_control", "regional_passive_context_control"}
        ),
        "new_family_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_allowed": False,
        "direct_futures_allowed": False,
        "forex_allowed": False,
        "margin_allowed": False,
        "candidate_exhaustive_run": False,
        "promotion_candidates_created": False,
        "best_single_variant_promoted": False,
        "paper_forward_activation": False,
        "new_paper_forward_candidate_created": False,
        "broker_api_called": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "broker_orders_reconciled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "active_vm_preserved": True,
        "active_dsr_preserved": True,
        "static_all_weather_benchmark_control_only": True,
        "global_multi_asset_continued": False,
        "high_return_tactical_continued": False,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_continued": False,
        "managed_futures_reopened": False,
        "crypto_continued": False,
        "regional_lane_run": False,
        "next_action": next_action,
    }


def tie_resolution_md() -> str:
    return """# Tie Resolution by Co-Seeded Family Design

The prior packet found a top-score tie between:

- `rim_regional_momentum_with_spy_gate_v1`
- `rim_regional_top2_momentum_bil_v1`

Both rows belong to `regional_international_momentum`, both had triage score `57.8187`, and both were labeled `too_risky`.

This design resolves the tie without arbitrary single-row selection by making both tied rows co-seeds in one bounded family-level design. The source rows remain context only; they are not promotion evidence.
"""


def source_lineage_md(lineage: list[dict[str, Any]]) -> str:
    lines = ["# Source-Lineage Assessment", ""]
    for row in lineage:
        lines.append(f"- `{row['source_registry_id']}`")
        lines.append(f"  - Source row found: `{row['source_row_found']}`")
        lines.append(f"  - Registry entry found: `{row['registry_entry_found']}`")
        lines.append(f"  - Source decision: `{row['source_decision']}`")
        lines.append(f"  - Source decision reason: `{row['source_decision_reason']}`")
        lines.append(f"  - Source context status: `{row['source_context_status']}`")
    lines.append("")
    lines.append("Expanded-universe evidence is design context only and is not treated as promotion, candidate_exhaustive, paper-forward, broker/live, or real-money evidence.")
    return "\n".join(lines) + "\n"


def cache_md(cache: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Preflight", ""]
    for row in cache:
        lines.append(
            f"- `{row['symbol']}`: available `{row['available']}`, status `{row['status']}`, "
            f"`{row['first_date']}` to `{row['last_date']}`, rows `{row['rows']}`"
        )
    lines.append("")
    lines.append("No provider download was run or authorized.")
    return "\n".join(lines) + "\n"


def eligibility_md(manifest: dict[str, Any]) -> str:
    return f"""# Eligibility Decision

Family: `{manifest['family_id']}`

Lane: `{manifest['lane_id']}`

Eligibility decision: `{manifest['eligibility_decision']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Next action: `{manifest['next_action']}`
"""


def design_table_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Variant Design Table", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: role `{row['variant_role']}`, source `{row['source_registry_id']}`, "
            f"concept `{row['concept']}`, universe `{row['universe']}`"
        )
    return "\n".join(lines) + "\n"


def variant_roles_md() -> str:
    return """# Variant Roles

- `source_context_spy_gate`: tied source row context, not a candidate row.
- `source_context_top2_bil`: tied source row context, not a candidate row.
- `risk_control_half_bil_spy_gate`: bounded risk-control check that halves the tied SPY-gated source exposure and assigns the remainder to BIL.
- `risk_control_half_bil_top2`: bounded risk-control check that halves the tied top-2 source exposure and assigns the remainder to BIL.
- `comparator_control`: SPY 200d frozen control, never a candidate.
- `cash_control`: BIL cash proxy control, never a candidate.
- `regional_passive_context_control`: EFA/EEM passive regional context, never a candidate.
"""


def comparator_policy_md() -> str:
    return """# Baseline / Comparator Policy

Comparators are diagnostic only:

- `SPY` same-window comparison.
- `SPY_200d_frozen_control` where supported.
- `BIL_cash_proxy` same-window cash/control.
- `EFA` and `EEM` passive regional context.
- `EFA_EEM_equal_weight_passive_context` as a regional passive control row.
- `static_all_weather_benchmark_v1` benchmark/control only, never candidate.
- Active VM/DSR diagnostics only where already supported by repository conventions.
- Both tied source rows remain historical context only.

No comparator can become a promotion, candidate_exhaustive, paper-forward, broker, live, or real-money row from this design packet.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run labels are research-only and must not create promotion or paper-forward eligibility.

Risk-control rows pass only if all are true:

- CAGR retention versus its tied source context row `>= 0.6000`.
- Total return retention versus its tied source context row `>= 0.6000`.
- Max drawdown reduction versus its tied source context row `>= 0.2500` relative improvement.
- 180-day worst drawdown improves from the prior tied-source `-798.4633` to `>= -500.0000` in project dollar-window convention.
- Risk buffer versus the `-600.0000` project stop is `>= 100.0000`.
- Average BIL/cash share `<= 0.6500`.
- Duplicate/reference correlation `< 0.9000`.
- Max daily exposure `<= 1.000001`.
- Max daily weight sum `<= 1.000001`.

Source context rows are not candidate rows. They are useful context only if they reproduce source-style behavior and preserve source labels as `too_risky_context`.

Control rows are benchmark/control rows only and cannot pass candidate-style criteria.

Failure labels for future run:

- `regional_signal_data_blocked`: required local-cache symbols are missing.
- `regional_signal_source_context_too_risky`: source context row remains too risky.
- `regional_signal_risk_control_pass`: risk-control row passes every numeric risk-control criterion.
- `regional_signal_return_destroyed`: return retention versus source context row `< 0.6000`.
- `regional_signal_drawdown_not_fixed`: drawdown reduction `< 0.2500` or 180-day worst drawdown `< -500.0000`.
- `regional_signal_too_cash_heavy`: average BIL/cash share `> 0.6500`.
- `regional_signal_duplicate_reference`: duplicate/reference correlation `>= 0.9000`.
- `regional_signal_control_only`: comparator/control rows.

These criteria are interpretation rules only. They are not promotion gates.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "regional_international_momentum_bounded_design_only",
        "regional_lane_run",
        "strategy_discovery_run",
        "new_research_batch_run",
        "new_backtests_run",
        "new_performance_metrics_from_raw_data_computed",
        "new_family_created",
        "new_variants_created",
        "hidden_parameter_grid_created",
        "provider_download",
        "intraday_data_used",
        "leverage_allowed",
        "shorting_allowed",
        "options_allowed",
        "direct_futures_allowed",
        "forex_allowed",
        "margin_allowed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
    ]
    return {key: manifest[key] for key in keys}


def exposure_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future bounded regional international momentum run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash is replacement/remainder only.
- BIL/cash must not accumulate on top of risky exposure.
- Zero target weights remain zero until the next explicit rebalance target.
- Zero target weights must not stale-forward-fill into old allocations.
- No leverage, shorting, margin, options, direct futures, forex, broker, live, or intraday logic.
"""


def rejected_exclusion_md() -> str:
    return """# Rejected / Closed Variant Exclusion Rule

This design does not reopen exact rejected variants and does not clone rejected rows with cosmetic changes.

Explicit exclusions:

- global multi-asset continuation
- high-return tactical continuation
- commodity-basket continuation
- Macro/GLD continuation
- volatility-throttle continuation
- managed-futures continuation
- crypto continuation
- candidate_exhaustive rows
- paper-forward rows
- promotion rows

The source regional rows are co-seed context because the direction-owner decision explicitly resolved a same-family tie this way. They remain non-promotable and research-only.
"""


def run_readiness_md(manifest: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Exact next action: `{manifest['next_action']}`

Do not execute the next action in this task.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Regional International Momentum Bounded Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Regional International Momentum Bounded Design

Family: `{manifest['family_id']}`

Lane: `{manifest['lane_id']}`

Tie-resolution method: `{manifest['tie_resolution_method']}`

Co-seed source candidates: `{', '.join(manifest['co_seed_source_candidate_ids'])}`

Source lineage verified: `{manifest['source_lineage_verified']}`

Source evidence context only: `{manifest['source_evidence_context_only']}`

Local cache complete: `{manifest['local_cache_complete']}`

Planned rows: `{manifest['planned_row_count']}`

Source context rows: `{manifest['source_context_row_count']}`

Risk-control rows: `{manifest['risk_control_row_count']}`

Control rows: `{manifest['control_row_count']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No lane run, backtest, strategy discovery, broad research batch, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live path, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["regional_international_momentum_bounded_design_consistency_check.json"] = True
    row_ids = {row["variant_id"] for row in rows}
    checks = {
        "design_only": manifest["regional_international_momentum_bounded_design_only"] is True,
        "correct_lane_id": manifest["lane_id"] == LANE_ID,
        "correct_family_id": manifest["family_id"] == FAMILY_ID,
        "tie_resolution_evidence_reviewed": manifest["tie_resolution_evidence_reviewed"] is True,
        "co_seed_ids_present": set(manifest["co_seed_source_candidate_ids"]) == set(SOURCE_CANDIDATES),
        "source_lineage_verified": manifest["source_lineage_verified"] is True,
        "source_context_only": manifest["source_evidence_context_only"] is True
        and manifest["source_evidence_promotion_evidence"] is False,
        "local_cache_complete": manifest["local_cache_complete"] is True,
        "planned_count_bounded": manifest["planned_row_count_between_6_and_8"] is True
        and manifest["planned_row_count_lte_10"] is True,
        "expected_rows_present": row_ids
        == {
            "rim_bounded_source_spy_gate_top2_126_v1",
            "rim_bounded_source_top2_bil_126_v1",
            "rim_bounded_spy_gate_top2_half_bil_126_v1",
            "rim_bounded_top2_half_bil_126_v1",
            "rim_bounded_spy200d_control_v1",
            "rim_bounded_bil_cash_control_v1",
            "rim_bounded_efa_eem_equal_weight_control_v1",
        },
        "no_lane_run_or_backtest": manifest["regional_lane_run"] is False
        and manifest["new_backtests_run"] is False
        and manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_discovery_or_broad_batch": manifest["strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_family_variant_grid": manifest["new_family_created"] is False
        and manifest["new_variants_created"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_leverage_derivatives": manifest["leverage_allowed"] is False
        and manifest["shorting_allowed"] is False
        and manifest["options_allowed"] is False
        and manifest["direct_futures_allowed"] is False
        and manifest["forex_allowed"] is False
        and manifest["margin_allowed"] is False,
        "no_candidate_promotion_paper": manifest["candidate_exhaustive_run"] is False
        and manifest["promotion_candidates_created"] is False
        and manifest["best_single_variant_promoted"] is False
        and manifest["paper_forward_activation"] is False
        and manifest["new_paper_forward_candidate_created"] is False,
        "no_broker_live_real_money": manifest["broker_api_called"] is False
        and manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["broker_orders_reconciled"] is False
        and manifest["live_orders"] is False
        and manifest["real_money_recommendation"] is False,
        "protected_state_preserved": manifest["active_vm_preserved"] is True
        and manifest["active_dsr_preserved"] is True
        and manifest["static_all_weather_benchmark_control_only"] is True,
        "excluded_tracks_not_continued": manifest["global_multi_asset_continued"] is False
        and manifest["high_return_tactical_continued"] is False
        and manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_continued"] is False
        and manifest["managed_futures_reopened"] is False
        and manifest["crypto_continued"] is False,
        "run_ready_or_blocked_valid": manifest["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    lineage = build_source_lineage(root)
    cache = cache_rows(root)
    rows = planned_rows(root)
    manifest = build_manifest(root, created, output, lineage, cache, rows)

    write_json(output / "regional_international_momentum_bounded_design_manifest.json", manifest)
    write_text(output / "regional_international_momentum_bounded_design_summary.md", summary_md(manifest))
    write_text(output / "tie_resolution_co_seeded_design.md", tie_resolution_md())
    write_csv(output / "source_lineage_assessment.csv", lineage, list(SOURCE_FIELDS))
    write_text(output / "source_lineage_assessment.md", source_lineage_md(lineage))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_preflight.md", cache_md(cache))
    write_text(output / "eligibility_decision.md", eligibility_md(manifest))
    write_csv(output / "planned_variant_design_table.csv", rows, list(DESIGN_FIELDS))
    write_text(output / "planned_variant_design_table.md", design_table_md(rows))
    write_text(output / "variant_roles.md", variant_roles_md())
    write_text(output / "baseline_comparator_policy.md", comparator_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "rejected_closed_variant_exclusion_rule.md", rejected_exclusion_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "regional_international_momentum_bounded_design_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, rows, output)
    write_json(output / "regional_international_momentum_bounded_design_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "planned_row_count": result["planned_row_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
