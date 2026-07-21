from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from strategy_lab.research_os.research import currency_momentum_alpaca_data_and_overlay_readiness_v1 as impl


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / impl.OUTPUT_DIR


def read_json(name: str) -> dict[str, object]:
    if not (EVIDENCE / name).exists():
        impl.run(ROOT)
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    if not (EVIDENCE / name).exists():
        impl.run(ROOT)
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sample_history(pair: str, rows: int = 2) -> impl.PairHistory:
    records = [
        {"timestamp": "2024-01-31T00:00:00Z", "raw_rate": 1.0, "provider_fields": ["t", "r"]},
        {"timestamp": "2024-02-29T00:00:00Z", "raw_rate": 1.1, "provider_fields": ["t", "r"]},
    ][:rows]
    return impl.PairHistory(
        requested_pair=pair,
        returned_pair_identifier=pair,
        records=records,
        pages=1,
        status="ok",
        error="",
        loaded_from_cache=True,
        cache_path=Path(f"{pair}.json"),
        cache_hash="hash",
        request_metadata={},
    )


def test_all_nine_non_usd_pair_mappings_are_present() -> None:
    non_usd_rows = [row for row in impl.pair_map_rows() if row["currency"] != "USD"]
    assert len(non_usd_rows) == 9
    assert {row["alpaca_pair"] for row in non_usd_rows} == {
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "NZDUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "USDNOK",
        "USDSEK",
    }


def test_required_inverse_pairs_are_inverted_and_direct_pairs_are_not() -> None:
    assert impl.normalize_pair_rate("USDJPY", 100.0) == 0.01
    assert impl.normalize_pair_rate("USDCHF", 2.0) == 0.5
    assert impl.normalize_pair_rate("EURUSD", 1.25) == 1.25
    assert impl.normalize_pair_rate("GBPUSD", 1.5) == 1.5


def test_usd_momentum_is_exactly_zero() -> None:
    assert impl.usd_momentum_signal() == 0.0


def test_monthly_dates_strictly_increasing_and_gaps_are_reported_not_filled() -> None:
    canonical: dict[str, list[dict[str, object]]] = {}
    for row in impl.PAIR_DEFINITIONS:
        pair = row["pair"]
        canonical[pair] = impl.canonical_daily_records(sample_history(pair).records and sample_history(pair))
    canonical["USDSEK"] = canonical["USDSEK"][:1]

    monthly_rows, gap_rows, summary = impl.monthly_common_calendar(canonical)

    assert impl.monthly_dates_strictly_increasing(monthly_rows)
    assert summary["complete_month_count"] == 1
    assert summary["incomplete_month_count"] == 1
    assert gap_rows == [
        {
            "month": "2024-02",
            "missing_pairs": ["USDSEK"],
            "missing_currencies": ["SEK"],
            "gap_handling": "reported_not_filled",
        }
    ]


def test_duplicate_dates_are_rejected_by_invariant_helper() -> None:
    rows = [
        {
            "pair": "EURUSD",
            "currency": "EUR",
            "timestamp": "2024-01-31T00:00:00+00:00",
            "date": "2024-01-31",
            "raw_rate": 1.1,
            "normalized_rate": 1.1,
            "duplicate_timestamp": False,
        },
        {
            "pair": "EURUSD",
            "currency": "EUR",
            "timestamp": "2024-01-31T00:00:00+00:00",
            "date": "2024-01-31",
            "raw_rate": 1.1,
            "normalized_rate": 1.1,
            "duplicate_timestamp": True,
        },
    ]
    assert impl.duplicate_dates_rejected(rows) is False


def test_quote_normalization_and_provider_cache_hashing_are_deterministic() -> None:
    rows = impl.canonical_daily_records(sample_history("EURUSD"))
    assert impl.canonical_series_hash(rows) == impl.canonical_series_hash(rows)
    assert impl.stable_payload_hash({"b": 2, "a": 1}) == sha256_text('{"a":1,"b":2}')


def test_api_keys_are_not_logged_or_persisted() -> None:
    consistency = read_json("consistency_check.json")
    repo_review = read_json("alpaca_repository_capability_review.json")
    assert consistency["api_keys_logged_or_persisted"] is False
    assert repo_review["paper_credentials_integration"]["api_secrets_persisted"] is False
    assert repo_review["paper_credentials_integration"]["masked_credentials_written"] is False


def test_missing_required_currency_prevents_data_ready_outcome() -> None:
    histories = {row["pair"]: sample_history(row["pair"]) for row in impl.PAIR_DEFINITIONS}
    histories["USDSEK"] = impl.PairHistory(
        requested_pair="USDSEK",
        returned_pair_identifier="USDSEK",
        records=[],
        pages=0,
        status="no_records",
        error="missing",
        loaded_from_cache=False,
        cache_path=Path("USDSEK.json"),
        cache_hash="missing",
        request_metadata={},
    )
    outcome = impl.determine_outcome(
        histories,
        {"has_at_least_13_complete_months": True},
        {"materially_inconsistent_rows": 0, "insufficient_overlap_rows": 0},
    )
    assert outcome == "alpaca_pair_coverage_incomplete"


def test_insufficient_12_month_history_prevents_data_ready_outcome() -> None:
    histories = {row["pair"]: sample_history(row["pair"]) for row in impl.PAIR_DEFINITIONS}
    outcome = impl.determine_outcome(
        histories,
        {"has_at_least_13_complete_months": False},
        {"materially_inconsistent_rows": 0, "insufficient_overlap_rows": 0},
    )
    assert outcome == "alpaca_history_too_short"


def test_reconciliation_is_independent_of_strategy_performance() -> None:
    outcome = read_json("alpaca_data_feasibility_outcome.json")
    reconciliation_rows = read_csv("public_source_reconciliation.csv")
    assert outcome["selected_based_on_strategy_returns"] is False
    assert "CAGR" not in reconciliation_rows[0] if reconciliation_rows else True
    assert "Sharpe" not in reconciliation_rows[0] if reconciliation_rows else True
    assert "drawdown" not in ",".join(reconciliation_rows[0].keys()).lower() if reconciliation_rows else True


def test_no_strategy_performance_metrics_are_calculated() -> None:
    if not EVIDENCE.exists():
        impl.run(ROOT)
    forbidden_files = {
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_metrics.csv",
        "window_level_results.csv",
        "screening_outcomes.csv",
    }
    assert not any((EVIDENCE / name).exists() for name in forbidden_files)
    forbidden_columns = {"cagr", "sharpe", "max_drawdown", "strategy_return"}
    for csv_name in ["public_source_reconciliation.csv", "alpaca_raw_coverage_inventory.csv"]:
        rows = read_csv(csv_name)
        if rows:
            assert forbidden_columns.isdisjoint({column.lower() for column in rows[0].keys()})
    outcome = read_json("alpaca_data_feasibility_outcome.json")
    assert outcome["selected_based_on_strategy_returns"] is False


def test_no_order_placement_broker_write_bybit_crypto_or_state_change() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["order_placement_or_broker_write_called"] is False
    assert consistency["bybit_or_crypto_source_used"] is False
    assert consistency["strategy_registry_changed"] is False
    assert consistency["active_observations_changed"] is False


def test_no_trade_management_performance_experiment_and_deterministic_classifications() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["trade_management_performance_experiment_executed"] is False
    assert impl.overlay_compatibility_rows() == impl.overlay_compatibility_rows()
    classifications = {row["overlay"]: row["classification"] for row in impl.overlay_compatibility_rows()}
    assert classifications["IdentityOverlay"] == "compatible_after_narrow_adapter"
    assert classifications["WideATRCatastrophicStopOverlay"] == "not_appropriate_for_monthly_long_short_fx"


def test_frozen_baseline_spec_contains_exactly_one_config_when_data_ready() -> None:
    ready_spec = impl.build_frozen_baseline_spec(
        "alpaca_ready_with_public_reconciliation_limits",
        {"earliest_complete_month": "2020-01", "latest_complete_month": "2025-12", "complete_month_count": 72},
    )
    blocked_spec = impl.build_frozen_baseline_spec("alpaca_pair_coverage_incomplete", {})
    assert len(ready_spec["strategy_configurations"]) == 1
    assert ready_spec["strategy_configurations"][0]["strategy_id"] == impl.SPOT_PROXY_ID
    assert blocked_spec["strategy_configurations"] == []


def test_real_evidence_has_required_file_set_and_next_action() -> None:
    if not EVIDENCE.exists():
        impl.run(ROOT)
    expected = {
        "source_identity_and_lineage.json",
        "alpaca_repository_capability_review.json",
        "alpaca_endpoint_and_schema_review.json",
        "required_currency_and_pair_map.csv",
        "quote_normalization_map.csv",
        "alpaca_raw_coverage_inventory.csv",
        "monthly_common_calendar_coverage.csv",
        "missing_months_and_currency_gaps.csv",
        "public_source_reconciliation.csv",
        "data_hash_and_provenance_review.json",
        "alpaca_data_feasibility_outcome.json",
        "source_exact_vs_spot_proxy_map.csv",
        "frozen_baseline_experiment_spec.json",
        "trade_management_overlay_compatibility.csv",
        "trade_management_onboarding_requirements.md",
        "concrete_blockers.csv",
        "next_action.json",
        "command_validation_log.csv",
        "consistency_check.json",
        "feasibility_summary.md",
    }
    assert expected <= {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert read_json("next_action.json")["next_action"] == impl.NEXT_ACTION
