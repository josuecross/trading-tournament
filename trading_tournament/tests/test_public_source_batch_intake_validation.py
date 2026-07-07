from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.public_source_intake_validation import (
    DECISION_DUPLICATE,
    DECISION_ELIGIBLE,
    DECISION_INCOMPLETE,
    DECISION_REVIEW,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "public_source_batch_intake_validation" / "latest"
CANDIDATE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "public_source_batch_intake_validation_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "public_source_batch_intake_validation_consistency_check.json").read_text(encoding="utf-8")
    )


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def row_by_source(filename: str, source_id: str) -> dict[str, str]:
    rows = read_rows(filename)
    matches = [row for row in rows if row["source_id"] == source_id]
    assert len(matches) == 1, source_id
    return matches[0]


def test_manifest_records_batch_intake_only_guardrails() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_batch_intake_validation_only"] is True
    assert manifest["candidate_count"] == 10
    assert manifest["expected_candidate_count"] == 10
    assert manifest["candidate_count_matches_manual_batch"] is True
    assert manifest["bounded_bt_design_created"] is False
    assert manifest["public_strategy_selected_by_codex"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["public_strategy_list_ingested"] is False
    assert manifest["public_strategy_implemented"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["broad_research_batch_run"] is False
    assert manifest["new_packages_installed"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["public_source_presence_is_profitability_proof"] is False
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["next_action"] == "direction_owner_review_required_for_public_source_batch_intake"
    assert consistency["consistency_passed"] is True


def test_candidate_files_and_required_evidence_exist() -> None:
    candidates = sorted(path.name for path in CANDIDATE_DIR.glob("*.yaml"))
    assert candidates == [
        "bollinger_band_squeeze_breakout.yaml",
        "cci_correction.yaml",
        "coppock_curve_monthly_equity_signal.yaml",
        "golden_cross_50_200.yaml",
        "larry_connors_rsi2_mean_reversion.yaml",
        "low_volatility_factor_proxy.yaml",
        "macd_stochastic_double_cross.yaml",
        "percent_b_money_flow.yaml",
        "sector_momentum_rotational_system.yaml",
        "sell_in_may_halloween_effect.yaml",
    ]

    required = [
        "public_source_batch_intake_validation_manifest.json",
        "candidate_batch_inventory.csv",
        "batch_source_summary.md",
        "required_field_validation_table.csv",
        "constraint_filter_table.csv",
        "similarity_do_not_retest_table.csv",
        "local_cache_availability_table.csv",
        "eligibility_decisions.csv",
        "ranked_batch_intake_report.md",
        "top_candidates_for_direction_owner_review.md",
        "guardrail_checklist.json",
        "public_source_batch_intake_validation_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename


def test_batch_decision_counts_and_key_decisions() -> None:
    manifest = load_manifest()

    assert manifest["eligible_candidate_count"] == 4
    assert manifest["needs_direction_review_candidate_count"] == 2
    assert manifest["duplicate_or_do_not_retest_candidate_count"] == 3
    assert manifest["blocked_candidate_count"] == 0
    assert manifest["incomplete_candidate_count"] == 1
    assert manifest["eligible_source_ids"] == [
        "cci_correction",
        "coppock_curve_monthly_equity_signal",
        "larry_connors_rsi2_mean_reversion",
        "percent_b_money_flow",
    ]
    assert set(manifest["needs_direction_review_source_ids"]) == {
        "bollinger_band_squeeze_breakout",
        "macd_stochastic_double_cross",
    }
    assert set(manifest["duplicate_source_ids"]) == {
        "golden_cross_50_200",
        "sector_momentum_rotational_system",
        "sell_in_may_halloween_effect",
    }
    assert manifest["incomplete_source_ids"] == ["low_volatility_factor_proxy"]


def test_eligibility_rows_preserve_expected_filter_reasons() -> None:
    cci = row_by_source("eligibility_decisions.csv", "cci_correction")
    assert cci["eligibility_decision"] == DECISION_ELIGIBLE
    assert cci["next_action"] == "design_public_source_cci_correction_bounded_bt_lane"
    assert "spy200d_trend_control" in cci["family_similarity_hits"]
    assert "global_multi_asset" in cci["family_similarity_hits"]
    assert "macro_gld_duration_risk_off" in cci["family_similarity_hits"]
    assert "high_return_tactical_equity" in cci["family_similarity_hits"]
    assert "volatility_throttle_volatility_managed_equity" in cci["family_similarity_hits"]
    assert "turn_of_month_calendar_effect" in cci["family_similarity_hits"]
    assert "mean_reversion_rejected_or_existing_candidate" in cci["family_similarity_hits"]
    assert "larry_connors_rsi2_mean_reversion" in cci["family_similarity_hits"]
    assert "price_band_money_flow_confirmation" in cci["family_similarity_hits"]
    assert "coppock_curve_monthly_equity_signal" in cci["family_similarity_hits"]

    coppock = row_by_source("eligibility_decisions.csv", "coppock_curve_monthly_equity_signal")
    assert coppock["eligibility_decision"] == DECISION_ELIGIBLE
    assert coppock["next_action"] == "design_public_source_coppock_curve_monthly_equity_signal_bounded_bt_lane"
    assert "spy200d_trend_control" in coppock["family_similarity_hits"]
    assert "global_multi_asset" in coppock["family_similarity_hits"]
    assert "macro_gld_duration_risk_off" in coppock["family_similarity_hits"]
    assert "high_return_tactical_equity" in coppock["family_similarity_hits"]
    assert "volatility_throttle_volatility_managed_equity" in coppock["family_similarity_hits"]
    assert "turn_of_month_calendar_effect" in coppock["family_similarity_hits"]
    assert "mean_reversion_rejected_or_existing_candidate" in coppock["family_similarity_hits"]
    assert "price_band_money_flow_confirmation" in coppock["family_similarity_hits"]

    percent_b = row_by_source("eligibility_decisions.csv", "percent_b_money_flow")
    assert percent_b["eligibility_decision"] == DECISION_ELIGIBLE
    assert percent_b["next_action"] == "design_public_source_percent_b_money_flow_bounded_bt_lane"

    rsi2 = row_by_source("eligibility_decisions.csv", "larry_connors_rsi2_mean_reversion")
    assert rsi2["eligibility_decision"] == DECISION_ELIGIBLE
    assert rsi2["next_action"] == "design_public_source_larry_connors_rsi2_mean_reversion_bounded_bt_lane"
    assert "mean_reversion_rejected_or_existing_candidate" in rsi2["family_similarity_hits"]

    golden_cross = row_by_source("eligibility_decisions.csv", "golden_cross_50_200")
    assert golden_cross["eligibility_decision"] == DECISION_DUPLICATE
    assert "spy200d_trend_control" in golden_cross["family_similarity_hits"]

    sector_momentum = row_by_source("eligibility_decisions.csv", "sector_momentum_rotational_system")
    assert sector_momentum["eligibility_decision"] == DECISION_DUPLICATE
    assert "high_return_tactical_equity" in sector_momentum["family_similarity_hits"]

    sell_in_may = row_by_source("eligibility_decisions.csv", "sell_in_may_halloween_effect")
    assert sell_in_may["eligibility_decision"] == DECISION_DUPLICATE
    assert "turn_of_month_calendar_effect" in sell_in_may["family_similarity_hits"]

    low_vol = row_by_source("eligibility_decisions.csv", "low_volatility_factor_proxy")
    assert low_vol["eligibility_decision"] == DECISION_INCOMPLETE
    assert "strategy_description.rule_clarity" in low_vol["missing_required_fields"]
    assert "rules.entry_rule" in low_vol["missing_required_fields"]


def test_local_cache_availability_checked_for_explicit_instruments() -> None:
    rows = read_rows("local_cache_availability_table.csv")
    by_source_symbol = {(row["source_id"], row["symbol"]): row for row in rows}

    for source_id in {
        "coppock_curve_monthly_equity_signal",
        "cci_correction",
        "percent_b_money_flow",
        "golden_cross_50_200",
        "larry_connors_rsi2_mean_reversion",
        "sell_in_may_halloween_effect",
    }:
        assert by_source_symbol[(source_id, "SPY")]["cache_status"] == "cache_ready"
        assert by_source_symbol[(source_id, "BIL")]["cache_status"] == "cache_ready"

    for symbol in ["SPLV", "USMV", "SPY", "BIL"]:
        assert by_source_symbol[("low_volatility_factor_proxy", symbol)]["cache_status"] == "cache_ready"

    for symbol in ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY", "BIL"]:
        assert by_source_symbol[("sector_momentum_rotational_system", symbol)]["cache_status"] == "cache_ready"
