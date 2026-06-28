# Strategy Lab Summary

## Research-Only Statement

This registry is a project-control layer only. It does not validate strategies, place trades, connect to brokers, or recommend real-money trading.

## Run Identity

- run_id: 20260623_040541
- registry rows: 176
- validation_passed: True

## Active Paper-Forward Candidate

`SPY_200d_trend_model` is the leading ETF paper-forward watchlist candidate. It is frozen and may only be observed or compared.

## Active Risk Framework

`balanced_speculative_research_v1` is active. Paper-forward rows must be allowed by the framework; Tier 1, simulated exposure/leverage, crypto exploratory, and gate-blocked rows are not paper-forward eligible.

## Frozen Paper-Forward Rows

SPY_200d_trend_model, current_no_cash_proxy_alpha_AB, SPY_buy_hold, BIL_cash_proxy, profit_combo_SPY200d_GLD_50_50_v1, paper_forward_vm_quality_lowvol_proxy_v1, paper_forward_dsr_sector_equal_weight_defensive_filter_v1

## Parallel Development Allowed

Parallel work is allowed only for rows in `experiment_queue.csv`, and only as isolated new versions, audit hardening, or memo/gate work. Frozen paper-forward rows must not be changed.

## Blocked Or Deferred Work

Blocked/deferred/rejected/too-risky rows are listed in `blocked_items.csv`. Individual stock momentum remains deferred after Gate 1A vendor verification. Crypto remains Tier 1 exploratory. C/D/E remain rejected or archived.

## Next Recommended Action

continue_vendor_review for individual_stock_momentum_gate1a

## No Real-Money Recommendation

Nothing in this registry is a real-money recommendation. No broker integration, live orders, or order placement are allowed.
