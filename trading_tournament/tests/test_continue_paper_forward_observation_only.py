import json
from pathlib import Path

from strategy_lab.research_os.operations.observation_checkpoint import (
    DSR_ID,
    OBSERVATION_LOGS_MISSING,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    VM_ID,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "observation_only_manifest.json").read_text(encoding="utf-8"))


def test_observation_only_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "observation_only_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["observation_only"] is True
    assert manifest["operations_track_used_as_authoritative"] is True
    assert manifest["research_track_paused"] is True
    assert manifest["archive_lineage_track_preserved"] is True
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
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["indicator_library_dependency_added"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["active_strategy_state_changed"] is False
    assert manifest["rejected_strategy_state_changed"] is False
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["intraday_research_remains_paused"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS


def test_active_observation_status_and_logs_are_recorded() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()

    assert manifest["current_active_observation_count"] == 2
    assert manifest["active_observation_ids"] == [VM_ID, DSR_ID]
    assert manifest["active_vm_observation_exists"] is True
    assert manifest["active_vm_status"] == "active_paper_demo_observation"
    assert manifest["active_vm_rules_unchanged"] is True
    assert manifest["active_dsr_observation_exists"] is True
    assert manifest["active_dsr_status"] == "active_paper_demo_observation"
    assert manifest["active_dsr_rules_unchanged"] is True
    assert manifest["static_all_weather_state"] == "benchmark_control_only"
    assert manifest["observation_logs_status"] == OBSERVATION_LOGS_MISSING
    assert manifest["next_action"] == "manual_review_required_for_observation_logs"

    assert (output / "observation_logs_review.md").exists()
    assert (output / "future_manual_review_triggers.md").exists()
    assert (output / "forbidden_next_steps.md").exists()
    assert OBSERVATION_LOGS_MISSING in (output / "observation_logs_review.md").read_text(encoding="utf-8")


def test_research_and_archive_state_are_preserved() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["research_track_paused"] is True
    assert manifest["sandbox_batch_authorization"] is False
    assert manifest["strategy_discovery_authorization"] is False
    assert manifest["candidate_exhaustive_authorization"] is False
    assert manifest["paper_forward_candidate_creation_authorization"] is False
    assert manifest["provider_download_authorization"] is False
    assert manifest["intraday_data_authorization"] is False
    assert manifest["broker_live_authorization"] is False
    assert manifest["gld_macro_recovery_status"] == "queued_not_run"
    assert manifest["family_lineage_ledger_exists"] is True
    assert manifest["authoritative_state_policy_exists"] is True
    assert manifest["evidence_lineage_policy_exists"] is True
