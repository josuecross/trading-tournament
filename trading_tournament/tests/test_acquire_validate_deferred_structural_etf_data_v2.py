from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from strategy_lab.research_os.research import acquire_validate_deferred_structural_etf_data_v2 as task


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "data_capability" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_exists() -> None:
    if not (EVIDENCE / "consistency_check.json").exists():
        task.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_outputs_and_exact_counts() -> None:
    required = {
        "task_manifest.yaml",
        "source_library_records.csv",
        "data_capability_task_log.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "provider_attempts.csv",
        "data_source_manifest.csv",
        "data_coverage.csv",
        "data_integrity_checks.csv",
        "cache_reload_reconciliation.csv",
        "strategy_data_sufficiency.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "data_feasibility_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("task_manifest.yaml")
    assert manifest["task_id"] == task.TASK_ID
    assert manifest["mode"] == "data-capability"
    assert manifest["stage"] == "feasibility"
    assert manifest["target_symbols"] == ["CSD", "IWR", "PKW"]
    assert manifest["source_library_records_carried_forward"] == 2
    assert manifest["data_capability_tasks"] == 3
    assert manifest["process_tasks"] == 1
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["experiment_trials_created"] == 0
    assert manifest["paper_demo_observations_created"] == 0
    assert manifest["new_research_candidates_created"] == 0


def test_source_records_are_carried_forward_without_becoming_strategies() -> None:
    rows = read_csv("source_library_records.csv")
    assert len(rows) == 2
    assert {row["source_record_id"] for row in rows} == set(task.SOURCE_RECORD_IDS)
    assert {row["entity_type"] for row in rows} == {"source_library_record"}
    assert {row["stage"] for row in rows} == {"source_extracted"}
    assert {row["counted_as_strategy_configuration"] for row in rows} == {"false"}
    assert {row["counted_as_experiment_trial"] for row in rows} == {"false"}
    assert {row["rules_or_mapping_changed"] for row in rows} == {"false"}
    by_strategy = {row["proposed_strategy_id"]: row for row in rows}
    assert by_strategy["invesco_sp_us_spinoff_csd_v1"]["required_instruments"] == "CSD|IWR|SPY"
    assert by_strategy["nasdaq_buyback_achievers_pkw_v1"]["required_instruments"] == "PKW|SPY|DGRO"


def test_exactly_three_data_tasks_have_standardized_outcomes() -> None:
    rows = read_csv("data_capability_task_log.csv")
    assert len(rows) == 3
    assert {row["symbol"] for row in rows} == {"CSD", "IWR", "PKW"}
    assert {row["entity_type"] for row in rows} == {"data_capability_task"}
    assert {row["stage"] for row in rows} <= {"feasible", "blocked"}
    assert {row["adaptation_label"] for row in rows} == {"data_feasibility_adjustment"}
    assert {row["counted_as_strategy_configuration"] for row in rows} == {"false"}
    assert {row["counted_as_experiment_trial"] for row in rows} == {"false"}
    assert {row["counted_as_paper_demo_observation"] for row in rows} == {"false"}
    allowed_failures = {"", "data_unavailable", "capability_missing", "data_or_comparability_failure", "methodology_failure"}
    assert {row["failure_reason"] for row in rows} <= allowed_failures
    for row in rows:
        assert (row["stage"] == "feasible") == (row["failure_reason"] == "")


def test_provider_sequence_is_bounded_and_read_only() -> None:
    rows = read_csv("provider_attempts.csv")
    assert len(rows) == 6
    for symbol in task.TARGET_SYMBOLS:
        symbol_rows = sorted(
            (row for row in rows if row["symbol"] == symbol),
            key=lambda row: int(row["attempt_order"]),
        )
        assert [row["provider_id"] for row in symbol_rows] == ["alpaca_market_data", "yfinance"]
        assert symbol_rows[0]["provider_role"] == "preferred_read_only_market_data"
        assert symbol_rows[1]["provider_role"] == "single_existing_repo_supported_fallback"
        assert sum(row["attempted"] == "true" for row in symbol_rows if row["attempt_order"] == "2") <= 1
        assert {row["account_order_or_position_endpoint_called"] for row in symbol_rows} == {"false"}
        assert {row["credentials_persisted"] for row in symbol_rows} == {"false"}


def test_validated_symbols_have_canonical_cache_integrity_and_reload() -> None:
    tasks = {row["symbol"]: row for row in read_csv("data_capability_task_log.csv")}
    coverage = {row["symbol"]: row for row in read_csv("data_coverage.csv")}
    reloads = {row["symbol"]: row for row in read_csv("cache_reload_reconciliation.csv")}
    manifests = {row["symbol"]: row for row in read_csv("data_source_manifest.csv")}
    integrity = read_csv("data_integrity_checks.csv")
    for symbol, data_task in tasks.items():
        if data_task["stage"] == "blocked":
            continue
        assert coverage[symbol]["status"] == "validated"
        assert coverage[symbol]["covers_required_through_date"] == "true"
        assert pd.Timestamp(coverage[symbol]["last_date"]) >= task.REQUIRED_THROUGH_DATE
        assert int(coverage[symbol]["row_count"]) > 0
        assert reloads[symbol]["reload_identical"] == "true"
        assert reloads[symbol]["normal_backtester_load_pass"] == "true"
        assert manifests[symbol]["admitted_to_canonical_cache"] == "true"
        assert manifests[symbol]["provider_identifier"]
        assert manifests[symbol]["acquisition_timestamp"]
        assert manifests[symbol]["canonical_cache_hash"].startswith("sha256:")
        assert manifests[symbol]["canonical_frame_hash"].startswith("sha256:")
        assert manifests[symbol]["metadata_hash"].startswith("sha256:")
        symbol_checks = [row for row in integrity if row["symbol"] == symbol]
        assert symbol_checks
        assert {row["status"] for row in symbol_checks} == {"pass"}
        check_names = {row["check_name"] for row in symbol_checks}
        assert {
            "dates_strictly_increasing",
            "dates_unique",
            "no_impossible_or_future_timestamps",
            "prices_positive",
            "volume_finite_nonnegative",
            "adjusted_ohlc_relationships",
            "canonical_adjustment_compatibility",
            "missing_session_and_coverage_gap_report_generated",
            "coverage_through_required_date",
            "normal_backtester_data_interface_load",
        } <= check_names


def test_source_data_sufficiency_and_next_action_are_mechanical() -> None:
    rows = read_csv("strategy_data_sufficiency.csv")
    assert len(rows) == 2
    assert {row["entity_type"] for row in rows} == {"source_library_record"}
    assert {row["stage"] for row in rows} == {"source_extracted"}
    assert {row["data_sufficiency_outcome"] for row in rows} <= {"data_feasible", "blocked"}
    assert {row["evaluation_dates_selected_from_returns"] for row in rows} == {"false"}
    assert {row["strategy_result_calculated"] for row in rows} == {"false"}
    by_id = {row["proposed_strategy_id"]: row for row in rows}
    spin_ready = by_id["invesco_sp_us_spinoff_csd_v1"]["data_sufficiency_outcome"] == "data_feasible"
    buyback_ready = by_id["nasdaq_buyback_achievers_pkw_v1"]["data_sufficiency_outcome"] == "data_feasible"
    expected = (
        "run_deferred_structural_source_batch_v2"
        if spin_ready and buyback_ready
        else "run_spinoff_structural_source_exploration_v2"
        if spin_ready
        else "run_buyback_structural_source_exploration_v2"
        if buyback_ready
        else "refresh_strategy_source_library_v3"
    )
    assert read_csv("outcome_summary.csv")[0]["exact_next_action"] == expected
    assert {row["exact_next_action"] for row in read_csv("next_actions.csv")} == {expected}
    assert {row["execute_now"] for row in read_csv("next_actions.csv")} == {"false"}


def test_benchmark_and_process_entities_remain_separate() -> None:
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert len(benchmarks) == 4
    assert {row["benchmark_or_control_id"] for row in benchmarks} == {
        "IWR_buy_and_hold",
        "SPY_buy_and_hold",
        "DGRO_buy_and_hold",
    }
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["calculated_in_this_task"] for row in benchmarks} == {"false"}
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "feasibility"
    assert process[0]["strategy_configurations_created"] == "0"
    assert process[0]["experiment_trials_created"] == "0"
    assert process[0]["paper_demo_observations_created"] == "0"


def test_protected_state_and_unrelated_cache_files_are_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["protected_state_hashes_unchanged"] is True
    assert check["input_evidence_hashes_unchanged"] is True
    assert check["cache_changes_limited_to_validated_target_files"] is True
    assert check["unexpected_state_or_cache_changes"] == []
    assert check["strategy_configurations_created"] == 0
    assert check["experiment_trials_created"] == 0
    assert check["paper_demo_observations_created"] == 0
    assert check["new_research_candidates_created"] == 0
    state_rows = read_csv("state_change_manifest.csv")
    changed = {row["path"] for row in state_rows if row["changed"] == "true"}
    allowed = {
        f"data/cache/{symbol}.csv"
        for symbol in task.TARGET_SYMBOLS
    } | {
        f"data/cache/{symbol}.acquisition.json"
        for symbol in task.TARGET_SYMBOLS
    }
    assert changed <= allowed
    assert all(row["change_permitted"] == "true" for row in state_rows)


def test_no_secret_or_performance_result_is_persisted() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in EVIDENCE.iterdir()
        if path.is_file()
    )
    credentials = load_alpaca_credentials("paper")
    if credentials.api_key:
        assert credentials.api_key not in combined
    if credentials.secret_key:
        assert credentials.secret_key not in combined
    lowered = combined.lower()
    assert "candidate_metrics" not in lowered
    assert "strategy_return" not in lowered
    assert "sharpe_ratio" not in lowered
    assert "maximum_drawdown" not in lowered
    assert "cagr" not in lowered
    consistency = read_json("consistency_check.json")
    assert consistency["broker_order_submitted"] is False


def test_duplicate_dates_and_invalid_prices_fail_canonical_validation() -> None:
    valid = pd.DataFrame(
        {
            "date": ["2026-06-17", "2026-06-18"],
            "raw_open": [10.0, 10.5],
            "raw_high": [11.0, 11.0],
            "raw_low": [9.0, 10.0],
            "raw_close": [10.5, 10.75],
            "raw_adj_close": [10.5, 10.75],
            "raw_volume": [100.0, 120.0],
            "dividends": [0.0, 0.0],
            "stock_splits": [0.0, 0.0],
        }
    )
    duplicate = pd.concat([valid, valid.iloc[[-1]]], ignore_index=True)
    normalized_duplicate = task.canonicalize_cache_frame(duplicate, "CSD")
    assert len(normalized_duplicate) == 2
    invalid = valid.copy()
    invalid.loc[1, "raw_close"] = -1.0
    with pytest.raises(Exception):
        task.canonicalize_cache_frame(invalid, "CSD")
