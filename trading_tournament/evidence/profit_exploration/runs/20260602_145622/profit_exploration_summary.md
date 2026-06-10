# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260602_145622
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Experiments

Completed experiments: combo_SPY200d_GLD_BIL_60_30_10_v1, IEF_buy_hold, multi_asset_top2_momentum_v1, combo_SPY200d_GLD_50_50_v1, SPY_200d_trend_model, IEF_200d_trend_model_v1, SPY_buy_hold, GLD_200d_trend_model_v1, SPY_GLD_IEF_dual_momentum_v1, GLD_SPY_rotation_v1, SPY_GLD_dual_momentum_v1, BIL_cash_proxy, GLD_buy_hold.

Blocked experiments: individual_stock_momentum, options_directional, options_premium, futures_trend_following, forex_momentum_carry, intraday_orb, volatility_products, event_news_momentum.

Incomplete experiments: A_ETF_sector_momentum, current_no_cash_proxy_alpha_AB.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (100.0%)
- Highest exact +$400 probability: GLD_buy_hold (98.8%)
- Highest +$600 probability: GLD_buy_hold (98.4%)
- Highest +$900 probability: GLD_buy_hold (98.2%)
- Highest +$1200 probability: GLD_buy_hold (97.0%)

## Profit And Risk

- Highest median stop-enforced equity: SPY_buy_hold ($6,849.54)
- Highest upside tail: SPY_buy_hold ($20,022.48)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: combo_SPY200d_GLD_BIL_60_30_10_v1
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_SPY200d_GLD_BIL_60_30_10_v1, combo_SPY200d_GLD_50_50_v1.

High-upside but too-risky rows: multi_asset_top2_momentum_v1, combo_SPY200d_GLD_50_50_v1, SPY_200d_trend_model, SPY_buy_hold, GLD_200d_trend_model_v1, SPY_GLD_IEF_dual_momentum_v1, GLD_SPY_rotation_v1, SPY_GLD_dual_momentum_v1, GLD_buy_hold.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
