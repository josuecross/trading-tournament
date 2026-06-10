# Duplicate Risk Review

## Compared Rows

- `asset_class_tsmom_top2_v1`
- `asset_class_tsmom_equal_weight_v1`
- `SPY_200d_trend_model`
- `combo_SPY200d_GLD_50_50_v1`

## Main Risk

QQQ may mostly add growth/equity beta instead of a genuinely new diversifying return driver.

## Candidate Versus Top2

Top2 currently ranks SPY, GLD, and IEF. Adding QQQ creates a different universe, but the likely overlap is high because QQQ and SPY can both express equity momentum. A later implementation must report how often QQQ is selected instead of SPY and whether that improves stop-aware results after stress costs.

## Candidate Versus Equal Weight

Equal-weight TSMOM diversifies across eligible risky assets. The QQQ candidate may become more concentrated if QQQ dominates relative momentum. That concentration must be measured.

## Candidate Versus SPY_200d

QQQ could behave like a higher-beta SPY trend sleeve. It must beat SPY_200d without simply spending more drawdown budget.

## Candidate Versus Combo

The combo is the current practical drawdown-aware leader. The QQQ candidate must show a better stop-aware profit/risk tradeoff than the combo, not just higher target rates.

## Later Duplicate Detection Requirements

A future implementation must record:

- canonical rule hash
- asset universe
- rebalance frequency
- ranking lookback
- trend filter
- cash fallback
- selected asset count
- weighting rule
- execution timing
- max gross exposure
- leverage setting
- realized allocation share to QQQ, SPY, GLD, IEF, and BIL

## Conclusion

Duplicate risk is conditional but not a blocker. The candidate may proceed to research_sample implementation only if the implementation prompt includes allocation concentration reporting and benchmark failure criteria.

