from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import run_indicator_validation_harness_implementation as impl
from src.indicators import (
    add_indicators,
    atr,
    bollinger_bands,
    ema,
    prepare_indicators,
    realized_volatility,
    rolling_high,
    rolling_percentile_rank,
    rolling_return,
    rsi,
    sma,
)
from tests.indicator_fixtures import (
    flat_price_fixture,
    gap_fixture,
    known_manual_calculation_fixture,
    missing_values_fixture,
    monotonic_down_fixture,
    monotonic_up_fixture,
    short_history_fixture,
)


def test_fixture_builders_produce_deterministic_ohlcv_data() -> None:
    first = monotonic_up_fixture()
    second = monotonic_up_fixture()
    pd.testing.assert_frame_equal(first, second)
    assert {"date", "open", "high", "low", "close", "volume"} <= set(first.columns)
    assert flat_price_fixture()["close"].nunique() == 1
    assert len(gap_fixture()) == 8
    assert len(short_history_fixture()) < 5


def test_sma_matches_hand_computed_expected_values() -> None:
    close = known_manual_calculation_fixture()["close"]
    out = sma(close, 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == 11.0
    assert out.iloc[3] == (12.0 + 11.0 + 15.0) / 3.0
    assert out.iloc[5] == (15.0 + 14.0 + 18.0) / 3.0


def test_ema_is_deterministic_and_respects_warmup_policy() -> None:
    close = known_manual_calculation_fixture()["close"]
    first = ema(close, 3)
    second = ema(close, 3)
    pd.testing.assert_series_equal(first, second)
    assert first.iloc[:2].isna().all()
    assert np.isfinite(first.iloc[2])
    assert first.iloc[-1] > first.iloc[2]


def test_roc_rolling_return_matches_hand_computed_expected_values() -> None:
    close = known_manual_calculation_fixture()["close"]
    out = rolling_return(close, 2)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == 11.0 / 10.0 - 1.0
    assert out.iloc[3] == 15.0 / 12.0 - 1.0
    assert out.iloc[5] == 18.0 / 15.0 - 1.0


def test_atr_handles_gap_fixture_with_true_range() -> None:
    frame = gap_fixture()
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - frame["close"].shift(1)).abs(),
            (frame["low"] - frame["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    expected = true_range.rolling(window=3, min_periods=3).mean()
    pd.testing.assert_series_equal(atr(frame, 3), expected)
    assert atr(frame, 3).iloc[2] > 0
    assert true_range.iloc[5] > true_range.iloc[4]
    assert atr(frame, 3).dropna().max() > 4.0


def test_realized_volatility_handles_flat_monotonic_and_gap_fixtures() -> None:
    flat = realized_volatility(flat_price_fixture()["close"], 20)
    assert flat.iloc[:20].isna().all()
    assert (flat.dropna() == 0.0).all()

    up = realized_volatility(monotonic_up_fixture()["close"], 20)
    gaps = realized_volatility(gap_fixture()["close"], 3)
    assert up.dropna().ge(0.0).all()
    assert gaps.dropna().max() > 0.0


def test_rsi_handles_flat_rising_and_falling_fixtures_without_future_leakage() -> None:
    flat = rsi(flat_price_fixture()["close"], 2)
    rising = rsi(monotonic_up_fixture()["close"], 2)
    falling = rsi(monotonic_down_fixture()["close"], 2)
    assert flat.iloc[:2].isna().all()
    assert (flat.dropna() == 0.0).all()
    assert (rising.dropna() == 100.0).all()
    assert (falling.dropna() == 0.0).all()

    base = monotonic_up_fixture(rows=30)["close"]
    changed_future = base.copy()
    changed_future.iloc[-1] = 9999.0
    pd.testing.assert_series_equal(rsi(base, 2).iloc[:-1], rsi(changed_future, 2).iloc[:-1])


def test_bollinger_bands_handle_flat_prices_and_warmup_periods() -> None:
    bands = bollinger_bands(flat_price_fixture()["close"], 20, 2.0)
    assert bands.iloc[:19].isna().all().all()
    valid = bands.dropna()
    assert (valid["bb_mid"] == 100.0).all()
    assert (valid["bb_upper"] == 100.0).all()
    assert (valid["bb_lower"] == 100.0).all()


def test_donchian_prior_high_excludes_current_signal_row() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 50.0, 4.0])
    prior_high = rolling_high(values, 3, shift=1)
    assert prior_high.iloc[:3].isna().all()
    assert prior_high.iloc[3] == 3.0
    assert prior_high.iloc[4] == 50.0


def test_volume_sma_handles_zero_and_missing_volume() -> None:
    zero_volume = flat_price_fixture(volume=0.0)
    zero_indicators = add_indicators(zero_volume)
    assert zero_indicators["avg_volume_20"].dropna().eq(0.0).all()

    missing = add_indicators(missing_values_fixture())
    assert math.isnan(float(missing.loc[20, "avg_volume_20"]))
    assert np.isfinite(missing.loc[28, "avg_volume_20"])


def test_percentile_rank_does_not_use_future_rows() -> None:
    values = pd.Series(np.arange(1.0, 61.0))
    future_changed = values.copy()
    future_changed.iloc[-1] = 9999.0
    base_rank = rolling_percentile_rank(values, window=10, min_periods=5)
    changed_rank = rolling_percentile_rank(future_changed, window=10, min_periods=5)
    pd.testing.assert_series_equal(base_rank.iloc[:40], changed_rank.iloc[:40])
    assert 0.0 <= base_rank.dropna().iloc[-2] <= 1.0


def test_moving_average_and_spy_regime_use_completed_current_row_without_future_leakage() -> None:
    spy = monotonic_up_fixture(rows=260)
    altered_future = spy.copy()
    altered_future.loc[250:, "close"] = 1.0
    prepared = prepare_indicators({"SPY": spy})["SPY"]
    altered = prepare_indicators({"SPY": altered_future})["SPY"]

    pd.testing.assert_series_equal(prepared.loc[:240, "sma_200"], altered.loc[:240, "sma_200"])
    assert prepared.loc[210, "close"] > prepared.loc[210, "sma_200"]
    assert str(prepared.loc[210, "market_regime"]).startswith("bull_")


def test_short_history_fixture_produces_expected_warmup_invalid_behavior() -> None:
    indicators = add_indicators(short_history_fixture())
    for column in ["sma_5", "ema_10", "atr_10", "atr_20", "ret_63", "high_20", "avg_volume_20"]:
        assert indicators[column].isna().all()


def test_missing_values_fixture_produces_safe_invalid_outputs() -> None:
    indicators = add_indicators(missing_values_fixture())
    assert indicators.loc[5, "close"] != indicators.loc[5, "close"]
    assert indicators.loc[5:9, "sma_5"].isna().any()
    assert indicators.loc[6:9, "atr_10"].isna().any()
    assert indicators.loc[8:27, "avg_volume_20"].isna().any()


def test_strategy_consumed_indicator_columns_are_present_and_aligned() -> None:
    indicators = add_indicators(flat_price_fixture())
    consumed = {
        "sma_50",
        "sma_100",
        "sma_200",
        "ema_10",
        "atr_20",
        "rsi_2",
        "bb_lower",
        "avg_volume_20",
        "ret_63",
        "ret_126",
        "rv_20",
        "high_20",
        "atr_10_percentile",
    }
    assert consumed <= set(indicators.columns)
    assert indicators.loc[19, "high_20"] != indicators.loc[19, "high_20"]
    assert indicators.loc[20, "high_20"] == 100.0
    assert indicators.loc[19, "avg_volume_20"] == 1000.0


def test_gated_future_indicators_remain_gated_if_not_implemented() -> None:
    indicators = add_indicators(flat_price_fixture())
    lower_columns = {column.lower() for column in indicators.columns}
    assert "macd" not in lower_columns
    assert "obv" not in lower_columns
    assert not any("keltner" in column for column in lower_columns)
    assert "MACD" in impl.GATED_FUTURE_INDICATORS
    assert "Keltner Channel" in impl.GATED_FUTURE_INDICATORS
    assert "OBV" in impl.GATED_FUTURE_INDICATORS


def test_no_indicator_library_dependency_is_added() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower().splitlines()
    forbidden = {"ta", "pandas-ta", "pandas-ta-classic", "ta-lib", "talib", "vectorbt"}
    declared = {line.strip().split("==")[0] for line in requirements if line.strip()}
    assert forbidden.isdisjoint(declared)


def test_no_forbidden_research_actions_are_authorized_by_harness_manifest_flags() -> None:
    assert impl.MANIFEST_FLAGS["strategy_discovery_run"] is False
    assert impl.MANIFEST_FLAGS["backtests_run"] is False
    assert impl.MANIFEST_FLAGS["new_performance_metrics_computed"] is False
    assert impl.MANIFEST_FLAGS["provider_download"] is False
    assert impl.MANIFEST_FLAGS["intraday_data_used"] is False
    assert impl.MANIFEST_FLAGS["candidate_exhaustive_run"] is False
    assert impl.MANIFEST_FLAGS["paper_forward_activation"] is False
    assert impl.MANIFEST_FLAGS["real_money_recommendation"] is False


def test_manifest_flags_match_strict_scope_in_temp_evidence(tmp_path: Path) -> None:
    registry_path = tmp_path / impl.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        "registry:\n  schema_version: 1\n  research_only: true\nstrategies:\n"
        "- id: paper_forward_vm_quality_lowvol_proxy_v1\n  status: active\n"
        "- id: rc_donchian_breakout_risk_budget_v1\n  status: discovery_reject\n",
        encoding="utf-8",
    )
    roadmap_path = tmp_path / impl.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text("# Research Roadmap\n", encoding="utf-8")
    result = impl.run_indicator_validation_harness_implementation(tmp_path)
    manifest = json.loads(
        (Path(result["output_dir"]) / "indicator_validation_implementation_manifest.json").read_text(encoding="utf-8")
    )
    consistency = json.loads(
        (Path(result["output_dir"]) / "indicator_validation_implementation_consistency_check.json").read_text(
            encoding="utf-8"
        )
    )
    for key, expected in impl.MANIFEST_FLAGS.items():
        assert manifest[key] == expected
    assert consistency["consistency_passed"] is True
