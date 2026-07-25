from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as batch


EVIDENCE = batch.OUTPUT_DIR
REQUIRED_ARTIFACTS = {
    "batch_manifest.yaml",
    "preregistered_strategy_cards.csv",
    "all_trial_results.csv",
    "family_results_summary.csv",
    "exploratory_followup_candidates.csv",
    "rejection_and_data_issue_log.csv",
    "trial_lineage.csv",
    "cohort_funnel_counts.json",
    "batch_report.md",
    "consistency_check.json",
}
PROTECTED_STATE_PATHS = [
    batch.ROOT / "strategy_lab" / "strategy_registry.yaml",
    batch.ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    batch.ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    batch.ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    batch.ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
ALLOWED_CLASSIFICATIONS = {
    "exploratory_followup_candidate_standalone",
    "exploratory_followup_candidate_diversifier",
    "closed_exploration",
    "inconclusive_data_issue",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _manifest() -> dict:
    return yaml.safe_load((EVIDENCE / "batch_manifest.yaml").read_text(encoding="utf-8"))


def test_batch_writes_required_artifacts_and_expected_scope() -> None:
    result = batch.run()

    assert result["batch_id"] == batch.BATCH_ID
    assert result["task_outcome"] == "fast_price_volume_discovery_batch_v2_complete"
    assert result["evidence_path"] == "evidence/research_recovery/fast_price_volume_discovery_batch_v2/latest"
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _manifest()
    assert manifest["batch_id"] == batch.BATCH_ID
    assert manifest["mode"] == "bounded_exploratory_batch"
    assert manifest["broad_strategy_discovery"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["hidden_parameter_grid"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["live_orders"] is False
    assert manifest["paper_demo_activation"] is False
    assert manifest["promotion_review"] is False
    assert manifest["candidate_exhaustive"] is False
    assert manifest["dsr_pbo_cscv_or_reality_check_run"] is False
    assert manifest["clean_holdout_claimed"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["max_distinct_families_allowed"] == 8


def test_selected_cohort_is_from_local_queue_and_reports_shortfall() -> None:
    batch.run()

    cards = _rows("preregistered_strategy_cards.csv")
    selected_strategy_ids = {row["strategy_id"] for row in cards}
    selected_family_ids = {row["family_id"] for row in cards}
    assert selected_strategy_ids == {
        "qqq_spy_gld_ief_dual_momentum_v1",
        "treasury_duration_trend_rotation_v1",
    }
    assert selected_family_ids == {"dual_momentum", "bond_trend_rotation"}
    assert len(cards) == 2
    assert all("evidence/strategy_candidate_queue/latest/candidate_queue_matrix.csv" in row["source_or_research_lineage"] for row in cards)

    funnel = _json("cohort_funnel_counts.json")
    assert funnel["selected_family_count"] == 2
    assert funnel["implemented_configuration_count"] == 2
    assert funnel["completed_trial_count"] == 2
    assert funnel["eligible_family_cap"] == 8
    assert funnel["eligible_family_shortfall_vs_cap"] == 6


def test_strategy_cards_are_pre_registered_complete_and_not_process_records() -> None:
    batch.run()

    cards = _rows("preregistered_strategy_cards.csv")
    required_non_unknown = [
        "family_id",
        "strategy_id",
        "display_name",
        "strategy_architecture",
        "source_or_research_lineage",
        "economic_or_behavioral_rationale",
        "complete_canonical_rule",
        "parameters",
        "instrument_universe",
        "primary_benchmark_control",
        "static_control",
        "trial_id",
        "changed_fields_from_parent",
        "preregistration_timestamp",
    ]
    for row in cards:
        assert row["task_or_process_record"] == "false"
        assert row["preregistration_timestamp"] == batch.FROZEN_PREREGISTRATION_TIMESTAMP
        assert all(row[field] and row[field] != "unknown" for field in required_non_unknown)
        assert '"lookback_trading_days":126' in row["parameters"]
        assert '"absolute_trend_sma_days":200' in row["parameters"]


def test_trials_lineage_and_failed_rows_are_preserved() -> None:
    batch.run()

    cards = _rows("preregistered_strategy_cards.csv")
    results = _rows("all_trial_results.csv")
    lineage = _rows("trial_lineage.csv")
    card_trials = {row["trial_id"] for row in cards}
    result_trials = {row["trial_id"] for row in results}
    lineage_trials = {row["trial_id"] for row in lineage}

    assert card_trials == result_trials == lineage_trials
    assert len(results) == len(lineage) == len(cards) == 2
    assert all(row["classification"] in ALLOWED_CLASSIFICATIONS for row in results)
    assert all(row["task_or_process_record"] == "false" for row in lineage)
    assert all(row["predeclared_before_results"] == "true" for row in lineage)
    assert all(row["promotion_review"] == "false" for row in results)
    assert all(row["paper_demo_eligibility"] == "false" for row in results)
    assert all(row["paper_demo_activation"] == "false" for row in results)
    assert all(row["candidate_exhaustive"] == "false" for row in results)
    assert all(row["real_money_action"] == "false" for row in results)


def test_recent_active_duplicate_and_blocked_families_are_excluded() -> None:
    batch.run()

    selected = {row["strategy_id"] for row in _rows("preregistered_strategy_cards.csv")}
    rejected = _rows("rejection_and_data_issue_log.csv")
    rejected_by_strategy = {row["strategy_id"]: row["rejection_or_status"] for row in rejected if row["strategy_id"]}
    rejected_by_family = {row["family_id"]: row["rejection_or_status"] for row in rejected if row["family_id"]}

    assert not selected.intersection(batch.QUEUE_EXCLUSION_REASONS)
    for strategy_id, reason in batch.QUEUE_EXCLUSION_REASONS.items():
        assert rejected_by_strategy[strategy_id] == reason
    for family_id, reason in batch.PARALLEL_QUEUE_EXCLUSION_REASONS.items():
        assert rejected_by_family[family_id] == reason
    assert rejected_by_strategy["treasury_duration_trend_rotation_v1"] == "selected"
    assert rejected_by_strategy["qqq_spy_gld_ief_dual_momentum_v1"] == "selected"


def test_results_include_required_controls_halves_reference_and_invariants() -> None:
    batch.run()

    results = _rows("all_trial_results.csv")
    required_columns = [
        "evaluation_start",
        "evaluation_end",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "maximum_drawdown",
        "turnover",
        "trade_or_rebalance_count",
        "estimated_cost_return_drag",
        "primary_control_total_return",
        "delta_total_return_vs_primary_control",
        "static_control_total_return",
        "delta_total_return_vs_static_control",
        "first_half_total_return",
        "second_half_total_return",
        "first_half_excess_vs_primary_control",
        "second_half_excess_vs_primary_control",
        "correlation_to_frozen_current_active_vm_dsr_usci_combo",
        "fixed_20pct_sleeve_sharpe_ratio",
        "fixed_20pct_sleeve_maximum_drawdown",
        "max_daily_exposure",
        "max_daily_weight_sum",
        "exposure_invariant_pass",
    ]
    for row in results:
        for column in required_columns:
            assert row[column] != "", (row["trial_id"], column)
        assert row["evaluation_start"] < row["evaluation_end"]
        assert float(row["max_daily_exposure"]) <= 1.000001
        assert float(row["max_daily_weight_sum"]) <= 1.000001
        assert row["exposure_invariant_pass"] == "true"


def test_cohort_funnel_next_action_and_consistency_flags() -> None:
    batch.run()

    funnel = _json("cohort_funnel_counts.json")
    consistency = _json("consistency_check.json")
    assert funnel["completed_trial_count"] + funnel["data_blocked_configuration_count"] == funnel["all_trial_result_count"]
    assert (
        funnel["standalone_followup_candidate_count"]
        + funnel["diversifier_followup_candidate_count"]
        + funnel["closed_configuration_count"]
        + funnel["data_blocked_configuration_count"]
    ) == funnel["all_trial_result_count"]
    expected_next = (
        batch.NEXT_ACTION_WITH_CANDIDATES
        if funnel["total_followup_candidate_count"]
        else batch.NEXT_ACTION_ZERO_CANDIDATES
    )
    assert consistency["exact_next_action"] == expected_next
    assert consistency["all_trials_preserved"] is True
    assert consistency["cohort_funnel_arithmetically_consistent"] is True
    assert consistency["strategy_cards_have_required_non_unknown_fields"] is True
    assert consistency["task_audit_runner_report_records_kept_out_of_trial_tables"] is True
    assert consistency["protected_state_hashes_unchanged"] is True
    assert consistency["no_post_result_parameter_benchmark_timeframe_universe_changes"] is True
    assert consistency["broad_strategy_discovery"] is False
    assert consistency["strategy_discovery_run"] is False
    assert consistency["hidden_parameter_grid"] is False
    assert consistency["parameter_grid_or_optimizer_run"] is False
    assert consistency["provider_download"] is False
    assert consistency["intraday_data_used"] is False
    assert consistency["broker_api_called"] is False
    assert consistency["broker_orders_submitted"] is False
    assert consistency["live_orders"] is False


def test_protected_state_unchanged_and_generation_deterministic() -> None:
    before = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}
    first = batch.run()
    first_bytes = {name: (EVIDENCE / name).read_bytes() for name in REQUIRED_ARTIFACTS}

    second = batch.run()
    second_bytes = {name: (EVIDENCE / name).read_bytes() for name in REQUIRED_ARTIFACTS}
    after = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}

    assert first["protected_state_hashes_unchanged"] is True
    assert second["protected_state_hashes_unchanged"] is True
    assert before == after
    assert first_bytes == second_bytes
