# Risk Framework Summary

## Research-Only Statement

This is the canonical paper/demo risk-governance framework. It does not validate any strategy, recommend real-money trading, connect to brokers, or place orders.

## Run Identity

- run_id: 20260610_051551
- framework: balanced_speculative_research_v1
- validation_passed: True

## Account And Targets

- starting_equity: $3,000
- primary challenge target: $3,300 (+$300 / +10%)
- aggressive challenge target: $3,400 (+$400 / +13.3%)
- hard stop: $2,400 or high-water mark minus $600

## Risk Bands

- normal: under -10% drawdown
- warning: -10% / -$300
- review: -15% / -$450
- hard stop: -20% / -$600

## Exposure Policy

Only 1.00x can be paper-forward eligible after candidate validation. 1.05x and 1.10x are diagnostic only. 1.15x and above are too risky by default or stress diagnostics.

## Decision Use

The framework prioritizes rolling 90-day +$300 before stop, stress survival, benchmark-relative result, stop-hit rate, and worst rolling drawdown. Target hits alone are not success.
