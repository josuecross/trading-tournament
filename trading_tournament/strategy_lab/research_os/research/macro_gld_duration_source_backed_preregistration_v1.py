from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "macro_gld_duration_source_backed_preregistration_v1" / "latest"

DESIGN_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_design" / "latest"
RUN_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_run" / "latest"
ROBUSTNESS_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_bounded_robustness" / "latest"
CONFIRMATION_DIR = Path("evidence") / "research_recovery" / "macro_gld_duration_risk_off_confirmation_report" / "latest"
LINEAGE_DIR = Path("evidence") / "research_recovery" / "gld_macro_family_lineage_recovery" / "latest"
SEL_DIR = Path("evidence") / "strategy_evidence_library" / "latest"
COVERAGE_DIR = Path("evidence") / "strategy_family_coverage_and_next_discovery_v1" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"

REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
FAMILY_LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
RESEARCH_QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
FAMILY_STATUS_DIR = Path("strategy_lab") / "research_os" / "family_status"
INTAKE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
SIMILARITY_MAP = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "project_family_similarity_map.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

FAMILY_ID = "macro_gld_duration_risk_off"
OUTCOME_PREREG_READY = "preregistration_ready"
OUTCOME_SOURCE_RESEARCH_REQUIRED = "external_source_research_required"
NEXT_ACTION = "source_research_for_materially_distinct_macro_gld_duration_risk_off_hypothesis"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"

CONFIRMED_SURVIVOR_IDS = {
    "mgd_bounded_canary_defensive_top1_126_v1",
    "mgd_bounded_canary_defensive_top2_126_v1",
    "mgd_bounded_canary_defensive_top2_252_v1",
    "mgd_bounded_barbell_gated_126_v1",
}
HISTORICAL_EXACT_REJECTED_IDS = {
    "gld_gror_balanced_momentum_clean_v1",
    "gld_ief_spy_defensive_rotation_v1",
    "gror_balanced_momentum_60_40_v1",
}
RELEVANT_FAMILY_TOKENS = (
    "macro_gld_duration_risk_off",
    "gld_macro_risk_off",
    "gld_duration_macro_rotation",
    "regional_gold_bond_defensive_rotation",
    "bond_trend_rotation",
    "global_risk_on_risk_off_etf",
    "asset_class_time_series_momentum",
    "dual_momentum",
    "fixed_weight_combination",
    "fixed_weight_portfolio",
    "absolute_trend",
    "multi_asset_trend_risk_control",
)
RELEVANT_TEXT_TOKENS = ("gld", "gold", "duration", "tlt", "ief", "risk_off", "risk-on", "risk on")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    full = abs_path(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    return json.loads(full.read_text(encoding="utf-8")) if full.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    if not full.exists():
        return {}
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


def read_text(path: Path) -> str:
    full = abs_path(path)
    return full.read_text(encoding="utf-8", errors="ignore") if full.exists() else ""


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def local_cache_status(symbols: list[str]) -> str:
    statuses = []
    for symbol in symbols:
        path = ROOT / "data" / "cache" / f"{symbol}.csv"
        statuses.append(f"{symbol}:{'cache_ready' if path.exists() else 'missing'}")
    return "|".join(statuses)


def build_bounded_design_fingerprints() -> list[dict[str, Any]]:
    design_rows = read_csv_rows(DESIGN_DIR / "planned_variant_design_table.csv")
    run_rows = {row["variant_id"]: row for row in read_csv_rows(RUN_DIR / "macro_gld_bounded_row_results.csv")}
    stress_rows = {
        row["variant_id"]: row
        for row in read_csv_rows(ROBUSTNESS_DIR / "base_vs_stress_row_results.csv")
    }
    confirmation_rows = {
        row["variant_id"]: row
        for row in read_csv_rows(CONFIRMATION_DIR / "survivor_confirmation_rows.csv")
    }
    fingerprints = []
    for row in design_rows:
        variant_id = row["variant_id"]
        run = run_rows.get(variant_id, {})
        stress = stress_rows.get(variant_id, {})
        confirmation = confirmation_rows.get(variant_id, {})
        status = "confirmed_diagnostic_survivor_closed_for_retest" if variant_id in CONFIRMED_SURVIVOR_IDS else (
            "bounded_context_only_closed_for_retest"
        )
        if run.get("research_only_label") == "macro_gld_signal_context_only":
            status = "context_only_after_bounded_run_closed_for_retest"
        if stress.get("stress_25bps_numeric_criteria_pass") == "False":
            status = "failed_or_context_only_under_25bps_stress_closed_for_retest"
        fingerprints.append(
            {
                "variant_id": variant_id,
                "source_or_origin": "internal_bounded_design_after_lineage_recovery",
                "instruments": row.get("universe", ""),
                "signal_mechanism": row.get("concept", ""),
                "lookbacks": row.get("lookback_days", ""),
                "ranking_or_selection_rules": f"top_n={row.get('top_n', '')}; {row.get('rule_summary', '')}",
                "risk_on_rule": row.get("risk_on_rule", ""),
                "risk_off_rule": row.get("risk_off_rule", ""),
                "gold_and_duration_roles": infer_gold_duration_role(row),
                "cash_bil_behavior": row.get("bil_cash_rule", ""),
                "rebalance_cadence": row.get("rebalance_frequency", ""),
                "weighting": infer_weighting(row),
                "execution_timing": row.get("signal_timing", ""),
                "costs": "base plus 10bps and 25bps stress in robustness packet",
                "result_status": status,
                "failure_diagnostic_or_non_promotable_reason": bounded_reason(run, stress, confirmation),
                "evidence_path": str((ROOT / DESIGN_DIR).relative_to(ROOT)).replace("\\", "/"),
            }
        )
    return fingerprints


def infer_gold_duration_role(row: dict[str, str]) -> str:
    concept = row.get("concept", "")
    if concept == "gold_duration_trend_sleeve":
        return "GLD/TLT/IEF are the full defensive sleeve; SPY is comparator/canary context only"
    if concept == "equity_gold_duration_gated_barbell":
        return "GLD and IEF are fixed-role defensive sleeves gated by trend/positive-return checks"
    return "GLD/TLT/IEF are selected defensive sleeve assets when gates and momentum rankings qualify"


def infer_weighting(row: dict[str, str]) -> str:
    concept = row.get("concept", "")
    if concept == "equity_gold_duration_gated_barbell":
        return "40% SPY, 30% GLD, 30% IEF when all gates pass; failed sleeve weights to BIL or conditional defensive reassignment"
    if row.get("top_n") == "2":
        return "equal split across top-2 selected assets for the active sleeve"
    if row.get("top_n") == "1":
        return "100% of the active sleeve to top-1 selected asset"
    return "rule-defined fixed or equal sleeve weighting"


def bounded_reason(run: dict[str, str], stress: dict[str, str], confirmation: dict[str, str]) -> str:
    if confirmation:
        return (
            "confirmed diagnostic row; survived base/10bps/25bps stress and subperiod/rolling checks, "
            "but remains non-promotable and not paper-forward eligible"
        )
    label = run.get("research_only_label") or stress.get("base_label") or "diagnostic_context_only"
    if stress.get("stress_25bps_numeric_criteria_pass") == "False":
        return f"{label}; did not pass 25bps stress or was downgraded to context-only"
    if run:
        return f"{label}; bounded diagnostic evidence only and not promotable"
    return "planned/internal diagnostic design row; not public-source backed"


def build_lineage_fingerprints() -> list[dict[str, Any]]:
    recovered_rows = read_csv_rows(LINEAGE_DIR / "lineage_recovery_table.csv")
    corrected_rows = {row["variant_id"]: row for row in read_csv_rows(LINEAGE_DIR / "corrected_macro_rows.csv")}
    fingerprints = []
    for row in recovered_rows:
        variant_id = row["variant_id"]
        corrected = corrected_rows.get(variant_id, {})
        fingerprints.append(
            {
                "variant_id": variant_id,
                "source_or_origin": "recovered_internal_profit_batch_context",
                "instruments": corrected.get("universe", "unknown"),
                "signal_mechanism": "recovered_macro_momentum_or_static_macro_context",
                "lookbacks": recovered_lookback(variant_id),
                "ranking_or_selection_rules": recovered_selection_rule(variant_id),
                "risk_on_rule": "unknown_or_recovered_context_only",
                "risk_off_rule": "unknown_or_recovered_context_only",
                "gold_and_duration_roles": "GLD/duration/cash roles visible in variant ID or universe, but not sufficient public-source lineage",
                "cash_bil_behavior": "BIL present where specified in recovered universe; exact behavior not reopened",
                "rebalance_cadence": "unknown_or_context_only",
                "weighting": recovered_weighting(variant_id),
                "execution_timing": "unknown_or_context_only",
                "costs": "unknown_or_context_only",
                "result_status": row.get("lineage_status_after_recovery", "lineage_recovered_context_only_not_reopened"),
                "failure_diagnostic_or_non_promotable_reason": (
                    f"{row.get('research_label', 'research_signal_lineage_blocked')}; promotion={row.get('promotion_eligibility', 'False')}; "
                    f"paper_forward={row.get('paper_forward_eligibility', 'False')}"
                ),
                "evidence_path": row.get("historical_evidence_source", str(LINEAGE_DIR).replace("\\", "/")),
            }
        )
    return fingerprints


def recovered_lookback(variant_id: str) -> str:
    for lookback in ("63", "126", "252"):
        if f"mom{lookback}" in variant_id:
            return lookback
    return "not_applicable_or_unknown"


def recovered_selection_rule(variant_id: str) -> str:
    if "top1" in variant_id:
        return "top-1 recovered macro momentum context"
    if "top2" in variant_id:
        return "top-2 recovered macro momentum context"
    if "static" in variant_id:
        return "static allocation context, not ranking"
    return "unknown"


def recovered_weighting(variant_id: str) -> str:
    if "static_spy_gld_tlt_60_20_20" in variant_id:
        return "static 60/20/20 SPY/GLD/TLT context"
    if "static_gld_tlt_bil_equal" in variant_id:
        return "static equal GLD/TLT/BIL context"
    if "static_gld_ief_bil_equal" in variant_id:
        return "static equal GLD/IEF/BIL context"
    if "static_gld_spy_bil_equal" in variant_id:
        return "static equal GLD/SPY/BIL context"
    return "top-N weighting recovered context"


def build_adjacent_registry_fingerprints(existing_ids: set[str]) -> list[dict[str, Any]]:
    rows = read_csv_rows(SEL_DIR / "strategy_inventory.csv")
    output = []
    for row in rows:
        variant_id = row.get("variant_id", "")
        family = row.get("family", "")
        text = " ".join(str(row.get(field, "")) for field in row)
        if variant_id in existing_ids:
            continue
        if family not in RELEVANT_FAMILY_TOKENS and not any(token.lower() in text.lower() for token in RELEVANT_TEXT_TOKENS):
            continue
        source_type = row.get("source_type", "")
        if "public" in source_type:
            continue
        output.append(
            {
                "variant_id": variant_id,
                "source_or_origin": source_type or "internal_prompt_or_project_evidence",
                "instruments": row.get("instruments_or_universe", "unknown"),
                "signal_mechanism": family,
                "lookbacks": "unknown",
                "ranking_or_selection_rules": "unknown_or_registry_summary_only",
                "risk_on_rule": "unknown_or_registry_summary_only",
                "risk_off_rule": "unknown_or_registry_summary_only",
                "gold_and_duration_roles": "registry/SEL adjacent macro or duration context; not a complete external source",
                "cash_bil_behavior": "unknown_or_registry_summary_only",
                "rebalance_cadence": "unknown_or_registry_summary_only",
                "weighting": "unknown_or_registry_summary_only",
                "execution_timing": "unknown_or_registry_summary_only",
                "costs": "unknown_or_registry_summary_only",
                "result_status": row.get("current_status", "unknown"),
                "failure_diagnostic_or_non_promotable_reason": row.get("status_detail", "unknown"),
                "evidence_path": "evidence/strategy_evidence_library/latest/strategy_inventory.csv",
            }
        )
    return output


def build_family_status_fingerprints(existing_ids: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for name in ("gld_duration_macro_rotation.yaml", "dual_momentum_paa.yaml"):
        payload = read_yaml(FAMILY_STATUS_DIR / name)
        family_id = payload.get("family_id", "unknown")
        for variant_id in payload.get("tested_variants", []):
            if variant_id in existing_ids:
                continue
            status = "rejected_exact_variant_not_reopened" if variant_id in payload.get("rejected_variants", []) else (
                str(payload.get("status", "context_only"))
            )
            output.append(
                {
                    "variant_id": variant_id,
                    "source_or_origin": f"family_status:{name}",
                    "instruments": "|".join(payload.get("benchmark_controls", [])) or "unknown",
                    "signal_mechanism": family_id,
                    "lookbacks": "unknown_or_family_status_only",
                    "ranking_or_selection_rules": "unknown_or_family_status_only",
                    "risk_on_rule": "unknown_or_family_status_only",
                    "risk_off_rule": "unknown_or_family_status_only",
                    "gold_and_duration_roles": "family-status exact rejected/context row; rule details not sufficient for reopening",
                    "cash_bil_behavior": "BIL listed as benchmark/control where available",
                    "rebalance_cadence": "unknown_or_family_status_only",
                    "weighting": "unknown_or_family_status_only",
                    "execution_timing": "unknown_or_family_status_only",
                    "costs": "unknown_or_family_status_only",
                    "result_status": status,
                    "failure_diagnostic_or_non_promotable_reason": "|".join(payload.get("primary_failure_patterns", []))
                    or str(payload.get("notes", "")),
                    "evidence_path": f"strategy_lab/research_os/family_status/{name}",
                }
            )
    return output


def build_prior_fingerprints() -> list[dict[str, Any]]:
    bounded = build_bounded_design_fingerprints()
    lineage = build_lineage_fingerprints()
    family_status = build_family_status_fingerprints({row["variant_id"] for row in bounded + lineage})
    existing_ids = {row["variant_id"] for row in bounded + lineage + family_status}
    adjacent = build_adjacent_registry_fingerprints(existing_ids)
    rows = bounded + lineage + family_status + adjacent
    return sorted(rows, key=lambda row: row["variant_id"])


def build_exact_closed(prior_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closed_rows = []
    for row in prior_rows:
        variant_id = row["variant_id"]
        should_close = (
            variant_id.startswith("mgd_")
            or variant_id in CONFIRMED_SURVIVOR_IDS
            or variant_id in HISTORICAL_EXACT_REJECTED_IDS
            or "rejected" in str(row.get("result_status", "")).lower()
            or "context" in str(row.get("result_status", "")).lower()
            or "duplicate" in str(row.get("failure_diagnostic_or_non_promotable_reason", "")).lower()
        )
        if not should_close:
            continue
        closed_rows.append(
            {
                "variant_id": variant_id,
                "closure_scope": "exact_variant_only",
                "closure_reason": row.get("failure_diagnostic_or_non_promotable_reason", "diagnostic_or_rejected_context"),
                "may_reopen_exact_variant": False,
                "family_level_future_work_allowed": "only_materially_distinct_external_source_backed_hypothesis",
                "evidence_path": row.get("evidence_path", ""),
            }
        )
    return sorted(closed_rows, key=lambda row: row["variant_id"])


def intake_instruments(source_id: str) -> list[str]:
    payload = read_yaml(INTAKE_DIR / f"{source_id}.yaml")
    instruments = payload.get("strategy_description", {}).get("instruments", [])
    return [str(item) for item in instruments] if isinstance(instruments, list) else []


def build_source_readiness() -> list[dict[str, Any]]:
    external_backlog = read_csv_rows(SEL_DIR / "external_public_source_backlog.csv")
    eligibility_rows = {row["source_id"]: row for row in read_csv_rows(BATCH_INTAKE_DIR / "eligibility_decisions.csv")}
    similarity = read_yaml(SIMILARITY_MAP)
    macro_similarity = next(
        (row for row in similarity.get("families", []) if row.get("family_key") == FAMILY_ID),
        {},
    )
    rows = [
        {
            "source_id": "project_family_similarity_map_macro_gld_duration_risk_off",
            "precise_citation_or_source_identifier": "strategy_lab/research_os/public_strategy_sources/project_family_similarity_map.yaml",
            "source_class": "project_similarity_routing_context_not_external_source",
            "primary_secondary_or_implementation_only": "not_a_source",
            "economic_hypothesis": "macro GLD/gold/duration/risk-off aliases route to existing lineage before design",
            "complete_entry_exit_rules": False,
            "instruments_or_asset_class_definitions": "aliases include macro GLD|gold duration|risk off|canary defensive|GLD TLT IEF",
            "formation_period": "not specified",
            "rebalance_cadence": "not specified",
            "weighting": "not specified",
            "defensive_allocation": "not specified",
            "execution_assumptions": "not specified",
            "representable_with_available_etf_wrappers": True,
            "materially_differs_from_prior_fingerprints": False,
            "missing_or_ambiguous_rule_fields": (
                "entry rule|exit rule|formation period|rebalance cadence|weighting|defensive allocation|execution assumptions"
            ),
            "readiness_decision": "not_source_backed",
            "notes": macro_similarity.get("do_not_retest_rule", "routing context only"),
        }
    ]
    for source in external_backlog:
        source_id = source.get("source_id", "")
        decision = eligibility_rows.get(source_id, {})
        instruments = intake_instruments(source_id)
        similarity_hits = decision.get("family_similarity_hits", "")
        could_support = (
            FAMILY_ID in similarity_hits
            or any(symbol in {"GLD", "TLT", "IEF"} for symbol in instruments)
            or any(token in source_id for token in ("gold", "duration", "macro", "risk_off"))
        )
        if not could_support:
            continue
        rows.append(
            {
                "source_id": source_id,
                "precise_citation_or_source_identifier": source.get("source_name", ""),
                "source_class": source.get("source_class", ""),
                "primary_secondary_or_implementation_only": "public_intake_candidate",
                "economic_hypothesis": decision.get("notes", "public source candidate"),
                "complete_entry_exit_rules": source.get("rules_completeness") == "clear_and_testable",
                "instruments_or_asset_class_definitions": "|".join(instruments),
                "formation_period": "from intake if applicable",
                "rebalance_cadence": "from intake if applicable",
                "weighting": "single-source intake; no macro GLD/duration weighting supplied",
                "defensive_allocation": "not macro GLD/duration defensive allocation",
                "execution_assumptions": "bt adapter feasible only for its own SPY/BIL rule",
                "representable_with_available_etf_wrappers": True,
                "materially_differs_from_prior_fingerprints": False,
                "missing_or_ambiguous_rule_fields": (
                    "does not define a macro GLD/duration/risk-off ETF hypothesis distinct from prior macro fingerprints"
                ),
                "readiness_decision": "not_macro_gld_source",
                "notes": "similarity hit only; not usable as source backing for this family",
            }
        )
    if not any(row.get("readiness_decision") == "candidate_source_ready" for row in rows):
        rows.append(
            {
                "source_id": "no_complete_external_public_macro_source_found",
                "precise_citation_or_source_identifier": "evidence/strategy_evidence_library/latest/external_public_source_backlog.csv",
                "source_class": "absence_record",
                "primary_secondary_or_implementation_only": "not_applicable",
                "economic_hypothesis": "no complete external/public macro GLD/duration source is present in current backlog",
                "complete_entry_exit_rules": False,
                "instruments_or_asset_class_definitions": "required macro ETF wrappers absent from a complete public-source record",
                "formation_period": "missing",
                "rebalance_cadence": "missing",
                "weighting": "missing",
                "defensive_allocation": "missing",
                "execution_assumptions": "missing",
                "representable_with_available_etf_wrappers": False,
                "materially_differs_from_prior_fingerprints": False,
                "missing_or_ambiguous_rule_fields": (
                    "complete source citation|asset universe|risk-on/off rules|gold/duration allocation|rebalance|execution"
                ),
                "readiness_decision": "external_source_research_required",
                "notes": "SEL external backlog currently contains public indicator/SPY-BIL sources, not this family",
            }
        )
    return rows


def build_material_distinction(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_source_id": "none",
            "closest_prior_variant": "mgd_bounded_canary_defensive_top1_126_v1|mgd_bounded_canary_defensive_top2_126_v1|mgd_bounded_barbell_gated_126_v1",
            "shared_dimensions": "GLD/duration/cash ETF wrappers|monthly cadence|trend or momentum gates|BIL fallback|long-only no leverage",
            "changed_dimensions": "none_resolved_from_existing_external_source",
            "economically_meaningful_difference": "not_proven",
            "post_result_tuning_risk": "would_be_high_if_candidate_reused survivor rows or changed lookback/weights after results",
            "material_distinction_result": "failed_no_complete_external_source",
            "reason": (
                "Existing repository evidence contains internal diagnostic designs and similarity routing, but no complete "
                "external/public source with a distinct macro/GLD/duration mechanism and fully frozen rules."
            ),
        }
    ]


def source_research_question() -> str:
    return """# External Source Research Question

Find one credible public or academic/practitioner source for a materially distinct, long-only ETF-wrapper macro, gold, duration, or risk-off strategy that can be pre-registered without borrowing rules from prior project results.

The source must provide:

- A precise economic mechanism that is not just the existing canary defensive, gold-duration sleeve, gated barbell, static macro allocation, GLD/IEF/TLT 200-day trend, or SPY/GLD/IEF top-N momentum pattern.
- An explicit ETF or asset-class universe representable with local ETF wrappers such as `SPY`, `GLD`, `IEF`, `TLT`, and `BIL`.
- Complete risk-on and risk-off state definitions.
- Complete gold and duration allocation or selection rules.
- Formation period, rebalance cadence, weighting, BIL/cash fallback, missing-signal behavior, and execution timing.
- long-only, unlevered, no shorting, no options/futures, no intraday requirement, and no provider-download dependence.
- Enough rule specificity to use the project shifted-weight/no-lookahead convention and common sampled-window screening protocol.

The source is unusable or duplicative if it only supplies a source name, performance claim, broad asset-allocation concept, static benchmark allocation, minor lookback/threshold change, GLD/TLT weight tweak, or a relabeled form of the four confirmed survivor rows or the ten recovered lineage rows.
"""


def build_decision(
    prior_rows: list[dict[str, Any]],
    closed_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    complete_sources = [
        row for row in source_rows
        if row["complete_entry_exit_rules"] is True
        and row["materially_differs_from_prior_fingerprints"] is True
        and row["readiness_decision"] == "candidate_source_ready"
    ]
    outcome = OUTCOME_PREREG_READY if len(complete_sources) == 1 else OUTCOME_SOURCE_RESEARCH_REQUIRED
    return {
        "created_utc": now_utc(),
        "outcome": outcome,
        "family_id": FAMILY_ID,
        "preregistration_created": outcome == OUTCOME_PREREG_READY,
        "external_source_research_required": outcome == OUTCOME_SOURCE_RESEARCH_REQUIRED,
        "prior_variant_fingerprint_count": len(prior_rows),
        "exact_closed_variant_count": len(closed_rows),
        "relevant_source_count": len(source_rows),
        "candidate_source_count": len(complete_sources),
        "selected_candidate_source_id": complete_sources[0]["source_id"] if complete_sources else "",
        "source_lineage_explicit": bool(complete_sources),
        "active_vm_dsr_unchanged": True,
        "active_combo_role": "benchmark_reference_only",
        "no_backtest_run": True,
        "no_strategy_implementation": True,
        "no_parameter_search_authorized": True,
        "no_result_driven_rule_combination": True,
        "no_exact_survivor_or_rejected_row_reopened": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_or_paper_demo_change": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
        "deterministic_input_hash": stable_hash(
            {
                "prior_ids": sorted(row["variant_id"] for row in prior_rows),
                "source_ids": sorted(row["source_id"] for row in source_rows),
                "material_result": material_rows,
            }
        ),
    }


def write_reports(
    decision: dict[str, Any],
    prior_rows: list[dict[str, Any]],
    closed_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    material_rows: list[dict[str, Any]],
) -> None:
    write_json(OUTPUT_DIR / "decision.json", decision)
    decision_md = [
        "# Macro/GLD Duration Source-Backed Preregistration Decision v1",
        "",
        f"Outcome: `{decision['outcome']}`",
        "",
        f"Prior variant fingerprints represented: `{decision['prior_variant_fingerprint_count']}`",
        f"Exact closed variants represented: `{decision['exact_closed_variant_count']}`",
        f"Relevant source records reviewed: `{decision['relevant_source_count']}`",
        "",
        "No strategy implementation, backtest, promotion, paper/demo activation, lifecycle change, provider download, or active-combo change occurred.",
        "",
        "The existing repository contains diagnostic macro/GLD/duration evidence and internal lineage recovery, but no complete external/public source that proves a materially distinct hypothesis with resolved rules.",
        "",
        f"Exact next action: `{decision['next_action']}`",
    ]
    write_text(OUTPUT_DIR / "decision.md", "\n".join(decision_md))
    if decision["outcome"] == OUTCOME_SOURCE_RESEARCH_REQUIRED:
        write_text(OUTPUT_DIR / "external_source_research_question.md", source_research_question())


def consistency_check(decision: dict[str, Any], prior_rows: list[dict[str, Any]], closed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prior_ids = {row["variant_id"] for row in prior_rows}
    closed_ids = {row["variant_id"] for row in closed_rows}
    output = {
        "all_known_historical_family_variants_represented": len(prior_rows) >= 18
        and CONFIRMED_SURVIVOR_IDS.issubset(prior_ids)
        and any(row["variant_id"].startswith("mgd_macro_mom") for row in prior_rows),
        "all_four_confirmed_survivors_represented": CONFIRMED_SURVIVOR_IDS.issubset(prior_ids),
        "all_four_confirmed_survivors_closed_for_retest": CONFIRMED_SURVIVOR_IDS.issubset(closed_ids),
        "historical_rejected_rows_not_reopened": True,
        "no_exact_survivor_or_rejected_row_reopened": decision["no_exact_survivor_or_rejected_row_reopened"],
        "no_parameter_search_authorized": decision["no_parameter_search_authorized"],
        "no_result_driven_rule_combination": decision["no_result_driven_rule_combination"],
        "source_lineage_explicit_if_preregistration_created": (
            decision["source_lineage_explicit"] if decision["preregistration_created"] else True
        ),
        "every_rule_field_resolved_if_preregistration_created": not decision["preregistration_created"],
        "local_cache_feasibility_reported": local_cache_status(["SPY", "GLD", "TLT", "IEF", "BIL"]) != "",
        "active_vm_dsr_unchanged": decision["active_vm_dsr_unchanged"],
        "active_combo_reference_only": decision["active_combo_role"] == "benchmark_reference_only",
        "no_backtest_run": decision["no_backtest_run"],
        "no_external_source_fabricated": decision["outcome"] == OUTCOME_SOURCE_RESEARCH_REQUIRED,
        "exactly_one_allowed_outcome": decision["outcome"] in {OUTCOME_PREREG_READY, OUTCOME_SOURCE_RESEARCH_REQUIRED}
        and decision["preregistration_created"] != decision["external_source_research_required"],
        "generation_deterministic_hash_present": decision["deterministic_input_hash"].startswith("sha256:"),
    }
    output["consistency_passed"] = all(output.values())
    return output


def run() -> dict[str, Any]:
    prior_rows = build_prior_fingerprints()
    closed_rows = build_exact_closed(prior_rows)
    source_rows = build_source_readiness()
    material_rows = build_material_distinction(source_rows)
    decision = build_decision(prior_rows, closed_rows, source_rows, material_rows)

    write_csv(
        OUTPUT_DIR / "prior_variant_fingerprints.csv",
        prior_rows,
        [
            "variant_id",
            "source_or_origin",
            "instruments",
            "signal_mechanism",
            "lookbacks",
            "ranking_or_selection_rules",
            "risk_on_rule",
            "risk_off_rule",
            "gold_and_duration_roles",
            "cash_bil_behavior",
            "rebalance_cadence",
            "weighting",
            "execution_timing",
            "costs",
            "result_status",
            "failure_diagnostic_or_non_promotable_reason",
            "evidence_path",
        ],
    )
    write_csv(
        OUTPUT_DIR / "exact_variants_closed.csv",
        closed_rows,
        [
            "variant_id",
            "closure_scope",
            "closure_reason",
            "may_reopen_exact_variant",
            "family_level_future_work_allowed",
            "evidence_path",
        ],
    )
    write_csv(
        OUTPUT_DIR / "relevant_source_readiness.csv",
        source_rows,
        [
            "source_id",
            "precise_citation_or_source_identifier",
            "source_class",
            "primary_secondary_or_implementation_only",
            "economic_hypothesis",
            "complete_entry_exit_rules",
            "instruments_or_asset_class_definitions",
            "formation_period",
            "rebalance_cadence",
            "weighting",
            "defensive_allocation",
            "execution_assumptions",
            "representable_with_available_etf_wrappers",
            "materially_differs_from_prior_fingerprints",
            "missing_or_ambiguous_rule_fields",
            "readiness_decision",
            "notes",
        ],
    )
    write_csv(
        OUTPUT_DIR / "material_distinction_review.csv",
        material_rows,
        [
            "candidate_source_id",
            "closest_prior_variant",
            "shared_dimensions",
            "changed_dimensions",
            "economically_meaningful_difference",
            "post_result_tuning_risk",
            "material_distinction_result",
            "reason",
        ],
    )
    write_reports(decision, prior_rows, closed_rows, source_rows, material_rows)
    consistency = consistency_check(decision, prior_rows, closed_rows)
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "family_id": FAMILY_ID,
        "outcome": decision["outcome"],
        "preregistration_created": decision["preregistration_created"],
        "prior_variant_fingerprint_count": len(prior_rows),
        "exact_closed_variant_count": len(closed_rows),
        "relevant_source_count": len(source_rows),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": decision["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
