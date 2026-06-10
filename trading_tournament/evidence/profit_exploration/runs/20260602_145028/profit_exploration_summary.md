# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260602_145028
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Experiments

Completed experiments: combo_SPY200d_GLD_50_50_v1, SPY_200d_trend_model, BIL_cash_proxy, GLD_buy_hold.

Blocked experiments: individual_stock_momentum.

Incomplete experiments: A_ETF_sector_momentum.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (100.0%)
- Highest exact +$400 probability: combo_SPY200d_GLD_50_50_v1 (92.0%)
- Highest +$600 probability: GLD_buy_hold (92.0%)
- Highest +$900 probability: GLD_buy_hold (92.0%)
- Highest +$1200 probability: GLD_buy_hold (80.0%)

## Profit And Risk

- Highest median stop-enforced equity: GLD_buy_hold ($6,093.26)
- Highest upside tail: GLD_buy_hold ($21,422.22)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: combo_SPY200d_GLD_50_50_v1
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: combo_SPY200d_GLD_50_50_v1

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_SPY200d_GLD_50_50_v1.

High-upside but too-risky rows: SPY_200d_trend_model, GLD_buy_hold.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
