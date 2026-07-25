from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import rerun_fast_source_library_blocked_candidates_v3 as task


EVIDENCE = task.OUTPUT_DIR
REQUIRED_ARTIFACTS = {
    "batch_manifest.yaml",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "process_task_log.csv",
    "benchmark_reference_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
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
        task.run()
        _RAN_ONCE = True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_runner_writes_required_artifacts_and_exact_scope() -> None:
    result = task.run()
    global _RAN_ONCE
    _RAN_ONCE = True

    assert result["batch_id"] == task.BATCH_ID
    assert result["strategies_considered"] == 3
    assert result["trials_executed"] == 3
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _yaml("batch_manifest.yaml")
    assert manifest["target_strategy_ids"] == list(task.TARGET_STRATEGY_IDS)
    assert manifest["excluded_strategy_ids"] == [task.NVI_STRATEGY_ID]
    assert manifest["adaptation_label"] == task.ADAPTATION_LABEL
    assert manifest["provider_download"] is False


def test_preflight_reconciles_vnq_jnk_and_all_strategy_inputs() -> None:
    _ensure_run()

    rows = _rows("data_preflight_reconciliation.csv")
    symbol_rows = {row["symbol"]: row for row in rows if row["record_type"] == "symbol_preflight"}
    assert set(symbol_rows) == {"VNQ", "JNK"}
    for row in symbol_rows.values():
        assert row["preflight_status"] == "pass"
        assert row["row_count_matches_evidence"] == "true"
        assert row["first_date_matches_evidence"] == "true"
        assert row["last_date_matches_evidence"] == "true"
        assert row["cache_hash_matches_evidence"] == "true"
        assert row["canonical_frame_hash_matches_evidence"] == "true"

    strategy_rows = [row for row in rows if row["record_type"] == "strategy_preflight"]
    assert {row["strategy_id"] for row in strategy_rows} == set(task.TARGET_STRATEGY_IDS)
    assert all(row["preflight_status"] == "pass" for row in strategy_rows)
    assert all(row["all_candidate_and_control_instruments_available"] == "true" for row in strategy_rows)


def test_strategy_cards_trial_ledger_and_entities_are_separate() -> None:
    _ensure_run()

    cards = _rows("strategy_cards.csv")
    assert {row["strategy_id"] for row in cards} == set(task.TARGET_STRATEGY_IDS)
    assert all(row["entity_type"] == "strategy_configuration" for row in cards)
    assert all(row["stage"] == "exploration" for row in cards)
    assert all(row["nvi_record"] == "false" for row in cards)

    ledger = _rows("trial_ledger.csv")
    assert {row["strategy_id"] for row in ledger} == set(task.TARGET_STRATEGY_IDS)
    assert all(row["entity_type"] == "experiment_trial" for row in ledger)
    assert all(row["adaptation_label"] == task.ADAPTATION_LABEL for row in ledger)
    assert all(row["changed_fields_from_parent"] == "data_availability_and_common_eligible_period_only" for row in ledger)
    assert all(row["trial_id"].startswith("rerun_fast_source_v3__") for row in ledger)
    assert all(row["trial_id"] != row["parent_trial_id"] for row in ledger)

    process = _rows("process_task_log.csv")
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"
    assert process[0]["stage"] == "exploration"
    assert process[0]["strategy_counted"] == "false"
    assert process[0]["experiment_trial_counted"] == "false"


def test_results_controls_halves_and_portfolio_contribution_are_complete_and_separate() -> None:
    _ensure_run()

    trial_rows = _rows("all_trial_results.csv")
    assert len(trial_rows) == 9
    assert {row["strategy_id"] for row in trial_rows} == set(task.TARGET_STRATEGY_IDS)
    assert {row["cost_assumption_bps"] for row in trial_rows} == {"0", "5", "10"}
    assert all(row["strategy_id"] != task.NVI_STRATEGY_ID for row in trial_rows)

    control_rows = _rows("control_results.csv")
    assert len(control_rows) == 18
    assert all(row["entity_type"] == "benchmark_reference" for row in control_rows)
    assert all(row["stage"] == "benchmark_reference_only" for row in control_rows)

    half_rows = _rows("chronological_half_results.csv")
    assert len(half_rows) == 54
    assert {row["half_label"] for row in half_rows} == {"first_chronological_half", "second_chronological_half"}
    assert all(row["half_source"] == "chronological_half_not_clean_holdout" for row in half_rows)

    portfolio_rows = _rows("portfolio_contribution_results.csv")
    assert len(portfolio_rows) == 108
    assert {row["period_label"] for row in portfolio_rows} == {
        "full_period",
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all(float(row["max_daily_exposure"]) <= 1.000001 for row in portfolio_rows)
    assert all(float(row["max_daily_weight_sum"]) <= 1.000001 for row in portfolio_rows)


def test_outcomes_failure_reasons_and_next_actions_are_standardized() -> None:
    _ensure_run()

    ledger = _rows("trial_ledger.csv")
    allowed_outcomes = {
        "exploratory_followup_candidate_diversifier",
        "closed_exploration",
        "inconclusive_data_issue",
        "blocked_feasibility",
    }
    allowed_stages = {"exploration", "exploratory_followup_diversifier", "closed", "blocked", "benchmark_reference_only"}
    allowed_failure_reasons = {
        "",
        "weak_vs_primary_control",
        "weak_return",
        "excess_drawdown",
        "cost_drag",
        "turnover_drag",
        "signal_scarcity",
        "period_instability",
        "benchmark_like_behavior",
        "data_or_comparability_failure",
        "methodology_failure",
        "data_unavailable",
        "capability_missing",
        "duplicate_or_redundant",
        "too_risky",
        "overfit_or_unstable",
    }
    assert all(row["outcome"] in allowed_outcomes for row in ledger)
    assert all(row["stage"] in allowed_stages for row in ledger)
    assert all(row["primary_failure_reason"] in allowed_failure_reasons for row in ledger)
    assert all(row["primary_failure_reason"] for row in ledger if row["outcome"] != "exploratory_followup_candidate_diversifier")

    next_actions = _rows("next_actions.csv")
    global_rows = [row for row in next_actions if row["scope"] == "global"]
    assert len(global_rows) == 1
    assert global_rows[0]["execute_now"] == "false"
    assert global_rows[0]["exact_next_action"] == _json("consistency_check.json")["exact_next_action"]


def test_funnel_counts_reconcile_and_guardrails_hold() -> None:
    _ensure_run()

    funnel = _json("cohort_funnel_counts.json")
    consistency = _json("consistency_check.json")
    assert funnel["strategy_configuration_count"] == 3
    assert funnel["new_experiment_trial_count"] == 3
    assert funnel["process_task_count"] == 1
    assert funnel["completed_executable_strategies"] + funnel["blocked_or_inconclusive_strategy_count"] == 3
    assert consistency["cohort_counts_reconcile"] is True
    assert consistency["symbol_preflight_passed"] is True
    assert consistency["benchmark_references_separate"] is True
    assert consistency["process_task_separate"] is True
    assert consistency["nvi_excluded_and_unchanged"] is True
    for key, value in task.FORBIDDEN_FLAGS.items():
        assert consistency[key] is value


def test_protected_state_prior_evidence_and_vnq_jnk_cache_unchanged() -> None:
    protected_before = {path: _sha256(path) for path in task.PROTECTED_STATE_PATHS if path.exists()}
    cache_before = {path: _sha256(path) for path in task.PROTECTED_CACHE_PATHS if path.exists()}
    result = task.run()
    global _RAN_ONCE
    _RAN_ONCE = True
    protected_after = {path: _sha256(path) for path in task.PROTECTED_STATE_PATHS if path.exists()}
    cache_after = {path: _sha256(path) for path in task.PROTECTED_CACHE_PATHS if path.exists()}

    assert protected_before == protected_after
    assert cache_before == cache_after
    assert result["protected_state_hashes_unchanged"] is True
    assert result["input_evidence_hashes_unchanged"] is True
    assert result["vnq_jnk_cache_hashes_unchanged"] is True


def test_output_generation_is_deterministic() -> None:
    task.run()
    first_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    task.run()
    second_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    assert first_bytes == second_bytes
