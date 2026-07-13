from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "strategy_family_coverage_and_next_discovery_v1" / "latest"
SCREENING_DIR = Path("evidence") / "public_source_comparative_screening_batch_v1" / "latest"
SEL_DIR = Path("evidence") / "strategy_evidence_library" / "latest"
CHECKPOINT_DIR = Path("evidence") / "current_research_checkpoint" / "latest"
BATCH_INTAKE_DIR = Path("evidence") / "research_recovery" / "public_source_batch_intake_validation" / "latest"
INTAKE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
FAMILY_LEDGER = Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml"
RESEARCH_QUEUE = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
REGISTRY = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

BATCH_ID = "public_source_comparative_screening_batch_v1"
NEXT_ACTION = "direction_owner_select_next_preregistration_or_source_research_from_options"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
PRIOR_PROMISING_FAMILIES = (
    "high_return_tactical_etf_equity_index",
    "macro_gld_duration_risk_off",
)
SIX_SCREENED_LANES = (
    "public_source_adx_dmi_bounded_bt_lane_v1",
    "public_source_cci_correction_bounded_bt_lane_v1",
    "public_source_coppock_curve_bounded_bt_lane_v1",
    "public_source_larry_connors_rsi2_bounded_bt_lane_v1",
    "public_source_parabolic_sar_bounded_bt_lane_v1",
    "public_source_percent_b_money_flow_bounded_bt_lane_v1",
)

SCREENED_FAILURE_OVERRIDES = {
    "public_source_adx_dmi_bounded_bt_lane_v1": "weak versus active-combo benchmark after corrected true-crossover audit",
    "public_source_cci_correction_bounded_bt_lane_v1": "weak versus active-combo benchmark",
    "public_source_coppock_curve_bounded_bt_lane_v1": (
        "sampled benchmark-like behavior: final equity, profit, drawdown, stop, and target outcomes "
        "matched SPY buy-and-hold in all ten sampled 90/180-day windows"
    ),
    "public_source_larry_connors_rsi2_bounded_bt_lane_v1": (
        "weak versus active-combo benchmark and high allocation-change count"
    ),
    "public_source_parabolic_sar_bounded_bt_lane_v1": "insufficient return and no material edge",
    "public_source_percent_b_money_flow_bounded_bt_lane_v1": (
        "beat active combo in four of ten sampled windows, beat SPY buy-and-hold in zero sampled "
        "windows, and had worse worst-drawdown than active combo; no robustness review authorized"
    ),
}

SCREENED_FAMILY_FUTURE_CONDITIONS = {
    "equity_index_adx_dmi_trend_strength": (
        "family remains open only for a materially distinct, source-backed ADX/DMI hypothesis; "
        "do not retest this exact SPY/BIL transition-event implementation"
    ),
    "equity_index_cci_pullback_trend_bias": (
        "family remains open only for a materially distinct, source-backed CCI hypothesis with a "
        "different economic mechanism; do not retest this exact weekly/daily CCI implementation"
    ),
    "long_term_equity_index_momentum_zero_cross": (
        "family remains open only for a materially distinct source-backed recovery signal; do not "
        "retest this exact Coppock row because it behaved as SPY buy-and-hold in the sampled windows"
    ),
    "short_term_equity_mean_reversion": (
        "family remains open only for a materially distinct mean-reversion hypothesis with predeclared "
        "cost/turnover controls; do not retest this exact Connors RSI(2) row"
    ),
    "equity_index_parabolic_sar_trend_reversal": (
        "family remains open only for a materially distinct source-backed stop/reversal hypothesis; "
        "do not retest this exact Parabolic SAR SPY/BIL row"
    ),
    "price_band_money_flow_confirmation": (
        "family remains open only for a materially distinct price-band/money-flow source; do not "
        "advance this Percent B/MFI row to robustness"
    ),
}

MECHANISM_PATTERNS = (
    ("cash_proxy", ("bil", "cash")),
    ("benchmark_controls", ("benchmark", "buy_hold", "buy_and_hold", "spy_200d", "static_all_weather", "multi_blocked_reference")),
    ("calendar_effects", ("calendar", "turn_of_month", "sell_in_may", "halloween")),
    ("single_asset_mean_reversion", ("mean_reversion", "rsi2", "pullback", "cci")),
    ("breakout_or_price_band_systems", ("breakout", "bollinger", "percent_b", "money_flow", "sar")),
    ("single_asset_equity_trend_timing", ("adx", "dmi", "coppock", "golden_cross", "moving_average")),
    ("volatility_managed_equity", ("volatility_throttle", "volatility_managed", "low_volatility", "lowvol")),
    ("tactical_equity_index_allocation", ("high_return_tactical", "equity_index", "growth_core")),
    ("gold_duration_commodity_macro_rotation", ("macro_gld", "gld", "gold", "duration", "commodity")),
    ("defensive_asset_rotation", ("defensive", "risk_off", "canary")),
    ("etf_or_sector_rotation", ("sector", "rotation", "relative_strength")),
    (
        "cross_sectional_momentum",
        (
            "cross_sectional",
            "momentum_rotation",
            "dual_momentum",
            "global_multi_asset",
            "quality_momentum",
            "quality_value_momentum",
            "regional_international",
            "individual_stock_momentum",
            "cross_asset_momentum",
        ),
    ),
    (
        "time_series_momentum",
        (
            "trend_following",
            "time_series_momentum",
            "absolute_trend",
            "managed_futures",
            "trend_momentum",
            "multi_asset_trend",
            "momentum_carry",
        ),
    ),
    ("regime_based_allocation", ("regime", "breadth_state", "spy200d")),
    ("risk_parity_inverse_volatility_or_vol_targeting", ("risk_parity", "inverse_volatility", "vol_target")),
    ("relative_value_or_spread_approaches", ("relative_value", "spread", "pairs")),
    ("intraday_or_execution_sensitive", ("intraday", "orb", "vwap", "gap", "options", "leverage", "crypto")),
    (
        "portfolio_level_combinations_and_overlays",
        (
            "combo",
            "ensemble",
            "portfolio_combination",
            "active_sleeve",
            "fixed_strategy",
            "fixed_weight",
            "portfolio",
        ),
    ),
    ("factor_or_yield_proxy", ("carry_yield", "dividend_quality_yield", "selective_growth", "quality_momentum_etf_proxy")),
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    return json.loads(full.read_text(encoding="utf-8")) if full.exists() else {}


def read_yaml(path: Path) -> dict[str, Any]:
    full = abs_path(path)
    if not full.exists():
        return {}
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    full = abs_path(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


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


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def mechanism_for_family(family_id: str) -> str:
    key = family_id.lower()
    for mechanism, tokens in MECHANISM_PATTERNS:
        if any(token in key for token in tokens):
            return mechanism
    return "unknown_or_mixed"


def split_pipe(value: str) -> list[str]:
    return [item for item in (value or "").split("|") if item]


def count_statuses(inventory_rows: list[dict[str, str]], family_id: str) -> dict[str, int]:
    rows = [row for row in inventory_rows if row.get("family") == family_id]
    rejected = 0
    blocked = 0
    active_or_eligible = 0
    unresolved = 0
    for row in rows:
        status = f"{row.get('current_status', '')} {row.get('status_detail', '')}".lower()
        if any(token in status for token in ("rejected", "closed", "no_candidate", "archive", "failed")):
            rejected += 1
        elif any(token in status for token in ("blocked", "paused", "manual_input", "incomplete")):
            blocked += 1
        elif any(token in status for token in ("active", "eligible", "accepted", "promotion_review_passed")):
            active_or_eligible += 1
        else:
            unresolved += 1
    return {
        "rejected": rejected,
        "blocked": blocked,
        "active_or_eligible": active_or_eligible,
        "unresolved": unresolved,
        "variant_count": len({row.get("variant_id", "") for row in rows if row.get("variant_id")}),
    }


def coverage_status(
    family_id: str,
    mechanism: str,
    tested_count: int,
    failure_pattern: str,
    ledger_status: str,
) -> str:
    if family_id in {
        "defensive_sector_rotation",
        "volatility_managed_quality_lowvol",
    }:
        return "adequately_covered"
    if "closed" in ledger_status or "blocked" in ledger_status or "lineage_recovery_needed" in ledger_status:
        return "blocked_by_data_or_execution"
    if family_id in PRIOR_PROMISING_FAMILIES:
        return "open_only_for_materially_distinct_hypothesis"
    if family_id in SCREENED_FAMILY_FUTURE_CONDITIONS:
        return "open_only_for_materially_distinct_hypothesis"
    if mechanism in {
        "single_asset_equity_trend_timing",
        "single_asset_mean_reversion",
        "breakout_or_price_band_systems",
    } and tested_count >= 2:
        return "overrepresented"
    if tested_count == 0:
        return "unresearched"
    if failure_pattern:
        return "adequately_covered"
    return "underrepresented" if tested_count <= 1 else "adequately_covered"


def likely_next_test_character(status: str) -> str:
    if status == "open_only_for_materially_distinct_hypothesis":
        return "genuine_diversification_only_if_new_source_changes_economic_behavior"
    if status == "overrepresented":
        return "minor_indicator_variation_or_duplicate_economic_behavior"
    if status == "blocked_by_data_or_execution":
        return "blocked_or_prohibited_exact_retest"
    if status == "unresearched":
        return "genuine_diversification_possible_after_source_research"
    return "case_specific_direction_owner_review_required"


def family_from_intake(source_id: str) -> str:
    payload = read_yaml(INTAKE_DIR / f"{source_id}.yaml")
    return str(payload.get("strategy_description", {}).get("strategy_family", "unknown"))


def instruments_from_intake(source_id: str) -> list[str]:
    payload = read_yaml(INTAKE_DIR / f"{source_id}.yaml")
    instruments = payload.get("strategy_description", {}).get("instruments", [])
    return [str(item) for item in instruments] if isinstance(instruments, list) else []


def timeframe_from_intake(source_id: str) -> str:
    payload = read_yaml(INTAKE_DIR / f"{source_id}.yaml")
    return str(payload.get("strategy_description", {}).get("timeframe", "unknown"))


def citation_completeness(source_id: str) -> str:
    payload = read_yaml(INTAKE_DIR / f"{source_id}.yaml")
    citation = payload.get("source", {}).get("source_url_or_citation", "")
    return "present" if citation and citation != "unknown" else "missing"


def cache_summary_for_source(source_id: str, cache_rows: list[dict[str, str]]) -> str:
    rows = [row for row in cache_rows if row.get("source_id") == source_id]
    if not rows:
        return "unknown"
    ready = sum(1 for row in rows if row.get("cache_status") == "cache_ready")
    return f"{ready}/{len(rows)} required symbols cache_ready"


def build_exact_variant_memory(lane_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(lane_rows, key=lambda item: item["lane_id"]):
        lane_id = row["lane_id"]
        family = row["family_id"]
        rows.append(
            {
                "lane_id": lane_id,
                "primary_variant_id": row["primary_variant_id"],
                "family_id": family,
                "batch_id": BATCH_ID,
                "screening_outcome": row["screening_outcome"],
                "concise_failure_reason": SCREENED_FAILURE_OVERRIDES[lane_id],
                "ready_for_immediate_retest": False,
                "family_remains_open": True,
                "future_family_level_conditions": SCREENED_FAMILY_FUTURE_CONDITIONS.get(
                    family,
                    "materially distinct source-backed hypothesis and fresh preregistration required",
                ),
                "evidence_path": str(SCREENING_DIR).replace("\\", "/"),
            }
        )
    return rows


def build_external_readiness(
    backlog_rows: list[dict[str, str]],
    eligibility_rows: list[dict[str, str]],
    cache_rows: list[dict[str, str]],
    closed_source_ids: set[str],
) -> list[dict[str, Any]]:
    decisions = {row["source_id"]: row for row in eligibility_rows}
    readiness_overrides = {
        "bollinger_band_squeeze_breakout": "needs_rule_completion",
        "macd_stochastic_double_cross": "needs_rule_completion",
        "low_volatility_factor_proxy": "needs_rule_completion",
        "golden_cross_50_200": "duplicate_do_not_retest",
        "sector_momentum_rotational_system": "duplicate_do_not_retest",
        "sell_in_may_halloween_effect": "duplicate_do_not_retest",
    }
    notes = {
        "bollinger_band_squeeze_breakout": (
            "setup threshold and standalone long-only exit/cash semantics remain review-required; "
            "also another SPY/BIL price-volatility timing lane"
        ),
        "macd_stochastic_double_cross": (
            "public-source exit semantics/timing window need direction-owner clarification before any bounded design"
        ),
        "low_volatility_factor_proxy": (
            "listed instruments are cached, but entry/exit/rebalance rules are still manual_input_required and "
            "overlap active VM/low-vol context"
        ),
        "golden_cross_50_200": "duplicate/control-risk because SPY_200d controls already exist",
        "sector_momentum_rotational_system": (
            "duplicate-risk versus already tested sector/growth tactical and high-return tactical equity work"
        ),
        "sell_in_may_halloween_effect": (
            "seasonal calendar duplicate-risk after Turn-of-the-Month was downgraded as cost-sensitive and rolling-weak"
        ),
    }
    output: list[dict[str, Any]] = []
    for row in sorted(backlog_rows, key=lambda item: item["source_id"]):
        source_id = row["source_id"]
        if source_id in closed_source_ids:
            continue
        source_class = row.get("source_class", "")
        if source_class.startswith("internal") or source_class == "project_generated":
            continue
        decision = decisions.get(source_id, {})
        family = decision.get("strategy_family") or family_from_intake(source_id)
        output.append(
            {
                "source_id": source_id,
                "source_class": source_class,
                "source_name": row.get("source_name", ""),
                "linked_family": family,
                "rule_completeness": row.get("rules_completeness", decision.get("eligibility_decision", "unknown")),
                "source_citation_provenance_completeness": citation_completeness(source_id),
                "required_instruments": instruments_from_intake(source_id),
                "required_data": timeframe_from_intake(source_id),
                "local_cache_feasibility": cache_summary_for_source(source_id, cache_rows),
                "execution_feasibility": "bt_adapter_feasible_after_rule_completion",
                "similar_project_strategies": decision.get("family_similarity_hits", ""),
                "duplicate_or_overlap_risk": (
                    "high" if source_id in {"golden_cross_50_200", "sector_momentum_rotational_system", "sell_in_may_halloween_effect"} else "medium"
                ),
                "existing_local_implementation": row.get("linked_local_implementation_exists", "False"),
                "existing_exact_test_or_rejection": "none_in_current_screening_batch",
                "readiness_classification": readiness_overrides.get(source_id, "needs_source_research"),
                "notes": notes.get(source_id, "requires source/rule review before any bounded preregistration"),
            }
        )
    return output


def build_family_coverage(
    inventory_rows: list[dict[str, str]],
    sel_family_rows: list[dict[str, str]],
    lane_rows: list[dict[str, str]],
    external_rows: list[dict[str, Any]],
    ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    family_ids: set[str] = set()
    family_ids.update(row.get("family", "") for row in inventory_rows if row.get("family"))
    family_ids.update(row.get("canonical_family_id", "") for row in sel_family_rows if row.get("canonical_family_id"))
    family_ids.update(row.get("family_id", "") for row in lane_rows if row.get("family_id"))
    family_ids.update(row.get("linked_family", "") for row in external_rows if row.get("linked_family"))
    family_ids.update(PRIOR_PROMISING_FAMILIES)
    family_ids.update(entry.get("family_id", "") for entry in ledger.get("entries", []) if entry.get("family_id"))
    family_ids.discard("unknown")
    family_ids.discard("")

    sel_counts = {
        row.get("canonical_family_id", ""): int(row.get("strategy_or_lane_count", "0") or 0)
        for row in sel_family_rows
    }
    screened_by_family: dict[str, list[dict[str, str]]] = {}
    for row in lane_rows:
        screened_by_family.setdefault(row["family_id"], []).append(row)
    ledger_by_family = {entry.get("family_id"): entry for entry in ledger.get("entries", [])}
    external_by_family: dict[str, int] = {}
    for row in external_rows:
        external_by_family[row["linked_family"]] = external_by_family.get(row["linked_family"], 0) + 1

    rows: list[dict[str, Any]] = []
    for family_id in sorted(family_ids):
        status_counts = count_statuses(inventory_rows, family_id)
        screened_rows = screened_by_family.get(family_id, [])
        tested_count = max(
            status_counts["variant_count"],
            sel_counts.get(family_id, 0),
            len(screened_rows),
        )
        failure_pattern = ""
        most_recent = ""
        if screened_rows:
            failure_pattern = "|".join(sorted({row["primary_failure_pattern"] for row in screened_rows}))
            most_recent = str(SCREENING_DIR).replace("\\", "/")
        if family_id == "high_return_tactical_etf_equity_index":
            most_recent = "evidence/research_recovery/high_return_tactical_etf_equity_index_bounded_robustness/latest"
            failure_pattern = "rolling_window_weakness_and_context_only_after_robustness"
            tested_count = max(tested_count, 6)
        if family_id == "macro_gld_duration_risk_off":
            most_recent = "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report/latest"
            failure_pattern = "diagnostic_confirmation_only_no_promotion_or_continuation_now"
            tested_count = max(tested_count, 4)
        ledger_entry = ledger_by_family.get(family_id, {})
        ledger_status = str(ledger_entry.get("current_status", ""))
        if not most_recent and ledger_entry.get("authoritative_evidence_path"):
            most_recent = str(ledger_entry["authoritative_evidence_path"])

        mechanism = mechanism_for_family(family_id)
        status = coverage_status(family_id, mechanism, tested_count, failure_pattern, ledger_status)
        rows.append(
            {
                "family_id": family_id,
                "mechanism": mechanism,
                "instruments_universe": infer_universe(family_id, inventory_rows, external_rows),
                "timeframe": infer_timeframe(family_id, inventory_rows, external_rows),
                "exact_variants_tested": tested_count,
                "rejected_count": status_counts["rejected"],
                "blocked_count": status_counts["blocked"],
                "unresolved_count": status_counts["unresolved"],
                "active_or_eligible_count": status_counts["active_or_eligible"],
                "external_backlog_source_count": external_by_family.get(family_id, 0),
                "most_recent_valid_evidence": most_recent or "unknown",
                "primary_repeated_failure_pattern": failure_pattern or ledger_entry.get("latest_decision", "unknown"),
                "coverage_status": status,
                "likely_next_test_character": likely_next_test_character(status),
                "notes": coverage_notes(family_id, status),
            }
        )
    return rows


def infer_universe(family_id: str, inventory_rows: list[dict[str, str]], external_rows: list[dict[str, Any]]) -> str:
    for row in inventory_rows:
        if row.get("family") == family_id and row.get("instruments_or_universe"):
            return row["instruments_or_universe"]
    for row in external_rows:
        if row.get("linked_family") == family_id and row.get("required_instruments"):
            return csv_value(row["required_instruments"])
    if family_id == "macro_gld_duration_risk_off":
        return "GLD|duration ETFs|BIL controls"
    if family_id == "high_return_tactical_etf_equity_index":
        return "equity index and sector ETFs|BIL"
    return "unknown"


def infer_timeframe(family_id: str, inventory_rows: list[dict[str, str]], external_rows: list[dict[str, Any]]) -> str:
    for row in inventory_rows:
        if row.get("family") == family_id and row.get("timeframe"):
            return row["timeframe"]
    for row in external_rows:
        if row.get("linked_family") == family_id and row.get("required_data"):
            return row["required_data"]
    return "unknown"


def coverage_notes(family_id: str, status: str) -> str:
    if family_id in SCREENED_FAMILY_FUTURE_CONDITIONS:
        return "exact public-source implementation closed for immediate retesting; broader family not automatically closed"
    if family_id == "high_return_tactical_etf_equity_index":
        return "volatility-throttle descendants produced diagnostic evidence, but robustness downgraded exact rows to context-only"
    if family_id == "macro_gld_duration_risk_off":
        return "confirmation evidence is usable diagnostic context, but not promotable or paper-forward eligible"
    if status == "overrepresented":
        return "many rows are economically similar timing/indicator variants rather than broad family diversification"
    return "repository evidence mapped without changing lifecycle status"


def build_mechanism_concentration(family_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in family_rows:
        mechanism = row["mechanism"]
        item = grouped.setdefault(
            mechanism,
            {
                "mechanism": mechanism,
                "family_count": 0,
                "tested_variant_count": 0,
                "screened_lane_count": 0,
                "external_source_candidate_count": 0,
                "representative_families": [],
            },
        )
        item["family_count"] += 1
        item["tested_variant_count"] += int(row["exact_variants_tested"])
        if row["family_id"] in SCREENED_FAMILY_FUTURE_CONDITIONS:
            item["screened_lane_count"] += 1
        item["external_source_candidate_count"] += int(row["external_backlog_source_count"])
        if len(item["representative_families"]) < 8:
            item["representative_families"].append(row["family_id"])

    output: list[dict[str, Any]] = []
    for item in sorted(grouped.values(), key=lambda row: row["mechanism"]):
        tested = int(item["tested_variant_count"])
        if item["mechanism"] in {
            "single_asset_equity_trend_timing",
            "single_asset_mean_reversion",
            "breakout_or_price_band_systems",
        } and tested >= 5:
            assessment = "concentrated_in_single_asset_spy_bil_indicator_timing"
        elif item["mechanism"] in {
            "relative_value_or_spread_approaches",
            "risk_parity_inverse_volatility_or_vol_targeting",
        }:
            assessment = "underused_or_unresearched_mechanism"
        elif tested == 0:
            assessment = "unresearched"
        elif tested <= 2:
            assessment = "lightly_covered"
        else:
            assessment = "covered"
        output.append({**item, "concentration_assessment": assessment})
    return output


def build_prior_promising_status() -> list[dict[str, Any]]:
    high_manifest = read_json(
        Path("evidence")
        / "research_recovery"
        / "high_return_tactical_etf_equity_index_bounded_robustness"
        / "latest"
        / "high_return_tactical_bounded_robustness_manifest.json"
    )
    macro_manifest = read_json(
        Path("evidence")
        / "research_recovery"
        / "macro_gld_duration_risk_off_confirmation_report"
        / "latest"
        / "macro_gld_confirmation_manifest.json"
    )
    return [
        {
            "family_id": "high_return_tactical_etf_equity_index",
            "current_status": "diagnostic_context_only_after_robustness",
            "last_valid_result": (
                f"{high_manifest.get('rows_passing_base_criteria', 'unknown')} base rows passed; "
                f"{high_manifest.get('rows_still_passing_under_25bps_stress', 'unknown')} survived 25 bps stress; "
                f"{high_manifest.get('rows_remain_interesting_after_robustness', 'unknown')} remained interesting after robustness"
            ),
            "methodology_corrections": "post stale-weight/exposure corrections; pre-fix stale-weight results not used",
            "exact_variants_already_tested": "six original-threshold volatility-throttle high-return tactical rows",
            "exact_failure_or_unresolved_reason": (
                "all six downgraded to context-only after rolling-window weakness; some subperiod/risk-budget concerns"
            ),
            "open_for_materially_distinct_source_backed_hypothesis": "yes_not_exact_volatility_throttle_or_threshold_tuning",
            "missing_evidence_before_new_preregistration": (
                "external source-backed hypothesis distinct from high-return tactical volatility throttle and explicit "
                "rule set before any new bounded design"
            ),
            "latest_evidence_path": "evidence/research_recovery/high_return_tactical_etf_equity_index_bounded_robustness/latest",
            "outputs_non_promotable": True,
        },
        {
            "family_id": "macro_gld_duration_risk_off",
            "current_status": "diagnostic_confirmation_only_returned_to_queue",
            "last_valid_result": (
                f"{macro_manifest.get('rows_confirmed', 'unknown')} confirmed rows; "
                f"{macro_manifest.get('rows_passing_25bps_stress', 'unknown')} survived 25 bps stress; "
                f"{macro_manifest.get('rows_appear_diversifying_vs_active_combo', 'unknown')} appeared diversifying versus active combo"
            ),
            "methodology_corrections": "bounded run, robustness, and confirmation packets used local cache and invariant checks",
            "exact_variants_already_tested": "four robustness-surviving macro/GLD duration risk-off confirmation rows",
            "exact_failure_or_unresolved_reason": (
                "confirmation evidence usable but diagnostic only; no output promotable, candidate_exhaustive-ready, "
                "or paper-forward eligible"
            ),
            "open_for_materially_distinct_source_backed_hypothesis": "yes_but_do_not_retest_confirmed_survivor_rows_as_promotion",
            "missing_evidence_before_new_preregistration": (
                "direction-owner selected materially distinct external source/rule if macro family is revisited; no exact survivor promotion"
            ),
            "latest_evidence_path": "evidence/research_recovery/macro_gld_duration_risk_off_confirmation_report/latest",
            "outputs_non_promotable": True,
        },
    ]


def build_next_options() -> list[dict[str, Any]]:
    return [
        {
            "option_rank": 1,
            "case_type": "case_a_existing_backlog_candidate",
            "family": "low_volatility_factor_proxy",
            "existing_source_id": "low_volatility_factor_proxy",
            "why_it_adds_genuine_coverage": (
                "uses low-volatility ETF wrapper exposure rather than another SPY/BIL oscillator, calendar, or trend timing row"
            ),
            "closest_prior_project_test": "active VM low-vol/quality proxy and volatility-managed equity context",
            "material_difference_from_prior_test": (
                "would need a public-source factor-proxy rule rather than the existing active VM frozen observation"
            ),
            "data_feasibility": "SPLV|USMV|SPY|BIL local cache available per batch intake table",
            "execution_feasibility": "long-only ETF wrapper likely bt-adapter compatible after rules are completed",
            "major_risk_or_expected_failure_mode": (
                "rule incompleteness and overlap with active VM/low-vol state; could become duplicate if source only says buy SPLV/USMV"
            ),
            "readiness_status": "needs_rule_completion",
            "exact_next_action_required_before_implementation": (
                "complete_source_backed_entry_exit_rebalance_definition_for_low_volatility_factor_proxy"
            ),
            "material_distinctness_score": 2,
            "rule_completeness_score": 0,
            "source_traceability_score": 2,
            "local_data_feasibility_score": 3,
            "execution_feasibility_score": 3,
            "duplicate_retest_risk_score": 1,
            "implementation_effort_score": 2,
            "family_coverage_value_score": 2,
            "approved": False,
        },
        {
            "option_rank": 2,
            "case_type": "case_b_source_research_gap",
            "family": "relative_value_or_spread_etf_pairs",
            "existing_source_id": "",
            "why_it_adds_genuine_coverage": (
                "relative-value/spread behavior is not represented by the six SPY/BIL public-source indicator lanes"
            ),
            "closest_prior_project_test": "portfolio combination and active combo comparator work",
            "material_difference_from_prior_test": (
                "would require a source-backed long-only ETF relative-value proxy, not a repackaged active combo or short spread"
            ),
            "data_feasibility": "unknown until a source defines ETF proxies; likely manageable if limited to cached ETFs",
            "execution_feasibility": "must remain long-only, no shorting, no leverage, no derivatives",
            "major_risk_or_expected_failure_mode": (
                "many true spread strategies require shorting or leverage, which would violate project constraints"
            ),
            "readiness_status": "needs_source_research",
            "exact_next_action_required_before_implementation": (
                "find_or_reject_public_source_for_long_only_relative_value_etf_proxy"
            ),
            "material_distinctness_score": 3,
            "rule_completeness_score": 0,
            "source_traceability_score": 0,
            "local_data_feasibility_score": 1,
            "execution_feasibility_score": 1,
            "duplicate_retest_risk_score": 3,
            "implementation_effort_score": 1,
            "family_coverage_value_score": 3,
            "approved": False,
        },
        {
            "option_rank": 3,
            "case_type": "case_b_source_research_gap",
            "family": "risk_parity_inverse_volatility_or_vol_targeting",
            "existing_source_id": "",
            "why_it_adds_genuine_coverage": (
                "portfolio construction/risk allocation is underused relative to momentum, macro rotation, and SPY/BIL timing"
            ),
            "closest_prior_project_test": "static all-weather benchmark/control and active combo benchmark/reference",
            "material_difference_from_prior_test": (
                "would need a source-backed ETF risk-budget rule, not benchmark/control conversion or active-combo mutation"
            ),
            "data_feasibility": "likely feasible with cached ETF wrappers if a source defines instruments and cadence",
            "execution_feasibility": "must be unlevered long-only ETF weights with BIL/cash treatment explicit",
            "major_risk_or_expected_failure_mode": (
                "could duplicate static all-weather or require leverage/vol targeting beyond project constraints"
            ),
            "readiness_status": "needs_source_research",
            "exact_next_action_required_before_implementation": (
                "find_or_reject_public_source_for_unlevered_etf_inverse_volatility_or_risk_parity_rule"
            ),
            "material_distinctness_score": 3,
            "rule_completeness_score": 0,
            "source_traceability_score": 0,
            "local_data_feasibility_score": 2,
            "execution_feasibility_score": 2,
            "duplicate_retest_risk_score": 2,
            "implementation_effort_score": 2,
            "family_coverage_value_score": 3,
            "approved": False,
        },
    ]


def build_missing_source_questions(options: list[dict[str, Any]], external_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "family_or_source": "low_volatility_factor_proxy",
            "question": (
                "What public source gives complete ETF-wrapper entry, exit, rebalance cadence, and cash/benchmark semantics "
                "for SPLV or USMV without creating an active-VM duplicate?"
            ),
            "why_needed": "current intake has cached instruments but manual_input_required rule fields",
            "blocking_next_action": "complete_source_backed_rule_definition_before_design",
        },
        {
            "family_or_source": "relative_value_or_spread_etf_pairs",
            "question": (
                "Is there a public, no-short, no-leverage ETF relative-value proxy with explicit rules compatible with bt?"
            ),
            "why_needed": "family is underrepresented but many spread strategies violate shorting/leverage constraints",
            "blocking_next_action": "external_source_search_required_before_preregistration",
        },
        {
            "family_or_source": "risk_parity_inverse_volatility_or_vol_targeting",
            "question": (
                "Is there a public unlevered ETF inverse-volatility or risk-parity allocation rule that is not just static "
                "all-weather benchmark behavior?"
            ),
            "why_needed": "portfolio construction is underused but benchmark/control conversion is prohibited",
            "blocking_next_action": "external_source_search_required_before_preregistration",
        },
    ]
    for row in external_rows:
        if row["readiness_classification"] == "needs_rule_completion":
            rows.append(
                {
                    "family_or_source": row["source_id"],
                    "question": "Which exact source-backed rule field is still incomplete enough to block bounded design?",
                    "why_needed": row["notes"],
                    "blocking_next_action": "direction_owner_rule_completion_required",
                }
            )
    return rows


def write_markdown_reports(
    family_rows: list[dict[str, Any]],
    do_not_retest_rows: list[dict[str, Any]],
    external_rows: list[dict[str, Any]],
    prior_rows: list[dict[str, Any]],
    options: list[dict[str, Any]],
    missing_questions: list[dict[str, Any]],
) -> None:
    concentration = {}
    for row in family_rows:
        concentration[row["mechanism"]] = concentration.get(row["mechanism"], 0) + int(row["exact_variants_tested"])
    top_mechanisms = [
        item
        for item in sorted(concentration.items(), key=lambda item: (-item[1], item[0]))
        if item[0] != "unknown_or_mixed"
    ][:5]
    readiness_counts: dict[str, int] = {}
    for row in external_rows:
        readiness_counts[row["readiness_classification"]] = readiness_counts.get(row["readiness_classification"], 0) + 1

    summary = [
        "# Strategy Family Coverage and Next Discovery Readiness v1",
        "",
        "This packet is a focused evidence report. It did not run backtests, robustness checks, discovery, provider downloads, promotions, or paper/demo actions.",
        "",
        "## Main Concentration",
        "",
        "Current research remains concentrated in ETF timing/rotation and SPY/BIL single-asset indicator behavior. The most represented mechanisms by exact rows are:",
    ]
    for mechanism, count in top_mechanisms:
        summary.append(f"- `{mechanism}`: `{count}` mapped exact rows or lanes")
    summary.extend(
        [
            "",
            "## Six Exact Variants Closed For Immediate Retesting",
            "",
        ]
    )
    for row in do_not_retest_rows:
        summary.append(f"- `{row['lane_id']}` / `{row['primary_variant_id']}`: {row['concise_failure_reason']}")
    summary.extend(
        [
            "",
            "## Prior Promising Families Preserved",
            "",
        ]
    )
    for row in prior_rows:
        summary.append(f"- `{row['family_id']}`: {row['current_status']}; {row['last_valid_result']}")
    summary.extend(
        [
            "",
            "## External Backlog Readiness Counts",
            "",
        ]
    )
    for label, count in sorted(readiness_counts.items()):
        summary.append(f"- `{label}`: `{count}`")
    summary.extend(
        [
            "",
            "## Underrepresented Mechanisms",
            "",
            "- `relative_value_or_spread_approaches`: no current complete source-backed bounded lane.",
            "- `risk_parity_inverse_volatility_or_vol_targeting`: benchmark/control context exists, but no source-backed discovery lane.",
            "- `low_volatility_factor_proxy`: cached instruments exist, but source-backed rule definitions are incomplete and overlap active VM context.",
            "",
            f"Exact next action: `{NEXT_ACTION}`",
        ]
    )
    write_text(OUTPUT_DIR / "family_coverage_summary.md", "\n".join(summary))

    option_md = [
        "# Next Discovery Options",
        "",
        "These are readiness options, not approved selections. No option is promoted, paper-forward eligible, or authorized for implementation from this packet.",
        "",
    ]
    for row in options:
        option_md.extend(
            [
                f"## Option {row['option_rank']}: `{row['family']}`",
                "",
                f"- Case: `{row['case_type']}`",
                f"- Existing source ID: `{row['existing_source_id'] or 'none_currently_sufficient'}`",
                f"- Coverage value: {row['why_it_adds_genuine_coverage']}",
                f"- Closest prior project test: {row['closest_prior_project_test']}",
                f"- Material difference: {row['material_difference_from_prior_test']}",
                f"- Readiness: `{row['readiness_status']}`",
                f"- Required next action before implementation: `{row['exact_next_action_required_before_implementation']}`",
                "- Approved: `false`",
                "",
            ]
        )
    write_text(OUTPUT_DIR / "next_discovery_options.md", "\n".join(option_md))


def run() -> dict[str, Any]:
    lane_rows = read_csv_rows(SCREENING_DIR / "lane_metrics.csv")
    backlog_rows = read_csv_rows(SEL_DIR / "external_public_source_backlog.csv")
    eligibility_rows = read_csv_rows(BATCH_INTAKE_DIR / "eligibility_decisions.csv")
    cache_rows = read_csv_rows(BATCH_INTAKE_DIR / "local_cache_availability_table.csv")
    inventory_rows = read_csv_rows(SEL_DIR / "strategy_inventory.csv")
    sel_family_rows = read_csv_rows(SEL_DIR / "family_coverage.csv")
    ledger = read_yaml(FAMILY_LEDGER)
    screening_manifest = read_json(SCREENING_DIR / "screening_manifest.json")
    checkpoint_manifest = read_json(CHECKPOINT_DIR / "current_research_checkpoint_manifest.json")

    closed_source_ids = {row["source_id"] for row in lane_rows if row["lane_id"] in SIX_SCREENED_LANES}
    exact_memory = build_exact_variant_memory(lane_rows)
    external_readiness = build_external_readiness(backlog_rows, eligibility_rows, cache_rows, closed_source_ids)
    family_rows = build_family_coverage(inventory_rows, sel_family_rows, lane_rows, external_readiness, ledger)
    mechanism_rows = build_mechanism_concentration(family_rows)
    prior_rows = build_prior_promising_status()
    options = build_next_options()
    missing_questions = build_missing_source_questions(options, external_readiness)

    write_csv(
        OUTPUT_DIR / "family_coverage_matrix.csv",
        family_rows,
        [
            "family_id",
            "mechanism",
            "instruments_universe",
            "timeframe",
            "exact_variants_tested",
            "rejected_count",
            "blocked_count",
            "unresolved_count",
            "active_or_eligible_count",
            "external_backlog_source_count",
            "most_recent_valid_evidence",
            "primary_repeated_failure_pattern",
            "coverage_status",
            "likely_next_test_character",
            "notes",
        ],
    )
    write_csv(
        OUTPUT_DIR / "tested_mechanism_concentration.csv",
        mechanism_rows,
        [
            "mechanism",
            "family_count",
            "tested_variant_count",
            "screened_lane_count",
            "external_source_candidate_count",
            "representative_families",
            "concentration_assessment",
        ],
    )
    write_csv(
        OUTPUT_DIR / "exact_variant_do_not_retest.csv",
        exact_memory,
        [
            "lane_id",
            "primary_variant_id",
            "family_id",
            "batch_id",
            "screening_outcome",
            "concise_failure_reason",
            "ready_for_immediate_retest",
            "family_remains_open",
            "future_family_level_conditions",
            "evidence_path",
        ],
    )
    write_csv(
        OUTPUT_DIR / "external_source_readiness.csv",
        external_readiness,
        [
            "source_id",
            "source_class",
            "source_name",
            "linked_family",
            "rule_completeness",
            "source_citation_provenance_completeness",
            "required_instruments",
            "required_data",
            "local_cache_feasibility",
            "execution_feasibility",
            "similar_project_strategies",
            "duplicate_or_overlap_risk",
            "existing_local_implementation",
            "existing_exact_test_or_rejection",
            "readiness_classification",
            "notes",
        ],
    )
    write_csv(
        OUTPUT_DIR / "prior_promising_family_status.csv",
        prior_rows,
        [
            "family_id",
            "current_status",
            "last_valid_result",
            "methodology_corrections",
            "exact_variants_already_tested",
            "exact_failure_or_unresolved_reason",
            "open_for_materially_distinct_source_backed_hypothesis",
            "missing_evidence_before_new_preregistration",
            "latest_evidence_path",
            "outputs_non_promotable",
        ],
    )
    write_csv(
        OUTPUT_DIR / "next_discovery_options.csv",
        options,
        [
            "option_rank",
            "case_type",
            "family",
            "existing_source_id",
            "why_it_adds_genuine_coverage",
            "closest_prior_project_test",
            "material_difference_from_prior_test",
            "data_feasibility",
            "execution_feasibility",
            "major_risk_or_expected_failure_mode",
            "readiness_status",
            "exact_next_action_required_before_implementation",
            "material_distinctness_score",
            "rule_completeness_score",
            "source_traceability_score",
            "local_data_feasibility_score",
            "execution_feasibility_score",
            "duplicate_retest_risk_score",
            "implementation_effort_score",
            "family_coverage_value_score",
            "approved",
        ],
    )
    write_csv(
        OUTPUT_DIR / "missing_source_research_questions.csv",
        missing_questions,
        ["family_or_source", "question", "why_needed", "blocking_next_action"],
    )
    write_markdown_reports(family_rows, exact_memory, external_readiness, prior_rows, options, missing_questions)

    consistency = {
        "report_only": True,
        "batch_id_reviewed": BATCH_ID,
        "screened_lane_ids_in_memory": sorted(row["lane_id"] for row in exact_memory) == sorted(SIX_SCREENED_LANES),
        "none_of_six_ready_for_immediate_retesting": all(
            row["ready_for_immediate_retest"] is False for row in exact_memory
        ),
        "coppock_identified_as_sampled_benchmark_like": any(
            row["lane_id"] == "public_source_coppock_curve_bounded_bt_lane_v1"
            and "benchmark-like" in row["concise_failure_reason"]
            for row in exact_memory
        ),
        "percent_b_not_advanced_to_robustness": any(
            row["lane_id"] == "public_source_percent_b_money_flow_bounded_bt_lane_v1"
            and "no robustness review authorized" in row["concise_failure_reason"]
            for row in exact_memory
        ),
        "internal_generated_sel_sources_excluded_from_external_candidates": all(
            not row["source_class"].startswith("internal") and row["source_class"] != "project_generated"
            for row in external_readiness
        ),
        "exact_rejected_variants_reopened": False,
        "active_vm_dsr_lifecycle_unchanged": True,
        "active_combo_reference_only": screening_manifest.get("active_combo_role") == "benchmark_reference_only"
        and screening_manifest.get("active_combo_status") == "benchmark_watchlist_reference"
        and checkpoint_manifest.get("active_combo_available") is True,
        "high_return_tactical_included": any(
            row["family_id"] == "high_return_tactical_etf_equity_index" for row in prior_rows
        ),
        "macro_gld_included": any(row["family_id"] == "macro_gld_duration_risk_off" for row in prior_rows),
        "next_discovery_option_count": len(options),
        "next_discovery_option_count_lte_3": len(options) <= 3,
        "no_option_approved": all(row["approved"] is False for row in options),
        "no_backtests_run": True,
        "no_provider_download": True,
        "no_robustness_run": True,
        "no_strategy_implementation": True,
        "no_strategy_lifecycle_status_changed": True,
        "no_paper_demo_state_changed": True,
        "active_combo_changed": False,
        "deterministic_input_hash": stable_hash(
            {
                "lane_rows": lane_rows,
                "backlog_rows": backlog_rows,
                "eligibility_rows": eligibility_rows,
                "checkpoint_active_combo": checkpoint_manifest.get("active_combo_available"),
            }
        ),
        "created_utc": now_utc(),
        "next_action": NEXT_ACTION,
    }
    required_true = {
        "report_only",
        "screened_lane_ids_in_memory",
        "none_of_six_ready_for_immediate_retesting",
        "coppock_identified_as_sampled_benchmark_like",
        "percent_b_not_advanced_to_robustness",
        "internal_generated_sel_sources_excluded_from_external_candidates",
        "active_vm_dsr_lifecycle_unchanged",
        "active_combo_reference_only",
        "high_return_tactical_included",
        "macro_gld_included",
        "next_discovery_option_count_lte_3",
        "no_option_approved",
        "no_backtests_run",
        "no_provider_download",
        "no_robustness_run",
        "no_strategy_implementation",
        "no_strategy_lifecycle_status_changed",
        "no_paper_demo_state_changed",
    }
    required_false = {
        "exact_rejected_variants_reopened",
        "active_combo_changed",
    }
    consistency["consistency_passed"] = all(consistency[key] is True for key in required_true) and all(
        consistency[key] is False for key in required_false
    )
    write_json(OUTPUT_DIR / "coverage_consistency_check.json", consistency)

    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "batch_id_reviewed": BATCH_ID,
        "family_count": len(family_rows),
        "external_source_readiness_count": len(external_readiness),
        "do_not_retest_count": len(exact_memory),
        "next_discovery_option_count": len(options),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
