# Survivorship And Bias Risks

Using today's S&P 500, Nasdaq 100, or current liquid tickers across history is invalid for serious stock momentum research.

## Survivorship Bias

Today's surviving companies are not the same as the historical investable universe. Failed, acquired, merged, or delisted names may have had poor returns that disappear from a current-ticker test.

## Delisting Bias

Delisting losses can be severe. If a backtest simply drops delisted stocks, it can overstate returns and understate drawdown.

## Index Membership Lookahead

Using current index constituents for old dates leaks future information. A stock that is in today's index may not have been in the index historically.

## IPO Inclusion Bias

New listings need an IPO seasoning rule. Including IPO winners only after they become obvious can create lookahead-like selection.

## Current Liquidity Selection Bias

Selecting names based on today's liquidity excludes names that were liquid historically but later failed, and includes names that were not liquid in earlier periods.

## Split-Adjustment Issues

Bad split adjustment can create fake momentum or fake drawdowns. Stock data requires stricter corporate action audit than broad ETF data.

## Missing Bankruptcies

Bankruptcies and near-zero terminal values are essential for realistic stock momentum risk.

## Sector Composition Changes

Sector leadership changes through time. Static sector assumptions can distort ranking, diversification, and benchmark comparisons.

## Data Vendor Revision Risk

Vendors can revise historical prices, symbols, and corporate actions. Cache and audit hashes are useful, but they do not solve point-in-time membership.

## Conclusion

No stock momentum implementation should be approved until universe and delisting treatment are specified.

