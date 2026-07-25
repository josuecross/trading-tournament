from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research import maio_dont_fight_fed_author_appendix_correction_v1 as impl


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
    outcome = read_json("corrected_source_rule_outcome.json")
    assert outcome["outcome"] == "author_appendix_insufficient_for_implementation"
    assert outcome["official_author_appendix_retrieved"] is True
    assert outcome["source_rules_complete"] is False
    assert outcome["next_action"] == "direction_owner_review_maio_dont_fight_fed_author_appendix_correction_v1"
    assert read_json("consistency_check.json")["consistency_passed"] is True


def test_appendix_url_originates_from_official_author_website() -> None:
    verification = read_json("official_author_source_verification.json")
    assert verification["official_author_page_url"] == impl.AUTHOR_PAGE_URL
    assert verification["appendix_view_url"] == impl.APPENDIX_VIEW_URL
    assert verification["appendix_link_found_on_author_page"] is True
    assert verification["normal_public_access_only"] is True
    assert verification["private_credentials_or_cookies_used"] is False
    assert verification["paywall_bypass_or_piracy_used"] is False


def test_downloaded_appendix_hash_is_recorded() -> None:
    appendix_hash = read_json("author_appendix_hash.json")
    assert appendix_hash["file_id"] == impl.APPENDIX_FILE_ID
    assert appendix_hash["sha256"] != "missing"
    assert len(appendix_hash["sha256"]) == 64
    assert int(appendix_hash["bytes"]) > 0
    metadata = read_json("author_appendix_file_metadata.json")
    assert metadata["page_count"] == 18
    assert metadata["file_version"] == "December 2012"


def test_every_confirmed_rule_has_appendix_page_and_section() -> None:
    rows = read_csv("appendix_rule_extraction.csv")
    confirmed = [row for row in rows if row["status"] == "confirmed_by_appendix"]
    assert confirmed
    for row in confirmed:
        assert row["appendix_page"]
        assert row["section_table_or_equation"]
    assert read_json("consistency_check.json")["every_confirmed_rule_has_appendix_page_and_section"] is True


def test_rules_merely_mentioned_are_not_marked_confirmed() -> None:
    rows = {row["field"]: row for row in read_csv("appendix_rule_extraction.csv")}
    assert rows["regression_equation"]["status"] == "referenced_but_not_defined"
    assert rows["equity_entry_condition"]["status"] == "referenced_but_not_defined"
    assert rows["risk_free_return_definition"]["status"] == "unresolved"
    assert read_json("consistency_check.json")["rules_merely_mentioned_not_marked_confirmed"] is True


def test_appendix_is_not_treated_as_the_complete_article() -> None:
    metadata = read_json("author_appendix_file_metadata.json")
    assert metadata["complete_appendix"] is True
    assert metadata["contains_main_paper_methodology_sections"] is False
    assert metadata["main_article_accessed"] is False
    spec = (EVIDENCE / "corrected_exact_source_rule_spec.yaml").read_text(encoding="utf-8")
    assert "appendix_is_complete_article: false" in spec


def test_effective_and_target_ffr_are_not_conflated() -> None:
    rows = {row["field"]: row for row in read_csv("appendix_rule_extraction.csv")}
    assert rows["effective_versus_target_rate"]["status"] == "unresolved"
    assert "not distinguished" in rows["effective_versus_target_rate"]["short_paraphrase"]
    assert read_json("consistency_check.json")["effective_and_target_ffr_not_conflated"] is True


def test_monthly_average_and_month_end_ffr_are_not_conflated() -> None:
    rows = {row["field"]: row for row in read_csv("appendix_rule_extraction.csv")}
    assert rows["monthly_average_month_end_or_daily"]["status"] == "unresolved"
    assert "monthly average" in rows["monthly_average_month_end_or_daily"]["short_paraphrase"]
    assert read_json("consistency_check.json")["monthly_average_and_month_end_ffr_not_conflated"] is True


def test_no_warmup_lag_threshold_cost_or_allocation_rule_is_invented() -> None:
    rows = {row["field"]: row for row in read_csv("appendix_rule_extraction.csv")}
    assert rows["initial_estimation_period"]["status"] == "confirmed_by_appendix"
    for field in ["lags", "forecast_restrictions", "transaction_costs", "portfolio_weights"]:
        assert rows[field]["status"] == "unresolved"
        assert rows[field]["sufficient_for_implementation"] == "false"
    assert read_json("consistency_check.json")["no_warmup_lag_threshold_cost_or_allocation_invented"] is True


def test_no_strategy_return_or_performance_metric_is_calculated() -> None:
    outcome = read_json("corrected_source_rule_outcome.json")
    assert outcome["strategy_implementation"] is False
    assert outcome["backtest_run"] is False
    assert outcome["performance_analysis"] is False
    assert outcome["parameter_search"] is False
    forbidden = {"candidate_metrics.csv", "benchmark_metrics.csv", "screening_outcomes.csv", "window_level_results.csv"}
    assert not any((EVIDENCE / name).exists() for name in forbidden)


def test_no_spy_bil_strategy_is_implemented_and_no_future_spec_created() -> None:
    future = read_json("future_baseline_spec.json")
    assert future["spec_created"] is False
    assert future["strategy_configurations"] == []
    assert future["baseline_implementation_prompt_created"] is False
    assert read_json("consistency_check.json")["no_spy_bil_strategy_implemented"] is True


def test_no_overlay_or_broker_write_endpoint_is_called() -> None:
    outcome = read_json("corrected_source_rule_outcome.json")
    assert outcome["trade_management_overlay_experiment"] is False
    assert outcome["broker_write_endpoint_called"] is False
    assert outcome["paper_demo_activation"] is False
    check = read_json("consistency_check.json")
    assert check["no_overlay_executed"] is True
    assert check["no_broker_write_endpoint_called"] is True


def test_existing_prior_evidence_files_remain_unchanged() -> None:
    rows = read_csv("prior_vs_corrected_source_inventory.csv")
    assert rows
    assert {row["prior_packet_modified"] for row in rows} == {"false"}
    assert read_json("consistency_check.json")["existing_evidence_files_unchanged"] is True


def test_outputs_are_deterministic() -> None:
    first = impl.run(ROOT)
    first_hash = read_json("consistency_check.json")["outputs_deterministic_hash"]
    second = impl.run(ROOT)
    second_hash = read_json("consistency_check.json")["outputs_deterministic_hash"]
    assert first["outcome"] == second["outcome"]
    assert first_hash == second_hash
