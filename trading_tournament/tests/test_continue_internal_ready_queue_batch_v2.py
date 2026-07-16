from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import continue_internal_ready_queue_batch_v2 as batch


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "continue_internal_ready_queue_batch_v2" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> dict[str, object]:
    return batch.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "batch_manifest.json",
        "candidate_eligibility.csv",
        "selection_policy.csv",
        "selected_candidates.csv",
        "provider_acquisition_manifest.json",
        "frozen_window_definitions.csv",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "accounting_and_exposure_invariants.csv",
        "screening_outcomes.csv",
        "failure_reasons.csv",
        "exact_variant_research_memory.csv",
        "blocked_near_ready_candidates.csv",
        "batch_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_active_observations_and_benchmarks_cannot_enter() -> None:
    eligibility = {row["candidate_id"]: row for row in read_csv("candidate_eligibility.csv")}
    consistency = read_json("consistency_check.json")
    assert eligibility["paper_forward_vm_quality_lowvol_proxy_v1"]["eligible"] == "False"
    assert eligibility["paper_forward_dsr_sector_equal_weight_defensive_filter_v1"]["eligible"] == "False"
    assert eligibility["active_combo_vm_dsr_equal_weight_v1"]["eligible"] == "False"
    assert consistency["active_observations_excluded"] is True
    assert consistency["benchmarks_excluded"] is True


def test_closed_exact_and_previously_screened_candidates_cannot_reenter() -> None:
    eligibility = {row["candidate_id"]: row for row in read_csv("candidate_eligibility.csv")}
    selected = read_csv("selected_candidates.csv")
    assert selected == []
    for candidate_id in [
        "qqq_spy_gld_ief_dual_momentum_v1",
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
        "spy_turn_of_month_bil_v1",
        "max_diversification_cross_asset_etf_v1",
    ]:
        assert eligibility[candidate_id]["eligible"] == "False"
        assert eligibility[candidate_id]["blocker_type"] == "closed_exact_variant"
    consistency = read_json("consistency_check.json")
    assert consistency["closed_exact_candidates_excluded"] is True
    assert consistency["previously_screened_candidates_excluded"] is True


def test_candidate_eligibility_requires_complete_rules() -> None:
    eligibility = {row["candidate_id"]: row for row in read_csv("candidate_eligibility.csv")}
    assert eligibility["treasury_duration_trend_rotation_v1"]["eligible"] == "False"
    assert eligibility["treasury_duration_trend_rotation_v1"]["blocker_type"] == "rules_data"
    assert eligibility["low_vol_quality_defensive_rotation_v1"]["eligible"] == "False"
    assert eligibility["low_vol_quality_defensive_rotation_v1"]["blocker_type"] == "rules"
    assert read_json("consistency_check.json")["eligibility_requires_complete_rules"] is True


def test_selection_policy_is_deterministic_and_not_performance_based() -> None:
    policy = read_csv("selection_policy.csv")
    consistency = read_json("consistency_check.json")
    assert all(row["applied_before_performance"] == "True" for row in policy)
    assert consistency["deterministic_selection_policy_recorded"] is True
    assert consistency["performance_used_for_selection"] is False
    assert all(row["performance_used_for_selection"] == "False" for row in read_csv("candidate_eligibility.csv"))


def test_max_one_candidate_per_family_and_no_selection_when_none_eligible() -> None:
    manifest = read_json("batch_manifest.json")
    consistency = read_json("consistency_check.json")
    assert manifest["eligible_candidate_count"] == 0
    assert manifest["selected_candidate_count"] == 0
    assert manifest["screen_ran"] is False
    assert consistency["max_one_candidate_per_family"] is True


def test_provider_acquisition_limits_and_valid_caches_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    consistency = read_json("consistency_check.json")
    assert provider["provider_download"] is False
    assert provider["downloaded_symbol_count"] == 0
    assert provider["downloaded_symbol_count"] <= provider["max_missing_symbols_authorized"]
    assert provider["valid_caches_refreshed"] is False
    assert provider["only_frozen_missing_tickers_downloadable"] is True
    assert consistency["downloaded_symbol_count_lte_2"] is True
    assert consistency["valid_caches_refreshed"] is False


def test_windows_and_accounting_guardrails_for_zero_eligible_packet() -> None:
    consistency = read_json("consistency_check.json")
    invariants = read_csv("accounting_and_exposure_invariants.csv")[0]
    assert read_csv("frozen_window_definitions.csv") == []
    assert consistency["windows_frozen_before_performance"] is True
    assert consistency["actual_holdings_accounting_used"] == "not_applicable_no_screen"
    assert consistency["no_stale_weight_forward_fill"] == "not_applicable_no_screen"
    assert invariants["screen_ran"] == "False"


def test_registry_and_active_observations_remain_byte_identical() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_byte_identical"] is True
    assert consistency["registry_hash_before"] == consistency["registry_hash_after"]
    assert consistency["active_observations_unchanged"] is True
    assert consistency["active_observations_hash_before"] == consistency["active_observations_hash_after"]


def test_external_source_pause_and_no_project_pause() -> None:
    consistency = read_json("consistency_check.json")
    manifest = read_json("batch_manifest.json")
    assert consistency["external_source_auto_selection_paused"] is True
    assert consistency["project_paused"] is False
    assert consistency["next_lane"] == "direction_owner_fast_discovery_required"
    assert manifest["project_paused"] is False


def test_qqq_failure_wording_correction_only() -> None:
    memory = {row["candidate_id"]: row for row in read_csv("exact_variant_research_memory.csv")}
    failure = {row["candidate_id"]: row for row in read_csv("failure_reasons.csv")}
    assert memory["qqq_spy_gld_ief_dual_momentum_v1"]["primary_failure_description"] == batch.CORRECTED_QQQ_FAILURE
    assert memory["qqq_spy_gld_ief_dual_momentum_v1"]["wording_correction_only"] == "True"
    assert memory["qqq_spy_gld_ief_dual_momentum_v1"]["rerun_in_this_task"] == "False"
    assert failure["qqq_spy_gld_ief_dual_momentum_v1"]["primary_failure_reason"] == batch.CORRECTED_QQQ_FAILURE


def test_no_disallowed_paths() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["provider_download"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["promotion_created"] is False
    assert consistency["broker_live_path_touched"] is False
    assert consistency["real_money_recommendation"] is False


def test_generation_is_deterministic() -> None:
    manifest_hash = sha256(EVIDENCE / "batch_manifest.json")
    eligibility_hash = sha256(EVIDENCE / "candidate_eligibility.csv")
    memory_hash = sha256(EVIDENCE / "exact_variant_research_memory.csv")
    batch.run()
    assert sha256(EVIDENCE / "batch_manifest.json") == manifest_hash
    assert sha256(EVIDENCE / "candidate_eligibility.csv") == eligibility_hash
    assert sha256(EVIDENCE / "exact_variant_research_memory.csv") == memory_hash
