# Combo Versus SPY_200d

## Summary

`combo_SPY200d_GLD_50_50_v1` should be evaluated as a risk-controlled challenger, not as a pure target-rate leader.

## Target Rates

The combo did not beat `SPY_200d_trend_model` on raw +300 or +400 target rates at the key 90-day or 180-day horizons.

| Horizon | Metric | Combo | SPY_200d | Leader |
|---|---|---:|---:|---|
| 90d | +300 before stop | 20.9% | 24.2% | SPY_200d |
| 90d | +400 before stop | 9.2% | 10.0% | SPY_200d |
| 180d | +300 before stop | 48.1% | 54.0% | SPY_200d |
| 180d | +400 before stop | 31.5% | 38.5% | SPY_200d |

## Risk Control

The combo had superior drawdown and stop behavior.

| Horizon | Metric | Combo | SPY_200d | Better |
|---|---|---:|---:|---|
| 90d | stop-hit rate | 0.0% | 0.5% | Combo |
| 90d | worst drawdown | -$452.23 | -$661.82 | Combo |
| 90d | risk-budget use | 0.75 | 1.10 | Combo |
| 180d | stop-hit rate | 0.0% | 4.9% | Combo |
| 180d | worst drawdown | -$516.49 | -$743.40 | Combo |
| 180d | risk-budget use | 0.86 | 1.24 | Combo |

## Equity Outcomes

The combo improved 90-day median stop-enforced equity and 180-day p95 equity, while SPY_200d had slightly better 90-day p95.

## Conclusion

The combo does not replace SPY_200d on target speed. It deserves paper-forward review as a potential risk-controlled companion observation that may reduce stop/drawdown behavior while preserving meaningful upside.

