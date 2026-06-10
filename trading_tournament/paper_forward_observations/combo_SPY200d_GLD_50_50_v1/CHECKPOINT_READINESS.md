# Checkpoint Readiness

Subject: combo_SPY200d_GLD_50_50_v1

Observation id: combo_SPY200d_GLD_50_50_v1_observation_v1

Readiness status: ready_for_first_30_trading_day_checkpoint

Current checkpoint_status: inconclusive_too_early

This document defines observation checkpoint readiness only. It does not change strategy rules, run a backtest, run Profit Exploration, download data, place orders, connect to brokers, or make a real-money recommendation.

## Schedule

- First checkpoint: after 30 trading days from activation.
- Recurring checkpoints: monthly after the first checkpoint.
- Minimum evidence before judgment: at least 30 trading days.
- Stronger evidence windows: 60, 90, and 180 observation days.
- No conclusion is allowed before 30 trading days.

## Comparison Design

The combo must be evaluated beside `SPY_200d_trend_model`; it does not replace it. SPY_200d remains the frozen control until a separate governance decision says otherwise.

## Required Checkpoint Metrics

Each checkpoint should record:

- current equity
- distance to +300
- distance to +400
- distance to -600 stop
- max drawdown
- trailing drawdown
- target flags
- stop flags
- signal state
- equity difference versus SPY_200d
- drawdown difference versus SPY_200d

## Current First-Day State

- combo status: active_paper_demo_observation
- combo paper_forward_active: true
- combo current equity: $2,998.50
- combo distance to +300: $301.50
- combo distance to +400: $401.50
- combo distance to -600 stop: $598.50
- combo max drawdown: $0.00
- checkpoint_status: inconclusive_too_early
- SPY_200d frozen control: true
- SPY_200d replaced: false

## Governance Rules Before First Checkpoint

- No promotion from first-day data.
- No demotion from first-day data.
- No strategy changes before checkpoint.
- No parameter tuning.
- No new filters.
- No risk-framework changes.
- No broker integration.
- No live orders.
- No order placement.
- No real-money recommendation.

## Failure Or Review Triggers

Future checkpoints must flag review if any of these occur:

- project stop hit
- drawdown worse than SPY_200d by material threshold
- combo underperforms SPY_200d while taking more drawdown
- data or signal missing
- rule hash mismatch
- evidence packet inconsistency
- observation drift from frozen rule
- manual intervention
- any broker, live-order, order-placement, or real-money behavior appears
