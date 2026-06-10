# Verdict Audit

Audit decision: `verdict_labels_corrected_with_no_candidate_exhaustive_run`

Source evidence:

- `evidence/combination_lab/latest/combination_batch1_results.csv`
- `evidence/combination_lab/latest/combination_batch1_rankings.csv`
- `evidence/combination_lab/latest/combination_batch1_risk_summary.csv`
- `evidence/combination_lab/latest/combination_batch1_correlation_diagnostics.csv`
- `evidence/profit_exploration/latest/rolling_profit_distribution.csv`

## 1. Were all three too_slow verdicts justified?

No. The original `too_slow` labels were directionally useful as a first-pass rejection of immediate advancement, but they were too coarse for all three rows.

- `combo_plus_top2_50_50_v1` is better described as `duplicate_or_near_duplicate` because its correlations to combo and top2 are both above 0.92 and its duplicate warning is true.
- `combo_plus_managed_futures_80_20_v1` is not generically too slow. It is slow at 30/60 days but shows stronger 180-day target rates and lower drawdown usage than the current leaders over the available short-history sample.
- `top2_plus_managed_futures_80_20_v1` has the same broad pattern: weak 30/60-day target rates, but stronger 180-day +300/+400 rates and lower drawdown-budget usage.

## 2. Is combo_plus_managed_futures_80_20_v1 truly too slow?

Only at the short horizons. Its 30-day and 60-day +300/+400 rates are 0.0%, so `short_horizon_too_slow` is supported. The generic `too_slow` label is not precise because the 180-day profile is stronger:

- 180d +300: 64.1%
- 180d +400: 53.8%
- 180d +600: 41.0%
- 90d/180d stop-hit: 0.0% / 0.0%
- 90d/180d worst drawdown: -$321.11 / -$372.25
- 90d/180d risk-budget usage: 53.5% / 62.0%

## 3. Does the 180d profile contradict generic too_slow?

Yes. The 180-day +300/+400/+600 profile contradicts a generic label that implies the row lacks target potential. The better interpretation is:

`short_history_watchlist`

This keeps the candidate out of candidate_exhaustive today while preserving that it may deserve more diagnostic review.

## 4. Should verdicts distinguish more states?

Yes. The audit recommends distinguishing:

- `short_horizon_too_slow`: weak 30/60-day behavior despite possible longer-horizon strength.
- `long_horizon_watchlist`: 180-day evidence is interesting but not enough for advancement.
- `short_history_watchlist`: managed-futures wrapper-proxy combinations with short inception evidence.
- `candidate_exhaustive_review_required_short_history_labeled`: not assigned here; it may be considered only after stronger diagnostics.

## 5. Most appropriate verdict by combination

| combination | prior verdict | audited verdict | rationale |
| --- | --- | --- | --- |
| `combo_plus_top2_50_50_v1` | `too_slow` | `duplicate_or_near_duplicate` | High correlation to combo/top2 and duplicate warning true. |
| `combo_plus_managed_futures_80_20_v1` | `too_slow` | `short_history_watchlist` | Stronger 180-day target/drawdown profile but 30/60-day target rates are 0.0%, evidence starts in the managed-futures proxy era, and correlation to combo is high. |
| `top2_plus_managed_futures_80_20_v1` | `too_slow` | `short_history_watchlist` | Similar long-horizon improvement but still short-history wrapper-proxy evidence and highly correlated to top2. |

## 6. Should registry status be corrected?

Yes. Strategy Lab status should be corrected to the audited labels above. This is a status correction only. It does not activate paper-forward, does not run candidate_exhaustive, and does not change strategy rules.

## 7. Evidence that would justify candidate_exhaustive later

Future candidate_exhaustive review would require:

- explicit short-history label for any managed-futures blend
- target-window co-movement diagnostics
- stronger drawdown co-incidence analysis
- benchmark-relative target and stop behavior across exact fresh windows
- evidence that improvement is not just a short sample artifact
- explicit runtime/horizon plan in a future prompt

