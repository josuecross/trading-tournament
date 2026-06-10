# Goal Audit

The challenge target is simple:

- +$300 from $3,000 = +10%.
- +$400 from $3,000 = +13.3%.
- -$600 risk budget = -20%.

The +$300/+400 target should be treated as a challenge metric, not as proof of a reliable income system.

## Why The Target Is Useful

The target is arbitrary, but useful. It forces the project to evaluate time-to-target, drawdown, execution cost, and opportunity cost instead of only asking whether a strategy eventually made money over a long history.

## Why The Target Can Mislead

A full-period backtest can reach +$300 once and still be unsuitable for a 30-, 60-, 90-, or 180-day challenge. If the target is reached after a stop would have ended the project, the target does not count for the chosen risk interpretation.

## Target-Before-Stop Probability

The central question is not "did it ever hit +$300?" The central question is "how often did it hit +$300 or +$400 before the project stop across independent rolling windows?"

## Time-To-Target

The time horizon matters. A +$300 target reached after five years is not the same as a +$300 target reached within 90 trading days. Future reports should separate target hit, target-before-stop, and target trading days.

## Stress Slippage

Stress slippage matters because a strategy that barely works under ideal fills may fail under realistic execution. If stress slippage materially reduces final equity or rolling target rates, the strategy is execution-sensitive.

## Benchmark-Relative Performance

If a strategy reaches the target only because the benchmark had a strong period, the evidence may be beta rather than strategy edge. Benchmark-relative performance is essential.

## Evidence The Target Is Plausible

Evidence would include a meaningful rolling target-before-stop rate across standard and stress slippage, stable performance across market regimes, drawdowns inside the risk budget, reasonable turnover, clear benchmark improvement, and no dependence on a few lucky trades or symbols.

## Evidence The Target Is Unrealistic

The target is unrealistic for a strategy family if rolling windows rarely hit +$300 before stop, +$400 is almost never reached, stress slippage destroys results, drawdowns regularly exceed -$600, or outcomes depend on fragile assumptions.
