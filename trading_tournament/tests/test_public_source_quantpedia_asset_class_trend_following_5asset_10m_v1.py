from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import public_source_quantpedia_asset_class_trend_following_5asset_10m_v1 as impl


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


def test_pre_implementation_gate_runs_before_backtesting_and_blocks() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["gate_ran_before_backtest"] is True
    assert gate["gate_decision"] == "prohibited_nearby_variant"
    assert gate["screening_outcome"] == "duplicate_or_prohibited_variant"
    assert gate["primary_failure_reason"] == "prohibited_nearby_variant"
    assert gate["implementation_allowed"] is False
    assert gate["backtest_allowed"] is False
    assert gate["backtest_run"] is False


def test_exact_economic_and_prohibited_duplicate_evidence_blocks() -> None:
    rows = read_csv("duplicate_and_closure_review.csv")
    by_id = {row["project_id"]: row for row in rows}
    assert by_id["faber_10m_sma_long_bil_portability_v1"]["classification"] == "prohibited_nearby_variant"
    assert by_id["faber_10m_sma_long_bil_portability_v1"]["blocks_implementation"] == "true"
    assert by_id["faber_taa"]["classification"] == "prohibited_nearby_variant"
    assert by_id["faber_taa"]["blocks_implementation"] == "true"
    assert by_id["gtaa_faber_style_benchmark_lane"]["blocks_implementation"] == "false"


def test_source_rules_incomplete_fields_are_recorded_as_secondary_blockers() -> None:
    missing = {row["requirement"]: row for row in read_csv("missing_requirements.csv")}
    assert missing["prohibited_nearby_variant_review"]["status"] == "blocking"
    assert missing["equal_signal_behavior"]["status"] == "unresolved_secondary_blocker"
    assert missing["missing_data_behavior"]["status"] == "unresolved_secondary_blocker"
    gate = read_json("pre_implementation_gate.json")
    assert gate["secondary_material_blockers"] == ["equal_signal_behavior", "missing_data_behavior"]


def test_public_page_is_not_copied_verbatim_or_as_full_page() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["public_page_copied_verbatim"] is False
    assert gate["full_public_page_stored"] is False
    assert gate["long_passages_stored"] is False
    text = (EVIDENCE / "blocker_report.md").read_text(encoding="utf-8")
    assert "https://quantpedia.com/strategies/asset-class-trend-following" not in text


def test_source_reported_performance_does_not_influence_selection_or_pass_fail() -> None:
    gate = read_json("pre_implementation_gate.json")
    assert gate["source_reported_performance_present"] is True
    assert gate["source_reported_performance_used_for_selection"] is False
    assert gate["source_reported_performance_used_for_pass_fail"] is False
    assert read_json("consistency_check.json")["source_reported_performance_used"] is False


def test_original_source_provenance_controls_frozen_rule_fields() -> None:
    packet = read_yaml("source_packet_used.yaml")
    rules = packet["rules"]
    assert rules["signal"]["provenance"] == "original_source_verified"
    assert rules["parameter"]["provenance"] == "original_source_verified"
    assert rules["entry"]["provenance"] == "original_source_verified"
    assert rules["exit"]["provenance"] == "original_source_verified"
    assert rules["weighting"]["provenance"] == "original_source_verified"
    assert rules["project_safe_execution"]["provenance"] == "project_execution_convention"


def test_frozen_parameters_and_universe_remain_unchanged() -> None:
    packet = read_yaml("source_packet_used.yaml")
    assert packet["rules"]["parameter"]["value"] == "10_month_sma"
    assert packet["universe"]["quantpedia_etf_translation"]["value"] == ["SPY", "EFA", "BND", "VNQ", "GSG"]
    assert packet["cash_proxy"]["project_translation"] == "BIL"
    gate = read_json("pre_implementation_gate.json")
    assert gate["instrument_substitution_performed"] is False
    assert gate["missing_data_silently_shrank_universe"] is False


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
    assert gate["broker_or_order_behavior"] is False
    assert gate["real_money_recommendation"] is False


def test_consistency_and_family_scope() -> None:
    consistency = read_json("consistency_check.json")
    gate = read_json("pre_implementation_gate.json")
    assert consistency["consistency_passed"] is True
    assert consistency["duplicate_or_prohibited_variant_blocked"] is True
    assert gate["family_status_after_gate"] == "broader_family_not_closed_by_this_task"
    assert gate["exact_variant_status_after_gate"] == "blocked_not_implemented"


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
