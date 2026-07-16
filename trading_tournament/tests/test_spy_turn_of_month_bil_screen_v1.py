from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from strategy_lab.research_os.research import spy_turn_of_month_bil_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spy_turn_of_month_bil_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen_evidence() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_exist() -> None:
    required = {
        "source_intake_record.yaml",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "duplicate_gate.csv",
        "material_distinction_review.csv",
        "cache_feasibility.csv",
        "preregistration.yaml",
        "execution_manifest.json",
        "event_schedule.csv",
        "event_level_results.csv",
        "daily_strategy_path.csv",
        "calendar_year_metrics.csv",
        "chronological_thirds_metrics.csv",
        "inside_vs_outside_return_diagnostic.csv",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "accounting_invariants.csv",
        "screening_summary.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_source_and_instruments_are_exactly_as_supplied() -> None:
    intake = read_yaml("source_intake_record.yaml")
    manifest = read_json("execution_manifest.json")
    assert intake["source"]["source_id"] == screen.SOURCE_ID
    assert intake["source"]["source_class"] == "academic_primary"
    assert intake["project_candidate"]["candidate_id"] == screen.CANDIDATE_ID
    assert intake["project_candidate"]["risk_asset"] == "SPY"
    assert intake["project_candidate"]["outside_asset"] == "BIL"
    assert manifest["uses_only_spy_and_bil"] is True
    assert manifest["risk_asset"] == "SPY"
    assert manifest["outside_asset"] == "BIL"
    assert manifest["instrument_count"] == 2


def test_calendar_schedule_identifies_day_minus2_minus1_and_plus_days() -> None:
    dates = pd.to_datetime(
        [
            "2023-12-27",
            "2023-12-28",
            "2023-12-29",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-30",
            "2024-01-31",
            "2024-02-01",
            "2024-02-02",
            "2024-02-05",
        ]
    )
    rows = screen.generate_event_schedule(pd.DatetimeIndex(dates))
    assert rows[0]["day_minus_2"] == "2023-12-28"
    assert rows[0]["day_minus_1"] == "2023-12-29"
    assert rows[0]["day_plus_1"] == "2024-01-02"
    assert rows[0]["day_plus_2"] == "2024-01-03"
    assert rows[0]["day_plus_3"] == "2024-01-04"
    assert rows[0]["entry_close_date"] == "2023-12-28"
    assert rows[0]["exit_close_date"] == "2024-01-04"
    assert rows[1]["day_plus_3"] == "2024-02-05"


def test_entry_exit_and_exact_four_spy_return_days() -> None:
    dates = pd.to_datetime(
        [
            "2023-12-27",
            "2023-12-28",
            "2023-12-29",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
        ]
    )
    prices = pd.DataFrame({"SPY": [100, 101, 102, 103, 104, 105, 106], "BIL": [100] * 7}, index=dates)
    events = screen.generate_event_schedule(pd.DatetimeIndex(dates))
    path, completed, _stats = screen.simulate_strategy(prices, events, slippage=screen.active.SLIPPAGE)
    by_date = {row["date"]: row for row in path.to_dict("records")}
    assert by_date["2023-12-28"]["trade_action"] == "entry_sell_bil_buy_spy"
    assert by_date["2024-01-04"]["trade_action"] == "exit_sell_spy_buy_bil"
    assert [by_date[d]["return_asset"] for d in ["2023-12-29", "2024-01-02", "2024-01-03", "2024-01-04"]] == ["SPY"] * 4
    assert by_date["2023-12-27"]["return_asset"] == "BIL"
    assert by_date["2024-01-05"]["return_asset"] == "BIL"
    assert completed[0]["event_id"] == events[0]["event_id"]


def test_actual_shares_costs_and_no_intervening_trades() -> None:
    path = read_csv("daily_strategy_path.csv")
    events = read_csv("event_schedule.csv")
    trades = [row for row in path if row["trade_action"] != "none"]
    scheduled = {row["entry_close_date"] for row in events} | {row["exit_close_date"] for row in events}
    assert {row["date"] for row in trades} == scheduled
    assert len(trades) == len(events) * 2
    assert all(float(row["trade_cost_dollars"]) > 0.0 for row in trades)
    assert any(float(row["SPY_shares"]) > 0.0 and float(row["BIL_shares"]) == 0.0 for row in path)
    assert any(float(row["BIL_shares"]) > 0.0 and float(row["SPY_shares"]) == 0.0 for row in path)


def test_no_price_dependent_signal_and_no_calendar_window_search() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    assert manifest["no_price_dependent_signal"] is True
    assert manifest["no_trend_filter"] is True
    assert manifest["no_momentum_or_mean_reversion_filter"] is True
    assert manifest["no_volatility_target"] is True
    assert manifest["no_ranking"] is True
    assert manifest["no_calendar_window_search"] is True
    assert prereg["calendar_window_variation_prohibited"] is True


def test_full_event_schedule_is_frozen_before_performance() -> None:
    manifest = read_json("execution_manifest.json")
    prereg = read_yaml("preregistration.yaml")
    rows = read_csv("event_schedule.csv")
    candidate = read_csv("candidate_metrics.csv")[0]
    assert manifest["event_schedule_generated_before_performance"] is True
    assert prereg["event_schedule_generated_before_performance"] is True
    assert len(rows) == int(candidate["complete_event_count"])
    assert all(row["generated_before_performance"] == "true" for row in rows)
    assert all(row["event_valid"] == "true" for row in rows)


def test_no_missing_price_forward_fill_and_no_duplicate_overlap() -> None:
    check = read_json("consistency_check.json")
    invariants = read_csv("accounting_invariants.csv")[0]
    assert check["no_missing_price_forward_fill"] is True
    assert check["no_overlapping_or_duplicate_trade_event"] is True
    assert invariants["no_forward_filled_missing_prices"] == "true"
    assert invariants["no_overlapping_or_duplicate_trade_event"] == "true"
    assert invariants["no_trade_between_scheduled_boundaries"] == "true"


def test_path_final_equity_matches_candidate_metric_product() -> None:
    path = read_csv("daily_strategy_path.csv")
    candidate = read_csv("candidate_metrics.csv")[0]
    assert float(path[-1]["equity"]) == pytest.approx(float(candidate["final_equity"]), rel=0, abs=1e-6)


def test_cache_no_provider_and_registry_active_observations_unchanged() -> None:
    outcome = read_json("screening_outcome.json")
    check = read_json("consistency_check.json")
    cache = read_csv("cache_feasibility.csv")
    assert {row["symbol"] for row in cache} == {"SPY", "BIL", "COMMON_SPY_BIL"}
    assert all(row["cache_status"] == "cache_ready" for row in cache)
    assert all(row["provider_download_required"] == "false" for row in cache)
    assert check["no_provider_calls"] is True
    assert outcome["provider_download"] is False
    assert outcome["intraday_data_used"] is False
    assert outcome["registry_byte_identical"] is True
    assert outcome["registry_hash_before"] == outcome["registry_hash_after"]
    assert outcome["active_observations_unchanged"] is True
    assert outcome["active_observations_hash_before"] == outcome["active_observations_hash_after"]


def test_duplicate_and_material_distinction_gates() -> None:
    duplicate_rows = read_csv("duplicate_gate.csv")
    material_rows = read_csv("material_distinction_review.csv")
    assert any(row["duplicate_gate_outcome"] == "prior_test_methodologically_superseded" for row in duplicate_rows)
    assert screen.exact_duplicate_exists(screen.duplicate_gate_rows()) is False
    assert all(row["material_distinction_outcome"] == "materially_distinct_turn_of_month_calendar_effect" for row in material_rows)


def test_outcome_memory_and_no_lifecycle_changes() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["outcome"] == "calendar_effect_present_but_no_strategy_edge"
    assert outcome["next_action"] == "record_spy_turn_of_month_bil_v1_exact_variant_memory_only"
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["robustness_authorized"] is False
    assert memory["canonical_lifecycle_status_modified"] == "false"
    assert memory["automatic_calendar_variation_followup_authorized"] == "false"


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["exactly_one_external_source_evaluated"] is True
    assert check["uses_only_spy_and_bil"] is True
    assert check["actual_shares_held"] is True
    assert check["costs_apply_to_both_switch_legs"] is True
    assert check["event_schedule_frozen_before_performance"] is True
    assert check["deterministic_generation_no_timestamps"] is True


def test_generation_is_deterministic() -> None:
    first_outcome = read_json("screening_outcome.json")
    first_candidate = (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8")
    first_schedule = (EVIDENCE / "event_schedule.csv").read_text(encoding="utf-8")
    rerun = screen.run()
    second_outcome = read_json("screening_outcome.json")
    second_candidate = (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8")
    second_schedule = (EVIDENCE / "event_schedule.csv").read_text(encoding="utf-8")
    assert rerun["consistency_passed"] is True
    assert second_outcome == first_outcome
    assert second_candidate == first_candidate
    assert second_schedule == first_schedule
