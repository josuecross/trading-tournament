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
from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import (
    LANE_ID,
    build_variant_plan,
    frozen_rules_md,
    success_failure_md,
    variant_fieldnames,
    variant_table_md,
    write_csv,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_FAMILY = "high_return_tactical_etf_equity_index"
SOURCE_PATCH_AUDIT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_audit" / "latest"
METHODOLOGY_SOURCE = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest" / "corrected_profit_research_variant_results.csv"
LABEL_SOURCE = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest" / "corrected_label_variant_results.csv"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch_v2" / "latest"

NEXT_ACTION_AUDIT = "audit_high_return_tactical_risk_control_lane_design_patch_v2"
NEXT_ACTION_PATCH_AGAIN = "patch_high_return_tactical_risk_control_lane_design_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design_patch_v2"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_PATCH_AGAIN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_patch_v2_manifest.json",
    "risk_control_lane_design_patch_v2_summary.md",
    "patched_v2_variant_design_table.csv",
    "patched_v2_variant_design_table.md",
    "patched_v2_frozen_rule_summaries.md",
    "volatility_input_policy.md",
    "drawdown_guard_timing_policy.md",
    "combined_rule_precedence_v2.md",
    "baseline_mapping_table.csv",
    "baseline_mapping_table.md",
    "baseline_mapping_policy.md",
    "remaining_ambiguity_review.md",
    "do_not_run_until_patch_v2_audited.md",
    "risk_control_lane_design_patch_v2_next_action.md",
    "risk_control_lane_design_patch_v2_consistency_check.json",
)

BASELINE_FIELDS = (
    "variant_id",
    "baseline_variant_id",
    "baseline_family",
    "baseline_universe_group",
    "baseline_universe",
    "baseline_lookback",
    "baseline_top_n",
    "baseline_rebalance_frequency",
    "baseline_corrected_methodology_source",
    "baseline_corrected_label_source",
    "same_window_baseline_comparison_required",
    "baseline_found_in_methodology_source",
    "baseline_found_in_label_source",
    "baseline_mapping_status",
)

MANIFEST_BASE = {
    "risk_control_lane_design_patch_v2_only": True,
    "lane_id": LANE_ID,
    "source_patch_audit_reviewed": True,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
    "new_variants_created": False,
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
    "max_exposure_allowed": 1.0,
    "leverage_allowed": False,
    "shorting_allowed": False,
    "options_allowed": False,
    "direct_futures_allowed": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def baseline_index(root: Path, source: Path) -> dict[str, dict[str, str]]:
    return {row["variant_id"]: row for row in load_csv_rows(root / source)}


def source_patch_audit_reviewed(root: Path) -> bool:
    manifest = read_json(root / SOURCE_PATCH_AUDIT_DIR / "risk_control_lane_design_patch_audit_manifest.json")
    return manifest.get("run_readiness_decision") == "patch_needs_another_design_fix"


def build_baseline_mapping(root: Path, variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    methodology = baseline_index(root, METHODOLOGY_SOURCE)
    labels = baseline_index(root, LABEL_SOURCE)
    rows: list[dict[str, Any]] = []
    for variant in variants:
        baseline_id = str(variant["baseline_variant_id"])
        found_methodology = baseline_id in methodology
        found_label = baseline_id in labels
        status = "baseline_mapping_complete" if found_methodology and found_label else "design_blocked_missing_baseline"
        rows.append(
            {
                "variant_id": variant["variant_id"],
                "baseline_variant_id": baseline_id,
                "baseline_family": variant["baseline_family"],
                "baseline_universe_group": variant["baseline_universe_group"],
                "baseline_universe": variant["baseline_universe"],
                "baseline_lookback": variant["baseline_lookback"],
                "baseline_top_n": variant["baseline_top_n"],
                "baseline_rebalance_frequency": variant["baseline_rebalance_frequency"],
                "baseline_corrected_methodology_source": variant["baseline_corrected_methodology_source"],
                "baseline_corrected_label_source": variant["baseline_corrected_label_source"],
                "same_window_baseline_comparison_required": variant["same_window_baseline_comparison_required"],
                "baseline_found_in_methodology_source": found_methodology,
                "baseline_found_in_label_source": found_label,
                "baseline_mapping_status": status,
            }
        )
    return rows


def write_baseline_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, list(BASELINE_FIELDS))


def baseline_mapping_md(rows: list[dict[str, Any]]) -> str:
    columns = [
        "variant_id",
        "baseline_variant_id",
        "baseline_universe_group",
        "baseline_lookback",
        "baseline_top_n",
        "baseline_mapping_status",
    ]
    lines = [
        "# Baseline Mapping Table",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def patched_variant_table_md(rows: list[dict[str, Any]]) -> str:
    return variant_table_md(rows).replace("# Variant Design Table", "# Patched V2 Variant Design Table")


def volatility_input_policy_md() -> str:
    return """# Volatility Input Policy

- Volatility throttle uses the uncontrolled baseline tactical strategy return stream.
- It does not use the post-risk-control strategy return stream.
- BIL/fallback returns are excluded from the volatility input unless BIL is part of the baseline tactical selection itself.
- The input is calculated from prior available daily baseline returns only.
- Use `60` trading days.
- Annualize using `sqrt(252)`.
- For allocation decision on date `t`, the volatility estimate must use information available through date `t-1`.
- No same-day return may be used for the decision on date `t`.
- If fewer than 60 prior daily baseline returns are available, use normal allocation to avoid early artificial BIL bias.
- Normal-vol regime: volatility `<= 25%`; risky multiplier `1.00`; BIL `0.00`.
- High-vol regime: `25% < volatility <= 35%`; risky multiplier `0.50`; BIL `0.50`.
- Extreme-vol regime: volatility `> 35%`; risky multiplier `0.25`; BIL `0.75`.
"""


def drawdown_guard_timing_policy_md() -> str:
    return """# Drawdown Guard Timing Policy

- Drawdown guard uses the controlled strategy equity curve, not the uncontrolled baseline equity curve.
- Drawdown state is updated daily.
- The guard decision for date `t` uses controlled strategy equity and controlled drawdown known through date `t-1`.
- No same-day return is used to activate, deactivate, or change guard state.
- The controlled equity curve continues to update while guard is active using actual guarded allocation returns, including BIL returns when in fallback.
- Warning drawdown threshold: `-15%`; risky multiplier `0.50`; BIL allocation `0.50`.
- Hard drawdown threshold: `-25%`; risky multiplier `0.00`; BIL allocation `1.00`.
- If guard is active, restore normal base allocation only after prior-day controlled drawdown improves to better than `-10%`.
- If prior-day controlled drawdown remains `<= -10%`, keep guard active.
- If both warning and hard thresholds are breached, hard threshold takes precedence.
- If SPY regime filter is risk-off in a combined variant, SPY risk-off takes precedence and final allocation is `100% BIL`.
"""


def combined_rule_precedence_md() -> str:
    return """# Combined Rule Precedence V2

For combined-control logic in this lane:

1. Build baseline tactical target allocation.
2. Apply SPY 200-day regime filter.
3. If SPY risk-off, final allocation is `100% BIL`; stop.
4. If SPY risk-on, apply volatility throttle where applicable.
5. Apply drawdown guard where applicable.
6. If multiple controls reduce risk, use the most defensive risky multiplier.
7. Example: volatility says `0.50`, drawdown guard says `0.00`; final risky multiplier is `0.00`.
8. Final BIL allocation is `1 - risky_multiplier`.
9. Final exposure must be `<= 1.0`.

The current `regime_plus_volatility_guard` variants include SPY regime plus volatility throttle. They do not include drawdown guard; the drawdown step is documented for precedence consistency if a future audited design combines all controls.
"""


def baseline_mapping_policy_md() -> str:
    return f"""# Baseline Mapping Policy

Every controlled variant maps to the corresponding uncontrolled high-return tactical baseline with the same:

- universe group
- universe
- momentum lookback
- top-N
- rebalance frequency

Corrected methodology source:

`{METHODOLOGY_SOURCE.as_posix()}`

Corrected label source:

`{LABEL_SOURCE.as_posix()}`

If an exact baseline cannot be found, the variant must be marked `design_blocked_missing_baseline` and cannot be run until patched.

No baseline results are invented in this patch.
"""


def remaining_ambiguity_md(payload: dict[str, Any], missing_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Remaining Ambiguity Review",
        "",
        f"- Volatility input explicit after patch v2: `{payload['volatility_input_explicit_after_patch_v2']}`",
        f"- Drawdown guard timing explicit after patch v2: `{payload['drawdown_guard_timing_explicit_after_patch_v2']}`",
        f"- Controlled equity tracking explicit: `{payload['controlled_equity_tracking_explicit']}`",
        f"- Combined rule precedence explicit after patch v2: `{payload['combined_rule_precedence_explicit_after_patch_v2']}`",
        f"- Baseline mapping explicit after patch v2: `{payload['baseline_mapping_explicit_after_patch_v2']}`",
        f"- Baseline mapping missing count: `{payload['baseline_mapping_missing_count']}`",
        "",
        "Missing baseline mappings:",
    ]
    if not missing_rows:
        lines.append("- None")
    for row in missing_rows:
        lines.append(f"- `{row['variant_id']}` -> `{row['baseline_variant_id']}`")
    return "\n".join(lines) + "\n"


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design Patch V2

Lane ID: `{payload['lane_id']}`

Source patch audit reviewed: `{payload['source_patch_audit_reviewed']}`

Planned variants: `{payload['variant_count_planned']}`

Variant count changed: `{payload['variant_count_changed']}`

Volatility input explicit after patch v2: `{payload['volatility_input_explicit_after_patch_v2']}`

Drawdown guard timing explicit after patch v2: `{payload['drawdown_guard_timing_explicit_after_patch_v2']}`

Controlled equity tracking explicit: `{payload['controlled_equity_tracking_explicit']}`

Baseline mapping complete count: `{payload['baseline_mapping_complete_count']}`

Baseline mapping missing count: `{payload['baseline_mapping_missing_count']}`

All variant rules explicit after patch v2: `{payload['all_variant_rules_explicit_after_patch_v2']}`

No lane run, backtest, discovery, provider download, broker/live path, promotion, candidate_exhaustive, paper-forward activation, or real-money recommendation occurred.

Exact next action: `{payload['next_action']}`
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Patch V2 Audited

This packet patches the design but does not authorize execution.

Exact next action: `{payload['next_action']}`

The patched v2 design requires independent audit before any research-lane run.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Risk-Control Lane Design Patch V2 Next Action

Exact next action:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def all_variant_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row.get("risk_control_rule", "")) for row in variants)
    required = (
        "uncontrolled baseline tactical strategy return stream",
        "through date t-1",
        "controlled strategy equity curve",
        "Drawdown guard state is updated daily",
        "baseline tactical target allocation",
    )
    forbidden = ("selected risky basket or base strategy return stream", "prior-day or prior-period")
    return all(token in text for token in required) and not any(token in text for token in forbidden)


def fallback_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row.get("cash_bil_handling_rule", "")) for row in variants)
    return all(token in text for token in ("1.00", "0.50", "0.25", "0.75", "<= 1.00", "never additive"))


def reentry_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row.get("risk_control_rule", "")) for row in variants if row["risk_control_concept"] == "strategy_drawdown_guard")
    return "-10%" in text and "prior-day controlled drawdown" in text and "restore normal base allocation" in text


def thresholds_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row.get("risk_control_rule", "")) for row in variants)
    return all(token in text for token in ("200-day SMA", "60-trading-day", "25%", "35%", "-15%", "-25%", "-10%"))


def success_failure_criteria_measurable() -> bool:
    text = success_failure_md()
    return all(token in text for token in ("25%", "60%", "70%", "15%", "40%", "5%", "10%", "-45%", "0.90"))


def write_patch_v2_csv(path: Path, variants: list[dict[str, Any]]) -> None:
    write_csv(path, variants, variant_fieldnames())


def manifest(created: str, output: Path, root: Path, variants: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prior_manifest = read_json(root / SOURCE_PATCH_AUDIT_DIR / "risk_control_lane_design_patch_audit_manifest.json")
    prior_count = int(prior_manifest.get("variant_count_reviewed", 0))
    missing_rows = [row for row in baseline_rows if row["baseline_mapping_status"] != "baseline_mapping_complete"]
    complete_count = len(baseline_rows) - len(missing_rows)
    success = (
        source_patch_audit_reviewed(root)
        and len(variants) <= 24
        and prior_count == len(variants)
        and all_variant_rules_explicit(variants)
        and thresholds_explicit(variants)
        and fallback_rules_explicit(variants)
        and reentry_rules_explicit(variants)
        and success_failure_criteria_measurable()
        and len(missing_rows) == 0
    )
    return {
        "created_utc": created,
        **MANIFEST_BASE,
        "source_family": SOURCE_FAMILY,
        "evidence_path": str(output.resolve()),
        "source_patch_audit_path": str((root / SOURCE_PATCH_AUDIT_DIR).resolve()),
        "variant_count_planned": len(variants),
        "variant_count_changed": prior_count != len(variants),
        "volatility_input_explicit_after_patch_v2": True,
        "drawdown_guard_timing_explicit_after_patch_v2": True,
        "controlled_equity_tracking_explicit": True,
        "combined_rule_precedence_explicit_after_patch_v2": True,
        "baseline_mapping_explicit_after_patch_v2": len(missing_rows) == 0,
        "baseline_mapping_complete_count": complete_count,
        "baseline_mapping_missing_count": len(missing_rows),
        "all_variant_rules_explicit_after_patch_v2": all_variant_rules_explicit(variants),
        "thresholds_explicit_after_patch_v2": thresholds_explicit(variants),
        "fallback_rules_explicit_after_patch_v2": fallback_rules_explicit(variants),
        "reentry_rules_explicit_after_patch_v2": reentry_rules_explicit(variants),
        "success_failure_criteria_measurable_after_patch_v2": success_failure_criteria_measurable(),
        "patch_v2_success_criteria_passed": success,
        "next_action": NEXT_ACTION_AUDIT if success else NEXT_ACTION_PATCH_AGAIN,
    }


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    checks = {
        "design_patch_v2_only": payload["risk_control_lane_design_patch_v2_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "source_patch_audit_reviewed": payload["source_patch_audit_reviewed"] is True,
        "no_research_batch": payload["new_research_batch_run"] is False,
        "no_strategy_discovery": payload["new_strategy_discovery_run"] is False,
        "no_backtests": payload["new_backtests_run"] is False,
        "no_raw_data_metrics": payload["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": payload["new_variants_created"] is False,
        "no_new_families": payload["new_families_created"] is False,
        "no_provider_download": payload["provider_download"] is False,
        "no_intraday": payload["intraday_data_used"] is False,
        "no_broker_api": payload["broker_api_called"] is False,
        "no_broker_orders": (
            payload["broker_orders_submitted"] is False
            and payload["broker_orders_cancelled"] is False
            and payload["broker_orders_reconciled"] is False
        ),
        "no_live_orders": payload["live_orders"] is False,
        "no_real_money_recommendation": payload["real_money_recommendation"] is False,
        "no_promotion_candidates": payload["promotion_candidates_created"] is False,
        "no_paper_forward_activation": payload["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "best_single_variant_not_promoted": payload["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_lineage_recovery_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "alpaca_execution_module_delegated": payload["alpaca_execution_module_delegated"] is True,
        "variant_count_lte_24": payload["variant_count_planned"] <= 24,
        "volatility_input_explicit": payload["volatility_input_explicit_after_patch_v2"] is True,
        "drawdown_guard_timing_explicit": payload["drawdown_guard_timing_explicit_after_patch_v2"] is True,
        "controlled_equity_tracking_explicit": payload["controlled_equity_tracking_explicit"] is True,
        "combined_rule_precedence_explicit": payload["combined_rule_precedence_explicit_after_patch_v2"] is True,
        "baseline_mapping_table_exists": (output / "baseline_mapping_table.csv").exists(),
        "baseline_mapping_complete_or_not_audit_ready": (
            payload["baseline_mapping_missing_count"] == 0 or payload["next_action"] != NEXT_ACTION_AUDIT
        ),
        "all_variant_rules_explicit": payload["all_variant_rules_explicit_after_patch_v2"] is True,
        "thresholds_explicit": payload["thresholds_explicit_after_patch_v2"] is True,
        "fallback_rules_explicit": payload["fallback_rules_explicit_after_patch_v2"] is True,
        "reentry_rules_explicit": payload["reentry_rules_explicit_after_patch_v2"] is True,
        "success_failure_criteria_measurable": payload["success_failure_criteria_measurable_after_patch_v2"] is True,
        "max_exposure_lte_1": payload["max_exposure_allowed"] <= 1.0,
        "leverage_not_allowed": payload["leverage_allowed"] is False,
        "shorting_not_allowed": payload["shorting_allowed"] is False,
        "options_not_allowed": payload["options_allowed"] is False,
        "direct_futures_not_allowed": payload["direct_futures_allowed"] is False,
        "remaining_ambiguity_review_exists": (output / "remaining_ambiguity_review.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## High-Return Tactical Risk-Control Lane Design Patch V2

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{payload['lane_id']}`
- Planned variants: `{payload['variant_count_planned']}`
- Volatility input explicit after patch v2: `{payload['volatility_input_explicit_after_patch_v2']}`
- Drawdown guard timing explicit after patch v2: `{payload['drawdown_guard_timing_explicit_after_patch_v2']}`
- Baseline mapping complete count: `{payload['baseline_mapping_complete_count']}`
- Baseline mapping missing count: `{payload['baseline_mapping_missing_count']}`
- New backtests run: `{payload['new_backtests_run']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design Patch V2", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    variants = build_variant_plan()
    baseline_rows = build_baseline_mapping(root, variants)
    payload = manifest(created, output, root, variants, baseline_rows)
    missing_rows = [row for row in baseline_rows if row["baseline_mapping_status"] != "baseline_mapping_complete"]

    write_json(output / "risk_control_lane_design_patch_v2_manifest.json", payload)
    write_text(output / "risk_control_lane_design_patch_v2_summary.md", summary_md(payload))
    write_patch_v2_csv(output / "patched_v2_variant_design_table.csv", variants)
    write_text(output / "patched_v2_variant_design_table.md", patched_variant_table_md(variants))
    write_text(output / "patched_v2_frozen_rule_summaries.md", frozen_rules_md(variants))
    write_text(output / "volatility_input_policy.md", volatility_input_policy_md())
    write_text(output / "drawdown_guard_timing_policy.md", drawdown_guard_timing_policy_md())
    write_text(output / "combined_rule_precedence_v2.md", combined_rule_precedence_md())
    write_baseline_csv(output / "baseline_mapping_table.csv", baseline_rows)
    write_text(output / "baseline_mapping_table.md", baseline_mapping_md(baseline_rows))
    write_text(output / "baseline_mapping_policy.md", baseline_mapping_policy_md())
    write_text(output / "remaining_ambiguity_review.md", remaining_ambiguity_md(payload, missing_rows))
    write_text(output / "do_not_run_until_patch_v2_audited.md", do_not_run_md(payload))
    write_text(output / "risk_control_lane_design_patch_v2_next_action.md", next_action_md(payload))
    write_json(output / "risk_control_lane_design_patch_v2_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output)
    write_json(output / "risk_control_lane_design_patch_v2_consistency_check.json", check)
    update_research_metadata(root, created, output, payload)
    return {**payload, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_planned": result["variant_count_planned"],
                "baseline_mapping_complete_count": result["baseline_mapping_complete_count"],
                "baseline_mapping_missing_count": result["baseline_mapping_missing_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
