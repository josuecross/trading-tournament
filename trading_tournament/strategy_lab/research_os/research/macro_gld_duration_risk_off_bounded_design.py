from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


LANE_ID = "macro_gld_duration_risk_off_bounded_lane_v1"
SOURCE_FAMILY = "macro_gld_duration_risk_off"
SOURCE_TASK = "recover_gld_macro_family_lineage"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"

LINEAGE_DIR = Path("evidence") / "research_recovery" / "gld_macro_family_lineage_recovery" / "latest"
LABEL_FIX_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"
LABEL_AUDIT_DIR = (
    Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix_audit" / "latest"
)
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
LINEAGE_LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"

NEXT_ACTION_RUN = "run_macro_gld_duration_risk_off_bounded_research_lane"
NEXT_ACTION_BLOCKED = "macro_gld_bounded_design_blocked"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}

RUN_READY = "macro_gld_bounded_design_run_ready"
RUN_BLOCKED = "macro_gld_bounded_design_blocked"
VALID_RUN_READINESS = {RUN_READY, RUN_BLOCKED}

REJECTED_OR_CONTEXT_VARIANTS = {
    "gld_gror_balanced_momentum_clean_v1",
    "gld_ief_spy_defensive_rotation_v1",
    "gror_balanced_momentum_60_40_v1",
    "mgd_macro_mom63_top1_trend",
    "mgd_macro_mom63_top2_trend",
    "mgd_macro_mom126_top1_trend",
    "mgd_macro_mom126_top2_trend",
    "mgd_macro_mom252_top1_trend",
    "mgd_macro_mom252_top2_trend",
    "mgd_static_spy_gld_tlt_60_20_20",
    "mgd_static_gld_tlt_bil_equal",
    "mgd_static_gld_ief_bil_equal",
    "mgd_static_gld_spy_bil_equal",
}

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "concept",
    "universe_group",
    "universe",
    "lookback_days",
    "top_n",
    "rebalance_frequency",
    "signal_timing",
    "rule_summary",
    "risk_on_rule",
    "risk_off_rule",
    "asset_gate_rule",
    "bil_cash_rule",
    "baseline_context_rows",
    "comparator_references",
    "static_all_weather_role",
    "rejected_variant_exclusion_rule",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "zero_weight_policy",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

REQUIRED_FILES = (
    "macro_gld_bounded_design_manifest.json",
    "macro_gld_bounded_design_summary.md",
    "source_lineage_context_review.md",
    "planned_variant_design_table.csv",
    "planned_variant_design_table.md",
    "variant_role_definitions.md",
    "frozen_rule_summaries.md",
    "baseline_comparator_policy.md",
    "numeric_success_failure_criteria.md",
    "guardrail_checklist.md",
    "exposure_invariant_requirements.md",
    "historical_lineage_context_summary.md",
    "rejected_variant_exclusion_policy.md",
    "run_readiness_decision.md",
    "do_not_promote_from_macro_gld_design.md",
    "macro_gld_bounded_design_next_action.md",
    "macro_gld_bounded_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_sources(root: Path) -> dict[str, Any]:
    return {
        "lineage_manifest": read_json(root / LINEAGE_DIR / "gld_macro_lineage_recovery_manifest.json"),
        "lineage_summary": read_text(root / LINEAGE_DIR / "gld_macro_lineage_recovery_summary.md"),
        "lineage_findings": read_text(root / LINEAGE_DIR / "lineage_recovery_findings.md"),
        "lineage_table": read_csv(root / LINEAGE_DIR / "lineage_recovery_table.csv"),
        "corrected_macro_rows": read_csv(root / LINEAGE_DIR / "corrected_macro_rows.csv"),
        "macro_label_status": read_text(root / LABEL_FIX_DIR / "macro_gld_lineage_label_status.md"),
        "label_audit_manifest": read_json(root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json"),
        "roadmap": read_text(root / ROADMAP),
        "registry": read_text(root / REGISTRY),
        "family_ledger": read_text(root / LINEAGE_LEDGER),
    }


def build_design_rows() -> list[dict[str, Any]]:
    common = {
        "lane_id": LANE_ID,
        "family_id": SOURCE_FAMILY,
        "rebalance_frequency": "monthly",
        "signal_timing": "signals calculated after close using data through t-1; next scheduled rebalance uses those frozen signals",
        "baseline_context_rows": "recovered_macro_gld_rows_context_only",
        "comparator_references": "SPY_200d_frozen_control|SPY_buy_hold|BIL_cash_reference|static_all_weather_benchmark_control|active_VM_DSR_combo_when_supported",
        "static_all_weather_role": "benchmark_control_only_not_candidate",
        "rejected_variant_exclusion_rule": "do_not_reopen_exact_rejected_or_recovered_context_variant_ids",
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "zero_weight_policy": "zero target weights remain zero until the next explicit rebalance target; never stale-forward-fill old nonzero allocations into zero targets",
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    concepts = [
        {
            "variant_id": "mgd_bounded_canary_defensive_top1_126_v1",
            "variant_role": "primary_macro_risk_off_test",
            "concept": "spy_canary_gold_duration_top1",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|TLT|IEF|BIL",
            "lookback_days": 126,
            "top_n": 1,
            "rule_summary": "If SPY is above its 200-day SMA, hold 50% SPY and 50% top-1 of GLD/TLT/IEF by 126-day momentum when that defensive asset is above its own 200-day SMA; failed defensive sleeve weight goes to BIL. If SPY is below or equal to its 200-day SMA, allocate 100% to top-1 of GLD/TLT/IEF/BIL by 126-day momentum, with BIL eligible as explicit risk-off asset.",
            "risk_on_rule": "SPY 50%; defensive sleeve 50% to top-1 GLD/TLT/IEF if asset gate passes, otherwise BIL.",
            "risk_off_rule": "100% to top-1 of GLD/TLT/IEF/BIL; if all risky defensive assets fail own trend gates, BIL receives 100%.",
            "asset_gate_rule": "GLD/TLT/IEF require close above own 200-day SMA for risky allocation; SPY requires close above SPY 200-day SMA for risk-on state.",
            "bil_cash_rule": "BIL is fallback/remainder only and cannot add above total exposure 1.0.",
        },
        {
            "variant_id": "mgd_bounded_canary_defensive_top1_252_v1",
            "variant_role": "primary_macro_risk_off_test",
            "concept": "spy_canary_gold_duration_top1",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|TLT|IEF|BIL",
            "lookback_days": 252,
            "top_n": 1,
            "rule_summary": "Same as canary defensive top-1 design, using 252-day momentum for the GLD/TLT/IEF/BIL selection step.",
            "risk_on_rule": "SPY 50%; defensive sleeve 50% to top-1 GLD/TLT/IEF if asset gate passes, otherwise BIL.",
            "risk_off_rule": "100% to top-1 of GLD/TLT/IEF/BIL by 252-day momentum; if risky defensive gates fail, BIL receives 100%.",
            "asset_gate_rule": "GLD/TLT/IEF require close above own 200-day SMA for risky allocation; SPY requires close above SPY 200-day SMA for risk-on state.",
            "bil_cash_rule": "BIL is fallback/remainder only and cannot add above total exposure 1.0.",
        },
        {
            "variant_id": "mgd_bounded_canary_defensive_top2_126_v1",
            "variant_role": "breadth_check_not_grid",
            "concept": "spy_canary_gold_duration_top2",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|TLT|IEF|BIL",
            "lookback_days": 126,
            "top_n": 2,
            "rule_summary": "If SPY is above its 200-day SMA, hold 50% SPY and split 50% equally across top-2 GLD/TLT/IEF assets with positive own 200-day trend; failed sleeve weight goes to BIL. If SPY is risk-off, split 100% across top-2 GLD/TLT/IEF/BIL by 126-day momentum with BIL allowed.",
            "risk_on_rule": "SPY 50%; defensive sleeve 50% split across top-2 GLD/TLT/IEF with trend gates; failed slots to BIL.",
            "risk_off_rule": "100% split across top-2 GLD/TLT/IEF/BIL by 126-day momentum; failed risky gates to BIL.",
            "asset_gate_rule": "Every risky asset allocation requires its own 200-day SMA gate; BIL has no trend gate.",
            "bil_cash_rule": "BIL is fallback/remainder only and cannot add above total exposure 1.0.",
        },
        {
            "variant_id": "mgd_bounded_canary_defensive_top2_252_v1",
            "variant_role": "breadth_check_not_grid",
            "concept": "spy_canary_gold_duration_top2",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|TLT|IEF|BIL",
            "lookback_days": 252,
            "top_n": 2,
            "rule_summary": "Same as canary defensive top-2 design, using 252-day momentum for the GLD/TLT/IEF/BIL selection step.",
            "risk_on_rule": "SPY 50%; defensive sleeve 50% split across top-2 GLD/TLT/IEF with trend gates; failed slots to BIL.",
            "risk_off_rule": "100% split across top-2 GLD/TLT/IEF/BIL by 252-day momentum; failed risky gates to BIL.",
            "asset_gate_rule": "Every risky asset allocation requires its own 200-day SMA gate; BIL has no trend gate.",
            "bil_cash_rule": "BIL is fallback/remainder only and cannot add above total exposure 1.0.",
        },
        {
            "variant_id": "mgd_bounded_gold_duration_sleeve_top1_126_v1",
            "variant_role": "defensive_sleeve_contribution_test",
            "concept": "gold_duration_trend_sleeve",
            "universe_group": "gold_duration_cash",
            "universe": "GLD|TLT|IEF|BIL",
            "lookback_days": 126,
            "top_n": 1,
            "rule_summary": "Monthly defensive sleeve only: allocate 100% to top-1 GLD/TLT/IEF by 126-day momentum if that asset is above its own 200-day SMA; otherwise allocate 100% BIL. SPY is comparator/canary context only, not a held risk-on sleeve.",
            "risk_on_rule": "Not applicable as an equity risk-on sleeve; this is a defensive contribution sleeve.",
            "risk_off_rule": "Top-1 GLD/TLT/IEF if own 200-day trend gate passes; otherwise BIL 100%.",
            "asset_gate_rule": "GLD/TLT/IEF require own 200-day trend gate; BIL has no trend gate.",
            "bil_cash_rule": "BIL receives 100% when no defensive asset qualifies; otherwise BIL receives 0%.",
        },
        {
            "variant_id": "mgd_bounded_gold_duration_sleeve_top1_252_v1",
            "variant_role": "defensive_sleeve_contribution_test",
            "concept": "gold_duration_trend_sleeve",
            "universe_group": "gold_duration_cash",
            "universe": "GLD|TLT|IEF|BIL",
            "lookback_days": 252,
            "top_n": 1,
            "rule_summary": "Monthly defensive sleeve only: allocate 100% to top-1 GLD/TLT/IEF by 252-day momentum if that asset is above its own 200-day SMA; otherwise allocate 100% BIL. SPY is comparator/canary context only, not a held risk-on sleeve.",
            "risk_on_rule": "Not applicable as an equity risk-on sleeve; this is a defensive contribution sleeve.",
            "risk_off_rule": "Top-1 GLD/TLT/IEF if own 200-day trend gate passes; otherwise BIL 100%.",
            "asset_gate_rule": "GLD/TLT/IEF require own 200-day trend gate; BIL has no trend gate.",
            "bil_cash_rule": "BIL receives 100% when no defensive asset qualifies; otherwise BIL receives 0%.",
        },
        {
            "variant_id": "mgd_bounded_barbell_gated_126_v1",
            "variant_role": "allocation_behavior_context",
            "concept": "equity_gold_duration_gated_barbell",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|IEF|BIL",
            "lookback_days": 126,
            "top_n": 3,
            "rule_summary": "Monthly fixed-role barbell with gates: target 40% SPY, 30% GLD, 30% IEF. Each risky sleeve must have positive 126-day return and close above own 200-day SMA; failed sleeve weight goes to BIL. If SPY fails, its 40% sleeve is reassigned 20% to GLD and 20% to IEF only if their gates pass; otherwise failed reassigned weight goes to BIL.",
            "risk_on_rule": "40% SPY, 30% GLD, 30% IEF when all sleeves pass gates.",
            "risk_off_rule": "Failed SPY sleeve is conditionally reassigned to GLD/IEF gates; failed GLD/IEF sleeve weights go to BIL.",
            "asset_gate_rule": "Each risky sleeve requires positive lookback return and own 200-day trend gate.",
            "bil_cash_rule": "BIL receives only failed sleeve weight and cannot add above total exposure 1.0.",
        },
        {
            "variant_id": "mgd_bounded_barbell_gated_252_v1",
            "variant_role": "allocation_behavior_context",
            "concept": "equity_gold_duration_gated_barbell",
            "universe_group": "equity_gold_duration_cash",
            "universe": "SPY|GLD|IEF|BIL",
            "lookback_days": 252,
            "top_n": 3,
            "rule_summary": "Same as gated barbell design, using positive 252-day return plus own 200-day SMA as the sleeve eligibility gate.",
            "risk_on_rule": "40% SPY, 30% GLD, 30% IEF when all sleeves pass gates.",
            "risk_off_rule": "Failed SPY sleeve is conditionally reassigned to GLD/IEF gates; failed GLD/IEF sleeve weights go to BIL.",
            "asset_gate_rule": "Each risky sleeve requires positive lookback return and own 200-day trend gate.",
            "bil_cash_rule": "BIL receives only failed sleeve weight and cannot add above total exposure 1.0.",
        },
    ]
    return [{**common, **row} for row in concepts]


def source_inventory(root: Path) -> list[dict[str, Any]]:
    paths = [
        root / ROADMAP,
        root / REGISTRY,
        root / LINEAGE_LEDGER,
        root / LINEAGE_DIR / "gld_macro_lineage_recovery_manifest.json",
        root / LINEAGE_DIR / "corrected_macro_rows.csv",
        root / LINEAGE_DIR / "lineage_recovery_table.csv",
        root / LABEL_FIX_DIR / "macro_gld_lineage_label_status.md",
        root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json",
    ]
    return [{"path": str(path.resolve()), "exists": path.exists()} for path in paths]


def run_readiness(rows: list[dict[str, Any]], inventory: list[dict[str, Any]], sources: dict[str, Any]) -> tuple[str, str, str]:
    blocked_reasons: list[str] = []
    variant_ids = [row["variant_id"] for row in rows]
    if not 6 <= len(rows) <= 12:
        blocked_reasons.append("planned variant count is outside 6 to 12")
    if len(set(variant_ids)) != len(variant_ids):
        blocked_reasons.append("variant IDs are not unique")
    if any(variant_id in REJECTED_OR_CONTEXT_VARIANTS for variant_id in variant_ids):
        blocked_reasons.append("design reuses rejected or recovered-context variant ID")
    if any(not item["exists"] for item in inventory):
        blocked_reasons.append("required source evidence is missing")
    if sources["lineage_manifest"].get("lineage_recovery_completed") is not True:
        blocked_reasons.append("lineage recovery is not complete")
    if sources["lineage_manifest"].get("macro_rows_recovered_count") != 10:
        blocked_reasons.append("expected 10 recovered Macro/GLD rows")
    if sources["label_audit_manifest"].get("macro_gld_lineage_recovery_supported") is not True:
        blocked_reasons.append("label audit does not support Macro/GLD lineage recovery")
    if blocked_reasons:
        return RUN_BLOCKED, NEXT_ACTION_BLOCKED, "; ".join(blocked_reasons)
    return RUN_READY, NEXT_ACTION_RUN, "none"


def manifest(created: str, output: Path, rows: list[dict[str, Any]], inventory: list[dict[str, Any]], sources: dict[str, Any]) -> dict[str, Any]:
    readiness, next_action, blocker = run_readiness(rows, inventory, sources)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "macro_gld_bounded_design_only": True,
        "lane_id": LANE_ID,
        "source_family": SOURCE_FAMILY,
        "source_task": SOURCE_TASK,
        "lineage_recovery_evidence_reviewed": True,
        "selection_from_existing_roadmap_registry_only": True,
        "new_research_lane_run": False,
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_variants_created_for_execution": False,
        "new_family_created": False,
        "hidden_parameter_grid_created": False,
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
        "exact_rejected_variants_reopened": False,
        "rejected_variant_ids_excluded": True,
        "alpaca_execution_module_delegated": True,
        "planned_variant_count": len(rows),
        "planned_variant_count_between_6_and_12": 6 <= len(rows) <= 12,
        "concept_count": len({row["concept"] for row in rows}),
        "lookback_count": len({row["lookback_days"] for row in rows}),
        "max_daily_exposure": 1.0,
        "max_daily_weight_sum": 1.0,
        "exposure_invariants_defined": True,
        "zero_weight_stale_forward_fill_blocked": True,
        "baseline_comparator_policy_defined": True,
        "numeric_success_failure_criteria_defined": True,
        "run_readiness_decision": readiness,
        "run_readiness_blocker": blocker,
        "usable_diagnostic_design_evidence": readiness == RUN_READY,
        "next_action": next_action,
    }


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Macro / GLD Duration Risk-Off Bounded Design

Lane ID: `{payload['lane_id']}`

Source family: `{payload['source_family']}`

Planned rows: `{payload['planned_variant_count']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Run-readiness blocker: `{payload['run_readiness_blocker']}`

This is design-only. No Macro/GLD lane run, backtest, discovery, provider download, intraday use, broker/live action, promotion, candidate_exhaustive, paper-forward activation, or real-money recommendation occurred.

Exact next action: `{payload['next_action']}`
"""


def source_context_md(sources: dict[str, Any], inventory: list[dict[str, Any]]) -> str:
    missing = [item for item in inventory if not item["exists"]]
    manifest = sources["lineage_manifest"]
    return f"""# Source Lineage Context Review

Lineage recovery evidence path: `{(ROOT / LINEAGE_DIR).resolve()}`

Lineage recovery completed: `{manifest.get('lineage_recovery_completed')}`

Recovered Macro/GLD rows: `{manifest.get('macro_rows_recovered_count')}`

Missing source evidence paths: `{len(missing)}`

Recovered rows are context only. They remain diagnostic, non-promotable, and not paper-forward eligible.

Reviewed source files:

{chr(10).join(f"- `{item['path']}` exists `{item['exists']}`" for item in inventory)}
"""


def design_table_md(rows: list[dict[str, Any]]) -> str:
    columns = ["variant_id", "variant_role", "concept", "universe", "lookback_days", "top_n"]
    lines = ["# Planned Variant Design Table", "", f"Planned rows: `{len(rows)}`", ""]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def role_definitions_md() -> str:
    return """# Variant Role Definitions

- `primary_macro_risk_off_test`: tests whether GLD/duration risk-off behavior can contribute without reopening exact rejected variants.
- `breadth_check_not_grid`: checks top-2 breadth against top-1 without adding a hidden parameter grid.
- `defensive_sleeve_contribution_test`: tests GLD/duration as a standalone defensive sleeve context, not as a promotion candidate.
- `allocation_behavior_context`: tests gated allocation behavior while keeping static all-weather as benchmark/control only.
"""


def frozen_rules_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Frozen Rule Summaries", ""]
    for row in rows:
        lines.extend(
            [
                f"## {row['variant_id']}",
                "",
                f"- Role: `{row['variant_role']}`",
                f"- Universe: `{row['universe']}`",
                f"- Lookback days: `{row['lookback_days']}`",
                f"- Top-N: `{row['top_n']}`",
                f"- Rebalance: `{row['rebalance_frequency']}`",
                f"- Signal timing: `{row['signal_timing']}`",
                f"- Rule: {row['rule_summary']}",
                f"- Risk-on rule: {row['risk_on_rule']}",
                f"- Risk-off rule: {row['risk_off_rule']}",
                f"- Asset gate: {row['asset_gate_rule']}",
                f"- BIL/cash: {row['bil_cash_rule']}",
                "- Promotion eligibility: `false`",
                "- Paper-forward eligibility: `false`",
                "",
            ]
        )
    return "\n".join(lines)


def baseline_policy_md() -> str:
    return """# Baseline / Comparator Policy

Primary comparators for a future run:

- `SPY_200d_frozen_control`, where applicable.
- `SPY_buy_hold`, same-window.
- `BIL_cash_reference`, same-window.
- `static_all_weather_benchmark_v1`, benchmark/control only.
- Active VM, active DSR, and active VM/DSR combo contribution diagnostics where supported.
- Recovered `macro_gld_duration_risk_off` rows as historical context only, not as promotion evidence.

Static all-weather may only be used as benchmark/control. It must not be treated as a candidate row.

The recovered Macro/GLD rows provide context for why this lane is bounded; they do not authorize reopening exact rejected variants.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Future run labels are research-only:

- `macro_gld_signal_interesting`
- `macro_gld_signal_diversifier`
- `macro_gld_signal_context_only`
- `macro_gld_signal_too_defensive`
- `macro_gld_signal_drawdown_not_fixed`
- `macro_gld_signal_duplicate_reference`
- `macro_gld_signal_data_blocked`
- `macro_gld_signal_weak`

Standalone diagnostic evidence requires all of:

- CAGR `>= 0.0600`.
- Max drawdown `>= -0.3000`.
- Calmar or return/drawdown proxy `>= 0.2500`.
- Same-window total return greater than BIL by at least `0.5000` cumulative return units.
- Average BIL/cash share `<= 0.5500`.

Portfolio-diversifier diagnostic evidence requires all of:

- Active VM/DSR combo max-drawdown improvement `>= 0.0300`, where supported.
- Active VM/DSR combo total-return drag `>= -0.0200`, where supported.
- Correlation to active combo `< 0.7500`, where supported.
- Average BIL/cash share `<= 0.6500`.

Failure labels:

- `macro_gld_signal_too_defensive`: average BIL/cash share `> 0.6500` or CAGR `< 0.0400`.
- `macro_gld_signal_drawdown_not_fixed`: max drawdown `< -0.3500`.
- `macro_gld_signal_duplicate_reference`: correlation to SPY_200d/static all-weather/active combo `>= 0.9000`, where supported.
- `macro_gld_signal_weak`: CAGR `< 0.0600` and no portfolio-diversifier criterion passes.

Concept-level continuation requires at least `2` rows from different concepts to satisfy either standalone diagnostic evidence or portfolio-diversifier diagnostic evidence.

These criteria do not create promotion, candidate_exhaustive, or paper-forward eligibility.
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "new_research_lane_run",
        "new_strategy_discovery_run",
        "new_backtests_run",
        "new_performance_metrics_from_raw_data_computed",
        "hidden_parameter_grid_created",
        "provider_download",
        "intraday_data_used",
        "broker_api_called",
        "promotion_candidates_created",
        "candidate_exhaustive_run",
        "paper_forward_activation",
        "real_money_recommendation",
        "active_vm_preserved",
        "active_dsr_preserved",
        "static_all_weather_benchmark_control_only",
        "exact_rejected_variants_reopened",
    ]
    lines = ["# Guardrail Checklist", ""]
    for key in keys:
        lines.append(f"- `{key}`: `{payload[key]}`")
    return "\n".join(lines) + "\n"


def exposure_invariants_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any future run:

- Max daily exposure must be `<= 1.0`.
- Max daily weight sum must be `<= 1.0`.
- No negative weights below tolerance.
- No NaN final weights.
- BIL/cash must be replacement/remainder only.
- BIL/cash must not accumulate on top of risky exposure.
- Zero target weights must remain zero until the next explicit rebalance target.
- Zero target weights must not be stale-forward-filled into prior nonzero allocations.
- Failed trend/momentum gates must explicitly route the failed sleeve weight to BIL or zero, as defined by the frozen rule.
"""


def historical_context_md(sources: dict[str, Any]) -> str:
    manifest = sources["lineage_manifest"]
    return f"""# Historical Lineage Context Summary

Recovered family: `{SOURCE_FAMILY}`

Recovered rows: `{manifest.get('macro_rows_recovered_count')}`

Lineage recovery completed: `{manifest.get('lineage_recovery_completed')}`

Prior lineage notes:

- `gld_gror_balanced_momentum_clean_v1` was rejected and is not reopened.
- `gld_ief_spy_defensive_rotation_v1` was rejected and is not reopened.
- Static all-weather remains benchmark/control only.
- Corrected batch v1 Macro/GLD rows remain `research_signal_lineage_blocked`.

The design uses this history to define a bounded, materially distinct research lane. It does not use recovered rows as promotion evidence.
"""


def rejected_policy_md(rows: list[dict[str, Any]]) -> str:
    design_ids = {row["variant_id"] for row in rows}
    overlap = sorted(design_ids & REJECTED_OR_CONTEXT_VARIANTS)
    return f"""# Rejected Variant Exclusion Policy

Exact rejected/context variant IDs excluded:

{chr(10).join(f"- `{item}`" for item in sorted(REJECTED_OR_CONTEXT_VARIANTS))}

Design ID overlap with excluded IDs: `{len(overlap)}`

This design also avoids cloning exact recovered rows by:

- Removing `AGG` from the canary and sleeve designs.
- Adding explicit SPY canary and own-asset 200-day gates.
- Avoiding exact static equal-weight and 60/20/20 recovered allocations.
- Treating recovered rows as context only.
"""


def run_readiness_md(payload: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{payload['run_readiness_decision']}`

Blocker: `{payload['run_readiness_blocker']}`

If run-ready, the exact next action is:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Macro / GLD Design

This design creates no promotion, candidate_exhaustive, paper-forward, live/demo, broker, or real-money eligibility.

All planned rows are diagnostic research designs only.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Macro / GLD Bounded Design Next Action

Exact next action:

`{next_action}`

Do not execute it in this task.
"""


def consistency_check(payload: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["macro_gld_bounded_design_consistency_check.json"] = True
    design_ids = {row["variant_id"] for row in rows}
    checks = {
        "design_only": payload["macro_gld_bounded_design_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "correct_source_family": payload["source_family"] == SOURCE_FAMILY,
        "lineage_reviewed": payload["lineage_recovery_evidence_reviewed"] is True,
        "existing_state_selection": payload["selection_from_existing_roadmap_registry_only"] is True,
        "no_lane_run": payload["new_research_lane_run"] is False,
        "no_discovery_or_batch": payload["new_strategy_discovery_run"] is False
        and payload["new_research_batch_run"] is False,
        "no_backtests_or_raw_metrics": payload["new_backtests_run"] is False
        and payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_execution_variants_or_family": payload["new_variants_created_for_execution"] is False
        and payload["new_family_created"] is False,
        "no_hidden_grid": payload["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": payload["provider_download"] is False and payload["intraday_data_used"] is False,
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
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_state_preserved": payload["active_vm_preserved"] is True and payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "rejected_not_reopened": payload["exact_rejected_variants_reopened"] is False,
        "excluded_ids_not_used": len(design_ids & REJECTED_OR_CONTEXT_VARIANTS) == 0,
        "planned_count_between_6_and_12": payload["planned_variant_count_between_6_and_12"] is True
        and 6 <= len(rows) <= 12,
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_paper": all(row["paper_forward_eligibility"] is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row["candidate_exhaustive_eligibility"] is False for row in rows),
        "exposure_invariants_defined": payload["exposure_invariants_defined"] is True,
        "zero_weight_stale_forward_fill_blocked": payload["zero_weight_stale_forward_fill_blocked"] is True,
        "baseline_policy_defined": payload["baseline_comparator_policy_defined"] is True,
        "numeric_criteria_defined": payload["numeric_success_failure_criteria_defined"] is True,
        "run_readiness_valid": payload["run_readiness_decision"] in VALID_RUN_READINESS,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, sources: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    inventory = source_inventory(root)
    payload = manifest(created, output, rows, inventory, sources)

    write_json(output / "macro_gld_bounded_design_manifest.json", payload)
    write_text(output / "macro_gld_bounded_design_summary.md", summary_md(payload))
    write_text(output / "source_lineage_context_review.md", source_context_md(sources, inventory))
    write_csv(output / "planned_variant_design_table.csv", rows, DESIGN_FIELDS)
    write_text(output / "planned_variant_design_table.md", design_table_md(rows))
    write_text(output / "variant_role_definitions.md", role_definitions_md())
    write_text(output / "frozen_rule_summaries.md", frozen_rules_md(rows))
    write_text(output / "baseline_comparator_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "exposure_invariant_requirements.md", exposure_invariants_md())
    write_text(output / "historical_lineage_context_summary.md", historical_context_md(sources))
    write_text(output / "rejected_variant_exclusion_policy.md", rejected_policy_md(rows))
    write_text(output / "run_readiness_decision.md", run_readiness_md(payload))
    write_text(output / "do_not_promote_from_macro_gld_design.md", do_not_promote_md())
    write_text(output / "macro_gld_bounded_design_next_action.md", next_action_md(payload["next_action"]))
    check = consistency_check(payload, rows, output)
    write_json(output / "macro_gld_bounded_design_consistency_check.json", check)
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
                "planned_variant_count": result["planned_variant_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
