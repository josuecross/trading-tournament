import json
from pathlib import Path

from strategy_lab.research_os.research.profit_oriented_research_batch_v1_audit import (
    BATCH_ID,
    NEXT_ACTION_FIX,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "profit_batch_v1_audit_manifest.json").read_text(encoding="utf-8"))


def test_profit_batch_v1_audit_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = json.loads((output / "profit_batch_v1_audit_consistency_check.json").read_text(encoding="utf-8"))

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["profit_batch_v1_audit_only"] is True
    assert manifest["batch_id_audited"] == BATCH_ID
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True
    assert manifest["manual_observation_loop_blocking_research"] is False
    assert manifest["alpaca_execution_module_delegated"] is True


def test_audit_conclusions_and_next_action() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["source_variant_count"] == 58
    assert manifest["source_family_count"] == 5
    assert manifest["methodology_valid"] is False
    assert manifest["exposure_weighting_issue_found"] is True
    assert manifest["cash_bil_issue_found"] is True
    assert manifest["return_calculation_issue_found"] is True
    assert manifest["scoring_labeling_issue_found"] is True
    assert manifest["benchmark_alignment_issue_found"] is False
    assert manifest["gld_macro_lineage_blocks_deeper_research"] is True
    assert manifest["families_deeper_research_accepted_count"] == 0
    assert manifest["average_exposure_gt_1_count"] > 0
    assert manifest["max_average_exposure"] > 1.0
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_FIX


def test_required_audit_review_files_exist_and_contain_findings() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR

    exposure = (output / "exposure_and_weighting_audit.md").read_text(encoding="utf-8")
    cash = (output / "cash_bil_handling_audit.md").read_text(encoding="utf-8")
    returns = (output / "return_calculation_audit.md").read_text(encoding="utf-8")
    benchmark = (output / "benchmark_alignment_audit.md").read_text(encoding="utf-8")
    scoring = (output / "scoring_and_labeling_audit.md").read_text(encoding="utf-8")
    family = (output / "family_deeper_research_review.md").read_text(encoding="utf-8")
    gld = (output / "gld_macro_lineage_review.md").read_text(encoding="utf-8")
    guardrails = (output / "non_promotable_guardrail_review.md").read_text(encoding="utf-8")

    assert "Variants with `average_exposure > 1.0`" in exposure
    assert "blocking_issue" in exposure
    assert "cash/BIL" in cash or "Cash / BIL" in cash
    assert "blocked_by_weighting_issue" in returns
    assert "alignment_code_mostly_valid_but_interpretation_blocked" in benchmark
    assert "reject_current_deeper_research_flags" in family
    assert "not_decision_grade" in scoring
    assert "lineage_incomplete_research_only" in gld
    assert "Promotion eligibility all false" in guardrails
