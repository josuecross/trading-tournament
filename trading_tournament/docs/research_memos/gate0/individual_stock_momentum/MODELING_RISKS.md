# Modeling Risks

| Risk | How It Can Fool The Project | Mitigation |
|---|---|---|
| Lookahead bias | Uses data unavailable at ranking time. | Enforce prior-close signals and point-in-time universe membership. |
| Survivorship bias | Excludes failed stocks and overstates returns. | Require survivorship-free data. |
| Delisting bias | Ignores bankruptcies or terminal losses. | Include delisting returns or conservative terminal marks. |
| Corporate action errors | Split/dividend issues create false momentum. | Preserve raw and adjusted audit fields. |
| Earnings timestamp leakage | Uses earnings dates known after the fact. | Require point-in-time event data or avoid earnings-sensitive rules. |
| Universe rebalance timing | Adds names before they were investable. | Define rebalance calendar and membership lag. |
| Ranking window overfitting | Chooses lookbacks that fit history. | Pre-specify windows before testing and avoid grid search. |
| Liquidity filter overfitting | Tunes filters to keep winners and drop losers. | Predefine liquidity thresholds in Gate 1. |
| Stop-loss artifacts | Daily bars misrepresent intraday stops. | Use conservative gap-through-stop rules. |
| Same-bar stop/target ambiguity | Chooses favorable fill order. | Use stop-first convention for same-bar conflicts. |
| Top-trade concentration | A few winners explain most profit. | Report contribution and concentration diagnostics. |
| Regime dependence | Works only in specific bull markets. | Test by regime and rolling windows. |
| Market beta correlation | Results are mostly benchmark exposure. | Compare to SPY, stock universe, and ETF momentum baselines. |
| Repeated redesign | Keeps changing screens until they work. | Gate policy, anti-overfitting log, and no parameter tuning. |

No model should be considered credible unless these risks are addressed before implementation.

