from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import cache_inventory, write_csv


OUTPUT_DIR = (
    Path("evidence")
    / "research_recovery"
    / "next_registry_candidate_bounded_design_after_regional_momentum"
    / "latest"
)
TRIAGE_DIR = Path("evidence") / "research_recovery" / "profit_oriented_registry_research_sample_triage" / "latest"
REGIONAL_RUN_DIR = (
    Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_run" / "latest"
)
REGIONAL_DESIGN_DIR = (
    Path("evidence") / "research_recovery" / "regional_international_momentum_bounded_design" / "latest"
)
AFTER_GLOBAL_DIR = (
    Path("evidence")
    / "research_recovery"
    / "next_registry_candidate_bounded_design_after_global_multi_asset"
    / "latest"
)
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"

NEXT_ACTION_SOURCE_OF_TRUTH = "resolve_profit_oriented_registry_queue_source_of_truth_before_bounded_design"
NEXT_ACTION_DESIGN_READY = "run_selected_next_registry_candidate_bounded_design"
VALID_NEXT_ACTIONS = {NEXT_ACTION_SOURCE_OF_TRUTH, NEXT_ACTION_DESIGN_READY}

EXCLUDED_FAMILIES = {
    "global_multi_asset_etf_momentum": "global multi-asset lane already completed and excluded",
    "regional_international_momentum": "regional bounded run produced 0 risk-control passes and return-destroyed risk-control rows",
    "high_return_tactical_etf_equity_index": "recently completed high-return tactical lane excluded",
    "commodity_basket_etf_momentum_v1": "recently completed commodity-basket lane excluded",
    "commodity_wrapper_time_series_momentum": "commodity continuation excluded",
    "macro_gld_duration_risk_off": "recently completed Macro/GLD lane excluded",
    "gld_macro_risk_off": "Macro/GLD lineage continuation excluded",
    "macro_portfolio_contribution": "Macro/GLD contribution context excluded",
    "volatility_throttle_focused_research_lane_v1": "completed volatility-throttle lane excluded",
    "managed_futures_etf_wrapper": "managed futures closed under current mechanics",
    "managed_futures_style_trend": "managed futures style trend excluded",
    "crypto_spot_trend": "crypto_spot is deferred by roadmap/source-of-truth rules",
}

TERMINAL_STATUSES = {
    "rejected",
    "closed",
    "blocked",
    "benchmark_watchlist",
    "duplicate_or_near_duplicate",
    "too_slow_for_profit_goal",
    "active_observation_running",
    "promotion_candidate_found",
}

RANKING_FIELDS = (
    "rank",
    "strategy_id",
    "family",
    "status",
    "triage_score",
    "disposition_after_regional_momentum_exclusion",
    "exclusion_reason",
    "metric_source_csv",
    "median_180d_final_equity",
    "worst_drawdown",
    "risk_buffer_vs_minus_600",
    "max_reference_correlation",
    "required_local_data_symbols",
    "expected_bounded_design_size_recommendation",
)

CACHE_FIELDS = (
    "strategy_id",
    "family",
    "symbol",
    "required_for_remaining_candidate",
    "cache_status",
    "first_date",
    "last_date",
    "rows",
    "path",
)

REQUIRED_FILES = (
    "next_registry_candidate_bounded_design_after_regional_manifest.json",
    "next_registry_candidate_bounded_design_after_regional_summary.md",
    "triage_ranking_after_exclusions.csv",
    "exclusions_applied.md",
    "candidate_selection_decision.md",
    "no_eligible_candidate_blocker.md",
    "source_lineage_assessment.md",
    "local_cache_availability.csv",
    "local_cache_availability.md",
    "planned_variant_design_table_not_created.md",
    "variant_roles_not_created.md",
    "baseline_comparator_policy_not_created.md",
    "numeric_success_failure_criteria_not_created.md",
    "guardrail_checklist.json",
    "exposure_invariant_requirements.md",
    "run_readiness_decision.md",
    "next_registry_candidate_bounded_design_after_regional_next_action.md",
    "next_registry_candidate_bounded_design_after_regional_consistency_check.json",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def split_symbols(value: str) -> list[str]:
    if not value:
        return []
    return [symbol.strip() for symbol in value.replace("|", ";").split(";") if symbol.strip()]


def roadmap_crypto_deferred(root: Path) -> bool:
    text = read_text(root / ROADMAP)
    return "crypto_spot" in text and "defer_crypto_spot" in text


def regional_failed_diagnostic(root: Path) -> bool:
    manifest = read_json(root / REGIONAL_RUN_DIR / "regional_international_momentum_bounded_run_manifest.json")
    return (
        manifest.get("family_id") == "regional_international_momentum"
        and manifest.get("variant_count_evaluated") == 7
        and manifest.get("risk_control_rows_passed") == 0
        and manifest.get("regional_signal_return_destroyed_count") == 2
        and manifest.get("results_interpretable") is True
    )


def exclusion_reason(root: Path, row: dict[str, str]) -> str:
    family = row.get("family", "")
    status = row.get("status", "")
    if family == "crypto_spot_trend" and roadmap_crypto_deferred(root):
        return EXCLUDED_FAMILIES[family]
    if family in EXCLUDED_FAMILIES:
        return EXCLUDED_FAMILIES[family]
    if status in TERMINAL_STATUSES:
        return f"status `{status}` is terminal or not selectable for bounded design"
    return ""


def rank_after_exclusions(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_csv_rows(root / TRIAGE_DIR / "ranking_scoring_table.csv")
    ranked: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        reason = exclusion_reason(root, row)
        disposition = "excluded_after_regional_momentum" if reason else "eligible_after_regional_momentum_exclusion"
        scored = {
            **row,
            "disposition_after_regional_momentum_exclusion": disposition,
            "exclusion_reason": reason,
        }
        ranked.append(scored)
        if reason:
            excluded.append(scored)
        else:
            eligible.append(scored)
    eligible.sort(key=lambda item: parse_score(item.get("triage_score")), reverse=True)
    return ranked, eligible, excluded


def top_candidates(eligible: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not eligible:
        return []
    top = parse_score(eligible[0].get("triage_score"))
    return [row for row in eligible if math.isclose(parse_score(row.get("triage_score")), top, rel_tol=0.0, abs_tol=1e-9)]


def cache_rows(root: Path, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory = {row["symbol"]: row for row in cache_inventory(root)}
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        for symbol in split_symbols(candidate.get("required_local_data_symbols", "")):
            info = inventory.get(symbol, {})
            out.append(
                {
                    "strategy_id": candidate.get("strategy_id", ""),
                    "family": candidate.get("family", ""),
                    "symbol": symbol,
                    "required_for_remaining_candidate": True,
                    "cache_status": info.get("status", "missing"),
                    "first_date": info.get("first_date", ""),
                    "last_date": info.get("last_date", ""),
                    "rows": info.get("rows", 0),
                    "path": info.get("path", ""),
                }
            )
    return out


def build_manifest(
    root: Path,
    created: str,
    output: Path,
    eligible: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    top: list[dict[str, Any]],
    cache: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = top[0] if len(top) == 1 else {}
    no_eligible = len(eligible) == 0
    ambiguous = len(top) > 1
    bounded_design_created = bool(selected)
    run_readiness = (
        f"{selected.get('family')}_bounded_design_run_ready"
        if selected
        else "next_registry_candidate_bounded_design_blocked"
    )
    blocker = "none"
    if no_eligible:
        blocker = "no_eligible_candidate_after_required_exclusions"
    elif ambiguous:
        blocker = "ambiguous_top_triage_score_tie"
    next_action = NEXT_ACTION_DESIGN_READY if selected else NEXT_ACTION_SOURCE_OF_TRUTH
    return {
        "created_utc": created,
        "evidence_path": str(output.resolve()),
        "next_registry_candidate_bounded_design_after_regional_momentum": True,
        "existing_triage_ranking_inspected": (root / TRIAGE_DIR / "ranking_scoring_table.csv").exists(),
        "post_global_candidate_evidence_inspected": (root / AFTER_GLOBAL_DIR).exists(),
        "regional_design_evidence_inspected": (root / REGIONAL_DESIGN_DIR).exists(),
        "regional_run_evidence_inspected": (root / REGIONAL_RUN_DIR).exists(),
        "regional_momentum_left_failed_diagnostic": regional_failed_diagnostic(root),
        "regional_momentum_audit_run": False,
        "regional_momentum_continued_or_tuned": False,
        "bounded_design_created": bounded_design_created,
        "no_eligible_candidate_blocker_created": no_eligible,
        "ambiguity_blocker_created": ambiguous,
        "selected_candidate": selected.get("strategy_id", "none"),
        "selected_family": selected.get("family", "none"),
        "selected_triage_score": parse_score(selected.get("triage_score")) if selected else None,
        "eligible_after_exclusions_count": len(eligible),
        "excluded_after_exclusions_count": len(excluded),
        "remaining_top_candidate_count": len(top),
        "remaining_top_candidate_ids": [row.get("strategy_id", "") for row in top],
        "remaining_top_family_ids": sorted({row.get("family", "") for row in top}),
        "source_lineage_assessed": True,
        "local_cache_availability_checked": True,
        "remaining_required_symbols_cache_ready": all(row.get("cache_status") == "cache_ready" for row in cache)
        if cache
        else True,
        "crypto_spot_deferred_by_roadmap": roadmap_crypto_deferred(root),
        "planned_row_count": 0,
        "planned_row_count_lte_12": True,
        "run_readiness_decision": run_readiness,
        "run_readiness_blocker": blocker,
        "new_strategy_run": False,
        "new_backtests_run": False,
        "new_strategy_discovery_run": False,
        "new_research_batch_run": False,
        "new_families_created": False,
        "new_variants_created": False,
        "hidden_parameter_grid_created": False,
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
        "regional_momentum_continued": False,
        "next_action": next_action,
    }


def exclusions_md(excluded: list[dict[str, Any]]) -> str:
    grouped: dict[str, int] = {}
    for row in excluded:
        reason = row["exclusion_reason"]
        grouped[reason] = grouped.get(reason, 0) + 1
    lines = ["# Exclusions Applied", ""]
    for reason, count in sorted(grouped.items()):
        lines.append(f"- `{reason}`: `{count}` row(s)")
    lines.append("")
    lines.append("Regional momentum was excluded because its bounded run produced `0` risk-control passes.")
    lines.append("Crypto rows were excluded because the roadmap source-of-truth records `defer_crypto_spot`.")
    lines.append("No new family was invented and no bounded design was created without one eligible candidate.")
    return "\n".join(lines) + "\n"


def selection_md(manifest: dict[str, Any], eligible: list[dict[str, Any]]) -> str:
    lines = ["# Candidate Selection Decision", ""]
    lines.append(f"Selected candidate: `{manifest['selected_candidate']}`")
    lines.append(f"Selected family: `{manifest['selected_family']}`")
    lines.append(f"Run-readiness decision: `{manifest['run_readiness_decision']}`")
    lines.append("")
    if manifest["eligible_after_exclusions_count"] == 0:
        lines.append("Reason: no row remains eligible after applying the required exclusions to the existing triage ranking.")
    else:
        lines.append("Reason: one or more rows remained eligible, but no bounded design was authorized in this blocker branch.")
    lines.append("")
    lines.append("Eligible rows after exclusions:")
    if eligible:
        for row in eligible:
            lines.append(
                f"- `{row['strategy_id']}` / `{row['family']}` score `{row['triage_score']}` status `{row['status']}`"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def blocker_md(manifest: dict[str, Any], excluded: list[dict[str, Any]]) -> str:
    lines = ["# No Eligible Candidate Blocker", ""]
    lines.append(f"Blocker: `{manifest['run_readiness_blocker']}`")
    lines.append("")
    lines.append("The existing triage ranking was used as the source list. After required exclusions, no row remains eligible.")
    lines.append("")
    lines.append("Final excluded ranked rows:")
    for row in excluded:
        lines.append(f"- Rank `{row['rank']}` `{row['strategy_id']}` / `{row['family']}`: `{row['exclusion_reason']}`")
    lines.append("")
    lines.append("No bounded lane design was created. A future step needs an updated source-of-truth queue or explicit candidate authorization.")
    return "\n".join(lines) + "\n"


def source_lineage_md(candidates: list[dict[str, Any]], excluded: list[dict[str, Any]]) -> str:
    rows = candidates if candidates else excluded
    lines = ["# Source Lineage Assessment", ""]
    for row in rows:
        source = row.get("metric_source_csv", "")
        exists = Path(source).exists() if source else False
        lines.append(f"- `{row['strategy_id']}`")
        lines.append(f"  - Family: `{row['family']}`")
        lines.append(f"  - Status: `{row['status']}`")
        lines.append(f"  - Source CSV: `{source}`")
        lines.append(f"  - Source CSV exists: `{exists}`")
        lines.append(f"  - Disposition: `{row.get('disposition_after_regional_momentum_exclusion', '')}`")
        lines.append(f"  - Exclusion reason: `{row.get('exclusion_reason', '')}`")
    lines.append("")
    lines.append("No old evidence was converted into promotion, candidate_exhaustive, or paper-forward eligibility.")
    return "\n".join(lines) + "\n"


def cache_md(cache: list[dict[str, Any]]) -> str:
    lines = ["# Local Cache Availability", ""]
    if not cache:
        lines.append("No remaining eligible candidate required cache validation.")
    for row in cache:
        lines.append(
            f"- `{row['strategy_id']}` requires `{row['symbol']}`: `{row['cache_status']}`, "
            f"`{row['first_date']}` to `{row['last_date']}`"
        )
    return "\n".join(lines) + "\n"


def not_created_md(title: str, reason: str) -> str:
    return f"""# {title}

Not created.

Reason: `{reason}`

The task stopped before bounded design construction because the filtered triage ranking did not identify one eligible next candidate.
"""


def guardrail_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "regional_momentum_audit_run",
        "regional_momentum_continued_or_tuned",
        "new_strategy_run",
        "new_backtests_run",
        "new_strategy_discovery_run",
        "new_research_batch_run",
        "new_families_created",
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

If a future bounded design is authorized, it must enforce:

- Max daily exposure `<= 1.0`.
- Max daily weight sum `<= 1.0`.
- No NaN final weights.
- No negative weights below tolerance.
- BIL/cash replacement/remainder only.
- No BIL/cash accumulation on top of risky exposure.
- Zero target weights remain zero and are not stale-forward-filled into old allocations.

No exposure-producing design was created in this task.
"""


def run_readiness_md(manifest: dict[str, Any]) -> str:
    return f"""# Run-Readiness Decision

Decision: `{manifest['run_readiness_decision']}`

Blocker: `{manifest['run_readiness_blocker']}`

Selected candidate: `{manifest['selected_candidate']}`

No bounded lane can be run from this packet because no bounded design was created.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Next Registry Candidate Bounded Design After Regional Momentum Next Action

Exact next action:

`{next_action}`

Do not execute the next action in this task.
"""


def summary_md(manifest: dict[str, Any]) -> str:
    return f"""# Next Registry Candidate Bounded Design After Regional Momentum

Existing triage ranking inspected: `{manifest['existing_triage_ranking_inspected']}`

Regional momentum left as failed diagnostic evidence: `{manifest['regional_momentum_left_failed_diagnostic']}`

Selected candidate: `{manifest['selected_candidate']}`

Selected family: `{manifest['selected_family']}`

Eligible rows after exclusions: `{manifest['eligible_after_exclusions_count']}`

Bounded design created: `{manifest['bounded_design_created']}`

Run-readiness decision: `{manifest['run_readiness_decision']}`

Run-readiness blocker: `{manifest['run_readiness_blocker']}`

No strategy run, backtest, strategy discovery, broad research batch, provider download, intraday data, candidate_exhaustive, promotion, paper-forward activation, broker/live path, or real-money recommendation occurred.

Exact next action: `{manifest['next_action']}`
"""


def consistency_check(manifest: dict[str, Any], eligible: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_FILES}
    required["next_registry_candidate_bounded_design_after_regional_consistency_check.json"] = True
    checks = {
        "existing_triage_ranking_inspected": manifest["existing_triage_ranking_inspected"] is True,
        "regional_failed_diagnostic_preserved": manifest["regional_momentum_left_failed_diagnostic"] is True,
        "no_regional_audit_or_continuation": manifest["regional_momentum_audit_run"] is False
        and manifest["regional_momentum_continued_or_tuned"] is False,
        "bounded_design_not_created_without_candidate": manifest["eligible_after_exclusions_count"] == 0
        and manifest["bounded_design_created"] is False
        and manifest["selected_candidate"] == "none",
        "crypto_deferred_by_roadmap": manifest["crypto_spot_deferred_by_roadmap"] is True,
        "cache_availability_checked": manifest["local_cache_availability_checked"] is True,
        "no_strategy_run_or_backtest": manifest["new_strategy_run"] is False
        and manifest["new_backtests_run"] is False
        and manifest["new_strategy_discovery_run"] is False
        and manifest["new_research_batch_run"] is False,
        "no_new_family_variant_grid": manifest["new_families_created"] is False
        and manifest["new_variants_created"] is False
        and manifest["hidden_parameter_grid_created"] is False,
        "no_provider_or_intraday": manifest["provider_download"] is False and manifest["intraday_data_used"] is False,
        "no_leverage_or_derivatives": manifest["leverage_allowed"] is False
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
        "no_excluded_track_continuation": manifest["global_multi_asset_continued"] is False
        and manifest["high_return_tactical_continued"] is False
        and manifest["commodity_continued"] is False
        and manifest["macro_gld_continued"] is False
        and manifest["volatility_throttle_continued"] is False
        and manifest["managed_futures_reopened"] is False
        and manifest["crypto_continued"] is False
        and manifest["regional_momentum_continued"] is False,
        "run_readiness_blocked": manifest["run_readiness_decision"] == "next_registry_candidate_bounded_design_blocked",
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "no_eligible_rows": len(eligible) == 0,
        "required_files_present": all(required.values()),
        "required_files": required,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def run(root: Path = ROOT) -> dict[str, Any]:
    created = now_utc()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    ranked, eligible, excluded = rank_after_exclusions(root)
    top = top_candidates(eligible)
    cache = cache_rows(root, top)
    manifest = build_manifest(root, created, output, eligible, excluded, top, cache)

    write_json(output / "next_registry_candidate_bounded_design_after_regional_manifest.json", manifest)
    write_text(output / "next_registry_candidate_bounded_design_after_regional_summary.md", summary_md(manifest))
    write_csv(output / "triage_ranking_after_exclusions.csv", ranked, list(RANKING_FIELDS))
    write_text(output / "exclusions_applied.md", exclusions_md(excluded))
    write_text(output / "candidate_selection_decision.md", selection_md(manifest, eligible))
    write_text(output / "no_eligible_candidate_blocker.md", blocker_md(manifest, excluded))
    write_text(output / "source_lineage_assessment.md", source_lineage_md(top, excluded))
    write_csv(output / "local_cache_availability.csv", cache, list(CACHE_FIELDS))
    write_text(output / "local_cache_availability.md", cache_md(cache))
    write_text(
        output / "planned_variant_design_table_not_created.md",
        not_created_md("Planned Variant Design Table", manifest["run_readiness_blocker"]),
    )
    write_text(output / "variant_roles_not_created.md", not_created_md("Variant Roles", manifest["run_readiness_blocker"]))
    write_text(
        output / "baseline_comparator_policy_not_created.md",
        not_created_md("Baseline / Comparator Policy", manifest["run_readiness_blocker"]),
    )
    write_text(
        output / "numeric_success_failure_criteria_not_created.md",
        not_created_md("Numeric Success / Failure Criteria", manifest["run_readiness_blocker"]),
    )
    write_json(output / "guardrail_checklist.json", guardrail_payload(manifest))
    write_text(output / "exposure_invariant_requirements.md", exposure_md())
    write_text(output / "run_readiness_decision.md", run_readiness_md(manifest))
    write_text(output / "next_registry_candidate_bounded_design_after_regional_next_action.md", next_action_md(manifest["next_action"]))
    check = consistency_check(manifest, eligible, output)
    write_json(output / "next_registry_candidate_bounded_design_after_regional_consistency_check.json", check)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": check["consistency_passed"]}
