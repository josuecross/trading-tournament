from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research.risk_parity_trend_wrapper_resolution_v1 import (
    AUTHORIZED_DOWNLOAD_SYMBOLS,
    CANDIDATE_ID,
    FAMILY_ID,
    FIXED_UNIVERSE,
    SOURCE_ID,
    TREND_WINDOW_MONTHS,
    VOLATILITY_WINDOW_MONTHS,
    run,
    validate_authorized_download_symbol,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "risk_parity_trend_wrapper_resolution_v1" / "latest"
INTAKE = (
    ROOT
    / "strategy_lab"
    / "research_os"
    / "public_strategy_sources"
    / "intake_candidates"
    / f"{SOURCE_ID}.yaml"
)


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def setup_module() -> None:
    run()


def test_required_artifacts_and_preregistration_exist_when_ready() -> None:
    for name in {
        "decision.json",
        "decision.md",
        "approved_wrapper_mapping.csv",
        "wrapper_source_differences.csv",
        "provider_acquisition_manifest.json",
        "cache_feasibility.csv",
        "common_history_review.csv",
        "deterministic_window_preview.csv",
        "material_distinction_confirmation.csv",
        "preregistration.yaml",
        "preregistration.md",
        "consistency_check.json",
    }:
        assert (EVIDENCE / name).exists(), name
    decision = _json("decision.json")
    assert decision["outcome"] == "preregistration_ready"
    assert decision["candidate_id"] == CANDIDATE_ID
    assert decision["family"] == FAMILY_ID


def test_only_urth_igov_reet_may_be_downloaded_and_other_ticker_requests_fail() -> None:
    assert tuple(AUTHORIZED_DOWNLOAD_SYMBOLS) == ("URTH", "IGOV", "REET")
    for symbol in AUTHORIZED_DOWNLOAD_SYMBOLS:
        assert validate_authorized_download_symbol(symbol) == symbol
    for symbol in ["EEM", "DBC", "BIL", "SPY", "GLD", "TLT", "GOVT", "VNQ", "XLRE"]:
        with pytest.raises(ValueError):
            validate_authorized_download_symbol(symbol)


def test_provider_acquisition_manifest_records_all_three_authorized_series() -> None:
    manifest = _json("provider_acquisition_manifest.json")
    assert manifest["authorized_download_symbols"] == ["URTH", "IGOV", "REET"]
    assert set(manifest["authorized_acquisition_series_recorded"]) == {"URTH", "IGOV", "REET"}
    series = {row["provider_symbol"]: row for row in manifest["series"]}
    assert set(series) == {"URTH", "IGOV", "REET"}
    for symbol, row in series.items():
        assert row["row_count"] > 1000
        assert row["raw_close_available"] is True
        assert row["adjusted_close_available"] is True
        assert row["missing_value_count"] == 0
        assert row["duplicate_date_count"] == 0
        assert row["non_positive_price_count"] == 0
        assert row["data_hash"]
        assert row["cache_destination"] == f"data/cache/{symbol}.csv"
        assert row["deterministic_after_cached"] is True


def test_urth_igov_reet_resolve_to_intended_instruments() -> None:
    series = {row["provider_symbol"]: row for row in _json("provider_acquisition_manifest.json")["series"]}
    assert series["URTH"]["intended_instrument_resolved"] is True
    assert "iShares MSCI World ETF" in series["URTH"]["long_name"]
    assert series["IGOV"]["intended_instrument_resolved"] is True
    assert "iShares International Treasury Bond ETF" in series["IGOV"]["long_name"]
    assert series["REET"]["intended_instrument_resolved"] is True
    assert "iShares Global REIT ETF" in series["REET"]["long_name"]
    assert {series[s]["currency"] for s in series} == {"USD"}


def test_igov_deviation_and_not_replication_language_remain_explicit() -> None:
    mapping = {row["local_ticker"]: row for row in _csv("approved_wrapper_mapping.csv")}
    assert mapping["IGOV"]["mapping_status"] == "role-preserving ETF-wrapper adaptation"
    assert "excludes US government bonds" in mapping["IGOV"]["known_difference_or_caveat"]
    assert mapping["URTH"]["adaptation_classification"] == "source_inspired_etf_wrapper_adaptation"
    assert mapping["DBC"]["known_difference_or_caveat"].lower().find("gld") >= 0
    differences = "\n".join(row["required_wording"] for row in _csv("wrapper_source_differences.csv"))
    assert "not_source_index_replication" in differences
    assert "known_mapping_difference" in differences


def test_no_wrapper_optimization_or_substitution_occurs() -> None:
    mapping = _csv("approved_wrapper_mapping.csv")
    assert [row["local_ticker"] for row in mapping] == list(FIXED_UNIVERSE)
    assert "EFA" not in [row["local_ticker"] for row in mapping]
    assert "AGG" not in [row["local_ticker"] for row in mapping]
    assert "TLT" not in [row["local_ticker"] for row in mapping]
    assert "XLRE" not in [row["local_ticker"] for row in mapping]
    decision = _json("decision.json")
    assert decision["no_wrapper_search"] is True
    assert decision["no_parameter_search"] is True


def test_common_history_start_is_mechanical_and_warmup_is_enforced() -> None:
    review = _csv("common_history_review.csv")[0]
    assert review["common_start"] == "2014-07-10"
    assert review["warmup_months"] == "12"
    assert review["warmup_eligible_start"] >= "2015-07-10"
    assert int(review["eligible_trading_days"]) > 1000
    assert review["normal_screening_protocol_feasible"] == "true"


def test_sample_windows_are_selected_deterministically_without_performance() -> None:
    windows = _csv("deterministic_window_preview.csv")
    assert len(windows) == 10
    assert sum(1 for row in windows if row["horizon_days"] == "90") == 5
    assert sum(1 for row in windows if row["horizon_days"] == "180") == 5
    assert {row["selection_algorithm"] for row in windows} == {
        "run_active_strategy_evidence_recompute.sample_starts_equivalent"
    }
    assert {row["performance_computed"] for row in windows} == {"false"}


def test_preregistration_freezes_parameters_bil_transfer_and_benchmarks() -> None:
    prereg = yaml.safe_load((EVIDENCE / "preregistration.yaml").read_text(encoding="utf-8"))
    assert prereg["candidate_id"] == CANDIDATE_ID
    assert prereg["adaptation_classification"] == "source_inspired_etf_wrapper_adaptation"
    assert prereg["source_replication_status"] == "not_source_index_replication"
    assert prereg["volatility_calculation"]["window_months"] == VOLATILITY_WINDOW_MONTHS
    assert prereg["trend_rule"]["window_months"] == TREND_WINDOW_MONTHS
    assert prereg["trend_rule"]["risk_off"].endswith("to BIL when below trend")
    assert prereg["trend_rule"]["redistribution_to_remaining_risky_assets"] is False
    assert prereg["maximum_exposure"] == 1.0
    assert prereg["leverage"] is False
    assert prereg["shorting"] is False
    assert "active_combo_vm_dsr_equal_weight_v1_benchmark_reference_only" in prereg["benchmarks"]
    assert prereg["forbidden_search"]["parameter_search"] is False
    assert prereg["forbidden_search"]["wrapper_search"] is False
    assert prereg["screening_protocol"]["performance_computation_authorized_by_this_packet"] is False


def test_material_distinction_confirmed_without_reopening_prior_variants() -> None:
    row = _csv("material_distinction_confirmation.csv")[0]
    assert row["material_distinction_result"] == "materially_distinct_source_inspired_etf_wrapper_adaptation"
    assert row["ticker_changes_are_source_of_distinction"] == "false"
    assert row["exact_prior_variant_reopened"] == "false"
    assert "inverse-volatility" in row["distinct_mechanism"]
    assert "transfer of each failed asset" in row["distinct_mechanism"]


def test_source_intake_record_is_updated_without_state_change() -> None:
    intake = yaml.safe_load(INTAKE.read_text(encoding="utf-8"))
    mapping = intake["approved_wrapper_mapping"]
    assert mapping["candidate_id"] == CANDIDATE_ID
    assert mapping["fixed_universe"] == list(FIXED_UNIVERSE)
    assert mapping["source_replication_status"] == "not_source_index_replication"
    assert mapping["provider_download_authorized_symbols"] == ["URTH", "IGOV", "REET"]
    assert mapping["provider_download_forbidden_for_all_other_symbols"] is True
    assert intake["governance"]["strategy_implemented"] is False
    assert intake["governance"]["backtest_run"] is False
    assert intake["governance"]["promotion_or_paper_forward_allowed"] is False


def test_no_backtest_performance_lifecycle_or_paper_demo_change() -> None:
    decision = _json("decision.json")
    assert decision["no_backtest_run"] is True
    assert decision["no_candidate_performance_computed"] is True
    assert decision["no_lifecycle_or_paper_demo_state_change"] is True
    assert decision["candidate_exhaustive_run"] is False
    assert decision["promotion_or_paper_demo_activation"] is False
    assert decision["intraday_data_used"] is False


def test_generation_is_deterministic_and_consistency_passes() -> None:
    first = run()
    second = run()
    assert first["outcome"] == second["outcome"]
    assert first["available_90_day_windows"] == second["available_90_day_windows"]
    assert first["available_180_day_windows"] == second["available_180_day_windows"]
    check = _json("consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["only_urth_igov_reet_may_be_downloaded"] is True
    assert check["all_other_ticker_requests_fail"] is True
    assert check["sample_windows_selected_deterministically"] is True
    assert check["no_performance_backtest_runs"] is True
    assert check["no_lifecycle_evidence_level_active_observation_or_paper_demo_changes"] is True
