# Trading Tournament Backtester

Research-only Python backtesting MVP for a speculative paper-trading strategy tournament.

This project does not connect to a brokerage, does not place real orders, and does not recommend real-money trading.

## Setup

Python 3.11 or 3.12 is preferred. If your machine only has `python3` as a newer version such as Python 3.14, use a virtual environment and current package versions.

```bash
cd /Users/jcruzlopez/trading/trading_tournament
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Dependencies are intentionally broad:

- pandas
- numpy
- yfinance
- matplotlib
- pyyaml
- pytest

## Run

```bash
python3 -m pytest
python3 run_backtest.py
python3 run_report.py
```

Each backtest creates a reproducible run directory:

```text
results/runs/YYYYMMDD_HHMMSS/
```

The latest run is also copied to:

```text
results/latest/
```

## Outputs

Each run writes:

- `config_used.yaml`
- `run_metadata.json`
- `package_versions.json`
- `pip_freeze.txt`
- `data_coverage.csv`
- `trades.csv`
- `skipped_signals.csv`
- `strategy_metrics.csv`
- `combined_equity_curve.csv`
- `benchmark_equity_curve.csv`
- `monthly_returns.csv`
- `regime_performance.csv`
- `comparative_results.csv`
- `summary_report.md`
- `equity_curve.png`
- `drawdown_curve.png`

## Data

The loader uses yfinance first with explicit non-auto-adjusted settings where supported:

- `auto_adjust=False`
- `actions=True`
- `progress=False`
- `multi_level_index=False`

Raw downloaded fields are preserved:

- `raw_open`
- `raw_high`
- `raw_low`
- `raw_close`
- `raw_adj_close`
- `raw_volume`
- `dividends`
- `stock_splits`

Adjusted OHLC is then constructed as:

```text
adjustment_factor = raw_adj_close / raw_close
open = raw_open * adjustment_factor
high = raw_high * adjustment_factor
low = raw_low * adjustment_factor
close = raw_adj_close
volume = raw_volume
```

Signals, entries, exits, stops, targets, returns, metrics, and benchmarks use adjusted OHLC. Raw volume is not dividend-adjusted.

Downloaded data is cached under `data/cache/`. If yfinance fails, the loader looks for CSV files under `data/raw/SYMBOL.csv`.

## Strategies

Main tournament strategies:

- A ETF/sector momentum rotation
- B ETF trend-following
- C swing trend pullback
- D mean reversion with trend filter
- E breakout / volatility contraction breakout

Shadow-only strategies:

- F opening range breakout
- G event-driven earnings/news momentum

Opening range breakout requires clean intraday data under `data/intraday/` and is excluded from main results. Event/news momentum requires reliable event timestamps and clean event data, so it is also excluded from the MVP.

## Excluded High-Risk Comparisons

Options, leveraged ETFs, crypto, forex, and futures are excluded from the main MVP because of execution complexity, spread/slippage sensitivity, leverage, paper-fill unreliability, and insufficient clean data in this framework.

## Exploratory Lanes

`exploratory/crypto_spot_momentum/` is a separate Tier 1 exploratory screen for long-only crypto spot momentum. It is non-final, excludes leverage/perpetuals/futures/margin/shorting, does not change ETF validated results, and is not a real-money recommendation.

## Compact Challenge Web UI

Run a local-only minimal web interface for the compact challenge audit:

```bash
.venv/bin/python run_challenge_web.py
```

Then open `http://127.0.0.1:8765`. The UI can start `research_sample` or focused `candidate_exhaustive` challenge runs, show the latest compact evidence, and download `evidence/challenge_runs/latest_challenge_packet.zip`. It does not connect to a broker or place orders.

## Strategy Lab Registry

`strategy_lab/` and `run_strategy_lab.py` coordinate parallel strategy research without changing frozen paper-forward rules. The compact registry evidence packet is written to `evidence/strategy_lab/latest/`. This is scope control only and remains research-only with no real-money recommendation.

## Risk Framework

`risk_framework/` and `run_risk_framework_audit.py` define the active Balanced Speculative Research v1 governance layer. It labels +$300 as the primary challenge target, +$400 as the aggressive target, and applies -10% warning, -15% review, and -20%/-$600 hard-stop bands. Evidence is written to `evidence/risk_framework/latest/`; this is research-only and not a real-money recommendation.

## Research Discipline

The project does not perform optimization, grid search, parameter tuning, cherry-picking, or removal of bad trades. Comparative runs are limited to:

- standard slippage
- stress slippage
- full period
- in-sample
- validation
- out-of-sample

Weak or negative results are expected to be reported honestly.

## Research Direction Documents

Scope-control and opportunity-map documents live in `docs/research_direction/`, with the latest upload-ready copy under `evidence/latest/research_direction/`. These files explain which instrument and strategy families should be kept, deferred, mapped, or rejected before more code is added. They are research documentation only and do not recommend real-money trading.

## Important Limitations

yfinance/Yahoo data may contain revisions, missing values, ETF inception differences, and personal-use limitations. This MVP uses simplified fractional-share accounting, ignores taxes, simplifies cash yield/cash drag, and assumes paper fills that can differ materially from live execution.

This is not a real-money recommendation.
