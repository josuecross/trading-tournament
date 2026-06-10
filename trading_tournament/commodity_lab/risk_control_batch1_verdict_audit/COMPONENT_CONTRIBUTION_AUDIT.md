# Component Contribution Audit

## Status

component_contribution_status: `partial_unavailable_exact_path_contribution`

The packet reports allocation share and sleeve concentration, but it does not export exact component return contributions by rolling window, target window, drawdown path, or recovery window.

## `combo_plus_commodity_basket_80_20_v1`

Available:

- combo sleeve allocation share: 80.0%
- commodity wrapper allocation share: 11.2%
- BIL/cash allocation share: 17.7%
- max product/sleeve concentration: 80.0%
- daily equity return correlation to combo: 0.962

Unavailable:

- combo sleeve contribution to final equity
- commodity sleeve contribution to final equity
- combo sleeve contribution in +300/+400 windows
- commodity sleeve contribution in +300/+400 windows
- commodity sleeve contribution to worst drawdown
- whether commodity sleeve created target hits rather than merely tilting the combo

Audit: current evidence suggests the row is mostly combo sleeve with a small commodity tilt. The 20% commodity sleeve may have modestly improved stop-aware score, but exact attribution is unavailable and should not be inferred from weights alone.

## `commodity_basket_tsmom_top2_half_bil_v1`

Available:

- BIL/cash allocation share: 68.8%
- commodity wrapper allocation share: 28.0%
- max wrapper concentration: 8.8%
- 90d/180d stop rate: 0.0% / 0.0%

Unavailable:

- exact commodity sleeve contribution
- exact BIL contribution
- target-window contribution split
- drawdown/recovery contribution split

Audit: BIL clearly reduced risk exposure at the portfolio-design level, but exact return attribution is unavailable. The result is defensive and diluted, not proof of additive commodity alpha.

## Required Future Fields

Future diagnostics need component daily return streams, window IDs, target-hit flags, drawdown start/end, recovery start/end, and per-window component return/drawdown/recovery contribution fields.
