# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260602_160225
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Experiments

Completed experiments: SPY_200d_trend_model, SPY_buy_hold, GLD_buy_hold, IEF_buy_hold, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1.

Blocked experiments: individual_stock_momentum.

Incomplete experiments: A_ETF_sector_momentum.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (52.0%)
- Highest exact +$400 probability: GLD_buy_hold (36.0%)
- Highest +$600 probability: GLD_buy_hold (20.0%)
- Highest +$900 probability: GLD_buy_hold (16.0%)
- Highest +$1200 probability: SPY_200d_trend_model (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: SPY_buy_hold ($3,212.48)
- Highest upside tail: GLD_buy_hold ($3,682.00)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: SPY_200d_trend_model
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: none.

High-upside but too-risky rows: none.

## Accounting Integrity Audit

- accounting_integrity_status: failed
- rolling_windows_rebased_to_3000: true
- buy_hold_reference_checks_passed: false
- combination_return_checks_passed: true
- failed_experiments: SPY_buy_hold, GLD_buy_hold, IEF_buy_hold, BIL_cash_proxy
- invalidated_rankings: SPY_200d_trend_model, SPY_buy_hold, GLD_buy_hold, IEF_buy_hold, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1
- profit_rankings_decision_usable: false

The previous pre-integrity profit league rankings are treated as invalidated because rolling windows had not yet proven fresh $3,000 rebasing. The current packet rebuilds every rolling window from window-local returns and blocks rankings if accounting integrity fails.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
