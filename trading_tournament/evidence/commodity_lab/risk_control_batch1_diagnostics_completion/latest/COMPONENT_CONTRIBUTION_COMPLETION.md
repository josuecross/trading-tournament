# Component Contribution Completion

component_contribution_status: `partial_available_final_equity_window_contribution`

The diagnostics-only export can compute fixed-sleeve final-equity contribution for combo-style rows. It still does not export an exact daily component contribution path to target-threshold timing, worst drawdown path, or recovery windows.

## combo_plus_commodity_basket_80_20_v1

Fixed sleeves:

- Primary sleeve: `combo_SPY200d_GLD_50_50_v1`
- Secondary sleeve: `commodity_basket_tsmom_top2_v1`

Across all sampled windows, final-equity contribution was available for 157 rows:

- combo sleeve median contribution: about `$75.94`
- commodity sleeve median contribution: about `$8.30`
- combo sleeve mean contribution: about `$117.90`
- commodity sleeve mean contribution: about `$33.80`

Target-hit windows:

- 90d +300 hits: combo sleeve median contribution about `$273.34`; commodity sleeve median contribution about `$3.20`.
- 90d +400 hits: combo sleeve median contribution about `$334.42`; commodity sleeve median contribution about `$3.02`.
- 180d +300 hits: combo sleeve median contribution about `$401.29`; commodity sleeve median contribution about `$119.53`.
- 180d +400 hits: combo sleeve median contribution about `$421.86`; commodity sleeve median contribution about `$121.62`.

Interpretation:

- At 90d, target hits are mostly combo-sleeve driven. The commodity sleeve contribution is small in the sampled target windows.
- At 180d, the commodity sleeve becomes more meaningful, but the combo sleeve still dominates the median target-hit contribution.
- Exact attribution of the target-threshold crossing is unavailable because the export does not yet include component daily contribution streams.
- Exact component contribution to worst drawdown is unavailable. The worst-window final-contribution view suggests the commodity sleeve can contribute positive final-equity return in weak drawdown windows, but that is not the same as path-level drawdown attribution.

## commodity_basket_tsmom_top2_half_bil_v1

Fixed sleeves:

- Primary sleeve: `commodity_basket_tsmom_top2_v1`
- Secondary sleeve: `BIL_cash_proxy`

Across all sampled windows, final-equity contribution was available for 157 rows:

- commodity sleeve median contribution: about `$19.80`
- BIL sleeve median contribution: about `$4.07`
- commodity sleeve mean contribution: about `$82.00`
- BIL sleeve mean contribution: about `$8.81`

Target-hit windows:

- 90d +300 hits: commodity sleeve median contribution about `$338.93`; BIL median contribution about `$20.70`.
- 90d +400 hits: commodity sleeve median contribution about `$364.05`; BIL median contribution about `$20.70`.
- 180d +300 hits: commodity sleeve median contribution about `$424.50`; BIL median contribution about `$41.70`.
- 180d +400 hits: commodity sleeve median contribution about `$445.17`; BIL median contribution about `$41.90`.

Interpretation:

- BIL drove drawdown reduction by scaling down commodity exposure, but target hits still depended on the commodity sleeve.
- The defensive scaling diluted target rates; it is useful as a risk-control reference row, not as an additive target candidate.

## Unavailable Fields

Still unavailable:

- component contribution to the exact +300/+400 crossing day,
- component contribution to the worst drawdown path,
- component contribution to recovery windows,
- daily component contribution stream per rolling window.

Future fields needed:

- `component_daily_return_contribution`
- `component_daily_equity_contribution`
- `component_drawdown_path_contribution`
- `component_recovery_path_contribution`
- target-crossing day by component

