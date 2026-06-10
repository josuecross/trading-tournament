# Correlation Diagnostics Audit

Audit decision: `correlation_available_but_diversification_not_fully_proven`

## 1. Are correlation diagnostics available?

Yes. They are available in `evidence/combination_lab/latest/combination_batch1_correlation_diagnostics.csv`.

## 2. Which correlations were calculated?

Diagnostics include correlation, rolling 60-day correlation mean, rolling 90-day correlation mean, stress-period correlation, and drawdown co-incidence rate versus:

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`
- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `BIL_cash_proxy`

## 3. Basis of calculation

The diagnostics are based on full-period standard equity-curve daily returns, not raw OHLCV.

## 4. Target-window co-movement

Target-window co-movement is unavailable. Stronger claims require that diagnostic.

## 5. Diversification claim

It is not valid to claim fully proven diversification.

It is valid to claim possible diversification or drawdown-budget improvement for the managed-futures blends, with caution.

## Key findings

`combo_plus_top2_50_50_v1`:

- correlation to combo: 0.925
- correlation to top2: 0.929
- duplicate risk is high

`combo_plus_managed_futures_80_20_v1`:

- correlation to combo: 0.956
- correlation to top2: 0.817
- drawdown co-incidence versus combo: 0.955
- possible drawdown-budget improvement, but not a clean diversifier versus combo

`top2_plus_managed_futures_80_20_v1`:

- correlation to combo: 0.778
- correlation to top2: 0.915
- drawdown co-incidence versus top2: 0.993
- more differentiated from combo than `combo_plus_managed_futures_80_20_v1`, but still highly tied to top2

## Required future diagnostics

Before stronger claims:

- target-window co-movement
- drawdown co-incidence by regime
- stress-period target/stop co-movement
- component contribution to target hits
- component contribution to drawdowns
- common-history sensitivity for managed-futures blends

