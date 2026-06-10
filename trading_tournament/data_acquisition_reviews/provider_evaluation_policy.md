# Provider Evaluation Policy

This policy governs future market-data acquisition reviews. It does not authorize a download by itself.

## Availability Gate

Pass criteria: provider coverage for required symbols is confirmed before acquisition.  
Fail criteria: provider does not cover required symbols or coverage is unknown and cannot be verified.  
Required evidence: provider coverage notes, symbol list, and planned acquisition scope.  
Coding allowed after passing: only a dedicated data-download prompt may be considered; no strategy code.

## History Gate

Pass criteria: enough history exists for 200-day SMA, 126-day momentum, and 30/60/90/180 rolling windows after warmup.  
Fail criteria: common overlap is too short or cannot be established.  
Required evidence: expected first date, last date, and overlap plan.  
Coding allowed after passing: data acquisition script or adapter only if separately approved.

## Adjustment Gate

Pass criteria: adjusted prices are available, or corporate-action data is sufficient to compute a documented adjusted convention.  
Fail criteria: unclear splits/dividends or inconsistent adjusted-close semantics.  
Required evidence: adjustment-field documentation and normalization plan.  
Coding allowed after passing: normalization tests only if data acquisition is approved.

## Reproducibility Gate

Pass criteria: downloaded data can be cached with provider id, timestamp, request/config hash, and symbol list.  
Fail criteria: one-off manual data without provenance.  
Required evidence: metadata schema and cache path plan.  
Coding allowed after passing: acquisition prompt may include metadata capture.

## Terms/Licensing Gate

Pass criteria: project use and local cache storage are permitted for personal research.  
Fail criteria: terms prohibit caching, analysis, or redistribution of required fields.  
Required evidence: terms review notes and provider constraints.  
Coding allowed after passing: only within reviewed terms.

## API Key/Security Gate

Pass criteria: no secrets are stored in the repo; keys are supplied by environment or local secret store only.  
Fail criteria: API key, token, or credential appears in tracked files or evidence.  
Required evidence: secret-handling plan.  
Coding allowed after passing: keyed provider adapter only if separately approved.

## Quality Gate

Pass criteria: data has sorted dates, no duplicate dates, acceptable missing-day profile, sufficient row count, and sanity checks against existing benchmark symbols.  
Fail criteria: duplicate dates, broken adjusted prices, large unexplained gaps, or insufficient overlap.  
Required evidence: coverage summary, gap report, and comparison checks.  
Coding allowed after passing: strategy research_sample can be considered after implementation review.

## Evidence Gate

Pass criteria: compact/advisor evidence contains metadata and coverage summaries only.  
Fail criteria: raw OHLCV or cache data appears in advisor packets.  
Required evidence: packet scan or manifest.  
Coding allowed after passing: evidence packaging only.
