from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import faber_composite_top3_source_rule_completion_v1 as comp
from strategy_lab.research_os.research import quantpedia_asset_class_momentum_adaptive_research_v1 as parent


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / comp.OUTPUT_DIR
PRIOR = ROOT / comp.PRIOR_DIR


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


BASELINE_HASHES_AT_IMPORT = {
    name: sha256(PRIOR / name)
    for name in comp.PRIMARY_BASELINE_FILES
}


@pytest.fixture(scope="module", autouse=True)
def generated_composite_evidence() -> dict[str, object]:
    return comp.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_existing_baseline_evidence_remains_byte_identical() -> None:
    verification = read_json("prior_baseline_hash_verification.json")
    assert verification["existing_baseline_remains_byte_identical"] is True
    for item in verification["files"]:
        assert item["byte_identical"] is True
        assert item["hash_before"] == item["hash_after"]
        assert item["hash_after"] == BASELINE_HASHES_AT_IMPORT[item["file"]]
        assert sha256(PRIOR / item["file"]) == BASELINE_HASHES_AT_IMPORT[item["file"]]


def test_source_lineage_distinguishes_four_rules() -> None:
    lineage = read_json("source_lineage_clarification.json")
    labels = {item["item"]: item["represented_by"] for item in lineage["lineage_items"]}
    assert labels["Quantpedia public 12-month ETF rule"] == comp.PARENT_ID
    assert labels["Faber 12-month historical-index result"] == "source_lineage_only"
    assert labels["Faber composite 1/3/6/9/12-month historical-index result"] == "source_lineage_only"
    assert labels["Project ETF translation of Faber composite signal"] == comp.VARIANT_ID
    assert lineage["rules_are_not_corrections_of_each_other"] is True
    assert lineage["source_reported_performance_copied_into_project_results"] is False


def test_preregistration_freezes_one_source_rule_completion_variant() -> None:
    prereg = read_json("experiment_preregistration.json")
    assert prereg["variant_id"] == comp.VARIANT_ID
    assert prereg["parent_id"] == comp.PARENT_ID
    assert prereg["adaptation_label"] == "source_rule_completion"
    assert prereg["created_before_result_calculation"] is True
    assert prereg["universe"] == ["SPY", "EFA", "BND", "VNQ", "GSG"]
    assert prereg["horizons_months"] == [1, 3, 6, 9, 12]
    assert "alternate_horizons" in prereg["prohibited_alternatives"]
    assert "parameter_search" in prereg["prohibited_alternatives"]


def test_composite_signal_specification_has_no_extra_filters_or_cash_rule() -> None:
    spec = read_json("composite_signal_specification.json")
    assert spec["horizons_months"] == [1, 3, 6, 9, 12]
    assert all(float(weight) == pytest.approx(0.2) for weight in spec["horizon_weights"].values())
    assert spec["no_absolute_momentum"] is True
    assert spec["no_moving_average_filter"] is True
    assert spec["no_cash_rule"] is True


def test_composite_momentum_is_arithmetic_mean_with_equal_horizon_weights() -> None:
    rows = read_csv("monthly_component_returns.csv")
    assert rows
    for row in rows[:20]:
        values = [float(row[f"return_{h}m"]) for h in comp.HORIZONS]
        weights = [float(row[f"horizon_{h}m_weight"]) for h in comp.HORIZONS]
        assert weights == pytest.approx([0.2] * 5)
        assert float(row["composite_momentum"]) == pytest.approx(sum(values) / 5.0)
        assert row["arithmetic_mean_verified"] == "true"


def test_universe_data_hashes_match_parent_baseline_and_no_download() -> None:
    verification = read_json("data_hash_verification.json")
    assert verification["same_verified_local_data_files_as_parent_baseline"] is True
    assert verification["provider_download"] is False
    rows = {row["symbol"]: row for row in verification["rows"]}
    assert set(rows) == set(comp.UNIVERSE)
    assert all(row["hash_match"] is True for row in rows.values())


def test_exactly_three_selected_with_one_third_and_explicit_zeros() -> None:
    rows = read_csv("monthly_target_weights.csv")
    assert rows
    for row in rows[:40]:
        weights = [float(row[symbol]) for symbol in comp.UNIVERSE]
        assert int(row["selected_count"]) == 3
        assert sum(weight > 0 for weight in weights) == 3
        assert sum(weight == pytest.approx(0.0) for weight in weights) == 2
        assert all(weight == pytest.approx(0.0) or weight == pytest.approx(1 / 3) for weight in weights)
        assert sum(weights) == pytest.approx(1.0)
        assert row["explicit_zero_targets"] == "true"


def test_signal_and_execution_timing_match_project_conventions() -> None:
    rows = read_csv("monthly_execution_dates.csv")
    assert rows
    assert all(row["signal_precedes_execution"] == "true" for row in rows)
    assert all(row["same_close_execution"] == "false" for row in rows)
    assert all(row["execution_delay_sessions"] == "1" for row in rows)
    assert all(row["signal_date"] < row["execution_date"] for row in rows)


def test_transaction_costs_match_baseline_and_static_benchmark_is_comparable() -> None:
    prereg = read_json("experiment_preregistration.json")
    full = read_json("full_sample_results.json")
    parent_spec = json.loads((PRIOR / "baseline_specification.json").read_text(encoding="utf-8"))
    assert str(parent_spec["transaction_cost"]) in prereg["costs"]
    assert full["transaction_cost_return_sum"] > 0
    assert full["benchmark_id"].endswith("__static_equal_weight_benchmark")
    assert prereg["benchmark"] == "static_equal_weight_same_five_etfs_monthly"


def test_12m_baseline_is_comparison_not_overwritten() -> None:
    comparison = read_json("comparison_with_12m_baseline.json")
    assert comparison["baseline_12m_variant_id"] == comp.PARENT_ID
    assert comparison["variant_id"] == comp.VARIANT_ID
    assert comparison["diagnostic_only_no_winner_selected"] is True
    assert "cagr_difference_vs_12m_baseline" in comparison
    assert "monthly_membership_agreement_pct" in comparison
    assert read_json("prior_baseline_hash_verification.json")["existing_baseline_remains_byte_identical"] is True


def test_signal_and_membership_agreement_is_recorded() -> None:
    rows = read_csv("signal_and_membership_agreement.csv")
    assert rows
    assert {"true", "false"} & {row["membership_agreement"] for row in rows}
    assert all("shared_selected_count" in row for row in rows)


def test_time_stability_and_cost_diagnostics_exist() -> None:
    assert read_csv("calendar_year_results.csv")
    subperiods = read_csv("subperiod_results.csv")
    rolling = read_csv("rolling_results.csv")
    relative_rolling = read_csv("baseline_relative_rolling_results.csv")
    stress = read_csv("transaction_cost_stress.csv")
    assert any(row["subperiod"].startswith("expanding_through_") for row in subperiods)
    assert {"180", "252", "756"} <= {row["window_sessions"] for row in rolling}
    assert {"180", "252", "756"} <= {row["window_sessions"] for row in relative_rolling}
    assert {"0", "5", "10", "25"} <= {row["cost_bps_per_turnover_unit"] for row in stress}


def test_baseline_targets_cannot_be_supplied_to_composite_cost_stress_generator() -> None:
    prices = parent.load_prices(comp.UNIVERSE)
    spec = comp.variant_spec()
    baseline_targets, baseline_signal_rows = parent.build_signals(spec, prices)
    composite_target_rows = read_csv("monthly_target_weights.csv")
    with pytest.raises(ValueError, match="cost stress targets do not match the composite target design"):
        comp.composite_cost_stress_rows(spec, prices, baseline_targets, baseline_signal_rows, composite_target_rows)


def test_corrected_cost_stress_uses_composite_path_and_matches_full_sample() -> None:
    full = read_json("full_sample_results.json")
    baseline = json.loads((PRIOR / "baseline_full_sample_results.json").read_text(encoding="utf-8"))
    stress = read_csv("transaction_cost_stress.csv")
    checks = comp.validate_cost_stress_rows(stress, full, baseline)
    canonical = next(row for row in stress if row["cost_bps_per_turnover_unit"] == "5")
    assert checks["transaction_cost_stress_uses_candidate_path"] is True
    assert checks["canonical_cost_row_matches_full_sample"] is True
    assert checks["canonical_cost_row_matches_parent_baseline_in_error"] is False
    assert canonical["variant_id"] == comp.VARIANT_ID
    assert canonical["source_path"] == "composite_targets_and_rankings"
    assert float(canonical["cagr"]) == pytest.approx(full["cagr"])
    assert float(canonical["total_return"]) == pytest.approx(full["total_return"])
    assert float(canonical["max_drawdown"]) == pytest.approx(full["max_drawdown"])
    assert float(canonical["transaction_cost_return_sum"]) == pytest.approx(full["transaction_cost_return_sum"])
    assert float(canonical["total_return"]) != pytest.approx(baseline["total_return"])


def test_cost_stress_cost_sums_and_monotonic_effects() -> None:
    stress = sorted(read_csv("transaction_cost_stress.csv"), key=lambda row: int(row["cost_bps_per_turnover_unit"]))
    cost_sums = [float(row["transaction_cost_return_sum"]) for row in stress]
    total_returns = [float(row["total_return"]) for row in stress]
    cagrs = [float(row["cagr"]) for row in stress]
    assert all(row["variant_id"] == comp.VARIANT_ID for row in stress)
    for row in stress:
        assert float(row["transaction_cost_return_sum"]) == pytest.approx(
            float(row["total_turnover"]) * float(row["cost_rate"]),
            abs=1e-10,
        )
    assert cost_sums == sorted(cost_sums)
    assert all(total_returns[idx] >= total_returns[idx + 1] for idx in range(len(total_returns) - 1))
    assert all(cagrs[idx] >= cagrs[idx + 1] for idx in range(len(cagrs) - 1))


def test_command_log_and_required_csv_files_are_standard_parseable() -> None:
    with (EVIDENCE / "command_validation_log.csv").open(newline="", encoding="utf-8") as handle:
        command_rows = list(csv.DictReader(handle))
    assert command_rows
    assert pd.read_csv(EVIDENCE / "command_validation_log.csv").shape[0] >= 1
    report = comp.csv_parse_report()
    assert report["all_required_csv_files_parse"] is True
    assert report["all_required_csv_files_have_expected_columns"] is True
    assert report["command_validation_log_parseable"] is True


def test_consistency_detects_contaminated_parent_baseline_cost_path() -> None:
    prices = parent.load_prices(comp.UNIVERSE)
    contaminated = parent.cost_stress_rows([comp.variant_spec()], prices)
    full = read_json("full_sample_results.json")
    baseline = json.loads((PRIOR / "baseline_full_sample_results.json").read_text(encoding="utf-8"))
    checks = comp.validate_cost_stress_rows(contaminated, full, baseline)
    consistency = read_json("consistency_check.json")
    consistency.update(checks)
    consistency["consistency_passed"] = comp.consistency_flags_pass(consistency)
    assert checks["canonical_cost_row_matches_full_sample"] is False
    assert checks["canonical_cost_row_matches_parent_baseline_in_error"] is True
    assert checks["transaction_cost_stress_uses_candidate_path"] is False
    assert consistency["consistency_passed"] is False


def test_consistency_detects_malformed_csv_artifact(tmp_path: Path) -> None:
    packet = tmp_path / "packet"
    shutil.copytree(EVIDENCE, packet)
    (packet / "command_validation_log.csv").write_text(
        "command,return_code,status,notes\n"
        ".venv\\Scripts\\python.exe run_fake.py,0,passed,note with,unquoted comma\n",
        encoding="utf-8",
    )
    report = comp.csv_parse_report(packet)
    consistency = read_json("consistency_check.json")
    consistency.update(report)
    consistency["consistency_passed"] = comp.consistency_flags_pass(consistency)
    assert report["command_validation_log_parseable"] is False
    assert report["all_required_csv_files_parse"] is False
    assert consistency["consistency_passed"] is False


def test_trial_ledgers_append_only_one_new_variant() -> None:
    exact = read_csv("exact_configuration_trial_ledger.csv")
    family = read_csv("family_trial_ledger.csv")
    exact_new = [row for row in exact if row["variant_id"] == comp.VARIANT_ID]
    family_new = [row for row in family if row["variant_id"] == comp.VARIANT_ID]
    assert len(exact_new) == 1
    assert len(family_new) == 1
    assert exact_new[0]["lookback_months"] == "composite_1_3_6_9_12"
    assert family_new[0]["changed_dimension"] == "source_rule_completion"
    assert family_new[0]["run_id"] == comp.RUN_ID


def test_no_sealed_holdout_provider_promotion_or_live_state() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["sealed_holdout_created"] is False
    assert not (EVIDENCE / "sealed_holdout_manifest.json").exists()
    assert consistency["provider_download"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["promotion"] is False
    assert consistency["broker_or_live_path"] is False
    assert consistency["registry_unchanged"] is True
    assert consistency["active_observations_unchanged"] is True


def test_methodology_and_exposure_invariants_pass() -> None:
    rows = read_csv("methodology_and_exposure_invariants.csv")
    assert rows
    assert all(row["passed"] == "true" for row in rows)
    assert all(float(row["observed"]) <= 1.000001 for row in rows if row["invariant"] in {"max_daily_exposure_lte_1", "max_daily_weight_sum_lte_1"})


def test_consistency_check_passes_and_next_action_is_exact() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["only_one_new_variant_calculated"] is True
    assert consistency["universe_exact"] is True
    assert consistency["horizons_exact"] is True
    assert consistency["transaction_cost_matches_baseline"] is True
    assert consistency["next_action"] == comp.NEXT_ACTION


def test_output_generation_is_deterministic_for_core_files() -> None:
    files = [
        "experiment_preregistration.json",
        "composite_signal_specification.json",
        "monthly_composite_scores.csv",
        "full_sample_results.json",
        "comparison_with_12m_baseline.json",
        "consistency_check.json",
    ]
    before = {name: sha256(EVIDENCE / name) for name in files}
    result = comp.run()
    after = {name: sha256(EVIDENCE / name) for name in files}
    assert result["consistency_passed"] is True
    assert before == after
