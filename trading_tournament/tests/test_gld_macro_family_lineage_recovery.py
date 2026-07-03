from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "gld_macro_family_lineage_recovery" / "latest"
MANIFEST = EVIDENCE / "gld_macro_lineage_recovery_manifest.json"
CONSISTENCY = EVIDENCE / "gld_macro_lineage_recovery_consistency_check.json"

VALID_NEXT_ACTIONS = {
    "design_macro_gld_duration_risk_off_bounded_research_lane",
    "block_macro_gld_research_until_lineage_inputs_completed",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_guardrails_and_selection() -> None:
    manifest = load_json(MANIFEST)

    assert manifest["selected_task"] == "recover_gld_macro_family_lineage"
    assert manifest["selected_family"] == "macro_gld_duration_risk_off"
    assert manifest["selection_from_existing_roadmap_registry_only"] is True
    assert manifest["volatility_throttle_lane_excluded"] is True
    assert manifest["lineage_recovery_only"] is True
    assert manifest["historical_evidence_generation_only"] is True

    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["hidden_parameter_grid_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True

    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["exact_rejected_variants_reopened"] is False
    assert manifest["alpaca_execution_module_delegated"] is True


def test_lineage_recovery_outputs_are_context_only() -> None:
    manifest = load_json(MANIFEST)
    rows = load_csv(EVIDENCE / "corrected_macro_rows.csv")
    lineage_rows = load_csv(EVIDENCE / "lineage_recovery_table.csv")

    assert manifest["lineage_recovery_supported_by_label_audit"] is True
    assert manifest["ledger_requires_recovery_before_reopening"] is True
    assert manifest["macro_rows_recovered_count"] == 10
    assert manifest["all_recovered_rows_non_promotable"] is True
    assert manifest["all_recovered_rows_not_paper_forward"] is True
    assert manifest["source_evidence_missing_count"] == 0
    assert manifest["usable_diagnostic_evidence"] is True
    assert manifest["lineage_recovery_completed"] is True

    assert len(rows) == 10
    assert len(lineage_rows) == 10
    assert {row["family_id"] for row in rows} == {"macro_gld_duration_risk_off"}
    assert {row["research_label"] for row in rows} == {"research_signal_lineage_blocked"}
    assert {row["promotion_eligibility"] for row in rows} == {"False"}
    assert {row["paper_forward_eligibility"] for row in rows} == {"False"}
    assert {
        row["lineage_status_after_recovery"] for row in lineage_rows
    } == {"lineage_recovered_context_only_not_reopened"}


def test_required_files_and_next_action() -> None:
    manifest = load_json(MANIFEST)
    consistency = load_json(CONSISTENCY)

    required = [
        "gld_macro_lineage_recovery_manifest.json",
        "gld_macro_lineage_recovery_summary.md",
        "selected_task_rationale.md",
        "source_evidence_inventory.md",
        "corrected_macro_rows.csv",
        "lineage_recovery_table.csv",
        "registry_macro_gld_snippets.md",
        "historical_decision_timeline.md",
        "lineage_recovery_findings.md",
        "blockers_and_data_gaps.md",
        "do_not_promote_from_lineage_recovery.md",
        "gld_macro_lineage_recovery_next_action.md",
        "gld_macro_lineage_recovery_consistency_check.json",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name

    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["next_action_valid"] is True
    assert consistency["consistency_passed"] is True
