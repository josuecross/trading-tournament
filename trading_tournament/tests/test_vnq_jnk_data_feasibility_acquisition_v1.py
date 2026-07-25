from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from strategy_lab.research_os.research import vnq_jnk_data_feasibility_acquisition_v1 as task


EVIDENCE = task.OUTPUT_DIR
REQUIRED_ARTIFACTS = {
    "task_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "process_task_log.csv",
    "data_source_manifest.csv",
    "data_coverage.csv",
    "data_integrity_checks.csv",
    "cache_reload_reconciliation.csv",
    "strategy_data_sufficiency.csv",
    "benchmark_reference_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "data_feasibility_report.md",
}
BLOCKED_STRATEGIES = {
    "daryanani_opportunistic_rebalance_20band_10day_v1",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "ice_vaneck_us_fallen_angel_angl_v1",
}
PROTECTED_STATE_PATHS = task.PROTECTED_STATE_PATHS


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_runner_writes_required_artifacts_and_preserves_symbol_scope() -> None:
    result = task.run()

    assert result["task_id"] == task.TASK_ID
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _yaml("task_manifest.yaml")
    assert manifest["target_symbols"] == ["VNQ", "JNK"]
    assert manifest["task_type"] == "data-acquisition-or-capability"
    assert manifest["stage"] == "feasibility"

    source_rows = _rows("data_source_manifest.csv")
    assert {row["symbol"] for row in source_rows} == {"VNQ", "JNK"}
    assert all(row["preferred_provider"] == "alpaca_market_data" for row in source_rows)
    assert all(row["fallback_provider"] in {"existing_cache", "yfinance_existing_repo_supported_fallback"} for row in source_rows)
    assert all(row["final_cache_status"] == "validated" for row in source_rows)


def test_validated_cache_has_required_schema_coverage_and_integrity() -> None:
    task.run()

    coverage = {row["symbol"]: row for row in _rows("data_coverage.csv")}
    assert set(coverage) == {"VNQ", "JNK"}
    for symbol, row in coverage.items():
        assert row["status"] == "validated"
        assert row["covers_required_through_date"] == "true"
        assert int(row["row_count"]) > 0
        assert pd.Timestamp(row["last_date"]) >= task.REQUIRED_THROUGH_DATE
        cache_file = task.DATA_CACHE_DIR / f"{symbol}.csv"
        frame = pd.read_csv(cache_file)
        assert set(task.REQUIRED_CACHE_COLUMNS).issubset(frame.columns)
        assert frame["date"].is_unique
        assert pd.to_datetime(frame["date"]).is_monotonic_increasing
        assert (frame[["open", "high", "low", "close", "adj_close"]] > 0).all().all()
        assert (frame[["volume", "raw_volume"]] >= 0).all().all()

    integrity = _rows("data_integrity_checks.csv")
    assert {row["symbol"] for row in integrity} == {"VNQ", "JNK"}
    assert all(row["status"] == "pass" for row in integrity)


def test_cache_reload_reconciliation_is_identical_and_hashes_are_present() -> None:
    task.run()

    reload_rows = _rows("cache_reload_reconciliation.csv")
    assert {row["symbol"] for row in reload_rows} == {"VNQ", "JNK"}
    for row in reload_rows:
        assert row["reload_identical"] == "true"
        assert row["original_row_count"] == row["reloaded_row_count"]
        assert row["original_frame_hash"] == row["reloaded_frame_hash"]
        assert row["cache_file_hash"].startswith("sha256:")


def test_strategy_sufficiency_unblocks_only_the_three_prior_data_issues_and_carries_nvi_as_non_cohort() -> None:
    task.run()

    strategy_cards = _rows("strategy_cards.csv")
    assert {row["strategy_id"] for row in strategy_cards} == BLOCKED_STRATEGIES
    assert all(row["new_strategy_trial_created"] == "false" for row in strategy_cards)
    assert all(row["strategy_backtest_run"] == "false" for row in strategy_cards)

    sufficiency = {row["strategy_id"]: row for row in _rows("strategy_data_sufficiency.csv")}
    assert set(sufficiency) == BLOCKED_STRATEGIES
    assert sufficiency["daryanani_opportunistic_rebalance_20band_10day_v1"]["previous_blocked_symbol"] == "VNQ"
    assert sufficiency["clare_inverse_volatility_five_asset_risk_parity_v1"]["previous_blocked_symbol"] == "VNQ"
    assert sufficiency["ice_vaneck_us_fallen_angel_angl_v1"]["previous_blocked_symbol"] == "JNK"
    assert all(row["backtest_run"] == "false" for row in sufficiency.values())

    outcomes = _rows("outcome_summary.csv")
    nvi = [row for row in outcomes if row["entity_id"] == "fosback_nvi_255ema_spy_bil_v1"]
    assert len(nvi) == 1
    assert nvi[0]["entity_type"] == "strategy_configuration"
    assert nvi[0]["stage"] == "exploratory_followup_standalone"
    assert nvi[0]["outcome"] == "exploratory_followup_candidate_standalone"
    assert nvi[0]["next_action"] == "targeted_nvi_incremental_signal_followup_v1"
    assert nvi[0]["counted_in_data_acquisition_symbol_cohort"] == "false"


def test_benchmark_rows_are_references_only_and_no_metrics_are_calculated() -> None:
    task.run()

    references = _rows("benchmark_reference_log.csv")
    assert len(references) == 6
    assert {row["strategy_id"] for row in references} == BLOCKED_STRATEGIES
    assert all(row["entity_type"] == "benchmark_reference" for row in references)
    assert all(row["stage"] == "benchmark_reference_only" for row in references)
    assert all(row["calculated_in_this_task"] == "false" for row in references)

    consistency = _json("consistency_check.json")
    assert consistency["benchmark_references_only_no_calculation"] is True
    assert consistency["strategy_backtest_run"] is False
    assert consistency["strategy_performance_metrics_calculated"] is False
    assert consistency["benchmark_metrics_calculated"] is False


def test_process_log_has_one_data_capability_task_per_symbol_and_next_action_matches_outcome() -> None:
    task.run()

    rows = _rows("process_task_log.csv")
    assert {row["symbol"] for row in rows} == {"VNQ", "JNK"}
    assert all(row["entity_type"] == "data_capability_task" for row in rows)
    assert all(row["stage"] == "feasibility" for row in rows)
    assert all(row["strategy_backtest_run"] == "false" for row in rows)
    assert all(row["broker_or_order_path_touched"] == "false" for row in rows)

    action_rows = _rows("next_actions.csv")
    global_rows = [row for row in action_rows if row["scope"] == "global"]
    assert len(global_rows) == 1
    consistency = _json("consistency_check.json")
    assert global_rows[0]["exact_next_action"] == consistency["exact_next_action"]
    assert global_rows[0]["execute_now"] == "false"


def test_guardrails_and_protected_state_are_preserved() -> None:
    before = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}
    result = task.run()
    after = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}

    assert before == after
    assert result["protected_state_hashes_unchanged"] is True
    consistency = _json("consistency_check.json")
    assert consistency["protected_state_hashes_unchanged"] is True
    assert consistency["prior_evidence_hashes_unchanged"] is True
    assert consistency["preexisting_cached_symbols_unchanged"] is True
    for key, value in task.FORBIDDEN_FLAGS.items():
        assert consistency[key] is value


def test_output_generation_is_deterministic_after_cache_admission() -> None:
    task.run()
    first_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}

    task.run()
    second_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}

    assert first_bytes == second_bytes
