import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.profit_research_batch_v1_methodology_fix import (
    NEXT_ACTION_AUDIT_FIXED,
    OUTPUT_DIR,
    REQUIRED_OUTPUT_FILES,
    VALID_NEXT_ACTIONS,
    run,
    run_synthetic_weight_tests,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    BATCH_ID,
    WEIGHT_TOLERANCE,
    complete_rebalance_weight_frame,
)


ROOT = Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "methodology_fix_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict[str, object]:
    return json.loads((ROOT / OUTPUT_DIR / "methodology_fix_consistency_check.json").read_text(encoding="utf-8"))


def corrected_rows() -> list[dict[str, str]]:
    with (ROOT / OUTPUT_DIR / "corrected_profit_research_variant_results.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float:
    return float(value) if value not in {"", None} else 0.0


def test_methodology_fix_packet_and_scope_flags() -> None:
    result = run(ROOT)
    output = ROOT / OUTPUT_DIR
    manifest = load_manifest()
    consistency = load_consistency()

    assert result["consistency_passed"] is True
    assert consistency["consistency_passed"] is True
    for filename in REQUIRED_OUTPUT_FILES:
        assert (output / filename).exists(), filename

    assert manifest["methodology_fix_only"] is True
    assert manifest["batch_id_fixed"] == BATCH_ID
    assert manifest["same_variant_set_rerun"] is True
    assert manifest["same_variant_set_verified"] is True
    assert manifest["new_research_batch_run"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_variants_created"] is False
    assert manifest["new_families_created"] is False
    assert manifest["provider_download"] is False
    assert manifest["uses_local_cache_only"] is True
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
    assert manifest["old_batch_v1_results_invalidated_or_superseded"] is True


def test_corrected_exposure_and_cash_bil_invariants() -> None:
    run(ROOT)
    manifest = load_manifest()
    rows = corrected_rows()

    assert manifest["weight_forward_fill_bug_fixed"] is True
    assert manifest["cash_bil_accumulation_bug_fixed"] is True
    assert manifest["average_exposure_gt_1_count_after_fix"] == 0
    assert manifest["average_exposure_gt_2_count_after_fix"] == 0
    assert manifest["max_daily_exposure_after_fix"] <= 1.0 + WEIGHT_TOLERANCE
    assert manifest["max_daily_weight_sum_after_fix"] <= 1.0 + WEIGHT_TOLERANCE
    assert manifest["impossible_cash_bil_plus_risky_row_count_after_fix"] == 0
    assert manifest["impossible_cash_and_risky_exposure_days_after_fix"] == 0

    for row in rows:
        avg_exposure = as_float(row["average_exposure"])
        cash_share = as_float(row["cash_bil_allocation_share"])
        max_exposure = as_float(row["max_daily_exposure"])
        max_weight_sum = as_float(row["max_daily_weight_sum"])
        assert avg_exposure <= 1.0 + WEIGHT_TOLERANCE
        assert max_exposure <= 1.0 + WEIGHT_TOLERANCE
        assert max_weight_sum <= 1.0 + WEIGHT_TOLERANCE
        assert not (cash_share >= 1.0 - WEIGHT_TOLERANCE and avg_exposure > WEIGHT_TOLERANCE)
        assert row["weight_sum_violation_count"] in {"", "0", "0.0"}
        assert row["negative_weight_violation_count"] in {"", "0", "0.0"}
        assert row["nan_weight_count"] in {"", "0", "0.0"}
        assert row["impossible_cash_and_risky_exposure_days"] in {"", "0", "0.0"}


def test_corrected_outputs_remain_non_promotable() -> None:
    run(ROOT)
    rows = corrected_rows()
    forbidden = {
        "promotion_review_candidate",
        "candidate_exhaustive_candidate",
        "paper_forward_candidate",
        "live_ready",
        "demo_active_new",
        "real_money_candidate",
    }

    assert rows
    for row in rows:
        assert row["research_label"] not in forbidden
        assert row["promotion_eligibility"] == "False"
        assert row["paper_forward_eligibility"] == "False"
        assert row["promotion_eligibility_score"] in {"0.0", "0"}

    assert (ROOT / OUTPUT_DIR / "do_not_promote_after_methodology_fix.md").exists()


def test_synthetic_weight_engine_cases() -> None:
    results = run_synthetic_weight_tests()
    assert results
    assert all(row["passed"] is True for row in results)

    index = pd.date_range("2021-01-01", periods=6, freq="D")
    weights = complete_rebalance_weight_frame(
        index,
        ["A", "B", "BIL"],
        {
            index[0]: {"A": 1.0},
            index[3]: {"B": 1.0},
        },
    )
    assert weights.loc[index[3], "A"] == 0.0
    assert weights.loc[index[3], "B"] == 1.0
    assert weights.sum(axis=1).max() <= 1.0 + WEIGHT_TOLERANCE

    fallback = complete_rebalance_weight_frame(
        index,
        ["A", "BIL"],
        {
            index[0]: {"BIL": 1.0},
            index[3]: {"A": 1.0},
        },
    )
    assert fallback.loc[index[2], "BIL"] == 1.0
    assert fallback.loc[index[3], "BIL"] == 0.0
    assert fallback.loc[index[3], "A"] == 1.0


def test_methodology_fix_summary_and_next_action() -> None:
    run(ROOT)
    manifest = load_manifest()
    consistency = load_consistency()
    output = ROOT / OUTPUT_DIR

    assert manifest["corrected_variant_count"] == 58
    assert manifest["corrected_family_count"] == 5
    assert manifest["synthetic_weight_tests_passed"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_AUDIT_FIXED
    assert consistency["corrected_variant_results_exist"] is True
    assert consistency["corrected_family_summary_exists"] is True
    assert consistency["exposure_invariant_report_exists"] is True
    assert consistency["synthetic_weight_tests_file_exists"] is True

    invalidated = (output / "invalidated_prior_batch_v1_results.md").read_text(encoding="utf-8")
    comparison = (output / "pre_fix_vs_post_fix_comparison.md").read_text(encoding="utf-8")
    exposure = (output / "exposure_invariant_report.md").read_text(encoding="utf-8")

    assert "superseded" in invalidated
    assert "pre-fix saved output" in comparison
    assert "Average-exposure > 1 count: `0`" in exposure
