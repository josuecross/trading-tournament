# Data Availability And Gate Review

| Family | data likely already cached | public ETF/fund data | provider/API needed | terms/security needed | raw data exclusion issues | local cache feasibility | sample history likely long enough | short-history risk | $3,000 suitability | no leverage/margin/shorting requirement | likely runtime | current engine can test after review |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| commodity_basket_etf_momentum_v1 | unknown | likely | not necessarily beyond existing ETF data path, after review | product/provider terms still reviewed before download | raw OHLCV excluded from advisor evidence | likely | mixed; symbols have different inceptions | medium | plausible with ETFs, but product spreads/fees matter | yes if long-only ETF/fund wrappers only | low/medium | likely after product/data review |
| treasury_duration_trend_rotation_v1 | partial/unknown | likely | not necessarily beyond existing ETF data path | standard ETF data review | raw OHLCV excluded | likely | likely long for SHY/IEF/TLT/BIL | low/medium | high operational fit, lower target speed | yes | low | likely after target-potential review |
| crypto_spot_tsmom_tier2_review_v1 | no serious Tier 2 cache | not ETF/fund-only unless spot ETF proxy reviewed | yes, exchange or crypto vendor if direct spot | high | raw data/security concerns | possible but gated | mixed | high | problematic for small account/friction | only if spot/no leverage | medium/high | no until Tier 2 framework |
| volatility_risk_proxy_review_v1 | unknown | likely for products | ETF/fund data possible, but futures wrapper mechanics matter | product-risk terms review | wrapper/futures-roll evidence issues | likely | mixed and product-specific | medium/high | risky | only if excluding leveraged/inverse/futures logic | low/medium | no until product-risk review |
| macro_regime_filter_review_v1 | maybe existing benchmark data | possible | not necessarily | methodology review more important | low if using existing evidence | high | depends on features | low/medium | indirect | yes if reporting-only first | low | only after strict methodology gate |
| factor_or_sector_extension_review_v1 | partial/likely | likely | not necessarily | standard ETF data review | low | high | likely adequate for many ETFs | medium | plausible | yes | low | yes after anti-duplication review |

## Gate Ranking

1. Commodity basket ETF momentum: best balance of accessibility, novelty, and reviewable product risks.
2. Treasury duration trend rotation: easiest data path, but likely lower target potential.
3. Factor/sector extension: accessible, but duplicate-beta risk is high.
4. Macro regime filter: design risk and tuning risk.
5. Crypto Tier 2: separate, high-risk, provider/exchange gated.
6. Volatility proxy: product-risk and futures-wrapper concerns are too high for next step.

## No-Action Boundary

No family should run immediately from this review. No data is downloaded in this task. No provider API is called. No implementation or backtest is approved.
