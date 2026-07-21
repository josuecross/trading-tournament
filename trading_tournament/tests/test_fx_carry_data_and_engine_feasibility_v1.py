from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import fx_carry_data_and_engine_feasibility_v1 as fx


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "public_source_strategy_intake" / "fx_carry_trade" / "data_and_engine_feasibility_v1" / "latest"


def read_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_generation_is_deterministic_and_guardrailed() -> None:
    fx.run()
    first = (EVIDENCE / "feasibility_outcome.json").read_text(encoding="utf-8")
    fx.run()
    second = (EVIDENCE / "feasibility_outcome.json").read_text(encoding="utf-8")
    assert first == second

    outcome = read_json("feasibility_outcome.json")
    assert outcome["strategy_id"] == fx.STRATEGY_ID
    assert outcome["family_id"] == fx.FAMILY_ID
    assert outcome["feasibility_outcome"] == "data_and_engine_work_both_required"
    assert outcome["strategy_implemented"] is False
    assert outcome["backtest_run"] is False
    assert outcome["performance_metrics_computed"] is False
    assert outcome["provider_download"] is False
    assert outcome["provider_api_called"] is False
    assert outcome["paper_demo_activation"] is False
    assert outcome["promotion"] is False
    assert outcome["broker_or_live_path_touched"] is False
    assert outcome["exact_next_action"] == fx.NEXT_ACTION


def test_required_evidence_files_exist_and_csvs_parse() -> None:
    fx.run()
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["required_files_present"] is True
    assert consistency["csv_files_parse"] is True
    for name in fx.REQUIRED_OUTPUTS:
        assert (EVIDENCE / name).exists(), name
    for name in [item for item in fx.REQUIRED_OUTPUTS if item.endswith(".csv")]:
        assert isinstance(read_csv(name), list)


def test_source_lanes_remain_distinct_and_no_monthly_variant_is_authorized() -> None:
    fx.run()
    rows = {row["lane"]: row for row in read_csv("quantpedia_vs_source_rule_map.csv")}
    assert set(rows) == {
        "quantpedia_public_monthly_policy_rate_summary",
        "deutsche_bank_quarterly_three_month_forward_methodology",
        "deutsche_bank_invesco_g10_futures_translation",
        "public_spot_plus_rate_research_proxy",
    }
    assert rows["quantpedia_public_monthly_policy_rate_summary"]["source_fidelity"] != rows[
        "deutsche_bank_quarterly_three_month_forward_methodology"
    ]["source_fidelity"]
    assert read_json("source_identity_and_lineage.json")["quantpedia_monthly_policy_rate_summary_kept_separate"] is True


def test_local_data_inventory_blocks_all_required_fx_inputs() -> None:
    fx.run()
    fx_rows = read_csv("local_fx_data_inventory.csv")
    rate_rows = read_csv("local_interest_rate_data_inventory.csv")
    futures_rows = read_csv("local_futures_and_forward_data_inventory.csv")
    assert {row["currency"] for row in fx_rows} == set(fx.CURRENCIES)
    assert {row["currency"] for row in rate_rows} == set(fx.CURRENCIES)
    assert all(row["complete_enough_for_source_exact_forward_strategy"] == "false" for row in fx_rows)
    assert all(row["complete_enough_for_source_exact_or_proxy_strategy"] == "false" for row in rate_rows)
    assert all(row["complete_enough"] == "false" for row in futures_rows)


def test_engine_capability_matrix_blocks_derivative_requirements() -> None:
    fx.run()
    rows = {row["capability"]: row for row in read_csv("engine_capability_matrix.csv")}
    for capability in [
        "derivative_notional_accounting",
        "futures_multipliers",
        "daily_futures_marking",
        "forward_or_futures_expiration_and_rolls",
        "quarterly_IMM_calendars",
        "inverse_FX_quote_conventions",
        "currency_PnL_conversion_to_USD",
    ]:
        assert rows[capability]["classification"] == "absent"
    assert rows["simultaneous_long_and_short_positions"]["classification"] == "partially_supported"
    assert rows["explicit_preservation_of_zero_positions"]["classification"] == "supported_and_tested"


def test_implementation_lanes_are_not_ready_and_sample_reconciliation_not_performed() -> None:
    fx.run()
    lanes = read_csv("implementation_lane_comparison.csv")
    assert {row["lane_decision"] for row in lanes} == {
        "blocked_data_and_engine",
        "separate_proxy_design_required_after_data_review",
    }
    assert all(row["allowed_now"] == "false" for row in lanes)
    sample = read_json("minimal_sample_reconciliation.json")
    assert sample["performed"] is False
    assert sample["equity_curve_constructed"] is False
    assert sample["performance_metrics_computed"] is False


def test_no_state_change_and_no_summary_metric_substitution() -> None:
    fx.run()
    provenance = read_json("data_hash_and_provenance_review.json")
    assert provenance["protected_state_unchanged"] is True
    assert provenance["data_modified_by_audit"] is False
    assert provenance["provider_download"] is False
    blockers = {row["blocker_id"] for row in read_csv("concrete_blockers.csv")}
    assert "missing_source_exact_forward_data" in blockers
    assert "derivative_engine_absent" in blockers
    command_rows = read_csv("command_validation_log.csv")
    assert command_rows
