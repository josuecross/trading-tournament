# Target Versus Drawdown Audit

Primary benchmarks:

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`

Secondary benchmarks:

- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `BIL_cash_proxy`
- `managed_futures_proxy_etf_trend_v1`

## combo_plus_top2_50_50_v1

This row did not create a compelling new return driver.

- 30/60/90-day +300/+400 target rates remain weak.
- 180d +300/+400 are 50.0% / 32.5%.
- 90d/180d stop-hit rates are 0.0% / 0.0%.
- 90d/180d worst drawdowns are -$450.67 / -$491.30.
- 90d/180d risk-budget usage is 75.1% / 81.9%.
- Correlation is high versus combo (0.925) and top2 (0.929).

Practical tradeoff: this looks more like a blend of already-known leaders than a distinct improvement. The audited verdict is `duplicate_or_near_duplicate`.

## combo_plus_managed_futures_80_20_v1

This row deserves the most nuanced interpretation.

- 30/60-day +300/+400 rates are 0.0% / 0.0%.
- 90d +300/+400 are 17.5% / 10.0%.
- 180d +300/+400 are 64.1% / 53.8%.
- 180d +600/+900/+1200 are 41.0% / 2.6% / 0.0%.
- 90d/180d stop-hit rates are 0.0% / 0.0%.
- 90d/180d worst drawdowns are -$321.11 / -$372.25.
- 90d/180d risk-budget usage is 53.5% / 62.0%.
- 90d median/p95 equity is $3,155.59 / $3,464.19.
- 180d median/p95 equity is $3,384.62 / $3,775.31.
- Stress degradation is 80.97.

Special finding: the managed-futures sleeve diluted short-horizon performance but improved 180-day stop-aware performance and drawdown-budget usage. That supports `short_history_watchlist`, not generic `too_slow`.

Limit: correlation to combo is high at 0.956, so diversification is possible but not proven.

## top2_plus_managed_futures_80_20_v1

This row also shows a short-horizon versus long-horizon split.

- 30/60-day +300/+400 rates are 0.0% / 0.0%.
- 90d +300/+400 are 15.0% / 10.0%.
- 180d +300/+400 are 69.2% / 56.4%.
- 180d +600/+900/+1200 are 33.3% / 0.0% / 0.0%.
- 90d/180d stop-hit rates are 0.0% / 0.0%.
- 90d/180d worst drawdowns are -$326.63 / -$402.75.
- 90d/180d risk-budget usage is 54.4% / 67.1%.
- Stress degradation is 59.53.

Practical tradeoff: the 180-day target rate is strong, but correlation to top2 is high at 0.915 and the managed-futures evidence is short-history. The audited verdict is `short_history_watchlist`.

## Overall target/drawdown decision

The audit does not approve candidate_exhaustive. It does conclude that the managed-futures combinations should not be collapsed into a generic too-slow bucket.

