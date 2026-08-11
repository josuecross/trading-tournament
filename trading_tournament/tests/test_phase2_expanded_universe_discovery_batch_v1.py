from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import phase2_expanded_universe_discovery_batch_v1 as batch


def read_csv(name: str) -> list[dict[str, str]]:
    with (batch.OUTPUT_DIR / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_frozen_scope_source_versions_and_controls() -> None:
    assert len(batch.SPECS) == 2
    assert {spec.strategy_id for spec in batch.SPECS} == {batch.ROTATOR_ID, batch.DOGS_ID}
    assert batch.SPEC_BY_ID[batch.ROTATOR_ID].parameters["source_version"] == "January_2026"
    assert batch.SPEC_BY_ID[batch.ROTATOR_ID].parameters["periodic_return_months"] == [1, 3, 6, 9, 12]
    assert batch.SPEC_BY_ID[batch.DOGS_ID].parameters["holding_calendar_years"] == 5
    assert batch.SPEC_BY_ID[batch.DOGS_ID].parameters["cohort_slots"] == 5
    assert len(batch.benchmark_rows()) == 10
    assert all(row["entity_type"] == "benchmark_reference" for row in batch.benchmark_rows())


def test_phase2_hash_and_required_symbol_contract() -> None:
    rows, by_symbol, reconciliation = batch.load_universe_contract()
    assert len(rows) == 88
    assert reconciliation["computed_hash"] == batch.EXPECTED_UNIVERSE_HASH
    assert set(batch.ROTATOR_UNIVERSE + batch.DOGS_UNIVERSE).issubset(by_symbol)
    assert not (batch.PROHIBITED_SYMBOLS & set(by_symbol))


def test_market_rotator_periodic_return_fixture_and_first_session_execution() -> None:
    index = pd.bdate_range("2020-01-01", "2021-04-05")
    series = {}
    for symbol, monthly_growth in (("SPY", 1.02), ("SPLV", 1.01), ("RSP", 1.015), ("BIL", 1.0001)):
        month_number = pd.Series(index.to_period("M")).factorize()[0]
        values = np.power(monthly_growth, month_number.astype(float))
        series[symbol] = pd.Series(values, index=index, name=symbol)
    prepared = batch.build_market_rotator(series)
    valid = [row for row in prepared["signal_rows"] if row["ranking_inputs_complete"]]
    assert valid
    first = valid[0]
    formation = pd.Timestamp(first["formation_date"])
    execution = pd.Timestamp(first["execution_date"])
    assert execution > formation
    assert execution == index[index.searchsorted(formation, side="right")]
    assert first["selected_component"] == "SPY"
    spy_returns = first["periodic_returns"]["SPY"]
    assert np.isclose(spy_returns["return_12m"], 1.02**12 - 1.0)


def test_dynamic_country_eligibility_rejects_partial_year() -> None:
    index = pd.bdate_range("2019-01-01", "2021-01-08")
    series = {symbol: pd.Series(np.linspace(10.0, 12.0, len(index)), index=index, name=symbol) for symbol in batch.DOGS_UNIVERSE}
    series["INDA"] = series["INDA"].loc[series["INDA"].index >= pd.Timestamp("2020-07-01")]
    prepared = batch.build_dogs_formations(series)
    row = next(
        item for item in prepared["eligibility_rows"]
        if item["formation_year"] == 2020 and item["country"] == "INDA"
    )
    assert row["eligible"] is False
    assert row["partial_year_return_used"] is False


def test_five_cohort_replacement_and_duplicate_country_lots() -> None:
    index = pd.bdate_range("2000-01-03", "2007-01-10")
    prices = pd.DataFrame(100.0, index=index, columns=list(batch.DOGS_UNIVERSE))
    formations = []
    for offset, year in enumerate(range(2000, 2007)):
        formation = index[(index.year == year) & (index.month == 12)][-1]
        execution = index[(index.year == year + 1) & (index.month == 1)][0]
        selection = ("EWA", "EWC", "EWG", "EWJ", "EWU")
        formations.append(
            {
                "formation_year": year,
                "formation_date": pd.Timestamp(formation),
                "execution_date": pd.Timestamp(execution),
                "eligible_countries": batch.DOGS_COUNTRIES,
                "eligible_count": len(batch.DOGS_COUNTRIES),
                "dogs_selection": selection,
                "winners_selection": selection,
            }
        )
    path = batch.simulate_dogs_cohorts(
        prices,
        formations,
        5.0,
        selection_key="dogs_selection",
        portfolio_id="fixture",
    )
    cohorts = {row["formation_year"]: row for row in path["cohort_records"]}
    assert cohorts[2000]["cohort_status"] == "completed_five_calendar_years"
    assert cohorts[2000]["completed_holding_years"] == 5
    assert len(path["replacement_execution_dates"]) == 2
    assert all(event.get("nonexpiring_slots_modified", False) is False for event in path["events"])
    assert "fixture__2004" in path["cohort_contributions"].columns
    assert "fixture__2005" in path["cohort_contributions"].columns


def test_turnover_cost_and_no_lookahead_fixture() -> None:
    index = pd.bdate_range("2020-01-01", periods=4)
    prices = pd.DataFrame({"SPY": [100, 101, 102, 103], "BIL": [100, 100, 100, 100]}, index=index)
    events = batch.event_frame(
        index,
        ("SPY", "BIL"),
        {
            index[0]: batch.explicit_target(("SPY", "BIL"), {"BIL": 1.0}),
            index[2]: batch.explicit_target(("SPY", "BIL"), {"SPY": 1.0}),
        },
    )
    path = batch.simulate_events(
        prices,
        events,
        5.0,
        timing_policy="fixture",
        formation_dates=(index[1],),
        execution_dates=(index[2],),
    )
    assert np.isclose(path["daily"].loc[index[2], "one_way_turnover"], 1.0)
    assert path["returns"].loc[index[2]] < 0.0
    assert path["returns"].loc[index[3]] > 0.0
    assert path["timing_invariant_pass"] is True


def test_failure_precedence_prefers_signal_scarcity() -> None:
    source = batch.classify_strategies
    text = source.__code__.co_consts
    assert "signal_scarcity" in text
    assert "weak_vs_primary_control" in text


def test_serial_run_packet_entities_and_determinism() -> None:
    first = batch.run()
    assert first["consistency_overall_pass"] is True
    first_check = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    second = batch.run()
    second_check = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
    assert first_check["deterministic_core_hash"] == second_check["deterministic_core_hash"]
    assert set(path.name for path in batch.OUTPUT_DIR.iterdir() if path.is_file()) == batch.REQUIRED_OUTPUTS
    assert set(path.name for path in batch.INTAKE_DIR.iterdir() if path.is_file()) == batch.REQUIRED_INTAKE_OUTPUTS
    counts = json.loads((batch.OUTPUT_DIR / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["source_library_records"] == 2
    assert counts["strategy_configurations"] == 2
    assert counts["canonical_experiment_trials"] == 2
    assert counts["provider_calls"] == 0
    assert counts["robustness_trials"] == counts["validation_trials"] == counts["observations"] == 0


def test_outputs_keep_failures_and_no_provider_or_cache_action() -> None:
    outcomes = read_csv("outcome_summary.csv")
    failures = read_csv("failure_vectors.csv")
    assert len(outcomes) == 2
    assert len(failures) == 18
    assert all(row["evaluated_before_primary_failure_selection"] == "True" for row in failures)
    manifest = yaml.safe_load((batch.OUTPUT_DIR / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["provider_calls"] == 0
    assert manifest["cache_modifications"] == 0
    consistency = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["protected_state_and_caches_unchanged"] is True
