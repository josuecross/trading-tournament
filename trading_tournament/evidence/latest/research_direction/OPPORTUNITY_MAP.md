# Opportunity Map

This map is intentionally skeptical. It does not claim that any instrument is guaranteed to reach +$300 to +$400 from a $3,000 simulated account. It only identifies what deserves implementation, research-only review, deferment, or rejection.

## 1. ETFs / Broad Indexes

- What it is: diversified index or asset-class ETF exposure.
- Why it might reach target: equity beta can produce +10% to +13.3% during strong windows.
- Main risk: slow return engine and benchmark dependence.
- Data requirement: daily adjusted OHLCV is usually available.
- Execution realism: relatively high.
- Modeling difficulty: low to moderate.
- Overfitting risk: moderate if many filters are added.
- Implement now: yes, Phase 1.
- Research-only: yes.
- Reject for now: no.
- Revisit evidence: rolling target-before-stop and benchmark-relative returns.

## 2. Sector ETFs

- What it is: rotation among equity sectors and thematic ETFs.
- Why it might reach target: sector dispersion can amplify trends.
- Main risk: correlation spikes and false diversification.
- Data requirement: daily ETF data with inception differences.
- Execution realism: relatively high.
- Modeling difficulty: moderate.
- Overfitting risk: moderate to high.
- Implement now: already Phase 1, but keep candidate set small.
- Research-only: yes.
- Reject for now: no, but do not keep expanding variants.
- Revisit evidence: stress slippage and rolling windows.

## 3. Tactical Asset Allocation

- What it is: rules-based movement among risk assets, defensive assets, and cash proxies.
- Why it might reach target: can participate in trends while reducing major drawdowns.
- Main risk: whipsaw and slow adaptation.
- Data requirement: daily adjusted ETF data.
- Execution realism: high for monthly/daily ETF rules.
- Modeling difficulty: moderate.
- Overfitting risk: moderate.
- Implement now: yes, as evidence-backed ETF candidate research.
- Research-only: yes.
- Reject for now: no.
- Revisit evidence: target rates, drawdown, and stress robustness.

## 4. Individual Stocks

- What it is: single-name momentum, trend, or swing systems.
- Why it might reach target: higher idiosyncratic volatility can reach +10% faster.
- Main risk: gap risk, survivorship bias, delistings, liquidity, earnings shocks.
- Data requirement: survivorship-free adjusted OHLCV and corporate actions.
- Execution realism: moderate.
- Modeling difficulty: high.
- Overfitting risk: high.
- Implement now: no.
- Research-only: yes.
- Reject for now: defer.
- Revisit evidence: clean universe construction and delisting-aware data.
- Gate 0 note: `docs/research_memos/gate0/individual_stock_momentum/` now exists. It permits only Gate 1 feasibility review; implementation remains blocked until survivorship-free data and delisting treatment are resolved.

## 5. Options Directional Strategies

- What it is: calls, puts, or directional debit structures.
- Why it might reach target: convexity can create large percentage gains.
- Main risk: time decay, volatility mispricing, spreads, assignment/exercise details.
- Data requirement: historical option chains, IV, Greeks, bid/ask.
- Execution realism: difficult.
- Modeling difficulty: high.
- Overfitting risk: very high.
- Implement now: no.
- Research-only: yes.
- Reject for now: reject until an options framework exists.
- Revisit evidence: clean option-chain data and realistic fill model.

## 6. Options Premium Strategies

- What it is: selling options premium through spreads or short options.
- Why it might reach target: frequent small gains can compound.
- Main risk: tail losses can exceed the project risk budget.
- Data requirement: option chains, margin, assignment, bid/ask, IV.
- Execution realism: difficult.
- Modeling difficulty: very high.
- Overfitting risk: high.
- Implement now: no.
- Research-only: yes.
- Reject for now: reject due to execution and tail-risk modeling.
- Revisit evidence: robust margin and tail-loss simulation.

## 7. Futures Trend Following

- What it is: trend systems on futures contracts.
- Why it might reach target: leverage and liquid trends can move quickly.
- Main risk: leverage, contract rolls, margin, overnight gaps.
- Data requirement: continuous futures with realistic rolls and costs.
- Execution realism: moderate to difficult.
- Modeling difficulty: high.
- Overfitting risk: high.
- Implement now: no.
- Research-only: yes.
- Reject for now: defer until futures framework exists.
- Revisit evidence: roll-adjusted data and margin model.

## 8. Forex Carry/Momentum

- What it is: currency carry or trend/momentum.
- Why it might reach target: leverage can magnify small currency moves.
- Main risk: leverage, financing, spreads, broker execution, regime shifts.
- Data requirement: spot/forward data, rates, spreads.
- Execution realism: difficult.
- Modeling difficulty: high.
- Overfitting risk: high.
- Implement now: no.
- Research-only: yes.
- Reject for now: defer.
- Revisit evidence: realistic financing and spread model.

## 9. Crypto Spot Momentum

- What it is: long-only spot crypto trend or momentum.
- Why it might reach target: high volatility can reach targets fast.
- Main risk: crash risk, exchange data quality, fees, 24/7 market handling.
- Data requirement: clean exchange OHLCV with fees and delisting awareness.
- Execution realism: moderate but exchange-specific.
- Modeling difficulty: moderate to high.
- Overfitting risk: high.
- Implement now: no.
- Research-only: yes.
- Reject for now: defer.
- Revisit evidence: exchange-specific data and fee/slippage assumptions.

## 10. Crypto Leverage/Perpetuals

- What it is: leveraged crypto futures/perpetuals.
- Why it might reach target: leverage and volatility.
- Main risk: liquidation, funding, gaps, exchange risk.
- Data requirement: perp prices, funding, liquidations, bid/ask.
- Execution realism: difficult.
- Modeling difficulty: very high.
- Overfitting risk: very high.
- Implement now: no.
- Research-only: yes.
- Reject for now: yes.
- Revisit evidence: dedicated leveraged derivatives framework.

## 11. Bonds / Treasury / Cash Proxies

- What it is: BIL, SHY, IEF, TLT, SGOV-like cash or Treasury exposure.
- Why it might reach target: usually not target engine, but can reduce drawdown.
- Main risk: rate shocks and false cash assumptions.
- Data requirement: daily ETF data and yield assumptions.
- Execution realism: high.
- Modeling difficulty: low to moderate.
- Overfitting risk: low to moderate.
- Implement now: benchmark/defensive only.
- Research-only: yes.
- Reject for now: no.
- Revisit evidence: cash drag and yield treatment.

## 12. Gold / Commodities Through ETFs

- What it is: GLD or commodity ETFs.
- Why it might reach target: diversifying trend windows.
- Main risk: regime-specific behavior and whipsaw.
- Data requirement: ETF OHLCV.
- Execution realism: high.
- Modeling difficulty: moderate.
- Overfitting risk: moderate.
- Implement now: yes as ETF component, not standalone promise.
- Research-only: yes.
- Reject for now: no.
- Revisit evidence: contribution and concentration.

## 13. Volatility Products

- What it is: VIX-linked ETPs or volatility strategies.
- Why it might reach target: volatility spikes can be large.
- Main risk: path dependency, decay, product mechanics, blowups.
- Data requirement: product-specific data, term structure, roll costs.
- Execution realism: difficult.
- Modeling difficulty: very high.
- Overfitting risk: very high.
- Implement now: no.
- Research-only: memo only.
- Reject for now: yes.
- Revisit evidence: dedicated volatility-product framework.

## 14. Intraday / Day Trading

- What it is: opening range breakout, VWAP, scalping, or intraday momentum.
- Why it might reach target: more opportunities and tighter risk in theory.
- Main risk: fills, latency, spread, overtrading, data quality.
- Data requirement: intraday bid/ask or high-quality bars.
- Execution realism: difficult.
- Modeling difficulty: high.
- Overfitting risk: very high.
- Implement now: no.
- Research-only: yes.
- Reject for now: defer.
- Revisit evidence: clean intraday data and fill assumptions.

## 15. Event / News Strategies

- What it is: earnings, news, analyst, macro, or event-driven momentum.
- Why it might reach target: event volatility can be large.
- Main risk: timestamp leakage and unavailable historical event feeds.
- Data requirement: point-in-time event timestamps and prices.
- Execution realism: difficult.
- Modeling difficulty: very high.
- Overfitting risk: very high.
- Implement now: no.
- Research-only: memo only.
- Reject for now: defer.
- Revisit evidence: reliable point-in-time event data.

## 16. AI-Assisted Strategy Selection

- What it is: AI summarization, audit, or market-condition interpretation.
- Why it might reach target: it might help review evidence, but not create edge by itself.
- Main risk: narrative overconfidence and hidden discretion.
- Data requirement: evidence packets and audit files.
- Execution realism: not applicable unless used for trading decisions.
- Modeling difficulty: high if decisions affect trades.
- Overfitting risk: high.
- Implement now: no trading influence.
- Research-only: report-audit later.
- Reject for now: reject as trade gate.
- Revisit evidence: use only for non-trading audit summaries.
