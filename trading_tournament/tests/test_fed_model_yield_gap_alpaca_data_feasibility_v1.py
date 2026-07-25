from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from strategy_lab.research_os.research import fed_model_yield_gap_alpaca_data_feasibility_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def setup_module() -> None:
    impl.run(ROOT)


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_outputs_outcome_and_next_action_are_present() -> None:
    for name in impl.REQUIRED_OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name

    outcome = read_json("feasibility_outcome.json")
    assert outcome["outcome"] in impl.OUTCOMES
    assert outcome["candidate_strategy"] == impl.CANDIDATE_STRATEGY_ID
    assert outcome["next_action"] == "direction_owner_review_next_alpaca_first_fundamental_strategy_page_v1"

    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["next_action_exact"] is True


def test_alpaca_spy_bil_checks_are_read_only_and_order_free() -> None:
    asset_check = read_json("alpaca_spy_bil_asset_check.json")
    assert set(asset_check["assets"]) == {"SPY", "BIL"}
    assert asset_check["account"]["read_only_endpoints_only"] is True
    assert asset_check["account"]["order_endpoint_called"] is False
    assert asset_check["account"]["credential_values_persisted"] is False

    bar_rows = read_csv("alpaca_bar_coverage.csv")
    assert {row["symbol"] for row in bar_rows} == {"SPY", "BIL"}
    assert {row["timeframe"] for row in bar_rows} == {"1Day"}
    assert {row["adjustment"] for row in bar_rows} == {"all"}


def test_yield_gap_formula_uses_ordinary_earnings_yield_and_no_substitute() -> None:
    assert impl.ordinary_earnings_yield(earnings=5.0, price=100.0) == 0.05
    expected = math.log1p(0.05) - math.log1p(0.04)
    assert impl.yield_gap(price=100.0, earnings=5.0, y10_value=4.0) == expected

    identity = read_json("source_identity.json")
    schema = read_json("earnings_data_schema.json")
    assert "CAPE" in identity["not_replaced_with"]
    assert "forward_earnings" in identity["not_replaced_with"]
    assert "CAPE" in schema["field_substitution_prohibited"]
    assert "forward_earnings" in schema["field_substitution_prohibited"]


def test_ten_year_yield_percent_conversion_is_explicit() -> None:
    assert impl.convert_percent_yield_to_decimal(4.6) == 0.046
    treasury = read_json("treasury_yield_schema.json")
    assert treasury["series_id"] == "DGS10"
    assert treasury["unit_conversion"] == "decimal_yield = percent / 100"
    assert "Percent" in treasury["units"]


def test_publication_lag_and_no_lookahead_status_are_explicit() -> None:
    rows = read_csv("monthly_information_availability.csv")
    assert rows
    assert {row["publication_lag_source"] for row in rows} == {"metadata_only_not_return_selected"}
    assert {row["future_earnings_enter_earlier_row"] for row in rows} == {"unknown_not_allowed"}
    assert impl.publication_lag_source() == "metadata_only_not_return_selected"
    assert impl.no_future_earnings_enter_earlier_rows(
        [{"month_end": "2024-01-31", "earnings_available_date": "2024-01-15"}]
    )
    assert not impl.no_future_earnings_enter_earlier_rows(
        [{"month_end": "2024-01-31", "earnings_available_date": "2024-02-01"}]
    )


def test_no_alternative_lags_or_parameter_search_are_performance_tested() -> None:
    availability = read_csv("monthly_information_availability.csv")
    assert {row["alternative_lags_performance_tested"] for row in availability} == {"false"}

    consistency = read_json("consistency_check.json")
    assert consistency["no_alternative_lags_performance_tested"] is True
    assert consistency["publication_lag_metadata_not_return_selected"] is True


def test_no_strategy_returns_backtest_or_performance_metrics_are_created() -> None:
    forbidden_files = {
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "screening_outcomes.csv",
        "accounting_invariants.csv",
    }
    assert not any((EVIDENCE / name).exists() for name in forbidden_files)

    outcome = read_json("feasibility_outcome.json")
    assert outcome["strategy_backtest_run"] is False
    assert outcome["performance_screen_run"] is False
    assert outcome["strategy_return_cagr_sharpe_drawdown_calculated"] is False


def test_no_trade_management_overlay_orders_paper_demo_or_real_money_actions() -> None:
    outcome = read_json("feasibility_outcome.json")
    assert outcome["trade_management_overlay_experiment_run"] is False
    assert outcome["broker_order_placement"] is False
    assert outcome["paper_demo_activation"] is False
    assert outcome["real_money_advice"] is False

    consistency = read_json("consistency_check.json")
    assert consistency["no_trade_management_overlay_executed"] is True
    assert consistency["no_order_endpoint_called"] is True


def test_future_baseline_spec_is_created_only_for_data_ready_outcomes() -> None:
    blocked = impl.future_baseline_spec("earnings_yield_timing_unresolvable")
    assert blocked["spec_created"] is False
    assert blocked["strategy_configurations"] == []

    ready = impl.future_baseline_spec("source_aligned_data_ready")
    assert ready["spec_created"] is True
    assert len(ready["strategy_configurations"]) == 1
    assert ready["strategy_configurations"][0]["strategy_id"] == impl.CANDIDATE_STRATEGY_ID
    assert ready["strategy_configurations"][0]["performance_screen_authorized"] is False

    evidence_spec = read_json("future_baseline_spec.json")
    evidence_outcome = read_json("feasibility_outcome.json")["outcome"]
    assert bool(evidence_spec["strategy_configurations"]) == (
        evidence_outcome in {"source_aligned_data_ready", "ready_with_publication_lag_convention"}
    )


def test_source_rule_completion_preserves_recursive_model_not_direct_threshold() -> None:
    identity = read_json("source_identity.json")
    assert identity["source_rule_preserved"]["yield_gap_formula"] == "YG_t = log(1 + E_t / P_t) - log(1 + Y10_t)"
    assert identity["source_rule_preserved"]["recursive_estimation"] is True
    assert "direct_E_over_P_threshold" in identity["not_replaced_with"]

    rows = {row["item"]: row for row in read_csv("source_rule_completion.csv")}
    assert rows["log_yield_gap_formula"]["status"] == "confirmed"
    assert rows["recursive_update_rule"]["status"] == "confirmed"
    assert rows["ten_year_yield_aggregation"]["status"] == "unresolved"


def test_public_data_schema_and_market_rf_inventory_are_documented() -> None:
    shiller = read_json("earnings_data_schema.json")
    assert shiller["download_url"] == impl.SHILLER_DATA_URL
    assert shiller["fields_required_for_candidate"] == ["Date", "Price", "Earnings"]
    assert shiller["historical_investor_knowledge_at_month_end"] == "not_established"

    inventory = read_csv("market_and_rf_series_inventory.csv")
    assert {"ken_french_mkt_rf_plus_rf", "ken_french_rf", "SPY", "BIL"} == {row["series_id"] for row in inventory}
    assert {row["strategy_returns_calculated"] for row in inventory} == {"false"}


def test_registry_active_observation_and_paper_demo_state_are_preserved() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["registry_and_paper_demo_state_preserved"] is True
    assert consistency["api_credentials_not_persisted"] is True


def test_outcome_is_blocked_until_exact_feasibility_issue_is_resolved() -> None:
    outcome = read_json("feasibility_outcome.json")
    assert outcome["outcome"] in {
        "alpaca_asset_or_bar_access_blocked",
        "official_public_data_access_blocked",
        "earnings_yield_timing_unresolvable",
        "source_rule_details_incomplete",
        "insufficient_aligned_history",
        "data_reconciliation_defect",
        "source_aligned_data_ready",
        "ready_with_publication_lag_convention",
    }
    if outcome["outcome"] != "source_aligned_data_ready":
        assert read_json("future_baseline_spec.json")["spec_created"] is False
