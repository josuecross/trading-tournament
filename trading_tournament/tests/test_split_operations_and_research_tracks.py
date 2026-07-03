import json
from pathlib import Path

import yaml

from strategy_lab.research_os.split_tracks import (
    ACTIVE_OBSERVATIONS_PATH,
    ARCHIVE_INDEX_PATH,
    ARCHIVE_POLICY_PATH,
    FAMILY_LEDGER_PATH,
    OPERATIONS_STATE_PATH,
    OUTPUT_DIR,
    RESEARCH_QUEUE_PATH,
    RESEARCH_STATE_PATH,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "split_tracks_manifest.json").read_text(encoding="utf-8"))


def test_split_tracks_packet_and_strict_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "split_tracks_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["split_tracks_only"] is True
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


def test_track_files_and_family_ledger_exist() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["operations_track_created"] is True
    assert manifest["research_track_created"] is True
    assert manifest["archive_track_created"] is True
    assert manifest["family_lineage_ledger_created"] is True
    assert manifest["gld_macro_recovery_queued"] is True

    assert (ROOT / OPERATIONS_STATE_PATH).exists()
    assert (ROOT / ACTIVE_OBSERVATIONS_PATH).exists()
    assert (ROOT / RESEARCH_STATE_PATH).exists()
    assert (ROOT / RESEARCH_QUEUE_PATH).exists()
    assert (ROOT / ARCHIVE_INDEX_PATH).exists()
    assert (ROOT / ARCHIVE_POLICY_PATH).exists()
    assert (ROOT / FAMILY_LEDGER_PATH).exists()
    assert (ROOT / OUTPUT_DIR / "authoritative_state_policy.md").exists()
    assert (ROOT / OUTPUT_DIR / "evidence_lineage_policy.md").exists()

    active = yaml.safe_load((ROOT / ACTIVE_OBSERVATIONS_PATH).read_text(encoding="utf-8"))
    assert active["research_mutation_allowed"] is False
    assert {row["strategy_id"] for row in active["active_observations"]} == {
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    }
    assert active["benchmark_controls"][0]["strategy_id"] == "static_all_weather_benchmark_v1"
    assert active["benchmark_controls"][0]["state"] == "benchmark_control_only"


def test_research_queue_and_lineage_recovery_are_governance_only() -> None:
    run(ROOT)
    queue = yaml.safe_load((ROOT / RESEARCH_QUEUE_PATH).read_text(encoding="utf-8"))
    ledger = yaml.safe_load((ROOT / FAMILY_LEDGER_PATH).read_text(encoding="utf-8"))

    assert queue["current_expansion_status"] == "paused"
    assert queue["sandbox_batch_authorized"] is False
    assert queue["strategy_discovery_authorized"] is False
    assert queue["candidate_exhaustive_authorized"] is False
    assert queue["paper_forward_candidate_creation_authorized"] is False

    gld_queue = queue["queued_governance_reviews"][0]
    assert gld_queue["id"] == "recover_gld_macro_family_lineage"
    assert gld_queue["status"] == "queued_not_run"
    assert gld_queue["authorizes_backtests"] is False
    assert gld_queue["authorizes_discovery"] is False
    assert gld_queue["authorizes_rejected_row_reopening"] is False

    family_ids = {entry["family_id"] for entry in ledger["entries"]}
    assert {
        "gld_macro_risk_off",
        "managed_futures_etf_wrapper",
        "quality_momentum_etf_proxy",
        "defensive_sector_rotation",
        "volatility_managed_quality_lowvol",
        "breakout_continuation",
        "macro_portfolio_contribution",
        "trend_momentum",
        "volatility_regime",
        "portfolio_combination_sleeve_ensemble",
    }.issubset(family_ids)

    gld = next(entry for entry in ledger["entries"] if entry["family_id"] == "gld_macro_risk_off")
    assert gld["lineage_recovery_needed"] is True
    assert gld["future_research_allowed"] is False
    assert gld["required_next_review_before_reopening"] == "recover_gld_macro_family_lineage"
