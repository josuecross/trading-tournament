# Managed Futures ETF Wrapper Risk Policy

Future research_sample must evaluate profit metrics: median final equity, mean final equity, upper-percentile final equity, best-window final equity, and +300/+400 target-before-stop rates.

Future research_sample must evaluate risk metrics: worst drawdown, median drawdown, -$600 stop-hit rate, worst loss window, loss-window rate, profit-to-drawdown ratio, and whether short history makes the result unreliable.

Practical risk review must include fund inception date, history length, missing data, high fee / wrapper behavior warning, and possible regime dependency.

Decision rules:

- If row is additive but too slow, watchlist.
- If row improves drawdown but kills target power, too_slow.
- If row breaches drawdown budget, too_risky.
- If row only duplicates bonds/GLD/BIL, duplicate_or_near_duplicate.
- If row has promising target/risk and additive behavior, promotion_review_candidate.
