from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import qual_static_quality_factor_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "qual_static_quality_factor_screen_v1" / "latest"


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
        "cache_feasibility.csv",
        "preregistration.yaml",
        "execution_manifest.json",
        "window_definitions.csv",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "accounting_invariants.csv",
        "screening_summary.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_exactly_one_external_source_and_qual_only() -> None:
    intake = read_yaml("source_intake_record.yaml")
    manifest = read_json("execution_manifest.json")
    assert intake["source"]["source_id"] == screen.SOURCE_ID
    assert intake["source"]["source_class"] == "index_methodology_and_direct_etf_wrapper"
    assert intake["source"]["etf_wrapper"] == "QUAL"
    assert manifest["source_id"] == screen.SOURCE_ID
    assert manifest["candidate_instrument"] == "QUAL"
    assert manifest["candidate_instrument_count"] == 1
    assert manifest["qual_only"] is True
    assert manifest["constituent_level_index_reconstruction"] is False


def test_cache_is_existing_local_cache_without_refresh() -> None:
    cache_rows = read_csv("cache_feasibility.csv")
    manifest = read_json("execution_manifest.json")
    assert len(cache_rows) == 1
    cache = cache_rows[0]
    assert cache["symbol"] == "QUAL"
    assert cache["cache_path"] == "data/cache/QUAL.csv"
    assert cache["cache_available"] == "true"
    assert cache["cache_status"] == "cache_ready"
    assert cache["provider_download_required"] == "false"
    assert manifest["no_provider_call"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False


def test_no_bil_trend_volatility_ranking_or_active_vm_rule_added() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    trading_rule = prereg["trading_rule"]
    assert manifest["uses_bil_or_cash_rule"] is False
    assert manifest["uses_tactical_signal"] is False
    assert manifest["uses_active_vm_rule"] is False
    assert manifest["uses_volatility_target"] is False
    assert manifest["uses_ranking_rule"] is False
    assert trading_rule["bil_or_cash_switch"] is False
    assert trading_rule["trend_or_moving_average_rule"] is False
    assert trading_rule["volatility_target"] is False
    assert trading_rule["leverage"] is False
    assert trading_rule["shorting"] is False


def test_exact_duplicate_detection_stops_redundant_execution_helper() -> None:
    duplicate = [
        {
            "uses_100pct_qual": True,
            "no_cross_etf_ranking": True,
            "no_volatility_targeting": True,
            "no_trend_filter": True,
            "no_bil_transition": True,
            "static_etf_share_holdings": True,
            "matching_or_equivalent_sampled_window_evaluation": True,
            "correct_drift_aware_accounting": True,
        }
    ]
    assert screen.exact_duplicate_exists(duplicate) is True
    gate_rows = screen.duplicate_gate_rows()
    assert screen.exact_duplicate_exists(gate_rows) is False
    assert all(row["duplicate_gate_outcome"] == "no_exact_duplicate" for row in gate_rows)


def test_windows_generated_before_performance_and_are_complete() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    windows = read_csv("window_definitions.csv")
    candidate = [row for row in read_csv("window_level_results.csv") if row["strategy_id"] == screen.CANDIDATE_ID]
    assert manifest["windows_generated_before_performance"] is True
    assert prereg["windows"]["generated_before_performance"] is True
    assert len(windows) == 10
    assert len(prereg["windows"]["window_records"]) == 10
    assert len(candidate) == 10
    assert {row["horizon_days"] for row in candidate} == {"90", "180"}
    assert all(row["generated_before_performance"] == "true" for row in windows)


def test_actual_etf_shares_and_no_index_turnover() -> None:
    invariants = read_csv("accounting_invariants.csv")
    assert len(invariants) == 10
    assert all(row["actual_etf_shares_held_constant"] == "true" for row in invariants)
    assert all(row["no_constant_target_daily_rebalance"] == "true" for row in invariants)
    assert all(row["no_artificial_index_rebalance_turnover"] == "true" for row in invariants)
    assert all(row["no_bil_cash_weight"] == "true" for row in invariants)
    assert all(float(row["max_daily_exposure"]) <= 1.0 for row in invariants)
    assert all(float(row["max_daily_weight_sum"]) <= 1.0 for row in invariants)
    assert all(row["invariant_passed"] == "true" for row in invariants)


def test_benchmarks_use_matching_dates_for_each_window() -> None:
    rows = read_csv("window_level_results.csv")
    expected_ids = set(screen.BENCHMARK_IDS) | {screen.CANDIDATE_ID}
    by_window: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        assert row["window_valid"] == "true"
        key = (row["horizon_days"], row["window_start"], row["window_end"])
        by_window.setdefault(key, set()).add(row["strategy_id"])
    assert len(by_window) == 10
    assert all(strategy_ids == expected_ids for strategy_ids in by_window.values())


def test_registry_active_observations_and_active_combo_are_unchanged() -> None:
    outcome = read_json("screening_outcome.json")
    consistency = read_json("consistency_check.json")
    assert outcome["registry_byte_identical"] is True
    assert outcome["registry_hash_before"] == outcome["registry_hash_after"]
    assert outcome["active_observations_unchanged"] is True
    assert outcome["active_observations_hash_before"] == outcome["active_observations_hash_after"]
    assert outcome["active_combo_unchanged"] is True
    assert outcome["active_combo_series_hash_before"] == outcome["active_combo_series_hash_after"]
    assert consistency["registry_byte_identical"] is True
    assert consistency["active_observations_unchanged"] is True


def test_no_lifecycle_paper_demo_or_promotion_state_change() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["robustness_authorized"] is False
    assert memory["canonical_lifecycle_status_modified"] == "false"
    assert memory["paper_demo_authorized"] == "false"
    assert memory["promotion_authorized"] == "false"


def test_result_is_allowed_and_exact_variant_memory_only_when_weak() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["outcome"] == "no_material_edge"
    assert outcome["next_action"] == "record_qual_static_quality_factor_wrapper_v1_exact_variant_memory_only"
    assert memory["candidate_id"] == screen.CANDIDATE_ID
    assert memory["exact_variant_memory_status"] == "close_exact_variant_for_immediate_retesting"
    assert memory["broader_quality_factor_family_status"] == "open_only_for_materially_different_source_backed_hypotheses"
    assert memory["automatic_followup_etf_or_overlay_authorized"] == "false"


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["exactly_one_external_source_evaluated"] is True
    assert check["qual_only"] is True
    assert check["cache_used_without_refresh"] is True
    assert check["no_bil_trend_volatility_or_ranking_rule"] is True
    assert check["no_active_vm_rule_borrowed"] is True
    assert check["windows_generated_before_performance"] is True
    assert check["actual_etf_shares_held"] is True
    assert check["no_artificial_index_rebalance_turnover"] is True


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
