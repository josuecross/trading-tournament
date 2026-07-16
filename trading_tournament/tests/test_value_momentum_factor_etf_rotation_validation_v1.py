from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import value_momentum_factor_etf_rotation_validation_v1 as validation


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "value_momentum_factor_etf_rotation_validation_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_validation_evidence() -> dict[str, object]:
    return validation.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "validation_manifest.json",
        "monthly_start_90d_results.csv",
        "monthly_start_180d_results.csv",
        "monthly_start_252d_results.csv",
        "monthly_start_504d_results.csv",
        "non_overlapping_180d_results.csv",
        "non_overlapping_252d_results.csv",
        "non_overlapping_504d_results.csv",
        "full_period_metrics.csv",
        "chronological_thirds_metrics.csv",
        "calendar_year_results.csv",
        "benchmark_dependence.csv",
        "factor_selection_attribution.csv",
        "turnover_attribution.csv",
        "redundancy_analysis.csv",
        "rolling_relative_diagnostics.csv",
        "accounting_and_alignment_invariants.csv",
        "validation_summary.md",
        "validation_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_candidate_rules_and_parameters_remain_frozen() -> None:
    manifest = read_json("validation_manifest.json")
    assert manifest["candidate_id"] == validation.CANDIDATE_ID
    assert manifest["rules_frozen"] is True
    assert manifest["universe"] == list(validation.CANDIDATE_SYMBOLS)
    assert manifest["ranking_lookback_days"] == 126
    assert manifest["trend_days"] == 200
    assert manifest["top_n"] == 2
    assert manifest["rebalance"] == "monthly"
    assert manifest["primary_benchmark"] == validation.PRIMARY_BENCHMARK
    assert manifest["no_parameter_universe_benchmark_or_period_change_after_results"] is True


def test_sector_candidate_is_not_rerun_and_memory_is_preserved() -> None:
    manifest = read_json("validation_manifest.json")
    consistency = read_json("consistency_check.json")
    memory = {row["candidate_id"]: row for row in read_csv("exact_variant_research_memory.csv")}
    assert manifest["sector_candidate_rerun"] is False
    assert consistency["sector_candidate_not_rerun"] is True
    assert memory[validation.SECTOR_CANDIDATE_ID]["validation_outcome"] == "control_weak"
    assert memory[validation.SECTOR_CANDIDATE_ID]["rerun_in_this_task"] == "False"


def test_rolling_and_non_overlapping_windows_are_deterministic() -> None:
    definitions = read_csv("frozen_window_and_period_definitions.csv")
    families = {row["window_family"] for row in definitions}
    assert {f"monthly_start_{h}d" for h in validation.MONTHLY_HORIZONS}.issubset(families)
    assert {f"non_overlapping_{h}d" for h in validation.NON_OVERLAP_HORIZONS}.issubset(families)
    assert all(row["frozen_before_performance"] == "True" for row in definitions)
    assert all(row["non_independent"] == "True" for row in definitions if row["window_family"].startswith("monthly_start"))
    assert all(row["non_independent"] == "False" for row in definitions if row["window_family"].startswith("non_overlapping"))


def test_windows_are_frozen_before_performance_and_benchmarks_match_dates() -> None:
    manifest = read_json("validation_manifest.json")
    consistency = read_json("consistency_check.json")
    full_rows = read_csv("full_period_metrics.csv")
    primary_rows = [row for row in read_csv("monthly_start_252d_results.csv") if row["benchmark_id"] == validation.PRIMARY_BENCHMARK]
    assert manifest["windows_frozen_before_performance"] is True
    assert consistency["windows_frozen_before_performance"] is True
    assert consistency["benchmarks_use_matching_dates"] is True
    assert all(row["candidate_excess_return"] != "" for row in primary_rows)
    assert {row["benchmark_id"] for row in full_rows} == set(validation.BENCHMARK_IDS)


def test_correct_accounting_no_stale_weight_and_bil_replacement() -> None:
    row = read_csv("accounting_and_alignment_invariants.csv")[0]
    consistency = read_json("consistency_check.json")
    assert row["actual_etf_shares_accounting"] == "True"
    assert row["monthly_scheduled_execution_only"] == "True"
    assert row["drift_aware_holdings"] == "True"
    assert row["turnover_from_actual_pre_trade_holdings"] == "True"
    assert row["no_stale_target_weight_forward_fill"] == "True"
    assert row["bil_replacement_behavior_unchanged"] == "True"
    assert float(row["max_daily_exposure"]) <= 1.000001
    assert float(row["max_daily_weight_sum"]) <= 1.000001
    assert row["accounting_and_alignment_valid"] == "True"
    assert consistency["actual_holdings_accounting_used"] is True
    assert consistency["no_stale_weight_forward_fill"] is True
    assert consistency["bil_replacement_behavior_unchanged"] is True


def test_attribution_redundancy_and_rolling_diagnostics_do_not_create_strategies() -> None:
    attribution = read_csv("factor_selection_attribution.csv")
    redundancy = read_csv("redundancy_analysis.csv")
    rolling = read_csv("rolling_relative_diagnostics.csv")
    consistency = read_json("consistency_check.json")
    assert attribution
    assert all(row["alternative_strategy_created"] == "False" for row in attribution)
    assert all(row["blended_portfolio_created"] == "False" for row in redundancy)
    assert all(row["rolling_diagnostics_create_signal"] == "False" for row in rolling)
    assert consistency["factor_selection_attribution_created_alternative_strategy"] is False
    assert consistency["redundancy_analysis_created_blended_portfolio"] is False
    assert consistency["rolling_diagnostics_created_signal"] is False


def test_no_provider_call_or_cache_refresh_and_state_unchanged() -> None:
    manifest = read_json("validation_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["provider_download"] is False
    assert manifest["cache_refresh"] is False
    assert consistency["provider_call_or_cache_refresh"] is False
    assert consistency["registry_byte_identical"] is True
    assert consistency["registry_hash_before"] == consistency["registry_hash_after"]
    assert consistency["active_observations_unchanged"] is True
    assert consistency["active_observations_hash_before"] == consistency["active_observations_hash_after"]
    assert consistency["active_combo_unchanged"] is True


def test_external_source_pause_remains_lane_specific_and_no_promotion_path() -> None:
    consistency = read_json("consistency_check.json")
    outcome = read_json("validation_outcome.json")
    assert consistency["external_source_selection_pause_lane_specific_and_active"] is True
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["promotion_created"] is False
    assert consistency["lifecycle_state_changed"] is False
    assert outcome["validation_outcome"] in validation.VALIDATION_OUTCOMES
    assert outcome["non_promotional"] is True
    assert outcome["promotion_created"] is False
    assert outcome["paper_forward_activation"] is False


def test_generation_is_deterministic() -> None:
    manifest_hash = sha256(EVIDENCE / "validation_manifest.json")
    outcome_hash = sha256(EVIDENCE / "validation_outcome.json")
    benchmark_hash = sha256(EVIDENCE / "benchmark_dependence.csv")
    validation.run()
    assert sha256(EVIDENCE / "validation_manifest.json") == manifest_hash
    assert sha256(EVIDENCE / "validation_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "benchmark_dependence.csv") == benchmark_hash
