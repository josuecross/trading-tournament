from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import quantpedia_asset_class_momentum_adaptive_research_v1 as research


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / research.OUTPUT_DIR
PRIOR_GATE = ROOT / research.PRIOR_GATE_DIR
REGISTRY = ROOT / research.REGISTRY_PATH
ACTIVE_OBSERVATIONS = ROOT / research.ACTIVE_OBSERVATIONS_PATH


@pytest.fixture(scope="module", autouse=True)
def generated_evidence() -> dict[str, object]:
    return research.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_previous_blocker_evidence_is_preserved_and_superseded_by_lineage() -> None:
    lineage = read_json("prior_gate_lineage.json")
    assert (PRIOR_GATE / "pre_implementation_gate.json").exists()
    assert (PRIOR_GATE / "blocker_report.md").exists()
    assert lineage["prior_gate_preserved"] is True
    assert lineage["prior_gate_decision"] == "source_rules_incomplete"
    assert lineage["superseded_for_implementation_authorization"] is True
    assert lineage["complete_quantpedia_library_no_longer_prerequisite"] is True
    assert lineage["page_by_page_workflow_active"] is True


def test_baseline_specification_freezes_public_page_rule() -> None:
    spec = read_json("baseline_specification.json")
    assert spec["universe"] == ["SPY", "EFA", "BND", "VNQ", "GSG"]
    assert spec["lookback_months"] == 12
    assert spec["top_n"] == 3
    assert spec["selected_weight"] == pytest.approx(1 / 3)
    assert spec["tie_handling"] == "ticker_symbol_ascending"
    assert spec["same_close_execution_allowed"] is False
    assert spec["zero_targets_preserved"] is True
    assert spec["missing_data_behavior"] == "do_not_forward_fill_or_shrink_universe"


def test_baseline_target_weights_select_three_and_preserve_explicit_zeros() -> None:
    rows = read_csv("baseline_target_weights.csv")
    assert rows
    for row in rows[:25]:
        weights = [float(row[symbol]) for symbol in research.BASELINE_UNIVERSE]
        assert sum(weight > 0 for weight in weights) == 3
        assert sum(weight == pytest.approx(0.0) for weight in weights) == 2
        assert all(weight == pytest.approx(0.0) or weight == pytest.approx(1 / 3) for weight in weights)
        assert sum(weights) == pytest.approx(1.0)


def test_zero_targets_do_not_become_stale_nonzero_allocations() -> None:
    trade_rows = read_csv("baseline_trades.csv")
    daily_rows = {row["date"]: row for row in read_csv("baseline_daily_path_and_weights.csv")}
    assert trade_rows
    checked_zero = False
    for trade in trade_rows[:40]:
        daily = daily_rows[trade["execution_date"]]
        for symbol in research.BASELINE_UNIVERSE:
            target = float(trade[f"{symbol}_target_weight"])
            post = float(daily[f"{symbol}_post_trade_weight"])
            if target == pytest.approx(0.0):
                checked_zero = True
                assert post == pytest.approx(0.0)
    assert checked_zero is True


def test_momentum_uses_adjusted_total_return_data_and_deterministic_ties() -> None:
    confidence = {row["rule"]: row for row in read_csv("source_rule_confidence.csv")}
    data = {row["symbol"]: row for row in read_csv("data_quality_report.csv")}
    assert confidence["lookback"]["value"] == "12_month_total_return"
    assert confidence["tie_handling"]["value"] == "ticker_symbol_ascending"
    assert all(data[symbol]["price_field"] == "adj_close" for symbol in research.BASELINE_UNIVERSE)
    first_rank = read_csv("baseline_rankings.csv")[0]
    assert first_rank["rank_order"].split("|") == sorted(
        first_rank["rank_order"].split("|"),
        key=lambda symbol: int(first_rank[f"{symbol}_rank"]),
    )


def test_signals_use_completed_month_end_and_execute_later() -> None:
    rows = read_csv("baseline_execution_dates.csv")
    assert rows
    assert all(row["signal_precedes_execution"] == "true" for row in rows)
    assert all(row["signal_date"] < row["execution_date"] for row in rows)
    assert all(row["signal_date"] != row["execution_date"] for row in rows)


def test_missing_prices_are_not_silently_forward_filled_or_universe_shrunk() -> None:
    spec = read_json("baseline_specification.json")
    manifest = read_json("data_acquisition_manifest.json")
    assert spec["missing_data_behavior"] == "do_not_forward_fill_or_shrink_universe"
    assert manifest["data_source"] == "existing_repository_pilot_etf_market_data_v1"
    assert set(manifest["data_symbols"]) >= set(research.BASELINE_UNIVERSE)
    assert manifest["provider_download"] is False


def test_exposure_weight_and_nan_invariants_pass() -> None:
    rows = read_csv("methodology_and_exposure_invariants.csv")
    assert rows
    assert all(row["passed"] == "true" for row in rows)
    assert all(float(row["observed"]) <= 1.000001 for row in rows if row["invariant"] in {"max_daily_exposure_lte_1", "max_daily_weight_sum_lte_1"})
    consistency = read_json("consistency_check.json")
    assert consistency["invariants_passed"] is True


def test_baseline_results_are_separate_from_adaptations() -> None:
    registry = read_csv("variant_registry.csv")
    by_id = {row["variant_id"]: row for row in registry}
    assert by_id[research.STRATEGY_ID]["variant_role"] == "source_aligned_baseline"
    adaptation_ids = {row["variant_id"] for row in registry if row["variant_role"] != "source_aligned_baseline"}
    assert adaptation_ids == {
        "qacm_top2_12m_concentration_v1",
        "qacm_top4_12m_diversification_v1",
        "qacm_dbc_commodity_translation_top3_12m_v1",
        "qacm_one_day_execution_delay_top3_12m_v1",
    }
    assert read_json("consistency_check.json")["baseline_results_separate_from_adaptations"] is True


def test_every_variant_is_planned_registered_and_ledged() -> None:
    plan = read_json("adaptation_research_plan.json")
    planned = {row["variant_id"] for row in plan["adaptations"]}
    registry = {row["variant_id"] for row in read_csv("variant_registry.csv")}
    results = {row["variant_id"] for row in read_csv("variant_results.csv")}
    family = {row["variant_id"] for row in read_csv("family_trial_ledger.csv")}
    exact = {row["variant_id"] for row in read_csv("exact_configuration_trial_ledger.csv")}
    assert planned == registry == results == family == exact
    assert plan["created_before_adaptation_results"] is True
    assert plan["large_parameter_search"] is False
    assert all(row["omitted_for_poor_performance"] == "false" for row in read_csv("exact_configuration_trial_ledger.csv"))


def test_proxy_and_etf_histories_are_distinguished_with_rationale() -> None:
    mapping = read_csv("instrument_compatibility_map.csv")
    translation = read_csv("instrument_translation_results.csv")
    assert any(row["baseline_ticker"] == "GSG" and row["compatible_adaptation"] == "DBC" for row in mapping)
    assert translation[0]["source_instrument"] == "GSG"
    assert translation[0]["translated_instrument"] == "DBC"
    assert translation[0]["performance_selected"] == "false"
    assert translation[0]["mechanism_changed"] == "false"
    portability = read_csv("portability_results.csv")
    assert portability[0]["portability_context_only"] == "true"


def test_full_available_recent_history_used_and_no_sealed_holdout_artifact() -> None:
    outcome = read_json("research_outcome.json")
    assert outcome["all_available_recent_history_used"] is True
    assert outcome["baseline_end_date"] == "2026-07-16"
    assert outcome["permanent_sealed_holdout_created"] is False
    assert not (EVIDENCE / "sealed_holdout_manifest.json").exists()
    assert not any("holdout" in path.name and "sealed" in path.name for path in EVIDENCE.iterdir())


def test_temporal_diagnostics_include_years_subperiods_rolling_and_stress() -> None:
    years = read_csv("baseline_calendar_year_results.csv")
    subperiods = read_csv("baseline_subperiod_results.csv")
    rolling = read_csv("baseline_rolling_results.csv")
    stress = read_csv("cost_and_execution_stress_results.csv")
    assert len(years) >= 10
    assert {"equal_length_partition_1", "equal_length_partition_2", "equal_length_partition_3"} <= {row["subperiod"] for row in subperiods}
    assert "recent_three_years" in {row["subperiod"] for row in subperiods}
    assert {"180", "252", "756"} <= {row["window_sessions"] for row in rolling}
    assert {"0", "5", "10", "25"} <= {row["cost_bps_per_turnover_unit"] for row in stress}


def test_transaction_costs_are_applied_consistently() -> None:
    baseline = read_json("baseline_full_sample_results.json")
    stress = [row for row in read_csv("cost_and_execution_stress_results.csv") if row["variant_id"] == research.STRATEGY_ID]
    by_cost = {int(row["cost_bps_per_turnover_unit"]): row for row in stress}
    assert baseline["transaction_cost_return_sum"] > 0
    assert float(by_cost[0]["total_return"]) >= float(by_cost[5]["total_return"]) >= float(by_cost[10]["total_return"]) >= float(by_cost[25]["total_return"])


def test_research_outcomes_are_assigned_without_promotion() -> None:
    outcome = read_json("research_outcome.json")
    assert outcome["baseline_implementation_status"] in {
        "baseline_implemented_and_verified",
        "baseline_implemented_with_documented_assumptions",
        "baseline_data_blocked",
        "baseline_source_blocked",
        "baseline_methodology_failed",
    }
    assert outcome["family_research_status"] in {
        "promising_for_deeper_research",
        "promising_defensive_or_diversifying_role",
        "mixed_family_evidence",
        "weak_family_evidence",
        "insufficient_history_or_data",
        "methodology_blocked",
    }
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_activation"] is False
    assert outcome["broker_or_live_path"] is False
    assert outcome["real_money_recommendation"] is False
    assert outcome["next_action"] == research.NEXT_ACTION


def test_registry_and_active_observations_remain_unchanged() -> None:
    consistency = read_json("consistency_check.json")
    outcome = read_json("research_outcome.json")
    assert consistency["registry_hash_before"] == sha256(REGISTRY)
    assert consistency["registry_hash_after"] == sha256(REGISTRY)
    assert consistency["active_observations_hash_before"] == sha256(ACTIVE_OBSERVATIONS)
    assert consistency["active_observations_hash_after"] == sha256(ACTIVE_OBSERVATIONS)
    assert consistency["registry_unchanged"] is True
    assert consistency["active_observations_unchanged"] is True
    assert outcome["registry_hash_before"] == outcome["registry_hash_after"]
    assert outcome["active_observations_hash_before"] == outcome["active_observations_hash_after"]


def test_consistency_check_and_guardrails() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["required_files_present"] is True
    assert consistency["sealed_holdout_manifest_created"] is False
    assert consistency["baseline_universe_exact"] is True
    assert consistency["baseline_lookback_months"] == 12
    assert consistency["baseline_top_n"] == 3
    assert consistency["all_variants_listed_in_plan_before_results"] is True
    assert consistency["paper_demo_activation"] is False
    assert consistency["broker_or_live_path"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["provider_download"] is False


def test_output_generation_is_deterministic() -> None:
    files = [
        "baseline_specification.json",
        "adaptation_research_plan.json",
        "variant_results.csv",
        "research_outcome.json",
        "consistency_check.json",
    ]
    before = {name: sha256(EVIDENCE / name) for name in files}
    result = research.run()
    after = {name: sha256(EVIDENCE / name) for name in files}
    assert result["consistency_passed"] is True
    assert before == after
