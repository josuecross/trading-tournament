from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .portfolio import is_backtest_strategy
import yaml

from .backtester import BacktestResult


def _fmt(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    table = df.copy()
    if columns is not None:
        table = table[[col for col in columns if col in table.columns]]
    if max_rows is not None:
        table = table.head(max_rows)
    headers = list(table.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in table.iterrows():
        lines.append("| " + " | ".join(_fmt(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def write_csvs(result: BacktestResult, run_dir: Path) -> None:
    result.trades.to_csv(run_dir / "trades.csv", index=False)
    result.skipped_signals.to_csv(run_dir / "skipped_signals.csv", index=False)
    result.strategy_metrics.to_csv(run_dir / "strategy_metrics.csv", index=False)
    result.equity_curve.to_csv(run_dir / "combined_equity_curve.csv", index=False)
    result.benchmark_curve.to_csv(run_dir / "benchmark_equity_curve.csv", index=False)
    result.monthly_returns.to_csv(run_dir / "monthly_returns.csv", index=False)
    result.regime_performance.to_csv(run_dir / "regime_performance.csv", index=False)
    result.target_timing.to_csv(run_dir / "target_timing.csv", index=False)
    result.risk_events.to_csv(run_dir / "risk_events.csv", index=False)
    result.strategy_lifecycle_events.to_csv(run_dir / "strategy_lifecycle_events.csv", index=False)


def plot_equity_and_drawdown(result: BacktestResult, run_dir: Path) -> None:
    equity = result.equity_curve.copy()
    equity["date"] = pd.to_datetime(equity["date"])

    plt.figure(figsize=(11, 6))
    plt.plot(equity["date"], equity["equity"], label="Combined tournament", linewidth=2)
    if not result.benchmark_curve.empty:
        bench = result.benchmark_curve.copy()
        bench["date"] = pd.to_datetime(bench["date"])
        for col in ["SPY_buy_hold", "equal_weight_basket", "BIL_cash_proxy"]:
            if col in bench:
                plt.plot(bench["date"], bench[col], label=col, alpha=0.75)
    plt.axhline(3000, color="black", linewidth=0.8, alpha=0.4)
    plt.axhline(2400, color="red", linewidth=0.8, alpha=0.5, linestyle="--")
    plt.title("Tournament Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(run_dir / "equity_curve.png", dpi=150)
    plt.close()

    running_peak = equity["equity"].cummax()
    drawdown = equity["equity"] - running_peak
    plt.figure(figsize=(11, 5))
    plt.plot(equity["date"], drawdown, color="crimson", linewidth=1.6)
    plt.axhline(0, color="black", linewidth=0.8)
    plt.title("Tournament Drawdown Curve")
    plt.xlabel("Date")
    plt.ylabel("Drawdown ($)")
    plt.tight_layout()
    plt.savefig(run_dir / "drawdown_curve.png", dpi=150)
    plt.close()


def summarize_comparative(comparative: pd.DataFrame | None) -> str:
    if comparative is None or comparative.empty:
        return "_Comparative runs were not available._"
    cols = [
        "period",
        "slippage_label",
        "slippage_pct_per_side",
        "final_equity",
        "total_return",
        "max_drawdown",
        "number_of_trades",
        "absolute_floor_stop_hit",
        "trailing_drawdown_stop_hit",
        "target_300_before_any_stop",
        "target_400_before_any_stop",
        "killed_strategies",
    ]
    return markdown_table(comparative, cols)


def generate_summary_report(
    result: BacktestResult,
    config: dict[str, Any],
    run_metadata: dict[str, Any],
    comparative: pd.DataFrame | None = None,
    rolling_summary: pd.DataFrame | None = None,
    variants: pd.DataFrame | None = None,
    audit_tables: dict[str, pd.DataFrame] | None = None,
) -> str:
    audit_tables = audit_tables or {}
    metrics = result.strategy_metrics.copy()
    combined = metrics.loc[metrics["name"] == "combined_tournament"].iloc[0] if not metrics.empty else {}
    killed = ", ".join(result.killed_strategies) if result.killed_strategies else "None"
    skipped_counts = (
        result.skipped_signals.groupby("reason_skipped").size().reset_index(name="count")
        if not result.skipped_signals.empty
        else pd.DataFrame(columns=["reason_skipped", "count"])
    )
    target = result.metadata
    rolling90 = (
        rolling_summary.loc[rolling_summary["horizon_trading_days"] == 90]
        if rolling_summary is not None and not rolling_summary.empty
        else pd.DataFrame()
    )
    rolling90_text = markdown_table(rolling90) if not rolling90.empty else "_No rolling 90-day rows._"
    variant_text = markdown_table(
        variants,
        [
            "variant_name",
            "slippage_label",
            "final_equity",
            "max_drawdown_dollars",
            "target_300_before_any_stop",
            "target_400_before_any_stop",
            "trailing_drawdown_stop_hit",
            "strategies_killed",
        ],
    ) if variants is not None and not variants.empty else "_No variant rows._"
    strategy_health = audit_tables.get("strategy_health", pd.DataFrame())
    r_diag = audit_tables.get("r_multiple_diagnostics", pd.DataFrame())
    symbol_contrib = audit_tables.get("symbol_contribution", pd.DataFrame())
    risk_events = audit_tables.get("risk_events", result.risk_events)
    data_quality = audit_tables.get("data_quality_summary", pd.DataFrame())
    best = "N/A"
    worst = "N/A"
    strategy_rows = metrics.loc[metrics["name"] != "combined_tournament"] if not metrics.empty else pd.DataFrame()
    if not strategy_rows.empty:
        best = strategy_rows.sort_values("total_return", ascending=False).iloc[0]["name"]
        worst = strategy_rows.sort_values("total_return", ascending=True).iloc[0]["name"]

    strategy_rules = """
- A ETF/sector momentum: weekly rank by 63/126-day return divided by 20-day realized volatility; top 2 eligible ETFs only when SPY is above its 200-day SMA; daily SMA/trailing stops and weekly rank-drop exits.
- B ETF trend-following: 50/200-day trend filter, 20-day high breakout, SPY risk-on filter, ATR stop and trailing stop.
- C swing trend pullback: uptrend filter, 3-7 declining-day pullback, reclaim trigger, pullback/ATR stop, +2R target, and 20 trading-day time exit.
- D mean reversion: 200-day trend filter, RSI(2) or lower Bollinger entry, RSI/SMA/time exits, ATR stop, no averaging down.
- E breakout/VCB: 20-day high breakout, volume confirmation, optional ATR-percentile contraction, +2R target, failed-breakout/trailing exits.
- N1 dual momentum TAA: monthly cross-sectional and absolute momentum ETF rotation with defensive fallback.
- N2 absolute trend TAA: monthly tactical allocation using 200-day trend and defensive risk-off assets.
- N3 dual momentum vol scaled: N1 with SPY realized-volatility scaling and defensive reallocation in high-volatility regimes.
- N4 inverse-vol defensive allocation: monthly inverse-volatility allocation across SPY/IEF/TLT/GLD with BIL/cash remainder.
- F opening range breakout and G event/news momentum are shadow-only placeholders because reliable intraday/event data is outside this MVP.
"""

    allocation_rows = []
    for name, cfg in config["strategies"].items():
        if is_backtest_strategy(name, cfg):
            allocation_rows.append(
                {
                    "strategy": name,
                    "allocation_label": cfg.get("allocation", 0.0),
                    "max_strategy_loss": cfg.get("max_strategy_loss", 0.0),
                    "risk_per_trade": cfg.get("risk_per_trade", 0.0),
                    "max_positions": cfg.get("max_positions", 0),
                }
            )
    allocation_df = pd.DataFrame(allocation_rows)

    text = f"""# Trading Tournament Summary Report

Clear statement: this is research-only paper/demo trading infrastructure. It is not a real-money recommendation, does not connect to a brokerage, and does not place real orders.

## 1. Executive Audit Summary
- Main selected stop mode: `{run_metadata.get("project_stop_mode", target.get("project_stop_mode", "unknown"))}`
- Final equity: ${combined.get("final_equity", float("nan")):,.2f}
- Max drawdown: ${combined.get("max_drawdown", float("nan")):,.2f} ({combined.get("max_drawdown_pct", float("nan")):.2%})
- +$300 before any selected stop: {target.get("target_300_before_any_stop", False)}
- +$400 before any selected stop: {target.get("target_400_before_any_stop", False)}
- Strategies killed by loss budgets: {killed}
- This remains unvalidated research output, not a profitability claim.

## 2. Stop Mode And Risk Budget
- Legacy absolute floor: equity <= ${config["project"].get("hard_stop_equity", 2400):,.2f}
- Configured absolute floor: ${config["project"]["project_stop"]["absolute_floor_equity"]:,.2f}
- Configured trailing drawdown: ${config["project"]["project_stop"]["trailing_drawdown_dollars"]:,.2f}
- Absolute floor stop hit: {target.get("absolute_floor_stop_hit", False)} on {target.get("absolute_floor_stop_date", "")}
- Trailing drawdown stop hit: {target.get("trailing_drawdown_stop_hit", False)} on {target.get("trailing_drawdown_stop_date", "")}
- First project stop type/date: {target.get("first_project_stop_type", "")} {target.get("first_project_stop_date", "")}
- Equity at first project stop: {target.get("equity_at_first_project_stop", "")}
- High water mark at stop: {target.get("high_water_mark_at_stop", "")}
- Drawdown at stop: {target.get("drawdown_at_stop", "")}

## 3. Target Timing
- +$300 hit: {target.get("target_300_hit", False)} on {target.get("target_300_first_date", "")}, trading days: {target.get("target_300_trading_days", "")}, equity: {target.get("equity_at_target_300", "")}
- +$300 before absolute/trailing/any stop: {target.get("target_300_before_absolute_stop", False)} / {target.get("target_300_before_trailing_stop", False)} / {target.get("target_300_before_any_stop", False)}
- +$400 hit: {target.get("target_400_hit", False)} on {target.get("target_400_first_date", "")}, trading days: {target.get("target_400_trading_days", "")}, equity: {target.get("equity_at_target_400", "")}
- +$400 before absolute/trailing/any stop: {target.get("target_400_before_absolute_stop", False)} / {target.get("target_400_before_trailing_stop", False)} / {target.get("target_400_before_any_stop", False)}

## 4. Rolling Window Validation
Rolling windows reset equity to $3,000 and replay observed daily tournament equity changes for the window as an audit diagnostic. Review this before treating the full-period result as challenge-ready.

{markdown_table(rolling_summary) if rolling_summary is not None and not rolling_summary.empty else "_No rolling summary generated._"}

Rolling 90-day focus:

{rolling90_text}

## 5. Strategy Variant Comparison
No parameters are changed. Only fixed strategy enable/disable sets and standard/stress slippage are compared.

{variant_text}

## 6. Strategy Health
{markdown_table(strategy_health) if not strategy_health.empty else "_No strategy health rows._"}

## 7. Standard vs Stress Slippage
{summarize_comparative(comparative)}

## 8. R-Multiple Quality Audit
{markdown_table(r_diag) if not r_diag.empty else "_No R diagnostics._"}

## 9. Symbol Contribution
{markdown_table(symbol_contrib.head(15)) if not symbol_contrib.empty else "_No symbol contribution rows._"}

## 10. Skipped Signal Summary
Only generated signals that were rejected are logged.

{markdown_table(skipped_counts)}

## 11. Risk Events
{markdown_table(risk_events.head(50)) if not risk_events.empty else "_No risk events._"}

## 12. Data Quality
{markdown_table(data_quality) if not data_quality.empty else "_See data_coverage.csv._"}

## 13. What Would Invalidate This Strategy
- Rolling 90-day +$300 target hit rate is too low.
- Rolling 90-day +$400 target hit rate is too low.
- Trailing drawdown stop kills most target-reaching windows.
- Stress slippage destroys returns.
- A/B core-only does not beat benchmark on a risk-adjusted basis.
- Results depend on BIL/SHY artifacts.
- C/D/E remain negative after enough trades.
- Top few trades explain most profit.
- R-multiple quality is distorted by tiny actual-risk trades.

## 14. Recommended Next Experiments
- Review the audit packet before changing any strategy parameter.
- Forward-test the strongest fixed variant in paper/demo mode.
- Add stricter liquidity and tiny-risk diagnostics as filters only after documenting their effect.
- Keep C/D/E shadow-only candidates unless forward evidence improves.

## 15. No Real-Money Recommendation
This report is for speculative research and paper/demo trading only. It does not recommend real-money trading.

## Appendix A. Project Assumptions
- Starting equity: ${config["project"]["starting_equity"]:,.2f}
- Target profits: +${config["project"]["target_profit_1"]:,.2f} and +${config["project"]["target_profit_2"]:,.2f}
- Hard project stop: equity <= ${config["project"]["hard_stop_equity"]:,.2f}
- Max daily loss block: ${config["project"]["max_daily_loss"]:,.2f}
- Max weekly loss block: ${config["project"]["max_weekly_loss"]:,.2f}
- Max total open risk: ${config["project"]["max_open_risk"]:,.2f}
- Reserve cash buffer label: ${config["project"]["reserve_cash_buffer"]:,.2f}

## Appendix B. Data Source And Date Range
- Data source summary: {run_metadata.get("data_source", "unknown")}
- Full requested backtest: {run_metadata.get("full_backtest_start")} to {run_metadata.get("full_backtest_end")}
- Effective main trading range after warmup: {result.metadata.get("effective_first_trading_date")} to {result.metadata.get("effective_last_trading_date")}
- yfinance parameters: `{run_metadata.get("yfinance_download_parameters")}`

## Appendix C. Strategy Rules
{strategy_rules}

## Appendix D. Tournament Allocations
Strategy allocations are reporting and risk-budget labels, not separate cash accounts.

{markdown_table(allocation_df)}

## Appendix E. Combined Result
- Final equity: ${combined.get("final_equity", float("nan")):,.2f}
- Total return: {combined.get("total_return", float("nan")):.2%}
- Max drawdown: ${combined.get("max_drawdown", float("nan")):,.2f} ({combined.get("max_drawdown_pct", float("nan")):.2%})
- Number of trades: {int(combined.get("number_of_trades", 0))}
- Target +$300 reached: {combined.get("target_300_reached", False)}
- Target +$400 reached: {combined.get("target_400_reached", False)}
- Hard -$600 project stop hit: {combined.get("project_stop_hit", False)}

## Appendix F. Per-Strategy Metrics
{markdown_table(metrics, ["name", "final_equity", "total_return", "max_drawdown", "win_rate", "profit_factor", "expectancy_per_trade_dollars", "expectancy_per_trade_r", "number_of_trades", "consecutive_losses"])}

## Appendix G. Legacy Targets And Stops
- +$300 target reached: {combined.get("target_300_reached", False)}
- +$400 target reached: {combined.get("target_400_reached", False)}
- -$600 project stop hit: {combined.get("project_stop_hit", False)}
- Strategies killed by loss budgets: {killed}

## Appendix H. Best And Worst Strategy
- Best strategy by total return: {best}
- Worst strategy by total return: {worst}

## Appendix I. Comparative Period Runs
- Main result uses slippage per side: {result.metadata.get("slippage_pct_per_side"):.4%}
- Stress run uses the configured higher slippage. All configured periods are reported below, including weak results.

{summarize_comparative(comparative)}

## Appendix J. Benchmark Construction
- SPY buy-and-hold uses the same adjusted close convention and the same effective date range.
- Equal-weight ETF basket uses valid symbols available on each benchmark date.
- BIL is used as the cash proxy when available; otherwise the cash proxy is flat.
- Benchmark curves are not tradable execution simulations and do not include taxes.

## Appendix K. Research Validity And Limitations
- Adjusted OHLC is constructed from raw Yahoo fields and raw OHLC is preserved for audit/debugging.
- Signals, entries, exits, stops, targets, returns, and metrics use adjusted OHLC.
- Volume is raw volume and is not dividend-adjusted.
- Signals use data available at the prior close; entries and signal exits fill at the next available open.
- Same-bar stop/target ambiguity is resolved conservatively: stop wins.
- Gap-through-stop handling fills at the open when the open is below the stop.
- The universe is static, so survivorship and ETF selection bias remain possible.
- ETF inception-date differences affect data availability and benchmark membership.
- yfinance/Yahoo data can have revisions, gaps, licensing and personal-use limitations.
- Cached data improves reproducibility but may differ from future Yahoo downloads.
- Paper fills are simplified and may differ materially from live execution.
- Accounting uses simple fractional shares, simplified cash yield/cash drag, no margin model, and ignores taxes.
- Open positions are closed or marked at final adjusted close so open P&L does not disappear.
- There is no broker integration, no real order placement, and no real-money recommendation.
- If a strategy has 4 consecutive losses it is visible in reporting, but the MVP only disables strategies when loss budgets are hit.

## Appendix L. Original Next Recommended Experiments
- Add walk-forward diagnostics without parameter optimization.
- Add stricter liquidity/spread filters and compare sensitivity.
- Test ETF inception-aware universes and alternative cash proxy assumptions.
- Add broker-like cash settlement and whole-share constraints.
- Add optional intraday ORB only when clean intraday CSV data is available.

## Appendix M. No Real-Money Recommendation
This report is for speculative research and paper/demo trading only. It does not recommend real-money trading.
"""
    return text


def write_report_artifacts(
    result: BacktestResult,
    config: dict[str, Any],
    run_metadata: dict[str, Any],
    run_dir: Path,
    comparative: pd.DataFrame | None = None,
    rolling_summary: pd.DataFrame | None = None,
    variants: pd.DataFrame | None = None,
    audit_tables: dict[str, pd.DataFrame] | None = None,
) -> None:
    write_csvs(result, run_dir)
    if comparative is not None:
        comparative.to_csv(run_dir / "comparative_results.csv", index=False)
    if rolling_summary is not None:
        rolling_summary.to_csv(run_dir / "rolling_window_summary.csv", index=False)
    if variants is not None:
        variants.to_csv(run_dir / "strategy_variant_results.csv", index=False)
    for name, df in (audit_tables or {}).items():
        df.to_csv(run_dir / f"{name}.csv", index=False)
    plot_equity_and_drawdown(result, run_dir)
    report = generate_summary_report(result, config, run_metadata, comparative, rolling_summary, variants, audit_tables)
    (run_dir / "summary_report.md").write_text(report, encoding="utf-8")


def regenerate_report_from_latest(run_dir: Path) -> None:
    config = yaml.safe_load((run_dir / "config_used.yaml").read_text(encoding="utf-8"))
    metadata = yaml.safe_load((run_dir / "run_metadata.json").read_text(encoding="utf-8"))

    class ResultShim:
        pass

    result = ResultShim()
    result.trades = pd.read_csv(run_dir / "trades.csv")
    result.skipped_signals = pd.read_csv(run_dir / "skipped_signals.csv")
    result.strategy_metrics = pd.read_csv(run_dir / "strategy_metrics.csv")
    result.equity_curve = pd.read_csv(run_dir / "combined_equity_curve.csv")
    result.benchmark_curve = pd.read_csv(run_dir / "benchmark_equity_curve.csv")
    result.monthly_returns = pd.read_csv(run_dir / "monthly_returns.csv")
    result.regime_performance = pd.read_csv(run_dir / "regime_performance.csv")
    result.target_timing = pd.read_csv(run_dir / "target_timing.csv") if (run_dir / "target_timing.csv").exists() else pd.DataFrame()
    result.risk_events = pd.read_csv(run_dir / "risk_events.csv") if (run_dir / "risk_events.csv").exists() else pd.DataFrame()
    result.strategy_lifecycle_events = pd.read_csv(run_dir / "strategy_lifecycle_events.csv") if (run_dir / "strategy_lifecycle_events.csv").exists() else pd.DataFrame()
    killed = metadata.get("main_run", {}).get("killed_strategies", [])
    result.killed_strategies = killed
    result.metadata = metadata.get("main_run", {})
    comparative_path = run_dir / "comparative_results.csv"
    comparative = pd.read_csv(comparative_path) if comparative_path.exists() else None
    rolling_summary = pd.read_csv(run_dir / "rolling_window_summary.csv") if (run_dir / "rolling_window_summary.csv").exists() else None
    variants = pd.read_csv(run_dir / "strategy_variant_results.csv") if (run_dir / "strategy_variant_results.csv").exists() else None
    audit_tables = {}
    for name in [
        "strategy_health",
        "r_multiple_diagnostics",
        "symbol_contribution",
        "data_quality_summary",
        "skipped_signal_summary",
    ]:
        path = run_dir / f"{name}.csv"
        if path.exists():
            audit_tables[name] = pd.read_csv(path)
    audit_tables["risk_events"] = result.risk_events
    plot_equity_and_drawdown(result, run_dir)
    (run_dir / "summary_report.md").write_text(
        generate_summary_report(result, config, metadata, comparative, rolling_summary, variants, audit_tables),
        encoding="utf-8",
    )
