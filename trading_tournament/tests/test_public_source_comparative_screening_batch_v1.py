from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.public_source_comparative_screening_batch_v1 import (
    ACTIVE_COMBO_ID,
    INCLUDED_LANE_IDS,
    OUTPUT_DIR,
    SCREENING_BATCH_ID,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_screening_artifacts_exist() -> None:
    required = [
        "screening_preregistration.json",
        "screening_manifest.json",
        "screening_summary.md",
        "lane_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "comparability_review.csv",
        "weight_exposure_invariants.csv",
        "failure_patterns.csv",
        "screening_outcomes.csv",
        "artifact_lineage.csv",
        "screening_consistency_check.json",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name


def test_exact_included_lane_set_and_exclusions() -> None:
    manifest = load_json("screening_manifest.json")
    outcomes = {row["lane_id"] for row in csv_rows("screening_outcomes.csv")}

    assert manifest["batch_id"] == SCREENING_BATCH_ID
    assert tuple(manifest["included_lane_ids"]) == INCLUDED_LANE_IDS
    assert outcomes == set(INCLUDED_LANE_IDS)
    for excluded in manifest["excluded_public_source_ids"]:
        assert excluded not in outcomes
    assert manifest["excluded_unimplemented_or_duplicate_entries"] is True


def test_frozen_lineage_hashes_and_no_parameter_search() -> None:
    prereg = load_json("screening_preregistration.json")
    lineage = csv_rows("artifact_lineage.csv")

    assert prereg["internal_consistency_errors"] == []
    assert prereg["parameter_search"] is False
    assert prereg["parameter_selection_from_results"] is False
    assert prereg["new_strategy_variants_created"] is False
    assert len(lineage) == 6
    assert all(row["implementation_hash"].startswith("sha256:") for row in lineage)
    assert all(row["configuration_hash"].startswith("sha256:") for row in lineage)
    assert all(row["runner_hash"].startswith("sha256:") for row in lineage)


def test_common_scored_windows_and_benchmark_alignment() -> None:
    manifest = load_json("screening_manifest.json")
    windows = csv_rows("window_level_results.csv")
    counts: dict[str, int] = {}
    for row in windows:
        counts[row["strategy_id"]] = counts.get(row["strategy_id"], 0) + 1

    assert manifest["common_scored_start"]
    assert manifest["common_scored_end"]
    assert manifest["common_window_count"] == 10
    assert set(manifest["common_window_horizons"]) == {90, 180}
    assert all(counts[lane_id] == manifest["common_window_count"] for lane_id in INCLUDED_LANE_IDS)
    for benchmark in manifest["benchmarks"]:
        assert counts[benchmark] == manifest["common_window_count"]


def test_active_combo_is_benchmark_only_and_dsr_historical_metric_unused() -> None:
    manifest = load_json("screening_manifest.json")
    benchmarks = {row["benchmark_id"]: row for row in csv_rows("benchmark_metrics.csv")}

    assert manifest["active_combo_role"] == "benchmark_reference_only"
    assert manifest["active_combo_status"] == "benchmark_watchlist_reference"
    assert benchmarks[ACTIVE_COMBO_ID]["benchmark_role"] == "benchmark_reference_only"
    assert manifest["dsr_unverified_historical_4071_04_used"] is False
    packet_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in EVIDENCE.glob("*.*"))
    assert "4071.04" not in packet_text


def test_weight_exposure_and_cash_invariants_pass() -> None:
    manifest = load_json("screening_manifest.json")
    rows = csv_rows("weight_exposure_invariants.csv")

    assert manifest["invariant_failure_count"] == 0
    assert rows
    for row in rows:
        assert row["invariant_passed"] == "True"
        if row["max_daily_exposure"]:
            assert float(row["max_daily_exposure"]) <= 1.000001
        if row["max_daily_weight_sum"]:
            assert float(row["max_daily_weight_sum"]) <= 1.000001
        assert row["zero_weight_preservation_status"] in {
            "no_weight_sum_or_nan_violation",
            "active_combo_reconciliation_invariants",
        }
        assert row["bil_cash_fallback_status"] in {
            "replacement_or_control_cash_only",
            "active_combo_reconciliation_invariants",
        }
        assert row["signal_execution_ordering"]
        assert row["no_lookahead_status"]


def test_outcomes_are_non_promotional_and_allowed() -> None:
    outcomes = csv_rows("screening_outcomes.csv")
    failures = csv_rows("failure_patterns.csv")

    assert len(outcomes) == 6
    assert len(failures) == 6
    assert all(row["outcome_label_allowed"] == "True" for row in outcomes)
    assert all(row["promotion_eligibility"] == "False" for row in outcomes)
    assert all(row["paper_forward_eligibility"] == "False" for row in outcomes)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in outcomes)
    assert all(row["failure_pattern_allowed"] == "True" for row in failures)


def test_no_lifecycle_evidence_or_active_observation_state_changes() -> None:
    manifest = load_json("screening_manifest.json")

    assert manifest["strategy_lifecycle_statuses_changed"] is False
    assert manifest["evidence_levels_changed"] is False
    assert manifest["active_observations_changed"] is False
    assert manifest["active_combo_changed"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False


def test_consistency_check_passes_and_core_hash_is_recorded() -> None:
    manifest = load_json("screening_manifest.json")
    consistency = load_json("screening_consistency_check.json")

    assert consistency["consistency_passed"] is True
    assert consistency["included_lane_set_exact"] is True
    assert consistency["excluded_records_not_evaluated"] is True
    assert consistency["common_scored_windows_present"] is True
    assert consistency["active_combo_benchmark_only"] is True
    assert consistency["no_dsr_unverified_historical_metric"] is True
    assert manifest["deterministic_core_hash"].startswith("sha256:")
