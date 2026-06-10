# Risk-Control Batch 1 Review

The base `commodity_basket_tsmom_top2_v1` screen showed strong +300/+400 target power but breached the -$600 drawdown budget at 90d and 180d. The base verdict should therefore be interpreted as `research_sample_candidate_risk_budget_breach`, not as a generic research_sample candidate.

This batch asks whether simple fixed risk controls can reduce drawdown while retaining meaningful target power:

- `commodity_basket_tsmom_top2_200d_filter_v1`: adds a close > 200-day SMA eligibility filter.
- `commodity_basket_tsmom_top2_half_bil_v1`: fixes 50% to the base commodity sleeve and 50% to BIL.
- `combo_plus_commodity_basket_80_20_v1`: blends 80% historical combo component with 20% base commodity sleeve.

All rows are exploratory ETF/fund-wrapper evidence only. No row is paper-forward ready from this batch.

