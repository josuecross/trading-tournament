from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import fast_price_volume_candidate_incremental_value_followup_v1 as followup


EVIDENCE = followup.OUTPUT_DIR
REQUIRED_ARTIFACTS = {
    "followup_manifest.yaml",
    "direction_owner_classification_override.yaml",
    "frozen_candidate_definitions.csv",
    "portfolio_control_definitions.csv",
    "reproduction_check.csv",
    "all_portfolio_comparison_results.csv",
    "chronological_half_results.csv",
    "incremental_signal_value_comparison.csv",
    "candidate_followup_decisions.csv",
    "trial_lineage.csv",
    "followup_report.md",
    "consistency_check.json",
}
PROTECTED_STATE_PATHS = [
    followup.ROOT / "strategy_lab" / "strategy_registry.yaml",
    followup.ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    followup.ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    followup.ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    followup.ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
VALID_DECISIONS = {
    "advance_to_validation_candidate",
    "close_no_incremental_signal_value",
    "inconclusive_incremental_value",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _yaml(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_followup_runner_writes_required_artifacts_and_scope_flags() -> None:
    result = followup.run()

    assert result["followup_id"] == followup.FOLLOWUP_ID
    assert result["candidate_count"] == 2
    assert result["task_outcome"] == "fast_price_volume_candidate_incremental_value_followup_v1_complete"
    for artifact in REQUIRED_ARTIFACTS:
        assert (EVIDENCE / artifact).exists(), artifact

    manifest = _yaml("followup_manifest.yaml")
    assert manifest["source_batch_id"] == "fast_price_volume_discovery_batch_v2"
    assert manifest["selected_strategy_ids"] == list(followup.SELECTED_STRATEGY_IDS)
    assert manifest["cost_diagnostic_bps"] == [0.0, 5.0, 10.0]
    assert manifest["portfolio_construction"] == "80pct_frozen_reference_plus_20pct_candidate_or_control_sleeve"
    assert manifest["standalone_classification_carried_forward"] is False
    assert manifest["candidate_followup_classification"] == "diversifier_followup_only"
    assert manifest["prior_batch_evidence_modified"] is False
    for key, value in followup.FORBIDDEN_FLAGS.items():
        assert manifest[key] is value


def test_direction_owner_override_and_frozen_candidate_definitions_preserve_rules() -> None:
    followup.run()

    override = _yaml("direction_owner_classification_override.yaml")
    definitions = _rows("frozen_candidate_definitions.csv")
    assert override["prior_evidence_rewritten_or_deleted"] is False
    assert {row["strategy_id"] for row in definitions} == set(followup.SELECTED_STRATEGY_IDS)
    assert all(row["direction_owner_followup_classification"] == "diversifier_followup_only" for row in definitions)
    for row in definitions:
        assert row["rules_changed"] == "false"
        assert row["parameters_changed"] == "false"
        assert row["lookbacks_changed"] == "false"
        assert row["rebalance_schedule_changed"] == "false"
        assert row["instrument_universe_changed"] == "false"
        assert row["cash_proxy_changed"] == "false"
        assert row["evaluation_dates_changed"] == "false"
        assert row["transaction_timing_changed"] == "false"
        assert row["transaction_cost_methodology_changed"] == "false"


def test_prior_5bps_candidate_and_reference_metrics_reproduce_within_tolerance() -> None:
    followup.run()

    checks = _rows("reproduction_check.csv")
    assert len(checks) == 26
    assert {row["candidate_strategy_id"] for row in checks} == set(followup.SELECTED_STRATEGY_IDS)
    assert all(row["reproduction_pass"] == "true" for row in checks)
    for row in checks:
        assert abs(float(row["difference"])) <= float(row["tolerance"])

    consistency = _json("consistency_check.json")
    assert consistency["all_reproduction_checks_pass"] is True
    assert consistency["prior_batch_evidence_unchanged"] is True


def test_portfolio_control_set_and_cost_diagnostics_are_complete() -> None:
    followup.run()

    controls = _rows("portfolio_control_definitions.csv")
    result_rows = _rows("all_portfolio_comparison_results.csv")
    assert len(result_rows) == 27
    assert {float(row["cost_assumption_bps"]) for row in result_rows} == {0.0, 5.0, 10.0}
    assert all(row["max_daily_exposure"] == "1" for row in result_rows)
    assert all(row["max_daily_weight_sum"] == "1" for row in result_rows)
    assert all(row["numeric_integrity_pass"] == "true" for row in result_rows)

    controls_by_candidate: dict[str, set[str]] = {}
    for row in controls:
        controls_by_candidate.setdefault(row["candidate_strategy_id"], set()).add(row["sleeve_identity"])
        assert row["reference_weight"] in {"1", "0.8"}
        assert row["sleeve_weight"] in {"0", "0.2"}
        assert row["maximum_total_exposure"] == "1"
    assert controls_by_candidate["qqq_spy_gld_ief_dual_momentum_v1"] == {
        "frozen_current_active_vm_dsr_usci_combo",
        "qqq_spy_gld_ief_dual_momentum_v1",
        "static_equal_weight_QQQ_SPY_GLD_IEF",
        "BIL",
    }
    assert controls_by_candidate["treasury_duration_trend_rotation_v1"] == {
        "frozen_current_active_vm_dsr_usci_combo",
        "treasury_duration_trend_rotation_v1",
        "IEF_buy_hold",
        "static_equal_weight_SHY_IEF_TLT",
        "BIL",
    }


def test_chronological_halves_use_prior_batch_halves_and_not_holdout_language() -> None:
    followup.run()

    half_rows = _rows("chronological_half_results.csv")
    assert len(half_rows) == 54
    assert {row["half_label"] for row in half_rows} == {
        "first_chronological_half",
        "second_chronological_half",
    }
    assert all(row["half_source"] == "exact_prior_batch_chronological_half_not_holdout" for row in half_rows)
    assert all(row["evaluation_start"] < row["evaluation_end"] for row in half_rows)
    report = (EVIDENCE / "followup_report.md").read_text(encoding="utf-8").lower()
    assert "clean holdout" not in report


def test_incremental_signal_decisions_use_simple_controls_not_reference_improvement_only() -> None:
    followup.run()

    comparisons = _rows("incremental_signal_value_comparison.csv")
    decisions = _rows("candidate_followup_decisions.csv")
    assert len(decisions) == 2
    assert {row["incremental_signal_value_decision"] for row in decisions}.issubset(VALID_DECISIONS)
    assert {float(row["cost_assumption_bps"]) for row in comparisons} == {0.0, 5.0, 10.0}
    assert all(row["reproduction_pass"] == "true" for row in decisions)
    assert all(row["exposure_and_numeric_invariants_pass"] == "true" for row in decisions)
    assert all(row["incremental_signal_value_decision"] == "close_no_incremental_signal_value" for row in decisions)
    assert all(row["validation_candidate_not_due_to_reference_only_improvement"] == "false" for row in decisions)

    decision_by_id = {row["candidate_strategy_id"]: row for row in decisions}
    assert decision_by_id["qqq_spy_gld_ief_dual_momentum_v1"]["any_simple_control_dominates_candidate"] == "true"
    assert decision_by_id["treasury_duration_trend_rotation_v1"]["candidate_sharpe_beats_best_same_purpose_control"] == "false"


def test_trial_lineage_links_every_followup_row_to_parent_and_only_permitted_changes() -> None:
    followup.run()

    lineage = _rows("trial_lineage.csv")
    result_trial_ids = {row["followup_trial_id"] for row in _rows("all_portfolio_comparison_results.csv")}
    lineage_trial_ids = {row["followup_trial_id"] for row in lineage}
    assert len(lineage) == 27
    assert result_trial_ids == lineage_trial_ids
    for row in lineage:
        assert row["parent_trial_id"] == row["original_trial_id"]
        assert row["predeclared_before_results"] == "true"
        assert row["task_or_process_record"] == "false"
        assert row["changed_fields_from_parent"] == (
            "portfolio_sleeve_comparison|predeclared_cost_diagnostic|chronological_half_reporting"
        )
        assert row["candidate_rule_changes"] == "false"
        assert row["parameter_changes"] == "false"
        assert row["benchmark_changes"] == "false"
        assert row["instrument_universe_changes"] == "false"
        assert row["timeframe_changes"] == "false"


def test_consistency_next_action_protected_state_and_deterministic_output() -> None:
    before = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}
    first = followup.run()
    first_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}

    second = followup.run()
    second_bytes = {artifact: (EVIDENCE / artifact).read_bytes() for artifact in REQUIRED_ARTIFACTS}
    after = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}

    assert first["exact_next_action"] == "refresh_strategy_source_library_v1"
    assert second["exact_next_action"] == "refresh_strategy_source_library_v1"
    assert first["protected_state_hashes_unchanged"] is True
    assert second["protected_state_hashes_unchanged"] is True
    assert first["prior_batch_evidence_unchanged"] is True
    assert second["prior_batch_evidence_unchanged"] is True
    assert before == after
    assert first_bytes == second_bytes

    consistency = _json("consistency_check.json")
    assert consistency["protected_state_hashes_unchanged"] is True
    assert consistency["prior_batch_evidence_unchanged"] is True
    assert consistency["only_permitted_followup_changes_used"] is True
    assert consistency["all_portfolios_exposure_invariant_pass"] is True
    assert consistency["portfolio_rows_have_identical_dates_by_candidate_and_cost"] is True
    assert consistency["half_rows_have_identical_dates_by_candidate_cost_and_half"] is True
    assert consistency["exact_next_action"] == "refresh_strategy_source_library_v1"
    for key, value in followup.FORBIDDEN_FLAGS.items():
        assert consistency[key] is value
