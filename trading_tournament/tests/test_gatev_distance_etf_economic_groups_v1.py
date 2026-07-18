from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from strategy_lab.research_os.universe_expansion import gatev_distance_etf_economic_groups_v1 as gatev


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "gatev_distance_etf_economic_groups_v1" / "latest"


EXPECTED_GROUP_COUNTS = {
    "us_broad_size_style_factors": 28,
    "us_sectors_liquid_industries": 36,
    "developed_emerging_regions_countries": 66,
    "government_bonds_and_credit": 36,
    "commodities_and_precious_metals": 6,
}

EXPECTED_CYCLES = [
    ("cycle_2017_H1", "2016-01-01", "2016-12-31", "2017-01-03", "2017-06-30"),
    ("cycle_2017_H2", "2016-07-01", "2017-06-30", "2017-07-03", "2017-12-29"),
    ("cycle_2018_H1", "2017-01-01", "2017-12-31", "2018-01-02", "2018-06-29"),
    ("cycle_2018_H2", "2017-07-01", "2018-06-30", "2018-07-02", "2018-12-31"),
    ("cycle_2019_H1", "2018-01-01", "2018-12-31", "2019-01-02", "2019-06-28"),
    ("cycle_2019_H2", "2018-07-01", "2019-06-30", "2019-07-01", "2019-12-31"),
    ("cycle_2020_H1", "2019-01-01", "2019-12-31", "2020-01-02", "2020-06-30"),
    ("cycle_2020_H2", "2019-07-01", "2020-06-30", "2020-07-01", "2020-12-31"),
    ("cycle_2021_H1", "2020-01-01", "2020-12-31", "2021-01-04", "2021-06-30"),
    ("cycle_2021_H2", "2020-07-01", "2021-06-30", "2021-07-01", "2021-12-31"),
]


@pytest.fixture(scope="module", autouse=True)
def generated_gatev() -> dict[str, object]:
    return gatev.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_required_outputs_exist() -> None:
    for name in gatev.OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name


def test_prior_universe_portability_and_sector_packets_remain_byte_identical() -> None:
    payload = read_json("pilot_universe_hash_verification.json")
    assert payload["protected_packets_byte_identical"] is True
    assert payload["protected_before"] == payload["protected_after"]
    assert read_json("consistency_check.json")["protected_packets_byte_identical"] is True


def test_only_frozen_172_within_group_pairs_exist_and_no_cross_group_pairs() -> None:
    pairs = read_csv("all_formation_candidate_pairs.csv")
    assert len(pairs) == 172
    assert Counter(row["economic_group"] for row in pairs) == EXPECTED_GROUP_COUNTS
    assert {row["within_group_pair"] for row in pairs} == {"true"}
    assert {row["cross_group_pair"] for row in pairs} == {"false"}
    assert {row["correlation_screen_used"] for row in pairs} == {"false"}
    assert {row["cointegration_screen_used"] for row in pairs} == {"false"}
    assert {row["validation_performance_screen_used"] for row in pairs} == {"false"}


def test_sector_group_is_known_overlap_and_excluded_from_independent_outcome() -> None:
    summary = read_csv("group_validation_summary.csv")
    sector = [row for row in summary if row["economic_group"] == gatev.KNOWN_OVERLAP_GROUP][0]
    assert sector["known_overlap_group"] == "true"
    assert sector["counts_as_independent_family_evidence"] == "false"
    outcome = read_json("family_outcome.json")
    assert outcome["sector_group_excluded_from_independent_family_evidence"] is True
    assert outcome["independent_selected_pair_cycle_trials"] == 80
    assert outcome["selected_pair_cycle_trials"] == 100


def test_frozen_formation_and_trading_cycle_boundaries() -> None:
    rows = read_csv("frozen_validation_cycles.csv")
    observed = [
        (
            row["cycle_id"],
            row["formation_calendar_start"],
            row["formation_calendar_end"],
            row["trading_start"],
            row["trading_end"],
        )
        for row in rows
    ]
    assert observed == EXPECTED_CYCLES
    assert {row["formation_months"] for row in rows} == {"12"}
    assert {row["trading_months"] for row in rows} == {"6"}
    assert {row["boundaries_frozen_before_distance_or_performance"] for row in rows} == {"true"}


def test_every_formation_candidate_remains_in_cycle_ledger() -> None:
    ledger = read_csv("formation_candidate_trial_ledger.csv")
    assert len(ledger) == 172 * 10
    counts = Counter((row["cycle_id"], row["economic_group"]) for row in ledger)
    for cycle_id, *_rest in EXPECTED_CYCLES:
        for group, expected_count in EXPECTED_GROUP_COUNTS.items():
            assert counts[(cycle_id, group)] == expected_count


def test_exactly_two_pairs_per_group_cycle_selected() -> None:
    selected = read_csv("selected_pair_cycle_inventory.csv")
    assert len(selected) == 2 * len(EXPECTED_GROUP_COUNTS) * len(EXPECTED_CYCLES)
    counts = Counter((row["cycle_id"], row["economic_group"]) for row in selected)
    assert set(counts.values()) == {2}


def test_selection_uses_only_formation_distance_with_lexicographic_tiebreak() -> None:
    rankings = read_csv("formation_cycle_rankings.csv")
    by_group_cycle: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rankings:
        assert row["selection_basis"] == "formation_distance_only"
        assert row["validation_performance_used_for_selection"] == "false"
        by_group_cycle[(row["cycle_id"], row["economic_group"])].append(row)
    for rows in by_group_cycle.values():
        valid = [row for row in rows if row["blocked"] == "false"]
        expected = {
            row["pair_id"]
            for row in sorted(valid, key=lambda item: (float(item["formation_distance"]), item["pair_id"]))[:2]
        }
        observed = {row["pair_id"] for row in rows if row["selected"] == "true"}
        assert observed == expected


def test_normalization_and_entry_threshold_are_frozen() -> None:
    rows = [row for row in read_csv("formation_cycle_rankings.csv") if row["blocked"] == "false"]
    assert rows
    assert {row["normalized_first_start"] for row in rows} == {"1"}
    assert {row["normalized_second_start"] for row in rows} == {"1"}
    for row in rows:
        assert float(row["entry_threshold"]) == pytest.approx(2.0 * float(row["formation_spread_std"]), abs=1e-12)


def test_entry_exit_timing_and_direction_are_no_lookahead() -> None:
    events = read_csv("frozen_entry_and_exit_dates.csv")
    assert events
    for row in events:
        if row["event_type"] in {"entry", "convergence_exit"}:
            assert row["execution_date"] > row["signal_date"]
            assert row["same_close_execution"] == "false"
        if row["event_type"] == "entry" and float(row["trigger_spread"]) > 0.0:
            first, second = row["pair_id"].split("-")
            assert row["short_symbol"] == first
            assert row["long_symbol"] == second
        if row["event_type"] == "entry" and float(row["trigger_spread"]) < 0.0:
            first, second = row["pair_id"].split("-")
            assert row["long_symbol"] == first
            assert row["short_symbol"] == second


def test_exposure_short_borrow_cost_and_close_invariants() -> None:
    invariants = read_csv("accounting_timing_short_data_and_exposure_invariants.csv")
    assert len(invariants) == 100
    assert max(float(row["max_gross_exposure"]) for row in invariants) <= 1.000001
    assert max(abs(float(row["max_abs_net_exposure"])) for row in invariants) <= 1e-9
    for field in [
        "gross_exposure_invariant_passed",
        "exposure_invariant_passed",
        "net_target_exposure_zero_at_entry",
        "borrow_cost_only_when_short_open",
        "costs_applied_per_leg",
        "spread_convergence_or_period_end_closes_pair",
        "no_stop_loss_or_alternate_threshold",
        "no_holdout_metric_generated",
    ]:
        assert {row[field] for row in invariants} == {"true"}
    costs = read_csv("cost_and_borrow_attribution.csv")
    assert all(float(row["transaction_cost_rate_per_leg"]) == pytest.approx(0.0005) for row in costs)
    assert all(float(row["borrow_rate_annual"]) == pytest.approx(0.05) for row in costs)
    assert all(float(row["borrow_rate_daily"]) == pytest.approx(gatev.BORROW_RATE_DAILY) for row in costs)
    assert all(float(row["borrow_cost"] or 0.0) >= 0.0 for row in costs)


def test_secondary_diagnostics_cannot_affect_outcomes_and_no_winners_selected() -> None:
    assert {row["secondary_diagnostics_only"] for row in read_csv("long_short_attribution.csv")} == {"true"}
    distribution = read_csv("trial_outcome_distribution.csv")
    assert {row["secondary_diagnostics_used_for_distribution"] for row in distribution} == {"false"}
    consistency = read_json("consistency_check.json")
    assert consistency["secondary_diagnostics_excluded_from_outcomes"] is True
    assert consistency["winning_pair_selected"] is False
    assert consistency["winning_group_selected"] is False
    assert consistency["portfolio_created_from_winners"] is False


def test_holdout_remains_sealed_and_no_holdout_result_file_exists() -> None:
    manifest = read_json("sealed_holdout_manifest.json")
    assert manifest["holdout_start"] == "2022-01-03"
    assert manifest["holdout_end"] == "2026-07-16"
    for key in [
        "holdout_pair_selection_calculated",
        "holdout_spread_calculated",
        "holdout_signal_calculated",
        "holdout_trade_calculated",
        "holdout_return_calculated",
    ]:
        assert manifest[key] is False
    forbidden = [
        path.name
        for path in EVIDENCE.iterdir()
        if path.is_file() and "holdout" in path.name and path.name != "sealed_holdout_manifest.json"
    ]
    assert forbidden == []


def test_registry_and_active_observations_remain_unchanged() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_byte_identical"] is True
    assert consistency["active_observations_byte_identical"] is True
    assert consistency["paper_demo_observation_created"] is False
    assert consistency["broker_order_created"] is False
    assert consistency["real_money_recommendation"] is False


def test_family_outcome_and_next_action_are_exact() -> None:
    outcome = read_json("family_outcome.json")
    assert outcome["primary_outcome"] == "failed_distribution"
    assert outcome["exact_family_trial_closed"] is True
    assert outcome["broader_family_preserved"] is True
    assert outcome["groups_with_positive_median_excess"] == 0
    assert outcome["median_net_return"] <= 0.0
    assert outcome["median_excess_vs_bil"] <= 0.0
    assert outcome["next_action"] == "direction_owner_review_controlled_etf_pairs_discovery_v1"
    assert read_json("consistency_check.json")["consistency_passed"] is True


def test_output_is_deterministic() -> None:
    names = [
        "formation_cycle_rankings.csv",
        "selected_pair_cycle_inventory.csv",
        "net_pair_cycle_results.csv",
        "family_outcome.json",
        "consistency_check.json",
    ]
    before = {name: sha256(EVIDENCE / name) for name in names}
    gatev.run()
    after = {name: sha256(EVIDENCE / name) for name in names}
    assert before == after
