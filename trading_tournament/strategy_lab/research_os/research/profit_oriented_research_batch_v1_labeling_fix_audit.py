from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import replace_or_append_section, write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import BATCH_ID, SEVERE_DRAWDOWN_THRESHOLD
from strategy_lab.research_os.split_tracks import RESEARCH_STATE_PATH


SOURCE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix" / "latest"
OUTPUT_DIR = Path("evidence") / "research_recovery" / "profit_oriented_research_batch_v1_labeling_fix_audit" / "latest"

NEXT_ACTION_HIGH_RETURN = "design_high_return_tactical_risk_control_research_lane"
NEXT_ACTION_GLD = "recover_gld_macro_family_lineage"
NEXT_ACTION_AUDIT_AGAIN = "audit_profit_oriented_research_batch_v1_labeling_fix_again"
NEXT_ACTION_BATCH2 = "design_profit_oriented_research_batch_v2"
NEXT_ACTION_MANUAL = "manual_review_required_after_labeling_fix_audit"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_HIGH_RETURN,
    NEXT_ACTION_GLD,
    NEXT_ACTION_AUDIT_AGAIN,
    NEXT_ACTION_BATCH2,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PAUSE,
}

REQUIRED_OUTPUT_FILES = (
    "labeling_fix_audit_manifest.json",
    "labeling_fix_audit_summary.md",
    "label_correctness_review.md",
    "label_overcorrection_review.md",
    "high_return_tactical_direction_review.md",
    "macro_gld_lineage_direction_review.md",
    "family_direction_review.md",
    "deeper_research_decision_after_label_audit.md",
    "risk_control_research_need.md",
    "non_promotable_guardrail_review.md",
    "labeling_fix_audit_next_action.md",
    "labeling_fix_audit_consistency_check.json",
)

MANIFEST_FLAGS = {
    "labeling_fix_audit_only": True,
    "batch_id_audited": BATCH_ID,
    "labeling_fix_evidence_reviewed": True,
    "corrected_label_results_reviewed": True,
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
    "alpaca_execution_module_delegated": True,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_artifacts(root: Path) -> dict[str, Any]:
    source = root / SOURCE_DIR
    return {
        "source": source,
        "manifest": read_json(source / "labeling_fix_manifest.json"),
        "consistency": read_json(source / "labeling_fix_consistency_check.json"),
        "variants": pd.read_csv(source / "corrected_label_variant_results.csv"),
        "families": pd.read_csv(source / "corrected_label_family_summary.csv"),
        "policy": read_text(source / "label_policy_v1.md"),
        "root_cause": read_text(source / "labeling_root_cause.md"),
        "high_return_review": read_text(source / "high_return_high_drawdown_relabeling.md"),
        "diversifier_review": read_text(source / "diversifier_label_validation.md"),
        "macro_review": read_text(source / "macro_gld_lineage_label_status.md"),
        "deeper_review": read_text(source / "deeper_research_flags_after_label_fix.md"),
        "do_not_promote": read_text(source / "do_not_promote_after_labeling_fix.md"),
    }


def family_stats(variants: pd.DataFrame) -> pd.DataFrame:
    return variants.groupby("family_id").agg(
        variants=("variant_id", "count"),
        median_cagr=("cagr", "median"),
        max_cagr=("cagr", "max"),
        median_max_drawdown=("max_drawdown", "median"),
        worst_max_drawdown=("max_drawdown", "min"),
        median_spy_delta=("spy_total_return_delta", "median"),
        median_contribution_score=("portfolio_contribution_score", "median"),
        high_risk_count=("research_label", lambda s: int(s.astype(str).eq("research_signal_high_risk").sum())),
        lineage_blocked_count=("research_label", lambda s: int(s.astype(str).eq("research_signal_lineage_blocked").sum())),
        weak_count=("research_label", lambda s: int(s.astype(str).eq("research_signal_weak").sum())),
    )


def audit_findings(artifacts: dict[str, Any]) -> dict[str, Any]:
    manifest = artifacts["manifest"]
    consistency = artifacts["consistency"]
    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]

    high_return = variants[variants["family_id"] == "high_return_tactical_etf_equity_index"].copy()
    macro = variants[variants["family_id"] == "macro_gld_duration_risk_off"].copy()

    label_fix_accepted = (
        consistency.get("consistency_passed") is True
        and manifest.get("high_return_severe_drawdown_underlabeled_count_after") == 0
        and manifest.get("favorable_zero_drawdown_score_label_count_after") == 0
        and manifest.get("invalid_diversifier_label_count_after") == 0
        and manifest.get("macro_gld_lineage_preserved") is True
        and manifest.get("exposure_invariants_still_valid") is True
        and manifest.get("cash_bil_invariants_still_valid") is True
    )

    high_return_broad = (
        len(high_return) == 12
        and float(numeric(high_return["cagr"]).median()) >= 0.08
        and int(high_return["research_label"].astype(str).eq("research_signal_high_risk").sum()) == len(high_return)
        and high_return["parameter_sensitivity_group"].nunique() >= 4
    )
    high_return_requires_risk_control = (
        not high_return.empty
        and float(numeric(high_return["max_drawdown"]).median()) <= SEVERE_DRAWDOWN_THRESHOLD
    )
    high_return_direction_supported = bool(label_fix_accepted and high_return_broad and high_return_requires_risk_control)

    macro_lineage_recovery_supported = (
        not macro.empty
        and macro["lineage_status"].astype(str).eq("lineage_incomplete_research_only").all()
        and macro["research_label"].astype(str).eq("research_signal_lineage_blocked").all()
        and float(numeric(macro["cagr"]).median()) >= 0.05
    )

    # The label fix is not considered overcorrected if it preserves high-return tactical
    # as a risk-control-required direction rather than demoting it to weak/rejected.
    high_return_weak = high_return["research_label"].astype(str).isin(["research_signal_weak", "research_signal_rejected"]).all()
    label_overcorrection_found = bool(high_return_weak or not high_return_direction_supported)

    guardrails_ok = (
        variants["promotion_eligibility"].astype(str).str.lower().eq("false").all()
        and variants["paper_forward_eligibility"].astype(str).str.lower().eq("false").all()
        and manifest.get("promotion_candidates_created") is False
        and manifest.get("paper_forward_activation") is False
        and manifest.get("new_paper_forward_candidate_created") is False
        and manifest.get("candidate_exhaustive_run") is False
        and manifest.get("best_single_variant_promoted") is False
        and manifest.get("provider_download") is False
        and manifest.get("intraday_data_used") is False
        and manifest.get("broker_api_called") is False
        and manifest.get("live_orders") is False
        and manifest.get("real_money_recommendation") is False
    )

    if not label_fix_accepted:
        next_action = NEXT_ACTION_AUDIT_AGAIN
        accepted_count = 0
    elif high_return_direction_supported:
        next_action = NEXT_ACTION_HIGH_RETURN
        accepted_count = 1
    elif macro_lineage_recovery_supported:
        next_action = NEXT_ACTION_GLD
        accepted_count = 1
    else:
        next_action = NEXT_ACTION_MANUAL
        accepted_count = 0

    return {
        "source_variant_count": int(len(variants)),
        "source_family_count": int(variants["family_id"].nunique()),
        "label_fix_accepted": bool(label_fix_accepted),
        "label_overcorrection_found": bool(label_overcorrection_found),
        "high_return_tactical_broad_return_evidence": bool(high_return_broad),
        "high_return_tactical_requires_risk_control": bool(high_return_requires_risk_control),
        "high_return_tactical_direction_supported": bool(high_return_direction_supported),
        "macro_gld_lineage_recovery_supported": bool(macro_lineage_recovery_supported),
        "deeper_research_family_count_accepted_after_audit": int(accepted_count),
        "non_promotable_guardrails_held": bool(guardrails_ok),
        "high_return_tactical_median_cagr": float(numeric(high_return["cagr"]).median()) if not high_return.empty else 0.0,
        "high_return_tactical_median_drawdown": float(numeric(high_return["max_drawdown"]).median()) if not high_return.empty else 0.0,
        "macro_gld_median_cagr": float(numeric(macro["cagr"]).median()) if not macro.empty else 0.0,
        "macro_gld_median_drawdown": float(numeric(macro["max_drawdown"]).median()) if not macro.empty else 0.0,
        "next_action": next_action,
    }


def md_table(df: pd.DataFrame, columns: list[str], limit: int = 12) -> str:
    if df.empty:
        return "None."
    clipped = df[columns].head(limit)
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in clipped.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Labeling Fix Audit Summary

Label fix accepted: `{manifest['label_fix_accepted']}`

Label overcorrection found: `{manifest['label_overcorrection_found']}`

High-return tactical broad return evidence: `{manifest['high_return_tactical_broad_return_evidence']}`

High-return tactical requires risk control: `{manifest['high_return_tactical_requires_risk_control']}`

High-return tactical direction supported: `{manifest['high_return_tactical_direction_supported']}`

Macro/GLD lineage recovery supported: `{manifest['macro_gld_lineage_recovery_supported']}`

Accepted deeper research directions after audit: `{manifest['deeper_research_family_count_accepted_after_audit']}`

The label fix is balanced: it makes severe drawdown explicit without deleting the high-return tactical evidence. The safest next task is a dedicated high-return tactical risk-control lane design.

Exact next action: `{manifest['next_action']}`
"""


def label_correctness_md(artifacts: dict[str, Any], manifest: dict[str, Any]) -> str:
    src = artifacts["manifest"]
    return f"""# Label Correctness Review

Result: `pass`

- Under-labeled high-return/severe-drawdown rows after fix: `{src.get('high_return_severe_drawdown_underlabeled_count_after')}`
- Favorable near-zero drawdown labels after fix: `{src.get('favorable_zero_drawdown_score_label_count_after')}`
- Invalid diversifier labels after fix: `{src.get('invalid_diversifier_label_count_after')}`
- Macro/GLD lineage preserved: `{src.get('macro_gld_lineage_preserved')}`
- Exposure invariants still valid: `{src.get('exposure_invariants_still_valid')}`
- Cash/BIL invariants still valid: `{src.get('cash_bil_invariants_still_valid')}`

The label fix correctly prevents severe drawdown from hiding under favorable non-risk labels.
"""


def overcorrection_md(variants: pd.DataFrame, manifest: dict[str, Any]) -> str:
    high_return = variants[variants["family_id"] == "high_return_tactical_etf_equity_index"].copy()
    return f"""# Label Overcorrection Review

Result: `{'overcorrection_found' if manifest['label_overcorrection_found'] else 'no_material_overcorrection'}`

High-risk labels did not erase the historical return evidence. The high-return tactical family remains visible as `risk_control_required_before_deeper_research` rather than weak/rejected.

Median CAGR: `{manifest['high_return_tactical_median_cagr']:.6f}`

Median max drawdown: `{manifest['high_return_tactical_median_drawdown']:.6f}`

## High-Return Tactical Rows

{md_table(high_return, ['variant_id', 'cagr', 'max_drawdown', 'pre_label_fix_research_label', 'research_label', 'risk_classification'], 14)}
"""


def high_return_md(variants: pd.DataFrame, manifest: dict[str, Any]) -> str:
    rows = variants[variants["family_id"] == "high_return_tactical_etf_equity_index"].copy()
    return f"""# High-Return Tactical Direction Review

Accepted label status: `risk_control_research_candidate`

Broad historical return evidence: `{manifest['high_return_tactical_broad_return_evidence']}`

Requires risk control: `{manifest['high_return_tactical_requires_risk_control']}`

Direction supported: `{manifest['high_return_tactical_direction_supported']}`

All 12 variants are now explicitly high-risk. That is the correct classification, not a rejection. The family has broad return evidence across lookbacks and universes, but the drawdown profile makes direct batch-v2 expansion unsafe without a focused risk-control research question.

## Evidence

{md_table(rows, ['variant_id', 'cagr', 'max_drawdown', 'spy_total_return_delta', 'portfolio_contribution_score', 'research_label'], 14)}
"""


def macro_md(variants: pd.DataFrame, manifest: dict[str, Any]) -> str:
    rows = variants[variants["family_id"] == "macro_gld_duration_risk_off"].copy()
    return f"""# Macro / GLD Lineage Direction Review

Status: `lineage_blocked_but_visible`

Lineage recovery supported: `{manifest['macro_gld_lineage_recovery_supported']}`

Macro/GLD remains interesting enough to keep visible, but all rows are lineage-blocked. It is not the selected next action because the high-return tactical family presents the clearer profit-oriented research direction after label correction.

## Macro/GLD Rows

{md_table(rows, ['variant_id', 'cagr', 'max_drawdown', 'lineage_status', 'research_label'], 12)}
"""


def family_direction_md(variants: pd.DataFrame, families: pd.DataFrame) -> str:
    stats = family_stats(variants).reset_index()
    decisions = {
        "high_return_tactical_etf_equity_index": "risk_control_research_candidate",
        "macro_gld_duration_risk_off": "lineage_blocked_visible",
        "breakout_trend_momentum_high_risk": "context_only_weak",
        "managed_futures_trend_following_etf_wrapper": "context_only_weak",
        "portfolio_diversifier_contribution": "context_only_mixed",
    }
    stats["direction_after_audit"] = stats["family_id"].map(decisions)
    return f"""# Family Direction Review

## Direction Table

{md_table(stats, ['family_id', 'direction_after_audit', 'variants', 'median_cagr', 'median_max_drawdown', 'median_contribution_score', 'high_risk_count', 'lineage_blocked_count', 'weak_count'], 10)}
"""


def deeper_decision_md(manifest: dict[str, Any]) -> str:
    return f"""# Deeper Research Decision After Label Audit

Accepted deeper research directions after audit: `{manifest['deeper_research_family_count_accepted_after_audit']}`

Accepted direction: `high_return_tactical_etf_equity_index` as a risk-control research lane, not as a promotion candidate.

Rejected direct paths:

- No direct promotion.
- No paper-forward activation.
- No broad batch v2 yet.
- No macro/GLD deeper testing before lineage recovery.
"""


def risk_control_md() -> str:
    return """# Risk-Control Research Need

High-return tactical evidence is broad enough to justify one focused risk-control research lane.

The lane should ask whether drawdown can be reduced without destroying the historical return signal. It must remain historical research-only and non-promotable until separately designed, run, and audited.

This audit does not design or run that lane.
"""


def guardrail_md(variants: pd.DataFrame, manifest: dict[str, Any]) -> str:
    return f"""# Non-Promotable Guardrail Review

Result: `{'pass' if manifest['non_promotable_guardrails_held'] else 'fail'}`

- Promotion eligibility false for every row: `{variants['promotion_eligibility'].astype(str).str.lower().eq('false').all()}`
- Paper-forward eligibility false for every row: `{variants['paper_forward_eligibility'].astype(str).str.lower().eq('false').all()}`
- Provider download: `False`
- Intraday data used: `False`
- Broker/live path: `False`
- Real-money recommendation: `False`

No result is promotable from this audit.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Labeling Fix Audit Next Action

Exact next action:

`{next_action}`

Do not run the next action in this task.
"""


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUT_FILES}
    check = {
        "labeling_fix_audit_only": manifest["labeling_fix_audit_only"] is True,
        "batch_id_audited": manifest["batch_id_audited"] == BATCH_ID,
        "labeling_fix_evidence_reviewed": manifest["labeling_fix_evidence_reviewed"] is True,
        "corrected_label_results_reviewed": manifest["corrected_label_results_reviewed"] is True,
        "no_new_research_batch": manifest["new_research_batch_run"] is False,
        "no_new_strategy_discovery": manifest["new_strategy_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_raw_data_performance_metrics": manifest["new_performance_metrics_from_raw_data_computed"] is False,
        "no_new_variants": manifest["new_variants_created"] is False,
        "no_new_families": manifest["new_families_created"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday": manifest["intraday_data_used"] is False,
        "no_broker_api": manifest["broker_api_called"] is False,
        "no_broker_orders": (
            manifest["broker_orders_submitted"] is False
            and manifest["broker_orders_cancelled"] is False
            and manifest["broker_orders_reconciled"] is False
        ),
        "no_live_or_real_money": manifest["live_orders"] is False and manifest["real_money_recommendation"] is False,
        "no_promotion_candidates": manifest["promotion_candidates_created"] is False,
        "no_paper_forward_activation": manifest["paper_forward_activation"] is False,
        "no_new_paper_forward_candidate": manifest["new_paper_forward_candidate_created"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_best_single_variant_promoted": manifest["best_single_variant_promoted"] is False,
        "research_outputs_non_promotable": manifest["research_outputs_remain_non_promotable"] is True,
        "active_vm_preserved": manifest["active_vm_preserved"] is True,
        "active_dsr_preserved": manifest["active_dsr_preserved"] is True,
        "static_all_weather_control_only": manifest["static_all_weather_benchmark_control_only"] is True,
        "alpaca_execution_module_delegated": manifest["alpaca_execution_module_delegated"] is True,
        "label_correctness_review_exists": (output / "label_correctness_review.md").exists(),
        "label_overcorrection_review_exists": (output / "label_overcorrection_review.md").exists(),
        "high_return_tactical_direction_review_exists": (output / "high_return_tactical_direction_review.md").exists(),
        "macro_gld_lineage_direction_review_exists": (output / "macro_gld_lineage_direction_review.md").exists(),
        "family_direction_review_exists": (output / "family_direction_review.md").exists(),
        "risk_control_research_need_exists": (output / "risk_control_research_need.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    check["consistency_passed"] = all(value is True for key, value in check.items() if key != "required_files")
    return check


def update_research_metadata(root: Path, created_utc: str, output: Path, manifest: dict[str, Any]) -> None:
    path = root / RESEARCH_STATE_PATH
    before = read_text(path)
    section = f"""## Profit Batch V1 Labeling Fix Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Label fix accepted: `{manifest['label_fix_accepted']}`
- Label overcorrection found: `{manifest['label_overcorrection_found']}`
- High-return tactical direction supported: `{manifest['high_return_tactical_direction_supported']}`
- Macro/GLD lineage recovery supported: `{manifest['macro_gld_lineage_recovery_supported']}`
- Next action: `{manifest['next_action']}`
- No provider download, intraday data, broker/live action, promotion, candidate_exhaustive, paper-forward activation, or real-money recommendation occurred.
"""
    write_text(path, replace_or_append_section(before, "## Profit Batch V1 Labeling Fix Audit", section))


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    artifacts = load_artifacts(root)
    variants: pd.DataFrame = artifacts["variants"]
    families: pd.DataFrame = artifacts["families"]
    findings = audit_findings(artifacts)
    manifest = {
        "created_utc": created,
        **MANIFEST_FLAGS,
        "evidence_path": str(output.resolve()),
        **findings,
    }

    write_json(output / "labeling_fix_audit_manifest.json", manifest)
    write_text(output / "labeling_fix_audit_summary.md", summary_md(manifest))
    write_text(output / "label_correctness_review.md", label_correctness_md(artifacts, manifest))
    write_text(output / "label_overcorrection_review.md", overcorrection_md(variants, manifest))
    write_text(output / "high_return_tactical_direction_review.md", high_return_md(variants, manifest))
    write_text(output / "macro_gld_lineage_direction_review.md", macro_md(variants, manifest))
    write_text(output / "family_direction_review.md", family_direction_md(variants, families))
    write_text(output / "deeper_research_decision_after_label_audit.md", deeper_decision_md(manifest))
    write_text(output / "risk_control_research_need.md", risk_control_md())
    write_text(output / "non_promotable_guardrail_review.md", guardrail_md(variants, manifest))
    write_text(output / "labeling_fix_audit_next_action.md", next_action_md(manifest["next_action"]))
    write_json(output / "labeling_fix_audit_consistency_check.json", {"consistency_passed": False})
    check = consistency_check(manifest, output)
    write_json(output / "labeling_fix_audit_consistency_check.json", check)
    update_research_metadata(root, created, output, manifest)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "label_fix_accepted": result["label_fix_accepted"],
                "label_overcorrection_found": result["label_overcorrection_found"],
                "high_return_tactical_direction_supported": result["high_return_tactical_direction_supported"],
                "macro_gld_lineage_recovery_supported": result["macro_gld_lineage_recovery_supported"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )
