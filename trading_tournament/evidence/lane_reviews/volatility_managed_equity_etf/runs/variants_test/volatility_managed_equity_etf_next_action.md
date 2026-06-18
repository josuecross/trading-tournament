# Next Action Decision

Decision: `approve_future_research_sample_prompt`

Exact next allowed action:

`create_volatility_managed_equity_etf_research_sample_prompt`

Reason: this lane is ETF/fund-wrapper compatible, requires no leverage/margin/shorting/options/futures/forex/intraday mechanics, uses fixed variants, keeps active observations untouched, and remains exploratory/non-final until later gates.

Forbidden next actions:

- candidate_exhaustive
- paper_forward_activation
- active combo mutation
- SPY_200d replacement
- live trading
- broker integration
- data download without explicit prompt
- provider API call without explicit prompt
- parameter optimization

This review approves only a future research_sample implementation prompt. It does not implement or run the strategy.
