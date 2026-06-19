# Dual Momentum PAA ETF Wrapper Risk Policy

Future research_sample must evaluate profit metrics: median final equity, mean final equity, upper-percentile final equity, best-window final equity, and +300/+400 target-before-stop rates.

Future research_sample must evaluate risk metrics: worst drawdown, median drawdown, -$600 stop-hit rate, worst loss window, loss-window rate, profit-to-drawdown ratio, and whether protection makes it too slow.

Practical risk review must include tactical rule overfitting, too many filters, BIL-heavy behavior, duplication with GROR / SPY_200d, and history sensitivity.

Decision rules:

- If row improves drawdown but kills target power, too_slow.
- If row breaches drawdown budget, too_risky.
- If row is mostly SPY_200d or GROR duplicate, duplicate_or_near_duplicate.
- If row has useful target/risk and additive behavior, promotion_review_candidate.
- If all rows are slow/duplicate, move to GTAA benchmark lane.
