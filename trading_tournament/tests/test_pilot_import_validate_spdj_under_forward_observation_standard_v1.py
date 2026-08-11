from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    SourceAdapterRegistry,
    normalized_spdj_package_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.errors import StandardContractError
from contracts.forward_observation.forward_observation_handoff_standard_v1.importer import HandoffImporter
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    DeploymentProfile,
    IdentityBinding,
    StrategyState,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.state import (
    JsonStrategyStateStore,
    apply_calculation_result,
    promote_pending_target,
)
from execution_lab.alpaca_micro_live_v1 import PACKAGE_ROOT
from execution_lab.alpaca_micro_live_v1.standard_handoff.pilot_spdj_import import (
    CANONICAL_CODE_HASH,
    CPI_DATASET_HASH,
    HANDOFF_ID,
    INSTANCE_ID,
    PACKAGE_HASH,
    PRICE_BUNDLE_HASH,
    STRATEGY_ID,
    UNIVERSE_HASH,
    normalization_field_map,
    verify_standard_evidence,
)
from execution_lab.alpaca_micro_live_v1.standard_handoff.spdj_calculator import (
    SYMBOLS,
    SpdjReceiverCalculator,
    beta_transform,
    build_xnys_calendar,
    classify_regime,
    inverse_volatility_weights,
    low_regime_weights,
    normalize_provider_frames,
)


PACKAGE = PACKAGE_ROOT / "evidence" / "handoff_exports" / "spdj_dynamic_inflation_forward_observation_handoff_v1" / "latest" / "package"


@pytest.fixture(scope="module")
def contract_and_binding():
    adaptation = SourceAdapterRegistry().identify(PACKAGE).adapt(PACKAGE)
    assert adaptation.normalized_handoff is not None
    binding = IdentityBinding.create(
        handoff=adaptation.normalized_handoff,
        receiver_strategy_id=STRATEGY_ID,
        strategy_instance_id=INSTANCE_ID,
        binding_timestamp="2026-08-10T00:00:00Z",
        binding_provenance="explicit_test_binding",
    )
    return adaptation.normalized_handoff, binding


def synthetic_inputs(month_count: int = 37, final_cpi: float = 1.0):
    periods = pd.period_range("2006-07", periods=month_count, freq="M")
    dates = periods.to_timestamp(how="end").normalize()
    frames = {}
    for position, symbol in enumerate(SYMBOLS):
        increments = 0.002 + (position + 1) * 0.0007 + np.sin(np.arange(month_count) * (0.3 + position * 0.04)) * 0.002
        prices = 100.0 * np.cumprod(1.0 + increments)
        frames[symbol] = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": prices})
    rows = []
    for index, period in enumerate(periods):
        release = period.to_timestamp(how="end").normalize() + pd.Timedelta(days=15)
        cpi = final_cpi if index == len(periods) - 1 else 2.0 + np.sin(index / 5.0) * 0.4
        rows.append({
            "reference_period": period,
            "reference_month": str(period),
            "release_date": release,
            "cpi_yoy": cpi,
            "event": True,
            "canonical_regime": classify_regime(cpi),
            "release_artifact_hash": f"sha256:{index:064x}",
        })
    cpi = pd.DataFrame(rows).set_index("reference_period", drop=False)
    prices, _ = normalize_provider_frames(frames)
    return periods[-1], prices, cpi


def test_standard_evidence_reconciles():
    assert verify_standard_evidence()["status"] == "pass"


def test_source_package_hash_and_declared_provenance():
    assert normalized_spdj_package_hash(PACKAGE) == PACKAGE_HASH
    manifest = json.loads((PACKAGE / "handoff_manifest.json").read_text(encoding="utf-8"))
    assert manifest["canonical_code_hash"] == CANONICAL_CODE_HASH
    assert manifest["CPI_dataset_hash"] == CPI_DATASET_HASH
    assert manifest["price_bundle_hash"] == PRICE_BUNDLE_HASH
    assert manifest["universe_hash"] == UNIVERSE_HASH


def test_normalization_map_invents_no_rules():
    assert normalization_field_map()
    assert not any(row["invented"] for row in normalization_field_map())


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1.499999999, "low"), (1.5, "medium"), (2.5, "medium"), (2.500000001, "high")],
)
def test_cpi_thresholds_are_exact(value, expected):
    assert classify_regime(value) == expected


def test_low_regime_target_is_exact(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=1.0)
    result = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="low"
    )
    assert result.target_weights == low_regime_weights()
    assert result.lookback_monthly_returns == 36
    assert result.pro_ib_diagnostics["pair_count"] == 25


def test_medium_inverse_volatility_uses_sample_ddof(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=2.0)
    result = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="medium"
    )
    monthly = prices.groupby(prices.index.to_period("M")).last().pct_change(fill_method=None).dropna()
    expected, diagnostics = inverse_volatility_weights(monthly.tail(36))
    assert diagnostics["sample_volatility_ddof"] == 1
    assert result.target_weights == pytest.approx(expected, abs=1e-14)


def test_high_proib_uses_25_pairs_at_first_window(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=3.0)
    result = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="high"
    )
    assert result.pro_ib_diagnostics["pair_count"] == 25
    assert sum(result.target_weights.values()) == pytest.approx(1.0)
    assert all(value >= 0.0 for value in result.target_weights.values())
    assert beta_transform(-0.25) == pytest.approx(0.8)
    assert beta_transform(0.25) == pytest.approx(1.25)


def test_history_expands_then_caps_at_120(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(month_count=131, final_cpi=2.0)
    result = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="rolling"
    )
    assert result.lookback_monthly_returns == 120


def test_prices_after_statistics_cutoff_do_not_change_target(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=2.0)
    calculator = SpdjReceiverCalculator(handoff, binding)
    first = calculator.calculate(reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="first")
    altered = prices.copy()
    future_date = prices.index.max() + pd.offsets.MonthEnd(1)
    altered.loc[future_date] = [value * (1.0 + index) for index, value in enumerate(prices.iloc[-1], start=1)]
    second = calculator.calculate(reference_month=str(month), cpi_reference=cpi, prices=altered, calendar=build_xnys_calendar(), fixture_id="second")
    assert first.target_weights == second.target_weights
    assert first.statistics_cutoff == second.statistics_cutoff


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        ("2009-08-14", "2009-08-17"),
        ("2010-01-15", "2010-01-19"),
        ("2013-04-16", "2013-04-17"),
        ("2024-09-11", "2024-09-12"),
    ],
)
def test_xnys_calendar_resolves_fixture_sessions(release, expected):
    assert build_xnys_calendar().next_session_after(release).session_date == expected


def test_no_release_creates_no_event_or_target(contract_and_binding):
    handoff, binding = contract_and_binding
    result = SpdjReceiverCalculator(handoff, binding).no_event_result(
        reference_month="2025-10", calculated_at="2025-11-01T00:00:00Z"
    )
    assert result.status == "no_event"
    assert result.event_id is None
    assert result.target_version_id is None
    assert result.target_weights == {}


def test_persistent_inactive_import_does_not_activate(tmp_path, contract_and_binding):
    profile = DeploymentProfile(
        deployment_profile_id="test_inactive",
        receiver_strategy_id=STRATEGY_ID,
        strategy_instance_id=INSTANCE_ID,
        handoff_id=HANDOFF_ID,
        observation_mode="paper_demo",
        market_data_capability_binding="historical_only",
        calendar_binding="XNYS",
        deployment_status="validated_not_active",
        paper_submission_enabled=False,
        live_submission_enabled=False,
    )
    result = HandoffImporter(storage_root=tmp_path).process(
        PACKAGE,
        mode="import_inactive",
        timestamp="2026-08-10T00:00:00Z",
        receiver_strategy_id=STRATEGY_ID,
        strategy_instance_id=INSTANCE_ID,
        binding_provenance="explicit_test_binding",
        deployment_profile=profile,
    )
    assert result.imported_path
    assert result.acceptance.acceptance_status == "validated_not_active"
    assert result.acceptance.activation_performed is False


def test_state_restart_idempotency_and_target_identity(tmp_path, contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=1.0)
    calculation = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="state"
    )
    initial = StrategyState(INSTANCE_ID, HANDOFF_ID, STRATEGY_ID, "validated_not_active")
    pending = apply_calculation_result(initial, calculation.result, now=calculation.result.calculated_at)
    store = JsonStrategyStateStore(tmp_path)
    store.save(pending)
    restarted = JsonStrategyStateStore(tmp_path).load(INSTANCE_ID)
    assert restarted == pending
    promoted = promote_pending_target(restarted, now=calculation.result.effective_timestamp)
    assert promoted.current_effective_target_version == calculation.result.target_version_id
    with pytest.raises(StandardContractError, match="already processed") as error:
        apply_calculation_result(promoted, calculation.result, now=calculation.result.effective_timestamp)
    assert error.value.code == "duplicate_event"


def test_receiver_target_contains_no_execution_objects(contract_and_binding):
    handoff, binding = contract_and_binding
    month, prices, cpi = synthetic_inputs(final_cpi=1.0)
    result = SpdjReceiverCalculator(handoff, binding).calculate(
        reference_month=str(month), cpi_reference=cpi, prices=prices, calendar=build_xnys_calendar(), fixture_id="boundary"
    ).result.to_dict()
    forbidden = {"orders", "proposed_orders", "shares", "quantities", "fills", "broker_instructions"}
    assert forbidden.isdisjoint(result)
