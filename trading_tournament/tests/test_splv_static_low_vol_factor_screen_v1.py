from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import splv_static_low_vol_factor_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "splv_static_low_vol_factor_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen_evidence() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_exist() -> None:
    required = {
        "source_intake_record.yaml",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "duplicate_gate.csv",
        "material_distinction_review.csv",
        "preregistration.yaml",
        "execution_manifest.json",
        "screening_summary.md",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "accounting_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_official_source_rules_are_preserved() -> None:
    intake = read_yaml("source_intake_record.yaml")
    rules = intake["source_supported_rules"]
    assert intake["source"]["source_id"] == screen.SOURCE_ID
    assert intake["source"]["source_class"] == "index_methodology_primary"
    assert rules["parent_universe"] == "S&P 500"
    assert rules["target_constituent_count"] == 100
    assert rules["volatility_window_trading_days"] == 252
    assert rules["volatility_definition"] == "standard deviation of daily price returns"
    assert "least volatile" in rules["selection"]
    assert rules["long_only"] is True
    assert rules["fully_invested_equity_index"] is True
    assert rules["source_defined_tactical_cash_or_bil_rule"] is False


def test_quantpedia_secondary_record_remains_unchanged() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["secondary_quantpedia_record_preserved"] is True
    assert manifest["secondary_quantpedia_hash_before"] == manifest["secondary_quantpedia_hash_after"]
    intake_path = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates" / "low_volatility_factor_proxy.yaml"
    quantpedia = yaml.safe_load(intake_path.read_text(encoding="utf-8"))
    assert quantpedia["source"]["source_id"] == screen.SECONDARY_QUANTPEDIA_ID
    assert quantpedia["source"]["source_evidence_public_context_only"] is True
    assert quantpedia["strategy_description"]["rule_clarity"] == "manual_input_required"


def test_splv_only_no_bil_tactical_or_active_vm_rule() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    assert manifest["candidate_instruments"] == ["SPLV"]
    assert manifest["splv_only"] is True
    assert manifest["uses_bil_or_cash_rule"] is False
    assert manifest["uses_tactical_signal"] is False
    assert manifest["uses_active_vm_rule"] is False
    assert manifest["uses_usmv_or_alternate_wrapper"] is False
    assert prereg["instrument"] == "SPLV"
    assert prereg["project_trading_rule"]["bil_or_cash_switch"] is False
    assert prereg["project_trading_rule"]["tactical_rebalance"] is False
    assert prereg["project_trading_rule"]["trend_filter"] is False
    assert prereg["project_trading_rule"]["volatility_target"] is False


def test_exact_duplicates_stop_execution_helper() -> None:
    duplicate = [
        {
            "uses_100pct_splv": True,
            "no_tactical_signal": True,
            "no_bil_or_cash_switch": True,
            "buy_and_hold_project_accounting": True,
            "matching_deterministic_sampled_windows": True,
            "comparable_costs_and_execution": True,
        }
    ]
    assert screen.exact_duplicate_exists(duplicate) is True
    assert screen.exact_duplicate_exists(screen.exact_duplicate_review()) is False
    gate_rows = read_csv("duplicate_gate.csv")
    assert all(row["duplicate_gate_outcome"] == "not_exact_duplicate" for row in gate_rows)


def test_window_generation_precedes_performance_and_is_deterministic() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    rows = read_csv("window_level_results.csv")
    candidate = [row for row in rows if row["strategy_id"] == screen.CANDIDATE_ID]
    assert manifest["windows_generated_before_performance"] is True
    assert prereg["windows"]["windows_generated_before_performance"] is True
    assert len(prereg["windows"]["window_records"]) == 10
    assert len(candidate) == 10
    assert {row["horizon_days"] for row in candidate} == {"90", "180"}
    assert all(row["generated_before_performance"] == "True" for row in candidate)


def test_no_provider_call_and_no_constituent_reconstruction() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["no_provider_call"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["constituent_level_index_reconstruction"] is False


def test_buy_and_hold_actual_etf_shares_and_no_quarterly_turnover() -> None:
    invariants = read_csv("accounting_invariants.csv")
    assert invariants
    assert all(row["actual_etf_shares_held_constant"] == "True" for row in invariants)
    assert all(row["no_artificial_daily_rebalance"] == "True" for row in invariants)
    assert all(row["no_artificial_quarterly_turnover"] == "True" for row in invariants)
    assert all(float(row["max_daily_exposure"]) <= 1.0 for row in invariants)
    assert all(float(row["max_daily_weight_sum"]) <= 1.0 for row in invariants)
    assert all(row["no_bil_cash_weight"] == "True" for row in invariants)


def test_active_vm_active_combo_and_registry_are_unchanged() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["registry_byte_identical"] is True
    assert manifest["registry_hash_before"] == manifest["registry_hash_after"]
    assert manifest["active_vm_state_unchanged"] is True
    assert manifest["active_combo_state_unchanged"] is True
    assert manifest["active_observations_hash_before"] == manifest["active_observations_hash_after"]
    assert manifest["active_combo_series_hash_before"] == manifest["active_combo_series_hash_after"]


def test_no_lifecycle_paper_demo_or_promotion_state_change() -> None:
    manifest = read_json("execution_manifest.json")
    outcome = read_json("screening_outcome.json")
    assert manifest["lifecycle_or_evidence_level_changed"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_authorized"] is False
    assert manifest["candidate_exhaustive_authorized"] is False
    assert manifest["robustness_authorized"] is False
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False


def test_result_is_allowed_and_memory_is_exact_variant_only() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert memory["candidate_id"] == screen.CANDIDATE_ID
    assert memory["broader_family_preserved"] == "True"
    assert memory["paper_demo_authorized"] == "False"
    assert memory["promotion_authorized"] == "False"


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["official_source_rules_preserved"] is True
    assert check["splv_only"] is True
    assert check["no_bil_or_tactical_rule_added"] is True
    assert check["no_active_vm_rule_borrowed"] is True
    assert check["window_generation_before_performance"] is True
    assert check["buy_and_hold_actual_etf_shares"] is True
    assert check["no_artificial_quarterly_turnover"] is True


def test_generation_is_deterministic() -> None:
    first_manifest = read_json("execution_manifest.json")
    first_outcome = read_json("screening_outcome.json")
    first_candidate_metrics = (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8")
    rerun = screen.run()
    second_manifest = read_json("execution_manifest.json")
    second_outcome = read_json("screening_outcome.json")
    second_candidate_metrics = (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_manifest == first_manifest
    assert second_outcome == first_outcome
    assert second_candidate_metrics == first_candidate_metrics
