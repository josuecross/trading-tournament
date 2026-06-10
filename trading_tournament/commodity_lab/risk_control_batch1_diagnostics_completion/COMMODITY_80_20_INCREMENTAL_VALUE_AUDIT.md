# Commodity 80/20 Incremental Value Audit

candidate: `combo_plus_commodity_basket_80_20_v1`

audited_label: `possible_incremental_target_value`

secondary_label: `mostly_combo_with_small_commodity_tilt`

## Evidence Used

- target-window co-movement: available
- final-equity sleeve contribution: partially available
- drawdown overlap detail: available
- score delta versus base commodity: `+93.73`
- score delta versus combo: `+4.98`
- score delta versus top2: `-210.61`
- score delta versus SPY_200d: `-229.06`
- score delta versus GLD: `-156.62`
- correlation to combo: `0.962`
- correlation to GLD: `0.816`
- 90d/180d stop-hit rate: `0.0% / 0.0%`
- 90d/180d risk-budget usage: `45.8% / 52.8%`

## Incremental Target Value

The candidate created some incremental target windows:

- versus combo: 2 new 90d +300 windows, 0 new 90d +400 windows, 3 new 180d +300 windows, 3 new 180d +400 windows.
- versus top2: 4 new 90d +300 windows, 0 new 90d +400 windows, 5 new 180d +300 windows, 4 new 180d +400 windows.
- versus GLD: 3 new 90d +300 windows, 0 new 90d +400 windows, 3 new 180d +300 windows, 2 new 180d +400 windows.

This is real enough to avoid a duplicate-only label, but too small to justify candidate_exhaustive now.

## Component Contribution

At 90d target-hit windows, the combo sleeve dominated:

- 90d +300 hits: combo sleeve median about `$273.34`; commodity sleeve median about `$3.20`.
- 90d +400 hits: combo sleeve median about `$334.42`; commodity sleeve median about `$3.02`.

At 180d target-hit windows, the commodity sleeve helped more:

- 180d +300 hits: combo sleeve median about `$401.29`; commodity sleeve median about `$119.53`.
- 180d +400 hits: combo sleeve median about `$421.86`; commodity sleeve median about `$121.62`.

The 180d contribution is useful, but the result is still mostly combo sleeve with a commodity tilt rather than a clearly independent return engine.

## Drawdown And Diversification

The candidate materially reduced drawdown versus the base commodity row and stayed inside the risk budget. But worst 180d drawdown windows overlapped combo and GLD in the inspected worst samples. Together with correlation to combo of `0.962`, diversification is possible but not proven.

## Candidate_exhaustive Readiness

Not ready. The score improvement versus combo is only `+4.98`, and the row lags top2, SPY_200d, and GLD on the reported score. Given the high combo correlation and limited target-window independence, this should stay a watchlist row.

