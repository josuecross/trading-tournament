import json
from pathlib import Path

from strategy_lab.research_os.research_engine_audit import (
    OUTPUT_DIR,
    REQUIRED_FILES,
    VALID_CLASSIFICATIONS,
    VALID_FINAL_RECOMMENDATIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def test_independent_research_engine_audit_packet() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = json.loads((output / "research_engine_audit_manifest.json").read_text(encoding="utf-8"))
    consistency = json.loads((output / "research_engine_audit_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_FILES:
        assert (output / filename).exists(), filename

    assert manifest["independent_research_engine_audit_only"] is True
    assert manifest["strategy_discovery_run"] is False
    assert manifest["new_sandbox_batch_run"] is False
    assert manifest["new_strategy_backtests_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_tests_run"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_live_action"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["strategy_promotion"] is False
    assert manifest["rejected_variant_reopened"] is False
    assert manifest["active_observations_mutated"] is False
    assert manifest["static_all_weather_status_changed"] is False

    assert manifest["final_recommendation"] in VALID_FINAL_RECOMMENDATIONS
    assert manifest["next_action"] == manifest["final_recommendation"]
    assert manifest["next_action"] == "split_operations_and_research_tracks"
    assert set(manifest["area_classifications"]) == {
        "data_pipeline",
        "signal_execution_timing",
        "backtester_calculation",
        "benchmark_alignment",
        "registry_state",
        "evidence_lineage",
        "gate_and_scoring",
        "lost_family_lineage",
    }
    assert all(value in VALID_CLASSIFICATIONS for value in manifest["area_classifications"].values())
    assert manifest["blocking_issue_found"] is False
    assert manifest["gld_macro_lineage_needs_recovery"] is True
    assert manifest["research_engine_rebuild_recommended"] is False
    assert manifest["operations_and_research_split_recommended"] is True


def test_independent_research_engine_audit_summary_names_guardrails() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR
    summary = (output / "research_engine_audit_summary.md").read_text(encoding="utf-8")
    next_action = (output / "research_engine_audit_next_action.md").read_text(encoding="utf-8")

    assert "Final recommendation: `split_operations_and_research_tracks`" in summary
    assert "strategy discovery" in summary
    assert "provider downloads" in summary
    assert "`split_operations_and_research_tracks`" in next_action
    assert "does not authorize strategy discovery" in next_action
