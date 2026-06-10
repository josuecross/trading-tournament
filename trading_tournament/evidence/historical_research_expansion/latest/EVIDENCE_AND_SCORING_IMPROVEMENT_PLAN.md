# Evidence And Scoring Improvement Plan

This plan corrects future reporting priorities without changing current scoring code.

## Required Reporting Corrections

1. Separate profit-seeking score from practical stop-aware score.
2. Penalize drawdown-budget usage before a -$600 breach.
3. Keep +$300/+$400 as hurdles, not final proof.
4. Report +$600/+$900/+$1200 but do not reward reckless upside without stop controls.
5. Report risk-budget usage percentage.
6. Report stress degradation.
7. Report benchmark-relative metrics.
8. Report whether performance comes from one asset, fund, sleeve, or regime.
9. Report if a strategy is too slow despite low drawdown.
10. Prevent target-rate-only ranking from dominating decisions.

## Preferred Future Score Layout

- profit-seeking target score
- stop-aware practical score
- drawdown budget score
- stress degradation penalty
- duplicate/correlation penalty
- concentration penalty
- evidence-tier cap

## Boundary

No scoring code is changed in this task. Any future reporting change should be isolated, tested, and labeled as a reporting update, not a strategy rule change.

