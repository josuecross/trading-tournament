# Short History And Managed-Futures Label Audit

Audit decision: `short_history_label_preserved`

Managed-futures combinations:

- `combo_plus_managed_futures_80_20_v1`
- `top2_plus_managed_futures_80_20_v1`

Required label:

`fund_wrapper_proxy_short_history_limited_inception_research_sample_only`

## Label verification

The managed-futures rows preserve the required label in the Profit Exploration outputs and Strategy Lab registry.

## Interpretation limits

The managed-futures sleeve is based on `managed_futures_proxy_etf_trend_v1`, which uses DBMF/KMLM fund-wrapper proxy evidence. This is not direct futures strategy evidence.

The audit preserves these limits:

- no futures contract logic
- no futures roll modeling
- no margin modeling
- no leverage model
- no shorting model
- no paper-forward approval from this audit
- no real-money recommendation

## History limitation

The managed-futures wrapper proxy evidence begins in the modern DBMF/KMLM availability window. It must not be treated as equivalent to 2007+ or 2008-crisis-covered evidence.

Any future candidate_exhaustive review, if allowed by a later prompt, must remain explicitly short-history labeled and must not imply direct managed-futures strategy validation.

