# Data Acquisition Reviews

This directory holds review-only packets for market-data acquisition gates.

The project distinguishes missing local cache from unavailable data. A symbol can be missing from cache while still requiring provider lookup, terms review, acquisition approval, and data-quality checks before any strategy work.

Allowed data states:

- `available_in_local_cache`
- `data_acquisition_required`
- `provider_available_not_cached`
- `provider_review_required`
- `data_acquired_pending_quality_check`
- `data_rejected`
- `data_unavailable`

This process does not download data, does not create API keys, does not store credentials, does not implement strategies, does not run backtests, and does not make real-money recommendations. Raw OHLCV must not be included in compact or advisor evidence packets.
