from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1 as subject


def csv_rows(name: str) -> list[dict[str, str]]:
    with (subject.OUTPUT_DIR / name).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def completed_run():
    result = subject.run()
    assert result["overall_pass"] is True
    return result


def test_exactly_one_canonical_trial_and_no_variant() -> None:
    manifest = json.loads((subject.OUTPUT_DIR / "trial_manifest.json").read_text(encoding="utf-8"))
    assert manifest["canonical_trial_count"] == 1
    assert manifest["canonical_trial_id"] == subject.TRIAL_ID
    assert manifest["variant_count"] == 0


def test_frozen_v2_and_universe_hashes_match() -> None:
    source = json.loads((subject.OUTPUT_DIR / "source_conformance.json").read_text(encoding="utf-8"))
    assert source["V2_hash_verification"]["observed_hash"] == subject.V2_EXPECTED_HASH
    assert source["price_data_verification"]["universe_hash"] == subject.UNIVERSE_EXPECTED_HASH


def test_threshold_cases_emerge_from_unrounded_signal() -> None:
    signal = subject.load_signal()
    observed = {month: signal.loc[pd.Period(month, freq="M"), "canonical_regime"] for month in subject.EXPECTED_THRESHOLD_REGIMES}
    assert observed == subject.EXPECTED_THRESHOLD_REGIMES


def test_low_regime_weights_are_exact_and_zero_complete() -> None:
    low = [row for row in csv_rows("monthly_signal_and_weights.csv") if row["regime"] == "low"]
    assert low
    for row in low:
        assert float(row["target_SPY"]) == 0.60
        assert float(row["target_AGG"]) == 0.40
        assert all(float(row[f"target_{symbol}"]) == 0.0 for symbol in ("IYR", "GSG", "GLD", "TIP"))


def test_medium_inverse_vol_weights_are_source_exact() -> None:
    rows = csv_rows("volwt_diagnostics.csv")
    first_month = rows[0]["formation_reference_month"]
    group = [row for row in rows if row["formation_reference_month"] == first_month]
    raw = np.array([float(row["raw_inverse_volatility"]) for row in group])
    weights = np.array([float(row["normalized_weight"]) for row in group])
    assert len(group) == 6
    assert np.allclose(weights, raw / raw.sum(), atol=subject.WEIGHT_TOLERANCE)


def test_beta_transform_source_formula() -> None:
    assert subject.beta_transform(2.0) == 3.0
    assert subject.beta_transform(-2.0) == pytest.approx(1.0 / 3.0)
    for row in csv_rows("proib_regression_diagnostics.csv"):
        assert float(row["transformed_beta"]) == pytest.approx(subject.beta_transform(float(row["beta"])), abs=subject.TOLERANCE)


def test_first_formation_warmup_and_pair_count() -> None:
    monthly = csv_rows("monthly_signal_and_weights.csv")
    assert monthly[0]["effective_close_date"] == "2009-08-17"
    assert int(monthly[0]["lookback_monthly_returns"]) == 36
    first = [row for row in csv_rows("proib_regression_diagnostics.csv") if row["formation_reference_month"] == "2009-07"]
    assert len(first) == 6
    assert all(int(row["rolling_12m_pair_count"]) == 25 for row in first)


def test_proib_uses_no_prewindow_return_and_no_unreleased_cpi() -> None:
    rows = csv_rows("proib_regression_diagnostics.csv")
    assert all(row["pre_window_return_used"] == "false" for row in rows)
    assert all(row["all_CPI_releases_available_by_formation"] == "true" for row in rows)
    assert all(row["latest_CPI_release_used"] <= row["formation_release_date"] for row in rows)


def test_lookback_expands_then_rolls_at_120() -> None:
    sizes = [int(row["lookback_monthly_returns"]) for row in csv_rows("monthly_signal_and_weights.csv")]
    assert sizes[0] == 36
    assert max(sizes) == 120
    assert all(36 <= value <= 120 for value in sizes)


def test_timing_cutoffs_and_next_interval_accounting() -> None:
    for row in csv_rows("monthly_signal_and_weights.csv"):
        assert row["lookback_end_month"] == row["reference_month"]
        assert row["regime_information_cutoff"] < row["effective_close_date"] < row["new_weights_first_return_date"]


def test_october_2025_creates_no_event() -> None:
    rows = {row["reference_month"]: row for row in csv_rows("regime_events.csv")}
    assert rows["2025-10"]["rebalance_event"] == "false"
    assert rows["2025-10"]["source_compliant_formation"] == "false"
    assert rows["2025-10"]["october_2025_no_event"] == "true"


def test_daily_targets_have_real_zeros_and_no_stale_weight_sum() -> None:
    rows = csv_rows("daily_target_weights.csv")
    sums = np.array([float(row["target_weight_sum"]) for row in rows])
    assert np.allclose(sums, 1.0, atol=subject.WEIGHT_TOLERANCE)
    assert any(int(row["explicit_zero_count"]) > 0 for row in rows)
    assert max(sums) <= 1.0 + subject.WEIGHT_TOLERANCE


def test_blocking_controls_are_ex_ante_and_diagnostic_cannot_block() -> None:
    rows = {row["control_id"]: row for row in csv_rows("control_information_set_audit.csv")}
    for control in subject.BLOCKING_CONTROLS:
        assert rows[control]["gate_role"] == "blocking_control"
        assert rows[control]["ex_ante_investable"] == "true"
        assert rows[control]["uses_evaluation_information"] == "false"
    assert rows[subject.DIAGNOSTIC_CONTROL]["gate_role"] == "diagnostic_only"
    assert rows[subject.DIAGNOSTIC_CONTROL]["can_block_advancement"] == "false"


def test_evaluation_access_obeys_selection_gate() -> None:
    access = json.loads((subject.OUTPUT_DIR / "evaluation_access_log.json").read_text(encoding="utf-8"))
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert access["evaluation_access_authorized"] == consistency["selection_gate"]["selection_eligible"]
    assert access["evaluation_calculated"] == access["evaluation_access_authorized"]
    if not access["evaluation_access_authorized"]:
        assert not (subject.OUTPUT_DIR / "evaluation_results.csv").exists()


def test_trial_accounting_and_protected_state_reconcile() -> None:
    accounting = json.loads((subject.OUTPUT_DIR / "trial_accounting.json").read_text(encoding="utf-8"))
    consistency = json.loads((subject.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert accounting["architecture_count"] == 1
    assert accounting["canonical_configuration_count"] == 1
    assert accounting["canonical_trial_count"] == 1
    assert accounting["strategy_variants_created"] == 0
    assert consistency["checks"]["protected_state_unchanged"] is True


def test_deterministic_replay_preserves_evidence_hash(completed_run) -> None:
    second = subject.run()
    assert second["deterministic_evidence_hash"] == completed_run["deterministic_evidence_hash"]
    assert second["overall_pass"] is True
