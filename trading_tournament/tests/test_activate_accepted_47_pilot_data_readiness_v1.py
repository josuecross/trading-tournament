from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from strategy_lab.research_os.research import activate_accepted_47_pilot_data_readiness_v1 as task


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_packet_and_ready_outcome() -> None:
    assert set(task.OUTPUT_FILES).issubset({path.name for path in OUTPUT.iterdir()})
    manifest = yaml.safe_load((OUTPUT / "activation_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["outcome"] == "accepted_47_pilot_data_ready"
    assert manifest["next_action"] == "design_accepted_47_hybrid_discovery_batch_v1"
    assert manifest["refreshed_symbol_count"] == 47
    assert manifest["authorized_cutoff"] == "2026-08-04"


def test_direction_correction_is_exact_and_append_only() -> None:
    direction = rows("direction_correction_record.csv")
    assert direction == [task.DIRECTION_ROW]
    checks = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert checks["direction_recorded_before_provider_access"] is True
    assert checks["direction_record_append_only_hash_unchanged_after_provider"] is True


def test_exact_ordered_47_membership_and_six_groups() -> None:
    accepted = task.read_csv(ROOT / task.COMPAT_DIR / "accepted_final_47_universe.csv")
    operational = rows("operational_universe_snapshot.csv")
    assert tuple(row["symbol"] for row in accepted) == task.SYMBOLS
    assert tuple(row["symbol"] for row in operational) == task.SYMBOLS
    assert len(operational) == 47
    assert len({row["economic_group"] for row in operational}) == 6
    assert not set(task.EXCLUDED_SEPARATE_APPROVALS).intersection(row["symbol"] for row in operational)
    assert all(row["performance_selected"] == "False" for row in operational)
    assert all(row["strategy_results_used"] == "False" for row in operational)


def test_existing_cache_state_reproduced_before_writes() -> None:
    reproduction = rows("existing_cache_reproduction.csv")
    assert len(reproduction) == 47
    assert all(row["last_valid_session"] == "2026-07-16" for row in reproduction)
    assert all(row["reproduction_passed"] == "True" for row in reproduction)
    assert all(row["ordered_unique_sessions"] == "True" for row in reproduction)
    assert all(row["valid_adjusted_ohlc"] == "True" for row in reproduction)
    assert all(row["deterministic_reload"] == "True" for row in reproduction)


def test_calibration_uses_frozen_symbols_and_established_tolerances() -> None:
    manifest = rows("provider_calibration_manifest.csv")
    overlap = rows("provider_overlap_reconciliation.csv")
    assert tuple(row["symbol"] for row in manifest) == task.CALIBRATION_SYMBOLS
    assert tuple(row["symbol"] for row in overlap) == task.CALIBRATION_SYMBOLS
    assert all(row["feed"] == "sip" for row in manifest)
    assert all(row["raw_request_adjustment"] == "raw" for row in manifest)
    assert all(row["adjusted_close_request_adjustment"] == "all" for row in manifest)
    assert all(int(row["overlap_rows"]) >= task.OVERLAP_MIN_ROWS for row in overlap)
    assert all(float(row["median_absolute_daily_return_difference"]) <= task.OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE for row in overlap)
    assert all(float(row["p99_absolute_daily_return_difference"]) <= task.OVERLAP_P99_ABS_RETURN_TOLERANCE for row in overlap)
    assert all(float(row["daily_return_correlation"]) >= task.OVERLAP_MIN_RETURN_CORRELATION for row in overlap)
    assert all(row["reconciliation_passed"] == "True" for row in overlap)
    assert all("2026-02-02" in row["known_provider_anomaly_disclosure"] for row in manifest)


def test_every_provider_call_is_read_only_market_data() -> None:
    requests = rows("provider_request_manifest.csv")
    assert requests
    assert all(row["http_method"] == "GET" for row in requests)
    assert all(row["endpoint"] == "/v2/stocks/bars" for row in requests)
    assert all(row["credentials_or_secrets_persisted"] == "False" for row in requests)
    assert all(row["broker_account_position_order_or_transfer_endpoint"] == "False" for row in requests)
    assert not any(token in json.dumps(requests).lower() for token in ("api_key", "secret_key", "authorization:"))


def test_all_47_caches_receive_only_the_13_authorized_sessions() -> None:
    acquisitions = rows("acquisition_results.csv")
    coverage = rows("completed_session_coverage.csv")
    assert len(acquisitions) == len(coverage) == 47
    assert all(row["result"] == "refreshed_and_validated" for row in acquisitions)
    assert all(row["cache_written"] == "True" for row in acquisitions)
    assert all(int(row["rows_added"]) == 13 for row in acquisitions)
    assert all(row["last_completed_session"] == "2026-08-04" for row in coverage)
    assert all(row["observed_new_completed_sessions"] == "13" for row in coverage)
    assert all(row["missing_completed_sessions"] == "" for row in coverage)
    assert all(row["extra_sessions"] == "" for row in coverage)
    assert all(row["coverage_passed"] == "True" for row in coverage)


def test_old_cache_bytes_are_an_exact_prefix_and_old_rows_are_unchanged() -> None:
    reconciliations = {row["symbol"]: row for row in rows("historical_row_reconciliation.csv")}
    hashes = {row["symbol"]: row for row in rows("old_new_cache_hash_manifest.csv")}
    for symbol in task.SYMBOLS:
        current = (ROOT / task.SNAPSHOT_DIR / f"{symbol}.csv").read_bytes()
        old_row_count = int(reconciliations[symbol]["old_row_count"])
        old_prefix = b"".join(current.splitlines(keepends=True)[: old_row_count + 1])
        assert hashlib.sha256(old_prefix).hexdigest() == hashes[symbol]["old_file_sha256"]
        assert reconciliations[symbol]["previous_rows_value_identical"] == "True"
        assert reconciliations[symbol]["provider_adjustment_revision_applied_to_old_rows"] == "False"


def test_canonical_adjustment_formula_and_ohlcv_quality() -> None:
    quality = rows("data_quality_results.csv")
    assert len(quality) == 47
    assert all(row["quality_pass"] == "True" for row in quality)
    assert all(row["duplicate_date_count"] == "0" for row in quality)
    assert all(row["invalid_adjusted_ohlc_count"] == "0" for row in quality)
    assert all(row["invalid_raw_ohlc_count"] == "0" for row in quality)
    assert all(row["after_cutoff_count"] == "0" for row in quality)
    for symbol in task.SYMBOLS:
        frame = pd.read_csv(ROOT / task.SNAPSHOT_DIR / f"{symbol}.csv").tail(13)
        factor = frame["raw_adj_close"] / frame["raw_close"]
        for field in ("open", "high", "low", "close"):
            pd.testing.assert_series_equal(
                frame[field].reset_index(drop=True),
                (frame[f"raw_{field}"] * factor).reset_index(drop=True),
                check_names=False,
                rtol=1e-12,
                atol=1e-12,
            )
        pd.testing.assert_series_equal(frame["adj_close"].reset_index(drop=True), frame["raw_adj_close"].reset_index(drop=True), check_names=False)
        pd.testing.assert_series_equal(frame["volume"].reset_index(drop=True), frame["raw_volume"].reset_index(drop=True), check_names=False)


def test_atomic_writer_replaces_only_after_valid_payload(tmp_path: Path) -> None:
    target = tmp_path / "atomic.txt"
    target.write_bytes(b"old\n")
    task.atomic_write_bytes(target, b"new\n")
    assert target.read_bytes() == b"new\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_metadata_groups_readiness_and_entity_counts_reconcile() -> None:
    groups = rows("economic_group_map.csv")
    readiness = rows("research_readiness_map.csv")
    checks = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert len(groups) == 47
    assert all(row["metadata_changed"] == "False" for row in groups)
    assert len(readiness) == 11
    assert all(row["readiness_status"] == "ready_for_nonperformance_research_design" for row in readiness)
    assert all(row["strategy_formula_defined"] == "False" for row in readiness)
    assert checks["direction_correction_count"] == 1
    assert checks["operational_universe_record_count"] == 47
    assert checks["data_capability_record_count"] == 47
    assert checks["process_task_record_count"] == 1
    assert checks["new_strategy_configuration_count"] == 0
    assert checks["experiment_trial_count"] == 0
    assert checks["paper_demo_observation_count"] == 0
    assert checks["strategy_performance_calculated"] is False
    assert checks["backtest_run"] is False


def test_protected_state_prior_packet_and_source_inputs_are_unchanged() -> None:
    reconciliation = rows("protected_state_reconciliation.csv")
    checks = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert reconciliation
    assert all(row["unchanged"] == "True" for row in reconciliation)
    assert checks["prior_blocked_packet_preserved"] is True
    assert checks["protected_state_and_source_inputs_unchanged"] is True
    assert checks["overall_pass"] is True

