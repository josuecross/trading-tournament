from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import fast_source_library_remaining_candidates_batch_v4 as batch


EVIDENCE = batch.OUTPUT_DIR
EXPECTED_CANDIDATES = {
    "lopez_de_prado_hrp_five_asset_v1",
    "ishares_msci_usa_min_vol_usmv_v1",
    "sp100_option_expiration_week_oef_bil_v1",
    "spy_close_to_open_overnight_cash_bounded_screen_v1",
}
EXCLUDED_AS_CANDIDATES = {
    "ice_vaneck_us_fallen_angel_angl_v1",
    "fosback_nvi_255ema_spy_bil_v1",
    "clare_inverse_volatility_five_asset_risk_parity_v1",
    "daryanani_opportunistic_rebalance_20band_10day_v1",
}
REQUIRED_ARTIFACTS = {
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "process_task_log.csv",
    "data_capability_task_log.csv",
    "benchmark_reference_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "portfolio_rebalance_events.csv",
    "turnover_cost_reconciliation.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
}
_RAN_ONCE = False


def _ensure_run() -> None:
    global _RAN_ONCE
    if not _RAN_ONCE:
        batch.run()
        _RAN_ONCE = True


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runner_writes_required_artifacts_and_exact_scope() -> None:
    result = batch.run()
    global _RAN_ONCE
    _RAN_ONCE = True

    assert result["batch_id"] == batch.BATCH_ID
    assert result["strategy_configurations_considered"] == 4
    assert set(result["outcomes"]) == EXPECTED_CANDIDATES
    assert result["consistency_passed"] is True
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _yaml("batch_manifest.yaml")
    assert set(manifest["exact_candidate_ids"]) == EXPECTED_CANDIDATES
    assert manifest["exact_candidate_count"] == 4
    assert set(manifest["required_symbols"]) == set(batch.REQUIRED_SYMBOLS)
    assert manifest["primary_cost_bps"] == batch.PRIMARY_COST_BPS
    assert set(manifest["excluded_ids"]) == {
        "ice_vaneck_us_fallen_angel_angl_v1",
        "fosback_nvi_255ema_spy_bil_v1",
        "clare_inverse_volatility_five_asset_risk_parity_v1_as_candidate",
        "daryanani_opportunistic_rebalance_20band_10day_v1",
    }


def test_data_preflight_and_bounded_oef_data_task_are_recorded() -> None:
    _ensure_run()

    preflight = _rows("data_preflight_reconciliation.csv")
    assert {row["symbol"] for row in preflight} == set(batch.REQUIRED_SYMBOLS)
    assert all(row["preflight_status"] == "pass" for row in preflight)
    assert all(row["ordered_unique_dates"] == "true" for row in preflight)
    assert all(row["positive_finite_prices"] == "true" for row in preflight)
    assert all(row["valid_ohlc_relationships"] == "true" for row in preflight)
    assert all(row["adjustment_compatibility"] == "true" for row in preflight)

    data_tasks = _rows("data_capability_task_log.csv")
    assert len(data_tasks) <= 1
    if data_tasks:
        row = data_tasks[0]
        assert row["entity_type"] == "data_capability_task"
        assert row["stage"] in {"feasible", "blocked"}
        assert row["adaptation_label"] == "data_feasibility_adjustment"
        assert row["symbol"] == "OEF"
        assert row["counted_as_strategy"] == "false"
        assert row["counted_as_trial"] == "false"


def test_strategy_cards_trials_and_benchmarks_are_separate() -> None:
    _ensure_run()

    cards = _rows("strategy_cards.csv")
    trials = _rows("trial_ledger.csv")
    benchmarks = _rows("benchmark_reference_log.csv")
    process = _rows("process_task_log.csv")

    assert {row["strategy_id"] for row in cards} == EXPECTED_CANDIDATES
    assert not ({row["strategy_id"] for row in cards} & EXCLUDED_AS_CANDIDATES)
    assert all(row["entity_type"] == "strategy_configuration" for row in cards)
    assert all(row["stage"] == "exploration" for row in cards)
    assert all("unknown" not in "|".join(row.values()).lower() for row in cards)

    assert {row["strategy_id"] for row in trials} == EXPECTED_CANDIDATES
    assert all(row["entity_type"] == "experiment_trial" for row in trials)
    assert len({row["trial_id"] for row in trials}) == 4
    assert all(row["parent_trial_id"] == "" for row in trials)
    assert all(row["adaptation_label"] == "" for row in trials)

    assert all(row["entity_type"] == "benchmark_reference" for row in benchmarks)
    assert all(row["stage"] == "benchmark_reference_only" for row in benchmarks)
    assert all(row["counted_as_strategy"] == "false" for row in benchmarks)
    assert all(row["counted_as_trial"] == "false" for row in benchmarks)
    inverse_vol_refs = [row for row in benchmarks if row["benchmark_or_control_id"] == "clare_inverse_volatility_five_asset_risk_parity_v1"]
    assert len(inverse_vol_refs) == 1
    assert inverse_vol_refs[0]["strategy_id"] == "lopez_de_prado_hrp_five_asset_v1"

    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["strategy_counted"] == "false"
    assert process[0]["experiment_trial_counted"] == "false"


def test_results_controls_halves_and_outcomes_are_complete() -> None:
    _ensure_run()

    trial_rows = _rows("all_trial_results.csv")
    control_rows = _rows("control_results.csv")
    half_rows = _rows("chronological_half_results.csv")
    outcomes = {row["strategy_id"]: row for row in _rows("outcome_summary.csv")}

    assert len(trial_rows) == 12
    assert {row["strategy_id"] for row in trial_rows} == EXPECTED_CANDIDATES
    assert {row["cost_assumption_bps"] for row in trial_rows} == {"0", "5", "10"}
    assert all(row["invariant_pass"] == "true" for row in trial_rows)

    assert len(control_rows) == 30
    assert all(row["entity_type"] == "benchmark_reference" for row in control_rows)
    assert {row["cost_assumption_bps"] for row in control_rows} == {"0", "5", "10"}

    assert len(half_rows) == 84
    assert {row["half_label"] for row in half_rows} == {"first_chronological_half", "second_chronological_half"}
    assert {row["half_source"] for row in half_rows} == {"chronological_half_not_clean_holdout"}
    assert "clean_holdout" not in (EVIDENCE / "batch_report.md").read_text(encoding="utf-8")

    assert outcomes["lopez_de_prado_hrp_five_asset_v1"]["outcome"] == "exploratory_followup_candidate_diversifier"
    assert outcomes["ishares_msci_usa_min_vol_usmv_v1"]["outcome"] == "closed_exploration"
    assert outcomes["sp100_option_expiration_week_oef_bil_v1"]["outcome"] == "closed_exploration"
    assert outcomes["spy_close_to_open_overnight_cash_bounded_screen_v1"]["outcome"] == "closed_exploration"


def test_corrected_monthly_80_20_portfolio_accounting_is_used() -> None:
    _ensure_run()

    rows = _rows("portfolio_contribution_results.csv")
    events = _rows("portfolio_rebalance_events.csv")
    turnover = _rows("turnover_cost_reconciliation.csv")

    assert {row["period_label"] for row in rows} == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all(
        row["portfolio_construction"] in {"100pct_frozen_reference", "monthly_rebalanced_80pct_reference_plus_20pct_candidate_or_control"}
        for row in rows
    )
    assert all(float(row["max_daily_exposure"]) <= 1.000001 for row in rows)
    assert all(float(row["max_daily_weight_sum"]) <= 1.000001 for row in rows)

    candidate_events = [
        row
        for row in events
        if row["portfolio_id"] == "lopez_de_prado_hrp_five_asset_v1_candidate_20pct" and row["cost_assumption_bps"] == "5"
    ]
    assert candidate_events
    assert candidate_events[0]["event_type"] == "initial_establishment"
    assert any(row["event_type"] == "monthly_rebalance_next_session_close" for row in candidate_events)
    assert any(abs(float(row["pretrade_sleeve_weight"]) - 0.2) > 1e-4 for row in candidate_events[1:])
    assert {row["post_trade_reference_weight"] for row in candidate_events} == {"0.8"}
    assert {row["post_trade_sleeve_weight"] for row in candidate_events} == {"0.2"}

    turnover_by_portfolio = {row["portfolio_id"]: row for row in turnover if row["cost_assumption_bps"] == "5"}
    assert float(turnover_by_portfolio["lopez_de_prado_hrp_five_asset_v1_candidate_20pct"]["total_one_way_turnover"]) > 0.0
    assert turnover_by_portfolio["lopez_de_prado_hrp_five_asset_v1_candidate_20pct"]["rebalance_policy"] == "monthly_rebalanced_80_20_with_natural_drift"


def test_materiality_gate_and_funnel_counts_reconcile() -> None:
    _ensure_run()

    funnel = _json("cohort_funnel_counts.json")
    consistency = _json("consistency_check.json")
    failures = _rows("failure_reasons.csv")

    assert funnel["source_library_record_count"] == 4
    assert funnel["strategy_configuration_count"] == 4
    assert funnel["executable_experiment_trial_count"] == 4
    assert funnel["standalone_followup_candidate_count"] == 0
    assert funnel["diversifier_followup_candidate_count"] == 1
    assert funnel["closed_strategy_count"] == 3
    assert funnel["benchmark_reference_count"] == 14
    assert funnel["process_task_count"] == 1
    assert consistency["cohort_counts_reconcile"] is True
    assert consistency["portfolio_contribution_uses_monthly_rebalanced_80_20_not_fixed_return_blend"] is True
    assert {row["primary_failure_reason"] for row in failures} <= batch.ALLOWED_FAILURE_REASONS
    assert len(failures) == funnel["closed_strategy_count"]
    assert all(row["primary_failure_reason"] for row in failures)
    assert _json("cohort_funnel_counts.json")["exact_next_action"] == batch.NEXT_ACTION_REVIEW


def test_guardrails_and_protected_state_hold() -> None:
    _ensure_run()
    protected_before = {path: _sha(path) for path in batch.PROTECTED_STATE_PATHS if path.exists()}
    protected_after = {path: _sha(path) for path in batch.PROTECTED_STATE_PATHS if path.exists()}
    consistency = _json("consistency_check.json")

    assert protected_before == protected_after
    assert consistency["protected_state_hashes_unchanged"] is True
    assert consistency["input_evidence_hashes_unchanged"] is True
    for key, expected in batch.FORBIDDEN_FLAGS.items():
        assert consistency[key] is expected
    assert consistency["angl_observation_modified"] is False
    assert consistency["candidate_exhaustive"] is False
    assert consistency["paper_demo_eligibility_or_activation"] is False
    assert consistency["broker_account_order_or_real_money_action"] is False


def test_output_generation_is_deterministic_after_cache_preflight() -> None:
    batch.run()
    first = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    batch.run()
    second = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    assert first == second
