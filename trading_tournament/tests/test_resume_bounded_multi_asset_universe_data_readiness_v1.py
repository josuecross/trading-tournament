from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import resume_bounded_multi_asset_universe_data_readiness_v1 as task


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / task.OUTPUT_DIR


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_required_packet_and_exact_blocked_outcome() -> None:
    assert {path.name for path in OUTPUT.iterdir()} == set(task.OUTPUT_FILES)
    manifest = yaml.safe_load((OUTPUT / "data_readiness_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["outcome"] == "authoritative_universe_freeze_blocked"
    assert manifest["next_action"] == "direction_owner_review_bounded_universe_freeze_v1"
    assert manifest["authoritative_broad_freeze_identified"] is False


def test_latest_accepted_pilot_is_preserved_as_context_only() -> None:
    rows = read_csv("authoritative_universe_snapshot.csv")
    source = task.read_csv(ROOT / task.PILOT_COMPAT_DIR / "accepted_final_47_universe.csv")
    assert len(rows) == 47
    assert [row["symbol"] for row in rows] == [row["symbol"] for row in source]
    assert all(row["membership_status"] == "accepted_pilot_context" for row in rows)
    assert all(row["authoritative_for_requested_80_150_scope"] == "False" for row in rows)


def test_separate_expansion_is_not_silently_merged() -> None:
    summary = read_csv("outcome_summary.csv")[0]
    assert summary["authoritative_pilot_count"] == "47"
    assert summary["separate_approved_expansion_count"] == "8"
    assert summary["union_count_without_authorized_merge"] == "49"
    blocked = {row["symbol_or_scope"]: row for row in read_csv("blocked_symbols.csv")}
    assert {"EFAV", "EEMV"}.issubset(blocked)


def test_no_provider_or_broker_scope_was_reached() -> None:
    rows = read_csv("provider_request_manifest.csv")
    assert len(rows) == 47
    assert all(row["provider_request_attempted"] == "False" for row in rows)
    assert all(row["account_position_order_or_transfer_endpoint_called"] == "False" for row in rows)
    assert all(row["secret_value_persisted"] == "False" for row in rows)
    assert all(row["request_status"] == "not_attempted_authoritative_universe_freeze_blocked" for row in rows)


def test_existing_pilot_snapshots_are_validated_without_mutation() -> None:
    quality = read_csv("data_quality_results.csv")
    hashes = read_csv("cache_hash_manifest.csv")
    assert len(quality) == len(hashes) == 47
    assert all(row["quality_pass"] == "True" for row in quality)
    assert all(row["deterministic_reload_match"] == "True" for row in quality)
    assert all(row["existing_historical_rows_changed"] == "False" for row in quality)
    assert all(row["cache_changed"] == "False" for row in hashes)
    assert all(row["file_sha256_before"] == row["file_sha256_after"] for row in hashes)


def test_cache_inventory_reports_staleness_instead_of_refreshing() -> None:
    rows = read_csv("existing_cache_inventory.csv")
    assert len(rows) == 47
    assert all(row["preliminary_readiness"] == "refresh_required" for row in rows)
    assert all(row["stale_ending_status"] == "stale_refresh_not_authorized" for row in rows)
    acquisitions = read_csv("acquisition_results.csv")
    assert all(row["acquisition_authorized"] == "False" for row in acquisitions)
    assert all(row["cache_written"] == "False" for row in acquisitions)


def test_economic_metadata_is_complete_and_nonperformance_based() -> None:
    rows = read_csv("economic_group_map.csv")
    assert len(rows) == 47
    assert all(row["primary_economic_group"] for row in rows)
    assert all(row["instrument_role"] for row in rows)
    assert all(row["mapping_performance_based"] == "False" for row in rows)
    assert all(row["mapping_status"] == "complete_for_pilot_context" for row in rows)


def test_compatibility_map_is_capability_only() -> None:
    rows = read_csv("research_compatibility_map.csv")
    assert len(rows) == 11
    assert all(row["capability_status"] == "blocked_authoritative_universe_freeze" for row in rows)
    assert not any("strategy_id" in row or "trial_id" in row for row in rows)


def test_entity_counts_and_prohibited_work_are_zero() -> None:
    checks = read_json("consistency_check.json")
    assert checks["new_strategy_configuration_count"] == 0
    assert checks["new_experiment_trial_count"] == 0
    assert checks["new_benchmark_strategy_count"] == 0
    assert checks["robustness_trial_count"] == 0
    assert checks["validation_observation_count"] == 0
    assert checks["paper_demo_observation_count"] == 0
    assert checks["strategy_performance_calculated"] is False
    assert checks["backtest_run"] is False
    assert checks["technical_factory_v3_launched"] is False


def test_protected_state_caches_and_source_inputs_are_unchanged() -> None:
    rows = read_csv("protected_state_reconciliation.csv")
    assert rows
    assert all(row["unchanged"] == "True" for row in rows)
    checks = read_json("consistency_check.json")
    assert checks["protected_state_unchanged"] is True
    assert checks["market_data_caches_unchanged"] is True
    assert checks["source_inputs_unchanged"] is True
    assert checks["overall_pass"] is True
