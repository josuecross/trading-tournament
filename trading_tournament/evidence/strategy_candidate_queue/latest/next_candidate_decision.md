# Next Candidate Decision

This decision is queue-only. It does not implement any strategy, start a backtest, alter paper-forward rules, or recommend real-money trading.

## Immediate Implementation-Review Candidates

After the current full 30/60/90/180 finalist validation is complete, the first implementation-review candidates are:

1. `qqq_spy_gld_ief_dual_momentum_v1`
   - Reason: It is ETF-testable, minimalist, and may add QQQ growth momentum while retaining GLD/IEF/BIL defensive assets.
   - Required first check: Confirm QQQ data is cached or separately approved for later download, and confirm the rule is not just a higher-risk duplicate of current top2 asset-class momentum.

2. `value_momentum_factor_etf_rotation_v1`
   - Reason: Value plus momentum has stronger literature priors than many ad hoc ETF rotations.
   - Required first check: Review ETF proxy history, inception dates, and whether MTUM/VLUE/VTV/QUAL/USMV are valid for this project.

3. `sector_top2_momentum_simple_v1`
   - Reason: Sector dispersion may improve target probability.
   - Required first check: Resolve the exact fresh-window stream issue for the existing A-sector family, or approve a clean minimal version that does not modify `A_ETF_sector_momentum`.

## Immediate Research-Only Candidate

1. `individual_stock_momentum_gate1b_v1`
   - Reason: The return-driver prior is meaningful, but the project cannot treat current-ticker or toy stock data as serious evidence.
   - Required next action: Gate 1B cost/access review for survivorship-free data, delisting treatment, point-in-time universe, corporate actions, execution model, and runtime.

## Data-Gated Before Code

- `managed_futures_proxy_etf_trend_v1`
- `commodity_basket_etf_momentum_v1`
- `crypto_spot_tsmom_tier2_review_v1`

## Not Allowed For Code Now

- Options premium
- Options directional
- Futures trend following
- Forex carry/momentum
- Intraday/day trading
- Volatility products
- Crypto leverage/perps
- AI trading gate

## Decision

If the current finalist validation still leaves room for a new ETF candidate, start with `qqq_spy_gld_ief_dual_momentum_v1` only after data availability and duplicate-risk review. If QQQ data is unavailable or the rule is too close to current top2 momentum, review `value_momentum_factor_etf_rotation_v1` next. Do not code any gated or rejected family before gates pass.
