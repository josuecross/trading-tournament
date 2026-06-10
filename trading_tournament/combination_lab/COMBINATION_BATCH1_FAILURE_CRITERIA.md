# Combination Batch 1 Failure Criteria

Primary benchmarks:

- `combo_SPY200d_GLD_50_50_v1`
- `asset_class_tsmom_top2_v1`

Secondary benchmarks:

- `SPY_200d_trend_model`
- `GLD_buy_hold`
- `SPY_buy_hold`
- `BIL_cash_proxy`
- `managed_futures_proxy_etf_trend_v1`

Predeclared failure criteria:

- Does not beat combo/top2 on stop-aware profit/risk.
- Target improvement comes only with worse drawdown.
- Stop-hit rate is materially worse than combo/top2.
- Worst drawdown consumes more of the -$600 budget without enough target improvement.
- Managed-futures sleeve makes the combination too slow.
- Combination mostly duplicates combo/top2 behavior.
- Short-history managed-futures evidence is overinterpreted.
- Exact fresh-window streams cannot be produced.
- Performance comes from one sleeve only.
- Correlation diagnostics are unavailable and diversification is claimed anyway.

Failure does not imply real-money loss. This is historical research-only evidence.

