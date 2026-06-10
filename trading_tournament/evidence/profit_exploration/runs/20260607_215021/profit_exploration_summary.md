# Profit Exploration Summary

## Research Boundary

This is research-only paper/demo evidence. It does not recommend real-money trading, does not connect to brokers or exchanges, and does not place orders.

## Run Identity

- run_id: 20260607_215021
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
- selected_horizons_completed: false
- full_horizon_validation_completed: false
- candidate_exhaustive_completed: false
- final_validation_completed: false
- sampled_results_are_final: false

## Experiments

Completed experiments: GLD_buy_hold, SPY_200d_trend_model, asset_class_tsmom_top2_v1, BIL_cash_proxy, combo_SPY200d_GLD_50_50_v1, commodity_basket_tsmom_top2_200d_filter_v1, commodity_basket_tsmom_top2_v1, commodity_basket_tsmom_top2_half_bil_v1, combo_plus_commodity_basket_80_20_v1.

Blocked experiments: none.

Incomplete experiments: none.

Duplicate-skipped experiments: none.

Duplicate handling: canonical rule hashes are computed from strategy family, universe, rebalance frequency, lookback, trend filter, cash fallback, selected asset count, weighting rule, execution timing, max gross exposure, and leverage setting. Later duplicate rows are retained for audit visibility but are not counted as independent evidence.

## Target Ladder

- Highest exact +$300 probability: GLD_buy_hold (53.8%)
- Highest exact +$400 probability: GLD_buy_hold (43.6%)
- Highest +$600 probability: GLD_buy_hold (20.5%)
- Highest +$900 probability: commodity_basket_tsmom_top2_200d_filter_v1 (17.9%)
- Highest +$1200 probability: GLD_buy_hold (0.0%)

## Profit And Risk

- Highest median stop-enforced equity: combo_plus_commodity_basket_80_20_v1 ($3,184.00)
- Highest upside tail: commodity_basket_tsmom_top2_200d_filter_v1 ($3,746.53)
- Best risk control: BIL_cash_proxy
- Best overall profit/risk tradeoff: GLD_buy_hold
- Exact best +$300 family/experiment: GLD_buy_hold
- Exact best +$400 family/experiment: GLD_buy_hold

## Combination Review

Combinations improving the diagnostic score versus SPY_200d: none.

High-upside but too-risky rows: GLD_buy_hold.




## Profit Score Audit

The original final_score ranked asset_class_tsmom_top2_v1 above combo_SPY200d_GLD_50_50_v1 because top2 had slightly higher 90-day +300/+400 target rates and lower stress degradation. The combo had better median equity, p95 equity, expected profit, stop behavior, and worst drawdown, but the original drawdown penalty only applies after the -$600 budget is breached. Original final_score: top2 73.6398; combo -56.5558.

Alternative diagnostic score leaders:

- profit_seeking_score leader: GLD_buy_hold (387.65)
- balanced_score leader: asset_class_tsmom_top2_v1 (198.24)
- drawdown_control_score leader: BIL_cash_proxy (353.20)

Score-audit verdict: the original score is usable as a target-ladder diagnostic, but it under-credits drawdown control inside the -$600 risk budget. The balanced and drawdown-control views should be reviewed before treating a narrow final_score edge as decision-dominant.



## Drawdown-Aware Score v2

Score v2 was added because the original final_score only penalized worst drawdown after the -$600 risk budget was breached. V2 penalizes risk-budget usage before the hard stop, so a row using roughly 95% of the drawdown budget is not treated the same as a row using roughly 75%.

V2 differs from the original final_score by combining 90-day and 180-day target/equity rewards with explicit stop, stress, evidence-quality, and drawdown-budget penalties. The drawdown penalty has no penalty up to 50% risk-budget use, moderate penalty from 50-75%, large penalty from 75-100%, and severe penalty above 100%.

- Original final_score leader: GLD_buy_hold (149.58).
- Drawdown-aware v2 leader: SPY_200d_trend_model (126.05).
- Practical leader after v2: SPY_200d_trend_model.
- Combo/top2 comparison: combo v2 score -107.99 versus top2 107.60; combo risk budget used 90d/180d 0.69/0.81 versus top2 0.76/0.99.
- combo_SPY200d_GLD_50_50_v1 verdict: watchlist; v2 confirms it as the robust practical challenger in this reduced packet.
- asset_class_tsmom_top2_v1 verdict: promotion_review_candidate; it remains a serious challenger/watchlist row, but its target-rate edge does not fully compensate for drawdown-budget usage.
- GLD_buy_hold verdict: high_upside_high_risk; GLD remains high-upside/high-risk.
- SPY_buy_hold verdict: unavailable; SPY buy-hold remains too risky.
- BIL_cash_proxy verdict: benchmark_only; BIL remains defensive benchmark only and too slow for the target ladder.
- SPY_200d_trend_model remains the frozen paper-forward candidate.
- Full 30/60/90/180 candidate_exhaustive is still needed before any promotion or paper-forward decision.
- No real-money recommendation is made.








	

	

	
## Commodity Basket Exploratory Screen

This section reports one fixed fast exploratory commodity wrapper row. It is research_sample only, uses local cache only, does not run candidate_exhaustive, does not activate paper-forward, and does not make a real-money recommendation.

- experiment_id: `commodity_basket_tsmom_top2_v1`
- data source/cache status: local adjusted ETF/fund wrapper cache populated by controlled fast exploratory acquisition; Profit Exploration itself used `--reuse-cache --no-network`
- symbols used: DBC, PDBC, COMT, GSG, USCI plus BIL fallback
- symbols failed or excluded: see `evidence/data_acquisition_runs/commodity_basket_fast_exploratory/latest/`
- rule: monthly rebalance; rank DBC, PDBC, COMT, GSG, USCI by 126-trading-day return; hold top 2 wrappers with positive 126-day return equally; unused weight goes to BIL; if no wrapper qualifies, 100% BIL
- product labels: exploratory_public_data; commodity_wrapper_evidence_research_sample_only; not_validated; not_paper_forward; not_real_money
- target/risk ladder: 30d +300 22.5%, +400 5.0%, +600 2.5%, +900 0.0%, +1200 0.0%, stop 2.5%, median $3,007.71, p95 $3,244.56, worst drawdown $-651.80; 60d +300 25.6%, +400 20.5%, +600 12.8%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,038.88, p95 $3,574.85, worst drawdown $-435.05; 90d +300 41.0%, +400 25.6%, +600 20.5%, +900 17.9%, +1200 0.0%, stop 2.6%, median $3,054.97, p95 $3,746.53, worst drawdown $-680.67; 180d +300 56.4%, +400 53.8%, +600 30.8%, +900 23.1%, +1200 17.9%, stop 7.7%, median $3,298.99, p95 $4,070.37, worst drawdown $-718.24
- BIL/cash fallback frequency: selected 50.3%; allocation share 44.0%
- product concentration: max_single_commodity_wrapper_allocation=17.6%; product_concentration_warning=false
- comparison versus combo: commodity row beat combo: no (commodity_basket_tsmom_top2_v1 $-196.74 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: commodity row beat top2: no (commodity_basket_tsmom_top2_v1 $-196.74 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: commodity row beat SPY_200d: no (commodity_basket_tsmom_top2_v1 $-196.74 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: commodity row beat GLD: no (commodity_basket_tsmom_top2_v1 $-196.74 vs GLD_buy_hold $53.61).
- verdict: research_sample_candidate_risk_budget_breach
- deserves candidate_exhaustive: false
- direct futures claim disallowed: true


	
## Commodity Risk-Control Batch 1

This section reports exactly three fixed predeclared commodity risk-control candidates. It is research_sample only, uses cached DBC/PDBC/COMT/GSG/USCI/BIL data only, does not run candidate_exhaustive, does not alter active paper-forward observations, and does not make a real-money recommendation.

### commodity_basket_tsmom_top2_200d_filter_v1

- rule summary: Monthly top-2 commodity wrapper TSMOM with 126-day positive return and close > 200-day SMA filter; unused weight to BIL.
- data source/cache status: local cache only; Profit Exploration used `--reuse-cache --no-network`
- symbols used: DBC, PDBC, COMT, GSG, USCI, BIL
- target/risk ladder: 30d +300 22.5%, +400 5.0%, +600 2.5%, +900 0.0%, +1200 0.0%, stop 2.5%, median $3,018.63, p95 $3,249.75, worst drawdown $-651.80; 60d +300 28.2%, +400 20.5%, +600 12.8%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,026.97, p95 $3,574.85, worst drawdown $-435.05; 90d +300 43.6%, +400 25.6%, +600 20.5%, +900 17.9%, +1200 0.0%, stop 2.6%, median $3,075.02, p95 $3,746.53, worst drawdown $-680.67; 180d +300 56.4%, +400 53.8%, +600 30.8%, +900 23.1%, +1200 17.9%, stop 7.7%, median $3,298.99, p95 $4,078.67, worst drawdown $-718.24
- BIL/cash allocation share: 49.8%
- product/sleeve concentration: max wrapper 16.2%; combo sleeve 0.0%
- comparison versus base commodity: risk-control row beat base commodity: yes (commodity_basket_tsmom_top2_200d_filter_v1 $-192.86 vs commodity_basket_tsmom_top2_v1 $-196.74).
- comparison versus combo: risk-control row beat combo: no (commodity_basket_tsmom_top2_200d_filter_v1 $-192.86 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: risk-control row beat top2: no (commodity_basket_tsmom_top2_200d_filter_v1 $-192.86 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: risk-control row beat SPY_200d: no (commodity_basket_tsmom_top2_200d_filter_v1 $-192.86 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: risk-control row beat GLD: no (commodity_basket_tsmom_top2_200d_filter_v1 $-192.86 vs GLD_buy_hold $53.61).
- verdict: research_sample_candidate_risk_budget_breach
- candidate_exhaustive recommendation: false
- no real-money recommendation

### commodity_basket_tsmom_top2_half_bil_v1

- rule summary: 50% base commodity_basket_tsmom_top2_v1 sleeve and 50% BIL, fixed monthly rebalance.
- data source/cache status: local cache only; Profit Exploration used `--reuse-cache --no-network`
- symbols used: DBC, PDBC, COMT, GSG, USCI, BIL
- target/risk ladder: 30d +300 2.5%, +400 2.5%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,009.85, p95 $3,160.46, worst drawdown $-301.14; 60d +300 15.4%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,019.80, p95 $3,302.31, worst drawdown $-225.26; 90d +300 23.1%, +400 17.9%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,034.31, p95 $3,405.61, worst drawdown $-307.74; 180d +300 33.3%, +400 25.6%, +600 20.5%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,160.00, p95 $3,555.57, worst drawdown $-319.65
- BIL/cash allocation share: 68.8%
- product/sleeve concentration: max wrapper 8.8%; combo sleeve 0.0%
- comparison versus base commodity: risk-control row beat base commodity: yes (commodity_basket_tsmom_top2_half_bil_v1 $-149.87 vs commodity_basket_tsmom_top2_v1 $-196.74).
- comparison versus combo: risk-control row beat combo: no (commodity_basket_tsmom_top2_half_bil_v1 $-149.87 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: risk-control row beat top2: no (commodity_basket_tsmom_top2_half_bil_v1 $-149.87 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: risk-control row beat SPY_200d: no (commodity_basket_tsmom_top2_half_bil_v1 $-149.87 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: risk-control row beat GLD: no (commodity_basket_tsmom_top2_half_bil_v1 $-149.87 vs GLD_buy_hold $53.61).
- verdict: research_sample_candidate
- candidate_exhaustive recommendation: false
- no real-money recommendation

### combo_plus_commodity_basket_80_20_v1

- rule summary: 80% historical combo_SPY200d_GLD_50_50_v1 component and 20% base commodity_basket_tsmom_top2_v1 sleeve, fixed monthly rebalance.
- data source/cache status: local cache only; Profit Exploration used `--reuse-cache --no-network`
- symbols used: DBC, PDBC, COMT, GSG, USCI, BIL
- target/risk ladder: 30d +300 0.0%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,048.10, p95 $3,196.08, worst drawdown $-209.44; 60d +300 7.7%, +400 0.0%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,091.09, p95 $3,269.16, worst drawdown $-272.16; 90d +300 30.8%, +400 5.1%, +600 0.0%, +900 0.0%, +1200 0.0%, stop 0.0%, median $3,184.00, p95 $3,334.41, worst drawdown $-275.02; 180d +300 64.1%, +400 46.2%, +600 20.5%, +900 2.6%, +1200 0.0%, stop 0.0%, median $3,279.79, p95 $3,681.08, worst drawdown $-316.93
- BIL/cash allocation share: 17.7%
- product/sleeve concentration: max wrapper 3.5%; combo sleeve 80.0%
- comparison versus base commodity: risk-control row beat base commodity: yes (combo_plus_commodity_basket_80_20_v1 $-103.01 vs commodity_basket_tsmom_top2_v1 $-196.74).
- comparison versus combo: risk-control row beat combo: yes (combo_plus_commodity_basket_80_20_v1 $-103.01 vs combo_SPY200d_GLD_50_50_v1 $-107.99).
- comparison versus top2: risk-control row beat top2: no (combo_plus_commodity_basket_80_20_v1 $-103.01 vs asset_class_tsmom_top2_v1 $107.60).
- comparison versus SPY_200d: risk-control row beat SPY_200d: no (combo_plus_commodity_basket_80_20_v1 $-103.01 vs SPY_200d_trend_model $126.05).
- comparison versus GLD: risk-control row beat GLD: no (combo_plus_commodity_basket_80_20_v1 $-103.01 vs GLD_buy_hold $53.61).
- verdict: research_sample_candidate
- candidate_exhaustive recommendation: false
- no real-money recommendation



	## Candidate Exhaustive Queue

Candidate-exhaustive was not run for this task. The queue below is for later overnight validation only and does not promote any row.

- SPY_200d_trend_model: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier3_candidate_validation; research_sample_result_summary=+300 25.6%, +400 12.8%, stop 0.0%, median $3,107.69; main_risk=equity drawdown and whipsaw; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=SPY_200d_trend_model, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy
- asset_class_tsmom_top2_v1: reason_for_queue=research_sample accounting-valid row improves diagnostic score versus combo_SPY200d_GLD_50_50; evidence_tier=tier2_credible_prototype; research_sample_result_summary=+300 25.6%, +400 12.8%, stop 0.0%, median $3,120.71; main_risk=whipsaw, concentration, and possible defensive drag; comparison_target=SPY_200d_trend_model and combo_SPY200d_GLD_50_50_v1; recommended_finalist_set=asset_class_tsmom_top2_v1, SPY_200d_trend_model, combo_SPY200d_GLD_50_50_v1, GLD_buy_hold, BIL_cash_proxy

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
