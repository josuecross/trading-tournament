from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.coppock_curve_portability_family_followup_audit_v1 import (
    AUDIT_ID,
    CANONICAL_SYMBOL,
    NEXT_ACTION,
    OUTPUT_DIR,
    PORTABILITY_SYMBOLS,
    STRATEGY_ID,
    data_hash,
    directory_hash,
    run,
)
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import OUTPUT_DIR as PRIOR_BATCH_DIR


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR
PRIOR = ROOT / PRIOR_BATCH_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def prior_csv_rows(name: str) -> list[dict[str, str]]:
    with (PRIOR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def core_hash() -> str:
    files = [
        "prior_batch_reconciliation.json",
        "canonical_family_selection.json",
        "common_monthly_target_states.csv",
        "family_signal_overlap.csv",
        "pairwise_return_correlations.csv",
        "episode_attribution.csv",
        "episode_concentration_summary.json",
        "existing_timeframe_review.csv",
        "family_control_comparison.csv",
        "portability_status.json",
        "family_verification_outcome.json",
        "consistency_check.json",
    ]
    return data_hash({name: (EVIDENCE / name).read_text(encoding="utf-8") for name in files})


def test_required_artifacts_and_prior_batch_unchanged() -> None:
    required = [
        "prior_batch_reconciliation.json",
        "canonical_family_selection.json",
        "common_monthly_target_states.csv",
        "family_signal_overlap.csv",
        "pairwise_return_correlations.csv",
        "episode_attribution.csv",
        "episode_concentration_summary.json",
        "existing_timeframe_review.csv",
        "family_control_comparison.csv",
        "portability_status.json",
        "family_verification_outcome.json",
        "command_validation_log.csv",
        "consistency_check.json",
        "verification_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    consistency = load_json("consistency_check.json")
    assert consistency["audit_id"] == AUDIT_ID
    assert consistency["consistency_passed"] is True
    assert consistency["prior_batch_packet_unchanged"] is True
    assert consistency["prior_batch_hash_before"] == consistency["prior_batch_hash_after"]
    assert consistency["prior_batch_hash_after"] == directory_hash(PRIOR)


def test_spy_selected_by_frozen_order_not_performance() -> None:
    selection = load_json("canonical_family_selection.json")
    prior_candidates = prior_csv_rows("followup_candidate_queue.csv")

    assert selection["canonical_representative"] == CANONICAL_SYMBOL == "SPY"
    assert prior_candidates[0]["symbol"] == "SPY"
    assert selection["performance_used_for_representative_selection"] is False
    assert "frozen universe order" in selection["selection_reason"]


def test_canonical_parameters_unchanged_and_no_new_etf_tested() -> None:
    selection = load_json("canonical_family_selection.json")
    control = csv_rows("family_control_comparison.csv")
    timeframe = csv_rows("existing_timeframe_review.csv")

    assert selection["strategy_id"] == STRATEGY_ID
    assert selection["frozen_parameters"] == {
        "roc_periods": [14, 11],
        "wma_smoothing_period": 10,
        "signal_threshold": 0.0,
        "cost_bps_per_turnover": 5.0,
        "cash_proxy": "BIL",
    }
    assert {row["symbol"] for row in control} == set(PORTABILITY_SYMBOLS)
    assert {row["symbol"] for row in timeframe} == set(PORTABILITY_SYMBOLS)
    assert "QQQ" not in {row["symbol"] for row in control}
    assert "IWM" not in {row["symbol"] for row in control}
    assert "SCHG" not in {row["symbol"] for row in control}


def test_existing_first_second_half_values_are_reused() -> None:
    output_rows = {row["trial_id"]: row for row in csv_rows("existing_timeframe_review.csv")}
    prior_rows = {row["trial_id"]: row for row in prior_csv_rows("timeframe_diagnostics.csv")}

    for symbol in PORTABILITY_SYMBOLS:
        trial_id = f"{STRATEGY_ID}__{symbol}"
        assert output_rows[trial_id]["frozen_timeframe_source"].endswith("timeframe_diagnostics.csv")
        assert float(output_rows[trial_id]["first_half_excess_vs_underlying"]) == float(
            prior_rows[trial_id]["first_half_excess_vs_primary_control"]
        )
        assert float(output_rows[trial_id]["second_half_excess_vs_underlying"]) == float(
            prior_rows[trial_id]["second_half_excess_vs_primary_control"]
        )


def test_switch_episodes_count_once_and_reconcile() -> None:
    episodes = csv_rows("episode_attribution.csv")
    concentration = load_json("episode_concentration_summary.json")

    episode_numbers = [int(row["episode_number"]) for row in episodes]
    assert episode_numbers == list(range(1, len(episodes) + 1))
    assert len(episodes) == concentration["episode_count"]
    assert concentration["episode_contribution_reconciliation_error"] <= 1e-10
    assert abs(
        sum(float(row["wealth_contribution_vs_SPY"]) for row in episodes)
        - concentration["sum_episode_contributions_vs_SPY"]
    ) <= 1e-10


def test_signal_overlap_uses_common_calendar_and_translations_not_independent() -> None:
    monthly = csv_rows("common_monthly_target_states.csv")
    overlap = csv_rows("family_signal_overlap.csv")
    correlations = csv_rows("pairwise_return_correlations.csv")
    status = load_json("portability_status.json")

    assert monthly
    assert all(set(row) == {"signal_month", "SPY_target_state", "DIA_target_state", "VTV_target_state", "all_three_same_state"} for row in monthly)
    assert {int(row["common_month_count"]) for row in overlap} == {len(monthly)}
    assert {int(row["common_month_count"]) for row in correlations} == {len(monthly)}
    assert status["instrument_translations_counted_as_independent_strategies"] is False
    assert status["portability_status"] == "one_canonical_family_correlated_translations"


def test_family_outcome_and_direction_boundary() -> None:
    outcome = load_json("family_verification_outcome.json")
    concentration = load_json("episode_concentration_summary.json")
    timeframe = csv_rows("existing_timeframe_review.csv")

    assert outcome["family_outcome"] == "family_timeframe_or_episode_fragile"
    assert outcome["next_permitted_step"] == "direction_owner_close_coppock_followup_and_resume_fast_lane"
    assert outcome["exact_next_action"] == NEXT_ACTION
    assert concentration["largest_episode_fraction_of_total_excess"] > 0.70
    assert all(float(row["second_half_excess_vs_underlying"]) < 0 for row in timeframe)


def test_no_new_parameter_cost_benchmark_overlay_or_state_changes() -> None:
    consistency = load_json("consistency_check.json")
    outcome = load_json("family_verification_outcome.json")
    artifact_names = {path.name.lower() for path in EVIDENCE.iterdir()}

    assert consistency["no_new_parameter_cost_or_benchmark"] is True
    assert consistency["no_overlay_output_created"] is True
    assert all("overlay" not in name for name in artifact_names)
    assert outcome["promotion_eligibility"] is False
    assert outcome["paper_forward_eligibility"] is False
    assert outcome["candidate_exhaustive_eligibility"] is False
    assert outcome["broker_or_order_path_touched"] is False
    assert outcome["real_money_recommendation"] is False
    assert consistency["provider_download"] is False
    assert consistency["intraday_data_used"] is False


def test_generation_is_deterministic() -> None:
    before = core_hash()
    result = run(ROOT)
    after = core_hash()
    assert result["consistency_passed"] is True
    assert before == after

