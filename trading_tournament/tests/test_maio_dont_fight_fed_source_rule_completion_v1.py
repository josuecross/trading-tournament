from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import maio_dont_fight_fed_source_rule_completion_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def setup_module() -> None:
    impl.run(ROOT)


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_outputs_outcome_and_consistency() -> None:
    for name in impl.REQUIRED_FILES:
        assert (EVIDENCE / name).exists(), name

    outcome = read_json("source_rule_outcome.json")
    assert outcome["outcome"] == "authorized_full_methodology_unavailable"
    assert outcome["source_rules_complete"] is False
    assert outcome["next_action"] == "direction_owner_review_next_observable_macro_fundamental_strategy_v1"

    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True


def test_no_strategy_returns_or_performance_metrics_are_calculated() -> None:
    outcome = read_json("source_rule_outcome.json")
    assert outcome["strategy_implementation"] is False
    assert outcome["backtest_run"] is False
    assert outcome["performance_screen_run"] is False
    assert outcome["parameter_search"] is False

    forbidden_files = {
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "screening_outcomes.csv",
    }
    assert not any((EVIDENCE / name).exists() for name in forbidden_files)


def test_no_paper_text_beyond_short_compliant_excerpts_is_copied() -> None:
    locations = read_csv("source_locations_and_citations.csv")
    assert locations
    for row in locations:
        assert row["compliant_short_excerpt"] == "true"
        assert len(row["short_excerpt_or_paraphrase"].split()) <= 24
    assert read_json("consistency_check.json")["no_paper_text_beyond_short_compliant_excerpts"] is True


def test_every_confirmed_rule_has_source_location() -> None:
    rows = read_csv("source_rule_completion.csv")
    confirmed = [row for row in rows if row["status"] == "confirmed"]
    assert confirmed
    assert all(row["source_location_id"] for row in confirmed)
    assert read_json("consistency_check.json")["every_confirmed_rule_has_source_location"] is True


def test_inferred_rules_cannot_be_marked_confirmed() -> None:
    rows = read_csv("source_rule_completion.csv")
    assert all(row["inferred"] == "false" for row in rows if row["status"] == "confirmed")
    assert impl.no_inferred_confirmed_rules(impl.source_rule_rows())
    assert read_json("consistency_check.json")["inferred_rules_cannot_be_marked_confirmed"] is True


def test_monthly_average_and_month_end_ffr_are_not_conflated() -> None:
    series = read_json("federal_funds_series_definition.json")
    assert series["monthly_average_and_month_end_not_conflated"] is True
    assert series["official_public_candidates"]["FRED_FEDFUNDS"]["definition"] == "Averages of daily figures"

    rows = {row["field"]: row for row in read_csv("source_rule_completion.csv")}
    assert rows["daily_month_end_or_monthly_average_value"]["status"] == "unresolved"


def test_effective_and_target_federal_funds_rates_are_not_conflated() -> None:
    series = read_json("federal_funds_series_definition.json")
    assert series["effective_and_target_rates_not_conflated"] is True
    assert series["source_rule_series_resolved"] is False

    rows = {row["field"]: row for row in read_csv("source_rule_completion.csv")}
    assert rows["effective_rate_vs_target_rate"]["status"] == "unresolved"


def test_publication_dates_precede_or_equal_allowed_signal_dates() -> None:
    rows = read_csv("public_data_timing_map.csv")
    dated = [row for row in rows if row["known_or_release_date"] and row["allowed_signal_date"]]
    assert dated
    for row in dated:
        assert row["known_or_release_date"] <= row["allowed_signal_date"]
    assert read_json("consistency_check.json")["publication_dates_precede_or_equal_allowed_signal_dates"] is True


def test_no_warmup_lag_threshold_or_transaction_cost_is_invented() -> None:
    rows = {row["field"]: row for row in read_csv("source_rule_completion.csv")}
    for field in [
        "number_of_lags",
        "initial_estimation_window",
        "equity_entry_condition",
        "transaction_costs",
    ]:
        assert rows[field]["status"] == "unresolved"
    assert read_json("consistency_check.json")["no_warmup_lag_threshold_or_transaction_cost_invented"] is True


def test_no_spy_bil_strategy_is_implemented() -> None:
    translation = read_csv("source_to_spy_bil_translation_map.csv")
    assert {row["translation_status"] for row in translation} == {
        "prospective_only_not_authorized",
        "separate_historical_translation_required",
    }
    controls = read_json("future_baseline_controls.json")
    assert controls["spec_created"] is False
    assert controls["controls"] == []
    assert read_json("consistency_check.json")["no_spy_bil_strategy_implemented"] is True


def test_no_overlay_or_broker_write_endpoint_is_called() -> None:
    outcome = read_json("source_rule_outcome.json")
    assert outcome["trade_management_overlay_experiment"] is False
    assert outcome["broker_write_endpoint_called"] is False
    assert outcome["paper_demo_activation"] is False
    assert read_json("consistency_check.json")["no_overlay_executed"] is True
    assert read_json("consistency_check.json")["no_broker_write_endpoint_called"] is True


def test_no_registry_or_paper_demo_state_changes_occur() -> None:
    outcome = read_json("source_rule_outcome.json")
    assert outcome["registry_or_lifecycle_state_changed"] is False
    assert outcome["real_money_advice"] is False
    assert read_json("consistency_check.json")["registry_and_paper_demo_state_preserved"] is True


def test_outputs_are_deterministic() -> None:
    first = impl.run(ROOT)
    first_hash = read_json("consistency_check.json")["outputs_deterministic_hash"]
    second = impl.run(ROOT)
    second_hash = read_json("consistency_check.json")["outputs_deterministic_hash"]
    assert first["outcome"] == second["outcome"]
    assert first_hash == second_hash
