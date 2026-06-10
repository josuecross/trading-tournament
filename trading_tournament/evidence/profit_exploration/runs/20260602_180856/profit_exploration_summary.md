# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260602_180856
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Experiments

Completed experiments: GLD_buy_hold, combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_top2_v1, asset_class_tsmom_equal_weight_v1, SPY_200d_trend_model, IEF_buy_hold, BIL_cash_proxy, asset_class_tsmom_top1_v1, SPY_buy_hold.

Blocked experiments: individual_stock_momentum.

Incomplete experiments: A_ETF_sector_momentum.

Duplicate-skipped experiments: dual_momentum_SPY_GLD_IEF_v1.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: asset_class_tsmom_top1_v1 (56.0%)
- Highest exact +$400 probability: GLD_buy_hold (36.0%)
- Highest +$600 probability: GLD_buy_hold (20.0%)
- Highest +$900 probability: GLD_buy_hold (16.0%)
- Highest +$1200 probability: GLD_buy_hold (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: SPY_buy_hold ($3,214.08)
- Highest upside tail: GLD_buy_hold ($3,682.00)
- Best risk control: IEF_buy_hold
- Best overall profit/risk tradeoff: GLD_buy_hold
- Exact best +$300 family/experiment: asset_class_tsmom_top1_v1
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_SPY200d_GLD_50_50_v1.

High-upside but too-risky rows: GLD_buy_hold, asset_class_tsmom_top1_v1, SPY_buy_hold.

## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- combo_SPY200d_GLD_50_50_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 32.0%, +400 16.0%, stop 0.0%, median $3,117.99; main_risk=combination may dilute upside or inherit GLD drawdown; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=combo_SPY200d_GLD_50_50_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 24.0%, +400 16.0%, stop 0.0%, median $3,102.77; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_equal_weight_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus SPY_200d; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 20.0%, +400 16.0%, stop 0.0%, median $3,083.38; main_risk=diluted upside, regime whipsaw, and defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_equal_weight_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

## Accounting Integrity Audit

- accounting_integrity_status: passed
- rolling_windows_rebased_to_3000: true
- buy_hold_reference_checks_passed: true
- combination_return_checks_passed: true
- failed_experiments: none
- invalidated_rankings: none
- profit_rankings_decision_usable: true

The previous pre-integrity profit league rankings are treated as invalidated because rolling windows had not yet proven fresh $3,000 rebasing. The current packet rebuilds every rolling window from window-local returns and blocks rankings if accounting integrity fails.

## Current Research Conclusion

SPY_200d_trend_model remains the frozen paper-forward candidate. Profit exploration is a parallel research league only. Any new leading profit candidate requires separate candidate-exhaustive/Tier 2 review before it can affect future research status.

## Next Work

Continue comparing independent experiments by stop-aware profit, not target hits alone. A/B and A-sector rows remain incomplete until exact fresh-window streams are exposed. Blocked instruments remain blocked until gates pass.

No real-money recommendation is made.
