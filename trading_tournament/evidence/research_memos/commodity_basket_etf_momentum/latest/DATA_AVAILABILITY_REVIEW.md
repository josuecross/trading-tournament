# Data Availability Review

Local cache inspection found no DBC, PDBC, COMT, GSG, or USCI files under `data/cache/`. No missing data was downloaded.

| symbol | cached_locally | row_count | first_date | last_date | enough_history_for_126d_momentum | enough_history_for_200d_sma | enough_history_for_30_60_90_180_windows_after_warmup | data_status |
|---|---|---:|---|---|---|---|---|---|
| DBC | false | 0 | unavailable | unavailable | false | false | false | missing_data_acquisition_review_required |
| PDBC | false | 0 | unavailable | unavailable | false | false | false | missing_data_acquisition_review_required |
| COMT | false | 0 | unavailable | unavailable | false | false | false | missing_data_acquisition_review_required |
| GSG | false | 0 | unavailable | unavailable | false | false | false | missing_data_acquisition_review_required |
| USCI | false | 0 | unavailable | unavailable | false | false | false | missing_data_acquisition_review_required |

## Questions

1. Which symbols are already cached locally?

   None of the reviewed commodity basket symbols are cached locally.

2. Which symbols are missing?

   DBC, PDBC, COMT, GSG, and USCI are all missing.

3. Is local cache coverage enough for 126-day momentum and 200-day filters if later used?

   No. Missing local data means no momentum or moving-average warmup can be calculated.

4. Does the project need a controlled data acquisition review?

   Yes. A controlled data acquisition review is required before any download.

5. Which provider path should be used if data is missing?

   A yfinance-compatible ETF/fund path may be considered later, subject to provider terms/security review and symbol approval. No provider path is approved by this review alone.

6. Can yfinance-compatible acquisition be considered later?

   Yes, in a future controlled acquisition-review prompt only. It must limit symbols, preserve raw OHLCV only in cache, and create metadata/quality evidence without raw data in advisor packets.

7. What metadata/quality checks are required?

   Required checks include symbol identity, adjusted close availability, split/dividend fields, row count, first/last date, missing values, duplicate dates, volume availability, stale data, inception/common-overlap, and wrapper-specific warnings.

8. Raw OHLCV must remain out of advisor packets.

   Raw OHLCV must remain out of advisor packets. Evidence may include metadata, coverage, quality summaries, and cache manifests only.
