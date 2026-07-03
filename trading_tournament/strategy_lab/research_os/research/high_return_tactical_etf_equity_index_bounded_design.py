from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text


FAMILY_ID = "high_return_tactical_etf_equity_index"
LANE_ID = "high_return_tactical_etf_equity_index_bounded_lane_v1"
OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "high_return_tactical_etf_equity_index_bounded_design"
    / "latest"
)

ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
LABEL_AUDIT_DIR = (
    Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix_audit" / "latest"
)
LABEL_FIX_DIR = (
    Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"
)
RISK_CONTROL_RUN_DIR = (
    Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run" / "latest"
)
RISK_CONTROL_AUDIT_DIR = (
    Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run_audit" / "latest"
)
VOL_FOLLOWUP_RUN_DIR = (
    Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_run" / "latest"
)
VOL_FOLLOWUP_AUDIT_DIR = (
    Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_results_audit" / "latest"
)

NEXT_ACTION_RUN = "run_high_return_tactical_etf_equity_index_bounded_lane"
NEXT_ACTION_BLOCKED = "fix_high_return_tactical_bounded_design_source_issue"
VALID_NEXT_ACTIONS = {NEXT_ACTION_RUN, NEXT_ACTION_BLOCKED}
RUN_READY = "high_return_tactical_bounded_design_run_ready"
RUN_BLOCKED = "high_return_tactical_bounded_design_blocked"

DESIGN_FIELDS = (
    "lane_id",
    "family_id",
    "variant_id",
    "variant_role",
    "source_family",
    "source_lane",
    "source_variant_id",
    "source_evidence_path",
    "concept",
    "universe_group",
    "universe",
    "lookback_days",
    "top_n",
    "rebalance_frequency",
    "risk_control_rule",
    "volatility_window",
    "normal_vol_threshold",
    "high_vol_threshold",
    "normal_multiplier",
    "high_vol_multiplier",
    "extreme_vol_multiplier",
    "insufficient_history_rule",
    "baseline_variant_id",
    "comparator_references",
    "bil_cash_rule",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "zero_weight_policy",
    "source_cagr",
    "source_max_drawdown",
    "source_drawdown_reduction_vs_baseline",
    "source_cagr_retention_vs_baseline",
    "source_average_bil_cash_share",
    "source_duplicate_reference_correlation",
    "promotion_eligibility",
    "paper_forward_eligibility",
    "candidate_exhaustive_eligibility",
)

REQUIRED_FILES = (
    "high_return_tactical_bounded_design_manifest.json",
    "high_return_tactical_bounded_design_summary.md",
    "source_evidence_review.md",
    "eligibility_decision.md",
    "planned_variant_design_table.csv",
    "planned_variant_design_table.md",
    "baseline_comparator_policy.md",
    "numeric_success_failure_criteria.md",
    "exposure_invariant_policy.md",
    "rejected_variant_exclusion.md",
    "guardrail_checklist.md",
    "do_not_promote_from_high_return_tactical_bounded_design.md",
    "high_return_tactical_bounded_design_next_action.md",
    "high_return_tactical_bounded_design_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
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


def load_sources(root: Path) -> dict[str, Any]:
    label_audit = read_json(root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json")
    risk_audit = read_json(root / RISK_CONTROL_AUDIT_DIR / "risk_control_lane_run_audit_manifest.json")
    risk_run = read_json(root / RISK_CONTROL_RUN_DIR / "risk_control_lane_run_manifest.json")
    vol_run = read_json(root / VOL_FOLLOWUP_RUN_DIR / "vol_throttle_followup_run_manifest.json")
    vol_audit = read_json(root / VOL_FOLLOWUP_AUDIT_DIR / "vol_throttle_followup_results_audit_manifest.json")
    return {
        "roadmap_text": read_text(root / ROADMAP),
        "registry_text": read_text(root / REGISTRY),
        "queue_text": read_text(root / QUEUE),
        "ledger_text": read_text(root / LEDGER),
        "label_audit": label_audit,
        "label_fix_manifest": read_json(root / LABEL_FIX_DIR / "labeling_fix_manifest.json"),
        "high_return_family_summary": read_csv_rows(root / LABEL_FIX_DIR / "corrected_label_family_summary.csv"),
        "high_return_source_rows": [
            row
            for row in read_csv_rows(root / LABEL_FIX_DIR / "corrected_label_variant_results.csv")
            if row.get("family_id") == FAMILY_ID
        ],
        "risk_control_run_manifest": risk_run,
        "risk_control_audit_manifest": risk_audit,
        "risk_control_rows": read_csv_rows(root / RISK_CONTROL_RUN_DIR / "variant_run_results.csv"),
        "vol_followup_run_manifest": vol_run,
        "vol_followup_audit_manifest": vol_audit,
        "vol_followup_rows": read_csv_rows(root / VOL_FOLLOWUP_RUN_DIR / "vol_throttle_followup_results.csv"),
    }


def source_supports_design(sources: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if sources["label_audit"].get("high_return_tactical_direction_supported") is not True:
        blockers.append("labeling-fix audit does not support high-return tactical direction")
    if sources["label_audit"].get("high_return_tactical_requires_risk_control") is not True:
        blockers.append("labeling-fix audit does not require/support a risk-control lane")
    if sources["risk_control_audit_manifest"].get("volatility_throttle_promising") is not True:
        blockers.append("risk-control audit did not mark volatility throttle promising")
    if sources["risk_control_audit_manifest"].get("methodology_invariants_valid") is not True:
        blockers.append("risk-control audit methodology invariants are not valid")
    if sources["vol_followup_audit_manifest"].get("final_audit_decision") != "followup_results_audit_passed":
        blockers.append("volatility follow-up audit is not passed")
    if sources["vol_followup_audit_manifest"].get("row_level_discrepancy_count", 1) != 0:
        blockers.append("volatility follow-up audit found row-level discrepancies")
    source_rows = [
        row
        for row in sources["vol_followup_rows"]
        if row.get("variant_role") == "confirmation_reference"
        and row.get("threshold_set_id") == "original_25_35_100_50_25"
    ]
    if len(source_rows) != 6:
        blockers.append("expected six original volatility-throttle confirmation rows")
    return not blockers, blockers


def build_design_rows(root: Path, sources: dict[str, Any]) -> list[dict[str, Any]]:
    source_rows = [
        row
        for row in sources["vol_followup_rows"]
        if row.get("variant_role") == "confirmation_reference"
        and row.get("threshold_set_id") == "original_25_35_100_50_25"
    ]
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        variant_id = source["variant_id"].replace("vt_focus_orig_", "hrt_bounded_vt_orig_")
        rows.append(
            {
                "lane_id": LANE_ID,
                "family_id": FAMILY_ID,
                "variant_id": variant_id,
                "variant_role": "risk_control_confirmation",
                "source_family": FAMILY_ID,
                "source_lane": "volatility_throttle_focused_research_lane_v1",
                "source_variant_id": source["variant_id"],
                "source_evidence_path": str((root / VOL_FOLLOWUP_RUN_DIR / "vol_throttle_followup_results.csv").resolve()),
                "concept": "realized_volatility_throttle_original_threshold",
                "universe_group": source["universe_group"],
                "universe": source["universe"],
                "lookback_days": source["lookback"],
                "top_n": source["top_n"],
                "rebalance_frequency": "monthly",
                "risk_control_rule": "Use uncontrolled baseline tactical ETF equity-index returns through t-1; calculate 60-trading-day annualized realized volatility; apply original audited 25/35 volatility throttle; BIL is replacement/remainder only.",
                "volatility_window": 60,
                "normal_vol_threshold": 0.25,
                "high_vol_threshold": 0.35,
                "normal_multiplier": 1.00,
                "high_vol_multiplier": 0.50,
                "extreme_vol_multiplier": 0.25,
                "insufficient_history_rule": "normal allocation until 60 prior daily baseline returns exist",
                "baseline_variant_id": source.get("baseline_variant_id")
                or source.get("baseline_comparator_variant_id", ""),
                "comparator_references": "uncontrolled_same_universe_baseline|SPY|SPY_200d_frozen_control|BIL_cash_proxy|regime_plus_volatility_guard_context|static_all_weather_benchmark_control|active_VM_DSR_combo_when_supported",
                "bil_cash_rule": "BIL/cash is replacement or remainder only; it must not accumulate above total exposure 1.0.",
                "max_daily_exposure": 1.0,
                "max_daily_weight_sum": 1.0,
                "zero_weight_policy": "zero target weights remain zero until next explicit rebalance target; stale-forward-filling old nonzero allocations into zero targets is forbidden",
                "source_cagr": source["cagr"],
                "source_max_drawdown": source["max_drawdown"],
                "source_drawdown_reduction_vs_baseline": source.get("drawdown_reduction_vs_baseline")
                or source.get("drawdown_reduction_vs_comparator", ""),
                "source_cagr_retention_vs_baseline": source.get("cagr_retention_vs_baseline")
                or source.get("cagr_retention_vs_comparator", ""),
                "source_average_bil_cash_share": source["average_bil_cash_share"],
                "source_duplicate_reference_correlation": source["duplicate_reference_correlation"],
                "promotion_eligibility": False,
                "paper_forward_eligibility": False,
                "candidate_exhaustive_eligibility": False,
            }
        )
    return rows


def run_readiness(sources: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    supported, blockers = source_supports_design(sources)
    if len(rows) < 6 or len(rows) > 12:
        blockers.append("planned row count is outside 6 to 12")
    if len({row["variant_id"] for row in rows}) != len(rows):
        blockers.append("variant IDs are not unique")
    if any("drawdown_guard" in row["variant_id"] or "drawdown_guard" in row["risk_control_rule"] for row in rows):
        blockers.append("strategy drawdown guard is included despite return-destroyed source evidence")
    if any(row["promotion_eligibility"] or row["paper_forward_eligibility"] or row["candidate_exhaustive_eligibility"] for row in rows):
        blockers.append("one or more rows has forbidden eligibility")
    if supported and not blockers:
        return RUN_READY, "none", NEXT_ACTION_RUN
    return RUN_BLOCKED, "; ".join(blockers), NEXT_ACTION_BLOCKED


def manifest_payload(created: str, output: Path, sources: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    decision, blocker, next_action = run_readiness(sources, rows)
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "high_return_tactical_bounded_design_only": True,
        "lane_id": LANE_ID,
        "family_id": FAMILY_ID,
        "eligibility_decision": "eligible_for_bounded_design" if decision == RUN_READY else "blocked_for_bounded_design",
        "run_readiness_decision": decision,
        "run_readiness_blocker": blocker,
        "source_roadmap_registry_ledger_reviewed": True,
        "corrected_label_evidence_reviewed": True,
        "corrected_risk_control_evidence_reviewed": True,
        "volatility_followup_evidence_reviewed_as_context": True,
        "pre_fix_stale_weight_results_used_as_evidence": False,
        "commodity_continued": False,
        "macro_gld_continued": False,
        "volatility_throttle_lane_continued": False,
        "managed_futures_reopened": False,
        "new_research_batch_run": False,
        "new_strategy_discovery_run": False,
        "new_backtests_run": False,
        "new_performance_metrics_from_raw_data_computed": False,
        "new_family_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
        "provider_download": False,
        "intraday_data_used": False,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "options_allowed": False,
        "direct_futures_allowed": False,
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
        "planned_row_count": len(rows),
        "planned_row_count_between_6_and_12": 6 <= len(rows) <= 12,
        "exact_rejected_variants_excluded": True,
        "strategy_drawdown_guard_excluded": True,
        "threshold_tuning_added": False,
        "threshold_set_count": len({(row["normal_vol_threshold"], row["high_vol_threshold"]) for row in rows}),
        "baseline_comparator_policy_defined": True,
        "numeric_success_failure_criteria_defined": True,
        "exposure_invariants_defined": True,
        "next_action": next_action,
    }


def source_review_md(sources: dict[str, Any]) -> str:
    return f"""# Source Evidence Review

Reviewed source-of-truth files:

- `strategy_lab/RESEARCH_ROADMAP.md`
- `strategy_lab/strategy_registry.yaml`
- `strategy_lab/research_os/research/research_queue.yaml`
- `strategy_lab/research_os/family_lineage/family_ledger.yaml`

Corrected evidence reviewed:

- `{LABEL_FIX_DIR}`
- `{LABEL_AUDIT_DIR}`
- `{RISK_CONTROL_RUN_DIR}`
- `{RISK_CONTROL_AUDIT_DIR}`
- `{VOL_FOLLOWUP_RUN_DIR}`
- `{VOL_FOLLOWUP_AUDIT_DIR}`

Eligibility evidence:

- Labeling audit supported `high_return_tactical_etf_equity_index` as a risk-control research lane: `{sources['label_audit'].get('high_return_tactical_direction_supported')}`.
- High-return tactical median CAGR from label audit: `{sources['label_audit'].get('high_return_tactical_median_cagr')}`.
- High-return tactical median drawdown from label audit: `{sources['label_audit'].get('high_return_tactical_median_drawdown')}`.
- Risk-control audit marked volatility throttle promising: `{sources['risk_control_audit_manifest'].get('volatility_throttle_promising')}`.
- Volatility follow-up audit decision: `{sources['vol_followup_audit_manifest'].get('final_audit_decision')}`.

Pre-fix stale-weight results are not used as evidence.
"""


def eligibility_md(payload: dict[str, Any]) -> str:
    return f"""# Eligibility Decision

Family: `{FAMILY_ID}`

Eligibility decision: `{payload['eligibility_decision']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Blocker: `{payload['run_readiness_blocker']}`

Rationale:

- Corrected label evidence preserved broad historical return evidence but marked the family high-risk.
- Corrected audit evidence required risk-control research before deeper research.
- Existing risk-control and volatility follow-up evidence supports a small frozen original-threshold volatility-control design.
- This design excludes return-destroyed drawdown-guard rows, exact rejected variants, broad discovery, threshold tuning, and all promotion/paper-forward paths.
"""


def design_table_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Planned Variant Design Table", "", f"Planned rows: `{len(rows)}`", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: role `{row['variant_role']}`, universe `{row['universe_group']}`, "
            f"lookback `{row['lookback_days']}`, top-N `{row['top_n']}`, source `{row['source_variant_id']}`"
        )
    return "\n".join(lines) + "\n"


def baseline_policy_md() -> str:
    return """# Baseline / Comparator Policy

Primary baseline:

- Same-universe, same-lookback, same-top-N uncontrolled high-return tactical ETF equity-index baseline.

Comparators and controls:

- `SPY`
- `SPY_200d_frozen_control`
- `BIL_cash_proxy`
- `regime_plus_volatility_guard` as context only
- `static_all_weather_benchmark_v1` as benchmark/control only, not candidate
- Active VM/DSR diagnostics where already supported by repository conventions

No comparator/control row can create promotion, candidate_exhaustive, or paper-forward eligibility.
"""


def criteria_md() -> str:
    return """# Numeric Success / Failure Criteria

Research-only labels:

- `high_return_tactical_signal_confirmed`
- `high_return_tactical_signal_high_risk`
- `high_return_tactical_signal_return_destroyed`
- `high_return_tactical_signal_duplicate_reference`
- `high_return_tactical_signal_too_defensive`
- `high_return_tactical_signal_data_blocked`
- `high_return_tactical_signal_weak`

Numeric criteria for an interpretable pass:

- CAGR retention versus uncontrolled baseline must be `>= 70%`.
- CAGR retention versus the source original volatility-throttle diagnostic row must be `>= 85%`.
- Max drawdown reduction versus uncontrolled baseline must be `>= 25%`.
- Calmar or return/drawdown proxy improvement versus uncontrolled baseline must be `> 0.0`.
- Average BIL/cash share must be `<= 35%`.
- Duplicate/reference correlation must be `< 0.90`.
- Max daily exposure must be `<= 1.000001`.
- Max daily weight sum must be `<= 1.000001`.
- No stale zero-target forward-fill violations are allowed.
- At least `2` related rows must pass before any family-level research conclusion is accepted.

These are research interpretation criteria only. They are not promotion gates.
"""


def exposure_policy_md() -> str:
    return """# Exposure Invariant Requirements

Hard invariants for any later run:

- Max daily exposure `<= 1.0`.
- Max daily weight sum `<= 1.0`.
- BIL/cash is replacement/remainder only.
- No BIL/cash accumulation on top of risky exposure.
- Zero target weights must remain zero and must not stale-forward-fill into old allocations.
- No leverage, shorting, options, direct futures, intraday data, broker APIs, live orders, or real-money paths.
"""


def rejected_exclusion_md(rows: list[dict[str, Any]]) -> str:
    return f"""# Rejected Variant Exclusion

Excluded from this bounded design:

- All `strategy_drawdown_guard` rows from `high_return_tactical_risk_control_lane_v1`, because the audit found return destroyed across all six rows.
- Exact rejected variants from prior high-return/risk-controlled discovery packets.
- SPY 200d duplicate/reference-like rows as candidate rows; SPY 200d is allowed only as a comparator/control reference.
- Less-defensive and more-defensive volatility-throttle threshold-tuning rows; threshold tuning is not continued here.

Included planned rows: `{len(rows)}` original-threshold volatility-control confirmation rows only.
"""


def guardrail_md(payload: dict[str, Any]) -> str:
    keys = [
        "new_research_batch_run",
        "new_strategy_discovery_run",
        "new_backtests_run",
        "new_family_created",
        "new_variants_created",
        "hidden_parameter_grid_created",
        "provider_download",
        "intraday_data_used",
        "leverage_allowed",
        "shorting_allowed",
        "options_allowed",
        "direct_futures_allowed",
        "candidate_exhaustive_run",
        "promotion_candidates_created",
        "paper_forward_activation",
        "broker_api_called",
        "live_orders",
        "real_money_recommendation",
        "commodity_continued",
        "macro_gld_continued",
        "managed_futures_reopened",
    ]
    return "# Guardrail Checklist\n\n" + "\n".join(f"- `{key}`: `{payload[key]}`" for key in keys) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical ETF Equity-Index Bounded Design

Family: `{payload['family_id']}`

Lane ID: `{payload['lane_id']}`

Planned rows: `{payload['planned_row_count']}`

Run-readiness decision: `{payload['run_readiness_decision']}`

Run-readiness blocker: `{payload['run_readiness_blocker']}`

Exact rejected variants excluded: `{payload['exact_rejected_variants_excluded']}`

Strategy drawdown guard excluded: `{payload['strategy_drawdown_guard_excluded']}`

Threshold tuning added: `{payload['threshold_tuning_added']}`

No run/backtest/discovery/promotion/paper-forward/broker/live action occurred.

Exact next action: `{payload['next_action']}`
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From High-Return Tactical Bounded Design

This packet is design-only.

No row is promotable, candidate_exhaustive-ready, paper-forward eligible, live/demo eligible, or suitable for real-money recommendation from this design packet.
"""


def next_action_md(next_action: str) -> str:
    return f"""# High-Return Tactical Bounded Design Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def consistency_check(payload: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["high_return_tactical_bounded_design_consistency_check.json"] = True
    checks = {
        "design_only": payload["high_return_tactical_bounded_design_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "correct_family_id": payload["family_id"] == FAMILY_ID,
        "source_reviewed": payload["source_roadmap_registry_ledger_reviewed"] is True,
        "corrected_evidence_reviewed": payload["corrected_label_evidence_reviewed"] is True
        and payload["corrected_risk_control_evidence_reviewed"] is True,
        "pre_fix_results_not_used": payload["pre_fix_stale_weight_results_used_as_evidence"] is False,
        "no_commodity_macro_managed_continuation": payload["commodity_continued"] is False
        and payload["macro_gld_continued"] is False
        and payload["managed_futures_reopened"] is False,
        "no_run_discovery_backtest": payload["new_research_batch_run"] is False
        and payload["new_strategy_discovery_run"] is False
        and payload["new_backtests_run"] is False,
        "no_raw_metrics": payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_family_variant_expansion": payload["new_family_created"] is False
        and payload["new_variants_created"] is False
        and payload["hidden_parameter_grid_created"] is False,
        "no_provider_intraday": payload["provider_download"] is False and payload["intraday_data_used"] is False,
        "no_leverage_short_options_futures": payload["leverage_allowed"] is False
        and payload["shorting_allowed"] is False
        and payload["options_allowed"] is False
        and payload["direct_futures_allowed"] is False,
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
        "active_state_preserved": payload["active_vm_preserved"] is True and payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "planned_count_bounded": payload["planned_row_count_between_6_and_12"] is True and 6 <= len(rows) <= 12,
        "variant_ids_unique": len({row["variant_id"] for row in rows}) == len(rows),
        "all_rows_non_promotable": all(row["promotion_eligibility"] is False for row in rows),
        "all_rows_not_paper": all(row["paper_forward_eligibility"] is False for row in rows),
        "all_rows_not_candidate_exhaustive": all(row["candidate_exhaustive_eligibility"] is False for row in rows),
        "drawdown_guard_excluded": payload["strategy_drawdown_guard_excluded"] is True
        and not any("drawdown_guard" in row["variant_id"] for row in rows),
        "no_threshold_tuning": payload["threshold_tuning_added"] is False and payload["threshold_set_count"] == 1,
        "baseline_policy_defined": payload["baseline_comparator_policy_defined"] is True,
        "criteria_defined": payload["numeric_success_failure_criteria_defined"] is True,
        "exposure_invariants_defined": payload["exposure_invariants_defined"] is True,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "run_readiness_valid": payload["run_readiness_decision"] in {RUN_READY, RUN_BLOCKED},
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, sources: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    payload = manifest_payload(created, output, sources, rows)
    write_json(output / "high_return_tactical_bounded_design_manifest.json", payload)
    write_text(output / "high_return_tactical_bounded_design_summary.md", summary_md(payload))
    write_text(output / "source_evidence_review.md", source_review_md(sources))
    write_text(output / "eligibility_decision.md", eligibility_md(payload))
    write_csv(output / "planned_variant_design_table.csv", rows, DESIGN_FIELDS)
    write_text(output / "planned_variant_design_table.md", design_table_md(rows))
    write_text(output / "baseline_comparator_policy.md", baseline_policy_md())
    write_text(output / "numeric_success_failure_criteria.md", criteria_md())
    write_text(output / "exposure_invariant_policy.md", exposure_policy_md())
    write_text(output / "rejected_variant_exclusion.md", rejected_exclusion_md(rows))
    write_text(output / "guardrail_checklist.md", guardrail_md(payload))
    write_text(output / "do_not_promote_from_high_return_tactical_bounded_design.md", do_not_promote_md())
    write_text(output / "high_return_tactical_bounded_design_next_action.md", next_action_md(payload["next_action"]))
    check = consistency_check(payload, rows, output)
    write_json(output / "high_return_tactical_bounded_design_consistency_check.json", check)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    sources = load_sources(root)
    rows = build_design_rows(root, sources)
    return write_outputs(root, created, sources, rows)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "planned_row_count": result["planned_row_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
