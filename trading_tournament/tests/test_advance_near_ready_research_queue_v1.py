from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import advance_near_ready_research_queue_v1 as task


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "advance_near_ready_research_queue_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> dict[str, object]:
    return task.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "task_manifest.json",
        "candidate_order.csv",
        "candidate_rule_recovery.csv",
        "rule_source_trace.csv",
        "candidate_gate_results.csv",
        "data_feasibility.csv",
        "provider_acquisition_manifest.json",
        "selected_candidate.csv",
        "execution_manifest.json",
        "frozen_window_definitions.csv",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "accounting_and_exposure_invariants.csv",
        "screening_outcome.json",
        "failure_reason.csv",
        "exact_variant_research_memory.csv",
        "blocked_candidates.csv",
        "task_summary.md",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_candidate_order_is_fixed() -> None:
    rows = read_csv("candidate_order.csv")
    consistency = read_json("consistency_check.json")
    assert [row["candidate_id"] for row in rows] == [task.QQQ_ID, task.TREASURY_ID]
    assert all(row["fixed_by_user_request"] == "True" for row in rows)
    assert all(row["performance_used"] == "False" for row in rows)
    assert consistency["candidate_order_fixed"] is True


def test_closed_value_and_sector_candidates_cannot_reenter() -> None:
    selected = read_csv("selected_candidate.csv")[0]
    memory = {row["candidate_id"]: row for row in read_csv("exact_variant_research_memory.csv")}
    consistency = read_json("consistency_check.json")
    assert selected["candidate_id"] == task.QQQ_ID
    assert task.VALUE_ID != selected["candidate_id"]
    assert task.SECTOR_ID != selected["candidate_id"]
    assert memory[task.VALUE_ID]["rerun_in_this_task"] == "False"
    assert memory[task.SECTOR_ID]["rerun_in_this_task"] == "False"
    assert consistency["value_momentum_candidate_reentered"] is False
    assert consistency["sector_candidate_reentered"] is False


def test_candidate1_executes_when_rules_are_complete() -> None:
    gates = {row["candidate_id"]: row for row in read_csv("candidate_gate_results.csv")}
    selected = read_csv("selected_candidate.csv")[0]
    consistency = read_json("consistency_check.json")
    assert gates[task.QQQ_ID]["rules_complete"] == "True"
    assert gates[task.QQQ_ID]["conflicting_rules"] == "False"
    assert gates[task.QQQ_ID]["gate_result"] == "execute_bounded_screen"
    assert selected["candidate_id"] == task.QQQ_ID
    assert consistency["candidate1_executed_when_rules_complete"] is True


def test_candidate2_considered_only_when_candidate1_is_blocked() -> None:
    gates = {row["candidate_id"]: row for row in read_csv("candidate_gate_results.csv")}
    consistency = read_json("consistency_check.json")
    assert gates[task.TREASURY_ID]["gate_result"] == "not_considered_candidate1_executed"
    assert consistency["candidate2_considered_only_when_candidate1_blocked"] is True
    assert consistency["candidate2_not_run_because_candidate1_executed"] is True


def test_missing_rules_are_not_invented_and_conflicts_block_execution_policy_exists() -> None:
    rows = read_csv("candidate_rule_recovery.csv")
    treasury_missing = [row for row in rows if row["candidate_id"] == task.TREASURY_ID]
    assert treasury_missing
    assert all(row["classification"] == "missing_existing_evidence" for row in treasury_missing)
    assert all(row["invented"] == "False" for row in rows)
    assert read_json("consistency_check.json")["conflicting_rules_block_execution"] is True


def test_no_performance_used_for_selection() -> None:
    selected = read_csv("selected_candidate.csv")[0]
    assert selected["performance_used_for_selection"] == "False"
    assert read_json("consistency_check.json")["performance_used_in_candidate_selection"] is False


def test_provider_acquisition_guardrails() -> None:
    provider = read_json("provider_acquisition_manifest.json")
    consistency = read_json("consistency_check.json")
    assert provider["provider_download"] is False
    assert provider["downloaded_symbol_count"] == 0
    assert provider["downloaded_symbol_count"] <= 2
    assert provider["only_explicitly_required_tickers_downloadable"] is True
    assert provider["valid_caches_refreshed"] is False
    assert consistency["downloaded_symbol_count_lte_2"] is True
    assert consistency["only_required_tickers_downloadable"] is True
    assert consistency["valid_caches_refreshed"] is False


def test_windows_are_frozen_before_performance() -> None:
    windows = read_csv("frozen_window_definitions.csv")
    execution = read_json("execution_manifest.json")
    consistency = read_json("consistency_check.json")
    assert len(windows) == 20
    assert {row["horizon_days"] for row in windows} == {"30", "60", "90", "180"}
    assert all(row["frozen_before_performance"] == "True" for row in windows)
    assert execution["windows_frozen_before_performance"] is True
    assert consistency["windows_frozen_before_performance"] is True


def test_correct_accounting_and_no_stale_weight_forward_fill() -> None:
    invariants = read_csv("accounting_and_exposure_invariants.csv")[0]
    consistency = read_json("consistency_check.json")
    assert invariants["actual_holdings_accounting_used"] == "True"
    assert invariants["holdings_drift_between_rebalances"] == "True"
    assert invariants["turnover_uses_pre_trade_actual_holdings"] == "True"
    assert invariants["no_stale_weight_forward_fill"] == "True"
    assert float(invariants["max_daily_exposure"]) <= 1.000001
    assert float(invariants["max_daily_weight_sum"]) <= 1.000001
    assert invariants["exposure_invariant_pass"] == "True"
    assert consistency["actual_holdings_accounting_used"] is True
    assert consistency["no_stale_weight_forward_fill"] is True


def test_registry_active_observations_and_active_combo_unchanged() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_byte_identical"] is True
    assert consistency["registry_hash_before"] == consistency["registry_hash_after"]
    assert consistency["active_vm_and_dsr_unchanged"] is True
    assert consistency["active_observations_hash_before"] == consistency["active_observations_hash_after"]
    assert consistency["active_combo_benchmark_reference_only"] is True


def test_external_source_pause_and_no_promotion_paths() -> None:
    consistency = read_json("consistency_check.json")
    outcome = read_json("screening_outcome.json")
    assert consistency["external_source_auto_selection_paused"] is True
    assert consistency["provider_download"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["promotion_created"] is False
    assert consistency["broker_live_path_touched"] is False
    assert outcome["screening_outcome"] in task.ALLOWED_OUTCOMES
    assert outcome["non_promotional"] is True


def test_generation_is_deterministic() -> None:
    manifest_hash = sha256(EVIDENCE / "task_manifest.json")
    windows_hash = sha256(EVIDENCE / "frozen_window_definitions.csv")
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    task.run()
    assert sha256(EVIDENCE / "task_manifest.json") == manifest_hash
    assert sha256(EVIDENCE / "frozen_window_definitions.csv") == windows_hash
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
