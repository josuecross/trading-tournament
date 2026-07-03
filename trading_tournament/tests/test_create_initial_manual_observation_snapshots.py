import csv
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.operations.initial_manual_snapshots import (
    DSR_ID,
    LOG_ROOT,
    NEXT_ACTION_MANUAL_INPUT,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    VM_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "initial_manual_snapshots_manifest.json").read_text(encoding="utf-8"))


def test_initial_manual_snapshot_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "initial_manual_snapshots_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["initial_manual_snapshot_step_only"] is True
    assert manifest["manual_input_required"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["research_track_paused"] is True
    assert manifest["gld_macro_recovery_run"] is False
    assert manifest["new_sandbox_batch_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["formal_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["future_preregistration_candidates_created"] is False
    assert manifest["formal_preregistration_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_review"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["active_strategy_state_changed"] is False
    assert manifest["rejected_strategy_state_changed"] is False
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["intraday_research_remains_paused"] is True
    assert manifest["target_weights_invented"] is False
    assert manifest["equity_values_invented"] is False
    assert manifest["positions_invented"] is False
    assert manifest["orders_invented"] is False
    assert manifest["benchmark_values_invented"] is False
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_MANUAL_INPUT


def test_initial_snapshot_files_created_for_active_observations() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["current_active_observation_count"] == 2
    assert manifest["active_observation_ids"] == [VM_ID, DSR_ID]
    assert manifest["vm_initial_snapshot_created"] is True
    assert manifest["dsr_initial_snapshot_created"] is True
    assert manifest["unknown_values_preserved"] is True

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        assert (log_dir / "latest_manual_checkpoint.md").exists()
        assert (log_dir / "initial_manual_checkpoint.md").exists()
        assert (log_dir / "observation_metadata.yaml").exists()
        assert (log_dir / "target_allocation_snapshot.yaml").exists()
        assert (log_dir / "initial_position_snapshot.csv").exists()
        assert (log_dir / "initial_order_snapshot.csv").exists()
        assert (log_dir / "initial_equity_snapshot.csv").exists()
        assert (log_dir / "initial_benchmark_snapshot.csv").exists()
        assert (log_dir / "issues_log.md").exists()
        assert (log_dir / "notes.md").exists()


def test_unknown_values_are_explicit_and_not_invented() -> None:
    run(ROOT)

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        metadata = yaml.safe_load((log_dir / "observation_metadata.yaml").read_text(encoding="utf-8"))
        target = yaml.safe_load((log_dir / "target_allocation_snapshot.yaml").read_text(encoding="utf-8"))
        checkpoint = (log_dir / "latest_manual_checkpoint.md").read_text(encoding="utf-8")

        assert metadata["status"] == "initial_manual_snapshot_created_manual_input_required"
        assert metadata["start_date"] == "unknown"
        assert metadata["rule_hash_or_checksum"] == "unknown"
        assert metadata["target_weights_available"] is False
        assert metadata["observed_weights_available"] is False
        assert metadata["latest_equity_snapshot_available"] is False
        assert metadata["latest_positions_available"] is False
        assert metadata["latest_orders_available"] is False
        assert metadata["latest_benchmark_snapshot_available"] is False
        assert metadata["broker_derived_values"] is False
        assert metadata["invented_target_weights"] is False
        assert metadata["invented_equity"] is False
        assert metadata["invented_positions"] is False
        assert metadata["invented_orders"] is False
        assert metadata["invented_benchmark_values"] is False
        assert metadata["manual_input_required"] is True

        assert target["status"] == "initial_manual_snapshot_created_manual_input_required"
        assert target["target_weight_status"] == "unknown_current_signal_required"
        assert target["target_weights"] == "unknown_current_signal_required"
        assert target["observed_weights"] == "unknown"
        assert target["cash_weight"] == "unknown"
        assert target["calculated_from_market_data"] is False
        assert target["broker_derived_values"] is False
        assert target["invented_values"] is False
        assert target["manual_input_required"] is True

        assert "`manual_input_required_before_clean_observation`" in checkpoint
        assert "Rule hash/checksum status: `unknown`" in checkpoint
        assert "Target allocation status: `unknown_current_signal_required`" in checkpoint
        assert "Equity/account snapshot status: `unknown`" in checkpoint
        assert "No broker API call was made" in checkpoint


def test_snapshot_csv_rows_have_no_blank_operational_values() -> None:
    run(ROOT)

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        for filename in (
            "initial_position_snapshot.csv",
            "initial_order_snapshot.csv",
            "initial_equity_snapshot.csv",
            "initial_benchmark_snapshot.csv",
        ):
            rows = list(csv.DictReader((log_dir / filename).open(newline="", encoding="utf-8")))
            assert len(rows) == 1
            assert all(value != "" for value in rows[0].values())
            assert rows[0]["source"] == "manual_input_required"


def test_manual_checklist_missing_values_and_no_broker_files_exist() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR

    checklist = (output / "manual_input_checklist.md").read_text(encoding="utf-8")
    missing = (output / "missing_values_after_initial_snapshot.md").read_text(encoding="utf-8")
    no_broker = (output / "no_broker_no_live_confirmation.md").read_text(encoding="utf-8")

    for strategy_id in (VM_ID, DSR_ID):
        assert strategy_id in checklist
        assert strategy_id in missing

    assert "Current intended target weights: `manual_input_required`" in checklist
    assert "`current_signal_state_required_for_exact_target_weights`" in missing
    assert "Broker API called: `false`" in no_broker
    assert "Orders submitted: `false`" in no_broker
    assert "Real-money recommendation made: `false`" in no_broker
