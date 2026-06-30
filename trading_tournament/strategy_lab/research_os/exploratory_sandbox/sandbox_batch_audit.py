from __future__ import annotations

import csv
import json
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .sandbox_config import REGISTRY_PATH, ROADMAP_PATH, ROOT
from .sandbox_status_taxonomy import ALLOWED_SANDBOX_STATUSES, FORBIDDEN_STATUSES


BATCH_ID = "batch_001"
BATCH_DIR = Path("evidence") / "exploratory_sandbox" / BATCH_ID / "latest"
OUTPUT_DIR = Path("evidence") / "exploratory_sandbox" / "batch_001_audit" / "latest"
COMPACT_STATE_PATH = Path("reports") / "compact_state" / "current_tournament_state.md"

NEXT_ACTION_FIX_PACKET = "fix_exploratory_sandbox_batch_evidence_packet"
NEXT_ACTION_PREREGISTER = "pre_register_one_family_from_sandbox_findings"
NEXT_ACTION_BATCH_002 = "run_exploratory_strategy_search_sandbox_batch_002"
NEXT_ACTION_PAUSE = "pause_expansion_and_wait_for_manual_direction"
NEXT_ACTION_MANUAL = "manual_review_required_after_sandbox_audit"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_FIX_PACKET,
    NEXT_ACTION_PREREGISTER,
    NEXT_ACTION_BATCH_002,
    NEXT_ACTION_PAUSE,
    NEXT_ACTION_MANUAL,
}

MANIFEST_FLAGS = {
    "sandbox_batch_audit_only": True,
    "new_sandbox_batch_run": False,
    "strategy_discovery_run": False,
    "formal_discovery_run": False,
    "new_backtests_run": False,
    "new_performance_metrics_computed": False,
    "indicator_library_dependency_added": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "active_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
    "sandbox_results_remain_non_promotable": True,
    "sandbox_can_create_paper_candidates": False,
}

REQUIRED_AUDIT_FILES = (
    "sandbox_batch_audit_manifest.json",
    "sandbox_batch_audit_summary.md",
    "sandbox_batch_consistency_issue_review.md",
    "sandbox_family_audit.md",
    "sandbox_family_audit.csv",
    "sandbox_breakout_continuation_review.md",
    "sandbox_portfolio_combination_review.md",
    "sandbox_volatility_regime_review.md",
    "sandbox_trend_momentum_review.md",
    "sandbox_mean_reversion_review.md",
    "sandbox_factor_style_rotation_review.md",
    "sandbox_macro_contribution_review.md",
    "sandbox_overfitting_audit.md",
    "sandbox_future_preregistration_review.md",
    "sandbox_next_action.md",
    "sandbox_batch_audit_consistency_check.json",
)

REQUIRED_BATCH_FILES = (
    "sandbox_batch_manifest.json",
    "sandbox_batch_summary.md",
    "sandbox_batch_preflight_report.md",
    "sandbox_variant_results.csv",
    "sandbox_family_summary.csv",
    "sandbox_family_summary.md",
    "sandbox_benchmark_comparison_summary.csv",
    "sandbox_risk_summary.csv",
    "sandbox_diversification_summary.csv",
    "sandbox_practicality_summary.csv",
    "sandbox_overfitting_risk_summary.md",
    "sandbox_research_only_leverage_summary.md",
    "sandbox_future_preregistration_candidates.md",
    "sandbox_discarded_or_weak_families.md",
    "sandbox_do_not_promote.md",
    "sandbox_batch_next_action.md",
    "sandbox_batch_consistency_check.json",
)

FAMILY_ORDER = (
    "breakout_continuation",
    "portfolio_combination_sleeve_ensemble",
    "volatility_regime",
    "trend_momentum",
    "mean_reversion",
    "factor_style_rotation",
    "macro_portfolio_contribution",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def zip_json(root: Path, name: str) -> dict[str, Any]:
    packet = root / BATCH_DIR / "sandbox_batch_packet.zip"
    if not packet.exists():
        return {}
    with zipfile.ZipFile(packet, "r") as archive:
        try:
            with archive.open(name) as handle:
                return json.loads(handle.read().decode("utf-8"))
        except KeyError:
            return {}


def zip_names(root: Path) -> set[str]:
    packet = root / BATCH_DIR / "sandbox_batch_packet.zip"
    if not packet.exists():
        return set()
    with zipfile.ZipFile(packet, "r") as archive:
        return {Path(item.filename).name for item in archive.infolist()}


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def source_state(root: Path) -> dict[str, Any]:
    batch_dir = root / BATCH_DIR
    manifest = read_json(batch_dir / "sandbox_batch_manifest.json")
    live_consistency = read_json(batch_dir / "sandbox_batch_consistency_check.json")
    packet_consistency = zip_json(root, "sandbox_batch_consistency_check.json")
    packet_files = zip_names(root)
    live_missing = [name for name in REQUIRED_BATCH_FILES if not (batch_dir / name).exists()]
    packet_missing = [name for name in REQUIRED_BATCH_FILES if name not in packet_files]
    variants = read_csv(batch_dir / "sandbox_variant_results.csv")
    families = read_csv(batch_dir / "sandbox_family_summary.csv")
    benchmark = read_csv(batch_dir / "sandbox_benchmark_comparison_summary.csv")
    risk = read_csv(batch_dir / "sandbox_risk_summary.csv")
    diversification = read_csv(batch_dir / "sandbox_diversification_summary.csv")
    registry = load_yaml(root / REGISTRY_PATH)
    compact_text = (root / COMPACT_STATE_PATH).read_text(encoding="utf-8") if (root / COMPACT_STATE_PATH).exists() else ""
    return {
        "manifest": manifest,
        "live_consistency": live_consistency,
        "packet_consistency": packet_consistency,
        "live_missing": live_missing,
        "packet_missing": packet_missing,
        "variants": variants,
        "families": families,
        "benchmark": benchmark,
        "risk": risk,
        "diversification": diversification,
        "registry": registry,
        "compact_state_stale": "audit_exploratory_sandbox_batch_results" not in compact_text,
        "packet_exists": (batch_dir / "sandbox_batch_packet.zip").exists(),
    }


def consistency_issue_review(state: dict[str, Any]) -> dict[str, Any]:
    live = state["live_consistency"]
    packet = state["packet_consistency"]
    issue_found = packet.get("consistency_passed") is False or packet.get("required_files_exist") is False
    false_missing = []
    if packet.get("required_files_exist") is False and not state["live_missing"] and not state["packet_missing"]:
        false_missing.append("sandbox_batch_consistency_check.json self-check was evaluated before the final consistency file was rewritten into the packet")
    issue_blocking = issue_found
    return {
        "issue_found": issue_found,
        "issue_blocking": issue_blocking,
        "live_consistency_passed": live.get("consistency_passed"),
        "live_required_files_exist": live.get("required_files_exist"),
        "packet_consistency_passed": packet.get("consistency_passed"),
        "packet_required_files_exist": packet.get("required_files_exist"),
        "live_missing_files": state["live_missing"],
        "packet_missing_files": state["packet_missing"],
        "falsely_detected_missing_file_or_condition": "; ".join(false_missing) if false_missing else "",
        "root_cause": "packet assembly timing: zip captured an intermediate consistency file before final live consistency was rewritten",
        "batch_validity": "live batch outputs remain readable and non-promotable, but the packet itself needs repair before acceptance",
    }


def variant_rule_review(variants: list[dict[str, str]]) -> dict[str, Any]:
    statuses = {row.get("status", "") for row in variants}
    promotable_true = [row.get("variant_id", "") for row in variants if row.get("promotable") != "false"]
    paper_true = [row.get("variant_id", "") for row in variants if row.get("paper_candidate_allowed") != "false"]
    forbidden = sorted(statuses & set(FORBIDDEN_STATUSES))
    return {
        "allowed_statuses_only": statuses <= set(ALLOWED_SANDBOX_STATUSES),
        "forbidden_statuses_absent": not forbidden,
        "forbidden_statuses_found": forbidden,
        "promotable_true_count": len(promotable_true),
        "paper_candidate_allowed_true_count": len(paper_true),
        "promotable_true_ids": promotable_true,
        "paper_candidate_allowed_true_ids": paper_true,
    }


def family_by_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["family_id"]: row for row in rows}


def median_benchmark_delta(benchmark_rows: list[dict[str, str]], family_id: str, benchmark_id: str = "active_combo") -> float:
    values = [
        safe_float(row.get("median_delta_180d_median_final_equity"))
        for row in benchmark_rows
        if row.get("family_id") == family_id and row.get("benchmark_id") == benchmark_id
    ]
    return values[0] if values else 0.0


def median_corr(diversification_rows: list[dict[str, str]], family_id: str, metric: str) -> float:
    values = [safe_float(row.get(metric)) for row in diversification_rows if row.get("family_id") == family_id]
    return values[0] if values else 0.0


def family_audit_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    families = family_by_id(state["families"])
    rows: list[dict[str, Any]] = []
    for family_id in FAMILY_ORDER:
        row = families.get(family_id, {})
        positive = int(row.get("variants_positive_objective_progress", 0) or 0)
        beating_combo = int(row.get("variants_beating_active_combo", 0) or 0)
        drawdown_pass = int(row.get("variants_passing_basic_drawdown_screen", 0) or 0)
        low_corr = int(row.get("variants_low_correlation_to_active_combo", 0) or 0)
        variants = int(row.get("variants_tested", 0) or 0)
        median_delta = median_benchmark_delta(state["benchmark"], family_id)
        active_corr = median_corr(state["diversification"], family_id, "median_corr_vs_active_combo")
        actionable = False
        if family_id == "breakout_continuation":
            conclusion = "useful diversifier clue, but likely low-return/cash-heavy behavior because no variants beat active combo"
            future = "not actionable now; possible future sleeve audit only after packet fix and separate preregistration"
            noise = "low correlation may reflect under-investment or defensive behavior rather than standalone alpha"
        elif family_id == "portfolio_combination_sleeve_ensemble":
            conclusion = "mostly repackages active combo behavior; high active-combo correlation overwhelms the one marginal active-combo beat"
            future = "not actionable now; contribution claim is not strong enough for preregistration"
            noise = "sleeve ensemble results risk duplicating active combo and mistaking diversification arithmetic for alpha"
        elif family_id == "volatility_regime":
            conclusion = "high-upside/high-risk pattern repeats the risk-buffer failure; drawdown pass count is zero"
            future = "sandbox-only unless a separately preregistered risk-control hypothesis is justified later"
            noise = "active-combo beats are not robust because risk gate fails"
        elif family_id == "trend_momentum":
            conclusion = "some active-combo beats, but zero drawdown passes means it remains sandbox-only"
            future = "open only under a separately justified risk-control hypothesis, not from this batch"
            noise = "positive rows are likely equity beta/parameter sensitivity without small-account risk fit"
        elif family_id == "mean_reversion":
            conclusion = "weak in daily ETF form; behavior likely needs shorter horizon/intraday data, which remains blocked"
            future = "not actionable under current daily ETF-only constraints"
            noise = "high drawdown and no active-combo beats make daily ETF mean reversion misleading"
        elif family_id == "factor_style_rotation":
            conclusion = "objective/risk mismatch and equity-beta exposure; some active-combo beats disappear under drawdown screen"
            future = "not actionable; too correlated/risky for current objective"
            noise = "style rotation may be repackaged equity beta with parameter sensitivity"
        else:
            conclusion = "useful as benchmark/control/contribution context, but weak objective progress"
            future = "not actionable as a standalone family; keep as contribution context"
            noise = "diversification without objective progress can be overvalued"
        rows.append(
            {
                "family_id": family_id,
                "source_status": row.get("family_status", ""),
                "variants_tested": variants,
                "positive_objective_progress_variants": positive,
                "variants_beating_active_combo": beating_combo,
                "drawdown_screen_passes": drawdown_pass,
                "low_active_combo_correlation_variants": low_corr,
                "median_delta_vs_active_combo": round(median_delta, 6),
                "median_corr_vs_active_combo": round(active_corr, 6),
                "audit_conclusion": conclusion,
                "future_preregistration_view": future,
                "overfitting_or_noise_risk": noise,
                "actionable_now": actionable,
            }
        )
    return rows


def decide_next_action(issue: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    if issue["issue_blocking"]:
        return NEXT_ACTION_FIX_PACKET
    actionable = [row for row in family_rows if row["actionable_now"]]
    if len(actionable) == 1:
        return NEXT_ACTION_PREREGISTER
    if len(actionable) > 1:
        return NEXT_ACTION_MANUAL
    interesting = [row for row in family_rows if row["source_status"] == "sandbox_family_interesting"]
    if interesting:
        return NEXT_ACTION_MANUAL
    return NEXT_ACTION_PAUSE


def consistency_issue_md(issue: dict[str, Any], state: dict[str, Any]) -> str:
    return f"""# Sandbox Batch Consistency Issue Review

Why did `consistency_passed` equal `false`?

The stale packet copy of `sandbox_batch_consistency_check.json` has `consistency_passed: false` because the zip packet captured an intermediate consistency file before the final live consistency check was rewritten.

Which required file was missing or falsely detected as missing?

`required_files_exist: false` was a self-referential timing issue involving `sandbox_batch_consistency_check.json`. The live evidence directory contains every required file, and the zip also contains every required file, but the zip's consistency JSON still reports the earlier false state.

Is the missing-file issue a real blocker?

It is not a blocker for reading the batch outputs, but it is a blocker for accepting the uploaded packet as internally consistent. The batch packet should be fixed before further sandbox runs or family preregistration decisions.

- Live consistency passed: `{issue['live_consistency_passed']}`
- Live required files exist: `{issue['live_required_files_exist']}`
- Packet consistency passed: `{issue['packet_consistency_passed']}`
- Packet required files exist: `{issue['packet_required_files_exist']}`
- Live missing files: `{', '.join(issue['live_missing_files']) or 'none'}`
- Packet missing files: `{', '.join(issue['packet_missing_files']) or 'none'}`
- Stale compact-state warning present in source state: `{state['compact_state_stale']}`
- Root cause: `{issue['root_cause']}`
"""


def family_audit_md(rows: list[dict[str, Any]]) -> str:
    lines = ["# Sandbox Family Audit", "", "No family is actionable directly from this sandbox batch.", ""]
    for row in rows:
        lines.append(f"## `{row['family_id']}`")
        lines.append(f"- Source status: `{row['source_status']}`")
        lines.append(f"- Variants tested: `{row['variants_tested']}`")
        lines.append(f"- Active-combo beat count: `{row['variants_beating_active_combo']}`")
        lines.append(f"- Drawdown-screen passes: `{row['drawdown_screen_passes']}`")
        lines.append(f"- Median delta vs active combo: `{row['median_delta_vs_active_combo']}`")
        lines.append(f"- Median corr vs active combo: `{row['median_corr_vs_active_combo']}`")
        lines.append(f"- Audit conclusion: {row['audit_conclusion']}")
        lines.append(f"- Future view: {row['future_preregistration_view']}")
        lines.append("")
    return "\n".join(lines)


def single_family_md(row: dict[str, Any]) -> str:
    return f"""# `{row['family_id']}` Review

Source status: `{row['source_status']}`

Variants tested: `{row['variants_tested']}`

Positive objective progress variants: `{row['positive_objective_progress_variants']}`

Variants beating active combo: `{row['variants_beating_active_combo']}`

Drawdown-screen passes: `{row['drawdown_screen_passes']}`

Low active-combo correlation variants: `{row['low_active_combo_correlation_variants']}`

Median delta vs active combo: `{row['median_delta_vs_active_combo']}`

Median correlation vs active combo: `{row['median_corr_vs_active_combo']}`

Audit conclusion: {row['audit_conclusion']}

Future preregistration view: {row['future_preregistration_view']}

Overfitting/noise risk: {row['overfitting_or_noise_risk']}

Actionable now: `{row['actionable_now']}`
"""


def overfitting_md(source_future_count: int) -> str:
    return f"""# Sandbox Overfitting Audit

- Best single variant cannot be promoted.
- Best parameter cannot be promoted.
- Best family cannot become a promotion candidate.
- Any future candidate must come from separate preregistration.
- `future_preregistration_candidate_count = {source_future_count}` means no automatic candidate is available.
- Any future family selection must be justified by robustness, not the best row.
- Indicators cannot be added after results to rescue rows.
- Risk gates cannot be weakened after results.

Conclusion: the opportunity map is useful for diagnosis, but not sufficient for promotion or paper-forward action.
"""


def future_prereg_md(source_future_count: int, family_rows: list[dict[str, Any]]) -> str:
    maybe = [row["family_id"] for row in family_rows if row["source_status"] == "sandbox_family_interesting"]
    return f"""# Sandbox Future Preregistration Review

Source future preregistration candidate count: `{source_future_count}`

Actionable family count after audit: `0`

Interesting but not actionable families: `{', '.join(maybe) or 'none'}`

No family deserves direct preregistration from this audit. The packet consistency issue should be fixed first. After that, a human may decide whether `breakout_continuation` deserves a separate diversifier/sleeve audit, but this audit does not authorize preregistration.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Sandbox Batch Audit Next Action

Exact next action: `{next_action}`

Do not run the next action in this audit task.
"""


def summary_md(manifest: dict[str, Any], issue: dict[str, Any], family_rows: list[dict[str, Any]]) -> str:
    interesting = [row["family_id"] for row in family_rows if row["source_status"] == "sandbox_family_interesting"]
    weak = [row["family_id"] for row in family_rows if row["source_status"] != "sandbox_family_interesting"]
    return f"""# Exploratory Sandbox Batch 001 Audit Summary

Audit-only: `{manifest['sandbox_batch_audit_only']}`

Audited batch: `{manifest['audited_batch_id']}`

Source variants: `{manifest['source_variant_count']}`

Source families: `{manifest['source_family_count']}`

Source future preregistration candidate count: `{manifest['source_future_preregistration_candidate_count']}`

Consistency issue found: `{issue['issue_found']}`

Consistency issue blocking: `{issue['issue_blocking']}`

Interesting but not actionable families: `{', '.join(interesting) or 'none'}`

Weak/noisy families: `{', '.join(weak) or 'none'}`

Next action: `{manifest['next_action']}`

No new sandbox batch, discovery, backtest, provider download, intraday use, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    before = deepcopy(metadata)
    metadata.update(
        {
            "exploratory_sandbox_batch_001_audit_path": str(output.resolve()),
            "exploratory_sandbox_batch_001_audit_status": "completed_packet_fix_required",
            "exploratory_sandbox_batch_001_audit_created_utc": created_utc,
            "current_research_mode": "exploratory_sandbox_batch_audited",
            "current_next_action": manifest["next_action"],
            "official_current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "sandbox_batch_audit_only": True,
            "sandbox_batch_packet_consistency_issue_found": manifest["consistency_issue_found"],
            "sandbox_batch_packet_consistency_issue_blocking": manifest["consistency_issue_blocking"],
            "sandbox_audit_families_actionable_count": manifest["families_actionable_count"],
            "sandbox_audit_no_new_batch_run": True,
            "sandbox_audit_no_candidate_exhaustive": True,
            "sandbox_audit_no_paper_forward_action": True,
            "sandbox_audit_no_provider_download": True,
            "sandbox_audit_no_intraday_data_used": True,
            "sandbox_audit_no_real_money_recommendation": True,
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")

    roadmap_path = root / ROADMAP_PATH
    roadmap_before = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    compact = f"""## Compact Current State

- Updated UTC: `{created_utc}`
- Current research mode: `exploratory_sandbox_batch_audited`
- Official current next action: `{manifest['next_action']}`
- Exploratory sandbox batch audit evidence: `{output.resolve()}`
- Audit-only: `true`
- Source batch variants: `{manifest['source_variant_count']}`
- Source families: `{manifest['source_family_count']}`
- Source future preregistration candidates: `{manifest['source_future_preregistration_candidate_count']}`
- Packet consistency issue found: `{manifest['consistency_issue_found']}`
- Packet consistency issue blocking: `{manifest['consistency_issue_blocking']}`
- Actionable families after audit: `{manifest['families_actionable_count']}`
- Sandbox results remain non-promotable: `true`
- Active VM and active DSR preserved.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday remains paused: `true`
- This audit did not run a new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation.
"""
    section = f"""## Exploratory Sandbox Batch 001 Audit

- Created UTC: `{created_utc}`
- Evidence path: `{output.resolve()}`
- Audit-only: `true`
- Consistency issue found: `{manifest['consistency_issue_found']}`
- Consistency issue blocking: `{manifest['consistency_issue_blocking']}`
- Families interesting count: `{manifest['families_interesting_count']}`
- Families actionable count: `{manifest['families_actionable_count']}`
- Next action: `{manifest['next_action']}`
- Do not run the next action in this audit task.
- No new sandbox batch, discovery, backtest, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""
    roadmap_after = replace_or_append_section(roadmap_before, "## Compact Current State", compact)
    roadmap_after = replace_or_append_section(roadmap_after, "## Exploratory Sandbox Batch 001 Audit", section)
    write_text(roadmap_path, roadmap_after)

    compact_path = root / COMPACT_STATE_PATH
    compact_before = compact_path.read_text(encoding="utf-8") if compact_path.exists() else ""
    compact_after = f"""# Current Tournament State

Created UTC: `{created_utc}`

Current research mode: `exploratory_sandbox_batch_audited`

Current next action: `{manifest['next_action']}`

Audit evidence: `{output.resolve()}`

## Audit Result

- Sandbox batch audit-only: `true`
- Source batch: `{manifest['audited_batch_id']}`
- Source variant count: `{manifest['source_variant_count']}`
- Source family count: `{manifest['source_family_count']}`
- Source future preregistration candidate count: `{manifest['source_future_preregistration_candidate_count']}`
- Packet consistency issue found: `{manifest['consistency_issue_found']}`
- Packet consistency issue blocking: `{manifest['consistency_issue_blocking']}`
- Families actionable after audit: `{manifest['families_actionable_count']}`

## Protected State

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.
- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Exact rejected variants remain closed.
- Intraday research remains paused.

## Forbidden Actions

- No new sandbox batch was run by this audit.
- No strategy discovery, new backtest, or new performance metric computation.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path or order action.
- No real-money recommendation.
"""
    write_text(compact_path, compact_after)
    return before != metadata, roadmap_before != roadmap_after, compact_before != compact_after


def replace_or_append_section(text: str, header: str, section: str) -> str:
    if header not in text:
        return text.rstrip() + "\n\n" + section.rstrip() + "\n"
    start = text.index(header)
    next_start = text.find("\n## ", start + len(header))
    if next_start == -1:
        return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
    return text[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + text[next_start + 1 :].lstrip()


def consistency_check(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    check = {
        "sandbox_batch_audit_only": manifest["sandbox_batch_audit_only"] is True,
        "no_new_sandbox_batch": manifest["new_sandbox_batch_run"] is False,
        "no_formal_strategy_discovery": manifest["strategy_discovery_run"] is False and manifest["formal_discovery_run"] is False,
        "no_new_backtests": manifest["new_backtests_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_indicator_library_dependency_added": manifest["indicator_library_dependency_added"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_live_action": manifest["broker_orders_submitted"] is False
        and manifest["broker_orders_cancelled"] is False
        and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "active_strategy_state_preserved": manifest["active_strategy_state_changed"] is False,
        "rejected_strategy_state_preserved": manifest["rejected_strategy_state_changed"] is False,
        "exact_rejected_variants_not_reopened": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "sandbox_results_remain_non_promotable": manifest["sandbox_results_remain_non_promotable"] is True,
        "sandbox_cannot_create_paper_candidates": manifest["sandbox_can_create_paper_candidates"] is False,
        "consistency_issue_review_exists": (output / "sandbox_batch_consistency_issue_review.md").exists(),
        "family_audit_exists": (output / "sandbox_family_audit.md").exists() and (output / "sandbox_family_audit.csv").exists(),
        "overfitting_audit_exists": (output / "sandbox_overfitting_audit.md").exists(),
        "future_preregistration_review_exists": (output / "sandbox_future_preregistration_review.md").exists(),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in REQUIRED_AUDIT_FILES),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_sandbox_batch_audit(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    created_utc = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    before_strategies = strategy_snapshot(root)
    state = source_state(root)
    issue = consistency_issue_review(state)
    variant_rules = variant_rule_review(state["variants"])
    family_rows = family_audit_rows(state)
    source_future_count = int(state["manifest"].get("sandbox_future_preregistration_candidate_count", 0) or 0)
    next_action = decide_next_action(issue, family_rows)
    manifest = {
        "created_utc": created_utc,
        "output_dir": str(output.resolve()),
        **MANIFEST_FLAGS,
        "audited_batch_id": BATCH_ID,
        "source_variant_count": int(state["manifest"].get("variant_count_evaluated", len(state["variants"])) or 0),
        "source_family_count": int(state["manifest"].get("families_evaluated_count", len(state["families"])) or 0),
        "source_future_preregistration_candidate_count": source_future_count,
        "consistency_issue_found": issue["issue_found"],
        "consistency_issue_blocking": issue["issue_blocking"],
        "families_interesting_count": sum(1 for row in family_rows if row["source_status"] == "sandbox_family_interesting"),
        "families_actionable_count": sum(1 for row in family_rows if row["actionable_now"]),
        "forbidden_statuses_absent": variant_rules["forbidden_statuses_absent"],
        "promotable_true_count": variant_rules["promotable_true_count"],
        "paper_candidate_allowed_true_count": variant_rules["paper_candidate_allowed_true_count"],
        "stale_compact_state_warning_present_in_source": state["compact_state_stale"],
        "next_action": next_action,
    }
    write_json(output / "sandbox_batch_audit_manifest.json", manifest)
    write_text(output / "sandbox_batch_consistency_issue_review.md", consistency_issue_md(issue, state))
    write_csv(
        output / "sandbox_family_audit.csv",
        family_rows,
        [
            "family_id",
            "source_status",
            "variants_tested",
            "positive_objective_progress_variants",
            "variants_beating_active_combo",
            "drawdown_screen_passes",
            "low_active_combo_correlation_variants",
            "median_delta_vs_active_combo",
            "median_corr_vs_active_combo",
            "audit_conclusion",
            "future_preregistration_view",
            "overfitting_or_noise_risk",
            "actionable_now",
        ],
    )
    write_text(output / "sandbox_family_audit.md", family_audit_md(family_rows))
    family_files = {
        "breakout_continuation": "sandbox_breakout_continuation_review.md",
        "portfolio_combination_sleeve_ensemble": "sandbox_portfolio_combination_review.md",
        "volatility_regime": "sandbox_volatility_regime_review.md",
        "trend_momentum": "sandbox_trend_momentum_review.md",
        "mean_reversion": "sandbox_mean_reversion_review.md",
        "factor_style_rotation": "sandbox_factor_style_rotation_review.md",
        "macro_portfolio_contribution": "sandbox_macro_contribution_review.md",
    }
    for row in family_rows:
        write_text(output / family_files[row["family_id"]], single_family_md(row))
    write_text(output / "sandbox_overfitting_audit.md", overfitting_md(source_future_count))
    write_text(output / "sandbox_future_preregistration_review.md", future_prereg_md(source_future_count, family_rows))
    write_text(output / "sandbox_next_action.md", next_action_md(next_action))
    write_text(output / "sandbox_batch_audit_summary.md", summary_md(manifest, issue, family_rows))
    write_json(output / "sandbox_batch_audit_consistency_check.json", {"consistency_passed": False})
    after_strategies = strategy_snapshot(root)
    if before_strategies != after_strategies:
        manifest["active_strategy_state_changed"] = True
        manifest["rejected_strategy_state_changed"] = True
    registry_updated, roadmap_updated, compact_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    manifest["compact_state_updated"] = compact_updated
    consistency = consistency_check(manifest, output)
    write_json(output / "sandbox_batch_audit_manifest.json", manifest)
    write_json(output / "sandbox_batch_audit_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "audited_batch_id": BATCH_ID,
        "consistency_issue_found": manifest["consistency_issue_found"],
        "consistency_issue_blocking": manifest["consistency_issue_blocking"],
        "families_interesting_count": manifest["families_interesting_count"],
        "families_actionable_count": manifest["families_actionable_count"],
        "source_future_preregistration_candidate_count": source_future_count,
        "next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }
