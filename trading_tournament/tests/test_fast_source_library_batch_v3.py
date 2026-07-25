from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import fast_source_library_batch_v3 as batch


EVIDENCE = batch.OUTPUT_DIR
REQUIRED_ARTIFACTS = {
    "batch_manifest.yaml",
    "frozen_source_cards.csv",
    "preregistered_strategy_cards.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "exploratory_followup_candidates.csv",
    "rejection_and_data_issue_log.csv",
    "trial_lineage.csv",
    "cohort_funnel_counts.json",
    "batch_report.md",
    "consistency_check.json",
}
EXPECTED_CANDIDATES = {
    "daryanani_opportunistic_rebalance_20band_10day_v1",
    "fosback_nvi_255ema_spy_bil_v1",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "ice_vaneck_us_fallen_angel_angl_v1",
}
PROTECTED_STATE_PATHS = [
    batch.ROOT / "strategy_lab" / "strategy_registry.yaml",
    batch.ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    batch.ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    batch.ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    batch.ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_runner_writes_required_artifacts_and_preserves_scope() -> None:
    result = batch.run()

    assert result["batch_id"] == batch.BATCH_ID
    assert result["candidate_count"] == 4
    assert result["task_outcome"] == "fast_source_library_batch_v3_complete"
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _yaml("batch_manifest.yaml")
    assert manifest["batch_id"] == batch.BATCH_ID
    assert manifest["source_library_id"] == batch.SOURCE_LIBRARY_ID
    assert set(manifest["exact_candidate_ids"]) == EXPECTED_CANDIDATES
    assert manifest["exact_candidate_count"] == 4
    assert manifest["closed_prior_candidates_reopened"] is False
    assert manifest["cost_diagnostics_bps"] == [0.0, 5.0, 10.0]
    for key, value in batch.FORBIDDEN_FLAGS.items():
        assert manifest[key] is value


def test_frozen_source_cards_and_preregistration_are_complete_not_process_records() -> None:
    batch.run()

    source_cards = _rows("frozen_source_cards.csv")
    prereg = _rows("preregistered_strategy_cards.csv")
    lineage = _rows("trial_lineage.csv")
    assert {row["strategy_id"] for row in source_cards} == EXPECTED_CANDIDATES
    assert {row["strategy_id"] for row in prereg} == EXPECTED_CANDIDATES
    assert {row["strategy_id"] for row in lineage} == EXPECTED_CANDIDATES
    for row in source_cards:
        assert row["source_library_id"] == batch.SOURCE_LIBRARY_ID
        assert row["complete_frozen_rule"]
        assert row["instruments"]
        assert row["principal_controls"]
        assert row["source_research_performed"] == "false"
        assert row["source_rule_completion_performed"] == "false"
    for row in prereg:
        assert row["task_or_process_record"] == "false"
        assert row["preregistration_timestamp"] == batch.FROZEN_TIMESTAMP
        assert row["transaction_cost_assumptions"] == "0|5|10 bps per one-way turnover proxy"
    for row in lineage:
        assert row["task_or_process_record"] == "false"
        assert row["predeclared_before_results"] == "true"


def test_missing_cache_blocks_without_substitution_and_sets_data_block_next_action() -> None:
    batch.run()

    issues = _rows("rejection_and_data_issue_log.csv")
    issue_by_id = {row["strategy_id"]: row for row in issues}
    assert set(issue_by_id) == {
        "daryanani_opportunistic_rebalance_20band_10day_v1",
        "clare_inverse_volatility_five_asset_risk_parity_v1",
        "ice_vaneck_us_fallen_angel_angl_v1",
    }
    assert issue_by_id["daryanani_opportunistic_rebalance_20band_10day_v1"]["missing_symbols"] == "VNQ"
    assert issue_by_id["clare_inverse_volatility_five_asset_risk_parity_v1"]["missing_symbols"] == "VNQ"
    assert issue_by_id["ice_vaneck_us_fallen_angel_angl_v1"]["missing_symbols"] == "JNK"
    assert all(row["no_substitution_made"] == "true" for row in issues)

    funnel = _json("cohort_funnel_counts.json")
    assert funnel["completed_candidate_count"] == 1
    assert funnel["data_blocked_candidate_count"] == 3
    assert funnel["exact_next_action"] == "direction_owner_review_data_feasibility_block_v1"


def test_all_trials_controls_and_cost_diagnostics_are_preserved() -> None:
    batch.run()

    trials = _rows("all_trial_results.csv")
    controls = _rows("control_results.csv")
    assert len(trials) == 12
    assert len(controls) == 24
    assert {float(row["cost_assumption_bps"]) for row in trials} == {0.0, 5.0, 10.0}
    assert {float(row["cost_assumption_bps"]) for row in controls} == {0.0, 5.0, 10.0}
    assert {row["strategy_id"] for row in trials} == EXPECTED_CANDIDATES
    assert all(row["strategy_id"] != "qqq_spy_gld_ief_dual_momentum_v1" for row in trials)
    assert all(row["strategy_id"] != "treasury_duration_trend_rotation_v1" for row in trials)

    nvi_rows = [row for row in trials if row["strategy_id"] == "fosback_nvi_255ema_spy_bil_v1"]
    assert len(nvi_rows) == 3
    assert all(row["classification"] == "exploratory_followup_candidate_standalone" for row in nvi_rows)
    assert all(row["invariant_pass"] == "true" for row in nvi_rows)
    blocked = [row for row in trials if row["strategy_id"] != "fosback_nvi_255ema_spy_bil_v1"]
    assert all(row["classification"] == "inconclusive_data_issue" for row in blocked)


def test_executable_candidate_controls_halves_and_portfolio_diagnostic_are_complete() -> None:
    batch.run()

    controls = [
        row
        for row in _rows("control_results.csv")
        if row["strategy_id"] == "fosback_nvi_255ema_spy_bil_v1" and row["cost_assumption_bps"] == "5"
    ]
    assert {row["control_id"] for row in controls} == {"SPY_buy_hold", "SPY_255_session_price_EMA_SPY_BIL"}
    assert all(row["evaluation_start"] == "2010-08-10" for row in controls)
    assert all(row["evaluation_end"] == "2026-06-18" for row in controls)

    halves = [row for row in _rows("chronological_half_results.csv") if row["strategy_id"] == "fosback_nvi_255ema_spy_bil_v1"]
    assert len(halves) == 18
    assert {row["half_label"] for row in halves} == {"first_chronological_half", "second_chronological_half"}
    assert all(row["half_source"] == "chronological_half_not_clean_holdout" for row in halves)

    contribution = [
        row
        for row in _rows("portfolio_contribution_results.csv")
        if row["strategy_id"] == "fosback_nvi_255ema_spy_bil_v1"
    ]
    assert len(contribution) == 12
    assert {row["portfolio_id"] for row in contribution if row["cost_assumption_bps"] == "5"} == {
        "frozen_reference_100pct",
        "fosback_nvi_255ema_spy_bil_v1_candidate_20pct",
        "SPY_buy_hold_20pct_control",
        "SPY_255_session_price_EMA_SPY_BIL_20pct_control",
    }
    assert all(float(row["max_daily_exposure"]) <= 1.000001 for row in contribution)
    assert all(float(row["max_daily_weight_sum"]) <= 1.000001 for row in contribution)


def test_funnel_and_consistency_are_arithmetic_and_date_aligned() -> None:
    batch.run()

    funnel = _json("cohort_funnel_counts.json")
    consistency = _json("consistency_check.json")
    assert funnel["completed_candidate_count"] + funnel["data_blocked_candidate_count"] == funnel["candidate_count"]
    assert (
        funnel["followup_candidate_count"]
        + funnel["closed_candidate_count"]
        + funnel["inconclusive_data_issue_count"]
    ) == funnel["candidate_count"]
    assert consistency["exactly_four_frozen_candidates_considered"] is True
    assert consistency["all_trials_preserved"] is True
    assert consistency["cost_diagnostics_preserved"] is True
    assert consistency["cohort_funnel_arithmetically_consistent"] is True
    assert consistency["candidate_control_dates_identical_by_strategy_and_cost"] is True
    assert consistency["chronological_half_dates_identical_by_strategy_cost_and_half"] is True
    assert consistency["portfolio_contribution_dates_identical_by_strategy_and_cost"] is True
    assert consistency["no_missing_instrument_substituted"] is True
    assert consistency["closed_prior_candidates_reopened"] is False


def test_no_validation_promotion_paper_broker_provider_or_holdout_claims() -> None:
    batch.run()

    consistency = _json("consistency_check.json")
    for key, value in batch.FORBIDDEN_FLAGS.items():
        assert consistency[key] is value
    assert consistency["promotion_review"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["provider_download"] is False
    assert consistency["clean_holdout_claimed"] is False
    report = (EVIDENCE / "batch_report.md").read_text(encoding="utf-8").lower()
    assert "clean holdout" not in report
    assert "paper/demo activation" in report


def test_protected_and_prior_evidence_hashes_unchanged_and_output_deterministic() -> None:
    before = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}
    first = batch.run()
    first_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}

    second = batch.run()
    second_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    after = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}

    assert first["protected_state_hashes_unchanged"] is True
    assert first["prior_evidence_hashes_unchanged"] is True
    assert second["protected_state_hashes_unchanged"] is True
    assert second["prior_evidence_hashes_unchanged"] is True
    assert before == after
    assert first_bytes == second_bytes
