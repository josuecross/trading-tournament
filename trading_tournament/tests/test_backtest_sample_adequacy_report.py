from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "backtest_sample_adequacy_report" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "backtest_sample_adequacy_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "backtest_sample_adequacy_consistency_check.json").read_text(encoding="utf-8"))


def read_rows(filename: str) -> list[dict[str, str]]:
    with (EVIDENCE / filename).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_manifest_is_audit_only_and_forbidden_actions_are_false() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["backtest_sample_adequacy_report_only"] is True
    assert manifest["new_backtests_run"] is False
    assert manifest["strategy_logic_changed"] is False
    assert manifest["new_variants_added"] is False
    assert manifest["parameters_tuned"] is False
    assert manifest["public_sources_scraped"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["paper_demo_observation_activated"] is False
    assert manifest["broker_live_paths_touched"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["fast_runtime_treated_as_quality_proof"] is False
    assert manifest["fast_runtime_treated_as_insufficient_testing_proof"] is False
    assert consistency["consistency_passed"] is True


def test_recent_public_and_project_runs_are_included() -> None:
    rows = read_rows("sample_adequacy_table.csv")
    run_ids = {row["run_id"] for row in rows}

    assert "public_source_turn_of_month_bounded_bt_run" in run_ids
    assert "public_source_percent_b_money_flow_bounded_bt_run" in run_ids
    assert "public_source_larry_connors_rsi2_bounded_bt_run" in run_ids
    assert "high_return_tactical_etf_equity_index_bounded_run" in run_ids
    assert "commodity_basket_etf_momentum_bounded_run" in run_ids
    assert "global_multi_asset_etf_momentum_bounded_run" in run_ids
    assert "regional_international_momentum_bounded_run" in run_ids
    assert "macro_gld_duration_risk_off_bounded_run" in run_ids
    assert "macro_gld_duration_risk_off_confirmation_report" in run_ids
    assert "volatility_throttle_focused_research_followup_run" in run_ids


def test_sample_classifications_and_event_counts_are_present() -> None:
    rows = read_rows("sample_adequacy_table.csv")
    event_rows = read_rows("event_signal_count_table.csv")
    classes = {row["sample_adequacy_classification"] for row in rows}

    assert rows
    assert event_rows
    assert classes <= {
        "adequate_diagnostic_sample",
        "marginal_sample",
        "too_short_or_too_sparse",
        "insufficient_event_count",
        "missing_required_evidence",
    }
    assert any(row["sample_adequacy_classification"] == "adequate_diagnostic_sample" for row in rows)
    assert all(row["calendar_years_covered"] != "" for row in rows)
    assert all(row["sample_adequacy_classification"] for row in rows)
    assert any(row["event_count_source"] != "missing" for row in event_rows)


def test_turn_of_month_calendar_events_are_counted() -> None:
    rows = read_rows("event_signal_count_table.csv")
    primary = next(
        row
        for row in rows
        if row["run_id"] == "public_source_turn_of_month_bounded_bt_run"
        and row["variant_id"] == "totm_spy_bil_primary_close_m1_to_plus3_v1"
    )

    assert primary["event_count_source"] == "robustness_event_count"
    assert int(float(primary["event_count"])) >= 100


def test_fast_runtime_explanation_and_missing_evidence_are_written() -> None:
    manifest = load_manifest()
    fast_runtime = (EVIDENCE / "fast_runtime_explanation.md").read_text(encoding="utf-8")
    missing = read_rows("missing_evidence_table.csv")

    assert "local cached daily data" in fast_runtime
    assert "absence_of_provider_download" in manifest["fast_runtime_explained_by"]
    assert len(manifest["fast_runtime_explained_by"]) >= 5
    assert missing
    assert any("missing_rolling_window_report" in row["missing_evidence_items"] for row in missing)


def test_required_files_and_next_action_exist() -> None:
    manifest = load_manifest()
    consistency = load_consistency()
    required = consistency["required_files"]

    assert manifest["next_action"] == "review_backtest_sample_adequacy_before_stronger_interpretation"
    assert all(required.values())
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
    assert (EVIDENCE / "evidence_paths_inspected.csv").exists()
    assert (EVIDENCE / "missing_evidence_table.csv").exists()
