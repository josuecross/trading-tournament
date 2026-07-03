from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


LANE_ID = "high_return_tactical_risk_control_lane_v1"
SOURCE_FAMILY = "high_return_tactical_etf_equity_index"
SOURCE_BATCH = "profit_oriented_research_batch_v1"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "high_return_tactical_risk_control_lane_design" / "latest"
LABEL_AUDIT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix_audit" / "latest"
METHODOLOGY_FIX_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_methodology_fix" / "latest"
LABEL_FIX_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"

NEXT_ACTION_AUDIT = "audit_high_return_tactical_risk_control_lane_design"
NEXT_ACTION_RUN = "run_high_return_tactical_risk_control_research_lane"
NEXT_ACTION_MANUAL = "manual_review_required_after_risk_control_lane_design"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {NEXT_ACTION_AUDIT, NEXT_ACTION_RUN, NEXT_ACTION_MANUAL, NEXT_ACTION_PAUSE}

REQUIRED_OUTPUT_FILES = (
    "risk_control_lane_design_manifest.json",
    "risk_control_lane_design_summary.md",
    "source_evidence_review.md",
    "risk_control_hypothesis.md",
    "variant_design_table.csv",
    "variant_design_table.md",
    "frozen_rule_summaries.md",
    "risk_control_evaluation_policy.md",
    "success_failure_criteria.md",
    "do_not_promote_from_lane_design.md",
    "risk_control_lane_next_action.md",
    "risk_control_lane_consistency_check.json",
)

MANIFEST_FLAGS = {
    "risk_control_lane_design_only": True,
    "lane_id": LANE_ID,
    "source_family": SOURCE_FAMILY,
    "source_batch": SOURCE_BATCH,
    "source_methodology_fixed": True,
    "source_labeling_fixed": True,
    "new_research_batch_run": False,
    "new_strategy_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_from_raw_data_computed": False,
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_source(root: Path) -> dict[str, Any]:
    return {
        "label_audit_manifest": read_json(root / LABEL_AUDIT_DIR / "labeling_fix_audit_manifest.json"),
        "methodology_manifest": read_json(root / METHODOLOGY_FIX_DIR / "methodology_fix_manifest.json"),
        "label_fix_manifest": read_json(root / LABEL_FIX_DIR / "labeling_fix_manifest.json"),
        "high_return_review": read_text(root / LABEL_AUDIT_DIR / "high_return_tactical_direction_review.md"),
        "risk_need": read_text(root / LABEL_AUDIT_DIR / "risk_control_research_need.md"),
        "family_direction": read_text(root / LABEL_AUDIT_DIR / "family_direction_review.md"),
        "deeper_decision": read_text(root / LABEL_AUDIT_DIR / "deeper_research_decision_after_label_audit.md"),
        "corrected_labels": pd.read_csv(root / LABEL_FIX_DIR / "corrected_label_variant_results.csv"),
    }


def build_variant_plan() -> list[dict[str, Any]]:
    universes = {
        "equity_growth_core": ("SPY", "QQQ", "IWM", "DIA", "XLK", "SCHG", "MTUM", "BIL"),
        "equity_sector_growth": ("XLK", "XLY", "XLF", "XLE", "XLV", "XLI", "BIL"),
    }
    concepts = [
        {
            "concept": "spy200d_regime_filter",
            "description": "Risk-on when SPY close is greater than its 200-day SMA; risk-off when SPY close is less than or equal to its 200-day SMA. In risk-on, hold the base top-2 tactical allocation. In risk-off, allocate 100% to BIL. BIL is replacement allocation only.",
            "suffix": "spy200d_filter",
            "fallback": "100% BIL when SPY close <= SPY 200-day SMA; otherwise 0% BIL unless no risky assets qualify.",
        },
        {
            "concept": "realized_volatility_throttle",
            "description": "Calculate 60-trading-day annualized realized volatility from the uncontrolled baseline tactical strategy return stream, using prior available daily baseline returns through date t-1 for the allocation decision on date t. Annualize with sqrt(252). Exclude BIL/fallback returns unless BIL is part of the baseline tactical selection itself. If fewer than 60 prior daily baseline returns are available, use normal allocation to avoid early artificial BIL bias. If volatility <= 25%, risky allocation multiplier is 1.00 and BIL is 0.00. If 25% < volatility <= 35%, risky allocation multiplier is 0.50 and BIL is 0.50. If volatility > 35%, risky allocation multiplier is 0.25 and BIL is 0.75. No same-day return may be used for the decision on date t.",
            "suffix": "vol_throttle",
            "fallback": "BIL receives 1.00 minus the risky allocation multiplier.",
        },
        {
            "concept": "strategy_drawdown_guard",
            "description": "Use the controlled strategy equity curve, not the uncontrolled baseline equity curve. Drawdown guard state is updated daily. The guard decision for date t uses controlled strategy equity and controlled drawdown known through date t-1; no same-day return is used to activate, deactivate, or change guard state. The controlled equity curve continues to update while guard is active using the actual guarded allocation returns, including BIL returns when in fallback. If prior-day controlled drawdown is better than -15%, use base allocation. If -25% < prior-day controlled drawdown <= -15%, risky allocation multiplier is 0.50 and BIL is 0.50. If prior-day controlled drawdown <= -25%, risky allocation multiplier is 0.00 and BIL is 1.00. If guard is active, restore normal base allocation only after prior-day controlled drawdown improves to better than -10%; otherwise keep guard active. If warning and hard thresholds are both breached, the hard threshold takes precedence.",
            "suffix": "drawdown_guard",
            "fallback": "BIL receives 0%, 50%, or 100% according to the explicit drawdown guard state.",
        },
        {
            "concept": "regime_plus_volatility_guard",
            "description": "Build baseline tactical target allocation, then apply the SPY 200-day regime filter first. If SPY risk-off, final allocation is 100% BIL and the volatility throttle cannot override this; stop. If SPY risk-on, apply the 60-day uncontrolled-baseline volatility throttle using information through date t-1. This variant has no drawdown-guard component, so the drawdown-guard precedence step is not applicable. If multiple controls reduce risk in a future combined-control design, use the most defensive risky multiplier. Final BIL allocation is 1.00 minus risky allocation and final exposure must be <= 1.00.",
            "suffix": "regime_vol_guard",
            "fallback": "100% BIL when SPY regime is risk-off; otherwise BIL receives 1.00 minus the volatility-throttled risky allocation.",
        },
    ]
    lookbacks = (63, 126, 252)
    rows: list[dict[str, Any]] = []
    for universe_name, universe in universes.items():
        for lookback in lookbacks:
            for concept in concepts:
                variant_id = f"hrt_rc_{concept['suffix']}_{universe_name}_mom{lookback}_top2_v1"
                baseline_variant_id = f"hrt_{universe_name}_mom{lookback}_top2"
                rows.append(
                    {
                        "lane_id": LANE_ID,
                        "variant_id": variant_id,
                        "source_family": SOURCE_FAMILY,
                        "universe_group": universe_name,
                        "universe": "|".join(universe),
                        "momentum_lookback_days": lookback,
                        "top_n": 2,
                        "rebalance_frequency": "monthly",
                        "baseline_variant_id": baseline_variant_id,
                        "baseline_family": SOURCE_FAMILY,
                        "baseline_universe_group": universe_name,
                        "baseline_universe": "|".join(universe),
                        "baseline_lookback": lookback,
                        "baseline_top_n": 2,
                        "baseline_rebalance_frequency": "monthly",
                        "baseline_corrected_methodology_source": "evidence/research_recovery/profit_oriented_research_batch_v1_methodology_fix/latest/corrected_profit_research_variant_results.csv",
                        "baseline_corrected_label_source": "evidence/research_recovery/profit_oriented_research_batch_v1_labeling_fix/latest/corrected_label_variant_results.csv",
                        "same_window_baseline_comparison_required": True,
                        "risk_control_concept": concept["concept"],
                        "risk_control_rule": concept["description"],
                        "fallback_allocation": concept["fallback"],
                        "exposure_cap": 1.0,
                        "leverage_allowed": False,
                        "shorting_allowed": False,
                        "options_allowed": False,
                        "direct_futures_allowed": False,
                        "cash_bil_handling_rule": "BIL is the only cash/fallback asset. BIL is replacement or remainder allocation only, never additive on top of 100% risky exposure. If risky allocation multiplier is 1.00, BIL is 0.00; if 0.50, BIL is 0.50; if 0.25, BIL is 0.75; if no risky assets qualify, BIL is 1.00. Weight sum must be <= 1.00.",
                        "status": "non_promotable_preregistered_design",
                        "promotion_eligible": False,
                        "paper_forward_eligible": False,
                    }
                )
    return rows


def variant_fieldnames() -> list[str]:
    return [
        "lane_id",
        "variant_id",
        "source_family",
        "universe_group",
        "universe",
        "momentum_lookback_days",
        "top_n",
        "rebalance_frequency",
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
        "risk_control_concept",
        "risk_control_rule",
        "fallback_allocation",
        "exposure_cap",
        "leverage_allowed",
        "shorting_allowed",
        "options_allowed",
        "direct_futures_allowed",
        "cash_bil_handling_rule",
        "status",
        "promotion_eligible",
        "paper_forward_eligible",
    ]


def manifest(created: str, output: Path, source: dict[str, Any], variants: list[dict[str, Any]]) -> dict[str, Any]:
    concepts = {row["risk_control_concept"] for row in variants}
    next_action = NEXT_ACTION_AUDIT if variants and len(variants) <= 24 and len(concepts) <= 4 else NEXT_ACTION_MANUAL
    return {
        "created_utc": created,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        "source_labeling_fix_audit_path": str((ROOT / LABEL_AUDIT_DIR).resolve()),
        "variant_count_planned": len(variants),
        "risk_control_concepts_count": len(concepts),
        "max_lookbacks": 3,
        "max_universe_groups": 2,
        "max_drawdown_thresholds": 3,
        "max_volatility_thresholds": 3,
        "source_high_return_direction_supported": source["label_audit_manifest"].get("high_return_tactical_direction_supported") is True,
        "source_macro_gld_lineage_recovery_supported": source["label_audit_manifest"].get("macro_gld_lineage_recovery_supported") is True,
        "next_action": next_action,
    }


def summary_md(payload: dict[str, Any]) -> str:
    return f"""# High-Return Tactical Risk-Control Lane Design

Lane ID: `{payload['lane_id']}`

Source family: `{payload['source_family']}`

Planned variants: `{payload['variant_count_planned']}`

Risk-control concepts: `{payload['risk_control_concepts_count']}`

Max exposure allowed: `{payload['max_exposure_allowed']}`

This is a design-only preregistration packet. No backtest, strategy discovery, provider download, broker action, paper-forward activation, or promotion occurred.

Exact next action: `{payload['next_action']}`
"""


def source_review_md(source: dict[str, Any]) -> str:
    hrt = source["corrected_labels"][source["corrected_labels"]["family_id"] == SOURCE_FAMILY]
    median_cagr = float(pd.to_numeric(hrt["cagr"], errors="coerce").median())
    median_dd = float(pd.to_numeric(hrt["max_drawdown"], errors="coerce").median())
    return f"""# Source Evidence Review

Source batch: `{SOURCE_BATCH}`

Source family: `{SOURCE_FAMILY}`

Methodology fixed: `{source['methodology_manifest'].get('weight_forward_fill_bug_fixed')}`

Labeling fixed: `{source['label_fix_manifest'].get('high_return_severe_drawdown_underlabeled_count_after') == 0}`

High-return tactical median CAGR: `{median_cagr:.6f}`

High-return tactical median max drawdown: `{median_dd:.6f}`

The source evidence supports a focused risk-control question. It does not support promotion or paper-forward action.
"""


def hypothesis_md() -> str:
    return """# Risk-Control Hypothesis

Question:

Can the high-return tactical ETF/equity-index momentum signal retain meaningful historical return while materially reducing severe drawdown?

Hypothesis:

Narrow, mechanical risk controls tied to crash exposure and volatility may improve return/drawdown tradeoff without turning the signal into a cash-heavy benchmark duplicate.

This lane intentionally avoids broad batch-v2 expansion and unrelated families.
"""


def variant_table_md(rows: list[dict[str, Any]]) -> str:
    columns = ["variant_id", "universe_group", "momentum_lookback_days", "top_n", "risk_control_concept", "fallback_allocation"]
    lines = ["# Variant Design Table", "", "| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def frozen_rules_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Frozen Rule Summaries", ""]
    for row in rows:
        lines.extend(
            [
                f"## `{row['variant_id']}`",
                "",
                f"- Universe: `{row['universe']}`",
                f"- Momentum lookback: `{row['momentum_lookback_days']}` trading days",
                f"- Top-N: `{row['top_n']}`",
                f"- Rebalance: `{row['rebalance_frequency']}`",
                f"- Baseline variant ID: `{row['baseline_variant_id']}`",
                f"- Baseline family: `{row['baseline_family']}`",
                f"- Baseline universe group: `{row['baseline_universe_group']}`",
                f"- Baseline universe: `{row['baseline_universe']}`",
                f"- Baseline lookback: `{row['baseline_lookback']}` trading days",
                f"- Baseline top-N: `{row['baseline_top_n']}`",
                f"- Baseline rebalance frequency: `{row['baseline_rebalance_frequency']}`",
                f"- Baseline corrected methodology source: `{row['baseline_corrected_methodology_source']}`",
                f"- Baseline corrected label source: `{row['baseline_corrected_label_source']}`",
                f"- Same-window baseline comparison required: `{row['same_window_baseline_comparison_required']}`",
                f"- Risk-control rule: {row['risk_control_rule']}",
                f"- Fallback allocation: `{row['fallback_allocation']}`",
                f"- Exposure cap: `{row['exposure_cap']}`",
                "- No leverage, shorting, options, direct futures, intraday data, provider download, or broker/live path.",
                "- BIL is fallback/remainder only and cannot accumulate on top of risky exposure.",
                "- Status: non-promotable preregistered design.",
                "",
            ]
        )
    return "\n".join(lines)


def evaluation_policy_md() -> str:
    return """# Risk-Control Evaluation Policy

Future run outputs must remain non-promotable research labels.

Allowed interpretation tiers:

- `risk_control_signal_promising`
- `risk_control_signal_tradeoff_interesting`
- `risk_control_signal_return_destroyed`
- `risk_control_signal_drawdown_not_fixed`
- `risk_control_signal_duplicate_existing_active`
- `risk_control_signal_data_blocked`

Evaluation dimensions:

- Drawdown reduction versus corrected high-return tactical baseline.
- Return retained versus corrected high-return tactical baseline.
- Return/drawdown profile improvement.
- Same-window SPY and BIL comparison.
- Cash/BIL share and exposure behavior.
- Active VM/DSR and active-combo duplication checks.
- Robustness across lookbacks and both source universe groups.

Future-run duplicate/overconservatism checks:

- Compare behavior against SPY_200d, active VM, active DSR, active combo, BIL, and static all-weather where available.
- Flag BIL-heavy variants when average BIL share is greater than `70%`.
- Flag overconservative variants when return is mostly explained by BIL/cash timing and the tactical return signal is destroyed.
- Flag duplicate variants when correlation to an existing active/reference strategy is `>= 0.90`.
"""


def success_failure_md() -> str:
    return """# Success / Failure Criteria

This lane has research interpretation criteria only, not promotion thresholds.

## `risk_control_signal_promising`

Use only if future run evidence shows:

- Max drawdown reduction versus the corresponding baseline is at least `25%` relative improvement.
- CAGR retention versus baseline is at least `60%`.
- Calmar or return/drawdown proxy improves at least `25%`.
- Average exposure is `<= 1.0`.
- Max daily exposure is `<= 1.0`.
- BIL/cash share is `<= 70%` unless explicitly classified as defensive/cash-heavy.
- Result is not solely a one-row artifact within its parameter group.

## `risk_control_signal_tradeoff_interesting`

Use if:

- Max drawdown reduction is at least `15%`, but CAGR retention is between `40%` and `60%`; or
- CAGR retention is at least `60%`, but drawdown reduction is between `10%` and `25%`.

## `risk_control_signal_return_destroyed`

Use if:

- CAGR retention is below `40%`; or
- CAGR falls below `5%` annualized where CAGR is available.

## `risk_control_signal_drawdown_not_fixed`

Use if:

- Drawdown reduction is below `10%`; or
- Corrected max drawdown remains worse than `-45%`.

## `risk_control_signal_duplicate_existing_active`

Use if:

- Behavior is highly similar to existing active VM, active DSR, active combo, or SPY_200d reference.
- Suggested future numeric duplicate warning threshold: correlation `>= 0.90`.

## `risk_control_signal_data_blocked`

Use if required local-cache symbols are missing.

## Hard Design Invariants

- Daily exposure never exceeds `1.0`.
- Any exposure, BIL/cash, or status guardrail fails.
- No promotion, candidate_exhaustive, paper-forward, broker/live, or real-money path can be created from this lane.
"""


def do_not_promote_md() -> str:
    return """# Do Not Promote From Lane Design

This packet is design-only.

No variant is a promotion-review candidate, candidate-exhaustive candidate, paper-forward candidate, demo-active strategy, live-ready strategy, or real-money candidate.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Risk-Control Lane Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(payload: dict[str, Any], output: Path, variants: list[dict[str, Any]]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "risk_control_lane_design_only": payload["risk_control_lane_design_only"] is True,
        "correct_lane_id": payload["lane_id"] == LANE_ID,
        "correct_source_family": payload["source_family"] == SOURCE_FAMILY,
        "source_methodology_fixed": payload["source_methodology_fixed"] is True,
        "source_labeling_fixed": payload["source_labeling_fixed"] is True,
        "no_new_research_batch": payload["new_research_batch_run"] is False,
        "no_strategy_discovery": payload["new_strategy_discovery_run"] is False,
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
        "no_promotion_candidates": payload["promotion_candidates_created"] is False,
        "no_paper_forward_activation": payload["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": payload["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": payload["candidate_exhaustive_run"] is False,
        "no_best_single_variant_promoted": payload["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": payload["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": payload["active_vm_preserved"] is True,
        "active_dsr_preserved": payload["active_dsr_preserved"] is True,
        "static_all_weather_control_only": payload["static_all_weather_benchmark_control_only"] is True,
        "macro_gld_lineage_not_run": payload["macro_gld_lineage_recovery_run"] is False,
        "macro_gld_lineage_blocked_visible": payload["macro_gld_remains_lineage_blocked_visible"] is True,
        "alpaca_execution_module_delegated": payload["alpaca_execution_module_delegated"] is True,
        "variant_design_table_exists": (output / "variant_design_table.csv").exists(),
        "frozen_rule_summaries_exist": (output / "frozen_rule_summaries.md").exists(),
        "success_failure_criteria_exist": (output / "success_failure_criteria.md").exists(),
        "leverage_not_allowed": payload["leverage_allowed"] is False,
        "shorting_not_allowed": payload["shorting_allowed"] is False,
        "options_not_allowed": payload["options_allowed"] is False,
        "direct_futures_not_allowed": payload["direct_futures_allowed"] is False,
        "max_exposure_allowed_lte_1": payload["max_exposure_allowed"] <= 1.0,
        "variant_count_lte_24": len(variants) <= 24,
        "risk_control_concepts_lte_4": payload["risk_control_concepts_count"] <= 4,
        "next_action_valid": payload["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_metadata(root: Path, created: str, output: Path, payload: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## High-Return Tactical Risk-Control Lane Design

- Created UTC: `{created}`
- Evidence path: `{output.resolve()}`
- Lane ID: `{LANE_ID}`
- Planned variants: `{payload['variant_count_planned']}`
- Risk-control concepts: `{payload['risk_control_concepts_count']}`
- New backtests run: `{payload['new_backtests_run']}`
- Promotion candidates created: `{payload['promotion_candidates_created']}`
- Next action: `{payload['next_action']}`
"""
    write_text(path, replace_or_append_section(before, "## High-Return Tactical Risk-Control Lane Design", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    source = load_source(root)
    variants = build_variant_plan()
    payload = manifest(created, output, source, variants)

    write_json(output / "risk_control_lane_design_manifest.json", payload)
    write_text(output / "risk_control_lane_design_summary.md", summary_md(payload))
    write_text(output / "source_evidence_review.md", source_review_md(source))
    write_text(output / "risk_control_hypothesis.md", hypothesis_md())
    write_csv(output / "variant_design_table.csv", variants, variant_fieldnames())
    write_text(output / "variant_design_table.md", variant_table_md(variants))
    write_text(output / "frozen_rule_summaries.md", frozen_rules_md(variants))
    write_text(output / "risk_control_evaluation_policy.md", evaluation_policy_md())
    write_text(output / "success_failure_criteria.md", success_failure_md())
    write_text(output / "do_not_promote_from_lane_design.md", do_not_promote_md())
    write_text(output / "risk_control_lane_next_action.md", next_action_md(payload["next_action"]))
    write_json(output / "risk_control_lane_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(payload, output, variants)
    write_json(output / "risk_control_lane_consistency_check.json", check)
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
                "risk_control_concepts_count": result["risk_control_concepts_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
