# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260604_055402
- mode: profit exploration
- account: independent $3,000 simulated account per experiment
- +$300/+400: minimum and strong success hurdles, not the final objective
- objective: highest stop-aware profit potential beyond +$400 while respecting the -$600 stop boundary

## Run Validation Scope

- run_validation_scope: all_horizons
- reduced_validation: false
- reduced_validation_reason: none
- selected_horizons: 30,60,90,180
- omitted_horizons: none
- selected_horizons_completed: true
- full_horizon_validation_completed: true
- candidate_exhaustive_completed: true
- final_validation_completed: true
- sampled_results_are_final: true

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


## Full Candidate-Exhaustive Finalist Validation Comparison

- mode: candidate_exhaustive
- run_validation_scope: all_horizons
- requested finalists: asset_class_tsmom_top2_v1, combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_equal_weight_v1, GLD_buy_hold, SPY_200d_trend_model, BIL_cash_proxy, SPY_buy_hold
- selected_horizons: 30,60,90,180
- omitted_horizons: none
- selected_horizons_completed: true
- full_horizon_validation_completed: true
- candidate_exhaustive_completed: true
- all_possible_30_60_90_180_standard_and_stress_completed: true
- incomplete_or_nonfinal_finalists: none

Full-horizon finalist metrics:

### 30-day standard

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,000.66; p95 $3,017.89; worst drawdown $-23.37
- GLD_buy_hold: +300 11.0%; +400 4.9%; +600 0.6%; +900 0.0%; +1200 0.0%; stop 0.5%; median $3,023.05; p95 $3,324.41; worst drawdown $-764.39
- SPY_200d_trend_model: +300 0.8%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,025.24; p95 $3,202.09; worst drawdown $-561.28
- SPY_buy_hold: +300 4.7%; +400 1.5%; +600 0.3%; +900 0.0%; +1200 0.0%; stop 1.9%; median $3,061.83; p95 $3,256.40; worst drawdown $-1,039.43
- asset_class_tsmom_equal_weight_v1: +300 1.1%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,023.30; p95 $3,185.61; worst drawdown $-512.23
- asset_class_tsmom_top2_v1: +300 2.2%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,027.05; p95 $3,212.95; worst drawdown $-535.90
- combo_SPY200d_GLD_50_50_v1: +300 1.3%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,033.53; p95 $3,204.92; worst drawdown $-415.63

### 30-day stress

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,000.66; p95 $3,017.89; worst drawdown $-23.37
- GLD_buy_hold: +300 11.0%; +400 4.9%; +600 0.6%; +900 0.0%; +1200 0.0%; stop 0.5%; median $3,023.05; p95 $3,324.41; worst drawdown $-764.39
- SPY_200d_trend_model: +300 0.8%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,023.68; p95 $3,202.09; worst drawdown $-574.40
- SPY_buy_hold: +300 4.7%; +400 1.5%; +600 0.3%; +900 0.0%; +1200 0.0%; stop 1.9%; median $3,061.83; p95 $3,256.40; worst drawdown $-1,039.43
- asset_class_tsmom_equal_weight_v1: +300 1.1%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,022.64; p95 $3,185.04; worst drawdown $-513.55
- asset_class_tsmom_top2_v1: +300 2.2%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,026.64; p95 $3,212.53; worst drawdown $-537.18
- combo_SPY200d_GLD_50_50_v1: +300 1.3%; +400 0.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,032.73; p95 $3,204.90; worst drawdown $-422.30

### 60-day standard

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.31; p95 $3,036.26; worst drawdown $-23.41
- GLD_buy_hold: +300 30.4%; +400 17.2%; +600 5.1%; +900 0.7%; +1200 0.0%; stop 2.8%; median $3,061.56; p95 $3,514.98; worst drawdown $-816.91
- SPY_200d_trend_model: +300 10.0%; +400 1.7%; +600 0.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,064.90; p95 $3,312.54; worst drawdown $-578.79
- SPY_buy_hold: +300 16.9%; +400 5.6%; +600 1.1%; +900 0.4%; +1200 0.1%; stop 4.2%; median $3,113.80; p95 $3,369.91; worst drawdown $-1,259.37
- asset_class_tsmom_equal_weight_v1: +300 6.4%; +400 1.6%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,057.36; p95 $3,275.06; worst drawdown $-535.48
- asset_class_tsmom_top2_v1: +300 10.3%; +400 3.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,064.12; p95 $3,314.26; worst drawdown $-557.47
- combo_SPY200d_GLD_50_50_v1: +300 9.8%; +400 3.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,064.96; p95 $3,315.52; worst drawdown $-434.58

### 60-day stress

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.31; p95 $3,036.26; worst drawdown $-23.41
- GLD_buy_hold: +300 30.4%; +400 17.2%; +600 5.1%; +900 0.7%; +1200 0.0%; stop 2.8%; median $3,061.56; p95 $3,514.98; worst drawdown $-816.91
- SPY_200d_trend_model: +300 9.9%; +400 1.7%; +600 0.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,063.09; p95 $3,312.21; worst drawdown $-592.32
- SPY_buy_hold: +300 16.9%; +400 5.6%; +600 1.1%; +900 0.4%; +1200 0.1%; stop 4.2%; median $3,113.80; p95 $3,369.91; worst drawdown $-1,259.37
- asset_class_tsmom_equal_weight_v1: +300 6.3%; +400 1.6%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,056.01; p95 $3,274.24; worst drawdown $-536.85
- asset_class_tsmom_top2_v1: +300 10.2%; +400 3.5%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,062.72; p95 $3,313.49; worst drawdown $-558.80
- combo_SPY200d_GLD_50_50_v1: +300 9.8%; +400 3.1%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,063.41; p95 $3,315.15; worst drawdown $-441.56

### 90-day standard

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.90; p95 $3,054.96; worst drawdown $-23.47
- GLD_buy_hold: +300 42.2%; +400 28.1%; +600 12.5%; +900 2.7%; +1200 0.2%; stop 5.2%; median $3,109.70; p95 $3,646.15; worst drawdown $-879.09
- SPY_200d_trend_model: +300 24.2%; +400 10.0%; +600 1.0%; +900 0.0%; +1200 0.0%; stop 0.5%; median $3,097.12; p95 $3,418.41; worst drawdown $-661.82
- SPY_buy_hold: +300 31.9%; +400 15.2%; +600 3.4%; +900 0.5%; +1200 0.1%; stop 6.4%; median $3,154.11; p95 $3,503.06; worst drawdown $-1,330.23
- asset_class_tsmom_equal_weight_v1: +300 14.9%; +400 5.2%; +600 0.4%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,096.21; p95 $3,343.26; worst drawdown $-563.55
- asset_class_tsmom_top2_v1: +300 21.5%; +400 9.4%; +600 0.9%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,098.03; p95 $3,396.01; worst drawdown $-579.66
- combo_SPY200d_GLD_50_50_v1: +300 20.9%; +400 9.2%; +600 1.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,107.86; p95 $3,414.35; worst drawdown $-452.23

### 90-day stress

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.90; p95 $3,054.96; worst drawdown $-23.47
- GLD_buy_hold: +300 42.2%; +400 28.1%; +600 12.5%; +900 2.7%; +1200 0.2%; stop 5.2%; median $3,109.70; p95 $3,646.15; worst drawdown $-879.09
- SPY_200d_trend_model: +300 24.0%; +400 9.9%; +600 0.6%; +900 0.0%; +1200 0.0%; stop 1.1%; median $3,094.02; p95 $3,417.04; worst drawdown $-688.43
- SPY_buy_hold: +300 31.9%; +400 15.2%; +600 3.4%; +900 0.5%; +1200 0.1%; stop 6.4%; median $3,154.11; p95 $3,503.06; worst drawdown $-1,330.23
- asset_class_tsmom_equal_weight_v1: +300 14.2%; +400 5.2%; +600 0.4%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,094.12; p95 $3,341.39; worst drawdown $-567.57
- asset_class_tsmom_top2_v1: +300 21.2%; +400 9.3%; +600 0.9%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,095.45; p95 $3,395.51; worst drawdown $-580.75
- combo_SPY200d_GLD_50_50_v1: +300 20.8%; +400 9.1%; +600 1.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,105.23; p95 $3,414.04; worst drawdown $-456.86

### 180-day standard

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,003.99; p95 $3,109.46; worst drawdown $-23.61
- GLD_buy_hold: +300 60.3%; +400 50.4%; +600 33.7%; +900 14.3%; +1200 5.9%; stop 16.8%; median $3,168.69; p95 $4,061.00; worst drawdown $-990.22
- SPY_200d_trend_model: +300 54.0%; +400 38.5%; +600 12.8%; +900 1.3%; +1200 0.0%; stop 4.9%; median $3,193.78; p95 $3,720.94; worst drawdown $-743.40
- SPY_buy_hold: +300 64.5%; +400 47.4%; +600 18.0%; +900 4.0%; +1200 0.9%; stop 16.0%; median $3,294.93; p95 $3,810.85; worst drawdown $-1,572.99
- asset_class_tsmom_equal_weight_v1: +300 43.5%; +400 28.1%; +600 6.3%; +900 0.0%; +1200 0.0%; stop 1.3%; median $3,195.51; p95 $3,551.07; worst drawdown $-655.41
- asset_class_tsmom_top2_v1: +300 46.8%; +400 32.2%; +600 12.3%; +900 2.0%; +1200 0.0%; stop 1.3%; median $3,199.75; p95 $3,670.23; worst drawdown $-655.41
- combo_SPY200d_GLD_50_50_v1: +300 48.1%; +400 31.5%; +600 12.7%; +900 2.3%; +1200 0.2%; stop 0.0%; median $3,195.27; p95 $3,722.65; worst drawdown $-516.49

### 180-day stress

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,003.99; p95 $3,109.46; worst drawdown $-23.61
- GLD_buy_hold: +300 60.3%; +400 50.4%; +600 33.7%; +900 14.3%; +1200 5.9%; stop 16.8%; median $3,168.69; p95 $4,061.00; worst drawdown $-990.22
- SPY_200d_trend_model: +300 53.3%; +400 38.2%; +600 12.7%; +900 1.1%; +1200 0.0%; stop 5.5%; median $3,182.81; p95 $3,719.46; worst drawdown $-773.26
- SPY_buy_hold: +300 64.5%; +400 47.4%; +600 18.0%; +900 4.0%; +1200 0.9%; stop 16.0%; median $3,294.93; p95 $3,810.85; worst drawdown $-1,572.99
- asset_class_tsmom_equal_weight_v1: +300 42.8%; +400 27.5%; +600 6.0%; +900 0.0%; +1200 0.0%; stop 1.6%; median $3,191.77; p95 $3,546.55; worst drawdown $-656.86
- asset_class_tsmom_top2_v1: +300 46.2%; +400 31.9%; +600 12.0%; +900 2.0%; +1200 0.0%; stop 1.6%; median $3,196.41; p95 $3,666.44; worst drawdown $-656.86
- combo_SPY200d_GLD_50_50_v1: +300 47.0%; +400 30.9%; +600 12.5%; +900 2.2%; +1200 0.2%; stop 0.0%; median $3,189.68; p95 $3,720.27; worst drawdown $-521.79

90-day standard finalist metrics:

- BIL_cash_proxy: +300 0.0%; +400 0.0%; +600 0.0%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,001.90; p95 $3,054.96; worst drawdown $-23.47
- GLD_buy_hold: +300 42.2%; +400 28.1%; +600 12.5%; +900 2.7%; +1200 0.2%; stop 5.2%; median $3,109.70; p95 $3,646.15; worst drawdown $-879.09
- SPY_200d_trend_model: +300 24.2%; +400 10.0%; +600 1.0%; +900 0.0%; +1200 0.0%; stop 0.5%; median $3,097.12; p95 $3,418.41; worst drawdown $-661.82
- SPY_buy_hold: +300 31.9%; +400 15.2%; +600 3.4%; +900 0.5%; +1200 0.1%; stop 6.4%; median $3,154.11; p95 $3,503.06; worst drawdown $-1,330.23
- asset_class_tsmom_equal_weight_v1: +300 14.9%; +400 5.2%; +600 0.4%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,096.21; p95 $3,343.26; worst drawdown $-563.55
- asset_class_tsmom_top2_v1: +300 21.5%; +400 9.4%; +600 0.9%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,098.03; p95 $3,396.01; worst drawdown $-579.66
- combo_SPY200d_GLD_50_50_v1: +300 20.9%; +400 9.2%; +600 1.1%; +900 0.0%; +1200 0.0%; stop 0.0%; median $3,107.86; p95 $3,414.35; worst drawdown $-452.23

Direct full-horizon comparison answers:

- combo beat SPY_200d on +300 across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 2/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 19.9% vs SPY_200d_trend_model 22.1%).
- combo beat SPY_200d on +400 across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 2/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 10.9% vs SPY_200d_trend_model 12.5%).
- combo beat SPY_200d on +600 across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 2/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 3.4% vs SPY_200d_trend_model 3.4%).
- combo beat SPY_200d on +900 across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 2/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 0.6% vs SPY_200d_trend_model 0.3%).
- combo beat SPY_200d on +1200 across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 2/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 0.0% vs SPY_200d_trend_model 0.0%).
- combo had lower stop-hit rate than SPY_200d across the full horizon set: mixed; combo_SPY200d_GLD_50_50_v1 better in 4/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 0.0% vs SPY_200d_trend_model 1.5%).
- combo had better worst drawdown than SPY_200d across the full horizon set: yes; combo_SPY200d_GLD_50_50_v1 better in 8/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 $-457.68 vs SPY_200d_trend_model $-646.71).
- combo had higher median stop-enforced equity than SPY_200d across the full horizon set: yes; combo_SPY200d_GLD_50_50_v1 better in 8/8 selected horizon/cost rows (average combo_SPY200d_GLD_50_50_v1 $3,099.08 vs SPY_200d_trend_model $3,093.08).
- asset_class_tsmom_top2 beat SPY_200d on median stop-enforced equity across the full horizon set: mixed; asset_class_tsmom_top2_v1 better in 6/8 selected horizon/cost rows (average asset_class_tsmom_top2_v1 $3,096.27 vs SPY_200d_trend_model $3,093.08).
- asset_class_tsmom_top2 beat combo on median stop-enforced equity across the full horizon set: mixed; asset_class_tsmom_top2_v1 better in 2/8 selected horizon/cost rows (average asset_class_tsmom_top2_v1 $3,096.27 vs combo_SPY200d_GLD_50_50_v1 $3,099.08).
- asset_class_tsmom_equal_weight beat SPY_200d on median stop-enforced equity across the full horizon set: mixed; asset_class_tsmom_equal_weight_v1 better in 3/8 selected horizon/cost rows (average asset_class_tsmom_equal_weight_v1 $3,092.11 vs SPY_200d_trend_model $3,093.08).
- asset_class_tsmom_equal_weight beat combo on median stop-enforced equity across the full horizon set: mixed; asset_class_tsmom_equal_weight_v1 better in 2/8 selected horizon/cost rows (average asset_class_tsmom_equal_weight_v1 $3,092.11 vs combo_SPY200d_GLD_50_50_v1 $3,099.08).

90-day ranking comparison answers:

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
- Promotion-review candidates after full 30/60/90/180 candidate_exhaustive: asset_class_tsmom_top2_v1, combo_SPY200d_GLD_50_50_v1, asset_class_tsmom_equal_weight_v1.
- This run completed all requested 30/60/90/180 horizons with all_possible windows; no horizons are omitted.
- No finalist is automatically paper-forward ready, and SPY_200d_trend_model remains the frozen paper-forward observation unless a separate promotion process changes it.
- No real-money recommendation is made.



## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 67.0481; combo 66.7705.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (249.84)
- balanced_score leader: combo_SPY200d_GLD_50_50_v1 (176.19)
- drawdown_control_score leader: BIL_cash_proxy (351.59)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: asset_class_tsmom_top2_v1 (67.05).
- Drawdown-aware v2 leader: combo_SPY200d_GLD_50_50_v1 (101.59).
- Practical leader after v2: combo_SPY200d_GLD_50_50_v1.
- Combo/top2 comparison: combo v2 score 101.59 versus top2 6.57; combo risk budget used 90d/180d 0.75/0.86 versus top2 0.97/1.09.
- combo_SPY200d_GLD_50_50_v1 verdict: practical_leader; v2 confirms it as the robust practical challenger in this full-horizon candidate-exhaustive packet.
- asset_class_tsmom_top2_v1 verdict: promotion_review_candidate; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: high_upside_high_risk; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: too_risky; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: benchmark_only; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- Full 30/60/90/180 candidate_exhaustive completed for this finalist packet; a separate promotion review is still required before any paper-forward decision.
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
