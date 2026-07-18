from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import public_source_quantpedia_asset_class_momentum_rotational_top3_12m_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "public_source_strategy_implementation" / impl.STRATEGY_ID / "latest"
REGISTRY = ROOT / impl.REGISTRY_PATH
ACTIVE_OBSERVATIONS = ROOT / impl.ACTIVE_OBSERVATIONS_PATH


@pytest.fixture(scope="module", autouse=True)
def generated_gate() -> dict[str, object]:
    return impl.run(ROOT)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8")) or {}


def test_blocked_evidence_file_set_only() -> None:
    assert sorted(path.name for path in EVIDENCE.iterdir() if path.is_file()) == [
        "blocker_report.md",
        "consistency_check.json",
        "duplicate_and_closure_review.csv",
        "missing_requirements.csv",
        "pre_implementation_gate.json",
        "source_packet_used.yaml",
    ]
    assert not (EVIDENCE / "candidate_metrics.csv").exists()
    assert not (EVIDENCE / "benchmark_metrics.csv").exists()
    assert not (EVIDENCE / "window_level_results.csv").exists()


def test_pre_implementation_gate_runs_before_backtesting_and_blocks() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["pre_implementation_gate_completed"] is True
    assert gate["gate_ran_before_backtest"] is True
    assert gate["gate_decision"] == "source_rules_incomplete"
    assert gate["screening_outcome"] == "source_rules_incomplete"
    assert gate["primary_failure_reason"] == "source_rules_incomplete"
    assert gate["implementation_ready"] is False
    assert gate["implementation_allowed"] is False
    assert gate["backtest_allowed"] is False
    assert gate["backtest_run"] is False


def test_same_family_material_distinction_does_not_authorize_implementation() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["source_packet_duplicate_status"] == "same_family_materially_distinct"
    assert gate["same_family_materially_distinct"] is True
    assert gate["exact_duplicate_found"] is False
    assert gate["economic_duplicate_found"] is False
    assert gate["prohibited_nearby_variant_found"] is False
    assert gate["source_packet_control_decision"] == "create_intake_record_only"
    assert gate["source_packet_says_no_codex_implementation_prompt_should_run"] is True


def test_external_library_and_queue_gates_block_direct_implementation() -> None:
    gate = read_json("pre_implementation_gate.json")
    rows = read_csv("duplicate_and_closure_review.csv")
    by_id = {row["project_id"]: row for row in rows}
    assert gate["quantpedia_free_library_intake_required"] is True
    assert gate["quantpedia_free_capture_status"] == "authorized_quantpedia_capture_required"
    assert gate["external_source_queue_authorizes_strategy_implementation"] is False
    assert by_id["quantpedia_free_v1"]["classification"] == "library_intake_required_before_implementation"
    assert by_id["quantpedia_free_v1"]["blocks_implementation"] == "true"
    assert by_id["external_source_discovery_lane"]["classification"] == "strategy_implementation_unauthorized_by_current_queue"
    assert by_id["external_source_discovery_lane"]["blocks_implementation"] == "true"


def test_related_prior_candidates_are_reviewed_without_closing_family() -> None:
    rows = read_csv("duplicate_and_closure_review.csv")
    by_id = {row["project_id"]: row for row in rows}
    assert by_id["qqq_spy_gld_ief_dual_momentum_v1"]["classification"] == "same_family_materially_distinct_not_exact_duplicate"
    assert by_id["asset_class_tsmom_top2_v1"]["classification"] == "related_prior_family_not_exact_duplicate"
    assert by_id["value_momentum_factor_etf_rotation_v1"]["classification"] == "related_duplicate_risk_not_exact_duplicate"
    assert by_id["qqq_spy_gld_ief_dual_momentum_v1"]["blocks_implementation"] == "false"
    gate = read_json("pre_implementation_gate.json")
    assert gate["family_status_after_gate"] == "family_not_closed_by_this_task"
    assert gate["exact_variant_status_after_gate"] == "blocked_not_implemented"


def test_source_rules_incomplete_fields_are_recorded() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["unresolved_material_fields"] == [
        "original_source_confirmation_of_exact_etf_translation",
        "tie_handling",
        "missing_data_behavior",
        "precise_original_execution_timestamp",
        "authorization_to_use_frozen_reserve_wrappers",
    ]
    missing = {row["requirement"]: row for row in read_csv("missing_requirements.csv")}
    assert missing["tie_handling"]["status"] == "unresolved_material_rule"
    assert missing["missing_data_behavior"]["status"] == "unresolved_material_rule"
    assert missing["authorization_to_use_frozen_reserve_wrappers"]["status"] == "blocking"


def test_public_page_is_not_copied_verbatim_or_as_full_page() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["public_page_copied_verbatim"] is False
    assert gate["full_public_page_stored"] is False
    assert gate["long_passages_stored"] is False
    text = (EVIDENCE / "blocker_report.md").read_text(encoding="utf-8")
    assert "Momentum Asset Allocation Strategy - Quantpedia" not in text
    assert "indicative annual performance" not in text.lower()


def test_source_reported_performance_does_not_influence_selection_or_pass_fail() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["source_reported_performance_present"] is True
    assert gate["source_reported_performance_used_for_selection"] is False
    assert gate["source_reported_performance_used_for_pass_fail"] is False
    assert read_json("consistency_check.json")["source_reported_performance_used"] is False


def test_source_packet_provenance_controls_frozen_rule_fields() -> None:
    packet = read_yaml("source_packet_used.yaml")
    rules = packet["rules"]
    assert rules["signal"]["provenance"] == "public_page_explicit"
    assert rules["signal_formula"]["provenance"] == "mechanical_translation"
    assert rules["selected_assets"]["provenance"] == "public_page_explicit"
    assert rules["weighting"]["provenance"] == "public_page_explicit"
    assert rules["rebalance"]["provenance"] == "public_page_explicit"
    assert rules["execution_timestamp"]["provenance"] == "project_execution_convention"
    assert rules["tie_handling"]["provenance"] == "unresolved"


def test_frozen_parameters_and_universe_remain_unchanged() -> None:
    packet = read_yaml("source_packet_used.yaml")
    rules = packet["rules"]
    assert packet["universe"]["value"] == ["SPY", "EFA", "BND", "VNQ", "GSG"]
    assert rules["signal"]["value"] == "trailing_12_month_total_return_rank"
    assert rules["selected_assets"]["value"] == 3
    assert rules["weighting"]["value"] == "equal_one_third_each"
    assert rules["cash_behavior"]["value"] == "no_cash_filter_fully_invested_top_3"
    gate = read_json("pre_implementation_gate.json")
    assert gate["instrument_substitution_performed"] is False
    assert gate["missing_data_silently_shrank_universe"] is False


def test_cache_is_checked_but_reserve_wrappers_still_need_authorization() -> None:
    gate = read_json("pre_implementation_gate.json")
    cache_rows = {row["symbol"]: row for row in gate["cache_availability"]}
    assert set(cache_rows) == {"SPY", "EFA", "BND", "VNQ", "GSG"}
    assert gate["local_cache_available_for_full_source_universe"] is True
    assert cache_rows["BND"]["role"] == "frozen_reserve_snapshot"
    assert cache_rows["VNQ"]["role"] == "frozen_reviewed_nonprimary_snapshot"
    assert cache_rows["GSG"]["role"] == "frozen_reserve_snapshot"
    assert gate["reserve_wrapper_authorization_required"] is True


def test_no_unregistered_parameter_variants_strategy_logic_or_backtest() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["strategy_logic_written"] is False
    assert gate["unregistered_parameter_variants_run"] is False
    assert gate["parameter_optimization_run"] is False
    assert gate["candidate_metrics_created"] is False
    assert gate["benchmark_metrics_created"] is False


def test_registry_active_observations_and_broker_paths_unchanged() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["registry_hash_before"] == sha256(REGISTRY)
    assert gate["registry_hash_after"] == sha256(REGISTRY)
    assert gate["active_observations_hash_before"] == sha256(ACTIVE_OBSERVATIONS)
    assert gate["active_observations_hash_after"] == sha256(ACTIVE_OBSERVATIONS)
    assert gate["paper_demo_activation"] is False
    assert gate["candidate_exhaustive_run"] is False
    assert gate["broker_or_order_behavior"] is False
    assert gate["real_money_recommendation"] is False


def test_consistency_check_passes_strict_scope() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["gate_ran_before_backtest"] is True
    assert consistency["implementation_allowed"] is False
    assert consistency["backtest_run"] is False
    assert consistency["candidate_metrics_created"] is False
    assert consistency["benchmark_metrics_created"] is False
    assert consistency["source_rules_incomplete_blocked"] is True
    assert consistency["registry_unchanged"] is True
    assert consistency["active_observations_unchanged"] is True


def test_output_generation_is_deterministic() -> None:
    names = [
        "source_packet_used.yaml",
        "pre_implementation_gate.json",
        "duplicate_and_closure_review.csv",
        "missing_requirements.csv",
        "blocker_report.md",
        "consistency_check.json",
    ]
    before = {name: sha256(EVIDENCE / name) for name in names}
    impl.run(ROOT)
    after = {name: sha256(EVIDENCE / name) for name in names}
    assert before == after
