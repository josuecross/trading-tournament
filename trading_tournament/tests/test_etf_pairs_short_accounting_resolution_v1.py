from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import etf_pairs_short_accounting_resolution_v1 as resolution


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "etf_pairs_short_accounting_resolution_v1" / "latest"
INTAKE_PATH = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / f"{resolution.SOURCE_ID}.yaml"
)


@pytest.fixture(scope="module", autouse=True)
def generated_resolution_packet() -> dict[str, object]:
    return resolution.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist_and_preregistration_ready() -> None:
    required = {
        "decision.json",
        "decision.md",
        "accounting_convention.yaml",
        "source_vs_project_conventions.csv",
        "cash_and_collateral_ledger_definition.csv",
        "exposure_convention.csv",
        "borrow_and_transaction_cost_convention.csv",
        "synthetic_ledger_scenarios.csv",
        "synthetic_ledger_results.csv",
        "accounting_invariants.csv",
        "local_history_feasibility.csv",
        "preregistration.yaml",
        "preregistration.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    decision = read_json("decision.json")
    assert decision["outcome"] == "preregistration_ready"
    assert decision["preregistration_created"] is True


def test_negative_share_quantities_and_mark_to_market() -> None:
    sleeve = resolution.SleeveLedger("test", 100.0)
    sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    assert sleeve.long_shares > 0
    assert sleeve.short_shares < 0
    before = sleeve.equity
    sleeve.mark("d1", 110.0, 90.0)
    assert sleeve.equity > before
    assert sleeve.long_market_value == pytest.approx(55.0)
    assert sleeve.short_liability == pytest.approx(45.0)


def test_cash_and_restricted_collateral_treatment_no_leverage() -> None:
    sleeve = resolution.SleeveLedger("collateral", 100.0)
    row = sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    assert sleeve.restricted_short_proceeds == pytest.approx(50.0)
    assert row["entry_long_notional"] == pytest.approx(50.0)
    assert row["entry_gross_target"] == pytest.approx(100.0)
    assert row["short_proceeds_restricted_not_buying_power"] is True
    assert sleeve.free_cash == pytest.approx(sleeve.cash - 50.0)


def test_borrow_cost_exactly_five_percent_over_252() -> None:
    sleeve = resolution.SleeveLedger("borrow", 100.0)
    sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    sleeve.mark("d1", 100.0, 100.0)
    assert resolution.BORROW_RATE_ANNUAL == pytest.approx(0.05)
    assert resolution.BORROW_RATE_DAILY == pytest.approx(0.05 / 252.0)
    assert sleeve.accrued_borrow_cost == pytest.approx(50.0 * 0.05 / 252.0)


def test_transaction_cost_on_every_traded_leg_and_short_cover_cash_flow() -> None:
    sleeve = resolution.SleeveLedger("costs", 100.0)
    sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    entry_cost = 2 * 50.0 * resolution.TRANSACTION_COST_RATE
    assert sleeve.transaction_costs == pytest.approx(entry_cost)
    exit_row = sleeve.exit("d1", 100.0, 100.0, "convergence_exit")
    assert sleeve.open_position is False
    assert sleeve.restricted_short_proceeds == pytest.approx(0.0)
    assert sleeve.long_shares == pytest.approx(0.0)
    assert sleeve.short_shares == pytest.approx(0.0)
    assert exit_row["short_cover_cost"] == pytest.approx(50.0 * resolution.TRANSACTION_COST_RATE)
    assert sleeve.transaction_costs >= 4 * 50.0 * resolution.TRANSACTION_COST_RATE - resolution.TOL


def test_target_gross_capped_at_sleeve_nav_and_exposure_drift_allowed() -> None:
    sleeve = resolution.SleeveLedger("drift", 100.0)
    entry = sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    assert entry["entry_gross_target"] <= entry["entry_nav_before_trade"] + resolution.TOL
    mark = sleeve.mark("d1", 120.0, 80.0)
    assert abs(mark["gross_exposure"] - 1.0) > 0.01
    assert sleeve.trade_count == 2


def test_no_daily_rebalancing_and_flat_sleeve_cash_zero_return() -> None:
    sleeve = resolution.SleeveLedger("flat", 100.0)
    row = sleeve.mark("d0", 100.0, 100.0)
    assert row["event"] == "flat_zero_return_cash"
    assert row["sleeve_equity"] == pytest.approx(100.0)
    sleeve.enter("d1", "AAA", "BBB", 100.0, 100.0)
    sleeve.mark("d2", 110.0, 90.0)
    sleeve.mark("d3", 120.0, 80.0)
    assert sleeve.trade_count == 2


def test_pair_overlap_preserved_at_sleeve_level_before_netting() -> None:
    s1 = resolution.SleeveLedger("overlap1", 20.0)
    s2 = resolution.SleeveLedger("overlap2", 20.0)
    s1.enter("d0", "XLK", "XLF", 100.0, 100.0)
    s2.enter("d0", "XLK", "XLE", 100.0, 100.0)
    assert s1.long_symbol == s2.long_symbol == "XLK"
    assert s1.trade_count == 2
    assert s2.trade_count == 2
    aggregate = resolution.aggregate_sleeves([s1, s2], "d0", "aggregate")
    assert aggregate["aggregate_transaction_costs"] == pytest.approx(s1.transaction_costs + s2.transaction_costs)


def test_reentry_uses_current_nav_and_forced_close() -> None:
    sleeve = resolution.SleeveLedger("reentry", 100.0)
    sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    sleeve.exit("d1", 110.0, 90.0, "convergence_exit")
    current_nav = sleeve.equity
    reentry = sleeve.enter("d2", "AAA", "BBB", 100.0, 100.0)
    assert reentry["entry_gross_target"] == pytest.approx(current_nav)
    forced = sleeve.exit("d_final", 102.0, 99.0, "forced_close")
    assert forced["event"] == "forced_close"
    assert sleeve.open_position is False


def test_missing_prices_invalidate_without_forward_fill() -> None:
    sleeve = resolution.SleeveLedger("missing", 100.0)
    sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
    row = sleeve.mark("d1", None, 100.0)
    assert sleeve.invalid is True
    assert row["event"] == "invalid_missing_mark_price"


def test_five_sleeves_aggregate_correctly() -> None:
    sleeves = [resolution.SleeveLedger(f"s{i}", 20.0) for i in range(5)]
    for sleeve in sleeves:
        sleeve.enter("d0", "AAA", "BBB", 100.0, 100.0)
        sleeve.mark("d1", 101.0, 99.0)
    aggregate = resolution.aggregate_sleeves(sleeves, "d1", "aggregate")
    assert aggregate["total_strategy_equity"] == pytest.approx(sum(sleeve.equity for sleeve in sleeves))
    assert aggregate["all_accounting_identities_hold"] is True


def test_exact_frozen_universe_and_history_feasibility() -> None:
    prereg = yaml.safe_load((EVIDENCE / "preregistration.yaml").read_text(encoding="utf-8"))
    assert prereg["exact_universe"] == list(resolution.FROZEN_UNIVERSE)
    history = read_csv("local_history_feasibility.csv")
    assert {row["symbol"] for row in history} == set(resolution.FROZEN_UNIVERSE)
    assert all(row["cache_ready"] == "true" for row in history)
    assert all(row["provider_download_required"] == "false" for row in history)


def test_no_provider_calls_no_historical_performance_no_state_changes() -> None:
    decision = read_json("decision.json")
    assert decision["provider_download"] is False
    assert decision["historical_backtest_run"] is False
    assert decision["candidate_performance_computed"] is False
    assert decision["parameter_search"] is False
    assert decision["alternate_universe_tested"] is False
    assert decision["registry_byte_identical"] is True
    assert decision["active_observations_unchanged"] is True
    assert decision["promotion_or_paper_demo_activation"] is False


def test_prior_intake_record_links_resolution_packet_without_hiding_blocked_state() -> None:
    intake = yaml.safe_load(INTAKE_PATH.read_text(encoding="utf-8"))
    assert intake["source"]["source_id"] == resolution.SOURCE_ID
    assert intake["intake_status"] == "single_direction_owner_source_supplied_for_preregistration_gate"
    links = intake.get("resolution_packets", [])
    assert any(link["resolution_id"] == "etf_pairs_short_accounting_resolution_v1" for link in links)
    assert intake["governance"]["prior_blocked_state_preserved"] is True


def test_consistency_check_passes_and_generation_is_deterministic() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["negative_share_quantities_supported_candidate_local"] is True
    assert check["borrow_cost_exact_5pct_over_252"] is True
    assert check["transaction_cost_exact_0005_per_leg"] is True
    first_decision = read_json("decision.json")
    first_scenarios = (EVIDENCE / "synthetic_ledger_scenarios.csv").read_text(encoding="utf-8")
    rerun = resolution.run()
    second_decision = read_json("decision.json")
    second_scenarios = (EVIDENCE / "synthetic_ledger_scenarios.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_decision == first_decision
    assert second_scenarios == first_scenarios
