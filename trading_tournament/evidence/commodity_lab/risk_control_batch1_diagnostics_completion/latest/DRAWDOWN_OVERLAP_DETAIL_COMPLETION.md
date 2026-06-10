# Drawdown Overlap Detail Completion

drawdown_overlap_status: `available`

The diagnostics-only export added worst drawdown start/end fields and overlap flags/rates versus base commodity, combo, top2, SPY_200d, and GLD.

## Summary

For each candidate, the export contains:

- `worst_drawdown_window_id_if_available`
- `worst_drawdown_start_if_available`
- `worst_drawdown_end_if_available`
- `drawdown_overlap_vs_combo_if_available`
- `drawdown_overlap_rate_vs_combo_if_available`
- equivalent fields versus top2, SPY_200d, GLD, and base commodity

## combo_plus_commodity_basket_80_20_v1

Worst 180d sampled windows had drawdowns around `-$316.93` to `-$312.53`. Their worst drawdown window was repeatedly `2026-01-29_to_2026-03-23`.

In those worst examples:

- overlap versus combo: `true`
- overlap rate versus combo: `1.0`
- overlap versus GLD: `true`
- overlap rate versus GLD: `1.0`

Interpretation:

- The 80/20 commodity sleeve reduced drawdown magnitude versus the base commodity row and stayed well inside the -$600 risk budget.
- It did not clearly create independent drawdown timing in the worst 180d samples; the bad periods overlapped the combo/GLD drawdown window.
- The risk improvement is meaningful in magnitude, but it is not proven drawdown-timing diversification. It looks like lower-risk blending with a small commodity tilt.

## commodity_basket_tsmom_top2_half_bil_v1

Half-BIL reduced drawdown magnitude below the -$600 budget:

- 90d worst drawdown: about `-$307.74`
- 180d worst drawdown: about `-$319.65`

Interpretation:

- The risk reduction is real in magnitude.
- The mechanism is mostly defensive scaling and BIL exposure, not independent target generation.

## commodity_basket_tsmom_top2_200d_filter_v1

The 200d filter retained the base commodity drawdown breach:

- 90d worst drawdown: about `-$680.67`
- 180d worst drawdown: about `-$718.24`

Interpretation:

- The filter did not reduce risk-budget usage below 100%.
- It remains over budget and does not qualify for candidate_exhaustive review.

## Candidate_exhaustive Relevance

combo_plus_commodity_basket_80_20_v1 has acceptable stop/drawdown behavior, but the overlap detail does not prove independent drawdown diversification. It supports watchlist-only status unless future evidence shows stronger target-window independence or a larger score improvement versus the combo benchmark.

