# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260602_204820
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Experiments

Completed experiments: asset_class_tsmom_top2_v1, combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_equal_weight_v1, GLD_buy_hold, SPY_200d_trend_model, BIL_cash_proxy, SPY_buy_hold.

Blocked experiments: none.

Incomplete experiments: none.

Duplicate-skipped experiments: none.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (42.2%)
- Highest exact +$400 probability: GLD_buy_hold (28.1%)
- Highest +$600 probability: GLD_buy_hold (12.5%)
- Highest +$900 probability: GLD_buy_hold (2.7%)
- Highest +$1200 probability: GLD_buy_hold (0.2%)

## Profit And Risk

- Highest median stop-enforced equity: SPY_buy_hold ($3,154.11)
- Highest upside tail: GLD_buy_hold ($3,646.15)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: asset_class_tsmom_top2_v1
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: combo_SPY200d_GLD_50_50_v1.

High-upside but too-risky rows: SPY_buy_hold.


## Finalist Candidate-Exhaustive Comparison

- mode: candidate_exhaustive
- requested finalists: combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_top2_v1, asset_class_tsmom_equal_weight_v1, SPY_200d_trend_model, GLD_buy_hold, SPY_buy_hold, BIL_cash_proxy
- all_possible_30_60_90_180_standard_and_stress_completed: true
- incomplete_or_nonfinal_finalists: none

90-day standard finalist metrics:

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.90; p95 $3,054.96; worst drawdown $-23.47
- GLD_buy_hold: +300 42.2%; +400 28.1%; +600 12.5%; +900 2.7%; +1200 0.2%; stop 5.2%; median $3,109.70; p95 $3,646.15; worst drawdown $-879.09
- SPY_200d_trend_model: +300 24.2%; +400 10.0%; +600 1.0%; +900 0.0%; +1200 0.0%; stop 0.5%; median $3,097.12; p95 $3,418.41; worst drawdown $-661.82
- SPY_buy_hold: +300 31.9%; +400 15.2%; +600 3.4%; +900 0.5%; +1200 0.1%; stop 6.4%; median $3,154.11; p95 $3,503.06; worst drawdown $-1,330.23
- asset_class_tsmom_equal_weight_v1: +300 14.9%; +400 5.2%; +600 0.4%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,096.21; p95 $3,343.26; worst drawdown $-563.55
- asset_class_tsmom_top2_v1: +300 21.5%; +400 9.4%; +600 0.9%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,098.03; p95 $3,396.01; worst drawdown $-579.66
- combo_SPY200d_GLD_50_50_v1: +300 20.9%; +400 9.2%; +600 1.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,107.86; p95 $3,414.35; worst drawdown $-452.23

Direct comparison answers:

- combo beat SPY_200d on +300: no (combo_SPY200d_GLD_50_50_v1 20.9% vs SPY_200d_trend_model 24.2%).
- combo beat SPY_200d on +400: no (combo_SPY200d_GLD_50_50_v1 9.2% vs SPY_200d_trend_model 10.0%).
- combo beat SPY_200d on +600: yes (combo_SPY200d_GLD_50_50_v1 1.1% vs SPY_200d_trend_model 1.0%).
- combo beat SPY_200d on +900: no (combo_SPY200d_GLD_50_50_v1 0.0% vs SPY_200d_trend_model 0.0%).
- combo beat SPY_200d on +1200: no (combo_SPY200d_GLD_50_50_v1 0.0% vs SPY_200d_trend_model 0.0%).
- combo had higher median stop-enforced equity: yes (combo_SPY200d_GLD_50_50_v1 $3,107.86 vs SPY_200d_trend_model $3,097.12).
- combo had lower stop-hit rate: yes (combo_SPY200d_GLD_50_50_v1 0.0% vs SPY_200d_trend_model 0.5%).
- combo had better worst drawdown: yes (combo_SPY200d_GLD_50_50_v1 $-452.23 vs SPY_200d_trend_model $-661.82).
- asset_class_tsmom_top2 beat SPY_200d on combined score: yes (asset_class_tsmom_top2_v1 67.0481 vs SPY_200d_trend_model 44.1406).
- asset_class_tsmom_top2 beat combo on combined score: yes (asset_class_tsmom_top2_v1 67.0481 vs combo_SPY200d_GLD_50_50_v1 66.7705).
- asset_class_tsmom_equal_weight beat SPY_200d on combined score: yes (asset_class_tsmom_equal_weight_v1 48.6538 vs SPY_200d_trend_model 44.1406).
- asset_class_tsmom_equal_weight beat combo on combined score: no (asset_class_tsmom_equal_weight_v1 48.6538 vs combo_SPY200d_GLD_50_50_v1 66.7705).

Finalist leaders:

- Best +300 rate: GLD_buy_hold (42.2%).
- Best +400 rate: GLD_buy_hold (28.1%).
- Best +600 rate: GLD_buy_hold (12.5%).
- Best +900 rate: GLD_buy_hold (2.7%).
- Best +1200 rate: GLD_buy_hold (0.2%).
- Highest median stop-enforced equity: SPY_buy_hold ($3,154.11).
- Best p95 upside tail: GLD_buy_hold ($3,646.15).
- Best drawdown/risk control: BIL_cash_proxy (stop 0.0%; worst drawdown $-23.47).
- Best overall profit/risk tradeoff: asset_class_tsmom_top2_v1 (67.0481).

Interpretation:

- GLD_buy_hold remains high-upside/high-risk if its stop-hit or drawdown penalty dominates the combined score.
- SPY_buy_hold remains too risky if its drawdown/stop behavior overwhelms target upside.
- BIL_cash_proxy remains the defensive benchmark and is too slow for the profit target ladder.
- Promotion-review rows: asset_class_tsmom_top2_v1.
- No finalist is automatically paper-forward ready, and SPY_200d_trend_model remains the frozen paper-forward observation unless a separate promotion process changes it.
- No real-money recommendation is made.


## Candidate Exhaustive Queue

Candidate-exhaustive mode was run for this packet. The text below is a promotion-review reminder, not a paper-forward promotion.

Candidate-exhaustive validation ran for the requested finalist set. Use promotion_review outside this task for any future status decision; no row is paper-forward ready from this packet.

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
