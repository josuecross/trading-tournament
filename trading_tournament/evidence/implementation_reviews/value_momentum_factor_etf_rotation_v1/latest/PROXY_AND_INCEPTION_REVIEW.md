# Proxy And Inception Review

This review uses local cached-data metadata and the completed acquisition quality packet. It does not include raw market rows and does not download data in this review update.

| symbol | factor_role | intended_use | expected_return_driver | cached_locally | first_cached_date | last_cached_date | row_count | overlap_with_SPY_BIL | enough_history_for_rolling_windows | inception_or_history_risk | proxy_quality | notes |
|---|---|---|---|---|---|---|---:|---|---|---|---|---|
| MTUM | momentum | Momentum proxy | ETF momentum factor tilt | true | 2013-04-18 | 2026-06-04 | 3303 | 2013-04-18 to 2026-05-29 | true | medium_to_high | moderate | Core momentum proxy passed quality checks, but its 2013 start limits stress-regime coverage. |
| VLUE | value | Value proxy option | ETF value factor tilt | true | 2013-04-18 | 2026-06-04 | 3303 | 2013-04-18 to 2026-05-29 | true | medium_to_high | moderate | Usable value proxy, but it has shorter history than VTV. |
| VTV | value | Preferred first value proxy | Large-cap value equity tilt | true | 2007-01-03 | 2026-06-04 | 4886 | 2007-05-30 to 2026-05-29 | true | low_to_medium | moderate_to_strong | Preferred over VLUE for first implementation because it has materially longer local history. |
| QUAL | quality | Quality proxy | Quality factor tilt | true | 2013-07-18 | 2026-06-04 | 3240 | 2013-07-18 to 2026-05-29 | true | medium_to_high | moderate | Quality is central to the candidate thesis, but QUAL sets the all-proxy common overlap start. |
| USMV | low_volatility | Preferred defensive equity proxy | Minimum-volatility equity tilt | true | 2011-10-20 | 2026-06-04 | 3676 | 2011-10-20 to 2026-05-29 | true | medium | moderate | Preferred first low-volatility proxy due broad minimum-volatility construction and sufficient history. |
| SPLV | low_volatility | Low-volatility fallback | Low-volatility equity tilt | true | 2011-05-05 | 2026-06-04 | 3793 | 2011-05-05 to 2026-05-29 | true | medium | moderate | Usable fallback or future diagnostic, but omitted from first fixed rule to avoid extra variants. |
| SPY | broad_market | Benchmark and equity baseline | Broad U.S. equity beta | true | 2007-01-03 | 2026-05-29 | 4882 | 2007-05-30 to 2026-05-29 | true | low | strong | Cached broad-market benchmark; not refreshed in the acquisition run. |
| BIL | cash_treasury | Cash/Treasury fallback | Short Treasury/cash-like return | true | 2007-05-30 | 2026-05-29 | 4781 | 2007-05-30 to 2026-05-29 | true | low_to_medium | moderate_to_strong | Cached cash/Treasury proxy; not refreshed in the acquisition run. |

## Inception Review Answers

1. Is the common overlap from 2013-07-18 long enough? Yes for a future research_sample implementation. It is not enough for strong final claims because it omits the 2008 crisis and other earlier regimes available to SPY/BIL.
2. Are MTUM/VLUE/QUAL histories short relative to SPY/BIL? Yes. MTUM and VLUE start in 2013, and QUAL starts in 2013-07. SPY/BIL have materially longer local histories.
3. Is 2013 onward too short for strong claims? Yes. It is acceptable for exploratory research_sample evidence but must be labeled limited by inception history.
4. Should VTV be preferred over VLUE? Yes for the first implementation, because VTV has a 2007 local start and reduces value-proxy inception risk.
5. Should USMV be preferred over SPLV or vice versa? Use USMV in the first fixed rule because it is a broad minimum-volatility proxy with sufficient history. SPLV has slightly earlier local history but should remain a fallback or future diagnostic.
6. Should QUAL be included despite shorter history? Yes for the first fixed rule, with an explicit inception-risk warning, because quality is a core part of the candidate's intended return driver.
7. Should the first implementation use fewer proxies to maximize overlap? Yes. The first implementation should use MTUM, VTV, QUAL, USMV, SPY, and BIL, excluding VLUE and SPLV substitutes to avoid variants and maximize interpretability.
8. What limitations remain? ETF factor proxies may not match academic factor portfolios, the common overlap starts in 2013, and all risky assets are U.S. equity ETFs that may mostly express equity beta.
