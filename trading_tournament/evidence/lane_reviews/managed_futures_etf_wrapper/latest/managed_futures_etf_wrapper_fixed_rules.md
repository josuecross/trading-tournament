# Managed Futures ETF Wrapper Fixed Rules

## `mf_wrapper_top1_trend_v1`

Universe: `DBMF;KMLM;CTA;FMF;WTMF;BIL`

Monthly rebalance; wrappers eligible if close > 200-day SMA; rank eligible wrappers by 126-day return; hold top 1; otherwise 100% BIL.

Purpose/profit driver: Pure managed-futures wrapper trend/momentum selection.

No leverage by our system. No direct futures contracts. No parameter optimization or grid search.

## `mf_wrapper_top2_risk_adjusted_v1`

Universe: `DBMF;KMLM;CTA;FMF;WTMF;BIL`

Monthly rebalance; eligible wrappers must be above 200-day SMA; rank by 126-day return / 60-day realized volatility; hold top 2 equally; unused allocation to BIL.

Purpose/profit driver: Diversified managed-futures wrapper selection with a fixed risk-adjusted ranking.

No leverage by our system. No direct futures contracts. No parameter optimization or grid search.

## `mf_wrapper_plus_spy_70_30_v1`

Universe: `SPY;DBMF;KMLM;CTA;FMF;WTMF;BIL`

Monthly rebalance; 70% SPY if SPY > 200-day SMA else BIL; 30% best eligible wrapper by 126-day return else BIL.

Purpose/profit driver: Managed-futures wrapper sleeve may improve an equity trend sleeve's drawdown/profit frontier.

No leverage by our system. No direct futures contracts. No parameter optimization or grid search.

## `mf_wrapper_plus_dsr_vm_combo_proxy_v1`

Universe: `protected_reference_proxy;DBMF;KMLM;CTA;FMF;WTMF;BIL`

Conditional only; separate research row; 70% existing protected reference proxy and 30% best eligible wrapper if safely inferable, otherwise evidence_missing.

Purpose/profit driver: Tests additive sleeve value without mutating active VM, DSR, or combo observations.

No leverage by our system. No direct futures contracts. No parameter optimization or grid search.

## `mf_wrapper_defensive_cash_switch_v1`

Universe: `DBMF;KMLM;CTA;FMF;WTMF;BIL`

Monthly rebalance; equal weight wrappers above 200-day SMA; if fewer than 2 qualify, 50% best wrapper and 50% BIL; if none, 100% BIL.

Purpose/profit driver: Lower-risk wrapper basket with cash fallback.

No leverage by our system. No direct futures contracts. No parameter optimization or grid search.
