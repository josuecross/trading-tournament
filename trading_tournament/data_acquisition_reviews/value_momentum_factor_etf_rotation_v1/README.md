# Value/Momentum Factor ETF Rotation Data Acquisition Review

This packet reviews data acquisition gates for `value_momentum_factor_etf_rotation_v1`.

It does not download data, call provider APIs, create API keys, store credentials, implement a strategy, run a backtest, change paper-forward rules, or make a real-money recommendation.

Correction from the prior cache-only review: missing from local cache is not the same as data unavailable. MTUM, VLUE, VTV, QUAL, USMV, and SPLV are now classified as `data_acquisition_required` / `provider_review_required`, not permanent `data_unavailable`.

Decision: `conditional_pending_terms_or_api_key`.
