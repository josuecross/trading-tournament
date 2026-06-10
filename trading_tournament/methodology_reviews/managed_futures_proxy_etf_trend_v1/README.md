# Managed-Futures Proxy Methodology Review

Subject: `managed_futures_proxy_etf_trend_v1`

This is a fund methodology review only. It does not implement a strategy, run a backtest, run Profit Exploration, add futures contract logic, activate paper-forward, or recommend real-money trading.

The review evaluates whether DBMF and KMLM are acceptable ETF/fund wrapper proxies for a future `research_sample` implementation prompt. DBMF and KMLM are reviewed as exchange-traded wrapper price series only. They are not treated as direct futures-contract strategy tests.

Data context used:

- DBMF: 1,780 rows, 2019-05-08 to 2026-06-05, quality pass.
- KMLM: 1,383 rows, 2020-12-02 to 2026-06-05, quality pass.
- Common DBMF/KMLM overlap: 2020-12-02 to 2026-06-05.
- Common overlap with cached SPY/BIL: 2020-12-02 to 2026-05-29.
- CTA, FMF, and WTMF were not downloaded.
- No raw OHLCV is included in this review or compact/advisor evidence.

Decision summary: a future research_sample implementation prompt is conditionally allowed only with explicit fund-wrapper proxy and short-history labels. No paper-forward or real-money action is approved.
