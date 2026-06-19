from __future__ import annotations

import math

import pandas as pd

from strategy_integrity_core import (
    TARGET_300_EQUITY,
    benchmark_delta,
    evaluate_equity_curve,
    is_eligible,
    monthly_rebalance_mask,
    normalize_with_bil,
    prepare_indicators,
    rank_assets,
    sample_starts,
)


def synthetic_close(periods: int = 320) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=periods)
    return pd.DataFrame(
        {
            "UP": [100 + i for i in range(periods)],
            "DOWN": [500 - i * 0.5 for i in range(periods)],
            "FLAT": [100.0 for _ in range(periods)],
            "BIL": [100 + i * 0.01 for i in range(periods)],
        },
        index=dates,
    )


def test_200_day_sma_eligibility_correct() -> None:
    close = synthetic_close()
    indicators = prepare_indicators(close)
    date = close.index[220]
    assert is_eligible(indicators, date, "UP") is True
    assert is_eligible(indicators, date, "DOWN") is False


def test_126_day_return_and_60_day_volatility_correct() -> None:
    close = synthetic_close()
    indicators = prepare_indicators(close)
    date = close.index[200]
    expected_return = close.loc[date, "UP"] / close.iloc[74]["UP"] - 1.0
    assert math.isclose(indicators["ret126"].loc[date, "UP"], expected_return)
    expected_vol = close["UP"].pct_change().fillna(0.0).rolling(60).std().loc[date]
    assert math.isclose(indicators["vol60"].loc[date, "UP"], expected_vol)


def test_monthly_rebalance_dates_correct() -> None:
    dates = pd.bdate_range("2024-01-25", periods=30)
    mask = monthly_rebalance_mask(dates)
    rebalances = [date for date, is_rebalance in mask.items() if is_rebalance]
    assert rebalances[0] == dates[0]
    assert pd.Timestamp("2024-02-01") in rebalances


def test_bil_fallback_and_weights_sum_to_one() -> None:
    weights = normalize_with_bil({"UP": 0.4})
    assert weights["BIL"] == 0.6
    assert math.isclose(sum(weights.values()), 1.0)
    assert normalize_with_bil({}) == {"BIL": 1.0}


def test_target_before_stop_logic_variants() -> None:
    target_first = evaluate_equity_curve([3000, TARGET_300_EQUITY + 1, 2500])
    stop_first = evaluate_equity_curve([3000, 2390, 3400])
    neither = evaluate_equity_curve([3000, 3020, 3010])
    target_after_stop = evaluate_equity_curve([3000, 2390, 3310])
    recovery = evaluate_equity_curve([3000, 2800, 3100, 3050])
    flat = evaluate_equity_curve([3000, 3000, 3000])
    assert target_first["target_300_before_stop"] is True
    assert stop_first["target_300_before_stop"] is False
    assert neither["target_300_before_stop"] is False
    assert target_after_stop["target_300_after_stop"] is True
    assert recovery["max_drawdown"] == -200
    assert flat["stop_hit"] is False


def test_benchmark_delta_sign_and_missing_benchmark() -> None:
    available = benchmark_delta([3100, 3200], [3000, 3050])
    missing = benchmark_delta([3100, 3200], None)
    assert available["comparison_status"] == "available"
    assert available["delta_median_final_equity"] == 125.0
    assert missing["comparison_status"] == "unavailable"
    assert missing["delta_median_final_equity"] == ""


def test_sample_windows_deterministic() -> None:
    first = sample_starts(1000, 180)
    second = sample_starts(1000, 180)
    assert first == second
    assert len(first) <= 180


def test_no_lookahead_signal_generation_convention() -> None:
    close = synthetic_close()
    indicators = prepare_indicators(close)
    signal_date = close.index[250]
    next_day = close.index[251]
    ranked_at_signal = rank_assets(indicators, signal_date, ["UP", "DOWN"])
    ranked_at_trade_day = rank_assets(indicators, next_day, ["UP", "DOWN"])
    assert ranked_at_signal[0][0] == "UP"
    assert ranked_at_trade_day[0][1] != ranked_at_signal[0][1]
