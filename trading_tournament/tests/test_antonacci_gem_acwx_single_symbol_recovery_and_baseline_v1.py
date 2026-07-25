from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import antonacci_gem_12m_global_equities_bond_v1 as gem
from strategy_lab.research_os.research.antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1 import (
    ACWX,
    OUTPUT_DIR,
    READY_QUEUE_POSITION_3_NEXT_LANE,
    STRATEGY_ID,
    TASK_ID,
    deterministic_core_hash,
    file_hash,
    run,
)
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import FROZEN_UNIVERSE_PATH


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR
PRIOR = ROOT / "evidence" / "fast_progress" / STRATEGY_ID / "latest"


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_and_successful_recovery_contract() -> None:
    required = [
        "prior_packet_reconciliation.json",
        "acwx_frozen_universe_omission_review.json",
        "acwx_alpaca_asset_check.json",
        "acwx_alpaca_bar_coverage.csv",
        "acwx_provider_acquisition.json",
        "acwx_data_coverage.csv",
        "acwx_provider_overlap_reconciliation.csv",
        "strategy_specific_universe_addendum.json",
        "source_to_etf_mapping.csv",
        "monthly_price_matrix.csv",
        "momentum_signal_audit.csv",
        "target_weights.csv",
        "transactions.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "family_outcome.json",
        "command_validation_log.csv",
        "consistency_check.json",
        "continuation_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    check = load_json("consistency_check.json")
    assert check["task_id"] == TASK_ID
    assert check["strategy_id"] == STRATEGY_ID
    assert check["task_outcome"] == "gem_acwx_recovery_and_fast_lane_complete"
    assert check["consistency_passed"] is True
    assert check["return_calculation_run"] is True


def test_original_gem_packet_and_frozen_universe_remain_unchanged() -> None:
    prior = load_json("prior_packet_reconciliation.json")
    addendum = load_json("strategy_specific_universe_addendum.json")
    assert prior["prior_packet_unchanged"] is True
    assert prior["prior_packet_hash_before"] == prior["prior_packet_hash_after"]
    assert prior["prior_return_calculation_run"] is False
    assert addendum["broad_frozen_universe_modified"] is False
    assert addendum["original_frozen_universe_hash"] == file_hash(ROOT / FROZEN_UNIVERSE_PATH)
    assert ACWX not in (ROOT / FROZEN_UNIVERSE_PATH).read_text(encoding="utf-8")


def test_acwx_omission_is_snapshot_or_cache_gap_without_performance_input() -> None:
    omission = load_json("acwx_frozen_universe_omission_review.json")
    assert omission["omission_classification"] == "snapshot_or_cache_gap"
    assert omission["official_inventory_contains_acwx"] is True
    assert omission["proposed_primary_contains_acwx"] is False
    assert omission["proposed_reserve_contains_acwx"] is False
    assert omission["explicit_nonperformance_failure_found"] is False
    assert omission["performance_data_used_for_classification"] is False
    text = json.dumps(omission).lower()
    assert "sharpe" not in text
    assert "cagr" not in text
    assert "return performance" not in text


def test_strategy_specific_addendum_scope_and_no_substitutes() -> None:
    addendum = load_json("strategy_specific_universe_addendum.json")
    mapping = {row["expected_symbol"]: row for row in csv_rows("source_to_etf_mapping.csv")}
    assert addendum["strategy_specific_addendum"] is True
    assert addendum["symbol"] == ACWX
    assert addendum["source_role"] == "all-country ex-U.S. equity"
    assert addendum["strategies_authorized_to_use_addendum"] == [STRATEGY_ID]
    assert addendum["unrelated_strategy_authorization"] is False
    assert mapping["ACWX"]["selected_symbol"] == "ACWX"
    assert mapping["ACWX"]["mapping_status"] == "strategy_specific_addendum_available"
    assert all(row["substitution_allowed"] == "False" for row in mapping.values())
    assert all(row["selected_symbol"] != "EFA" for row in mapping.values())


def test_only_acwx_acquired_through_existing_provider_convention() -> None:
    acquisition = load_json("acwx_provider_acquisition.json")
    check = load_json("consistency_check.json")
    coverage = csv_rows("acwx_data_coverage.csv")[0]
    assert acquisition["acquisition_passed"] is True
    assert acquisition["new_provider_added"] is False
    assert acquisition["existing_provider_convention_reused"] is True
    assert acquisition["provider"] == "yfinance_compatible_adjusted_daily_etf_data"
    assert acquisition["acquired_symbols"] == ["ACWX"]
    assert acquisition["only_acwx_acquired"] is True
    assert check["provider_download_symbols"] == ["ACWX"]
    assert check["provider_download_symbol_count_lte_1"] is True
    assert coverage["symbol"] == "ACWX"
    assert coverage["cache_ready"] == "True"


def test_alpaca_check_is_read_only_and_asset_bars_are_ready() -> None:
    alpaca = load_json("acwx_alpaca_asset_check.json")
    coverage = csv_rows("acwx_alpaca_bar_coverage.csv")[0]
    assert alpaca["status"] == "ready"
    assert alpaca["read_only_endpoints_only"] is True
    assert alpaca["order_endpoint_called"] is False
    assert alpaca["api_secrets_persisted"] is False
    assert alpaca["masked_credentials_written"] is False
    assert alpaca["asset"]["symbol"] == "ACWX"
    assert alpaca["asset"]["asset_class"] == "us_equity"
    assert alpaca["asset"]["active"] is True
    assert alpaca["asset"]["tradable"] is True
    assert coverage["historical_daily_bar_access"] == "True"
    assert int(coverage["rows"]) > 0


def test_acwx_provider_overlap_reconciliation_passed() -> None:
    row = csv_rows("acwx_provider_overlap_reconciliation.csv")[0]
    assert row["decision"] == "provider_overlap_reconciliation_passed"
    assert row["reconciliation_passed"] == "True"
    assert int(row["overlap_rows"]) >= 252
    assert float(row["median_abs_daily_return_difference"]) <= float(row["median_abs_daily_return_difference_tolerance"])
    assert float(row["p99_abs_daily_return_difference"]) <= float(row["p99_abs_daily_return_difference_tolerance"])
    assert float(row["daily_return_correlation"]) >= float(row["daily_return_correlation_minimum"])


def test_gem_parameters_gate_order_and_bil_hurdle_only_remain_unchanged() -> None:
    signals = csv_rows("momentum_signal_audit.csv")
    targets = csv_rows("target_weights.csv")
    assert signals
    assert targets
    assert gem.LOOKBACK_MONTHS == 12
    assert {row["lookback_months"] for row in signals if row["valid_common_signal_month"] == "True"} == {"12"}
    assert {row["uses_most_recent_month"] for row in signals if row["valid_common_signal_month"] == "True"} == {"True"}
    assert {row["gate_order"] for row in signals if row["valid_common_signal_month"] == "True"} == {"SPY_vs_BIL_before_SPY_vs_ACWX"}
    assert {row["BIL"] for row in targets} == {"0.0"}
    assert all(abs(float(row["weight_sum"]) - 1.0) <= 1e-10 for row in targets)
    assert all(sum(1 for symbol in ["SPY", "ACWX", "AGG"] if float(row[symbol]) > 0.5) == 1 for row in targets)


def test_exactly_one_canonical_trial_and_expected_controls() -> None:
    baseline = csv_rows("baseline_metrics.csv")
    controls = {row["control_id"] for row in csv_rows("control_metrics.csv")}
    assert len(baseline) == 1
    assert baseline[0]["trial_id"] == gem.TRIAL_ID
    assert controls == {
        "global_equity_50_50_monthly_rebalanced",
        "SPY_buy_hold",
        "ACWX_buy_hold",
        "AGG_buy_hold",
        "BIL_buy_hold_hurdle_context",
        "static_average_weight_control_ex_post_diagnostic",
        "zero_cost_gem_baseline",
        "five_bps_gem_diagnostic",
    }


def test_family_outcome_is_non_promotable_and_blocker_boundary_recorded() -> None:
    family = load_json("family_outcome.json")
    assert family["family_outcome"] in {
        "family_exploratory_followup_candidate",
        "family_timeframe_fragile",
        "family_control_weak",
        "family_cost_fragile",
    }
    assert family["family_outcome"] == "family_control_weak"
    assert family["promotion_eligibility"] is False
    assert family["paper_forward_eligibility"] is False
    assert family["candidate_exhaustive_eligibility"] is False
    assert family["gem_deferred"] is False
    assert family["next_permitted_lane_if_blocked"] in {"", READY_QUEUE_POSITION_3_NEXT_LANE}


def test_no_overlay_registry_paper_broker_or_second_recovery_task() -> None:
    check = load_json("consistency_check.json")
    names = {path.name.lower() for path in EVIDENCE.iterdir()}
    assert all("overlay" not in name for name in names)
    assert check["no_overlay_output_generated"] is True
    assert check["registry_lifecycle_unchanged"] is True
    assert check["active_paper_demo_state_unchanged"] is True
    assert check["broker_or_order_path_touched"] is False
    assert check["paper_forward_activation"] is False
    assert check["promotion_candidates_created"] is False
    assert check["candidate_exhaustive_run"] is False
    assert check["real_money_recommendation"] is False
    assert check["second_recovery_task_created"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
    assert load_json("prior_packet_reconciliation.json")["prior_packet_unchanged"] is True
