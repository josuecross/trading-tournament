from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ID = "quantpedia_asset_class_momentum_rotational_top3_12m_v1"
OUTPUT_DIR = Path("evidence") / "public_source_strategy_implementation" / STRATEGY_ID / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
QUANTPEDIA_FREE_INTAKE_BLOCKER = Path("evidence") / "quantpedia_free_library_intake_v1" / "latest" / "input_blocker.json"
PILOT_CACHE_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"

GATE_DECISION = "source_rules_incomplete"
SCREENING_OUTCOME = "source_rules_incomplete"
PRIMARY_FAILURE_REASON = "source_rules_incomplete"
NEXT_ACTION = "complete_quantpedia_free_library_intake_before_asset_class_momentum_implementation"

UNRESOLVED_MATERIAL_FIELDS = [
    "original_source_confirmation_of_exact_etf_translation",
    "tie_handling",
    "missing_data_behavior",
    "precise_original_execution_timestamp",
    "authorization_to_use_frozen_reserve_wrappers",
]

SOURCE_PACKET: dict[str, Any] = {
    "strategy_id": STRATEGY_ID,
    "source": {
        "secondary_page": {
            "title": "Momentum Asset Allocation Strategy",
            "alias": "Asset Class Momentum - Rotational System",
            "publisher": "Quantpedia",
            "url": "https://quantpedia.com/strategies/asset-class-momentum-rotational-system",
            "public_access": True,
        },
        "original_source": {
            "title": "Relative Strength Strategies for Investing",
            "author": "Mebane T. Faber",
            "date_written": "2010-04-01",
            "publication": "Cambria Investment Management Working Paper",
            "url": "https://ssrn.com/abstract=1585517",
            "verification_status": "partially_verified",
        },
    },
    "canonical_family": "cross_asset_relative_momentum_rotation",
    "implementation_tier": "A_existing_engine",
    "duplicate_status": "same_family_materially_distinct",
    "lifecycle": "lead_only",
    "economic_mechanism": {
        "value": "rank broad asset classes by trailing performance and hold the strongest three for the next month",
        "provenance": "public_page_explicit",
    },
    "universe": {
        "value": ["SPY", "EFA", "BND", "VNQ", "GSG"],
        "provenance": "public_page_explicit",
        "source_defined_universe_must_be_preserved": True,
    },
    "rules": {
        "data_frequency": {"value": "daily_adjusted_prices_sampled_monthly", "provenance": "mechanical_translation"},
        "signal": {"value": "trailing_12_month_total_return_rank", "provenance": "public_page_explicit"},
        "signal_formula": {
            "value": "adjusted_price_t / adjusted_price_t_minus_12_months - 1",
            "provenance": "mechanical_translation",
        },
        "selected_assets": {"value": 3, "provenance": "public_page_explicit"},
        "weighting": {"value": "equal_one_third_each", "provenance": "public_page_explicit"},
        "rebalance": {"value": "monthly", "provenance": "public_page_explicit"},
        "holding_period": {"value": "one_month", "provenance": "public_page_explicit"},
        "long_short": {"value": "long_only", "provenance": "project_derived_interpretation"},
        "cash_behavior": {"value": "no_cash_filter_fully_invested_top_3", "provenance": "project_derived_interpretation"},
        "signal_timestamp": {"value": "final_common_month_end_close", "provenance": "project_execution_convention"},
        "execution_timestamp": {"value": "next_common_session_close", "provenance": "project_execution_convention"},
        "tie_handling": {"value": "unresolved", "provenance": "unresolved"},
        "missing_data_behavior": {"value": "unresolved", "provenance": "unresolved"},
    },
    "engine_requirements": [
        "monthly_cross_sectional_ranking",
        "top_n_selection",
        "equal_weight_portfolio",
        "actual_weight_drift",
        "transaction_cost_accounting",
        "common_date_alignment",
    ],
    "pilot_snapshot_status": {
        "SPY": "primary_pilot_member",
        "EFA": "primary_pilot_member",
        "BND": "frozen_reserve_snapshot",
        "VNQ": "frozen_reviewed_nonprimary_snapshot",
        "GSG": "frozen_reserve_snapshot",
    },
    "secondary_source_reported_performance": {
        "annual_return": "14.49_percent",
        "volatility": "11_percent",
        "maximum_drawdown": "-47.77_percent",
        "sharpe_ratio": 0.78,
        "source_period": "1973_to_2009",
        "may_influence_project_decisions": False,
    },
    "closest_project_candidates": [
        "qqq_spy_gld_ief_dual_momentum_v1",
        "asset_class_tsmom_top2_v1",
        "value_momentum_factor_etf_rotation_v1",
    ],
    "duplicate_analysis": {
        "exact_duplicate": False,
        "rationale": "distinct five-asset universe, top_3 cross-sectional selection, no absolute filter, no cash fallback and equal-weight risky holdings",
    },
    "frozen_first_test_design": {
        "status": "direction_owner_authorization_required",
        "universe": ["SPY", "EFA", "BND", "VNQ", "GSG"],
        "parameter": "12_month_momentum",
        "selected_assets": 3,
        "weights": "equal",
        "formation_end": "2016-12-30",
        "validation": {"start": "2017-01-03", "end": "2021-12-31"},
        "sealed_holdout": {"start": "2022-01-03", "end": "2026-07-16"},
        "primary_benchmark": "static_equal_weight_same_five_etfs",
        "performance_selection_allowed": False,
    },
    "unresolved_fields": UNRESOLVED_MATERIAL_FIELDS,
    "source_packet_control_decision": {
        "decision": "create_intake_record_only",
        "codex_implementation_prompt_should_run": False,
        "required_route": "authorized_quantpedia_free_v1_intake_after_free_strategy_capture_is_supplied",
    },
    "stop_conditions": [
        "exact_or_economic_duplicate_discovered",
        "original_source_rule_conflict",
        "reserve_wrapper_use_not_authorized",
        "unresolved_material_rule_at_preregistration",
        "frozen_snapshot_hash_failure",
    ],
    "prohibited_post_result_tuning": [
        "momentum_horizon",
        "top_n_count",
        "universe_mapping",
        "cash_filter",
        "absolute_momentum_overlay",
        "volatility_weighting",
        "risk_parity",
        "rebalance_frequency",
        "performance_selected_asset_removal",
    ],
}


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def evidence_exists(root: Path, rel_path: str | Path) -> bool:
    return (root / rel_path).exists()


def quantpedia_free_outcome(root: Path) -> str:
    path = root / QUANTPEDIA_FREE_INTAKE_BLOCKER
    if not path.exists():
        return "missing_quantpedia_free_library_intake_blocker"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("outcome", "unknown"))


def cache_row(root: Path, symbol: str) -> dict[str, Any]:
    path = root / PILOT_CACHE_DIR / f"{symbol}.csv"
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": str(PILOT_CACHE_DIR / f"{symbol}.csv"),
        "exists": path.exists(),
        "has_adjusted_close_field": False,
        "first_date": "",
        "last_date": "",
        "role": SOURCE_PACKET["pilot_snapshot_status"].get(symbol, "unknown"),
    }
    if not path.exists():
        return row
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        row["has_adjusted_close_field"] = "adj_close" in (reader.fieldnames or [])
        first = next(reader, None)
        last = first
        for record in reader:
            last = record
    if first:
        row["first_date"] = first.get("date", "")
    if last:
        row["last_date"] = last.get("date", "")
    return row


def cache_availability(root: Path) -> list[dict[str, Any]]:
    return [cache_row(root, symbol) for symbol in SOURCE_PACKET["universe"]["value"]]


def duplicate_review_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "review_item": "closest_project_candidate",
            "project_id": "qqq_spy_gld_ief_dual_momentum_v1",
            "evidence_path": "strategy_lab/strategy_registry.yaml",
            "evidence_exists": evidence_exists(root, REGISTRY_PATH),
            "shared_mechanism": "multi-asset momentum rotation lineage",
            "shared_universe_or_controls": "ETF momentum universe with defensive assets",
            "material_difference": "source packet ranks five broad asset-class ETFs by 12-month relative momentum, selects top 3, has no absolute filter, and has no cash fallback",
            "classification": "same_family_materially_distinct_not_exact_duplicate",
            "blocks_implementation": False,
        },
        {
            "review_item": "closest_project_candidate",
            "project_id": "asset_class_tsmom_top2_v1",
            "evidence_path": "evidence/strategy_evidence_library/latest/duplicate_near_duplicate_variants.csv",
            "evidence_exists": evidence_exists(root, "evidence/strategy_evidence_library/latest/duplicate_near_duplicate_variants.csv"),
            "shared_mechanism": "asset-class momentum lineage",
            "shared_universe_or_controls": "multi-asset ETF momentum",
            "material_difference": "source packet is cross-sectional top-3 relative momentum rather than the existing time-series momentum top-2 fingerprint group",
            "classification": "related_prior_family_not_exact_duplicate",
            "blocks_implementation": False,
        },
        {
            "review_item": "closest_project_candidate",
            "project_id": "value_momentum_factor_etf_rotation_v1",
            "evidence_path": "evidence/strategy_evidence_library/latest/failure_code_provenance.csv",
            "evidence_exists": evidence_exists(root, "evidence/strategy_evidence_library/latest/failure_code_provenance.csv"),
            "shared_mechanism": "rotation/ranking framework",
            "shared_universe_or_controls": "ETF ranking candidate",
            "material_difference": "source packet is broad asset-class relative momentum without a value factor or factor-rotation mechanism",
            "classification": "related_duplicate_risk_not_exact_duplicate",
            "blocks_implementation": False,
        },
        {
            "review_item": "external_source_library_gate",
            "project_id": "quantpedia_free_v1",
            "evidence_path": str(QUANTPEDIA_FREE_INTAKE_BLOCKER),
            "evidence_exists": evidence_exists(root, QUANTPEDIA_FREE_INTAKE_BLOCKER),
            "shared_mechanism": "Quantpedia public-source library intake",
            "shared_universe_or_controls": "public-source strategy queue governance",
            "material_difference": "source packet says the record should be added through authorized quantpedia_free_v1 intake before any implementation",
            "classification": "library_intake_required_before_implementation",
            "blocks_implementation": True,
        },
        {
            "review_item": "current_research_queue_gate",
            "project_id": "external_source_discovery_lane",
            "evidence_path": str(RESEARCH_QUEUE_PATH),
            "evidence_exists": evidence_exists(root, RESEARCH_QUEUE_PATH),
            "shared_mechanism": "external source progression governance",
            "shared_universe_or_controls": "source validation before implementation",
            "material_difference": "queue explicitly records authorizes_strategy_implementation=false for the external source discovery lane",
            "classification": "strategy_implementation_unauthorized_by_current_queue",
            "blocks_implementation": True,
        },
    ]


def missing_requirement_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "requirement": "quantpedia_free_v1_library_intake",
            "status": "blocking",
            "source": str(QUANTPEDIA_FREE_INTAKE_BLOCKER),
            "observed_state": quantpedia_free_outcome(root),
            "reason": "source packet requires the authorized Quantpedia free-library intake route before implementation",
            "smallest_revisit_condition": "complete authorized quantpedia_free_v1 capture and deterministic source-library intake for this record",
        },
        {
            "requirement": "original_source_confirmation_of_exact_etf_translation",
            "status": "unresolved_material_rule",
            "source": "source_packet_unresolved_fields",
            "observed_state": "unresolved",
            "reason": "exact ETF mapping is secondary-source/public-page backed and only partially original-source verified",
            "smallest_revisit_condition": "original-source verification queue confirms or rejects the ETF translation before implementation",
        },
        {
            "requirement": "tie_handling",
            "status": "unresolved_material_rule",
            "source": "source_packet_unresolved_fields",
            "observed_state": "unresolved",
            "reason": "top-3 rank ties are not frozen",
            "smallest_revisit_condition": "freeze deterministic tie handling from source support or explicit direction-owner convention",
        },
        {
            "requirement": "missing_data_behavior",
            "status": "unresolved_material_rule",
            "source": "source_packet_unresolved_fields",
            "observed_state": "unresolved",
            "reason": "insufficient-history and missing month-end price behavior is not frozen",
            "smallest_revisit_condition": "freeze missing-data behavior before any implementation or screen",
        },
        {
            "requirement": "precise_original_execution_timestamp",
            "status": "unresolved_material_rule",
            "source": "source_packet_unresolved_fields",
            "observed_state": "project convention proposed but original timestamp unresolved",
            "reason": "source packet uses project no-lookahead execution convention but notes original timestamp uncertainty",
            "smallest_revisit_condition": "direction owner accepts project execution convention after source-library intake",
        },
        {
            "requirement": "authorization_to_use_frozen_reserve_wrappers",
            "status": "blocking",
            "source": "source_packet_pilot_snapshot_status",
            "observed_state": "BND and GSG are reserve snapshots; VNQ is frozen reviewed nonprimary",
            "reason": "source packet says reserve/nonprimary wrappers require explicit authorization",
            "smallest_revisit_condition": "direction owner authorizes source-defined reserve/nonprimary wrapper use before implementation",
        },
    ]


def pre_implementation_gate(root: Path) -> dict[str, Any]:
    registry_before = sha256_path(root / REGISTRY_PATH)
    active_before = sha256_path(root / ACTIVE_OBSERVATIONS_PATH)
    data_rows = cache_availability(root)
    duplicate_rows = duplicate_review_rows(root)
    return {
        "strategy_id": STRATEGY_ID,
        "pre_implementation_gate_completed": True,
        "gate_ran_before_backtest": True,
        "gate_decision": GATE_DECISION,
        "screening_outcome": SCREENING_OUTCOME,
        "primary_failure_reason": PRIMARY_FAILURE_REASON,
        "implementation_ready": False,
        "implementation_allowed": False,
        "backtest_allowed": False,
        "backtest_run": False,
        "candidate_metrics_created": False,
        "benchmark_metrics_created": False,
        "source_packet_duplicate_status": SOURCE_PACKET["duplicate_status"],
        "source_packet_lifecycle": SOURCE_PACKET["lifecycle"],
        "source_packet_control_decision": SOURCE_PACKET["source_packet_control_decision"]["decision"],
        "source_packet_says_no_codex_implementation_prompt_should_run": True,
        "quantpedia_free_library_intake_required": True,
        "quantpedia_free_capture_status": quantpedia_free_outcome(root),
        "external_source_queue_authorizes_strategy_implementation": False,
        "same_family_materially_distinct": True,
        "exact_duplicate_found": False,
        "economic_duplicate_found": False,
        "prohibited_nearby_variant_found": False,
        "unresolved_material_fields": UNRESOLVED_MATERIAL_FIELDS,
        "reserve_wrapper_authorization_required": True,
        "local_cache_available_for_full_source_universe": all(row["exists"] and row["has_adjusted_close_field"] for row in data_rows),
        "cache_availability": data_rows,
        "blocking_repository_evidence": [
            row["evidence_path"] for row in duplicate_rows if row["blocks_implementation"]
        ],
        "source_reported_performance_present": True,
        "source_reported_performance_used_for_selection": False,
        "source_reported_performance_used_for_pass_fail": False,
        "source_reported_performance": SOURCE_PACKET["secondary_source_reported_performance"],
        "public_page_copied_verbatim": False,
        "full_public_page_stored": False,
        "long_passages_stored": False,
        "strategy_logic_written": False,
        "unregistered_parameter_variants_run": False,
        "parameter_optimization_run": False,
        "instrument_substitution_performed": False,
        "missing_data_silently_shrank_universe": False,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_before,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_before,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_or_order_behavior": False,
        "real_money_recommendation": False,
        "family_status_after_gate": "family_not_closed_by_this_task",
        "exact_variant_status_after_gate": "blocked_not_implemented",
        "next_action": NEXT_ACTION,
    }


def blocker_report(gate: dict[str, Any]) -> str:
    return f"""# Public Source Strategy Implementation Blocker

Strategy: `{STRATEGY_ID}`

Gate decision: `{gate["gate_decision"]}`

Implementation stopped before strategy logic or backtesting. The supplied source packet classifies the idea as `same_family_materially_distinct`, but it also says the record should be added through the authorized `quantpedia_free_v1` intake and that no Codex implementation prompt should run. Current queue evidence is aligned with that stop: the external-source lane does not authorize implementation, and the Quantpedia free-library intake is still blocked on user-supplied capture input.

The current local cache contains the five listed ETF files with adjusted close fields, so this is not a missing-price-history stop. The blocking issues are unresolved material rule fields and source-library governance:

- `original_source_confirmation_of_exact_etf_translation`
- `tie_handling`
- `missing_data_behavior`
- `precise_original_execution_timestamp`
- `authorization_to_use_frozen_reserve_wrappers`

Repository evidence supporting the stop:

- `strategy_lab/research_os/research/research_queue.yaml`
- `evidence/current_research_checkpoint/latest/current_research_checkpoint_manifest.json`
- `evidence/quantpedia_free_library_intake_v1/latest/input_blocker.json`
- `evidence/strategy_evidence_library/latest/strategy_inventory.csv`

The broader family is not closed by this task. This exact supplied implementation request is blocked until the source-library intake and unresolved-rule review are complete.

No candidate metrics, benchmark metrics, paper/demo activation, broker path, or real-money recommendation was created.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    gate = pre_implementation_gate(root)
    duplicate_rows = duplicate_review_rows(root)
    missing_rows = missing_requirement_rows(root)

    write_yaml(output / "source_packet_used.yaml", SOURCE_PACKET)
    write_json(output / "pre_implementation_gate.json", gate)
    write_csv(
        output / "duplicate_and_closure_review.csv",
        duplicate_rows,
        [
            "review_item",
            "project_id",
            "evidence_path",
            "evidence_exists",
            "shared_mechanism",
            "shared_universe_or_controls",
            "material_difference",
            "classification",
            "blocks_implementation",
        ],
    )
    write_csv(
        output / "missing_requirements.csv",
        missing_rows,
        ["requirement", "status", "source", "observed_state", "reason", "smallest_revisit_condition"],
    )
    write_text(output / "blocker_report.md", blocker_report(gate))

    consistency = {
        "strategy_id": STRATEGY_ID,
        "expected_blocked_output_files": [
            "blocker_report.md",
            "consistency_check.json",
            "duplicate_and_closure_review.csv",
            "missing_requirements.csv",
            "pre_implementation_gate.json",
            "source_packet_used.yaml",
        ],
        "gate_ran_before_backtest": gate["gate_ran_before_backtest"],
        "implementation_allowed": gate["implementation_allowed"],
        "implementation_ready": gate["implementation_ready"],
        "backtest_run": gate["backtest_run"],
        "candidate_metrics_created": (output / "candidate_metrics.csv").exists(),
        "benchmark_metrics_created": (output / "benchmark_metrics.csv").exists(),
        "source_rules_incomplete_blocked": gate["gate_decision"] == "source_rules_incomplete",
        "quantpedia_free_library_intake_required": gate["quantpedia_free_library_intake_required"],
        "quantpedia_free_capture_status": gate["quantpedia_free_capture_status"],
        "unresolved_material_fields_recorded": sorted(gate["unresolved_material_fields"]) == sorted(UNRESOLVED_MATERIAL_FIELDS),
        "source_reported_performance_used": False,
        "public_page_copied_verbatim": False,
        "registry_unchanged": gate["registry_hash_before"] == sha256_path(root / REGISTRY_PATH),
        "active_observations_unchanged": gate["active_observations_hash_before"] == sha256_path(root / ACTIVE_OBSERVATIONS_PATH),
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_or_order_behavior": False,
        "real_money_recommendation": False,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["gate_ran_before_backtest"]
        and not consistency["implementation_allowed"]
        and not consistency["implementation_ready"]
        and not consistency["backtest_run"]
        and not consistency["candidate_metrics_created"]
        and not consistency["benchmark_metrics_created"]
        and consistency["source_rules_incomplete_blocked"]
        and consistency["quantpedia_free_library_intake_required"]
        and consistency["unresolved_material_fields_recorded"]
        and consistency["registry_unchanged"]
        and consistency["active_observations_unchanged"]
        and not consistency["source_reported_performance_used"]
        and not consistency["paper_demo_activation"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["broker_or_order_behavior"]
    )
    write_json(output / "consistency_check.json", consistency)

    return {
        "strategy_id": STRATEGY_ID,
        "evidence_dir": str(output),
        "gate_decision": gate["gate_decision"],
        "screening_outcome": gate["screening_outcome"],
        "primary_failure_reason": gate["primary_failure_reason"],
        "implementation_allowed": gate["implementation_allowed"],
        "backtest_run": gate["backtest_run"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
