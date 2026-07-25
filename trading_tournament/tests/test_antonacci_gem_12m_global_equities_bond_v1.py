from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.antonacci_gem_12m_global_equities_bond_v1 import (
    HURDLE_SYMBOL,
    LOOKBACK_MONTHS,
    OUTPUT_DIR,
    REQUIRED_SYMBOLS,
    TASK_ID,
    TRADABLE_SYMBOLS,
    TRIAL_ID,
    deterministic_core_hash,
    gem_signal_audit,
    run,
    select_gem_asset,
    twelve_month_momentum,
    weights_from_signal_audit,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def synthetic_monthly() -> pd.DataFrame:
    index = pd.date_range("2020-01-31", periods=14, freq="ME")
    return pd.DataFrame(
        {
            "SPY": [100.0] * 12 + [112.0, 114.0],
            "ACWX": [100.0] * 12 + [118.0, 116.0],
            "AGG": [100.0] * 12 + [101.0, 102.0],
            "BIL": [100.0] * 12 + [103.0, 103.5],
        },
        index=index,
    )


def test_runner_writes_required_artifacts_and_blocks_before_returns_when_acwx_missing() -> None:
    result = run(ROOT)
    assert result["task_id"] == TASK_ID
    assert result["task_outcome"] == "source_asset_mapping_or_data_unavailable"
    assert result["return_calculation_run"] is False
    assert "ACWX" in result["missing_required_symbols"]
    required = [
        "source_packet_used.yaml",
        "exact_duplicate_check.json",
        "repository_fit_check.json",
        "frozen_universe_reference.json",
        "source_to_etf_mapping.csv",
        "frozen_trial_manifest.csv",
        "data_coverage.csv",
        "monthly_price_matrix.csv",
        "momentum_signal_audit.csv",
        "target_weights.csv",
        "transactions.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "family_outcome.json",
        "family_followup_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "implementation_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name


def test_exact_duplicate_check_and_trial_contract() -> None:
    duplicate = load_json("exact_duplicate_check.json")
    manifest = csv_rows("frozen_trial_manifest.csv")
    check = load_json("consistency_check.json")
    assert duplicate["duplicate_check_completed_before_return_calculation"] is True
    assert duplicate["exact_duplicate_found"] is False
    assert {row["assessment"] for row in duplicate["reviewed_records"]} == {"not_exact_duplicate"}
    assert len(manifest) == 1
    assert manifest[0]["trial_id"] == TRIAL_ID
    assert manifest[0]["portfolio_trial_count"] == "1"
    assert manifest[0]["trial_evaluation_status"] == "blocked_before_return_calculation"
    assert check["exactly_one_canonical_portfolio_trial_registered"] is True


def test_frozen_mapping_requires_acwx_and_does_not_substitute_efa() -> None:
    rows = {row["expected_symbol"]: row for row in csv_rows("source_to_etf_mapping.csv")}
    assert set(rows) == set(REQUIRED_SYMBOLS)
    assert rows["ACWX"]["mapping_status"] == "required_symbol_unavailable"
    assert rows["ACWX"]["selected_symbol"] == ""
    assert rows["ACWX"]["substitution_allowed"] == "False"
    assert all(row["expected_symbol"] != "EFA" and row["selected_symbol"] != "EFA" for row in rows.values())
    assert rows["SPY"]["mapping_status"] == "expected_symbol_available"
    assert rows["AGG"]["mapping_status"] == "expected_symbol_available"
    assert rows["BIL"]["mapping_status"] == "expected_symbol_available"


def test_data_coverage_reports_acwx_missing_without_download() -> None:
    rows = {row["symbol"]: row for row in csv_rows("data_coverage.csv")}
    assert rows["ACWX"]["cache_ready"] == "False"
    assert rows["ACWX"]["frozen_universe_available"] == "False"
    assert rows["SPY"]["cache_ready"] == "True"
    assert rows["AGG"]["cache_ready"] == "True"
    assert rows["BIL"]["cache_ready"] == "True"
    check = load_json("consistency_check.json")
    assert check["provider_download"] is False
    assert check["return_calculation_run"] is False


def test_lookback_is_exactly_12_completed_months_and_latest_month_is_not_skipped() -> None:
    monthly = synthetic_monthly()
    momentum = twelve_month_momentum(monthly)
    first_valid = monthly.index[LOOKBACK_MONTHS]
    assert LOOKBACK_MONTHS == 12
    assert pd.isna(momentum.iloc[LOOKBACK_MONTHS - 1]["SPY"])
    assert abs(momentum.loc[first_valid, "SPY"] - 0.12) <= 1e-12
    assert abs(momentum.loc[first_valid, "ACWX"] - 0.18) <= 1e-12
    audit = gem_signal_audit(monthly)
    first_valid_row = audit.loc[audit["valid_common_signal_month"] == True].iloc[0]
    assert first_valid_row["month_end_date"] == first_valid.date().isoformat()
    assert bool(first_valid_row["uses_most_recent_month"]) is True


def test_gate_order_and_selection_branches() -> None:
    assert select_gem_asset(spy_return=0.02, acwx_return=0.40, bil_return=0.02) == "AGG"
    assert select_gem_asset(spy_return=0.01, acwx_return=0.40, bil_return=0.02) == "AGG"
    assert select_gem_asset(spy_return=0.20, acwx_return=0.10, bil_return=0.02) == "SPY"
    assert select_gem_asset(spy_return=0.20, acwx_return=0.20, bil_return=0.02) == "SPY"
    assert select_gem_asset(spy_return=0.20, acwx_return=0.25, bil_return=0.02) == "ACWX"


def test_signal_audit_records_spy_bil_gate_before_relative_selection() -> None:
    monthly = synthetic_monthly()
    audit = gem_signal_audit(monthly)
    valid = audit.loc[audit["valid_common_signal_month"] == True]
    assert set(valid["gate_order"]) == {"SPY_vs_BIL_before_SPY_vs_ACWX"}
    assert valid.iloc[0]["selected_asset"] == "ACWX"


def test_weights_hold_exactly_one_tradable_asset_and_never_hold_bil() -> None:
    daily_index = pd.date_range("2021-01-29", periods=6, freq="B")
    signal = pd.DataFrame(
        [
            {
                "month_end_date": "2021-01-29",
                "valid_common_signal_month": True,
                "selected_asset": "SPY",
            },
            {
                "month_end_date": "2021-02-01",
                "valid_common_signal_month": True,
                "selected_asset": "AGG",
            },
        ]
    )
    weights = weights_from_signal_audit(daily_index, signal)
    initialized = weights.loc[weights[TRADABLE_SYMBOLS].sum(axis=1) > 0.0]
    assert not initialized.empty
    assert set(weights.columns) == set(REQUIRED_SYMBOLS)
    assert (initialized[TRADABLE_SYMBOLS].sum(axis=1) == 1.0).all()
    assert ((initialized[TRADABLE_SYMBOLS] > 0.5).sum(axis=1) == 1).all()
    assert (weights[HURDLE_SYMBOL] == 0.0).all()


def test_no_same_period_return_is_earned_by_construction() -> None:
    daily_index = pd.to_datetime(["2021-01-29", "2021-02-01", "2021-02-02"])
    signal = pd.DataFrame([{"month_end_date": "2021-01-29", "valid_common_signal_month": True, "selected_asset": "SPY"}])
    weights = weights_from_signal_audit(daily_index, signal)
    first_signal_date = pd.Timestamp("2021-01-29")
    first_execution_date = daily_index[daily_index.get_loc(first_signal_date) + 1]
    assert first_execution_date > first_signal_date
    assert weights.loc[first_signal_date, "SPY"] == 1.0


def test_no_parameter_universe_alternative_overlay_or_state_changes() -> None:
    manifest = csv_rows("frozen_trial_manifest.csv")[0]
    check = load_json("consistency_check.json")
    names = {path.name.lower() for path in EVIDENCE.iterdir()}
    assert manifest["lookback_months"] == "12"
    assert manifest["symbols"] == "|".join(REQUIRED_SYMBOLS)
    assert check["required_symbols_exactly"] == REQUIRED_SYMBOLS
    assert check["no_overlay_output_generated"] is True
    assert all("overlay" not in name for name in names)
    assert check["registry_lifecycle_unchanged"] is True
    assert check["active_paper_demo_state_unchanged"] is True
    assert check["broker_or_order_path_touched"] is False
    assert check["paper_forward_activation"] is False
    assert check["promotion_candidates_created"] is False
    assert check["candidate_exhaustive_run"] is False
    assert check["real_money_recommendation"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
