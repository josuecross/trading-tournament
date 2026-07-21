from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from strategy_lab.research_os.research import currency_momentum_alpaca_etp_translation_feasibility_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def ensure_evidence() -> None:
    if not EVIDENCE.exists() or not (EVIDENCE / "feasibility_outcome.json").exists():
        impl.run(ROOT)


def read_json(name: str) -> dict[str, object]:
    ensure_evidence()
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    ensure_evidence()
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hashes() -> dict[str, str]:
    ensure_evidence()
    hashes: dict[str, str] = {}
    for path in sorted(EVIDENCE.iterdir()):
        if path.is_file() and path.name != "command_validation_log.csv":
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_every_source_currency_appears_in_mapping_and_usd_is_base_member() -> None:
    rows = read_csv("source_currency_to_etp_map.csv")
    by_currency = {row["source_currency"]: row for row in rows}
    assert set(by_currency) == set(impl.SOURCE_CURRENCIES)
    assert by_currency["USD"]["selected_symbol"] == "USD_BASE_CASH_MEMBER"
    assert by_currency["USD"]["coverage_classification"] == "base_currency_retained"


def test_leveraged_inverse_basket_and_inactive_products_are_rejected() -> None:
    rejected = {row["symbol"]: row for row in read_csv("rejected_instruments.csv")}
    assert "ULE" in rejected and "leveraged" in rejected["ULE"]["rejection_reasons"]
    assert "EUO" in rejected and "inverse" in rejected["EUO"]["rejection_reasons"]
    assert "YCL" in rejected and "leveraged" in rejected["YCL"]["rejection_reasons"]
    assert "YCS" in rejected and "inverse" in rejected["YCS"]["rejection_reasons"]
    assert "CEW" in rejected and "basket_product" in rejected["CEW"]["rejection_reasons"]
    assert "DBV" in rejected and "basket_product" in rejected["DBV"]["rejection_reasons"]
    assert "FXS" in rejected and "inactive_or_not_alpaca_recognized" in rejected["FXS"]["rejection_reasons"]


def test_basket_products_are_not_treated_as_single_currencies() -> None:
    official = {row["symbol"]: row for row in read_csv("official_instrument_verification.csv")}
    assert official["CEW"]["single_currency"] == "false"
    assert official["CEW"]["basket_product"] == "true"
    assert official["DBV"]["single_currency"] == "false"
    assert official["DBV"]["basket_product"] == "true"
    mapping = {row["source_currency"]: row for row in read_csv("source_currency_to_etp_map.csv")}
    assert mapping["NOK"]["coverage_classification"] == "basket_only"


def test_non_shortable_products_cannot_satisfy_full_readiness() -> None:
    mapping = {row["source_currency"]: row for row in read_csv("source_currency_to_etp_map.csv")}
    assert mapping["EUR"]["coverage_classification"] == "tradable_but_not_shortable"
    assert mapping["GBP"]["coverage_classification"] == "tradable_but_not_shortable"
    assert mapping["AUD"]["coverage_classification"] == "tradable_but_not_shortable"
    assert mapping["CAD"]["coverage_classification"] == "tradable_but_not_shortable"
    full = read_json("full_universe_coverage.json")
    shortability = read_json("shortability_and_margin_review.json")
    assert full["full_source_universe_translation_ready"] is False
    assert shortability["full_readiness_blocked_by_shortability"] is True


def test_candidate_selection_follows_frozen_non_performance_criteria() -> None:
    candidates = [candidate for candidate in impl.CANDIDATES if "EUR" in candidate.source_currencies]
    inventory = {
        "FXE": {"status": "active", "tradable": True, "shortable": False},
        "ULE": {"status": "active", "tradable": True, "shortable": True},
        "EUO": {"status": "active", "tradable": True, "shortable": True},
    }
    bars = {
        "FXE": {"monthly_observation_count": 10},
        "ULE": {"monthly_observation_count": 999},
        "EUO": {"monthly_observation_count": 999},
    }
    selected = impl.select_preferred_candidate(candidates, inventory, bars)
    assert selected is not None
    assert selected.symbol == "FXE"


def test_no_performance_metric_is_calculated_or_output() -> None:
    forbidden_files = {
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "window_level_results.csv",
        "screening_outcomes.csv",
    }
    assert not any((EVIDENCE / name).exists() for name in forbidden_files)
    forbidden_columns = {"cagr", "sharpe", "drawdown", "return"}
    for csv_name in ["alpaca_bar_coverage.csv", "alpaca_asset_inventory.csv", "source_currency_to_etp_map.csv"]:
        rows = read_csv(csv_name)
        if rows:
            assert forbidden_columns.isdisjoint({column.lower() for column in rows[0].keys()})
    assert read_json("feasibility_outcome.json")["selected_based_on_performance"] is False


def test_no_order_broker_write_trial_registry_or_active_state_changes() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["orders_or_broker_write_called"] is False
    assert consistency["strategy_trial_created"] is False
    assert consistency["registry_changed"] is False
    assert consistency["active_observations_changed"] is False
    assert consistency["fx_rates_endpoint_reopened"] is False
    assert consistency["bybit_or_crypto_used"] is False


def test_no_overlay_performance_test_runs_and_compatibility_is_deterministic() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["overlay_performance_test_run"] is False
    assert impl.overlay_compatibility_rows() == impl.overlay_compatibility_rows()
    rows = {row["overlay"]: row["classification"] for row in read_csv("trade_management_overlay_compatibility.csv")}
    assert rows["IdentityOverlay"] == "compatible_after_narrow_adapter"
    assert rows["LaggedVolatilityTargetOverlay"] == "defer_until_base_verified"
    assert rows["WideATRCatastrophicStopOverlay"] == "not_economically_appropriate"


def test_reduced_universe_strategy_is_not_frozen() -> None:
    subset = read_json("maximum_subset_coverage.json")
    spec = read_json("frozen_future_experiment_spec.json")
    assert subset["subset_strategy_frozen"] is False
    assert subset["subset_strategy_authorized"] is False
    if read_json("feasibility_outcome.json")["outcome"] != "alpaca_full_g10_etp_translation_ready":
        assert spec["spec_created"] is False
        assert spec["strategy_configurations"] == []


def test_output_generation_is_deterministic_for_static_helpers() -> None:
    before = file_hashes()
    # Re-check the deterministic portions without forcing another live Alpaca call.
    assert impl.overlay_compatibility_rows() == impl.overlay_compatibility_rows()
    assert impl.official_verification_rows() == impl.official_verification_rows()
    after = file_hashes()
    assert before == after


def test_required_evidence_files_exist_and_next_action_is_exact() -> None:
    expected = {
        "alpaca_asset_inventory.csv",
        "official_instrument_verification.csv",
        "source_currency_to_etp_map.csv",
        "rejected_instruments.csv",
        "alpaca_bar_coverage.csv",
        "full_universe_coverage.json",
        "maximum_subset_coverage.json",
        "shortability_and_margin_review.json",
        "translation_risks.md",
        "trade_management_overlay_compatibility.csv",
        "frozen_future_experiment_spec.json",
        "feasibility_outcome.json",
        "command_validation_log.csv",
        "consistency_check.json",
        "feasibility_summary.md",
    }
    ensure_evidence()
    assert expected <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert read_json("feasibility_outcome.json")["next_action"] == impl.NEXT_ACTION
