# Research Direction Packet

This folder is a scope-control and research-direction layer for the trading tournament project. It does not validate any strategy, change any strategy, add instruments to code, or recommend real-money trading.

Read these files in this order:

1. `PROJECT_CHARTER.md` for the research-only boundary and goal.
2. `CURRENT_PROJECT_SCOPE_DECISION.md` for the current decision.
3. `OPPORTUNITY_MAP.md` and `INSTRUMENT_AND_STRATEGY_MATRIX.csv` for the broader market opportunity map.
4. `IMPLEMENTATION_GATE_POLICY.md` before any new instrument or strategy is coded.
5. `RESEARCH_DIRECTION_SUMMARY.md` for the short audit conclusion.

These documents relate to `evidence/latest/` by explaining what the current evidence can and cannot answer. The current backtest evidence is useful for ETF Phase 1, but it is not the whole answer to whether a $3,000 simulated account can plausibly pursue a +$300 to +$400 challenge target before a -$600 drawdown.

Gate 0 research memos live under `docs/research_memos/`. The first memo is `docs/research_memos/gate0/individual_stock_momentum/`, which authorizes only Gate 1 feasibility review and does not approve implementation.

The Strategy Lab Registry lives under `strategy_lab/`, with compact registry evidence under `evidence/strategy_lab/latest/`. It coordinates paper-forward freezes, experiment queues, blocked items, and promotion controls without changing strategy rules.

The active risk framework lives under `risk_framework/`, with compact framework evidence under `evidence/risk_framework/latest/`. It defines the +$300 primary target, +$400 aggressive target, and -10%/-15%/-20% risk bands used by compact audits and paper-forward observation.

Current phase correction: the project is in `historical_research_expansion_parallel_to_paper_demo_observation`. The active combo paper/demo observation continues beside frozen `SPY_200d_trend_model`, but the 30-trading-day checkpoint rule applies only to forward-observation judgment. Historical research, data reviews, diagnostics work, and combination-design reviews may continue in parallel under gates.

Research-only statement: this project does not connect to a broker, does not place live orders, does not provide an income claim, and does not recommend real-money trading.
