from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import etf_pairs_distance_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "etf_pairs_distance_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist() -> None:
    required = {
        "execution_manifest.json",
        "cycle_definitions.csv",
        "formation_pair_distances.csv",
        "selected_pairs_by_cycle.csv",
        "daily_pair_signals.csv",
        "trade_ledger.csv",
        "daily_sleeve_ledgers.csv",
        "daily_strategy_path.csv",
        "cycle_metrics.csv",
        "aggregate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "gross_vs_cost_decomposition.csv",
        "exposure_and_accounting_invariants.csv",
        "invalid_cycles.csv",
        "screening_summary.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_manifest_freezes_candidate_scope_and_guardrails() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["candidate_id"] == screen.CANDIDATE_ID
    assert manifest["source_id"] == screen.SOURCE_ID
    assert manifest["exact_universe"] == list(screen.FROZEN_UNIVERSE)
    assert manifest["initial_capital"] == pytest.approx(3000.0)
    assert manifest["borrow_cost_convention"]["daily"] == pytest.approx(0.05 / 252.0)
    assert manifest["transaction_cost_convention"]["per_leg_rate"] == pytest.approx(0.0005)
    assert manifest["no_search_or_optimization_authorized"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_authorized"] is False
    assert manifest["paper_demo_activation"] is False
    assert manifest["broker_or_live_path"] is False


def test_complete_january_july_cycles_and_incomplete_final_cycle_excluded() -> None:
    rows = read_csv("cycle_definitions.csv")
    cycle_ids = {row["cycle_id"] for row in rows}
    assert "cycle_2018_07" not in cycle_ids
    assert "cycle_2019_01" not in cycle_ids
    assert "cycle_2026_01" not in cycle_ids
    assert rows[0]["cycle_id"] == "cycle_2019_07"
    assert all(pd.Timestamp(row["trading_start"]).month in {1, 7} for row in rows)
    for row in rows:
        boundary = pd.Timestamp(row["trading_start"]) - pd.DateOffset(months=12)
        assert pd.Timestamp(row["formation_start"]) <= boundary + pd.Timedelta(days=7)
        assert row["complete_formation_period"] == "true"
        assert row["complete_six_month_trading_period"] == "true"


def test_cache_hashes_and_frozen_universe_are_recorded() -> None:
    manifest = read_json("execution_manifest.json")
    cache_rows = manifest["cache_files"]
    assert [row["symbol"] for row in cache_rows] == list(screen.FROZEN_UNIVERSE)
    assert all(row["cache_ready"] is True for row in cache_rows)
    assert all(row["provider_download_required"] is False for row in cache_rows)
    lineage = [row for row in read_csv("artifact_lineage.csv") if row["artifact_type"] == "cache_file"]
    assert {row["artifact_id"] for row in lineage} == set(screen.FROZEN_UNIVERSE)
    assert all(row["sha256"] for row in lineage)


def test_formation_normalization_continues_into_trading() -> None:
    prices = screen.common_valid_prices(screen.load_price_frame(list(screen.FROZEN_UNIVERSE)))
    cycle = screen.generate_cycle_definitions(prices)[0]
    normalized = screen.normalize_for_cycle(prices, cycle)
    first_symbol = screen.FROZEN_UNIVERSE[0]
    assert normalized.at[cycle.formation_dates[0], first_symbol] == pytest.approx(1.0)
    trading_value = normalized.at[cycle.trading_dates[0], first_symbol]
    expected = prices.at[cycle.trading_dates[0], first_symbol] / prices.at[cycle.formation_dates[0], first_symbol]
    assert trading_value == pytest.approx(expected)
    assert trading_value != pytest.approx(1.0)


def test_distance_ranking_top_five_and_tie_breaking_are_deterministic() -> None:
    distances = read_csv("formation_pair_distances.csv")
    selected = read_csv("selected_pairs_by_cycle.csv")
    for cycle_id in {row["cycle_id"] for row in selected}:
        cycle_distances = [row for row in distances if row["cycle_id"] == cycle_id]
        expected = sorted(cycle_distances, key=lambda row: (float(row["distance"]), row["first_ticker"], row["second_ticker"]))[: screen.PAIR_COUNT]
        actual = [row for row in selected if row["cycle_id"] == cycle_id]
        assert [row["pair_id"] for row in actual] == [row["pair_id"] for row in expected]
        assert [int(row["pair_rank"]) for row in actual] == list(range(1, screen.PAIR_COUNT + 1))


def test_pair_overlap_is_allowed_and_sleeves_remain_independent() -> None:
    selected = read_csv("selected_pairs_by_cycle.csv")
    assert any(int(row["pair_overlap_count"]) > 0 for row in selected)
    ledgers = read_csv("daily_sleeve_ledgers.csv")
    first_cycle = selected[0]["cycle_id"]
    sleeve_ids = {row["sleeve_id"] for row in ledgers if row["cycle_id"] == first_cycle}
    assert len(sleeve_ids) == screen.PAIR_COUNT


def test_strict_two_standard_deviation_entry_direction_and_shifted_execution() -> None:
    signals = [row for row in read_csv("daily_pair_signals.csv") if row["signal_type"] == "pending_entry"]
    trades = [row for row in read_csv("trade_ledger.csv") if row["trade_event"] == "entry"]
    assert signals
    assert trades
    for row in signals[:50]:
        spread = float(row["spread"])
        threshold = float(row["threshold"])
        assert abs(spread) > threshold
        if spread > 0:
            assert row["long_symbol"] == row["second_ticker"]
            assert row["short_symbol"] == row["first_ticker"]
        else:
            assert row["long_symbol"] == row["first_ticker"]
            assert row["short_symbol"] == row["second_ticker"]
        assert row["same_close_execution"] == "false"
        assert pd.Timestamp(row["pending_execution_date"]) > pd.Timestamp(row["date"])
    for trade in trades[:50]:
        assert pd.Timestamp(trade["date"]) > pd.Timestamp(trade["signal_date"])


def test_exit_shift_forced_close_and_reentry_are_recorded() -> None:
    trades = read_csv("trade_ledger.csv")
    convergence = [row for row in trades if row["trade_event"] == "convergence_exit"]
    forced = [row for row in trades if row["trade_event"] == "forced_close"]
    assert convergence
    assert forced
    assert all(pd.Timestamp(row["date"]) > pd.Timestamp(row["signal_date"]) for row in convergence)
    cycles = read_csv("cycle_metrics.csv")
    assert any(int(row["reentry_count"]) > 0 for row in cycles)
    assert any(int(row["forced_close_count"]) > 0 for row in cycles)


def test_negative_share_restricted_proceeds_borrow_and_two_leg_costs() -> None:
    ledgers = read_csv("daily_sleeve_ledgers.csv")
    open_rows = [row for row in ledgers if row["open_position"] == "true"]
    assert open_rows
    assert any(float(row["short_shares"]) < 0.0 for row in open_rows)
    assert any(float(row["restricted_short_proceeds"]) > 0.0 for row in open_rows)
    aggregate = {row["metric"]: row["value"] for row in read_csv("aggregate_metrics.csv")}
    assert float(aggregate["total_borrow_cost"]) > 0.0
    assert float(aggregate["total_transaction_cost"]) > 0.0
    entries = [row for row in read_csv("trade_ledger.csv") if row["trade_event"] == "entry"]
    exits = [row for row in read_csv("trade_ledger.csv") if row["trade_event"] in {"convergence_exit", "forced_close"}]
    assert all(float(row["long_entry_cost"]) > 0.0 and float(row["short_entry_cost"]) > 0.0 for row in entries)
    assert all(float(row["long_exit_cost"]) > 0.0 and float(row["short_cover_cost"]) > 0.0 for row in exits)


def test_no_daily_rebalance_and_no_same_close_execution() -> None:
    events = {row["event"] for row in read_csv("daily_sleeve_ledgers.csv")}
    assert "rebalance" not in events
    assert "entry" in events
    assert "mark" in events
    signals = read_csv("daily_pair_signals.csv")
    assert all(row["same_close_execution"] == "false" for row in signals)


def test_insolvency_and_missing_price_helpers_invalidate_without_loss_cap_or_forward_fill() -> None:
    sleeve = screen.SleeveRuntime(
        cycle_id="synthetic",
        sleeve_id="synthetic_sleeve",
        pair_rank=1,
        first_ticker="AAA",
        second_ticker="BBB",
        threshold=0.1,
        ledger=screen.accounting.SleeveLedger("synthetic_sleeve", 100.0),
    )
    sleeve.ledger.enter("d0", "AAA", "BBB", 100.0, 100.0)
    sleeve.ledger.mark("d1", 1.0, 10000.0)
    assert screen.check_sleeve_feasible(sleeve) == "sleeve_insolvency"
    missing = screen.accounting.SleeveLedger("missing", 100.0)
    missing.enter("d0", "AAA", "BBB", 100.0, 100.0)
    missing.mark("d1", None, 100.0)
    sleeve.ledger = missing
    assert screen.check_sleeve_feasible(sleeve) == "missing_price_invalidated"


def test_benchmarks_decomposition_and_outcome_are_non_promotional() -> None:
    benchmark_rows = read_csv("benchmark_relative_metrics.csv")
    full = [row for row in benchmark_rows if row["window_id"] == "full_chained_period"]
    assert {row["benchmark_id"] for row in full} == {
        "SPY_buy_and_hold",
        "BIL_cash_proxy",
        "SPY_200d_trend_model",
        "active_combo_vm_dsr_equal_weight_v1",
    }
    decomposition = {row["component"]: float(row["amount"]) for row in read_csv("gross_vs_cost_decomposition.csv")}
    assert decomposition["gross_trading_pnl_before_borrow_and_transaction_costs"] > decomposition["net_pnl_after_all_costs"]
    outcome = read_json("screening_outcome.json")
    assert outcome["primary_outcome_label"] in screen.OUTCOME_LABELS
    assert outcome["primary_outcome_label"] == "no_material_edge"
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["robustness_authorized"] is False


def test_invalid_cycles_and_research_memory_are_visible() -> None:
    invalid = read_csv("invalid_cycles.csv")
    assert invalid == []
    memory = read_csv("exact_variant_research_memory.csv")
    assert len(memory) == 1
    assert memory[0]["candidate_id"] == screen.CANDIDATE_ID
    assert memory[0]["exact_variant_immediate_retest_status"] == "close_exact_variant_for_immediate_retesting"
    assert memory[0]["canonical_lifecycle_status_modified"] == "false"
    assert memory[0]["paper_demo_state_modified"] == "false"


def test_registry_active_observations_guardrails_and_consistency() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["registry_byte_identical"] is True
    assert outcome["registry_hash_before"] == outcome["registry_hash_after"]
    assert outcome["active_observations_unchanged"] is True
    assert outcome["active_observations_hash_before"] == outcome["active_observations_hash_after"]
    invariants = {row["invariant"]: row for row in read_csv("exposure_and_accounting_invariants.csv")}
    assert invariants["registry_byte_identical"]["passed"] == "true"
    assert invariants["active_observations_unchanged"]["passed"] == "true"
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["no_provider_calls"] is True
    assert check["no_parameter_search"] is True


def test_generation_is_deterministic() -> None:
    first_outcome = read_json("screening_outcome.json")
    first_cycles = (EVIDENCE / "cycle_definitions.csv").read_text(encoding="utf-8")
    first_selected = (EVIDENCE / "selected_pairs_by_cycle.csv").read_text(encoding="utf-8")
    rerun = screen.run()
    second_outcome = read_json("screening_outcome.json")
    second_cycles = (EVIDENCE / "cycle_definitions.csv").read_text(encoding="utf-8")
    second_selected = (EVIDENCE / "selected_pairs_by_cycle.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_outcome == first_outcome
    assert second_cycles == first_cycles
    assert second_selected == first_selected
