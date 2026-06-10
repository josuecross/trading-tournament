# Promotion Policy

This policy defines how the research-only trading lab moves a strategy row from exploratory evidence toward deeper validation. It does not approve real-money trading, broker integration, live orders, or order placement.

## What Successful Means

Successful means successful inside this project's evidence framework. A row may be historically useful if it shows meaningful simulated target potential, controlled drawdown behavior, explainable risk, and non-duplicate value versus existing leaders. It is not guaranteed, proven, safe, or reliable income.

## Reasonable Profit

Reasonable profit means evidence that a fixed-rule row can plausibly move a simulated $3,000 account toward +$300 or +$400 before stop loss, while staying near the $600 drawdown budget. The lab values target power only when it survives stop-aware and drawdown-aware review.

## Evidence Tiers

- `research_sample success`: early fixed-rule evidence. It can justify watchlist status, diagnostics, or candidate_exhaustive queue review, but it is non-final.
- `candidate_exhaustive candidate`: a row with enough target, drawdown, stop, stress, and duplicate-risk evidence to deserve a future exhaustive validation prompt.
- `paper-forward candidate`: a row that has passed candidate validation and a separate paper-forward review with frozen rules.
- `real-money evidence`: out of scope. This project does not approve real-money trading.

## Promotion Path

The intended path is:

`research_sample -> promotion_review -> candidate_exhaustive_queue -> candidate_exhaustive -> paper_forward_review`

Promotion review may queue a row for candidate_exhaustive, but it must not run candidate_exhaustive automatically. Paper-forward activation always requires a separate explicit review.

## Fast Promotion Principle

Promote quickly only when the row shows:

- meaningful +300/+400 target potential,
- acceptable drawdown and stop behavior,
- no obvious stress fragility,
- no risk-budget breach,
- no near-duplicate behavior versus existing leaders,
- enough diagnostics to explain why it adds value,
- no active data, terms, provider, instrument, or policy blocker.

Fast promotion removes unnecessary friction. It does not weaken evidence gates.

## Watchlist, Rejection, And Blocking

Rows stay on watchlist when they are interesting but not ready for deeper validation. Rows are rejected or marked too risky/too slow when evidence is enough to decide. Rows are blocked when data access, provider terms, survivorship controls, instrument mechanics, or execution realism are unresolved.

## Duplicate Handling

Rows that mainly inherit existing leader behavior, lack incremental target windows, or show high overlap/correlation with an existing leader should be marked duplicate_or_near_duplicate instead of promoted. A duplicate may remain useful as a benchmark or diagnostic row.

## Risk-Budget Handling

A high-upside row that breaches the $600 drawdown budget, has high stop-hit rates, or needs unapproved leverage, margin, shorting, futures, options, forex, intraday, broker, or live-order mechanics should not be promoted. It should be marked too_risky or blocked.

## Required Evidence Before Promotion

Candidate_exhaustive queue review requires target-before-stop rates, stop-hit rates, worst drawdown, stress evidence when available, duplicate-risk evidence, evidence tier, latest evidence path, and clear promotion reason. Missing fields must be named directly rather than hidden behind vague "more diagnostics required" language.

## Protected Rows

Active paper/demo observations, frozen controls, historical leaders, and benchmark/control rows may be preserved even when they are not perfect. Preservation means do not mutate or delete them; it does not mean future profitability is guaranteed.
