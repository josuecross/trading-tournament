from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import resume_existing_ready_research_batch_v1 as batch


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "resume_existing_ready_research_batch_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_batch_evidence() -> dict[str, object]:
    return batch.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest().upper()


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
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_active_vm_dsr_and_active_combo_cannot_enter_batch() -> None:
    selected = {row["candidate_id"] for row in read_csv("selected_candidates.csv")}
    consistency = read_json("consistency_check.json")
    assert batch.ACTIVE_VM_ID not in selected
    assert batch.ACTIVE_DSR_ID not in selected
    assert batch.ACTIVE_COMBO_ID not in selected
    assert consistency["active_vm_excluded"] is True
    assert consistency["active_dsr_excluded"] is True
    assert consistency["active_combo_excluded_as_candidate"] is True


def test_closed_and_previously_screened_exact_variants_cannot_enter() -> None:
    selected = {row["candidate_id"] for row in read_csv("selected_candidates.csv")}
    eligibility = {row["candidate_id"]: row for row in read_csv("candidate_eligibility.csv")}
    assert selected.isdisjoint(batch.PREVIOUSLY_CLOSED_EXACT)
    for closed_id in [
        "splv_static_low_vol_factor_wrapper_v1",
        "qual_static_quality_factor_wrapper_v1",
        "angl_static_fallen_angel_credit_v1",
        "spy_turn_of_month_bil_v1",
        "percent_b_mfi",
    ]:
        assert eligibility[closed_id]["eligible"] == "False"
        assert eligibility[closed_id]["blocker_type"] == "closed_exact_variant"


def test_candidate_selection_is_deterministic_and_not_performance_based() -> None:
    selected = read_csv("selected_candidates.csv")
    policy = read_csv("selection_policy.csv")
    consistency = read_json("consistency_check.json")
    assert [row["candidate_id"] for row in selected] == [
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
    ]
    assert all(row["applied_before_performance"] == "True" for row in policy)
    assert consistency["deterministic_selection_policy_recorded_before_performance"] is True
    assert consistency["performance_based_selection_used"] is False
    assert all(row["performance_used_for_selection"] == "False" for row in read_csv("candidate_eligibility.csv"))


def test_max_one_candidate_per_family() -> None:
    selected = read_csv("selected_candidates.csv")
    families = [row["family_id"] for row in selected]
    assert len(families) == len(set(families))
    assert read_json("consistency_check.json")["max_one_candidate_per_family"] is True


def test_no_provider_download_and_valid_caches_not_refreshed() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    consistency = read_json("consistency_check.json")
    assert provider["provider_download"] is False
    assert provider["downloaded_symbol_count"] == 0
    assert provider["downloaded_symbol_count"] <= provider["max_missing_symbols_authorized"]
    assert provider["valid_existing_caches_refreshed"] is False
    assert consistency["downloaded_symbol_count_lte_2"] is True
    assert consistency["only_frozen_candidate_tickers_downloadable"] is True
    assert consistency["valid_caches_refreshed"] is False


def test_windows_are_frozen_before_performance() -> None:
    manifest = read_json("batch_manifest.json")
    windows = read_csv("frozen_window_definitions.csv")
    assert manifest["windows_frozen_before_performance"] is True
    assert len(windows) == 20
    assert {row["horizon_days"] for row in windows} == {"90", "180"}
    assert all(row["generated_before_performance"] == "True" for row in windows)
    assert all(row["selection_performance_inputs_used"] == "False" for row in windows)


def test_correct_actual_holdings_accounting_and_pre_trade_turnover() -> None:
    invariants = read_csv("accounting_and_exposure_invariants.csv")
    consistency = read_json("consistency_check.json")
    assert consistency["actual_holdings_accounting_used"] is True
    assert consistency["turnover_uses_pre_trade_actual_holdings"] is True
    assert all(row["actual_holdings_accounting_used"] == "True" for row in invariants)
    assert all(row["holdings_drift_between_rebalances"] == "True" for row in invariants)
    assert all(row["turnover_uses_pre_trade_actual_holdings"] == "True" for row in invariants)


def test_no_stale_weight_bug_reintroduced_and_exposure_invariants_hold() -> None:
    invariants = read_csv("accounting_and_exposure_invariants.csv")
    consistency = read_json("consistency_check.json")
    assert consistency["no_stale_weight_forward_fill"] is True
    for row in invariants:
        assert row["zero_target_weights_preserved"] == "True"
        assert row["no_stale_weight_forward_fill"] == "True"
        assert row["bil_cash_replacement_remainder_only"] == "True"
        assert float(row["max_daily_exposure"]) <= 1.000001
        assert float(row["max_daily_weight_sum"]) <= 1.000001
        assert row["exposure_invariant_pass"] == "True"
        assert row["weight_sum_invariant_pass"] == "True"
        assert row["negative_weight_invariant_pass"] == "True"
        assert row["nan_weight_invariant_pass"] == "True"


def test_registry_and_active_observations_remain_byte_identical() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_byte_identical"] is True
    assert consistency["registry_hash_before"] == consistency["registry_hash_after"]
    assert consistency["active_observations_unchanged"] is True
    assert consistency["active_observations_hash_before"] == consistency["active_observations_hash_after"]


def test_external_source_auto_selection_pause_remains_active() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["external_source_auto_selection_pause_remains_active"] is True
    assert consistency["strategy_discovery_run"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["broker_or_live_path_touched"] is False


def test_outputs_remain_non_promotional_and_have_valid_outcomes() -> None:
    manifest = read_json("batch_manifest.json")
    outcomes = read_csv("screening_outcomes.csv")
    assert manifest["promotion_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["candidate_exhaustive_run"] is False
    for row in outcomes:
        assert row["screening_outcome"] in batch.ALLOWED_OUTCOMES
        assert row["promotion_eligible"] == "False"
        assert row["paper_forward_eligible"] == "False"
        assert row["candidate_exhaustive_ready"] == "False"


def test_generation_is_deterministic() -> None:
    manifest_before = sha256(EVIDENCE / "batch_manifest.json")
    windows_before = sha256(EVIDENCE / "frozen_window_definitions.csv")
    outcomes_before = sha256(EVIDENCE / "screening_outcomes.csv")
    batch.run()
    assert sha256(EVIDENCE / "batch_manifest.json") == manifest_before
    assert sha256(EVIDENCE / "frozen_window_definitions.csv") == windows_before
    assert sha256(EVIDENCE / "screening_outcomes.csv") == outcomes_before
