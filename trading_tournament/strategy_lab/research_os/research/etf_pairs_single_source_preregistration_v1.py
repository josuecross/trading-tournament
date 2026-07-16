from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
INTAKE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
EVIDENCE_DIR = ROOT / "evidence" / "etf_pairs_single_source_preregistration_v1" / "latest"
SOURCE_ID = "gatev_goetzmann_rouwenhorst_pairs_trading_2006"
FAMILY_ID = "relative_value_or_spread_etf_pairs"
CANDIDATE_ID = "etf_pairs_distance_12m_6m_2sd_v1"
OUTCOME = "source_not_ready"
BLOCKER = "short_accounting_and_borrow_cost_model_missing"
NEXT_ACTION = "define_paper_demo_short_accounting_and_borrow_cost_convention_before_pairs_preregistration"
SECTOR_UNIVERSE = tuple(active.SECTOR_ASSETS)
FORMATION_MONTHS = 12
TRADING_MONTHS = 6
ENTRY_THRESHOLD_SD = 2.0
PAIR_COUNT = 5
TOL = 1e-9


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def cache_info(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return {"symbol": symbol, "cache_ready": False, "cache_path": rel(path), "first_date": "", "last_date": "", "row_count": 0}
    first = ""
    last = ""
    count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            date = row.get("date", "")
            if not first:
                first = date
            last = date
            count += 1
    return {
        "symbol": symbol,
        "cache_ready": count > 0,
        "cache_path": rel(path),
        "first_date": first,
        "last_date": last,
        "row_count": count,
        "cache_sha256": sha256_path(path),
    }


def pair_sleeve_exposure(pair_count: int = PAIR_COUNT) -> dict[str, float]:
    sleeve_gross = 1.0 / pair_count
    long_leg = 0.5 * sleeve_gross
    short_leg = -0.5 * sleeve_gross
    gross = pair_count * (abs(long_leg) + abs(short_leg))
    net = pair_count * (long_leg + short_leg)
    return {
        "pair_count": float(pair_count),
        "sleeve_gross": sleeve_gross,
        "long_leg_weight": long_leg,
        "short_leg_weight": short_leg,
        "gross_exposure": gross,
        "net_exposure": net,
    }


def source_intake_payload() -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "intake_status": "single_direction_owner_source_supplied_for_preregistration_gate",
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "Pairs Trading: Performance of a Relative-Value Arbitrage Rule",
            "source_url_or_citation": "Evan Gatev, William N. Goetzmann, K. Geert Rouwenhorst, Review of Financial Studies, 2006; NBER Working Paper 7032",
            "source_type": "academic_primary",
            "source_class": "academic_primary",
            "authors": ["Evan Gatev", "William N. Goetzmann", "K. Geert Rouwenhorst"],
            "publication_date": "2006",
            "source_evidence_public_context_only": True,
        },
        "strategy_description": {
            "strategy_family": FAMILY_ID,
            "claimed_hypothesis": "Historically similar securities can diverge temporarily; a relative-value rule longs the underpriced member and shorts the overpriced member until normalized price paths converge.",
            "rule_clarity": "clear_for_source_stock_study_but_project_etf_short_accounting_blocked",
            "classification": "source_inspired_etf_pairs_adaptation",
            "timeframe": "daily data; 12-month formation followed by six-month trading periods",
        },
        "rules": {
            "formation_period": "12 months",
            "formation_price_series": "normalized cumulative total-return price series",
            "distance_measure": "sum of squared deviations between normalized price paths",
            "pair_ranking": "ascending historical distance; closest pairs selected before trading period",
            "trading_period": "following six months",
            "spread_std_estimation": "formation-period historical standard deviation of pair spread",
            "entry_rule": "open when normalized prices diverge by more than two formation-period spread standard deviations",
            "long_leg": "relatively lower-priced security",
            "short_leg": "relatively higher-priced security",
            "exit_rule": "close at next crossing/convergence of normalized prices",
            "forced_close": "close remaining positions at six-month trading period end",
            "reentry_rule": "permit reopening after convergence when later divergence occurs",
            "execution_timing": "delayed execution; no same-close fills",
            "sizing": "equal-dollar long and short legs in source; project adaptation would cap gross exposure at 1.0 if feasible",
        },
        "project_adaptation": {
            "candidate_id": CANDIDATE_ID,
            "candidate_family": FAMILY_ID,
            "adaptation_classification": "source_inspired_etf_pairs_adaptation",
            "not_exact_stock_universe_replication": True,
            "project_paper_demo_exposure_convention": {
                "max_gross_exposure": 1.0,
                "net_exposure_target": 0.0,
                "equal_gross_allocation_across_pair_sleeves": True,
                "long_leg_fraction_of_sleeve_gross": 0.5,
                "short_leg_fraction_of_sleeve_gross": 0.5,
                "short_proceeds_available_for_additional_leverage": False,
            },
        },
        "governance": {
            "source_selected_by_direction_owner": True,
            "web_browsing_used": False,
            "provider_download": False,
            "strategy_implemented": False,
            "backtest_run": False,
            "promotion_or_paper_demo_allowed": False,
        },
    }
    existing_path = INTAKE_DIR / f"{SOURCE_ID}.yaml"
    if existing_path.exists():
        try:
            existing = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            existing = {}
        if existing.get("resolution_packets"):
            payload["resolution_packets"] = existing["resolution_packets"]
            payload.setdefault("governance", {})["prior_blocked_state_preserved"] = True
    return payload


def source_rule_rows() -> list[dict[str, Any]]:
    refs = {
        "source_identity": "Review of Financial Studies, 2006; NBER Working Paper 7032",
        "formation": "Direction-owner supplied methodology summary: formation stage",
        "trading": "Direction-owner supplied methodology summary: trading stage",
        "project": "Direction-owner supplied project paper/demo adaptation convention",
    }
    return [
        {"rule_field": "source_identity", "extracted_rule": "academic_primary source by Gatev, Goetzmann, and Rouwenhorst", "classification": "source_explicit", "support_reference": refs["source_identity"]},
        {"rule_field": "formation_period", "extracted_rule": "12 months", "classification": "source_explicit", "support_reference": refs["formation"]},
        {"rule_field": "normalized_price_series", "extracted_rule": "normalized cumulative total-return price series", "classification": "source_explicit", "support_reference": refs["formation"]},
        {"rule_field": "distance_measure", "extracted_rule": "sum of squared deviations between normalized price paths", "classification": "source_explicit", "support_reference": refs["formation"]},
        {"rule_field": "pair_selection", "extracted_rule": "minimum historical distance / closest pairs before trading period", "classification": "source_explicit", "support_reference": refs["formation"]},
        {"rule_field": "trading_period", "extracted_rule": "following six months", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "entry_threshold", "extracted_rule": "divergence greater than two formation-period spread standard deviations", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "long_short_direction", "extracted_rule": "long relatively lower-priced security and short relatively higher-priced security", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "convergence_exit", "extracted_rule": "close at next normalized-price crossing/convergence", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "forced_close", "extracted_rule": "close open positions at six-month trading-period end", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "reentry", "extracted_rule": "allow reopening after completed convergence if later divergence occurs", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "delayed_execution", "extracted_rule": "use delayed execution; same-close fills prohibited", "classification": "source_explicit", "support_reference": refs["trading"]},
        {"rule_field": "gross_exposure_cap", "extracted_rule": "project cap max gross exposure at 1.0", "classification": "project_paper_demo_exposure_convention", "support_reference": refs["project"]},
        {"rule_field": "borrow_cost", "extracted_rule": "project borrow-cost assumption required but not currently canonical", "classification": "unresolved", "support_reference": "repository feasibility inspection"},
    ]


def source_support_rows() -> list[dict[str, Any]]:
    return [
        {
            "rule_field": row["rule_field"],
            "source_id": SOURCE_ID,
            "classification": row["classification"],
            "supports_rule": row["classification"] in {"source_explicit", "project_paper_demo_exposure_convention"},
            "support_reference": row["support_reference"],
            "notes": "Project execution conventions are separated from source claims." if row["classification"].startswith("project") else "",
        }
        for row in source_rule_rows()
    ]


def prior_inventory_rows() -> list[dict[str, Any]]:
    return [
        {
            "prior_record": "strategy_registry / evidence text search",
            "mechanism": "spread/financing/leverage blockers present, but no exact ETF distance-pairs implementation found",
            "exact_pairs_variant": False,
            "evidence_reference": "strategy_registry rows for blocked forex/options/high-complexity execution models; SEL borrow/spread fields unknown",
        },
        {
            "prior_record": "short_term_equity_mean_reversion public-source rows",
            "mechanism": "single-instrument long-only SPY/BIL mean-reversion timing",
            "exact_pairs_variant": False,
            "evidence_reference": "public-source intake and bounded bt rows",
        },
        {
            "prior_record": "sector/tactical ETF rotation families",
            "mechanism": "long-only ranking/rotation or defensive BIL fallback",
            "exact_pairs_variant": False,
            "evidence_reference": "strategy_registry and bounded run evidence",
        },
    ]


def duplicate_gate_rows() -> list[dict[str, Any]]:
    return [
        {
            "gate_component": "historical_distance_pair_formation",
            "prior_exact_match_found": False,
            "notes": "No prior valid test found with 12-month normalized-path distance pair formation.",
        },
        {
            "gate_component": "two_sd_spread_entry",
            "prior_exact_match_found": False,
            "notes": "No prior valid ETF pair spread test found with two-standard-deviation entry.",
        },
        {
            "gate_component": "long_loser_short_winner_convergence_exit",
            "prior_exact_match_found": False,
            "notes": "Current public-source and ETF research lanes are long-only; no exact simultaneous long/short convergence rule found.",
        },
        {
            "gate_component": "six_month_trading_reentry",
            "prior_exact_match_found": False,
            "notes": "No exact six-month trading period with re-entry after convergence found.",
        },
    ]


def etf_universe_rows() -> list[dict[str, Any]]:
    sector_cache = [cache_info(symbol) for symbol in SECTOR_UNIVERSE]
    return [
        {
            "universe_id": "canonical_sector_etf_universe_from_active_dsr",
            "selection_basis": "existing fixed sector ETF universe in active strategy evidence recompute",
            "symbols": SECTOR_UNIVERSE,
            "symbol_count": len(SECTOR_UNIVERSE),
            "performance_selected": False,
            "leveraged_inverse_or_etn_present": False,
            "all_symbols_cache_ready": all(row["cache_ready"] for row in sector_cache),
            "can_support_top_five_pairs_if_overlap_disallowed": len(SECTOR_UNIVERSE) >= 10,
            "universe_gate_status": "objective_universe_available_but_not_sufficient_without_short_accounting",
            "cache_start_min": min(row["first_date"] for row in sector_cache if row["cache_ready"]),
            "cache_end_max": max(row["last_date"] for row in sector_cache if row["cache_ready"]),
        },
        {
            "universe_id": "vm_quality_lowvol_proxy_universe",
            "selection_basis": "existing active VM universe",
            "symbols": ("SPLV", "USMV", "QUAL", "SPY"),
            "symbol_count": 4,
            "performance_selected": False,
            "leveraged_inverse_or_etn_present": False,
            "all_symbols_cache_ready": all(cache_info(symbol)["cache_ready"] for symbol in ("SPLV", "USMV", "QUAL", "SPY")),
            "can_support_top_five_pairs_if_overlap_disallowed": False,
            "universe_gate_status": "too_small_for_source_top_five_pair_portfolio_without_overlap_decision",
            "cache_start_min": "",
            "cache_end_max": "",
        },
    ]


def short_accounting_rows() -> list[dict[str, Any]]:
    exposure = pair_sleeve_exposure()
    return [
        {
            "requirement": "negative_share_quantities",
            "required_for_preregistration": True,
            "repository_status": "unsupported",
            "evidence": "Existing invariant helpers count negative weights as violations; no canonical negative-share ledger was found.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "long_short_mark_to_market_pnl",
            "required_for_preregistration": True,
            "repository_status": "unsupported",
            "evidence": "Current ETF runners compute long-only target weights/returns; no short proceeds and cover cash-flow model found.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "gross_and_net_exposure",
            "required_for_preregistration": True,
            "repository_status": "convention_defined_but_engine_support_missing",
            "evidence": f"Project convention would have gross={exposure['gross_exposure']:.1f}, net={exposure['net_exposure']:.1f} for {PAIR_COUNT} pair sleeves.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "short_entry_proceeds_and_cover_cash_flows",
            "required_for_preregistration": True,
            "repository_status": "unsupported",
            "evidence": "No canonical cash ledger for short proceeds not being reusable as leverage was found.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "borrow_cost",
            "required_for_preregistration": True,
            "repository_status": "missing_canonical_assumption",
            "evidence": "SEL builder records borrow_assumptions and financing_assumptions as unknown.",
            "blocks_preregistration": True,
        },
    ]


def execution_cost_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement": "same_close_execution_forbidden",
            "status": "freezable",
            "project_evidence": "Source and task require next-valid-session execution; no backtest implemented here.",
            "blocks_preregistration": False,
        },
        {
            "requirement": "two_leg_transaction_costs",
            "status": "missing_canonical_short_leg_cost_convention",
            "project_evidence": "Long-only slippage exists; no canonical two-leg long/short cost and borrow accrual convention found.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "forced_close_at_trading_period_end",
            "status": "rule_freezable_but_engine_not_validated_for_shorts",
            "project_evidence": "Calendar forced-close rule is source-supported; cash-flow implementation is not.",
            "blocks_preregistration": True,
        },
        {
            "requirement": "missing_price_or_delisting_handling",
            "status": "short_specific_policy_missing",
            "project_evidence": "ETF cache has daily data, but no short-specific missing/delisting policy was identified.",
            "blocks_preregistration": True,
        },
    ]


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "comparison_family": "single_asset_mean_reversion / Connors RSI2",
            "shared_features": "short-horizon reversal idea",
            "material_distinction": "Pairs source uses relative pricing between two instruments, simultaneous long/short legs, distance formation, and convergence exit.",
            "distinct": True,
        },
        {
            "comparison_family": "tactical ETF rotation / sector rotation",
            "shared_features": "ETF universe and daily prices",
            "material_distinction": "No cross-sectional momentum ranking or BIL defensive switch; source mechanism is spread convergence.",
            "distinct": True,
        },
        {
            "comparison_family": "static factor exposure / SPLV",
            "shared_features": "ETF wrapper evidence infrastructure",
            "material_distinction": "Static exposure has no pair formation, no short leg, and no convergence exit.",
            "distinct": True,
        },
        {
            "comparison_family": "historical spread or relative-value rows",
            "shared_features": "family label if present",
            "material_distinction": "No exact prior ETF distance-pairs implementation found; materially distinct but implementation-blocked.",
            "distinct": True,
        },
    ]


def missing_rows() -> list[dict[str, Any]]:
    return [
        {
            "blocking_field": "short_accounting.negative_share_quantities",
            "blocker": BLOCKER,
            "present_evidence": "Source explicitly requires long lower-priced and short higher-priced security.",
            "absent_evidence": "Canonical repository support for negative share quantities and short cash ledger.",
            "smallest_next_action": NEXT_ACTION,
        },
        {
            "blocking_field": "short_accounting.borrow_cost",
            "blocker": BLOCKER,
            "present_evidence": "Task requires borrow cost charged through time.",
            "absent_evidence": "Canonical paper/demo borrow-cost assumption.",
            "smallest_next_action": NEXT_ACTION,
        },
        {
            "blocking_field": "execution_cost.two_leg_short_costs",
            "blocker": BLOCKER,
            "present_evidence": "Long-only slippage conventions exist.",
            "absent_evidence": "Canonical two-leg long/short execution cost and short-cover convention.",
            "smallest_next_action": NEXT_ACTION,
        },
    ]


def decision_payload(hashes_before: dict[str, str], hashes_after: dict[str, str]) -> dict[str, Any]:
    exposure = pair_sleeve_exposure()
    return {
        "outcome": OUTCOME,
        "source_id": SOURCE_ID,
        "source_count_evaluated": 1,
        "source_class": "academic_primary",
        "family_id": FAMILY_ID,
        "candidate_id": CANDIDATE_ID,
        "blocker": BLOCKER,
        "smallest_next_action": NEXT_ACTION,
        "exact_duplicate_found": False,
        "duplicate_or_not_materially_distinct": False,
        "objective_etf_universe_available": True,
        "selected_feasible_universe_if_shorting_were_supported": "canonical_sector_etf_universe_from_active_dsr",
        "universe_performance_selected": False,
        "leveraged_inverse_or_etn_excluded": True,
        "formation_months": FORMATION_MONTHS,
        "trading_months": TRADING_MONTHS,
        "entry_threshold_standard_deviations": ENTRY_THRESHOLD_SD,
        "same_close_execution_forbidden": True,
        "long_and_short_legs_required": True,
        "project_paper_demo_exposure_convention": "project_paper_demo_exposure_convention",
        "pair_count_preference": PAIR_COUNT,
        "gross_exposure_convention": exposure["gross_exposure"],
        "net_exposure_convention": exposure["net_exposure"],
        "short_accounting_supported": False,
        "borrow_cost_assumption_available": False,
        "preregistration_created": False,
        "no_backtest_run": True,
        "no_provider_call": True,
        "provider_download": False,
        "intraday_data_used": False,
        "strategy_implemented": False,
        "no_parameter_search": True,
        "no_prior_exact_variant_reopened": True,
        "registry_hash_before": hashes_before["registry"],
        "registry_hash_after": hashes_after["registry"],
        "registry_byte_identical": hashes_before["registry"] == hashes_after["registry"],
        "active_observations_hash_before": hashes_before["active_observations"],
        "active_observations_hash_after": hashes_after["active_observations"],
        "active_observations_unchanged": hashes_before["active_observations"] == hashes_after["active_observations"],
        "lifecycle_or_evidence_level_changed": False,
        "promotion_or_paper_demo_activation": False,
        "real_money_recommendation": False,
    }


def decision_markdown(decision: dict[str, Any]) -> str:
    return f"""# ETF Pairs Single-Source Preregistration V1

Outcome: `{decision['outcome']}`

Source evaluated: `{SOURCE_ID}`.

The Gatev, Goetzmann, and Rouwenhorst pairs-trading source is external and rule-complete enough to describe the source mechanism. The project can identify an objective sector ETF universe from existing governance, but a preregistration is not ready because the current repository does not have canonical paper/demo support for true long/short pair accounting.

Primary blocker: `{decision['blocker']}`.

Smallest next action: `{decision['smallest_next_action']}`.

No pre-registration, implementation, backtest, provider download, parameter search, lifecycle change, paper/demo activation, or real-money recommendation occurred.
"""


def consistency(decision: dict[str, Any]) -> dict[str, Any]:
    exposure = pair_sleeve_exposure()
    return {
        "consistency_passed": bool(
            decision["outcome"] == OUTCOME
            and decision["source_count_evaluated"] == 1
            and decision["no_backtest_run"] is True
            and decision["no_provider_call"] is True
            and decision["registry_byte_identical"] is True
            and decision["active_observations_unchanged"] is True
            and decision["preregistration_created"] is False
        ),
        "exactly_one_source_evaluated": True,
        "no_backtest_run": True,
        "no_provider_call": True,
        "etf_universe_frozen_independent_of_performance": True,
        "leveraged_inverse_etn_excluded": True,
        "formation_period_fixed_12_months": FORMATION_MONTHS == 12,
        "trading_period_fixed_6_months": TRADING_MONTHS == 6,
        "entry_threshold_fixed_two_standard_deviations": ENTRY_THRESHOLD_SD == 2.0,
        "same_close_execution_forbidden": True,
        "long_and_short_legs_required": True,
        "gross_exposure_lte_1": exposure["gross_exposure"] <= 1.0 + TOL,
        "net_exposure_zero": abs(exposure["net_exposure"]) <= TOL,
        "unsupported_short_accounting_blocks_preregistration": True,
        "no_prior_exact_variant_reopened": True,
        "registry_byte_identical": decision["registry_byte_identical"],
        "active_observations_unchanged": decision["active_observations_unchanged"],
        "deterministic_generation_no_timestamps": True,
    }


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    hashes_before = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    intake = source_intake_payload()
    intake_path = INTAKE_DIR / f"{SOURCE_ID}.yaml"
    write_yaml(intake_path, intake)
    write_yaml(EVIDENCE_DIR / "source_intake_record.yaml", intake)
    write_csv(EVIDENCE_DIR / "source_rule_extraction.csv", source_rule_rows())
    write_csv(EVIDENCE_DIR / "source_support_trace.csv", source_support_rows())
    write_csv(EVIDENCE_DIR / "prior_pairs_and_spread_inventory.csv", prior_inventory_rows())
    write_csv(EVIDENCE_DIR / "duplicate_gate.csv", duplicate_gate_rows())
    write_csv(EVIDENCE_DIR / "etf_universe_feasibility.csv", etf_universe_rows())
    write_csv(EVIDENCE_DIR / "short_accounting_feasibility.csv", short_accounting_rows())
    write_csv(EVIDENCE_DIR / "execution_and_cost_feasibility.csv", execution_cost_rows())
    write_csv(EVIDENCE_DIR / "material_distinction_review.csv", material_distinction_rows())
    write_csv(EVIDENCE_DIR / "missing_or_ambiguous_fields.csv", missing_rows())

    hashes_after = {
        "registry": sha256_path(registry_path),
        "active_observations": sha256_path(active_observations_path),
    }
    decision = decision_payload(hashes_before, hashes_after)
    write_json(EVIDENCE_DIR / "decision.json", decision)
    write_text(EVIDENCE_DIR / "decision.md", decision_markdown(decision))
    check = consistency(decision)
    write_json(EVIDENCE_DIR / "consistency_check.json", check)
    return {**decision, **check}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
