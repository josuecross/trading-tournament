from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "assess_spdj_dynamic_inflation_research_eligibility_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
FAMILY_ID = "public_cpi_dynamic_inflation_regime_allocation"
ARCHITECTURE_ID = "monthly_cpi_regime_dynamic_multi_asset_inflation_allocation"
CANONICAL_TRIAL_ID = f"{STRATEGY_ID}__canonical"
ROBUSTNESS_TRIAL_ID = "run_spdj_dynamic_inflation_robustness_v1__robustness"

EXPECTED_EXPLORATION_OUTCOME = "spdj_dynamic_inflation_exploration_followup"
EXPECTED_ROBUSTNESS_OUTCOME = "spdj_dynamic_inflation_robustness_passed"
EXPECTED_EXPLORATION_HASH = "sha256:0f3cff1fbed4af952e5264fb60d21b4f0bdec2d7080bb3d16c356bef3e9ccea9"
EXPECTED_ROBUSTNESS_HASH = "sha256:d8c22c89989128454228795221d3b4d81b21d572c10c8e3b300e70b40586ec59"
EXPECTED_CPI_HASH = "sha256:e221af86dfd616f4fa65bec016910deaffe47f1d6e690495a4033cd0e3eefcc8"
EXPECTED_PRICE_BUNDLE_HASH = "sha256:ab05bef8ac2b12c6391bca65cb1312148db7d64bed11e9932379464f8bcc72c8"
EXPECTED_UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
EXPECTED_CODE_HASH = "sha256:55eff61ee55999df76d023e570440197c7dbf0d05da41775cf23671dbd15b1e4"

INTAKE_DIR = ROOT / "evidence/public_source_strategy_intake/phase2_public_signal_etf_mappable_candidate_intake_v2/latest"
CPI_V1_EVIDENCE_DIR = ROOT / "evidence/public_signal_data/acquire_validate_freeze_phase2_public_signal_inputs_v1/latest"
CPI_V2_EVIDENCE_DIR = ROOT / "evidence/public_signal_data/resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2/latest"
CPI_V1_DATA_DIR = ROOT / "data/public_signals/phase2_public_cpi_point_in_time_v1"
CPI_V2_DATA_DIR = ROOT / "data/public_signals/phase2_public_cpi_point_in_time_v2"
UNIVERSE_DIR = ROOT / "evidence/universe_expansion/phase2_bounded_multi_asset_research_universe_v1/latest"
EXPLORATION_DIR = ROOT / "evidence/research_recovery/spdj_multi_asset_dynamic_inflation_etf_portability_v1/latest"
ROBUSTNESS_DIR = ROOT / "evidence/robustness/spdj_dynamic_inflation_robustness_v1/latest"
CANONICAL_CODE = ROOT / "strategy_lab/research_os/research/implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1.py"
OUTPUT_DIR = ROOT / "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest"

SYMBOLS = ("SPY", "IYR", "GSG", "GLD", "AGG", "TIP")
ETF_MAPPING = {
    "U.S. equities": "SPY",
    "U.S. REITs": "IYR",
    "broad commodities": "GSG",
    "gold": "GLD",
    "U.S. aggregate bonds": "AGG",
    "U.S. TIPS": "TIP",
}
EXPECTED_ARTIFACT_HASHES = {
    "data/public_signals/phase2_public_cpi_point_in_time_v1": "sha256:60dcfea6c6d60db8381fb391e42981c60ead0dfd9ed10fe72b679dc4adf0f8fb",
    "data/public_signals/phase2_public_cpi_point_in_time_v2": "sha256:0b8e9030f98e092158e58957ab962c87c14c8aeed09bc795c0c8d19f556f54f7",
    "data/universe_expansion/phase2_bounded_multi_asset_market_data_v1": "sha256:a48c121ddae1fb0492c37105131892f921435de3f611a19d1b9307bab1717520",
    "data/universe_expansion/pilot_etf_market_data_v1": "sha256:0991ee2a0e0327581f6651408f54463cff5d03ec9f7024859cf6befac8646a53",
    "evidence/public_signal_data/acquire_validate_freeze_phase2_public_signal_inputs_v1/latest": "sha256:a86bdf9179c34723ac2f3b63cf026cf5de4e0838bbf739761db5ae7c3e6e3ff4",
    "evidence/public_signal_data/resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2/latest": "sha256:52f058ef66f45cd32dacc7b9c0ec20739023fdda52809e9c36494b0e4a2eee2e",
    "evidence/public_source_strategy_intake/phase2_public_signal_etf_mappable_candidate_intake_v2/latest": "sha256:727e36f9557083c7cecaffd1b4e279a779d7e403a88ef8450183fd678de458af",
    "evidence/research_recovery/spdj_multi_asset_dynamic_inflation_etf_portability_v1/latest": "sha256:ada1f2a72dfa1c9c0a91bea1e0ba5a5bcff1741124ae86abd1f088e44acaee1c",
    "evidence/universe_expansion/phase2_bounded_multi_asset_research_universe_v1/latest": "sha256:30bb4c54995757fa99eb9eee8eafb2f6bb2242b16318957280e33689d4be0f94",
}

REQUIRED_OUTPUTS = (
    "eligibility_report.md",
    "eligibility_gate_results.json",
    "lineage_reconciliation.json",
    "source_and_data_reconciliation.json",
    "exploration_reconciliation.json",
    "robustness_reconciliation.json",
    "implementation_integrity.json",
    "caveat_register.csv",
    "handoff_specification_readiness.json",
    "eligibility_decision.json",
    "trial_accounting.json",
    "consistency_check.json",
    "next_action.md",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    elif path.is_dir():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
    else:
        digest.update(b"missing")
    return f"sha256:{digest.hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: (
                        json.dumps(row.get(field), sort_keys=True, separators=(",", ":"))
                        if isinstance(row.get(field), (dict, list))
                        else str(row.get(field, "")).lower()
                        if isinstance(row.get(field), bool)
                        else row.get(field, "")
                    )
                    for field in fields
                }
            )


def protected_paths() -> list[Path]:
    return [
        CANONICAL_CODE,
        INTAKE_DIR,
        CPI_V1_EVIDENCE_DIR,
        CPI_V2_EVIDENCE_DIR,
        CPI_V1_DATA_DIR,
        CPI_V2_DATA_DIR,
        ROOT / "data/universe_expansion/pilot_etf_market_data_v1",
        ROOT / "data/universe_expansion/phase2_bounded_multi_asset_market_data_v1",
        UNIVERSE_DIR,
        EXPLORATION_DIR,
        ROBUSTNESS_DIR,
        ROOT / "strategy_lab/RESEARCH_ROADMAP.md",
        ROOT / "strategy_lab/strategy_registry.yaml",
        ROOT / "strategy_lab/research_os/research/research_queue.yaml",
        ROOT / "strategy_lab/research_os/family_lineage/family_ledger.yaml",
        ROOT / "strategy_lab/research_os/operations/active_observations.yaml",
        ROOT / "paper_forward_observation_plans",
        ROOT / "paper_forward_observations",
    ]


def snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def existing_decision_timestamp() -> str:
    path = OUTPUT_DIR / "eligibility_decision.json"
    if path.exists():
        value = read_json(path).get("eligibility_decision_timestamp")
        if isinstance(value, str) and value:
            return value
    return datetime.now(timezone.utc).isoformat()


def selected_source_package() -> dict[str, Any]:
    payload = read_json(INTAKE_DIR / "selected_work_packages.json")
    packages = payload.get("selected_work_packages", payload)
    for package in packages:
        if package.get("strategy_id") == STRATEGY_ID:
            return package
    raise KeyError(f"Missing selected source package for {STRATEGY_ID}")


def price_path(symbol: str) -> Path:
    phase2 = ROOT / f"data/universe_expansion/phase2_bounded_multi_asset_market_data_v1/{symbol}.csv"
    pilot = ROOT / f"data/universe_expansion/pilot_etf_market_data_v1/{symbol}.csv"
    return phase2 if phase2.exists() else pilot


def matching_result(path: Path, period_id: str, role: str, cost: str) -> dict[str, str]:
    for row in read_csv_rows(path):
        if (
            row.get("period_id") == period_id
            and row.get("entity_role") == role
            and row.get("cost_bps_one_way") == cost
        ):
            return row
    raise KeyError((path, period_id, role, cost))


def packet_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(item for item in REQUIRED_OUTPUTS if item != "consistency_check.json"):
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = snapshot(protected_paths())
    decision_timestamp = existing_decision_timestamp()

    intake_consistency = read_json(INTAKE_DIR / "consistency_check.json")
    source_package = selected_source_package()
    mappings = [
        row
        for row in read_csv_rows(INTAKE_DIR / "tradable_exposure_mapping.csv")
        if row["candidate_id"] == STRATEGY_ID
    ]
    v1_consistency = read_json(CPI_V1_EVIDENCE_DIR / "consistency_check.json")
    v2_consistency = read_json(CPI_V2_EVIDENCE_DIR / "consistency_check.json")
    v2_readiness = read_json(CPI_V2_EVIDENCE_DIR / "signal_readiness_v2.json")
    v2_freeze = read_json(CPI_V2_EVIDENCE_DIR / "freeze_manifest.json")
    universe_consistency = read_json(UNIVERSE_DIR / "consistency_check.json")
    universe_rows = read_csv_rows(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    exploration = read_json(EXPLORATION_DIR / "consistency_check.json")
    exploration_accounting = read_json(EXPLORATION_DIR / "trial_accounting.json")
    preregistration = read_json(EXPLORATION_DIR / "preregistration.json")
    evaluation_access = read_json(EXPLORATION_DIR / "evaluation_access_log.json")
    source_conformance = read_json(EXPLORATION_DIR / "source_conformance.json")
    correction = read_json(EXPLORATION_DIR / "implementation_correction_log.json")
    robustness = read_json(ROBUSTNESS_DIR / "consistency_check.json")
    robustness_gates = read_json(ROBUSTNESS_DIR / "robustness_gate_results.json")
    robustness_prereg = read_json(ROBUSTNESS_DIR / "robustness_preregistration.json")
    robustness_accounting = read_json(ROBUSTNESS_DIR / "trial_accounting.json")

    required_source_rules = source_package["source_defined_rules"]
    source_rule_fields_complete = all(
        required_source_rules.get(key) not in (None, "", "unknown", "unmapped")
        for key in (
            "signal_definition",
            "exact_signal_inputs",
            "lookback_or_measurement_period",
            "formation_timing",
            "allocation_weights",
            "transaction_timing",
            "material_conditions",
        )
    )
    mappings_by_symbol = {row["frozen_symbol_mapping"]: row for row in mappings}
    mapping_complete = set(mappings_by_symbol) == set(SYMBOLS)

    component_hashes_match = all(
        (ROOT / path).exists() and sha256_path(ROOT / path) == expected
        for path, expected in v2_freeze["core_file_hashes"].items()
    )
    artifact_hashes = {path: sha256_path(ROOT / path) for path in EXPECTED_ARTIFACT_HASHES}
    artifact_hashes_match = artifact_hashes == EXPECTED_ARTIFACT_HASHES
    universe_by_symbol = {row["symbol"]: row for row in universe_rows if row["symbol"] in SYMBOLS}
    individual_price_hashes_match = all(
        symbol in universe_by_symbol
        and universe_by_symbol[symbol]["cache_hash"] == sha256_path(price_path(symbol))
        and universe_by_symbol[symbol]["data_ready"].lower() == "true"
        for symbol in SYMBOLS
    )

    source_contract_checks = {
        "authoritative_primary_source_present": source_package["primary_source"]["authority"] == "primary_authoritative",
        "source_rules_complete": source_rule_fields_complete,
        "CPI_convention_resolved": v2_readiness["canonical_signal_rule"] == "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels",
        "timing_resolved": source_package["canonical_configuration"]["execution"] == "after_close_next_business_day_after_cpi_announcement",
        "warmup_resolved": v2_readiness["warmup_contract_status"] == "resolved_source_supported_portability_interpretation",
        "missing_release_behavior_resolved": v2_readiness["missing_release_exception_count"] == 1,
        "unresolved_material_source_rule_count_zero": v2_readiness["unresolved_source_contract_count"] == 0,
        "ETF_portability_claim_explicit": source_conformance["claim"] == "ETF_portability_research_not_official_SP_index_replication",
        "ETF_mapping_complete": mapping_complete,
    }

    data_checks = {
        "CPI_V1_point_in_time_provenance_complete": all(
            v1_consistency["checks"][key]
            for key in (
                "only_official_sources_accessed",
                "no_current_revised_history_substitution",
                "signal_unavailable_before_release",
                "release_dates_unique",
            )
        ),
        "CPI_V2_point_in_time_safe": v2_readiness["point_in_time_safe"] is True,
        "CPI_V2_logical_hash_matches": v2_freeze["frozen_dataset_hash"] == EXPECTED_CPI_HASH,
        "CPI_V2_component_hashes_match": component_hashes_match,
        "six_ETF_price_bundle_hash_matches": source_conformance["price_data_verification"]["frozen_price_data_bundle_hash"] == EXPECTED_PRICE_BUNDLE_HASH,
        "six_ETF_individual_cache_hashes_match": individual_price_hashes_match,
        "frozen_universe_hash_matches": universe_consistency["frozen_universe_hash"] == EXPECTED_UNIVERSE_HASH,
        "artifact_namespace_hashes_match": artifact_hashes_match,
        "no_unexplained_data_mutation": component_hashes_match and individual_price_hashes_match and artifact_hashes_match,
    }

    exploration_checks = {
        "expected_outcome": exploration["outcome"] == EXPECTED_EXPLORATION_OUTCOME,
        "deterministic_evidence_hash": exploration["deterministic_evidence_hash"] == EXPECTED_EXPLORATION_HASH,
        "one_canonical_configuration": exploration["entity_counts"]["canonical_configuration_count"] == 1,
        "one_canonical_trial": exploration["entity_counts"]["canonical_trial_count"] == 1,
        "zero_strategy_variants": exploration["entity_counts"]["strategy_variants_created"] == 0,
        "preregistration_before_performance": preregistration["preregistration_written_before_performance_access"] is True,
        "selection_preceded_evaluation_access": preregistration["preregistration_timestamp"] < evaluation_access["first_evaluation_access_timestamp"],
        "evaluation_accessed_exactly_once": exploration["entity_counts"]["evaluation_accesses"] == 1,
        "selection_period_matches": exploration["selection_period"] == {"start": "2009-08-17", "end": "2019-09-12", "events": 121},
        "evaluation_period_matches": exploration["evaluation_period"] == {"start": "2019-09-13", "end": "2026-08-04", "events": 82, "accessed": True},
        "selection_gate_passed": exploration["selection_gate"]["selection_eligible"] is True,
        "evaluation_gate_passed": exploration["evaluation_gate"]["exploration_followup_justified"] is True,
        "no_post_result_adaptation": preregistration["post_result_adaptation_allowed"] is False,
    }

    robustness_checks = {
        "expected_outcome": robustness["outcome"] == EXPECTED_ROBUSTNESS_OUTCOME,
        "deterministic_evidence_hash": robustness["deterministic_evidence_hash"] == EXPECTED_ROBUSTNESS_HASH,
        "one_robustness_trial": robustness_accounting["robustness_trial_count"] == 1,
        "robustness_trial_id_matches": robustness["robustness_trial_id"] == ROBUSTNESS_TRIAL_ID,
        "preregistration_before_calculation": robustness_prereg["written_before_robustness_results"] is True,
        "all_blocking_gates_passed": robustness_gates["blocking_gates_passed"] is True,
        "parent_reproduced": robustness_gates["parent_reproduction_pass"] is True,
        "zero_strategy_variants": robustness_accounting["strategy_variant_count"] == 0,
        "no_new_untouched_holdout_misclaimed": robustness_prereg["no_new_untouched_holdout"] is True,
        "blocking_controls_ex_ante": robustness["checks"]["blocking_controls_ex_ante"] is True,
        "ex_post_control_diagnostic_only": robustness["checks"]["ex_post_control_diagnostic_only"] is True,
    }

    implementation_checks = {
        "canonical_code_hash_matches": sha256_path(CANONICAL_CODE) == EXPECTED_CODE_HASH,
        "all_source_conformance_checks_pass": source_conformance["all_preperformance_checks_pass"] is True,
        "accounting_invariants_pass": source_conformance["postperformance_accounting_invariants_pass"] is True,
        "no_leverage_or_short_weights": source_conformance["preperformance_checks"]["no_leverage_or_short_weights"] is True,
        "explicit_zero_targets_preserved": source_conformance["preperformance_checks"]["zero_targets_preserved"] is True,
        "daily_weight_sums_valid": source_conformance["preperformance_checks"]["daily_target_rows_sum_one"] is True,
        "source_timing_correct": source_conformance["preperformance_checks"]["next_business_day_close_effective"] is True,
        "October_2025_no_synthetic_rebalance": source_conformance["preperformance_checks"]["october_2025_no_synthetic_rebalance"] is True,
        "invalid_run_preserved": correction["invalidated_selection_results_preserved"] is True,
        "correction_source_contract_preserving": correction["correction_type"] == "source_contract_preserving_implementation_defect_correction",
        "correction_did_not_change_strategy_rule": correction["strategy_rule_changed"] is False,
        "correction_did_not_change_trial_id": correction["trial_id_changed"] is False,
        "correction_not_performance_selected": correction["performance_result_used_to_choose_correction"] is False,
        "robustness_reproduced_corrected_parent": robustness["parent_reproduction_pass"] is True,
    }

    selection_primary = matching_result(EXPLORATION_DIR / "selection_results.csv", "selection", "canonical_candidate", "5.0")
    evaluation_primary = matching_result(EXPLORATION_DIR / "evaluation_results.csv", "reserved_evaluation", "canonical_candidate", "5.0")
    full_cost_rows = read_csv_rows(ROBUSTNESS_DIR / "cost_robustness.csv")
    full_primary = next(
        row for row in full_cost_rows
        if row["entity_role"] == "canonical_candidate" and row["cost_bps_one_way"] == "5.0"
    )
    full_high_cost = next(
        row for row in full_cost_rows
        if row["entity_role"] == "canonical_candidate" and row["cost_bps_one_way"] == "10.0"
    )

    handoff_spec = {
        "strategy_id": STRATEGY_ID,
        "status": "specification_complete_export_not_executed",
        "required_fields": {
            "tradable_symbols": list(SYMBOLS),
            "source_defined_schedule": "monthly_on_actual_CPI_announcement_events",
            "CPI_series_identity": "CPIAUCNS / CPI-U All Items NSA",
            "CPI_regime_formula": {
                "input": "unrounded point-in-time CPIAUCNS year-over-year percentage change",
                "low": "CPI_YoY < 1.5",
                "medium": "1.5 <= CPI_YoY <= 2.5",
                "high": "CPI_YoY > 2.5",
            },
            "point_in_time_and_release_timing": "use only the documented first release available at the CPI announcement",
            "allocation_statistics_cutoff": "previous_calendar_month_final_trading_close",
            "target_weight_algorithms": {
                "low": {"SPY": 0.6, "AGG": 0.4, "IYR": 0.0, "GSG": 0.0, "GLD": 0.0, "TIP": 0.0},
                "medium": "normalized inverse sample volatility across all six ETFs",
                "high": "normalized ProIB source beta transform across all six ETFs",
            },
            "warmup": "36 underlying monthly returns expanding one month at a time through 120, then rolling 120",
            "effective_date_rule": "target effective after close on the next business day after the CPI announcement",
            "missing_release_behavior": "no CPI announcement means no rebalance event; do not forward-fill, interpolate, or impute a signal",
            "transaction_cost_research_assumption": "5 bps per one-way turnover primary; 0 and 10 bps diagnostics",
            "source_and_dataset_hashes": {
                "CPI_dataset": EXPECTED_CPI_HASH,
                "price_bundle": EXPECTED_PRICE_BUNDLE_HASH,
                "universe": EXPECTED_UNIVERSE_HASH,
                "canonical_code": EXPECTED_CODE_HASH,
                "exploration_evidence": EXPECTED_EXPLORATION_HASH,
                "robustness_evidence": EXPECTED_ROBUSTNESS_HASH,
            },
            "source_citations": [
                source_package["primary_source"],
                {"provider": "U.S. Bureau of Labor Statistics", "series": "CPI-U All Items NSA / CPIAUCNS", "role": "official release provenance"},
            ],
            "known_research_caveats": ["C1", "C2", "C3", "C4", "C5", "C6"],
        },
        "October_2025_exception_representable": True,
        "forward_application_required_now": False,
        "forward_application_operational_health_tested": False,
        "handoff_export_executed": False,
    }
    handoff_checks = {
        "six_symbols_frozen": handoff_spec["required_fields"]["tradable_symbols"] == list(SYMBOLS),
        "schedule_specified": bool(handoff_spec["required_fields"]["source_defined_schedule"]),
        "CPI_identity_and_formula_specified": bool(handoff_spec["required_fields"]["CPI_series_identity"]) and bool(handoff_spec["required_fields"]["CPI_regime_formula"]),
        "timing_and_cutoffs_specified": bool(handoff_spec["required_fields"]["point_in_time_and_release_timing"]) and bool(handoff_spec["required_fields"]["allocation_statistics_cutoff"]),
        "weight_algorithms_specified": len(handoff_spec["required_fields"]["target_weight_algorithms"]) == 3,
        "warmup_and_effective_date_specified": bool(handoff_spec["required_fields"]["warmup"]) and bool(handoff_spec["required_fields"]["effective_date_rule"]),
        "missing_release_behavior_specified": handoff_spec["October_2025_exception_representable"] is True,
        "hashes_and_provenance_specified": len(handoff_spec["required_fields"]["source_and_dataset_hashes"]) == 6,
        "caveats_specified": len(handoff_spec["required_fields"]["known_research_caveats"]) == 6,
        "no_handoff_executed": handoff_spec["handoff_export_executed"] is False,
    }
    handoff_spec["checks"] = handoff_checks
    handoff_spec["overall_ready"] = all(handoff_checks.values())

    gates = {
        "gate_1_source_contract_complete": {
            "status": "pass" if all(source_contract_checks.values()) else "fail",
            "checks": source_contract_checks,
        },
        "gate_2_frozen_input_provenance_complete": {
            "status": "pass" if all(data_checks.values()) else "fail",
            "checks": data_checks,
        },
        "gate_3_canonical_trial_integrity": {
            "status": "pass" if all(exploration_checks.values()) else "fail",
            "checks": exploration_checks,
        },
        "gate_4_robustness_integrity": {
            "status": "pass" if all(robustness_checks.values()) else "fail",
            "checks": robustness_checks,
        },
        "gate_5_implementation_integrity": {
            "status": "pass" if all(implementation_checks.values()) else "fail",
            "checks": implementation_checks,
        },
        "gate_6_forward_handoff_specification_complete": {
            "status": "pass" if all(handoff_checks.values()) else "fail",
            "checks": handoff_checks,
        },
    }

    caveats = [
        {
            "caveat_id": "C1",
            "classification": "nonblocking_material",
            "title": "ETF portability",
            "finding": "The implementation maps source exposures to tradable ETFs and does not reproduce the official S&P index.",
            "handoff_requirement": "Preserve the ETF-portability label and exact frozen mapping.",
        },
        {
            "caveat_id": "C2",
            "classification": "nonblocking_material",
            "title": "60/40 raw-return tradeoff",
            "finding": "At 5 bps the 60/40 control has higher full-history CAGR; existing evidence records a slightly higher candidate Sharpe and materially better candidate drawdown.",
            "handoff_requirement": "Do not claim raw-CAGR superiority over 60/40.",
        },
        {
            "caveat_id": "C3",
            "classification": "nonblocking_material",
            "title": "Chronological control dominance",
            "finding": "One of four blocks is dominated by 60/40, a different block by equal weight, and no block by both controls simultaneously.",
            "handoff_requirement": "Retain the block-level robustness findings with the export.",
        },
        {
            "caveat_id": "C4",
            "classification": "nonblocking_material",
            "title": "No additional untouched holdout",
            "finding": "The reserved evaluation was untouched through selection, but later robustness reused already observed history.",
            "handoff_requirement": "Treat future observation as prospective evidence; do not relabel robustness history as a new holdout.",
        },
        {
            "caveat_id": "C5",
            "classification": "nonblocking_material",
            "title": "Source-to-ETF proxy risk",
            "finding": "SPY, IYR, GLD, AGG, and TIP are economically close source-preserving proxies; GSG is recorded as exact-match exposure.",
            "handoff_requirement": "Preserve mapping classifications and prohibit silent remapping.",
        },
        {
            "caveat_id": "C6",
            "classification": "nonblocking_minor",
            "title": "CPI exceptional release handling",
            "finding": "October 2025 had no official CPI release and creates no rebalance event under the frozen contract.",
            "handoff_requirement": "Represent no-release months as explicit no-event records without imputation.",
        },
    ]
    blocking_count = sum(row["classification"] == "blocking" for row in caveats)
    material_count = sum(row["classification"] == "nonblocking_material" for row in caveats)
    minor_count = sum(row["classification"] == "nonblocking_minor" for row in caveats)
    all_gates_pass = all(gate["status"] == "pass" for gate in gates.values())
    required_evidence_present = all(
        path.exists()
        for path in (
            INTAKE_DIR,
            CPI_V1_EVIDENCE_DIR,
            CPI_V2_EVIDENCE_DIR,
            CPI_V1_DATA_DIR,
            CPI_V2_DATA_DIR,
            UNIVERSE_DIR,
            EXPLORATION_DIR,
            ROBUSTNESS_DIR,
            CANONICAL_CODE,
        )
    )
    if not required_evidence_present:
        outcome = "spdj_dynamic_inflation_research_eligibility_blocked"
        next_action = "direction_owner_review_spdj_dynamic_inflation_eligibility_blocker_v1"
    elif all_gates_pass and blocking_count == 0:
        outcome = "spdj_dynamic_inflation_research_eligible_for_handoff"
        next_action = "export_spdj_dynamic_inflation_forward_observation_handoff_v1"
    else:
        outcome = "spdj_dynamic_inflation_research_not_eligible"
        next_action = "direction_owner_review_spdj_dynamic_inflation_ineligibility_v1"

    exploration_reconciliation = {
        "status": "reconciled" if all(exploration_checks.values()) else "not_reconciled",
        "checks": exploration_checks,
        "outcome": exploration["outcome"],
        "deterministic_evidence_hash": exploration["deterministic_evidence_hash"],
        "selection_period": exploration["selection_period"],
        "evaluation_period": exploration["evaluation_period"],
        "primary_5bps_existing_results": {
            "selection": {key: selection_primary[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
            "evaluation": {key: evaluation_primary[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
        },
        "new_performance_calculations": 0,
    }
    robustness_reconciliation = {
        "status": "reconciled" if all(robustness_checks.values()) else "not_reconciled",
        "checks": robustness_checks,
        "outcome": robustness["outcome"],
        "deterministic_evidence_hash": robustness["deterministic_evidence_hash"],
        "existing_full_history_results": {
            "candidate_5bps": {key: full_primary[key] for key in ("cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown")},
            "candidate_10bps": {key: full_high_cost[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
        },
        "four_block_summary": robustness_gates["four_block_summary"],
        "bootstrap_summary": robustness_gates["bootstrap_summary"],
        "diagnostic_findings": robustness_gates["diagnostic_findings"],
        "new_robustness_calculations": 0,
    }
    source_and_data = {
        "status": "reconciled" if all(source_contract_checks.values()) and all(data_checks.values()) else "not_reconciled",
        "source_contract_checks": source_contract_checks,
        "data_provenance_checks": data_checks,
        "hash_namespaces": {
            "logical_normalized_CPI_dataset": {"id": v2_freeze["dataset_id"], "hash": v2_freeze["frozen_dataset_hash"]},
            "CPI_V2_directory_artifact": {"path": rel(CPI_V2_DATA_DIR), "hash": artifact_hashes[rel(CPI_V2_DATA_DIR)]},
            "price_bundle": {"id": preregistration["price_cache_identifier"], "hash": preregistration["price_cache_bundle_hash"]},
            "frozen_universe_packet": {"id": preregistration["frozen_universe_id"], "logical_hash": preregistration["frozen_universe_hash"], "directory_hash": artifact_hashes[rel(UNIVERSE_DIR)]},
        },
        "mapping": [
            {
                "source_exposure": row["tradable_exposure_requirement"],
                "symbol": row["frozen_symbol_mapping"],
                "classification": row["mapping_classification"],
            }
            for row in mappings
        ],
        "artifact_hash_reconciliation": {
            path: {"expected": EXPECTED_ARTIFACT_HASHES[path], "observed": observed, "matches": observed == EXPECTED_ARTIFACT_HASHES[path]}
            for path, observed in artifact_hashes.items()
        },
    }
    lineage = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": CANONICAL_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "chain": [
            "phase2_public_signal_etf_mappable_candidate_intake_v2",
            "acquire_validate_freeze_phase2_public_signal_inputs_v1",
            "resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2",
            "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1",
            "run_spdj_dynamic_inflation_robustness_v1",
            TASK_ID,
        ],
        "correction_lineage": correction,
        "canonical_trial_id_preserved": correction["canonical_trial_id"] == CANONICAL_TRIAL_ID and correction["trial_id_changed"] is False,
        "strategy_rule_preserved_by_correction": correction["strategy_rule_changed"] is False,
        "robustness_reproduced_corrected_parent": robustness["parent_reproduction_pass"] is True,
        "new_trial_created": False,
        "strategy_variant_created": False,
    }
    implementation_integrity = {
        "status": "reconciled" if all(implementation_checks.values()) else "not_reconciled",
        "checks": implementation_checks,
        "canonical_code_path": rel(CANONICAL_CODE),
        "expected_code_hash": EXPECTED_CODE_HASH,
        "observed_code_hash": sha256_path(CANONICAL_CODE),
        "implementation_changed_by_task": False,
    }
    trial_accounting = {
        "parent_architecture_count": 1,
        "parent_canonical_configuration_count": 1,
        "parent_canonical_trial_count": 1,
        "robustness_trial_count": 1,
        "eligibility_decisions_created_by_task": 1,
        "new_canonical_trials": 0,
        "new_robustness_trials": 0,
        "strategy_variants": 0,
        "new_performance_calculations": 0,
        "evaluation_accesses": 0,
        "forward_observation_accesses": 0,
        "handoffs_executed": 0,
        "provider_calls": 0,
        "broker_calls": 0,
        "active_observation_mutations": 0,
    }
    decision = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": CANONICAL_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "eligibility_status": outcome,
        "eligibility_decision_timestamp": decision_timestamp,
        "source_contract_status": gates["gate_1_source_contract_complete"]["status"],
        "data_provenance_status": gates["gate_2_frozen_input_provenance_complete"]["status"],
        "canonical_trial_integrity_status": gates["gate_3_canonical_trial_integrity"]["status"],
        "robustness_integrity_status": gates["gate_4_robustness_integrity"]["status"],
        "implementation_integrity_status": gates["gate_5_implementation_integrity"]["status"],
        "handoff_specification_readiness": gates["gate_6_forward_handoff_specification_complete"]["status"],
        "blocking_caveat_count": blocking_count,
        "material_nonblocking_caveat_count": material_count,
        "minor_caveat_count": minor_count,
        "research_claim": "The frozen ETF-portability implementation passed its preregistered exploration and robustness research gates and is eligible for export to a separate forward-observation system for prospective paper/demo observation." if outcome.endswith("eligible_for_handoff") else "No eligibility claim is authorized.",
        "explicit_non_claims": [
            "alpha_is_proven",
            "future_profitability_is_established",
            "official_S&P_index_was_replicated",
            "strategy_is_safe",
            "broker_ready",
            "paper_execution_verified",
            "micro_live_ready",
            "real_money_approved",
        ],
        "parent_evidence_hashes": {"exploration": EXPECTED_EXPLORATION_HASH, "robustness": EXPECTED_ROBUSTNESS_HASH},
        "code_hash": EXPECTED_CODE_HASH,
        "CPI_dataset_id": "phase2_public_cpi_point_in_time_v2",
        "CPI_dataset_hash": EXPECTED_CPI_HASH,
        "price_bundle_hash": EXPECTED_PRICE_BUNDLE_HASH,
        "universe_id": "phase2_bounded_multi_asset_research_universe_v1",
        "universe_hash": EXPECTED_UNIVERSE_HASH,
        "next_action": next_action,
        "next_action_executed": False,
    }

    write_json(OUTPUT_DIR / "eligibility_gate_results.json", {"all_gates_pass": all_gates_pass, "gates": gates})
    write_json(OUTPUT_DIR / "lineage_reconciliation.json", lineage)
    write_json(OUTPUT_DIR / "source_and_data_reconciliation.json", source_and_data)
    write_json(OUTPUT_DIR / "exploration_reconciliation.json", exploration_reconciliation)
    write_json(OUTPUT_DIR / "robustness_reconciliation.json", robustness_reconciliation)
    write_json(OUTPUT_DIR / "implementation_integrity.json", implementation_integrity)
    write_csv(
        OUTPUT_DIR / "caveat_register.csv",
        caveats,
        ["caveat_id", "classification", "title", "finding", "handoff_requirement"],
    )
    write_json(OUTPUT_DIR / "handoff_specification_readiness.json", handoff_spec)
    write_json(OUTPUT_DIR / "eligibility_decision.json", decision)
    write_json(OUTPUT_DIR / "trial_accounting.json", trial_accounting)
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n\nNot executed by this task.\n", encoding="utf-8")
    report = f"""# S&P DJI Dynamic Inflation Research Eligibility

## Decision

- Outcome: `{outcome}`
- Strategy: `{STRATEGY_ID}`
- Exploration evidence: `{EXPECTED_EXPLORATION_HASH}`
- Robustness evidence: `{EXPECTED_ROBUSTNESS_HASH}`
- Six eligibility gates passed: `{str(all_gates_pass).lower()}`
- Blocking caveats: `{blocking_count}`
- Material nonblocking caveats: `{material_count}`
- Minor caveats: `{minor_count}`

## Scope

This is an evidence-only research eligibility decision. No performance was calculated, no trial or strategy variant was created, and no provider, broker, forward-observation, active-observation, or handoff operation occurred.

The eligible claim, when authorized, is limited to export of the frozen ETF-portability research package to a separate prospective paper/demo observation system. It is not an official S&P index replication, broker-readiness decision, execution verification, micro-live authorization, or real-money approval.

## Material Caveats

The evidence retains the ETF portability and source-proxy limitations, the higher full-history CAGR of the 60/40 control, block-specific control dominance, and the absence of an additional untouched historical holdout after evaluation. October 2025 remains an explicit no-release/no-rebalance event.

## Next Action

`{next_action}`

The next action was recorded but not executed.
"""
    (OUTPUT_DIR / "eligibility_report.md").write_text(report, encoding="utf-8")

    protected_after = snapshot(protected_paths())
    expected_existing_hashes_match = all(
        artifact_hashes.get(path) == expected for path, expected in EXPECTED_ARTIFACT_HASHES.items()
    )
    preliminary_hash = packet_hash()
    checks = {
        "parent_exploration_hash_unchanged": exploration["deterministic_evidence_hash"] == EXPECTED_EXPLORATION_HASH,
        "robustness_evidence_hash_unchanged": robustness["deterministic_evidence_hash"] == EXPECTED_ROBUSTNESS_HASH,
        "canonical_code_hash_unchanged": sha256_path(CANONICAL_CODE) == EXPECTED_CODE_HASH,
        "CPI_datasets_unchanged": component_hashes_match and artifact_hashes[rel(CPI_V1_DATA_DIR)] == EXPECTED_ARTIFACT_HASHES[rel(CPI_V1_DATA_DIR)] and artifact_hashes[rel(CPI_V2_DATA_DIR)] == EXPECTED_ARTIFACT_HASHES[rel(CPI_V2_DATA_DIR)],
        "price_cache_unchanged": individual_price_hashes_match,
        "universe_unchanged": universe_consistency["frozen_universe_hash"] == EXPECTED_UNIVERSE_HASH,
        "all_source_contracts_resolved": v2_readiness["unresolved_source_contract_count"] == 0,
        "eligibility_uses_no_new_performance_gate": True,
        "no_new_backtest_executed": trial_accounting["new_performance_calculations"] == 0,
        "no_optimization_executed": True,
        "no_evaluation_access_occurred": trial_accounting["evaluation_accesses"] == 0,
        "no_strategy_variant_created": trial_accounting["strategy_variants"] == 0,
        "no_broker_or_provider_call": trial_accounting["broker_calls"] == 0 and trial_accounting["provider_calls"] == 0,
        "no_forward_observation_access": trial_accounting["forward_observation_accesses"] == 0,
        "no_active_observation_mutation": trial_accounting["active_observation_mutations"] == 0,
        "no_handoff_export_executed": trial_accounting["handoffs_executed"] == 0,
        "protected_state_unchanged_during_task": protected_before == protected_after,
        "historical_artifact_hashes_reconcile": expected_existing_hashes_match,
        "all_required_artifacts_exist": all((OUTPUT_DIR / name).exists() for name in REQUIRED_OUTPUTS if name != "consistency_check.json"),
        "eligibility_outcome_matches_gates": (outcome == "spdj_dynamic_inflation_research_eligible_for_handoff") == (all_gates_pass and blocking_count == 0),
    }
    overall_pass = all(checks.values()) and all_gates_pass and outcome == "spdj_dynamic_inflation_research_eligible_for_handoff"
    consistency = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "overall_pass": overall_pass,
        "checks": checks,
        "deterministic_eligibility_packet_hash": preliminary_hash,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "trial_accounting": trial_accounting,
        "next_action": next_action,
        "required_outputs": list(REQUIRED_OUTPUTS),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
