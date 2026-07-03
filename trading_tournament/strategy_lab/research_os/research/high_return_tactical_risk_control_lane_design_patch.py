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
    evaluation_policy_md,
    frozen_rules_md,
    success_failure_md,
    variant_fieldnames,
    variant_table_md,
    write_csv,
)
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_FAMILY = "high_return_tactical_etf_equity_index"
SOURCE_AUDIT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_audit" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design_patch" / "latest"

NEXT_ACTION_AUDIT = "audit_high_return_tactical_risk_control_lane_design_patch"
NEXT_ACTION_PATCH_AGAIN = "patch_high_return_tactical_risk_control_lane_design_again"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design_patch"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_PATCH_AGAIN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_patch_manifest.json",
    "risk_control_lane_design_patch_summary.md",
    "patched_variant_design_table.csv",
    "patched_variant_design_table.md",
    "patched_frozen_rule_summaries.md",
    "explicit_threshold_policy.md",
    "fallback_and_bil_semantics.md",
    "drawdown_guard_reentry_policy.md",
    "combined_rule_precedence.md",
    "patched_success_failure_criteria.md",
    "duplication_overconservatism_policy.md",
    "do_not_run_until_patch_audited.md",
    "risk_control_lane_design_patch_next_action.md",
    "risk_control_lane_design_patch_consistency_check.json",
)

MANIFEST_BASE = {
    "risk_control_lane_design_patch_only": True,
    "lane_id": LANE_ID,
    "source_design_audit_reviewed": True,
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


def audited_variant_count(root: Path) -> int:
    manifest = read_json(root / SOURCE_AUDIT_DIR / "risk_control_lane_design_audit_manifest.json")
    return int(manifest.get("variant_count_reviewed", 0))


def variants_to_markdown(rows: list[dict[str, Any]]) -> str:
    return variant_table_md(rows).replace("# Variant Design Table", "# Patched Variant Design Table")


def write_patched_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, variant_fieldnames())


def concept_set(variants: list[dict[str, Any]]) -> set[str]:
    return {str(row["risk_control_concept"]) for row in variants}


def all_variant_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    forbidden_fragments = (
        "preregistered high-volatility threshold",
        "preregistered guard",
        "recovery condition",
        "BIL or BIL remainder",
        "materially reduced",
        "not excessive",
    )
    text = "\n".join(
        " ".join(
            str(row.get(field, ""))
            for field in ("risk_control_rule", "fallback_allocation", "cash_bil_handling_rule")
        )
        for row in variants
    )
    if any(fragment.lower() in text.lower() for fragment in forbidden_fragments):
        return False
    required_by_concept = {
        "spy200d_regime_filter": ("SPY close", "200-day SMA", "100% to BIL"),
        "realized_volatility_throttle": ("60-trading-day", "25%", "35%", "0.50", "0.25"),
        "strategy_drawdown_guard": ("-15%", "-25%", "-10%", "controlled strategy equity"),
        "regime_plus_volatility_guard": ("SPY 200-day", "volatility throttle cannot override", "uncontrolled-baseline volatility throttle"),
    }
    for concept, required in required_by_concept.items():
        rows = [row for row in variants if row["risk_control_concept"] == concept]
        if not rows:
            return False
        if any(not all(token.lower() in row["risk_control_rule"].lower() for token in required) for row in rows):
            return False
    return True


def thresholds_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(row["risk_control_rule"]) for row in variants)
    return all(token in text for token in ("200-day SMA", "60-trading-day", "25%", "35%", "-15%", "-25%", "-10%"))


def fallback_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    text = "\n".join(
        f"{row['fallback_allocation']} {row['cash_bil_handling_rule']}" for row in variants
    )
    required = ("1.00", "0.50", "0.25", "0.75", "<= 1.00", "never additive")
    return "BIL or BIL remainder" not in text and all(token in text for token in required)


def reentry_rules_explicit(variants: list[dict[str, Any]]) -> bool:
    rows = [row for row in variants if row["risk_control_concept"] == "strategy_drawdown_guard"]
    return bool(rows) and all("-10%" in row["risk_control_rule"] and "restore normal base allocation" in row["risk_control_rule"] for row in rows)


def criteria_measurable() -> bool:
    text = success_failure_md()
    required_tokens = ("25%", "60%", "70%", "15%", "40%", "5%", "10%", "-45%", "0.90")
    forbidden = ("materially reduced", "not excessive")
    return all(token in text for token in required_tokens) and not any(term in text.lower() for term in forbidden)


def explicit_threshold_policy_md() -> str:
    return """# Explicit Threshold Policy

## SPY 200-Day Regime Filter

- Risk-on if `SPY close > SPY 200-day SMA`.
- Risk-off if `SPY close <= SPY 200-day SMA`.
- In risk-on, use the base high-return tactical selected allocation.
- In risk-off, allocate `100% BIL`.
- No partial risky allocation is allowed in risk-off.
- BIL is replacement allocation only.

## Realized Volatility Throttle

- Future run calculation: 60-trading-day annualized realized volatility of the selected risky basket or base strategy return stream.
- Normal-vol regime: vol `<= 25%`; risky multiplier `1.00`; BIL allocation `0.00`.
- High-vol regime: `25% < vol <= 35%`; risky multiplier `0.50`; BIL allocation `0.50`.
- Extreme-vol regime: vol `> 35%`; risky multiplier `0.25`; BIL allocation `0.75`.
- Final total exposure must be `<= 1.0`.

## Strategy Drawdown Guard

- Future run calculation: strategy equity drawdown using only prior available daily returns.
- Warning threshold: drawdown `<= -15%` and `> -25%`; risky multiplier `0.50`; BIL allocation `0.50`.
- Hard threshold: drawdown `<= -25%`; risky multiplier `0.00`; BIL allocation `1.00`.
- Re-entry threshold: restore base allocation only after drawdown improves to better than `-10%`.
"""


def fallback_bil_md() -> str:
    return """# Fallback / BIL Semantics

- BIL is the only cash/fallback asset in this lane.
- BIL is replacement or remainder allocation only.
- BIL must never be added on top of `100%` risky allocation.
- If risky allocation multiplier is `1.00`, BIL is `0.00`.
- If risky allocation multiplier is `0.50`, BIL is `0.50`.
- If risky allocation multiplier is `0.25`, BIL is `0.75`.
- If no risky assets qualify, BIL is `1.00`.
- Weight sum must be `<= 1.00`.
"""


def drawdown_reentry_md() -> str:
    return """# Drawdown Guard Re-Entry Policy

- Drawdown is calculated from the strategy's own equity curve using only prior available daily returns in the future run.
- If drawdown is better than `-15%`, use the normal base allocation.
- If drawdown is `<= -15%` and `> -25%`, use `50%` risky allocation and `50%` BIL.
- If drawdown is `<= -25%`, use `0%` risky allocation and `100%` BIL.
- After warning or hard guard activation, restore normal base allocation only after drawdown improves to better than `-10%`.
- If drawdown remains `<= -10%`, keep the active guard allocation.
- No same-day lookahead is allowed.
- Guard state changes only after signal calculation using prior-day or prior-period information under the lane's monthly rebalance convention.
"""


def combined_precedence_md() -> str:
    return """# Combined Rule Precedence

For `regime_plus_volatility_guard` variants:

1. Apply base high-return tactical top-2 selection.
2. Apply SPY 200-day regime filter first.
3. If SPY regime is risk-off, final allocation is `100% BIL`; volatility throttle cannot override this.
4. If SPY regime is risk-on, apply the 60-day realized volatility throttle.
5. Final BIL allocation is `1.00 - risky_allocation`.
6. Final exposure must be `<= 1.00`.
"""


def duplication_policy_md() -> str:
    return """# Duplication / Overconservatism Policy

Future runs must compare behavior against SPY_200d, active VM, active DSR, active combo, BIL, and static all-weather where available.

- Flag BIL-heavy variants if average BIL share is greater than `70%`.
- Flag overconservative variants if return is mostly explained by BIL/cash timing and the tactical return signal is destroyed.
- Flag duplicate variants if correlation to existing active/reference strategies is high.
- Suggested future numeric duplicate warning threshold: correlation `>= 0.90`.

These checks are future-run interpretation rules only. This patch does not compute comparisons.
"""


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design Patch

Lane ID: `{payload['lane_id']}`

Source audit reviewed: `{payload['source_design_audit_reviewed']}`

Planned variants: `{payload['variant_count_planned']}`

Variant count changed: `{payload['variant_count_changed']}`

All variant rules explicit after patch: `{payload['all_variant_rules_explicit_after_patch']}`

Thresholds explicit after patch: `{payload['thresholds_explicit_after_patch']}`

Fallback rules explicit after patch: `{payload['fallback_rules_explicit_after_patch']}`

Re-entry rules explicit after patch: `{payload['reentry_rules_explicit_after_patch']}`

Success/failure criteria measurable after patch: `{payload['success_failure_criteria_measurable_after_patch']}`

This is a design patch only. No lane run, backtest, discovery, provider download, broker/live path, promotion, or paper-forward action occurred.

Exact next action: `{payload['next_action']}`
"""


def do_not_run_md(payload: dict[str, Any]) -> str:
    return f"""# Do Not Run Until Patch Audited

This packet patches the design but does not authorize execution.

Exact next action: `{payload['next_action']}`

The patched design requires an independent audit before any research-lane run.
"""


def next_action_md(payload: dict[str, Any]) -> str:
    return f"""# Risk-Control Lane Design Patch Next Action

Exact next action:

`{payload['next_action']}`

Do not run the next action in this task.
"""


def manifest(created: str, output: Path, variants: list[dict[str, Any]], prior_count: int) -> dict[str, Any]:
    explicit = all_variant_rules_explicit(variants)
    thresholds = thresholds_explicit(variants)
    fallback = fallback_rules_explicit(variants)
    reentry = reentry_rules_explicit(variants)
    criteria = criteria_measurable()
    variant_count_changed = prior_count != len(variants)
    success = (
        explicit
        and thresholds
        and fallback
        and reentry
        and criteria
        and len(variants) <= 24
        and not variant_count_changed
    )
    return {
        "created_utc": created,
        **MANIFEST_BASE,
        "source_family": SOURCE_FAMILY,
        "evidence_path": str(output.resolve()),
        "source_design_audit_path": str((ROOT / SOURCE_AUDIT_DIR).resolve()),
        "variant_count_planned": len(variants),
        "variant_count_changed": variant_count_changed,
        "risk_control_concepts_count": len(concept_set(variants)),
        "all_variant_rules_explicit_after_patch": explicit,
        "thresholds_explicit_after_patch": thresholds,
        "fallback_rules_explicit_after_patch": fallback,
        "reentry_rules_explicit_after_patch": reentry,
        "success_failure_criteria_measurable_after_patch": criteria,
        "patch_success_criteria_passed": success,
        "next_action": NEXT_ACTION_AUDIT if success else NEXT_ACTION_PATCH_AGAIN,
    }


def consistency_check(payload: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    checks = {
        "design_patch_only": payload["risk_control_lane_design_patch_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "source_design_audit_reviewed": payload["source_design_audit_reviewed"] is True,
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
        "all_variant_rules_explicit_after_patch": payload["all_variant_rules_explicit_after_patch"] is True,
        "thresholds_explicit_after_patch": payload["thresholds_explicit_after_patch"] is True,
        "fallback_rules_explicit_after_patch": payload["fallback_rules_explicit_after_patch"] is True,
        "reentry_rules_explicit_after_patch": payload["reentry_rules_explicit_after_patch"] is True,
        "success_failure_criteria_measurable_after_patch": payload["success_failure_criteria_measurable_after_patch"] is True,
        "max_exposure_lte_1": payload["max_exposure_allowed"] <= 1.0,
        "leverage_not_allowed": payload["leverage_allowed"] is False,
        "shorting_not_allowed": payload["shorting_allowed"] is False,
        "options_not_allowed": payload["options_allowed"] is False,
        "direct_futures_not_allowed": payload["direct_futures_allowed"] is False,
        "patched_variant_design_table_exists": (output / "patched_variant_design_table.csv").exists(),
        "patched_frozen_rule_summaries_exist": (output / "patched_frozen_rule_summaries.md").exists(),
        "explicit_threshold_policy_exists": (output / "explicit_threshold_policy.md").exists(),
        "fallback_bil_semantics_exists": (output / "fallback_and_bil_semantics.md").exists(),
        "drawdown_guard_reentry_policy_exists": (output / "drawdown_guard_reentry_policy.md").exists(),
        "combined_rule_precedence_exists": (output / "combined_rule_precedence.md").exists(),
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## High-Return Tactical Risk-Control Lane Design Patch

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{payload['lane_id']}`
- Planned variants: `{payload['variant_count_planned']}`
- Variant count changed: `{payload['variant_count_changed']}`
- Thresholds explicit after patch: `{payload['thresholds_explicit_after_patch']}`
- Success/failure criteria measurable after patch: `{payload['success_failure_criteria_measurable_after_patch']}`
- New backtests run: `{payload['new_backtests_run']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design Patch", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    variants = build_variant_plan()
    prior_count = audited_variant_count(root)
    payload = manifest(created, output, variants, prior_count)

    write_json(output / "risk_control_lane_design_patch_manifest.json", payload)
    write_text(output / "risk_control_lane_design_patch_summary.md", summary_md(payload))
    write_patched_csv(output / "patched_variant_design_table.csv", variants)
    write_text(output / "patched_variant_design_table.md", variants_to_markdown(variants))
    write_text(output / "patched_frozen_rule_summaries.md", frozen_rules_md(variants))
    write_text(output / "explicit_threshold_policy.md", explicit_threshold_policy_md())
    write_text(output / "fallback_and_bil_semantics.md", fallback_bil_md())
    write_text(output / "drawdown_guard_reentry_policy.md", drawdown_reentry_md())
    write_text(output / "combined_rule_precedence.md", combined_precedence_md())
    write_text(output / "patched_success_failure_criteria.md", success_failure_md())
    write_text(output / "duplication_overconservatism_policy.md", duplication_policy_md())
    write_text(output / "do_not_run_until_patch_audited.md", do_not_run_md(payload))
    write_text(output / "risk_control_lane_design_patch_next_action.md", next_action_md(payload))
    write_json(output / "risk_control_lane_design_patch_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output)
    write_json(output / "risk_control_lane_design_patch_consistency_check.json", check)
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
                "all_variant_rules_explicit_after_patch": result["all_variant_rules_explicit_after_patch"],
                "thresholds_explicit_after_patch": result["thresholds_explicit_after_patch"],
                "fallback_rules_explicit_after_patch": result["fallback_rules_explicit_after_patch"],
                "reentry_rules_explicit_after_patch": result["reentry_rules_explicit_after_patch"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
