from __future__ import annotations

from strategy_lab.research_os.research import materialize_and_resume_accepted_47_source_backed_batch_v1 as task


def test_exact_two_specs_and_families() -> None:
    assert len(task.SPECS) == 2
    assert len({spec["family_id"] for spec in task.SPECS}) == 2


def test_exact_proposed_trial_ids() -> None:
    assert {spec["proposed_trial_id"] for spec in task.SPECS} == {
        "accepted47_source_v1__caa_n8_tv10__canonical",
        "accepted47_source_v1__tactical_permanent_portfolio__canonical",
    }


def test_source_packet_schema_contract() -> None:
    assert all(task.source_packet_checks().values())


def test_caa_parameters_are_frozen() -> None:
    params = task.CAA_SPEC["parameters"]
    assert params["target_annualized_volatility"] == 0.10
    assert params["noncash_weight_cap"] == 0.25
    assert params["expected_return_divisor"] == 22


def test_tpp_parameters_are_frozen() -> None:
    params = task.TPP_SPEC["parameters"]
    assert params["trend_SMA_sessions"] == 200
    assert params["inverse_volatility_sessions"] == 21
    assert params["portfolio_covariance_sessions"] == 60
    assert params["target_annualized_volatility"] == 0.07


def test_all_symbols_are_in_accepted_membership() -> None:
    accepted = task.accepted_symbols()
    for row in task.configuration_rows():
        assert set(row["instrument_universe"]) <= accepted


def test_materialization_creates_no_trials() -> None:
    manifest = task.materialize_source_packet()
    assert manifest["experiment_trials_created"] == 0


def test_blocked_history_path_is_separate_from_latest() -> None:
    assert task.HISTORY_DIR != task.BLOCKED_DIR
    assert "history" in task.HISTORY_DIR.parts
