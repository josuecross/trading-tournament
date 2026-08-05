from __future__ import annotations

import csv
import json

import numpy as np

from strategy_lab.research_os.research import (
    correct_technical_factory_v1_route_classification_v1 as correction,
)


def original_rows(name: str) -> list[dict[str, str]]:
    with (correction.ORIGINAL_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def output_rows(name: str) -> list[dict[str, str]]:
    with (correction.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def portfolio_row(construction: str, cost: int) -> dict[str, str]:
    rows = original_rows("portfolio_contribution_results.csv")
    return correction.one(
        rows,
        strategy_id=correction.STRATEGY_ID,
        construction_id=construction,
        cost_bps_one_way=str(float(cost)),
    )


def test_archived_d1_identity_and_lineage_are_exact() -> None:
    strategy = correction.one(original_rows("strategy_cards.csv"), strategy_id=correction.STRATEGY_ID)
    trial = correction.one(original_rows("trial_ledger.csv"), trial_id=correction.TRIAL_ID)
    assert strategy["architecture_id"] == correction.ARCHITECTURE_ID
    assert strategy["family_id"] == correction.FAMILY_ID
    assert strategy["parameters"] == '{"lookback_sessions":60,"r2_threshold":0.25}'
    assert strategy["universe"] == '["SPY","BIL"]'
    assert strategy["route"] == "standalone_with_diversifier_diagnostic"
    assert trial["strategy_id"] == correction.STRATEGY_ID


def test_archived_standalone_closure_and_diversifier_flag_coexist() -> None:
    outcome = correction.one(original_rows("outcome_summary.csv"), architecture_id=correction.ARCHITECTURE_ID)
    assert outcome["selected_configuration_outcome"] == "closed_exploration"
    assert outcome["failure_reason"] == "weak_vs_primary_control"
    assert outcome["diversifier_diagnostic_pass"] == "true"


def test_frozen_diversifier_gate_reproduces_true() -> None:
    candidate = portfolio_row(correction.CANDIDATE_PORTFOLIO, 5)
    reference = portfolio_row(correction.REFERENCE, 5)
    named = portfolio_row(correction.NAMED_PORTFOLIO, 5)
    static = portfolio_row(correction.STATIC_PORTFOLIO, 5)
    passed, checks = correction.diversifier_gate(candidate, reference, named, static)
    assert passed is True
    assert all(checks.values())


def test_regression_branch_preserves_diversifier_when_standalone_fails() -> None:
    classification = correction.corrected_classification(False, True)
    assert classification == {
        "architecture_outcome": "factory_exploratory_followup_candidate",
        "selected_configuration_outcome": "exploratory_followup_candidate_diversifier",
        "route_classification": "diversifier",
    }


def test_five_bps_portfolio_arithmetic_matches_frozen_values() -> None:
    candidate = portfolio_row(correction.CANDIDATE_PORTFOLIO, 5)
    comparisons = {
        "reference": (portfolio_row(correction.REFERENCE, 5), 0.0812522965586044, 0.02367830883866895),
        "named": (portfolio_row(correction.NAMED_PORTFOLIO, 5), -0.0123254579121133, 0.01160911558093547),
        "static": (portfolio_row(correction.STATIC_PORTFOLIO, 5), -0.0119760437582348, 0.020912548993965),
    }
    for control, expected_sharpe, expected_drawdown in comparisons.values():
        sharpe = float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
        drawdown = float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"])
        assert np.isclose(sharpe, expected_sharpe, atol=1e-9)
        assert np.isclose(drawdown, expected_drawdown, atol=1e-9)


def test_ten_bps_portfolio_gate_also_reconciles() -> None:
    passed, checks = correction.diversifier_gate(
        portfolio_row(correction.CANDIDATE_PORTFOLIO, 10),
        portfolio_row(correction.REFERENCE, 10),
        portfolio_row(correction.NAMED_PORTFOLIO, 10),
        portfolio_row(correction.STATIC_PORTFOLIO, 10),
    )
    assert passed is True
    assert all(checks.values())


def test_correction_creates_no_strategy_or_trial() -> None:
    rows = output_rows("strategy_and_trial_lineage_reconciliation.csv")
    assert len(rows) == 1
    assert rows[0]["new_strategy_configurations"] == "0"
    assert rows[0]["new_experiment_trials"] == "0"
    counts = json.loads((correction.OUTPUT_DIR / "corrected_funnel_counts.json").read_text(encoding="utf-8"))
    assert counts["new_strategy_configurations"] == 0
    assert counts["new_experiment_trials"] == 0
    assert counts["route_classifications_corrected"] == 1


def test_corrected_overlay_is_diversifier_only() -> None:
    rows = output_rows("corrected_outcome_overlay.csv")
    assert len(rows) == 1
    row = rows[0]
    assert row["standalone_outcome"] == "closed_exploration"
    assert row["standalone_failure_reason"] == "weak_vs_primary_control"
    assert row["selected_configuration_outcome"] == "exploratory_followup_candidate_diversifier"
    assert row["architecture_outcome"] == "factory_exploratory_followup_candidate"
    assert row["route_classification"] == "diversifier"


def test_original_packet_and_protected_state_are_unchanged() -> None:
    consistency = json.loads((correction.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["original_packet_hash_before"] == consistency["original_packet_hash_after"]
    assert consistency["original_file_hashes_before"] == consistency["original_file_hashes_after"]
    assert consistency["protected_hashes_before"] == consistency["protected_hashes_after"]


def test_exact_output_set_and_consistency_pass() -> None:
    actual = {path.name for path in correction.OUTPUT_DIR.iterdir() if path.is_file()}
    assert actual == correction.REQUIRED_FILES
    consistency = json.loads((correction.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert all(consistency["checks"].values())


def test_next_action_is_robustness_not_lifecycle_or_paper_demo() -> None:
    rows = output_rows("next_actions.csv")
    assert len(rows) == 1
    assert rows[0]["exact_next_action"] == "technical_factory_v1_trend_quality_diversifier_robustness_v1"
    assert rows[0]["execute_in_this_task"] == "false"
