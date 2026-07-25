from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research import vojtko_dujava_inflation_acceleration_gld_ief_regime_v1 as impl


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
            "archived_release_url": [f"https://www.bls.gov/news.release/archives/cpi_{date.strftime('%m%d%Y')}.htm" for date in release_dates],
            "reported_mom_percent": values,
            "extraction_method": "synthetic_test_fixture",
            "content_hash": [f"h{i}" for i in range(len(values))],
            "whether_revised_later": "test_fixture",
        }
    )


def test_three_reports_required_before_two_consecutive_changes_are_evaluated() -> None:
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2]))
    assert len(regime) == 2
    assert regime["warmup_uninitialized"].all()
    assert regime["regime"].fillna("").eq("").all()


def test_two_positive_changes_trigger_inflation_up() -> None:
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4]))
    third = regime.iloc[2]
    assert third["trigger_reason"] == "two_positive_accelerations"
    assert third["regime"] == "INFLATION_UP"
    assert float(third["GLD"]) == 1.0
    assert float(third["IEF"]) == 0.0


def test_two_negative_changes_trigger_inflation_down() -> None:
    regime = impl.calculate_regime_records(synthetic_cpi([0.4, 0.2, -0.1]))
    third = regime.iloc[2]
    assert third["trigger_reason"] == "two_negative_accelerations"
    assert third["regime"] == "INFLATION_DOWN"
    assert float(third["GLD"]) == 0.0
    assert float(third["IEF"]) == 1.0


def test_zero_changes_trigger_neither_regime_and_existing_regime_is_retained() -> None:
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4, 0.4, 0.3]))
    assert regime.iloc[2]["regime"] == "INFLATION_UP"
    assert regime.iloc[3]["trigger_reason"] == "retain_previous_established_regime"
    assert regime.iloc[3]["regime"] == "INFLATION_UP"
    assert regime.iloc[4]["trigger_reason"] == "retain_previous_established_regime"
    assert regime.iloc[4]["regime"] == "INFLATION_UP"


def test_no_position_exists_before_first_confirmed_regime() -> None:
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2]))
    weights = impl.build_daily_weights(
        pd.DataFrame({"GLD": [1.0], "IEF": [1.0]}, index=pd.to_datetime(["2020-04-01"])),
        regime,
    )
    assert weights.empty


def test_release_dates_precede_permitted_target_dates_and_no_release_month_return() -> None:
    sessions = pd.bdate_range("2020-01-01", "2020-08-31")
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4]), sessions)
    timing = impl.cpi_release_timing_rows(regime)
    target_row = [row for row in timing if row["target_effective_date"]][0]
    assert target_row["release_date_before_target_effective"] is True
    assert target_row["target_month_after_release_month"] is True
    assert target_row["same_release_month_return_allowed"] is False


def test_revised_cpi_values_cannot_replace_archived_reported_values() -> None:
    evidence_config = impl.frozen_test_config(False)
    assert evidence_config["cpi_source"] == "archived_BLS_CPI_news_releases_first_release_values"
    assert evidence_config["alternative_inflation_series_used"] is False
    assert impl.SOURCE_PACKET["point_in_time_cpi_source"]["latest_revised_cpiaucsl_signal_use"] is False


def test_targets_are_always_exactly_gld_or_ief_after_initialization() -> None:
    sessions = pd.bdate_range("2020-01-01", "2020-12-31")
    prices = pd.DataFrame({"GLD": 100.0, "IEF": 100.0}, index=sessions)
    regime = impl.calculate_regime_records(synthetic_cpi([0.1, 0.2, 0.4, 0.4, 0.1]), sessions)
    weights = impl.build_daily_weights(prices, regime)
    assert not weights.empty
    valid = ((weights["GLD"] == 1.0) & (weights["IEF"] == 0.0)) | ((weights["GLD"] == 0.0) & (weights["IEF"] == 1.0))
    assert valid.all()
    assert (weights.sum(axis=1) == 1.0).all()


def test_no_momentum_trend_shy_uup_or_tlt_fields_are_used() -> None:
    config = impl.frozen_test_config(False)
    assert config["momentum_field_used"] is False
    assert config["trend_filter_used"] is False
    assert set(config["excluded_symbols"]) == {"SHY", "TLT", "UUP"}
    assert set(impl.SYMBOLS).isdisjoint(impl.PROHIBITED_SYMBOLS)


def test_costs_apply_only_when_regime_changes() -> None:
    sessions = pd.bdate_range("2020-01-01", "2020-10-31")
    regime = impl.calculate_regime_records(synthetic_cpi([0.4, 0.2, -0.1, -0.2, 0.3, 0.7]), sessions)
    tx = impl.transaction_rows(regime)
    assert len(tx) == 1
    assert tx[0]["from_regime"] == "INFLATION_DOWN"
    assert tx[0]["to_regime"] == "INFLATION_UP"
    assert tx[0]["source_cost_rate"] == 0.0
    assert tx[0]["cost_applied_once"] is True


def test_identity_overlay_equals_base_exactly() -> None:
    index = pd.bdate_range("2020-01-01", periods=3)
    weights = pd.DataFrame({"GLD": [1.0, 1.0, 0.0], "IEF": [0.0, 0.0, 1.0]}, index=index)
    returns = pd.Series([0.0, 0.01, -0.002], index=index)
    tx = [{"target_effective_date": "2020-01-03"}]
    metrics = {"total_return": 0.008}
    rows = impl.identity_overlay_equality_rows(weights, returns, tx, metrics)
    assert all(row["exact_match"] is True for row in rows)


def test_output_packet_is_deterministic_and_guardrailed() -> None:
    first = impl.run(ROOT)
    first_check = read_json("consistency_check.json")
    second = impl.run(ROOT)
    second_check = read_json("consistency_check.json")
    assert first["outcome"] == second["outcome"]
    assert first["next_action"] == second["next_action"] == impl.NEXT_ACTION
    assert first_check["all_required_files_present"] is True
    assert second_check["all_required_files_present"] is True
    assert second_check["no_overlay_performance_output"] is True


def test_manifest_blocks_promotion_paper_demo_broker_write_and_registry_changes() -> None:
    manifest = read_json("trial_manifest.json")
    assert manifest["outcome"] in impl.ALLOWED_OUTCOMES
    assert manifest["promotion_eligibility"] is False
    assert manifest["paper_demo_eligibility"] is False
    assert manifest["paper_demo_activation"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["broker_order_endpoint_called"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["registry_state_changed"] is False


def test_no_overlay_performance_artifact_is_created() -> None:
    ensure_evidence()
    assert not any("overlay_performance" in path.name for path in EVIDENCE.iterdir())
    rows = read_csv("overlay_compatibility_map.csv")
    assert {row["performance_experiment_run"] for row in rows} == {"false"}
    assert {row["overlay"] for row in rows} >= {"IdentityOverlay", "RebalanceBandOverlay", "StaticScaleOverlay"}


def test_broker_write_endpoint_is_not_called_and_api_secrets_not_persisted() -> None:
    alpaca = read_json("alpaca_asset_and_bar_check.json")
    consistency = read_json("consistency_check.json")
    assert alpaca["order_endpoint_called"] is False
    assert alpaca["read_only_endpoints_only"] is True
    assert consistency["api_credentials_not_persisted"] is True


def test_required_files_and_next_action_are_exact() -> None:
    ensure_evidence()
    assert impl.REQUIRED_FILES <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    manifest = read_json("trial_manifest.json")
    assert manifest["strategy_id"] == impl.STRATEGY_ID
    assert manifest["family_id"] == impl.FAMILY_ID
    assert manifest["next_action"] == "direction_owner_review_next_full_methodology_observable_macro_strategy_v1"
