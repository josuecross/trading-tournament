from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import (
    activate_faa_prospective_validation_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return yaml.safe_load((OUTPUT / "activation_manifest.yaml").read_text(encoding="utf-8"))


def require_output() -> None:
    if not (OUTPUT / "consistency_check.json").exists():
        pytest.skip("artifact assertions run after the bounded activation runner")


def test_offline_gate_traverses_complete_flow_without_network() -> None:
    if task.ACTIVE_DIR.exists():
        reconciliation = rows("design_reconciliation.csv")
        imports = rows("offline_import_and_dependency_preflight.csv")
        dry_run = rows("offline_activation_dry_run.csv")
        gate = rows("offline_gate_results.csv")
        assert {row["status"] for row in reconciliation} == {"pass"}
        assert {row["status"] for row in imports} == {"pass"}
        assert len(dry_run) == 17
        assert {row["status"] for row in dry_run} == {"pass"}
        assert {row["network_access"] for row in dry_run} == {"false"}
        assert {row["canonical_cache_write"] for row in dry_run} == {"false"}
        assert {row["status"] for row in gate} == {"pass"}
    else:
        result = task.offline_gate()
        assert result["passed"] is True
        assert all(result["reconciliation_checks"].values())
        assert {row["status"] for row in result["import_rows"]} == {"pass"}
        assert len(result["dry_run_rows"]) == 17
        assert {row["status"] for row in result["dry_run_rows"]} == {"pass"}
        assert {row["network_access"] for row in result["dry_run_rows"]} == {False}
        assert {row["canonical_cache_write"] for row in result["dry_run_rows"]} == {False}
        assert result["protected_before"] == result["protected_after"]


def test_activation_calendar_uses_following_regular_session() -> None:
    now = datetime(2026, 8, 2, 18, 0, tzinfo=timezone.utc)
    dates = task.activation_dates(now)
    assert dates["latest_completed_session"].isoformat() == "2026-07-31"
    assert dates["formation_date"].isoformat() == "2026-07-31"
    assert dates["formation_start_date"].isoformat() == "2026-03-31"
    assert dates["request_start"].isoformat() == "2026-03-30"
    assert dates["intended_execution_session"].isoformat() == "2026-08-03"
    assert dates["on_time_current_formation"] is True


def test_duplicate_retrieval_comparison_detects_any_value_change() -> None:
    frame = pd.DataFrame(
        {
            "trading_date": ["2026-07-30", "2026-07-31"],
            "adjusted_close": [100.0, 101.0],
        }
    )
    first = {symbol: frame.copy() for symbol in task.SYMBOLS}
    second = {symbol: frame.copy() for symbol in task.SYMBOLS}
    result, passed = task.reproduce_frames(first, second)
    assert passed is True
    assert len(result) == 7
    second["SPY"].loc[1, "adjusted_close"] = 101.01
    _result, changed = task.reproduce_frames(first, second)
    assert changed is False


def test_faa_formation_and_comparator_targets_are_deterministic() -> None:
    frames = task.fixture_frames()
    formation = task.compute_formation(
        frames,
        task.last_regular_session_of_month(2026, 1),
        task.last_regular_session_of_month(2026, 5),
    )
    targets_1 = task.compute_targets(formation)
    formation_2 = task.compute_formation(
        frames,
        task.last_regular_session_of_month(2026, 1),
        task.last_regular_session_of_month(2026, 5),
    )
    targets_2 = task.compute_targets(formation_2)
    assert targets_1 == targets_2
    assert tuple(targets_1) == task.COMPARATORS
    assert len(formation["pairwise_correlations"]) == 21
    assert len(formation["selection"]) == 3
    assert all(abs(sum(target.values()) - 1.0) <= 1e-12 for target in targets_1.values())


def test_initialization_costs_do_not_create_validation_return_or_nav_change() -> None:
    formation = task.compute_formation(
        task.fixture_frames(),
        task.last_regular_session_of_month(2026, 1),
        task.last_regular_session_of_month(2026, 5),
    )
    ledgers = task.initialization_ledgers(task.compute_targets(formation))
    assert len(ledgers) == 7
    assert {row["validation_return_created"] for row in ledgers} == {False}
    assert {row["completed_interval_created"] for row in ledgers} == {False}
    assert {row["differentiation_month_credit"] for row in ledgers} == {0}
    assert {row["validation_NAV_5bps"] for row in ledgers} == {1.0}


def test_required_outputs_and_entity_counts_after_runner() -> None:
    require_output()
    value = manifest()
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    assert value["new_strategy_configurations"] == 0
    assert value["updated_strategy_configurations"] == 0
    assert value["paper_demo_observations_created"] == 0
    assert value["completed_validation_performance_rows"] == 0
    assert value["benchmark_specifications_carried_forward"] == 7
    assert value["data_capability_tasks"] == 1
    assert value["process_tasks"] == 1
    if value["outcome"] == task.ACTIVATED:
        assert value["experiment_trials_created"] == 1
        assert value["validation_observations_created"] == 1
        assert value["initialization_records_created"] == 1
    else:
        assert value["experiment_trials_created"] == 0
        assert value["validation_observations_created"] == 0
        assert value["initialization_records_created"] == 0


def test_successful_activation_has_exact_trial_and_observation_or_zero_rows() -> None:
    require_output()
    value = manifest()
    trials = rows("validation_trial_record.csv")
    observations = rows("validation_observation_record.csv")
    if value["outcome"] == task.ACTIVATED:
        assert len(trials) == 1
        assert trials[0]["trial_id"] == task.TRIAL_ID
        assert trials[0]["parent_trial_id"] == task.PARENT_TRIAL_ID
        assert trials[0]["route"] == "standalone_only"
        assert trials[0]["outcome"] == ""
        assert len(observations) == 1
        assert observations[0]["validation_observation_id"] == task.OBSERVATION_ID
        assert observations[0]["paper_demo_observation"] == "false"
        assert observations[0]["completed_holding_intervals"] == "0"
        assert task.ACTIVE_DIR.exists()
    else:
        assert trials == []
        assert observations == []


def test_provider_data_is_reproducible_and_snapshots_are_immutable_on_success() -> None:
    require_output()
    value = manifest()
    if value["outcome"] != task.ACTIVATED:
        pytest.skip("activation data gate did not pass")
    reproducibility = rows("retrieval_reproducibility.csv")
    coverage = rows("required_session_coverage.csv")
    snapshots = rows("immutable_daily_snapshot_manifest.csv")
    assert len(reproducibility) == 7
    assert {row["reproducibility_status"] for row in reproducibility} == {"pass"}
    assert len(coverage) == 7
    assert {row["coverage_status"] for row in coverage} == {"pass"}
    assert len(snapshots) == 7
    assert {row["immutable"] for row in snapshots} == {"true"}
    assert {row["overwrite_permitted"] for row in snapshots} == {"false"}
    assert {row["validation_performance_rows"] for row in snapshots} == {"0"}
    assert {row["stored_snapshot_hash_verified"] for row in snapshots} == {"true"}
    for row in snapshots:
        snapshot_path = task.ROOT / row["snapshot_path"]
        assert task.file_hash(snapshot_path) == row["snapshot_hash"]


def test_frozen_boundaries_and_zero_performance_ledgers() -> None:
    require_output()
    state = yaml.safe_load((OUTPUT / "validation_state.yaml").read_text(encoding="utf-8"))
    check = payload("consistency_check.json")
    assert rows("daily_performance_ledger.csv") == []
    assert rows("monthly_checkpoint_ledger.csv") == []
    assert check["completed_validation_performance_rows"] == 0
    assert check["historical_backfill_performed"] is False
    assert check["validation_decision_made"] is False
    if manifest()["outcome"] == task.ACTIVATED:
        assert state["elapsed_completed_months"] == 0
        assert state["completed_holding_intervals"] == 0
        assert state["differentiation_months_vs_return_only"] == 0
        assert state["differentiation_months_vs_no_correlation"] == 0
        assert state["decision_boundary"] == task.DECISION_BOUNDARY
        active_boundary = yaml.safe_load(
            (task.ACTIVE_DIR / "decision_boundary.yaml").read_text(encoding="utf-8")
        )
        assert active_boundary == task.DECISION_BOUNDARY


def test_consistency_preserves_protected_state_and_forbids_broker_activity() -> None:
    require_output()
    check = payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["offline_gate_pass"] is True
    assert check["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert check["canonical_cache_modified"] is False
    assert check["account_endpoint_called"] is False
    assert check["position_endpoint_called"] is False
    assert check["order_endpoint_called"] is False
    assert check["broker_submission"] is False
    assert check["paper_order_submission"] is False
    assert check["real_money_authorization"] is False
    assert check["lifecycle_state_changed"] is False
    assert check["paper_demo_activity"] is False
    assert check["vix_fix_state_changed"] is False
    assert check["psar_state_changed"] is False
    assert check["stored_snapshot_file_hashes_verified"] is True
    assert check["immutable_snapshot_records_overwritten"] is False
    assert check["prospective_decision_boundary_frozen_in_active_state"] is True
