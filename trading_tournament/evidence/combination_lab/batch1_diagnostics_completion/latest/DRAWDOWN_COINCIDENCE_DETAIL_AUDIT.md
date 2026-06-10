# Drawdown Coincidence Detail Audit

Audit status: `available_window_level_overlap`

The diagnostics-only export added same-window drawdown overlap flags using a -5% drawdown threshold.

## 180-Day Drawdown Overlap

| combination | overlap vs combo | overlap vs top2 | overlap vs SPY_200d | strategy worst drawdown | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `combo_plus_top2_50_50_v1` | 85.0% | 80.0% | 72.5% | -$491.30 | highly overlapping drawdown timing |
| `combo_plus_managed_futures_80_20_v1` | 51.3% | 48.7% | 48.7% | -$372.25 | drawdowns are shallower and timing overlap is lower |
| `top2_plus_managed_futures_80_20_v1` | 48.7% | 61.5% | 59.0% | -$402.75 | shallower drawdowns, still tied to top2 timing |

## Interpretation

The managed-futures sleeve appears to reduce drawdown magnitude and some drawdown timing overlap. However, target-window diagnostics show it does not create independent target-hit windows.

This is risk-control value, not enough evidence for candidate_exhaustive.

## Unavailable Detail

Worst-5 drawdown window overlap is not separately exported as a ranked window table. It can be added later from the current detail CSV or from daily component contribution streams if a future prompt requests it.

