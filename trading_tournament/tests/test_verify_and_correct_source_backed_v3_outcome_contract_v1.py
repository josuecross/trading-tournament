from __future__ import annotations

import pandas as pd

from strategy_lab.research_os.research import (
    verify_and_correct_source_backed_v3_outcome_contract_v1 as correction,
)


def test_failure_precedence_assigns_trendpilot_period_instability() -> None:
    failures, _ = correction.failure_reasons_from_checks(
        {
            "positive_full_period_return": True,
            "named_control_does_not_dominate": True,
            "material_vs_named": True,
            "static_control_does_not_dominate": True,
            "material_vs_static": True,
            "chronological_halves_pass": False,
            "positive_at_10bps": True,
            "not_dominated_by_both_controls_at_10bps": True,
        },
        {"chronological_halves_pass": False},
        True,
        False,
    )

    assert failures[0] == "period_instability"


def test_failure_precedence_assigns_presidential_signal_scarcity() -> None:
    failures, _ = correction.failure_reasons_from_checks(
        {
            "positive_full_period_return": True,
            "named_control_does_not_dominate": False,
            "material_vs_named": False,
            "static_control_does_not_dominate": False,
            "material_vs_static": False,
            "chronological_halves_pass": False,
            "positive_at_10bps": True,
            "not_dominated_by_both_controls_at_10bps": False,
        },
        {"chronological_halves_pass": False},
        False,
        False,
    )

    assert failures[0] == "signal_scarcity"
    assert "weak_vs_primary_control" in failures
    assert "period_instability" in failures


def test_presidential_completed_window_contract_uses_windows_not_turnover_events() -> None:
    windows = pd.DataFrame(
        [
            {"strategy_id": correction.PRES_ID, "trial_id": "t", "election_year": 2008, "entry_execution_date": "", "exit_execution_date": "2008-10-31", "complete_source_window": False},
            {"strategy_id": correction.PRES_ID, "trial_id": "t", "election_year": 2012, "entry_execution_date": "2010-10-29", "exit_execution_date": "2012-10-31", "complete_source_window": True},
            {"strategy_id": correction.PRES_ID, "trial_id": "t", "election_year": 2016, "entry_execution_date": "2014-10-31", "exit_execution_date": "2016-10-31", "complete_source_window": True},
            {"strategy_id": correction.PRES_ID, "trial_id": "t", "election_year": 2020, "entry_execution_date": "2018-10-31", "exit_execution_date": "2020-10-30", "complete_source_window": True},
            {"strategy_id": correction.PRES_ID, "trial_id": "t", "election_year": 2024, "entry_execution_date": "2022-10-31", "exit_execution_date": "2024-10-31", "complete_source_window": True},
        ]
    )
    half_results = pd.DataFrame(
        [
            {"strategy_id": correction.PRES_ID, "series_id": correction.PRES_ID, "entity_role": "candidate", "period": "first_chronological_half", "evaluation_start": "2010-10-29", "evaluation_end": "2018-08-01"},
            {"strategy_id": correction.PRES_ID, "series_id": correction.PRES_ID, "entity_role": "candidate", "period": "second_chronological_half", "evaluation_start": "2018-08-02", "evaluation_end": "2026-08-04"},
        ]
    )

    _, detail = correction.presidential_window_reconciliation(windows, half_results)

    assert detail["evidence_measure"] == "completed_presidential_source_window"
    assert detail["total"] == 4
    assert detail["minimum_total"] == 5
    assert detail["minimum_per_half"] == 2
    assert detail["pass"] is False


def test_self_tests_pass() -> None:
    assert all(correction.self_tests().values())
