# Gate 0 Memo: Individual Stock Momentum

Research question: could individual stock momentum theoretically improve the probability of reaching +$300 to +$400 from a $3,000 simulated account before a -$600 / -20% stop, and what must be true before this instrument class deserves implementation?

## 1. Research-Only Statement

This memo is research-only. It does not approve implementation, validate a strategy, recommend real-money trading, connect to a broker, place orders, or change the ETF Phase 1 system.

## 2. Why Individual Stocks Are Being Considered

Individual stocks are being considered because the broader project question is not ETF-only. Stocks can move more than broad ETFs, and cross-sectional momentum has historically documented research priors. That makes the family worth mapping before dismissing it.

## 3. Why Individual Stocks Might Reach The Target Faster Than ETFs

Single names can have larger dispersion than ETFs. A stock momentum portfolio may capture stronger winners than sector or index ETFs, so a +10% to +13.3% target may be more reachable in theory.

## 4. Why Individual Stocks Are Riskier Than ETFs

The same dispersion creates gap risk, earnings risk, liquidity risk, and concentration risk. A small account can be forced into too few names, making a -20% project stop easier to hit.

## 5. Main Anomaly Or Strategy Logic

The broad prior is cross-sectional momentum: rank stocks by past returns over a defined lookback, hold stronger names, avoid weak names, and rebalance objectively. Variants may include trend filters, liquidity filters, sector controls, and earnings exclusions, but those choices are not approved here.

## 6. What Historical Evidence Generally Exists

Cross-sectional momentum is historically documented in academic and practitioner research across equities and other assets. This is a prior to verify, not a validation of this project.

## 7. Why Evidence Does Not Automatically Transfer To This Project

Published evidence may use institutional data, survivorship-free universes, transaction cost assumptions, broad diversification, and long horizons. This project has a $3,000 simulated account, a +$300/+400 challenge metric, a -$600 stop, and strict evidence requirements.

## 8. Data Requirements

Serious testing requires point-in-time universes, delisted stocks, corporate actions, adjusted OHLCV, liquidity fields, benchmark universe definitions, and earnings date handling. Current yfinance current-ticker data is not enough.

## 9. Execution Requirements

The project must define realistic spreads, slippage, open fills, gap-through-stop behavior, notional caps, small-account position sizing, and liquidity filters before code.

## 10. Universe Construction Requirements

The universe must specify market cap, price, liquidity, exchange, IPO seasoning, sector membership, and rebalance timing. Using today's S&P 500 or Nasdaq 100 across history is not acceptable.

## 11. Survivorship And Delisting Risks

Ignoring bankruptcies, delistings, mergers, and historical index membership can materially overstate stock momentum results. No implementation should start without a plan for these risks.

## 12. Earnings And Gap Risks

Momentum names can gap through stops around earnings, guidance, litigation, and macro shocks. The project must decide whether earnings windows are avoided, modeled, or explicitly accepted.

## 13. Liquidity And Spread Risks

Less liquid stocks can show attractive historical moves while being difficult to trade at modeled prices. Low-float, penny, and illiquid stocks are not acceptable for this project.

## 14. Small-Account Suitability

A $3,000 account limits diversification. Long-only fractional shares may help, but concentration, notional caps, and position count must be modeled honestly.

## 15. Expected Target Contribution

Individual stock momentum may improve upside target probability compared with ETFs, but only if the added volatility does not increase stop hits, slippage loss, and concentration risk too much.

## 16. Why It May Fail

It may fail because momentum crashes, market beta dominates, costs consume edge, winners concentrate in a few names, data is biased, or the account cannot diversify enough.

## 17. What Would Disqualify It

Disqualifiers include no survivorship-free data, no delisting treatment, no realistic liquidity/spread model, no benchmark universe, too few positions for risk control, or high rolling stop-hit rates.

## 18. What Evidence Is Required Before Gate 1

Gate 1 requires data vendor candidates, survivorship and delisting feasibility, corporate action handling, liquidity rules, earnings treatment, benchmarks, slippage assumptions, risk model, validation plan, and kill criteria.

## 19. Preliminary Verdict

Individual stock momentum is plausible and historically documented, but implementation-sensitive and not validated in this project. The preliminary verdict is to approve Gate 1 feasibility review only. No strategy code should be written yet.

