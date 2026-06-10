# Combination Batch 1 Diagnostics Spec

Required target and risk diagnostics:

- Target ladder: +300, +400, +600, +900, +1200.
- 30/60/90/180 target-before-stop rates.
- Stop-hit rates.
- Worst drawdown.
- Risk-budget usage percentage.
- Median stop-enforced equity.
- P95 stop-enforced equity.
- Stress degradation.

Required combination diagnostics:

- Component allocation share.
- Sleeve contribution if available.
- Max single-sleeve contribution.
- Correlation versus combo.
- Correlation versus top2.
- Correlation versus SPY_200d.
- Correlation versus GLD.
- Correlation versus BIL.
- Drawdown co-incidence if available.
- Target-window co-movement if available.
- Duplicate/correlation warning.
- Short-history warning for managed-futures combinations.

If correlation diagnostics cannot be calculated from generated daily equity returns, write `unavailable`. Do not infer correlation from strategy labels.

