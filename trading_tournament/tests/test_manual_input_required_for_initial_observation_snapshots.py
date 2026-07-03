import json
from pathlib import Path

import yaml

from strategy_lab.research_os.operations import manual_input_snapshot_validation as validation
from strategy_lab.research_os.operations.manual_input_snapshot_validation import (
    DSR_ID,
    LOG_ROOT,
    NEXT_ACTION_MANUAL_INPUT,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    SNAPSHOT_PARTIAL,
    VALID_NEXT_ACTIONS,
    VM_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "manual_input_snapshot_manifest.json").read_text(encoding="utf-8"))


def run_without_manual_file(monkeypatch) -> dict[str, object]:
    monkeypatch.setattr(
        validation,
        "MANUAL_INPUT_CANDIDATES",
        (Path("strategy_lab") / "research_os" / "operations" / "missing_manual_input_values_for_test.yaml",),
    )
    return run(ROOT)


def test_manual_input_snapshot_packet_and_scope_flags(monkeypatch) -> None:
    result = run_without_manual_file(monkeypatch)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "manual_input_snapshot_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["manual_input_snapshot_step_only"] is True
    assert manifest["manual_values_supplied"] is False
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
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_MANUAL_INPUT


def test_snapshot_statuses_and_remaining_inputs(monkeypatch) -> None:
    run_without_manual_file(monkeypatch)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()

    assert manifest["current_active_observation_count"] == 2
    assert manifest["active_observation_ids"] == [VM_ID, DSR_ID]
    assert manifest["vm_snapshot_status"] == SNAPSHOT_PARTIAL
    assert manifest["dsr_snapshot_status"] == SNAPSHOT_PARTIAL
    assert manifest["unknown_values_preserved"] is True

    remaining = (output / "remaining_manual_inputs.md").read_text(encoding="utf-8")
    for strategy_id in (VM_ID, DSR_ID):
        assert strategy_id in remaining
    for token in (
        "observation_start_date",
        "current_intended_target_weights",
        "current_actual_observed_weights",
        "current_account_or_equity_value",
        "current_positions",
        "current_open_orders",
        "benchmark_snapshot_date_and_values",
        "next_checkpoint_cadence",
        "current_signal_state_required_for_exact_target_weights",
    ):
        assert token in remaining


def test_observation_logs_preserve_unknowns_and_do_not_invent_values(monkeypatch) -> None:
    run_without_manual_file(monkeypatch)

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        metadata = yaml.safe_load((log_dir / "observation_metadata.yaml").read_text(encoding="utf-8"))
        target = yaml.safe_load((log_dir / "target_allocation_snapshot.yaml").read_text(encoding="utf-8"))
        checkpoint = (log_dir / "latest_manual_checkpoint.md").read_text(encoding="utf-8")

        assert metadata["status"] == SNAPSHOT_PARTIAL
        assert metadata["manual_values_supplied"] is False
        assert metadata["manual_source_confirmed"] is False
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

        assert target["status"] == SNAPSHOT_PARTIAL
        assert target["target_weight_status"] == "unknown_current_signal_required"
        assert target["target_weights"] == "unknown_current_signal_required"
        assert target["observed_weights"] == "unknown"
        assert target["calculated_from_market_data"] is False
        assert target["broker_derived_values"] is False
        assert target["invented_values"] is False

        assert "`partial_snapshot_manual_inputs_still_required`" in checkpoint
        assert "Manual values supplied: `False`" in checkpoint
        assert "Current intended target weights: `unknown_current_signal_required`" in checkpoint
        assert "Equity/account snapshot: `unknown`" in checkpoint
        assert "No broker API call was made" in checkpoint


def test_required_evidence_files_and_no_broker_confirmation(monkeypatch) -> None:
    run_without_manual_file(monkeypatch)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()

    assert (output / "manual_input_source_review.md").exists()
    assert (output / "vm_manual_input_validation.md").exists()
    assert (output / "dsr_manual_input_validation.md").exists()
    assert (output / "updated_snapshot_status.md").exists()
    assert (output / "remaining_manual_inputs.md").exists()
    assert (output / "no_broker_no_live_confirmation.md").exists()

    no_broker = (output / "no_broker_no_live_confirmation.md").read_text(encoding="utf-8")
    assert "Broker API called: `false`" in no_broker
    assert "Orders submitted: `false`" in no_broker
    assert "Orders canceled: `false`" in no_broker
    assert "Orders reconciled: `false`" in no_broker
    assert "Live order path touched: `false`" in no_broker
    assert "Real-money recommendation made: `false`" in no_broker

    assert manifest["target_weights_invented"] is False
    assert manifest["equity_values_invented"] is False
    assert manifest["positions_invented"] is False
    assert manifest["orders_invented"] is False
    assert manifest["benchmark_values_invented"] is False
