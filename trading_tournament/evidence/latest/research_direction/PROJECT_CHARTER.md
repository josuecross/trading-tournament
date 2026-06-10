# Project Charter

The project is a research and learning investigation into market-based strategies. It is not a real-money trading system, not an income claim, and not proof that any strategy will work.

## Status

- Research-only status: all outputs are paper/demo research artifacts.
- No real-money trading: no strategy output should be interpreted as a trade recommendation.
- No broker integration: the project must not connect to brokerage APIs.
- No live orders: the system must not place, route, or stage orders.
- No real-money recommendation: reports must not imply suitability for real capital.

## Goal

- Starting simulated balance: $3,000.
- Target profit: +$300 to +$400.
- Approximate risk budget: -$600, or about -20%.

The correct interpretation of the goal is a challenge metric: can a fixed, testable strategy family reach +10% to +13.3% before a -20% stop often enough to justify further paper-forward research? It is not evidence of income potential, reliability, safety, or edge by itself.

## What The Project Is

- A local research lab for objective market strategy testing.
- A reproducibility exercise with evidence packets, audit files, and explicit assumptions.
- A way to compare ETF strategies, benchmarks, rolling windows, slippage stress, and risk stops.
- A disciplined process for deciding what deserves future implementation.

## What The Project Is Not

- It is not a live trading system.
- It is not a broker simulator.
- It is not a recommendation engine.
- It is not proof that any method can reliably earn $300 to $400.
- It is not a mandate to keep adding strategies until one looks good.

## Success

Success means the project produces honest, reproducible evidence that clarifies whether a strategy or instrument family deserves more research, paper-forward monitoring, deferment, or rejection.

Success can include a negative result. A strategy that fails cleanly is useful if the failure is recorded, not tuned away.

## Failure

Failure means treating an isolated target hit, full-period equity curve, attractive chart, or complex implementation as proof. Failure also includes adding instruments before data, execution, risk, and validation requirements are understood.

## Why ETFs Are Phase 1

ETFs are suitable for Phase 1 because daily adjusted OHLC data is available, transaction cost assumptions are simpler than many alternatives, leverage can be avoided, and benchmarks are clear. ETFs make it easier to focus on research controls before modeling more difficult instruments.

## Why ETFs Are Not The Whole Investigation

ETF strategies may be too slow, too benchmark-like, or too limited to answer the broader question. The broader investigation must map stocks, options, futures, forex, crypto, volatility products, intraday strategies, and event strategies before deciding what, if anything, deserves implementation.

## High-Risk Instruments Are Not Automatically Better

Higher leverage or higher volatility can help reach a target faster in theory, but it can also make the -$600 stop easier to hit. Options, futures, crypto leverage, forex, volatility products, and intraday strategies require execution and risk models that are not present in the ETF MVP.

## Engineering Sophistication Is Not Edge

More code, more files, more charts, and more automation do not prove a strategy has edge. Evidence quality depends on realistic assumptions, out-of-sample behavior, rolling target-before-stop rates, stress slippage, benchmark comparison, and auditability.
