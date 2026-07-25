from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research import vojtko_dujava_inflation_acceleration_gld_ief_regime_v1 as base
from strategy_lab.research_os.research import vojtko_dujava_pit_cpi_access_recovery_and_baseline_completion_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def ensure_evidence() -> None:
    if not (EVIDENCE / "trial_manifest.json").exists():
        impl.run(ROOT)


def read_json(name: str) -> dict:
    ensure_evidence()
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    ensure_evidence()
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def synthetic_cpi(values: list[float]) -> pd.DataFrame:
    periods = pd.period_range("2020-01", periods=len(values), freq="M")
    release_dates = [(period + 1).to_timestamp() + pd.Timedelta(days=13) for period in periods]
    return pd.DataFrame(
        {
            "cpi_reference_month": [str(period) for period in periods],
            "release_date": [date.date().isoformat() for date in release_dates],
            "release_timestamp": "",
            "archived_release_url": "official_FRED_API_ALFRED_vintage_reconstruction",
            "reported_mom_percent": values,
            "extraction_method": "synthetic_test_fixture",
            "content_hash": [f"h{i}" for i in range(len(values))],
            "whether_revised_later": "test_fixture",
        }
    )


def test_prior_blocked_packet_remains_unchanged() -> None:
    result = impl.run(ROOT)
    prior = read_json("prior_packet_reconciliation.json")
    assert result["prior_packet_preserved_unchanged"] is True
    assert prior["prior_packet_preserved_unchanged"] is True
    assert prior["prior_outcome"] == "archived_bls_history_incomplete"


def test_alfred_access_uses_vintage_api_and_does_not_persist_key() -> None:
    access = read_json("fred_alfred_access_check.json")
    assert access["series_id"] == "CPIAUCSL"
    assert access["api_key_value_persisted"] is False
    assert "series_vintage_date_inventory" in access["required_capabilities"]
    assert "observations_as_of_specified_vintage" in access["required_capabilities"]
    assert "initial_release_output_for_audit" in access["required_capabilities"]
    assert access["status"] in {"ready", "blocked"}


def test_same_vintage_current_and_previous_level_contract() -> None:
    rows = read_csv("alfred_point_in_time_cpi_levels.csv")
    for row in rows:
        assert row["latest_revised_history_used"] if "latest_revised_history_used" in row else True
        assert row["same_vintage_current_and_previous"] in {"true", "false"}
        if row["query_status"] == "ready":
            assert row["earliest_vintage_date"]
            assert row["previous_month_value_from_same_vintage"]


def test_latest_revised_cpi_cannot_enter_historical_signals() -> None:
    manifest = read_json("trial_manifest.json")
    gate = read_json("point_in_time_signal_gate.json")
    assert manifest["latest_revised_cpi_used_for_signals"] is False
    assert gate["latest_revised_history_substituted"] is False


def test_every_fixed_bls_anchor_is_checked() -> None:
    inventory = read_csv("bls_anchor_release_inventory.csv")
    extraction = read_csv("bls_anchor_extraction.csv")
    assert len(inventory) == len(impl.BLS_ANCHORS)
    assert len(extraction) == len(impl.BLS_ANCHORS)
    assert {row["reference_month"] for row in inventory} == {anchor["reference_month"] for anchor in impl.BLS_ANCHORS}


def test_bls_and_alfred_reconciliation_table_is_anchor_complete() -> None:
    rows = read_csv("alfred_vs_bls_anchor_reconciliation.csv")
    assert len(rows) == len(impl.BLS_ANCHORS)
    for row in rows:
        assert row["reconciliation_status"] in {"matched", "blocked_no_alfred_data", "mismatch"}
        if row["reconciliation_status"] == "matched":
            assert row["one_decimal_value_agreement"] == "true"
            assert row["sign_agreement"] == "true"


def test_rounding_is_frozen_and_not_selected_from_investment_results() -> None:
    audit = read_json("rounding_convention_audit.json")
    assert audit["selected_rounding_rule"] == "decimal_round_half_up_one_decimal"
    assert audit["investment_results_used"] is False
    assert impl.round_one_decimal_half_up(0.25) == 0.3
    assert impl.round_one_decimal_half_up(-0.25) == -0.3


def test_three_reports_required_for_two_consecutive_changes() -> None:
    regime = base.calculate_regime_records(synthetic_cpi([0.1, 0.2]))
    assert regime["warmup_uninitialized"].all()
    assert regime["regime"].fillna("").eq("").all()


def test_zero_changes_trigger_neither_and_non_trigger_retains_previous_state() -> None:
    regime = base.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4, 0.4, 0.3]))
    assert regime.iloc[2]["regime"] == "INFLATION_UP"
    assert regime.iloc[3]["trigger_reason"] == "retain_previous_established_regime"
    assert regime.iloc[4]["trigger_reason"] == "retain_previous_established_regime"
    assert regime.iloc[4]["regime"] == "INFLATION_UP"


def test_no_position_exists_before_initialization() -> None:
    regime = base.calculate_regime_records(synthetic_cpi([0.2, 0.1]))
    prices = pd.DataFrame({"GLD": [1.0], "IEF": [1.0]}, index=pd.to_datetime(["2020-04-01"]))
    assert base.build_daily_weights(prices, regime).empty


def test_new_signals_cannot_earn_release_month_returns() -> None:
    sessions = pd.bdate_range("2020-01-01", "2020-09-30")
    regime = base.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4]), sessions)
    timing = [row for row in base.cpi_release_timing_rows(regime) if row["target_effective_date"]]
    assert timing
    assert all(row["target_month_after_release_month"] is True for row in timing)
    assert all(row["same_release_month_return_allowed"] is False for row in timing)


def test_only_gld_or_ief_is_held_when_baseline_runs() -> None:
    manifest = read_json("trial_manifest.json")
    if manifest["baseline_implemented"] is not True:
        return
    weights = pd.read_csv(EVIDENCE / "target_weights.csv")
    assert set(weights["held_asset"]) <= {"GLD", "IEF"}
    assert (((weights["GLD"] == 1.0) & (weights["IEF"] == 0.0)) | ((weights["GLD"] == 0.0) & (weights["IEF"] == 1.0))).all()


def test_no_momentum_shy_uup_or_tlt_logic_exists() -> None:
    manifest = read_json("trial_manifest.json")
    assert manifest["momentum_field_used"] is False
    assert manifest["trend_filter_used"] is False
    assert manifest["prohibited_symbols_used"] is False
    assert set(base.SYMBOLS).isdisjoint(base.PROHIBITED_SYMBOLS)


def test_costs_occur_only_on_regime_changes() -> None:
    sessions = pd.bdate_range("2020-01-01", "2020-10-31")
    regime = base.calculate_regime_records(synthetic_cpi([0.4, 0.2, -0.1, -0.2, 0.3, 0.7]), sessions)
    tx = base.transaction_rows(regime)
    assert len(tx) == 1
    assert tx[0]["source_cost_rate"] == 0.0
    assert tx[0]["cost_applied_once"] is True


def test_identity_overlay_equals_baseline_exactly_when_available() -> None:
    manifest = read_json("trial_manifest.json")
    if manifest["baseline_implemented"] is not True:
        assert read_csv("identity_overlay_equality.csv") == []
        return
    rows = read_csv("identity_overlay_equality.csv")
    assert rows
    assert all(row["exact_match"] == "true" for row in rows)


def test_no_overlay_performance_broker_write_promotion_or_paper_demo() -> None:
    ensure_evidence()
    manifest = read_json("trial_manifest.json")
    assert not any("overlay_performance" in path.name for path in EVIDENCE.iterdir())
    assert manifest["overlay_performance_experiment_run"] is False
    assert manifest["broker_order_endpoint_called"] is False
    assert manifest["promotion_eligibility"] is False
    assert manifest["paper_demo_eligibility"] is False
    assert manifest["paper_demo_activation"] is False


def test_outputs_are_deterministic_and_complete() -> None:
    first = impl.run(ROOT)
    second = impl.run(ROOT)
    check = read_json("consistency_check.json")
    assert first["outcome"] == second["outcome"]
    assert first["next_action"] == second["next_action"] == impl.NEXT_ACTION
    assert check["all_required_files_present"] is True
    assert impl.REQUIRED_FILES <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
