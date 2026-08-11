from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import role_aware_robustness_spdj_sp500_market_rotator_spy_splv_rsp_v1 as subject


OUTPUT = ROOT / "evidence" / "robustness" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run() -> dict[str, object]:
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_exact_identity_role_and_single_child_trial() -> None:
    lineage = rows("strategy_and_trial_lineage.csv")
    children = [row for row in lineage if row["record_type"] == "new_robustness_child_trial"]
    assert len(children) == 1
    assert children[0]["strategy_id"] == subject.STRATEGY_ID
    assert children[0]["trial_id"] == subject.TRIAL_ID
    assert children[0]["parent_trial_id"] == subject.PARENT_TRIAL_ID
    assert children[0]["primary_robustness_role"] == "dynamic_multi_asset_allocation_strategy"
    assert children[0]["adaptation_label"] == "robustness_diagnostics_only"
    assert children[0]["parameters_changed"] == "false"


def test_phase2_hash_source_version_and_local_cache_contract() -> None:
    universe = rows("phase2_universe_reconciliation.csv")
    assert {row["symbol"] for row in universe if row.get("symbol")} == {"SPY", "SPLV", "RSP", "BIL"}
    assert all(row["observed_frozen_hash"] == subject.EXPECTED_UNIVERSE_HASH for row in universe)
    assert all(row["provider_access"] == "false" for row in universe)
    source = rows("source_version_reconciliation.csv")
    assert len(source) == 1
    assert source[0]["institutional_source_methodology_version"] == subject.SOURCE_VERSION
    assert source[0]["phase2_additions_essential"] == "SPLV|RSP"


def test_parent_reproduction_and_first_business_day_timing() -> None:
    reproduction = rows("parent_reproduction_results.csv")
    assert reproduction
    assert all(row["reproduction_pass"] == "true" for row in reproduction)
    score_rows = rows("multi_horizon_score_attribution.csv")
    first = score_rows[0]
    assert first["formation_date"] < first["execution_date"]
    assert {"return_1m", "return_3m", "return_6m", "return_9m", "return_12m"}.issubset(first)
    assert {row["component"] for row in score_rows} == {"SPY", "SPLV", "RSP"}


def test_authoritative_gate_matrix_is_complete_and_frozen() -> None:
    standard = subject.load_standard()
    gates = rows("applicable_gate_matrix.csv")
    authoritative = [row for row in gates if row["gate_scope"] != "diagnostic"]
    expected = len(standard["universal_hard_gates"]) + len(standard["role_specific_hard_gate_contracts"][subject.PRIMARY_ROLE])
    assert len(authoritative) == expected
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["applicable_gate_matrix_hash"] == subject.file_hash(OUTPUT / "applicable_gate_matrix.csv")


def test_rolling_bootstrap_and_concentration_contracts() -> None:
    rolling = rows("rolling_window_summary.csv")
    assert {(row["window_months"], row["comparison_control_id"]) for row in rolling} == {
        (str(months), control) for months in (36, 60) for control in subject.DECISIVE_CONTROLS
    }
    assert all(float(row["candidate_improves_control_fraction"]) > 0.50 for row in rolling)
    bootstrap = rows("paired_bootstrap_results.csv")
    assert len(bootstrap) == 3
    assert all(row["pass"] == "true" for row in bootstrap)
    assert all(row["iterations"] == str(subject.BOOTSTRAP_RESAMPLES) for row in bootstrap)
    concentration = {row["concentration_unit"]: row for row in rows("role_valid_concentration_results.csv")}
    assert concentration["selected_state"]["blocking_for_role"] == "true"
    assert concentration["calendar_year"]["blocking_for_role"] == "true"
    assert float(concentration["selected_state"]["strongest_unit_share"]) <= 0.60
    assert float(concentration["calendar_year"]["strongest_unit_share"]) <= 0.60


def test_state_and_horizon_attribution_are_diagnostics_not_trials() -> None:
    states = rows("state_attribution_results.csv")
    assert {row["selected_state"] for row in states} == {"SPY", "SPLV", "RSP"}
    assert sum(int(row["selection_count"]) for row in states) == 171
    disagreements = rows("candidate_control_disagreement_results.csv")
    detail = [row for row in disagreements if row["formation_date"] != "summary"]
    assert len(detail) == 171
    assert any(row["candidate_control_agree"] == "false" for row in detail)
    counts = json.loads((OUTPUT / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["new_robustness_trials"] == 1
    assert counts["new_strategy_configurations"] == 0


def test_failure_vector_and_precedence_are_exact() -> None:
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["outcome"] == "robustness_failed"
    assert consistency["failure_reason"] == "period_instability"
    assert consistency["complete_failed_blocking_gate_vector"] == [
        "candidate_improves_every_decisive_control_in_at_least_3_of_4_quarters"
    ]
    quarters = rows("chronological_quarter_results.csv")
    named = [row for row in quarters if row["comparison_control_id"] == subject.NAMED_CONTROL]
    assert sum(row["candidate_improves_control_sharpe_or_drawdown"] == "true" for row in named) == 2
    assert rows("next_actions.csv")[0]["next_action"] == subject.NEXT_REVIEW


def test_costs_turnover_and_invariants() -> None:
    costs = rows("cost_stress_results.csv")
    assert {float(row["cost_bps_one_way"]) for row in costs} == set(subject.COSTS)
    turnover = rows("turnover_cost_reconciliation.csv")
    assert max(float(row["absolute_reconciliation_difference"]) for row in turnover) <= 1e-12
    invariants = rows("invariant_results.csv")
    assert all(row["invariant_pass"] == "true" for row in invariants)


def test_required_outputs_and_deterministic_rerun(completed_run: dict[str, object]) -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUTS
    first_hash = completed_run["deterministic_core_hash"]
    second = subject.run()
    assert second["overall_pass"] is True
    assert second["deterministic_core_hash"] == first_hash
    assert second["checks"]["protected_state_and_caches_unchanged"] is True
    assert second["forbidden_actions"] == {
        "broker_account_order_or_real_money_action": False,
        "cache_mutation": False,
        "dogs_reopened": False,
        "forward_observation": False,
        "handoff": False,
        "paper_demo_eligibility": False,
        "provider_or_network_call": False,
        "strategy_or_parameter_change": False,
    }
