# Managed-Futures Proxy Risk Review

## Representation Risk

ETF/fund proxies can provide convenient daily adjusted-price series, but they are not clean substitutes for a direct managed-futures trend-following system. The project should treat proxy results as fund-wrapper evidence, not as evidence about a full futures program.

## Methodology Risk

Different funds may use different trend models, markets, contract rolls, collateral practices, risk targets, fees, turnover, and implementation constraints. A future result could be driven by one sponsor's methodology rather than by a general managed-futures return driver.

## Hidden Futures Exposure

Some proxy funds may hold futures internally. The project can model the wrapper as an ETF/fund price series for research_sample only if the review explicitly accepts wrapper-level modeling. That does not mean the project has modeled futures rolls, margin, leverage, financing, or execution.

## Short-History Risk

Many managed-futures ETFs or funds have shorter public histories than SPY/BIL and may miss older crisis, rate, commodity, and inflation regimes. Short inception history can overstate confidence and should block candidate_exhaustive until documented.

## Unsuitable Proxy Conditions

The proxy should be rejected or deferred if data history is too short, provider metadata is weak, methodology is too opaque, fund behavior does not diversify current finalists, drawdown/stop behavior is worse than combo/top2, or exact fresh-window rolling streams cannot be produced.

No real-money recommendation is made.

