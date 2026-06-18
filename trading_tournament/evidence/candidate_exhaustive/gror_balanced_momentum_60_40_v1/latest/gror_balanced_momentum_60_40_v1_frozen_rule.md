# GROR Balanced Momentum 60/40 v1 Frozen Rule

Strategy id: `gror_balanced_momentum_60_40_v1`

Family: `global_risk_on_risk_off_etf`

Rule:

- Monthly rebalance.
- Universe:
  - SPY
  - QQQ
  - GLD
  - IEF if available and QA passes
  - BIL
- Risk-on candidates:
  - SPY
  - QQQ
- Defensive candidates:
  - GLD
  - IEF
- Rank risk-on assets by 126-day return.
- Rank defensive assets by 126-day return.
- Hold 60% best eligible risk-on asset if SPY is above its 200-day SMA.
- If SPY is not above its 200-day SMA, hold 60% BIL.
- Hold 40% best eligible defensive asset if available and eligible.
- If no defensive asset is available and eligible, hold 40% BIL.
- Eligibility uses close above 200-day SMA.
- No leverage.
- No margin.
- No shorting.
- No options/futures/forex/crypto/intraday.
- No broker/live-order path.
- No real-money recommendation.
- No parameter optimization.
- No mid-run rule changes.
