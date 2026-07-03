import json
from pathlib import Path

from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import BATCH_ID
from strategy_lab.research_os.research.profit_oriented_research_batch_v1_labeling_fix_audit import (
    NEXT_ACTION_HIGH_RETURN,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "labeling_fix_audit_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "labeling_fix_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_labeling_fix_audit_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = load_consistency()

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["labeling_fix_audit_only"] is True
    assert manifest["batch_id_audited"] == BATCH_ID
    assert manifest["labeling_fix_evidence_reviewed"] is True
    assert manifest["corrected_label_results_reviewed"] is True
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


def test_label_fix_accepted_and_direction_selected() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["label_fix_accepted"] is True
    assert manifest["label_overcorrection_found"] is False
    assert manifest["high_return_tactical_broad_return_evidence"] is True
    assert manifest["high_return_tactical_requires_risk_control"] is True
    assert manifest["high_return_tactical_direction_supported"] is True
    assert manifest["macro_gld_lineage_recovery_supported"] is True
    assert manifest["deeper_research_family_count_accepted_after_audit"] == 1
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_HIGH_RETURN


def test_required_audit_reviews_exist_and_contain_findings() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR

    label = (output / "label_correctness_review.md").read_text(encoding="utf-8")
    over = (output / "label_overcorrection_review.md").read_text(encoding="utf-8")
    high = (output / "high_return_tactical_direction_review.md").read_text(encoding="utf-8")
    macro = (output / "macro_gld_lineage_direction_review.md").read_text(encoding="utf-8")
    family = (output / "family_direction_review.md").read_text(encoding="utf-8")
    risk = (output / "risk_control_research_need.md").read_text(encoding="utf-8")
    next_action = (output / "labeling_fix_audit_next_action.md").read_text(encoding="utf-8")

    assert "Under-labeled high-return/severe-drawdown rows after fix: `0`" in label
    assert "no_material_overcorrection" in over
    assert "risk_control_research_candidate" in high
    assert "lineage_blocked_but_visible" in macro
    assert "risk_control_research_candidate" in family
    assert "High-return tactical evidence is broad enough" in risk
    assert NEXT_ACTION_HIGH_RETURN in next_action


def test_non_promotable_guardrails_and_consistency_flags() -> None:
    run(ROOT)
    manifest = load_manifest()
    consistency = load_consistency()
    output = ROOT / OUTPUT_DIR

    assert manifest["non_promotable_guardrails_held"] is True
    guardrails = (output / "non_promotable_guardrail_review.md").read_text(encoding="utf-8")
    assert "Promotion eligibility false for every row: `True`" in guardrails
    assert "Paper-forward eligibility false for every row: `True`" in guardrails

    assert consistency["label_correctness_review_exists"] is True
    assert consistency["label_overcorrection_review_exists"] is True
    assert consistency["high_return_tactical_direction_review_exists"] is True
    assert consistency["macro_gld_lineage_direction_review_exists"] is True
    assert consistency["family_direction_review_exists"] is True
    assert consistency["risk_control_research_need_exists"] is True
    assert consistency["next_action_valid"] is True
    assert consistency["required_files_present"] is True
