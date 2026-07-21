# Trade Management Overlay Architecture Notes

Research-only scope. This framework is for historical backtests and does not authorize, start, connect, or modify paper, demo, broker, scheduler, webhook, live order-routing, or account-management paths.

## Architecture Map

1. Market data are loaded in `src/data.py`. `load_market_data()` reads cached CSVs or yfinance fallback data, normalizes raw OHLCV fields, preserves raw columns, constructs adjusted OHLC from adjusted-close factors, and records coverage/cache hashes. `src/indicators.py` then adds lagged indicators and market-regime fields.
2. Signals are generated in `src/strategies.py` by `StrategyEngine.generate_entries()` and `StrategyEngine.generate_exits()`. The strategy methods produce `EntrySignal` and `ExitSignal` objects.
3. Signals become order intents in `src/backtester.py`. Entry and exit signals are queued as `PendingEntry` and `PendingExit`, then filled on the next valid open where possible.
4. Orders are created implicitly by the pending-entry and pending-exit queues in `Backtester.run()`. There is no separate broker order object in the canonical research engine.
5. Fills, execution timing, spread/slippage, and simplified costs are modeled in `src/backtester.py` via next-open fills, adjusted OHLC stop handling, and `apply_entry_slippage()` / `apply_exit_slippage()`. Slippage cost is recorded in trade metadata.
6. Portfolio cash, positions, P&L, leverage-like exposure, turnover inputs, and open-risk accounting live in `src/portfolio.py`. Overlays must use `Portfolio.attempt_open_position()` and `Portfolio.close_position()` rather than mutating P&L directly.
7. Reports and metrics are produced by `src/metrics.py`, `src/reporting.py`, `src/validation.py`, and top-level research runners such as `run_backtest.py`.
8. Existing lifecycle/risk abstractions include project stops and loss budgets in `src/risk.py` plus strategy stop/target/trailing logic in `src/strategies.py` and `src/backtester.py`. The overlay framework extends the backtester lifecycle rather than creating a parallel engine.
9. Paper/demo/live/broker modules exist under `execution_lab/alpaca_micro_live_v1/` and observation scripts such as `run_paper_forward_observation.py`. This task leaves those paths untouched and keeps all overlay code under `src/` plus research-only reporting scripts.

## Overlay Lifecycle

The optional `overlay` argument to `Backtester.run()` is the integration point. With `overlay=None`, the old backtest path is preserved.

Lifecycle hooks:

- `bind(...)`: records run/base identity and gives the overlay read-only access to data, indexed data, calendar, and config.
- `on_signal_batch(...)`: sees the same-date base entry and exit intents together and returns a separate `ManagedIntentBatch`.
- `on_after_entry_fill(...)`: records post-fill state such as fixed entry ATR without changing accounting.
- `process_position_lifecycle(...)`: can request position lifecycle exits, including ATR stops, through `Portfolio.close_position()`.
- `on_after_exit_fill(...)`: records actual fills from pending exits or base stops.

Base `EntrySignal` and `ExitSignal` generation remains in `src/strategies.py`; overlays clone and return managed signals when they resize or filter an intent.
