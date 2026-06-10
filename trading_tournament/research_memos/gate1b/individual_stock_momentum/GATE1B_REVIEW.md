# Gate 1B Review

## Why Review Individual Stock Momentum

Individual stock momentum is worth reviewing because it is a historically distinct return-driver family from the ETF/fund-level candidates already tested. It may expose cross-sectional momentum behavior, breadth effects, turnover/cost pressure, and stock-specific crash risk that cannot be evaluated with broad ETF proxies alone.

## Why It Is Not Implementation-Ready

The lane is not currently implementation-ready because credible individual-stock testing requires survivorship-free data, delisted names, delisting returns where possible, point-in-time universe construction, robust corporate-action handling, liquidity filters, execution-cost assumptions, and sustainable storage/runtime. Current-ticker-only data cannot support serious validation.

## Data Flaws That Could Make Results Meaningless

- survivorship bias from using only currently listed tickers,
- missing delisting returns,
- stale or incorrect split/dividend adjustments,
- symbol changes treated as separate securities,
- today's index membership projected backward,
- missing historical liquidity,
- lookahead from universe selection,
- under-modeled spreads, slippage, and turnover.

## Realistic First Credibility Tier

The realistic first tier is Tier 1 toy/current-ticker exploratory or Tier 2 credible prototype only if a provider can supply delisted-name coverage and usable point-in-time metadata. Tier 3 candidate validation requires stronger survivorship-free universe and delisting treatment.

## Requirements Before Future Implementation Prompt

Before any implementation prompt, the project must complete provider/cost/access review, define a survivorship policy, define universe membership timing, specify corporate-action checks, define liquidity/cost filters, cap runtime, and define evidence labels. It must also confirm that no API key or secret will be committed.

## Must Remain Forbidden

Forbidden next actions include implementing stock momentum without a data gate, treating current-ticker-only results as serious evidence, ignoring delistings, ignoring survivorship bias, running paper-forward, adding broker integration, placing live orders, or making any real-money recommendation.

## Can Exploratory Testing Be Useful Without Institutional-Grade Data?

Yes, but only as Tier 1 toy evidence. It can verify code-path ergonomics, rough turnover pressure, and whether the idea is computationally feasible. It cannot answer whether the strategy works.

## Allowed Conclusions From Exploratory Evidence

- code path works or fails,
- runtime/storage are manageable or not,
- turnover and liquidity pressure look high or low,
- evidence is toy/current-ticker only.

## Forbidden Conclusions

- strategy is profitable,
- strategy is validated,
- stock momentum is better than ETF finalists,
- paper-forward is justified,
- real-money trading is recommended.

No real-money recommendation is made.

