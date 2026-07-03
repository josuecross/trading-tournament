import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import BATCH_ID, label_row
from strategy_lab.research_os.research.profit_research_batch_v1_labeling_fix import (
    NEXT_ACTION_AUDIT,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    RISK_LABELS,
    VALID_NEXT_ACTIONS,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "labeling_fix_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "labeling_fix_consistency_check.json").read_text(encoding="utf-8"))


def label_rows() -> list[dict[str, str]]:
    with (ROOT / OUTPUT_DIR / "corrected_label_variant_results.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def base_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "cagr": 0.02,
        "max_drawdown": -0.10,
        "historical_profit_score": 35.0,
        "risk_adjusted_score": 30.0,
        "portfolio_contribution_score": 20.0,
        "drawdown_tolerance_score": 80.0,
        "active_combo_correlation": 0.25,
        "active_combo_blend_total_return_delta": 0.0,
        "active_combo_blend_drawdown_delta": 0.0,
        "lineage_status": "lineage_not_blocking_research_batch",
    }
    row.update(overrides)
    return row


def test_labeling_fix_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = load_consistency()

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["labeling_fix_only"] is True
    assert manifest["batch_id_fixed"] == BATCH_ID
    assert manifest["uses_corrected_methodology_outputs"] is True
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
    assert manifest["exposure_methodology_reopened"] is False


def test_labeling_success_criteria_and_invariants() -> None:
    run(ROOT)
    manifest = load_manifest()

    assert manifest["exposure_invariants_still_valid"] is True
    assert manifest["cash_bil_invariants_still_valid"] is True
    assert manifest["high_return_severe_drawdown_underlabeled_count_before"] > 0
    assert manifest["high_return_severe_drawdown_underlabeled_count_after"] == 0
    assert manifest["favorable_zero_drawdown_score_label_count_before"] > 0
    assert manifest["favorable_zero_drawdown_score_label_count_after"] == 0
    assert manifest["diversifier_label_requires_risk_check"] is True
    assert manifest["invalid_diversifier_label_count_after"] == 0
    assert manifest["macro_gld_lineage_preserved"] is True
    assert manifest["deeper_research_family_count_after_label_fix"] == 0
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_AUDIT


def test_corrected_label_rows_are_non_promotable_and_risk_explicit() -> None:
    run(ROOT)
    rows = label_rows()
    assert rows

    for row in rows:
        assert row["promotion_eligibility"] == "False"
        assert row["paper_forward_eligibility"] == "False"
        cagr = float(row["cagr"])
        max_drawdown = float(row["max_drawdown"])
        drawdown_score = float(row["drawdown_tolerance_score"])
        if cagr >= 0.08 and max_drawdown <= -0.35:
            assert row["research_label"] in RISK_LABELS
        if drawdown_score <= 5 and row["research_label"] in {"research_signal_diversifier", "research_signal_needs_robustness"}:
            raise AssertionError(f"favorable label hid zero drawdown tolerance: {row['variant_id']}")
        if row["family_id"] == "macro_gld_duration_risk_off":
            assert row["lineage_status"] == "lineage_incomplete_research_only"
            assert row["research_label"] == "research_signal_lineage_blocked"


def test_deterministic_label_policy_cases() -> None:
    assert label_row(base_row(cagr=0.12, max_drawdown=-0.55, drawdown_tolerance_score=0.0)) == "research_signal_high_risk"
    assert (
        label_row(
            base_row(
                cagr=0.09,
                max_drawdown=-0.40,
                drawdown_tolerance_score=20.0,
                portfolio_contribution_score=65.0,
                active_combo_correlation=0.25,
                active_combo_blend_total_return_delta=0.08,
                active_combo_blend_drawdown_delta=0.0,
            )
        )
        == "research_signal_high_risk_diversifier"
    )
    assert (
        label_row(
            base_row(
                cagr=0.12,
                max_drawdown=-0.20,
                drawdown_tolerance_score=0.0,
                portfolio_contribution_score=70.0,
                active_combo_correlation=0.20,
                active_combo_blend_total_return_delta=0.08,
            )
        )
        != "research_signal_diversifier"
    )
    assert (
        label_row(base_row(cagr=0.02, max_drawdown=-0.10, portfolio_contribution_score=20.0, active_combo_correlation=0.05))
        == "research_signal_weak"
    )
    assert (
        label_row(
            base_row(
                cagr=0.08,
                max_drawdown=-0.20,
                portfolio_contribution_score=60.0,
                active_combo_correlation=0.10,
                active_combo_blend_total_return_delta=0.05,
                lineage_status="lineage_incomplete_research_only",
            )
        )
        == "research_signal_lineage_blocked"
    )
    assert label_row(base_row(cagr=0.01, max_drawdown=-0.08, portfolio_contribution_score=10.0)) == "research_signal_weak"


def test_required_labeling_files_contain_expected_findings() -> None:
    run(ROOT)
    output = ROOT / OUTPUT_DIR

    high_risk = (output / "high_return_high_drawdown_relabeling.md").read_text(encoding="utf-8")
    diversifier = (output / "diversifier_label_validation.md").read_text(encoding="utf-8")
    macro = (output / "macro_gld_lineage_label_status.md").read_text(encoding="utf-8")
    deeper = (output / "deeper_research_flags_after_label_fix.md").read_text(encoding="utf-8")
    do_not = (output / "do_not_promote_after_labeling_fix.md").read_text(encoding="utf-8")

    assert "Under-labeled after: `0`" in high_risk
    assert "Invalid diversifier labels after fix: `0`" in diversifier
    assert "Macro/GLD lineage preserved: `True`" in macro
    assert "Accepted deeper-research families from this label fix: `0`" in deeper
    assert "non-promotable" in do_not


def test_consistency_check_manifest_flags() -> None:
    run(ROOT)
    consistency = load_consistency()

    assert consistency["exposure_methodology_not_reopened"] is True
    assert consistency["exposure_invariants_still_valid"] is True
    assert consistency["cash_bil_invariants_still_valid"] is True
    assert consistency["high_return_severe_underlabeled_zero"] is True
    assert consistency["favorable_zero_drawdown_labels_zero"] is True
    assert consistency["diversifier_labels_require_risk_check"] is True
    assert consistency["macro_gld_lineage_preserved"] is True
    assert consistency["deeper_research_flags_file_exists"] is True
    assert consistency["do_not_promote_file_exists"] is True
    assert consistency["next_action_valid"] is True
    assert consistency["required_files_present"] is True
