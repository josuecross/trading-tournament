import json
from pathlib import Path

from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import BATCH_ID
from strategy_lab.research_os.research.profit_oriented_research_batch_v1_after_methodology_fix_audit import (
    NEXT_ACTION_FIX_AGAIN,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "corrected_batch_audit_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "corrected_batch_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_corrected_batch_audit_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = load_consistency()

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["corrected_batch_audit_only"] is True
    assert manifest["batch_id_audited"] == BATCH_ID
    assert manifest["methodology_fix_evidence_reviewed"] is True
    assert manifest["corrected_results_reviewed"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_backtests_run"] is False
    assert manifest["new_performance_metrics_from_raw_data_computed"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
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
    assert manifest["alpaca_execution_module_delegated"] is True


def test_corrected_methodology_and_exposure_conclusions() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["methodology_fix_accepted"] is True
    assert manifest["exposure_weighting_issue_resolved"] is True
    assert manifest["cash_bil_issue_resolved"] is True
    assert manifest["return_benchmark_interpretation_valid"] is True
    assert manifest["average_exposure_gt_1_count"] == 0
    assert manifest["average_exposure_gt_2_count"] == 0
    assert manifest["max_daily_exposure"] <= 1.000001
    assert manifest["max_daily_weight_sum"] <= 1.000001
    assert manifest["negative_weight_violation_count"] == 0
    assert manifest["nan_weight_count"] == 0
    assert manifest["impossible_cash_bil_plus_risky_row_count"] == 0
    assert manifest["impossible_cash_bil_plus_risky_day_count"] == 0


def test_scoring_labeling_and_deeper_research_rejected_pending_fix() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["scoring_labeling_valid"] is False
    assert manifest["high_risk_underlabeled_count"] > 0
    assert manifest["favorable_zero_drawdown_score_label_count"] > 0
    assert manifest["source_deeper_research_family_count"] == 2
    assert manifest["deeper_research_family_count_accepted"] == 0
    assert manifest["high_return_tactical_deeper_research_accepted"] is False
    assert manifest["macro_gld_deeper_research_accepted"] is False
    assert manifest["gld_macro_lineage_blocks_deeper_research"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_FIX_AGAIN


def test_required_audit_files_contain_expected_findings() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR

    methodology = (output / "methodology_fix_verification.md").read_text(encoding="utf-8")
    exposure = (output / "corrected_exposure_weighting_audit.md").read_text(encoding="utf-8")
    cash = (output / "corrected_cash_bil_audit.md").read_text(encoding="utf-8")
    scoring = (output / "corrected_scoring_label_audit.md").read_text(encoding="utf-8")
    deeper = (output / "deeper_research_family_review.md").read_text(encoding="utf-8")
    guardrails = (output / "non_promotable_guardrail_review.md").read_text(encoding="utf-8")
    next_action = (output / "corrected_batch_audit_next_action.md").read_text(encoding="utf-8")

    assert "Same variant set rerun: `True`" in methodology
    assert "Average exposure > 1 count: `0`" in exposure
    assert "Impossible cash/BIL plus risky rows: `0`" in cash
    assert "major_issue" in scoring
    assert "Accepted by this audit: `0`" in deeper
    assert "Promotion eligibility false for every row: `True`" in guardrails
    assert NEXT_ACTION_FIX_AGAIN in next_action


def test_consistency_check_manifest_flags() -> None:
    run(ROOT)
    consistency = load_consistency()

    assert consistency["methodology_fix_verification_exists"] is True
    assert consistency["corrected_exposure_audit_exists"] is True
    assert consistency["corrected_cash_bil_audit_exists"] is True
    assert consistency["corrected_scoring_label_audit_exists"] is True
    assert consistency["deeper_research_family_review_exists"] is True
    assert consistency["non_promotable_guardrail_review_exists"] is True
    assert consistency["next_action_valid"] is True
    assert consistency["required_files_present"] is True
