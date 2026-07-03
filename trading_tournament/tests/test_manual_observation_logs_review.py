import json
from pathlib import Path

from strategy_lab.research_os.operations.manual_observation_logs_review import (
    DSR_ID,
    LOG_ROOT,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    VM_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "observation_logs_review_manifest.json").read_text(encoding="utf-8"))


def test_manual_observation_logs_review_strict_scope() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "observation_logs_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["manual_observation_log_review_only"] is True
    assert manifest["observation_logs_missing_or_not_available"] is True
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
    assert manifest["next_action"] == "create_initial_manual_observation_snapshots"


def test_canonical_schema_templates_and_placeholders_exist() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()

    assert manifest["current_active_observation_count"] == 2
    assert manifest["active_observation_ids"] == [VM_ID, DSR_ID]
    assert manifest["canonical_log_schema_created"] is True
    assert manifest["manual_checkpoint_template_created"] is True
    assert manifest["placeholder_snapshots_created"] is True

    assert (output / "canonical_observation_log_schema.md").exists()
    assert (output / "manual_checkpoint_template.md").exists()
    assert (output / "missing_observation_evidence.md").exists()
    assert (output / "no_broker_no_live_policy.md").exists()

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        assert (log_dir / "observation_metadata.yaml").exists()
        assert (log_dir / "frozen_rules_reference.md").exists()
        assert (log_dir / "target_allocation_snapshot.yaml").exists()
        assert (log_dir / "manual_checkpoint_template.md").exists()
        assert (log_dir / "latest_manual_checkpoint.md").exists()
        assert (log_dir / "position_snapshot_template.csv").exists()
        assert (log_dir / "order_snapshot_template.csv").exists()
        assert (log_dir / "equity_snapshot_template.csv").exists()
        assert (log_dir / "benchmark_snapshot_template.csv").exists()
        assert (log_dir / "issues_log.md").exists()
        assert (log_dir / "notes.md").exists()


def test_placeholders_do_not_invent_operational_values() -> None:
    run(ROOT)

    for strategy_id in (VM_ID, DSR_ID):
        log_dir = ROOT / LOG_ROOT / strategy_id
        metadata = (log_dir / "observation_metadata.yaml").read_text(encoding="utf-8")
        target = (log_dir / "target_allocation_snapshot.yaml").read_text(encoding="utf-8")
        checkpoint = (log_dir / "latest_manual_checkpoint.md").read_text(encoding="utf-8")

        assert (
            "status: placeholder_created_manual_input_required" in metadata
            or "status: initial_manual_snapshot_created_manual_input_required" in metadata
        )
        assert "start_date: unknown" in metadata
        assert "rule_hash_or_checksum: unknown" in metadata
        assert "broker_derived_values: false" in metadata
        assert "invented_equity: false" in metadata
        assert "invented_positions: false" in metadata
        assert "invented_orders: false" in metadata
        assert "target_weights: unknown" in target or "target_weights: unknown_current_signal_required" in target
        assert "observed_weights: unknown" in target
        assert "Equity/account value: `unknown`" in checkpoint or "Equity/account snapshot status: `unknown`" in checkpoint
        assert "Open orders: `unknown`" in checkpoint or "Open order status: `unknown`" in checkpoint
