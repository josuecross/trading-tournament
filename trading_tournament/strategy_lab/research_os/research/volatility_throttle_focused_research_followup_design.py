from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import (
    replace_or_append_section,
    write_json,
    write_text,
)
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import LANE_ID as SOURCE_LANE_ID
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


LANE_ID = "volatility_throttle_focused_research_lane_v1"
SOURCE_CONCEPT = "realized_volatility_throttle"
SOURCE_FAMILY = "high_return_tactical_etf_equity_index"
SOURCE_AUDIT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run_audit" / "latest"
SOURCE_RUN_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_run" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "volatility_throttle_focused_research_followup_design" / "latest"

NEXT_ACTION_AUDIT = "audit_volatility_throttle_focused_research_followup_design"
NEXT_ACTION_RUN = "run_volatility_throttle_focused_research_followup"
NEXT_ACTION_MANUAL = "manual_review_required_after_vol_throttle_followup_design"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_RUN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

THRESHOLD_SETS = {
    "original_25_35_100_50_25": {
        "role": "confirmation_reference",
        "normal_threshold": 0.25,
        "high_threshold": 0.35,
        "normal_multiplier": 1.00,
        "high_vol_multiplier": 0.50,
        "extreme_vol_multiplier": 0.25,
        "description": "Original audited threshold set.",
    },
    "less_defensive_30_40_100_60_30": {
        "role": "minimal_robustness_less_defensive",
        "normal_threshold": 0.30,
        "high_threshold": 0.40,
        "normal_multiplier": 1.00,
        "high_vol_multiplier": 0.60,
        "extreme_vol_multiplier": 0.30,
        "description": "Slightly less defensive robustness check.",
    },
    "more_defensive_20_30_100_40_20": {
        "role": "minimal_robustness_more_defensive",
        "normal_threshold": 0.20,
        "high_threshold": 0.30,
        "normal_multiplier": 1.00,
        "high_vol_multiplier": 0.40,
        "extreme_vol_multiplier": 0.20,
        "description": "Slightly more defensive robustness check.",
    },
}

REQUIRED_OUTPUT_FILES = (
    "vol_throttle_followup_design_manifest.json",
    "vol_throttle_followup_design_summary.md",
    "source_evidence_review.md",
    "volatility_throttle_hypothesis.md",
    "followup_variant_design_table.csv",
    "followup_variant_design_table.md",
    "frozen_rule_summaries.md",
    "threshold_set_policy.md",
    "baseline_and_comparator_policy.md",
    "success_failure_criteria.md",
    "do_not_promote_from_followup_design.md",
    "vol_throttle_followup_next_action.md",
    "vol_throttle_followup_consistency_check.json",
)

DESIGN_FIELDS = (
    "lane_id",
    "variant_id",
    "variant_role",
    "source_lane",
    "source_concept",
    "source_family",
    "source_variant_id",
    "universe_group",
    "universe",
    "lookback",
    "top_n",
    "rebalance_frequency",
    "volatility_window",
    "threshold_set_id",
    "normal_vol_threshold",
    "high_vol_threshold",
    "normal_multiplier",
    "high_vol_multiplier",
    "extreme_vol_multiplier",
    "insufficient_history_rule",
    "volatility_input_rule",
    "bil_fallback_rule",
    "exposure_cap",
    "baseline_variant_id",
    "source_baseline_path",
    "source_evidence_path",
    "source_cagr",
    "source_max_drawdown",
    "source_drawdown_reduction_vs_baseline",
    "source_cagr_retention_vs_baseline",
    "source_average_bil_cash_share",
    "source_duplicate_reference_correlation",
    "comparator_control_references",
    "promotion_eligibility",
    "paper_forward_eligibility",
)

MANIFEST_BASE = {
    "volatility_throttle_followup_design_only": True,
    "lane_id": LANE_ID,
    "source_lane": SOURCE_LANE_ID,
    "source_concept": SOURCE_CONCEPT,
    "source_audit_reviewed": True,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_families_created": False,
    "provider_download": False,
    "intraday_data_used": False,
    "broker_api_called": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "broker_orders_reconciled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "promotion_candidates_created": False,
    "paper_forward_activation": False,
    "new_paper_forward_candidate_created": False,
    "candidate_exhaustive_run": False,
    "best_single_variant_promoted": False,
    "research_outputs_remain_non_promotable": True,
    "active_vm_preserved": True,
    "active_dsr_preserved": True,
    "static_all_weather_benchmark_control_only": True,
    "macro_gld_lineage_recovery_run": False,
    "macro_gld_remains_lineage_blocked_visible": True,
    "alpaca_execution_module_delegated": True,
    "includes_drawdown_guard": False,
    "includes_macro_gld": False,
    "includes_managed_futures": False,
    "leverage_allowed": False,
    "shorting_allowed": False,
    "options_allowed": False,
    "direct_futures_allowed": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def safe_slug(text: str) -> str:
    return text.replace("equity_", "").replace("_core", "core").replace("_growth", "growth")


def load_source(root: Path) -> dict[str, Any]:
    run_rows = read_csv_rows(root / SOURCE_RUN_DIR / "variant_run_results.csv")
    vol_rows = [row for row in run_rows if row.get("risk_control_concept") == SOURCE_CONCEPT]
    return {
        "audit_summary": read_text(root / SOURCE_AUDIT_DIR / "risk_control_lane_run_audit_summary.md"),
        "volatility_review": read_text(root / SOURCE_AUDIT_DIR / "volatility_throttle_review.md"),
        "concept_level_audit": read_text(root / SOURCE_AUDIT_DIR / "concept_level_audit.md"),
        "next_direction": read_text(root / SOURCE_AUDIT_DIR / "next_research_direction_decision.md"),
        "variant_rows": vol_rows,
        "all_variant_rows": run_rows,
        "family_summary": read_text(root / SOURCE_RUN_DIR / "family_run_summary.md"),
        "baseline_comparison": read_csv_rows(root / SOURCE_RUN_DIR / "baseline_comparison_results.csv"),
        "promising": read_text(root / SOURCE_RUN_DIR / "promising_risk_control_signals.md"),
        "label_summary": read_text(root / SOURCE_RUN_DIR / "risk_control_label_summary.md"),
        "do_not_promote": read_text(root / SOURCE_RUN_DIR / "do_not_promote_from_risk_control_lane_run.md"),
    }


def build_design_rows(root: Path, source_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in source_rows:
        universe_group = source["universe_group"]
        lookback = source["lookback"]
        for threshold_id, threshold in THRESHOLD_SETS.items():
            suffix = {
                "original_25_35_100_50_25": "orig",
                "less_defensive_30_40_100_60_30": "lessdef",
                "more_defensive_20_30_100_40_20": "moredef",
            }[threshold_id]
            variant_id = f"vt_focus_{suffix}_{universe_group}_mom{lookback}_top{source['top_n']}_v1"
            rows.append(
                {
                    "lane_id": LANE_ID,
                    "variant_id": variant_id,
                    "variant_role": threshold["role"],
                    "source_lane": SOURCE_LANE_ID,
                    "source_concept": SOURCE_CONCEPT,
                    "source_family": SOURCE_FAMILY,
                    "source_variant_id": source["variant_id"],
                    "universe_group": universe_group,
                    "universe": source["universe"],
                    "lookback": lookback,
                    "top_n": source["top_n"],
                    "rebalance_frequency": "monthly",
                    "volatility_window": 60,
                    "threshold_set_id": threshold_id,
                    "normal_vol_threshold": threshold["normal_threshold"],
                    "high_vol_threshold": threshold["high_threshold"],
                    "normal_multiplier": threshold["normal_multiplier"],
                    "high_vol_multiplier": threshold["high_vol_multiplier"],
                    "extreme_vol_multiplier": threshold["extreme_vol_multiplier"],
                    "insufficient_history_rule": "normal_allocation_until_60_prior_daily_baseline_returns_exist",
                    "volatility_input_rule": "60-trading-day annualized realized volatility from uncontrolled baseline tactical returns through t-1; annualize with sqrt(252); exclude BIL/fallback unless BIL was baseline-selected",
                    "bil_fallback_rule": "BIL is replacement/remainder only: final BIL allocation equals 1 minus risky multiplier, with max exposure <= 1.0",
                    "exposure_cap": 1.0,
                    "baseline_variant_id": source["baseline_variant_id"],
                    "source_baseline_path": str((root / SOURCE_RUN_DIR / "baseline_comparison_results.csv").resolve()),
                    "source_evidence_path": str((root / SOURCE_RUN_DIR / "variant_run_results.csv").resolve()),
                    "source_cagr": source["cagr"],
                    "source_max_drawdown": source["max_drawdown"],
                    "source_drawdown_reduction_vs_baseline": source["drawdown_reduction_vs_baseline"],
                    "source_cagr_retention_vs_baseline": source["cagr_retention_vs_baseline"],
                    "source_average_bil_cash_share": source["average_bil_cash_share"],
                    "source_duplicate_reference_correlation": source["duplicate_reference_correlation"],
                    "comparator_control_references": "uncontrolled_baseline|original_volatility_throttle|regime_plus_volatility_guard_comparator|spy200d_regime_filter_control",
                    "promotion_eligibility": False,
                    "paper_forward_eligibility": False,
                }
            )
    return rows


def manifest_payload(created: str, output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    threshold_sets = {row["threshold_set_id"] for row in rows}
    next_action = NEXT_ACTION_AUDIT
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        **MANIFEST_BASE,
        "planned_variant_count": len(rows),
        "planned_variant_count_lte_18": len(rows) <= 18,
        "threshold_set_count": len(threshold_sets),
        "threshold_set_count_lte_3": len(threshold_sets) <= 3,
        "next_action": next_action,
    }


def source_review_md(source: dict[str, Any]) -> str:
    return f"""# Source Evidence Review

Reviewed source audit path: `{SOURCE_AUDIT_DIR}`

Reviewed run path: `{SOURCE_RUN_DIR}`

Volatility-throttle source rows reviewed: `{len(source['variant_rows'])}`

Key source conclusion:

- Volatility throttle was selected because it had broad evidence, no duplicate/reference-like labels, high CAGR retention, median drawdown reduction near `35.86%`, and modest BIL/cash share.
- Regime plus volatility remains a comparator/control because it is more SPY-regime/reference-adjacent.
- SPY 200d remains comparator/control only.
- Strategy drawdown guard is excluded because it destroyed return.

No new performance metrics were computed in this design step.
"""


def hypothesis_md() -> str:
    return """# Volatility Throttle Hypothesis

Hypothesis:

The realized-volatility throttle may preserve most of the high-return tactical ETF signal while reducing severe drawdown without becoming a SPY-regime duplicate or an over-defensive cash/BIL strategy.

Design intent:

- Confirm the original audited threshold set.
- Test only two nearby threshold sets to check sensitivity.
- Keep the same universe groups, lookbacks, top-N, monthly rebalance cadence, local-cache daily ETF/fund wrapper constraints, and non-promotable research status.
- Treat regime+volatility and SPY 200d as comparator/control references, not as the primary follow-up lane.
"""


def design_table_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Follow-Up Variant Design Table", "", f"Planned rows: `{len(rows)}`", ""]
    for row in rows:
        lines.append(
            f"- `{row['variant_id']}`: `{row['variant_role']}`, `{row['universe_group']}`, "
            f"lookback `{row['lookback']}`, thresholds `{row['threshold_set_id']}`"
        )
    return "\n".join(lines) + "\n"


def frozen_rules_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Frozen Rule Summaries", ""]
    for row in rows:
        lines.append(f"## {row['variant_id']}")
        lines.append("")
        lines.append(
            f"Monthly top-{row['top_n']} tactical ETF wrapper momentum over `{row['lookback']}` trading days, "
            f"with 60-day realized-volatility throttle `{row['threshold_set_id']}`. "
            "Signal inputs use information through t-1; BIL is replacement/remainder only; exposure cap is 1.0. "
            "Promotion and paper-forward eligibility are false."
        )
        lines.append("")
    return "\n".join(lines)


def threshold_policy_md() -> str:
    lines = ["# Threshold Set Policy", ""]
    for threshold_id, spec in THRESHOLD_SETS.items():
        lines.append(f"## {threshold_id}")
        lines.append("")
        lines.append(f"- Role: `{spec['role']}`")
        lines.append(f"- Normal volatility: `<= {spec['normal_threshold']}`")
        lines.append(f"- High volatility: `> {spec['normal_threshold']} and <= {spec['high_threshold']}`")
        lines.append(f"- Extreme volatility: `> {spec['high_threshold']}`")
        lines.append(
            f"- Multipliers: normal `{spec['normal_multiplier']}`, high `{spec['high_vol_multiplier']}`, extreme `{spec['extreme_vol_multiplier']}`"
        )
        lines.append("")
    return "\n".join(lines)


def baseline_policy_md() -> str:
    return """# Baseline And Comparator Policy

Primary baseline:

- Mapped uncontrolled high-return tactical ETF/equity-index baseline for the same universe group, lookback, top-N, and monthly rebalance cadence.

Comparator/control references:

- Original volatility-throttle source rows.
- Regime plus volatility as comparator only.
- SPY 200d regime filter as comparator/control only.
- BIL/cash and SPY reference comparisons where supported by the eventual run.

Excluded:

- Strategy drawdown guard.
- Macro/GLD lineage recovery.
- Managed futures.
- Broad batch v2 families.
"""


def criteria_md() -> str:
    return """# Success / Failure Criteria

Research-only labels:

- `vol_throttle_signal_confirmed`
- `vol_throttle_signal_threshold_sensitive`
- `vol_throttle_signal_too_defensive`
- `vol_throttle_signal_drawdown_reduction_below_threshold`
- `vol_throttle_signal_duplicate_reference`
- `vol_throttle_signal_weak`
- `vol_throttle_signal_data_blocked`

Interesting evidence requires:

- CAGR retention must be `>= 70%` of the applicable baseline/comparator row.
- When a mapped source original-volatility-throttle row exists, CAGR retention versus that source row must be `>= 85%`.
- Max drawdown reduction must be `>= 25%` versus baseline.
- Calmar or return/drawdown proxy improvement versus baseline must be `> 0.0`.
- Average BIL/cash share must be `< 35%`; otherwise label `vol_throttle_signal_too_defensive`.
- Duplicate/reference correlation must be `< 0.90`; otherwise label `vol_throttle_signal_duplicate_reference`.
- Exposure invariant must pass with max daily exposure `<= 1.000001`.
- At least `2` related rows in the same threshold-set or parameter-sensitivity group must satisfy the numeric criteria before concept-level confirmation.

These are research interpretation criteria, not promotion or paper-forward gates.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Follow-Up Design

This packet is design-only.

It creates no:

- promotion-review candidate
- candidate_exhaustive candidate
- paper-forward candidate
- paper-forward activation
- broker/live action
- real-money recommendation

Future execution of this lane requires a separate authorized step.
"""


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# Volatility Throttle Focused Research Follow-Up Design

Lane ID: `{payload['lane_id']}`

Source lane: `{payload['source_lane']}`

Source concept: `{payload['source_concept']}`

Planned variant count: `{payload['planned_variant_count']}`

Threshold set count: `{payload['threshold_set_count']}`

Drawdown guard included: `{payload['includes_drawdown_guard']}`

Macro/GLD included: `{payload['includes_macro_gld']}`

Managed futures included: `{payload['includes_managed_futures']}`

Next action: `{payload['next_action']}`
"""


def next_action_md(next_action: str) -> str:
    return f"""# Volatility Throttle Follow-Up Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Latest Volatility Throttle Focused Follow-Up Design

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{payload['lane_id']}`
- Source lane: `{payload['source_lane']}`
- Planned variants: `{payload['planned_variant_count']}`
- Threshold sets: `{payload['threshold_set_count']}`
- New backtests run: `{payload['new_backtests_run']}`
- Provider download: `{payload['provider_download']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Paper-forward activation: `{payload['paper_forward_activation']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## Latest Volatility Throttle Focused Follow-Up Design", section))


def consistency_check(payload: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    required["vol_throttle_followup_consistency_check.json"] = True
    threshold_sets = {row["threshold_set_id"] for row in rows}
    checks = {
        "design_only": payload["volatility_throttle_followup_design_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "correct_source_lane": payload["source_lane"] == SOURCE_LANE_ID,
        "correct_source_concept": payload["source_concept"] == SOURCE_CONCEPT,
        "source_audit_reviewed": payload["source_audit_reviewed"] is True,
        "no_research_batch": payload["new_research_batch_run"] is False,
        "no_discovery": payload["new_strategy_discovery_run"] is False,
        "no_backtests": payload["new_backtests_run"] is False,
        "no_raw_data_metrics": payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_provider_download": payload["provider_download"] is False,
        "no_intraday": payload["intraday_data_used"] is False,
        "no_broker_api": payload["broker_api_called"] is False,
        "no_broker_orders": (
            payload["broker_orders_submitted"] is False
            and payload["broker_orders_cancelled"] is False
            and payload["broker_orders_reconciled"] is False
        ),
        "no_live_or_real_money": payload["live_orders"] is False and payload["real_money_recommendation"] is False,
        "no_promotion": payload["promotion_candidates_created"] is False and payload["best_single_variant_promoted"] is False,
        "no_paper_forward": payload["paper_forward_activation"] is False and payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "alpaca_delegated": payload["alpaca_execution_module_delegated"] is True,
        "planned_variant_count_lte_18": payload["planned_variant_count_lte_18"] is True and len(rows) <= 18,
        "threshold_set_count_lte_3": payload["threshold_set_count_lte_3"] is True and len(threshold_sets) <= 3,
        "drawdown_guard_not_included": payload["includes_drawdown_guard"] is False
        and all("drawdown" not in str(row["threshold_set_id"]) for row in rows),
        "macro_gld_not_included": payload["includes_macro_gld"] is False
        and not any("GLD" in row["universe"].split("|") for row in rows),
        "managed_futures_not_included": payload["includes_managed_futures"] is False,
        "leverage_not_allowed": payload["leverage_allowed"] is False,
        "shorting_not_allowed": payload["shorting_allowed"] is False,
        "options_not_allowed": payload["options_allowed"] is False,
        "direct_futures_not_allowed": payload["direct_futures_allowed"] is False,
        "variant_design_table_exists": (output / "followup_variant_design_table.csv").exists(),
        "success_failure_criteria_exists": (output / "success_failure_criteria.md").exists(),
        "do_not_promote_exists": (output / "do_not_promote_from_followup_design.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def write_outputs(root: Path, created: str, source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    payload = manifest_payload(created, output, rows)
    write_json(output / "vol_throttle_followup_design_manifest.json", payload)
    write_text(output / "vol_throttle_followup_design_summary.md", summary_md(payload))
    write_text(output / "source_evidence_review.md", source_review_md(source))
    write_text(output / "volatility_throttle_hypothesis.md", hypothesis_md())
    write_csv(output / "followup_variant_design_table.csv", rows, DESIGN_FIELDS)
    write_text(output / "followup_variant_design_table.md", design_table_md(rows))
    write_text(output / "frozen_rule_summaries.md", frozen_rules_md(rows))
    write_text(output / "threshold_set_policy.md", threshold_policy_md())
    write_text(output / "baseline_and_comparator_policy.md", baseline_policy_md())
    write_text(output / "success_failure_criteria.md", criteria_md())
    write_text(output / "do_not_promote_from_followup_design.md", do_not_promote_md())
    write_text(output / "vol_throttle_followup_next_action.md", next_action_md(payload["next_action"]))
    consistency = consistency_check(payload, rows, output)
    write_json(output / "vol_throttle_followup_consistency_check.json", consistency)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    source = load_source(root)
    rows = build_design_rows(root, source["variant_rows"])
    return write_outputs(root, created, source, rows)


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "planned_variant_count": result["planned_variant_count"],
                "threshold_set_count": result["threshold_set_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
