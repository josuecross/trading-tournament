# Future Variant Rules

These rules allow controlled exploration without uncontrolled parameter mining.

1. A failed result rejects the exact candidate variant, not necessarily the entire family.
2. A new variant is allowed only if it changes exactly one major dimension: symbol universe, timeframe, entry rule family, exit rule family, or risk-control model.
3. Do not test many parameter values after seeing results.
4. Each new variant must receive a new candidate ID.
5. Each new variant must have a written hypothesis before testing.
6. Each new variant must declare what failed in the prior test and why the new test is structurally different.
7. Do not reopen archived ETF-wrapper strategies unless the hypothesis is structurally different from the stopped ETF-wrapper track.
8. Do not use small cosmetic changes to bypass rejection.
9. Do not promote a family just because one variant works; validate the exact rule.
10. Do not reject an entire family just because one narrow variant fails.

Operational controls:

- No post-result threshold tuning.
- No grid search unless separately approved as a methodology research project, not as a candidate promotion path.
- No intraday demo review until data quality, slippage, spreads, and execution assumptions are independently documented.
- No candidate may move to candidate_exhaustive or paper-forward from this registry alone.
