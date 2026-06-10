# Runtime And Storage Review

Individual-stock research is much larger than ETF/fund testing.

## Estimated Scale

- symbol count: thousands of current and delisted securities,
- daily row count: millions to tens of millions depending on history and universe,
- local storage: potentially gigabytes after raw prices, adjusted prices, metadata, corporate actions, and cache indexes,
- runtime: slow without efficient columnar cache and precomputed universe membership,
- test runtime: must use small fixtures,
- research_sample runtime: must be capped and sampled,
- candidate_exhaustive runtime: potentially heavy and not approved here.

## Cache And Metadata Needs

Future data work needs provider metadata, universe membership dates, adjustment metadata, delisting fields, symbol histories, cache hashes, and quality summaries.

Conclusion: sustainable one-person research is possible only with a well-scoped provider, compact cache format, runtime budgets, and strict sampling before exhaustive validation.

