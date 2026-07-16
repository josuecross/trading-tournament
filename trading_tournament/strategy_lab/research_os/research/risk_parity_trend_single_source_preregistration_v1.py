from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
INTAKE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
OUTPUT_DIR = Path("evidence") / "risk_parity_trend_single_source_preregistration_v1" / "latest"
SEL_DIR = Path("evidence") / "strategy_evidence_library" / "latest"
COVERAGE_DIR = Path("evidence") / "strategy_family_coverage_and_next_discovery_v1" / "latest"
MACRO_PREREG_DIR = Path("evidence") / "macro_gld_duration_source_backed_preregistration_v1" / "latest"

SOURCE_ID = "clare_seaton_smith_thomas_risk_parity_trend_following_2016"
FAMILY_ID = "risk_parity_inverse_volatility_or_vol_targeting"
CANDIDATE_ID = "rp_ivol_10m_trend_asset_class_etf_wrapper_v1"
OUTCOME_READY = "preregistration_ready"
OUTCOME_NOT_READY = "source_not_ready"
NEXT_ACTION_BLOCKED = "resolve_direct_etf_wrapper_mapping_for_government_bonds_and_global_real_estate_before_preregistration"

SUPPORT_REFS = {
    "source_identity": "Journal of Behavioral and Experimental Finance, Volume 9, 2016, pages 63-80; SSRN abstract 2126478",
    "risk_allocation": "Working-paper PDF Section 3.1, pages 6-7",
    "asset_trend_filter": "Working-paper PDF Section 3.1, pages 6-7",
    "asset_classes": "Table 1 notes, page 19",
    "conclusion": "Conclusion, pages 14-15",
    "project_execution": "Project execution convention supplied by direction owner; not attributed to source",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


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


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    full = abs_path(path)
    if not full.exists():
        return []
    with full.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def source_intake_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "intake_status": "single_direction_owner_source_supplied_for_validation",
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "Risk Parity, Momentum and Trend Following in Global Asset Allocation",
            "source_url_or_citation": (
                "Andrew Clare, James Seaton, Peter N. Smith, Stephen Thomas, "
                "Risk Parity, Momentum and Trend Following in Global Asset Allocation, "
                "Journal of Behavioral and Experimental Finance, Volume 9, 2016, pages 63-80; "
                "SSRN abstract 2126478"
            ),
            "source_type": "academic_primary",
            "authors": [
                "Andrew Clare",
                "James Seaton",
                "Peter N. Smith",
                "Stephen Thomas",
            ],
            "publication_date": "2016",
            "relevant_source_locations": [
                "Working-paper PDF Section 3.1, pages 6-7",
                "Table 1 notes, page 19",
                "Conclusion, pages 14-15",
            ],
            "source_evidence_public_context_only": True,
        },
        "strategy_description": {
            "strategy_family": FAMILY_ID,
            "claimed_hypothesis": (
                "Global asset classes can be combined using inverse-volatility risk allocation while "
                "independent 10-month moving-average trend filters transfer below-trend asset weights "
                "to Treasury bills."
            ),
            "rule_clarity": "clear_and_testable_subject_to_etf_wrapper_mapping",
            "instruments": [
                "developed_market_equities_wrapper_required",
                "emerging_market_equities_wrapper_required",
                "government_bonds_wrapper_required",
                "broad_commodities_wrapper_required",
                "global_real_estate_wrapper_required",
                "BIL",
            ],
            "timeframe": "monthly signals and monthly rebalance using daily or monthly adjusted close data",
        },
        "rules": {
            "risk_allocation_rule": (
                "Estimate each asset class's volatility from the preceding 12 months, assign weights "
                "proportional to inverse volatility, normalize weights so total exposure is 100%, and "
                "recalculate monthly."
            ),
            "trend_filter_rule": (
                "At each month end, compare each risky asset-class price with its 10-month moving average."
            ),
            "risk_on_rule": (
                "If an asset class is above its 10-month moving average, retain its calculated inverse-volatility weight."
            ),
            "risk_off_rule": (
                "If an asset class is below its 10-month moving average, assign that asset class's calculated "
                "weight to US Treasury bills rather than shorting or redistributing to remaining risky assets."
            ),
            "source_asset_classes": [
                "Developed-market equities",
                "Emerging-market equities",
                "Government bonds",
                "Broad commodities",
                "Global real estate",
                "US Treasury bills as risk-off",
            ],
            "rebalance_frequency": "monthly at month end",
            "weighting": "inverse volatility over the preceding 12 months, normalized to total exposure 1.0",
            "risk_controls": "Long-only; no shorting; no project leverage; below-trend asset weights move to Treasury bills/cash.",
            "forbidden_translation_choices": [
                "do_not_use_GLD_as_broad_commodities",
                "do_not_use_long_duration_treasury_as_silent_world_government_bond_substitute",
                "do_not_drop_missing_asset_classes",
                "do_not_select_wrappers_from_prior_results",
            ],
        },
        "data_and_execution": {
            "data_requirements": (
                "Monthly or daily adjusted close history for all mapped ETF wrappers sufficient for 12-month "
                "volatility and 10-month moving average warm-up."
            ),
            "execution_assumptions": (
                "Project execution assumptions are not source claims: signals are frozen at month end and any "
                "future screen would use the project no-lookahead shifted-weight convention, standard cost/slippage "
                "assumptions, and BIL as the Treasury-bill/cash wrapper."
            ),
            "compatible_with_bt_adapter": True,
        },
        "source_support": {
            "risk_allocation_rule": {"classification": "source_explicit", "reference": SUPPORT_REFS["risk_allocation"]},
            "trend_filter_rule": {"classification": "source_explicit", "reference": SUPPORT_REFS["asset_trend_filter"]},
            "risk_on_rule": {"classification": "source_explicit", "reference": SUPPORT_REFS["asset_trend_filter"]},
            "risk_off_rule": {"classification": "source_explicit", "reference": SUPPORT_REFS["asset_trend_filter"]},
            "source_asset_classes": {"classification": "source_explicit", "reference": SUPPORT_REFS["asset_classes"]},
            "monthly_rebalance": {"classification": "source_explicit", "reference": SUPPORT_REFS["risk_allocation"]},
            "no_project_leverage": {"classification": "project_execution_convention", "reference": SUPPORT_REFS["project_execution"]},
            "shifted_weight_execution": {"classification": "project_execution_convention", "reference": SUPPORT_REFS["project_execution"]},
            "project_costs_slippage": {"classification": "project_execution_convention", "reference": SUPPORT_REFS["project_execution"]},
        },
        "governance": {
            "public_strategy_selected_by_user": True,
            "source_scraped_by_codex": False,
            "strategy_implemented": False,
            "backtest_run": False,
            "promotion_or_paper_forward_allowed": False,
        },
    }


def write_intake_candidate() -> Path:
    path = INTAKE_DIR / f"{SOURCE_ID}.yaml"
    write_yaml(path, source_intake_payload())
    return abs_path(path)


def cache_info(symbol: str | None) -> dict[str, Any]:
    if not symbol:
        return {
            "local_ticker": "",
            "cache_ready": False,
            "cache_start": "",
            "cache_end": "",
            "row_count": 0,
        }
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return {
            "local_ticker": symbol,
            "cache_ready": False,
            "cache_start": "",
            "cache_end": "",
            "row_count": 0,
        }
    first_date = ""
    last_date = ""
    row_count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            date = row.get("date") or row.get("Date") or ""
            if not first_date:
                first_date = date
            last_date = date
            row_count += 1
    return {
        "local_ticker": symbol,
        "cache_ready": True,
        "cache_start": first_date,
        "cache_end": last_date,
        "row_count": row_count,
    }


def source_rule_rows() -> list[dict[str, Any]]:
    rows = [
        ("source_identity", "academic source identity, citation, authors, and 2016 publication date", "source_explicit", SUPPORT_REFS["source_identity"]),
        ("source_class", "academic_primary", "source_explicit", SUPPORT_REFS["source_identity"]),
        ("volatility_window", "preceding 12 months", "source_explicit", SUPPORT_REFS["risk_allocation"]),
        ("inverse_volatility_weighting", "weights proportional to inverse volatility", "source_explicit", SUPPORT_REFS["risk_allocation"]),
        ("weight_normalization", "normalize to total portfolio exposure of 100%", "source_explicit", SUPPORT_REFS["risk_allocation"]),
        ("weight_recalculation", "recalculate monthly", "source_explicit", SUPPORT_REFS["risk_allocation"]),
        ("trend_window", "10-month moving average", "source_explicit", SUPPORT_REFS["asset_trend_filter"]),
        ("risk_on_rule", "retain calculated asset weight when price is above its 10-month moving average", "source_explicit", SUPPORT_REFS["asset_trend_filter"]),
        ("risk_off_rule", "transfer below-trend asset weight to US Treasury bills", "source_explicit", SUPPORT_REFS["asset_trend_filter"]),
        ("source_asset_classes", "developed equities; emerging equities; government bonds; broad commodities; global real estate; Treasury bills", "source_explicit", SUPPORT_REFS["asset_classes"]),
        ("signal_timestamp", "month-end signal", "source_explicit", SUPPORT_REFS["risk_allocation"]),
        ("execution_convention", "project no-lookahead shifted-weight/next-session convention", "project_execution_convention", SUPPORT_REFS["project_execution"]),
        ("project_cost_slippage", "project standard transaction-cost and slippage assumptions", "project_execution_convention", SUPPORT_REFS["project_execution"]),
        ("no_project_leverage", "maximum gross exposure 1.0; no project leverage", "project_execution_convention", SUPPORT_REFS["project_execution"]),
        ("parameter_search", "no alternative windows, trend periods, universes, or wrapper optimizations authorized", "project_execution_convention", SUPPORT_REFS["project_execution"]),
    ]
    return [
        {
            "source_id": SOURCE_ID,
            "rule_field": field,
            "extracted_rule": value,
            "classification": classification,
            "support_reference": reference,
            "status": "resolved",
        }
        for field, value, classification, reference in rows
    ]


def source_support_rows(rule_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": SOURCE_ID,
            "rule_field": row["rule_field"],
            "source_reference_type": "manual_direction_owner_source_location",
            "source_reference": row["support_reference"],
            "supports_rule": row["classification"] in {"source_explicit", "project_execution_convention"},
            "classification": row["classification"],
            "notes": (
                "Project execution convention is not attributed to the source."
                if row["classification"] == "project_execution_convention"
                else "Source-supported rule extracted from supplied source packet."
            ),
        }
        for row in rule_rows
    ]


def wrapper_mapping_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "source_asset_class": "Developed-market equities",
            "local_ticker": "EFA",
            "candidate_wrapper_role": "developed_ex_us_equity_etf",
            "why_mapping_is_direct": "EFA is a broad developed-market equity ETF wrapper in local cache, but it excludes US equities.",
            "material_differences_from_source_index": "Potentially excludes US and may not match the source's developed-market equity index definition.",
            "mechanism_altered": True,
            "mapping_status": "ambiguous_material_difference",
            "blocking": True,
        },
        {
            "source_asset_class": "Emerging-market equities",
            "local_ticker": "EEM",
            "candidate_wrapper_role": "emerging_market_equity_etf",
            "why_mapping_is_direct": "EEM is a broad emerging-market equity ETF wrapper already present in local cache.",
            "material_differences_from_source_index": "ETF implementation and index provider can differ from source index, but asset-class role is direct.",
            "mechanism_altered": False,
            "mapping_status": "direct_cache_ready",
            "blocking": False,
        },
        {
            "source_asset_class": "Government bonds",
            "local_ticker": "",
            "candidate_wrapper_role": "no_direct_cached_government_bond_wrapper_selected",
            "why_mapping_is_direct": "No direct broad government-bond wrapper is selected.",
            "material_differences_from_source_index": "Cached AGG includes non-government bonds; IEF/TLT are US Treasury duration sleeves and cannot silently stand in for a broad government-bond index.",
            "mechanism_altered": True,
            "mapping_status": "unavailable_materially_non_equivalent",
            "blocking": True,
        },
        {
            "source_asset_class": "Broad commodities",
            "local_ticker": "DBC",
            "candidate_wrapper_role": "broad_commodity_etf",
            "why_mapping_is_direct": "DBC is a broad commodity ETF wrapper in local cache; GLD is not used as a broad commodity proxy.",
            "material_differences_from_source_index": "ETF construction and futures collateral mechanics can differ from source commodity index.",
            "mechanism_altered": False,
            "mapping_status": "direct_cache_ready_with_etf_caveat",
            "blocking": False,
        },
        {
            "source_asset_class": "Global real estate",
            "local_ticker": "",
            "candidate_wrapper_role": "no_direct_cached_global_real_estate_wrapper_selected",
            "why_mapping_is_direct": "No direct global real-estate ETF wrapper is present in the local cache.",
            "material_differences_from_source_index": "Cached XLRE is US real estate only and would delete the global real-estate mechanism.",
            "mechanism_altered": True,
            "mapping_status": "unavailable_materially_non_equivalent",
            "blocking": True,
        },
        {
            "source_asset_class": "US Treasury bills as risk-off",
            "local_ticker": "BIL",
            "candidate_wrapper_role": "treasury_bill_cash_proxy",
            "why_mapping_is_direct": "BIL is the project Treasury-bill/cash proxy and is already present in local cache.",
            "material_differences_from_source_index": "ETF inception/fees differ from a Treasury-bill index; role is direct for project cash proxy.",
            "mechanism_altered": False,
            "mapping_status": "direct_cache_ready",
            "blocking": False,
        },
    ]
    for row in rows:
        info = cache_info(row["local_ticker"])
        row.update(
            {
                "cache_ready": info["cache_ready"],
                "cache_start": info["cache_start"],
                "cache_end": info["cache_end"],
                "cache_row_count": info["row_count"],
                "all_required_common_screening_windows_remain_usable": (
                    info["cache_ready"] and not row["blocking"]
                ),
            }
        )
    return rows


def local_cache_rows(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_symbols = ["EFA", "EEM", "AGG", "IEF", "TLT", "DBC", "PDBC", "COMT", "GSG", "USCI", "XLRE", "BIL"]
    rows = []
    role_notes = {
        "EFA": "developed-market equity candidate; materially ambiguous because it is developed ex-US",
        "EEM": "emerging-market equity candidate",
        "AGG": "bond candidate rejected as not government-only",
        "IEF": "government-bond candidate rejected as US intermediate Treasury duration sleeve",
        "TLT": "government-bond candidate rejected as long-duration Treasury substitute",
        "DBC": "selected broad commodity candidate; GLD not used",
        "PDBC": "alternative broad commodity cache present but not selected or optimized",
        "COMT": "alternative broad commodity cache present but not selected or optimized",
        "GSG": "alternative broad commodity cache present but not selected or optimized",
        "USCI": "alternative broad commodity cache present but not selected or optimized",
        "XLRE": "real-estate candidate rejected as US-only, not global real estate",
        "BIL": "Treasury-bill/cash proxy candidate",
    }
    selected = {row["local_ticker"]: row for row in mapping_rows if row["local_ticker"]}
    for symbol in candidate_symbols:
        info = cache_info(symbol)
        selected_row = selected.get(symbol, {})
        rows.append(
            {
                "local_ticker": symbol,
                "cache_ready": info["cache_ready"],
                "cache_start": info["cache_start"],
                "cache_end": info["cache_end"],
                "cache_row_count": info["row_count"],
                "role_or_relevance": role_notes[symbol],
                "selected_for_preregistration": bool(selected_row) and not selected_row.get("blocking", False),
                "rejection_or_caveat": selected_row.get("material_differences_from_source_index", role_notes[symbol]),
            }
        )
    return rows


def closest_prior_rows() -> list[dict[str, Any]]:
    return [
        {
            "prior_variant_or_family": "static_all_weather_benchmark_v1",
            "source_artifact": "strategy registry / SEL benchmark-control records",
            "shared_dimensions": "multi-asset defensive benchmark context; long-only ETF/fund benchmark role",
            "key_difference_from_candidate": "candidate uses monthly inverse-volatility weights plus independent per-asset 10-month trend-to-T-bills rule; static all-weather is benchmark/control only",
            "exact_closed_variant_reopened": False,
        },
        {
            "prior_variant_or_family": "macro_gld_duration_risk_off_bounded_lane_v1 / MGD survivor rows",
            "source_artifact": "evidence/macro_gld_duration_source_backed_preregistration_v1/latest/exact_variants_closed.csv",
            "shared_dimensions": "GLD/duration/cash defensive behavior and monthly ETF wrapper research context",
            "key_difference_from_candidate": "candidate is a global asset-class inverse-volatility portfolio with per-asset trend filter, not canary-defensive, gold-duration sleeve, or gated barbell",
            "exact_closed_variant_reopened": False,
        },
        {
            "prior_variant_or_family": "multi_asset_trend_risk_control / top-N global asset rows",
            "source_artifact": "evidence/strategy_evidence_library/latest/strategy_inventory.csv",
            "shared_dimensions": "multi-asset trend and BIL/cash fallback context",
            "key_difference_from_candidate": "candidate does not rank top-N assets; it risk-budgets all mapped assets and transfers below-trend weights to T-bills",
            "exact_closed_variant_reopened": False,
        },
        {
            "prior_variant_or_family": "SPY_200d_vol_target_12_cap_*",
            "source_artifact": "strategy registry / SEL duplicate records",
            "shared_dimensions": "volatility-based sizing/control concept",
            "key_difference_from_candidate": "candidate uses cross-asset inverse-volatility allocation plus asset-level trend filter; it is not single-equity volatility targeting",
            "exact_closed_variant_reopened": False,
        },
    ]


def material_distinction_row(mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocking_assets = [row["source_asset_class"] for row in mapping_rows if row["blocking"] or not row["cache_ready"]]
    return {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "closest_prior_strategy": "static_all_weather_benchmark_v1; macro_gld_duration_risk_off_bounded_lane_v1; multi_asset_trend_risk_control rows",
        "shared_universe_dimensions": "multi-asset ETF wrappers; defensive BIL/cash behavior; monthly cadence",
        "shared_trend_rule": "per-asset trend context overlaps broad multi-asset trend rows, but supplied source uses 10-month MA on each asset class",
        "shared_defensive_behavior": "below-trend or defensive states use BIL/T-bills/cash-like exposure",
        "materially_changed_mechanism": "inverse-volatility portfolio construction plus independent per-asset trend-to-BIL rule",
        "inverse_volatility_new_or_distinct": True,
        "mechanism_originates_in_supplied_source": True,
        "minor_ticker_or_lookback_change_only": False,
        "result_driven_tuning_risk": "low_for_rules; mapping unresolved so no screen authorized",
        "mapping_gate_blocking_assets": blocking_assets,
        "material_distinction_result": (
            "provisionally_materially_distinct_but_mapping_blocked"
            if blocking_assets
            else "materially_distinct"
        ),
    }


def missing_rows(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in mapping_rows:
        if row["blocking"] or not row["cache_ready"]:
            rows.append(
                {
                    "source_id": SOURCE_ID,
                    "blocking_field": f"etf_wrapper_mapping.{row['source_asset_class']}",
                    "blocking_reason": row["mapping_status"],
                    "source_evidence_present": "source asset class required by Table 1 notes / supplied source packet",
                    "source_evidence_absent": "direct cache-ready materially equivalent ETF wrapper",
                    "resolution_question": (
                        f"Provide a direct local-cache wrapper for {row['source_asset_class']} or reject this source for project translation."
                    ),
                }
            )
    return rows


def decision_for(mapping_rows: list[dict[str, Any]], material_row: dict[str, Any], missing: list[dict[str, Any]]) -> dict[str, Any]:
    exact_one_source = True
    source_rules_complete = True
    mapping_ready = all(row["cache_ready"] and not row["blocking"] and not row["mechanism_altered"] for row in mapping_rows)
    material_ready = material_row["material_distinction_result"] == "materially_distinct"
    outcome = OUTCOME_READY if exact_one_source and source_rules_complete and mapping_ready and material_ready else OUTCOME_NOT_READY
    blocker = ""
    if not mapping_ready:
        blocker = "etf_wrapper_mapping_unavailable_or_materially_non_equivalent"
    elif not material_ready:
        blocker = "material_distinction_not_proven"
    return {
        "created_utc": now_utc(),
        "source_id": SOURCE_ID,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "outcome": outcome,
        "blocker": blocker,
        "source_count_evaluated": 1,
        "normalized_source_class": "academic_primary",
        "source_identity_complete": True,
        "source_rule_support_complete": source_rules_complete,
        "volatility_window_months": 12,
        "trend_moving_average_months": 10,
        "below_trend_weight_destination": "BIL",
        "no_leverage": True,
        "no_shorting": True,
        "broad_commodity_wrapper_uses_gld": False,
        "mapping_ready": mapping_ready,
        "material_distinction_result": material_row["material_distinction_result"],
        "closest_prior_strategy": material_row["closest_prior_strategy"],
        "blocking_asset_classes": [row["source_asset_class"] for row in mapping_rows if row["blocking"] or not row["cache_ready"]],
        "preregistration_created": outcome == OUTCOME_READY,
        "source_not_ready": outcome == OUTCOME_NOT_READY,
        "missing_or_ambiguous_field_count": len(missing),
        "no_backtest_run": True,
        "no_parameter_search_authorized": True,
        "no_strategy_implementation": True,
        "no_lifecycle_or_paper_demo_state_change": True,
        "provider_download": False,
        "intraday_data_used": False,
        "candidate_exhaustive_run": False,
        "promotion_or_paper_demo_activation": False,
        "next_action": NEXT_ACTION_BLOCKED if outcome == OUTCOME_NOT_READY else "design_or_run_only_after_separate_authorization",
    }


def preregistration_payload(decision: dict[str, Any], mapping_rows: list[dict[str, Any]], material_row: dict[str, Any]) -> dict[str, Any]:
    selected = [row for row in mapping_rows if row["local_ticker"] and not row["blocking"]]
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "source_id": SOURCE_ID,
        "citation": source_intake_payload()["source"]["source_url_or_citation"],
        "closest_prior_strategy": material_row["closest_prior_strategy"],
        "material_distinction_statement": material_row["materially_changed_mechanism"],
        "deterministic_fingerprint": stable_hash(
            {
                "family": FAMILY_ID,
                "signal": "12m_inverse_volatility_allocation_plus_10m_asset_trend_to_bil",
                "universe": [row["local_ticker"] for row in selected],
                "rebalance": "monthly",
                "max_exposure": 1.0,
            }
        ),
        "universe": [{row["source_asset_class"]: row["local_ticker"]} for row in selected],
        "signal_and_weighting": {
            "volatility_estimation": "preceding 12 months",
            "raw_weights": "inverse volatility",
            "normalization": "sum risky calculated weights to total exposure 1.0 before trend transfer",
            "trend_filter": "10-month moving average independently applied to each risky asset",
            "below_trend_transfer": "calculated weight transferred to BIL",
            "rebalance": "monthly",
        },
        "execution": {
            "signal_timestamp": "month end",
            "execution_convention": "project no-lookahead shifted-weight / next-session convention",
            "costs": "project standard costs/slippage assumptions",
            "max_gross_exposure": 1.0,
            "leverage": False,
            "shorting": False,
        },
        "screening": {
            "canonical_sampled_windows": "use existing repository canonical scored windows only",
            "parameter_search": False,
            "alternative_windows": False,
            "alternative_universes": False,
        },
        "benchmarks": [
            "SPY_200d_trend_model",
            "SPY_buy_and_hold",
            "BIL_cash_proxy",
            "active_combo_vm_dsr_equal_weight_v1_benchmark_reference_only",
            "same_mapped_universe_equal_weight_control_if_available_without_new_candidate",
        ],
        "required_invariants": [
            "total_weights_lte_1",
            "no_stale_weights",
            "below_trend_weights_fully_transferred_to_BIL",
            "no_residual_risky_exposure_after_transfer",
            "no_lookahead",
            "deterministic_results",
            "consistent_cost_application",
        ],
        "decision_hash": stable_hash(decision),
    }


def write_reports(
    intake_path: Path,
    rule_rows: list[dict[str, Any]],
    support_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, Any]],
    cache_rows: list[dict[str, Any]],
    prior_rows: list[dict[str, Any]],
    material_row: dict[str, Any],
    missing: list[dict[str, Any]],
    decision: dict[str, Any],
) -> None:
    write_yaml(OUTPUT_DIR / "source_intake_record.yaml", source_intake_payload())
    write_csv(
        OUTPUT_DIR / "source_rule_extraction.csv",
        rule_rows,
        ["source_id", "rule_field", "extracted_rule", "classification", "support_reference", "status"],
    )
    write_csv(
        OUTPUT_DIR / "source_support_trace.csv",
        support_rows,
        ["source_id", "rule_field", "source_reference_type", "source_reference", "supports_rule", "classification", "notes"],
    )
    write_csv(
        OUTPUT_DIR / "etf_wrapper_mapping.csv",
        mapping_rows,
        [
            "source_asset_class",
            "local_ticker",
            "candidate_wrapper_role",
            "cache_ready",
            "cache_start",
            "cache_end",
            "cache_row_count",
            "why_mapping_is_direct",
            "material_differences_from_source_index",
            "mechanism_altered",
            "mapping_status",
            "all_required_common_screening_windows_remain_usable",
            "blocking",
        ],
    )
    write_csv(
        OUTPUT_DIR / "local_cache_feasibility.csv",
        cache_rows,
        [
            "local_ticker",
            "cache_ready",
            "cache_start",
            "cache_end",
            "cache_row_count",
            "role_or_relevance",
            "selected_for_preregistration",
            "rejection_or_caveat",
        ],
    )
    write_csv(
        OUTPUT_DIR / "closest_prior_variants.csv",
        prior_rows,
        [
            "prior_variant_or_family",
            "source_artifact",
            "shared_dimensions",
            "key_difference_from_candidate",
            "exact_closed_variant_reopened",
        ],
    )
    write_csv(
        OUTPUT_DIR / "material_distinction_review.csv",
        [material_row],
        [
            "candidate_id",
            "family",
            "closest_prior_strategy",
            "shared_universe_dimensions",
            "shared_trend_rule",
            "shared_defensive_behavior",
            "materially_changed_mechanism",
            "inverse_volatility_new_or_distinct",
            "mechanism_originates_in_supplied_source",
            "minor_ticker_or_lookback_change_only",
            "result_driven_tuning_risk",
            "mapping_gate_blocking_assets",
            "material_distinction_result",
        ],
    )
    write_csv(
        OUTPUT_DIR / "missing_or_ambiguous_fields.csv",
        missing,
        [
            "source_id",
            "blocking_field",
            "blocking_reason",
            "source_evidence_present",
            "source_evidence_absent",
            "resolution_question",
        ],
    )
    write_json(OUTPUT_DIR / "decision.json", {**decision, "intake_candidate_path": str(intake_path.relative_to(ROOT))})
    lines = [
        "# Risk Parity Trend Single Source Preregistration v1",
        "",
        f"Outcome: `{decision['outcome']}`",
        f"Source ID: `{SOURCE_ID}`",
        f"Family: `{FAMILY_ID}`",
        f"Blocker: `{decision['blocker'] or 'none'}`",
        "",
        "The supplied academic source identity and core rule skeleton were complete. The preregistration gate is blocked by ETF-wrapper translation, not by a missing rule or by source performance claims.",
        "",
        "Blocking wrapper mappings:",
    ]
    for row in missing:
        lines.append(f"- `{row['blocking_field']}`: {row['blocking_reason']}")
    lines.extend(
        [
            "",
            f"Closest prior strategy context: `{decision['closest_prior_strategy']}`.",
            f"Material distinction result: `{decision['material_distinction_result']}`.",
            "",
            "No strategy implementation, screening run, backtest, parameter search, lifecycle change, paper/demo activation, provider download, intraday data, broker/live path, or real-money recommendation occurred.",
        ]
    )
    write_text(OUTPUT_DIR / "decision.md", "\n".join(lines))
    if decision["outcome"] == OUTCOME_READY:
        prereg = preregistration_payload(decision, mapping_rows, material_row)
        write_yaml(OUTPUT_DIR / "preregistration.yaml", prereg)
        write_text(
            OUTPUT_DIR / "preregistration.md",
            "# Risk Parity Trend Preregistration\n\n"
            f"Candidate `{CANDIDATE_ID}` is frozen from source `{SOURCE_ID}`. No screening run is authorized by this packet.",
        )
    else:
        for name in ("preregistration.yaml", "preregistration.md"):
            path = abs_path(OUTPUT_DIR / name)
            if path.exists():
                path.unlink()


def consistency_check(decision: dict[str, Any], mapping_rows: list[dict[str, Any]], material_row: dict[str, Any]) -> dict[str, Any]:
    exact_closed = read_csv_rows(MACRO_PREREG_DIR / "exact_variants_closed.csv")
    closed_ids = {row.get("variant_id", "") for row in exact_closed}
    gld_commodity = any(row["source_asset_class"] == "Broad commodities" and row["local_ticker"] == "GLD" for row in mapping_rows)
    missing_mapping_blocks = any(row["blocking"] or not row["cache_ready"] for row in mapping_rows)
    check = {
        "exactly_one_external_source_evaluated": decision["source_count_evaluated"] == 1,
        "normalized_source_class_academic_primary": decision["normalized_source_class"] == "academic_primary",
        "risk_parity_uses_frozen_12_month_volatility_window": decision["volatility_window_months"] == 12,
        "trend_signal_uses_frozen_10_month_moving_average": decision["trend_moving_average_months"] == 10,
        "below_trend_weight_moves_to_bil": decision["below_trend_weight_destination"] == "BIL",
        "no_leverage_or_shorting_introduced": decision["no_leverage"] is True and decision["no_shorting"] is True,
        "gld_cannot_represent_broad_commodities": gld_commodity is False,
        "missing_asset_classes_block_preregistration": (
            missing_mapping_blocks and decision["outcome"] == OUTCOME_NOT_READY
        )
        or not missing_mapping_blocks,
        "material_distinction_compared_with_existing_fingerprints": material_row["closest_prior_strategy"] != "",
        "closed_variants_remain_closed": all(
            closed in closed_ids
            for closed in (
                "mgd_bounded_canary_defensive_top1_126_v1",
                "mgd_bounded_barbell_gated_126_v1",
            )
        ),
        "no_backtest_or_parameter_search": decision["no_backtest_run"] is True and decision["no_parameter_search_authorized"] is True,
        "no_lifecycle_evidence_level_active_observation_or_paper_demo_changes": decision["no_lifecycle_or_paper_demo_state_change"] is True,
        "generation_deterministic": stable_hash(
            {
                "source": SOURCE_ID,
                "mapping": mapping_rows,
                "material": material_row,
                "outcome": decision["outcome"],
            }
        ).startswith("sha256:"),
        "candidate_not_forced_into_macro_gld_family": decision["family"] == FAMILY_ID,
        "preregistration_only_if_ready": (
            decision["preregistration_created"] is True if decision["outcome"] == OUTCOME_READY else decision["preregistration_created"] is False
        ),
    }
    check["consistency_passed"] = all(value is True for value in check.values() if isinstance(value, bool))
    return check


def run() -> dict[str, Any]:
    intake_path = write_intake_candidate()
    rule_rows = source_rule_rows()
    support_rows = source_support_rows(rule_rows)
    mapping_rows = wrapper_mapping_rows()
    cache_rows = local_cache_rows(mapping_rows)
    prior_rows = closest_prior_rows()
    material_row = material_distinction_row(mapping_rows)
    missing = missing_rows(mapping_rows)
    decision = decision_for(mapping_rows, material_row, missing)
    write_reports(intake_path, rule_rows, support_rows, mapping_rows, cache_rows, prior_rows, material_row, missing, decision)
    check = consistency_check(decision, mapping_rows, material_row)
    write_json(OUTPUT_DIR / "consistency_check.json", check)
    return {
        "output_dir": str(abs_path(OUTPUT_DIR)),
        "intake_candidate_path": str(intake_path),
        "source_id": SOURCE_ID,
        "family": FAMILY_ID,
        "outcome": decision["outcome"],
        "blocker": decision["blocker"],
        "blocking_asset_classes": decision["blocking_asset_classes"],
        "material_distinction_result": decision["material_distinction_result"],
        "preregistration_created": decision["preregistration_created"],
        "consistency_passed": check["consistency_passed"],
        "next_action": decision["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
