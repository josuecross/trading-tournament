# Cost And Runtime Assessment

## Data Cost

Credible survivorship-free stock data may require paid commercial or academic access. Free current-ticker data is not enough for serious evidence.

## Storage

A stock universe can contain thousands of symbols and many delisted names. Storage requirements may be materially larger than ETF data.

## Runtime

Rolling-window validation across many stocks can be expensive. Gate 2 must estimate runtime for full-period, sampled, and exhaustive finalist validation.

## Implementation Complexity

Complexity is high because the project would need point-in-time universe handling, corporate actions, delisting treatment, liquidity filters, earnings policy, benchmarks, and stock-specific execution assumptions.

## Maintenance Burden

Maintaining stock data quality is more demanding than maintaining ETF data. Symbol changes, mergers, delistings, and vendor revisions require ongoing audit work.

## Licensing

Commercial data may restrict redistribution, caching, or publication of derived data. Licensing must be reviewed before implementation.

## Scope Assessment

If credible data is too expensive or unavailable, serious implementation should be deferred. A toy demo may teach mechanics, but it must not be presented as validation.

