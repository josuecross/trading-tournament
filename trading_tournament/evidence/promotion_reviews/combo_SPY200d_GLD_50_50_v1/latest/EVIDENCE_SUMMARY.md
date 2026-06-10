# Evidence Summary

## Source Evidence

Primary source: `evidence/profit_exploration/latest/`

Validation status:

- mode: `candidate_exhaustive`
- horizons: 30, 60, 90, 180
- rolling method: `all_possible`
- finality: `exact_all_possible`
- accounting_integrity_status: `passed`
- full_horizon_validation_completed: `true`
- candidate_exhaustive_completed: `true`

## Ranking Evidence

| Metric | Combo | SPY_200d | Top2 |
|---|---:|---:|---:|
| original final_score | 66.77 | 44.14 | 67.05 |
| balanced_drawdown_aware_score_v2 | 101.59 | -38.23 | 6.57 |
| profit_seeking_score | 169.48 | 157.58 | 160.85 |
| drawdown_control_score | 221.47 | 138.18 | 176.33 |
| practical_verdict_v2 | practical_leader | watchlist | promotion_review_candidate |

## 90-Day Evidence

| Metric | Combo | SPY_200d | Top2 |
|---|---:|---:|---:|
| +300 before stop | 20.9% | 24.2% | 21.5% |
| +400 before stop | 9.2% | 10.0% | 9.4% |
| +600 before stop | 1.1% | 1.0% | 0.9% |
| stop-hit rate | 0.0% | 0.5% | 0.0% |
| median stop equity | $3,107.86 | $3,097.12 | $3,098.03 |
| p95 stop equity | $3,414.35 | $3,418.41 | $3,396.01 |
| worst drawdown | -$452.23 | -$661.82 | -$579.66 |

## 180-Day Evidence

| Metric | Combo | SPY_200d | Top2 |
|---|---:|---:|---:|
| +300 before stop | 48.1% | 54.0% | 46.8% |
| +400 before stop | 31.5% | 38.5% | 32.2% |
| +600 before stop | 12.7% | 12.8% | 12.3% |
| stop-hit rate | 0.0% | 4.9% | 1.3% |
| median stop equity | $3,195.27 | $3,193.78 | $3,199.75 |
| p95 stop equity | $3,722.65 | $3,720.94 | $3,670.23 |
| worst drawdown | -$516.49 | -$743.40 | -$655.41 |

## Interpretation

The combo is not the raw target-rate leader. Its promotion-review case is that it improves the stop-aware risk profile while maintaining enough target potential to remain a serious practical challenger.

