from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import angl_static_fallen_angel_credit_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "angl_static_fallen_angel_credit_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "execution_manifest.json",
        "frozen_window_definitions.csv",
        "methodology_regime_definitions.csv",
        "candidate_metrics.csv",
        "primary_benchmark_metrics.csv",
        "context_benchmark_metrics.csv",
        "window_level_results.csv",
        "benchmark_relative_metrics.csv",
        "chronological_thirds_metrics.csv",
        "methodology_regime_metrics.csv",
        "return_risk_joint_outcomes.csv",
        "accounting_and_alignment_invariants.csv",
        "source_and_methodology_caveats.md",
        "screening_summary.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_exact_angl_and_hyg_cache_hashes_are_used() -> None:
    manifest = read_json("execution_manifest.json")
    cache_rows = {row["symbol"]: row for row in manifest["cache_preflight_rows"]}
    assert cache_rows["ANGL"]["cache_hash"] == screen.REQUIRED_ANGL_HASH
    assert cache_rows["ANGL"]["hash_match"] is True
    assert cache_rows["ANGL"]["cache_ready"] is True
    assert cache_rows["HYG"]["cache_ready"] is True
    assert cache_rows["HYG"]["cache_hash"] == file_hash(ROOT / "data" / "cache" / "HYG.csv")


def test_no_provider_call_or_refresh_occurs() -> None:
    manifest = read_json("execution_manifest.json")
    check = read_json("consistency_check.json")
    assert manifest["no_provider_call"] is True
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert check["no_provider_call_or_refresh"] is True


def test_windows_are_frozen_before_performance_and_deterministic() -> None:
    manifest = read_json("execution_manifest.json")
    windows = read_csv("frozen_window_definitions.csv")
    assert manifest["windows_generated_before_performance"] is True
    assert manifest["pre_performance_manifest_written"] is True
    assert len(windows) == 10
    assert sum(1 for row in windows if row["horizon_days"] == "90") == 5
    assert sum(1 for row in windows if row["horizon_days"] == "180") == 5
    assert {row["performance_computed_at_definition_time"] for row in windows} == {"false"}
    assert {row["selection_algorithm"] for row in windows} == {
        "deterministic_linspace_max_5_per_horizon_common_angl_hyg_period"
    }


def test_matching_angl_hyg_dates_and_actual_shares_are_used() -> None:
    windows = read_csv("window_level_results.csv")
    invariants = read_csv("accounting_and_alignment_invariants.csv")
    assert all(row["window_valid"] == "true" for row in windows)
    assert all(row["matching_angl_hyg_dates_used"] == "true" for row in windows)
    assert all(row["actual_etf_shares_held"] == "true" for row in windows)
    assert all(row["entry_trade_count"] == "1" for row in windows)
    assert all(row["measurement_exit_count"] == "1" for row in windows)
    assert {row["invariant_passed"] for row in invariants} == {"true"}


def test_identical_transaction_cost_and_adjusted_close_handling() -> None:
    manifest = read_json("execution_manifest.json")
    candidate = read_csv("candidate_metrics.csv")
    benchmark = read_csv("primary_benchmark_metrics.csv")
    context = read_csv("context_benchmark_metrics.csv")
    assert manifest["transaction_cost_convention"]["standard_slippage_pct_per_side"] == pytest.approx(0.0005)
    assert set(manifest["transaction_cost_convention"]["identical_treatment_for"]) == {"ANGL", "HYG", "BIL", "IEF"}
    assert all(row["entry_cost_dollars"] in {"", "1.5"} or float(row["entry_cost_dollars"]) >= 0 for row in candidate + benchmark + context)
    assert all(row["actual_shares_held_constant"] in {"", "true"} for row in candidate + benchmark + context)


def test_three_methodology_regimes_are_represented_correctly() -> None:
    definitions = {row["period_id"]: row for row in read_csv("methodology_regime_definitions.csv")}
    metrics = {row["period_id"]: row for row in read_csv("methodology_regime_metrics.csv")}
    assert set(definitions) == {
        "methodology_regime_1_prior_benchmark_methodology",
        "methodology_regime_2_initial_h0cf_methodology",
        "methodology_regime_3_amended_h0cf_methodology",
    }
    assert definitions["methodology_regime_1_prior_benchmark_methodology"]["start_date"] == "2012-04-11"
    assert definitions["methodology_regime_2_initial_h0cf_methodology"]["start_date"] == "2020-02-28"
    assert definitions["methodology_regime_3_amended_h0cf_methodology"]["start_date"] == "2024-01-02"
    assert metrics["methodology_regime_1_prior_benchmark_methodology"]["evidence_weight"] == "hard_evidence_eligible"
    assert metrics["methodology_regime_2_initial_h0cf_methodology"]["evidence_weight"] == "hard_evidence_eligible"


def test_post_2023_regime_is_descriptive_only_and_not_decisive() -> None:
    metrics = {row["period_id"]: row for row in read_csv("methodology_regime_metrics.csv")}
    post = metrics["methodology_regime_3_amended_h0cf_methodology"]
    assert post["post_2023_short_sample_caveat"] == "true"
    if int(post["trading_day_count"]) < screen.HARD_REGIME_MIN_SESSIONS:
        assert post["evidence_weight"] == "descriptive_only"
        assert post["descriptive_only_cannot_pass_or_fail"] == "true"
    else:
        assert post["evidence_weight"] == "hard_evidence_eligible"
        assert post["descriptive_only_cannot_pass_or_fail"] == "false"
    check = read_json("consistency_check.json")
    assert check["post_2023_descriptive_only_when_below_504"] is True
    assert check["descriptive_only_cannot_independently_pass_or_fail"] is True


def test_hyg_remains_primary_and_context_cannot_determine_outcome() -> None:
    outcome = read_json("screening_outcome.json")
    relatives = read_csv("benchmark_relative_metrics.csv")
    assert outcome["primary_benchmark"] == "HYG"
    assert outcome["primary_outcome"] in screen.ALLOWED_OUTCOMES
    assert all(row["benchmark_role"] == "primary_decision_benchmark" for row in relatives if row["benchmark_symbol"] == "HYG")
    assert all(row["benchmark_role"] == "context_only" for row in relatives if row["benchmark_symbol"] in {"BIL", "IEF"})
    assert all(row["can_determine_primary_outcome"] == "false" for row in relatives if row["benchmark_symbol"] in {"BIL", "IEF"})


def test_no_filters_alternative_wrapper_or_window_search() -> None:
    manifest = read_json("execution_manifest.json")
    check = read_json("consistency_check.json")
    assert manifest["no_parameter_wrapper_benchmark_or_window_selection_authorized"] is True
    assert manifest["no_alternative_wrapper"] is True
    assert manifest["no_timing_trend_rate_duration_spread_bil_or_downgrade_filter"] is True
    assert check["no_timing_trend_rate_duration_bil_or_downgrade_filter"] is True
    assert check["no_alternative_wrapper_or_window_search"] is True


def test_registry_active_observations_and_discovery_pause_remain_unchanged() -> None:
    check = read_json("consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_unchanged"] is True
    assert check["external_discovery_pause_remains_active"] is True


def test_no_promotion_paper_demo_or_lifecycle_change() -> None:
    outcome = read_json("screening_outcome.json")
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["validation_authorized"] is False
    assert memory["lifecycle_status_changed"] == "false"
    assert memory["paper_demo_authorized"] == "false"
    assert memory["promotion_authorized"] == "false"


def test_generation_is_deterministic() -> None:
    first_outcome = read_json("screening_outcome.json")
    first_manifest = read_json("execution_manifest.json")
    first_windows = (EVIDENCE / "frozen_window_definitions.csv").read_text(encoding="utf-8")
    first_metrics = (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8")
    result = screen.run()
    assert result["consistency_passed"] is True
    assert read_json("screening_outcome.json") == first_outcome
    assert read_json("execution_manifest.json") == first_manifest
    assert (EVIDENCE / "frozen_window_definitions.csv").read_text(encoding="utf-8") == first_windows
    assert (EVIDENCE / "candidate_metrics.csv").read_text(encoding="utf-8") == first_metrics


def test_consistency_check_passes() -> None:
    check = read_json("consistency_check.json")
    assert check["consistency_passed"] is True
