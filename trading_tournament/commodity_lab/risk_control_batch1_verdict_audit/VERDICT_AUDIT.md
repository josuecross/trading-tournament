# Verdict Audit

## Questions

1. Was the base commodity verdict correction valid?

Yes. `commodity_basket_tsmom_top2_v1` had strong target power, but its 90d and 180d worst drawdowns breached the -$600 risk budget: -$680.67 and -$718.24. Risk-budget usage was 113.4% and 119.7%. The corrected verdict `research_sample_candidate_risk_budget_breach` is valid.

2. Was the 200d filter candidate actually risk-reducing?

No, not in the reported 90d/180d windows. `commodity_basket_tsmom_top2_200d_filter_v1` still had -$680.67 at 90d and -$718.24 at 180d, with risk-budget usage of 113.4% and 119.7%. It did not solve the central risk failure.

3. Did the 200d filter behave identically or nearly identically to the base commodity rule?

Nearly identical in the key risk dimensions. The target ladder and worst drawdowns match the base profile closely enough that the filter is not currently useful as a risk-control row.

4. Is this expected or a possible implementation/diagnostic issue?

It could be either. A 200d filter can be ineffective if selected wrappers remained above their 200d SMA during the drawdown windows, but the identical 90d/180d drawdowns should be treated as `filter_ineffective_or_bug_review` until window-level diagnostics confirm whether the filter failed naturally or was not binding.

5. Is half-BIL too slow, or a useful defensive row?

It is a useful defensive diagnostic row but too slow for stronger validation. It reduced 90d/180d worst drawdowns to -$307.74/-$319.65 and eliminated stop hits, but diluted 180d +300/+400 to 33.3%/25.6%. Audited verdict: `too_slow_defensive_watchlist`.

6. Is `combo_plus_commodity_basket_80_20_v1` strong enough for watchlist, candidate_exhaustive review, or rejection?

It is stronger than the standalone commodity risk controls and belongs in diagnostics review, not candidate_exhaustive yet. It reduced drawdown to -$275.02/-$316.93, kept 180d +300/+400 at 64.1%/46.2%, and improved the stop-aware score versus the base commodity row by +93.73 and versus combo by +4.98. However, the +4.98 improvement over combo is small, it lagged top2/SPY_200d/GLD, its daily equity return correlation to combo was 0.962, and target-window independence is unavailable. Audited verdict: `candidate_diagnostics_review_required`.

## Audited Verdicts

| Row | Prior verdict | Audited verdict | Reason |
|---|---:|---:|---|
| `commodity_basket_tsmom_top2_v1` | `research_sample_candidate_risk_budget_breach` | `research_sample_candidate_risk_budget_breach` | Strong targets but 90d/180d drawdown breaches. |
| `commodity_basket_tsmom_top2_200d_filter_v1` | `research_sample_candidate_risk_budget_breach` | `filter_ineffective_or_bug_review` | Did not reduce 90d/180d risk-budget breach; nearly base-like behavior. |
| `commodity_basket_tsmom_top2_half_bil_v1` | `research_sample_candidate` | `too_slow_defensive_watchlist` | Defensive but target-dilutive. |
| `combo_plus_commodity_basket_80_20_v1` | `research_sample_candidate` | `candidate_diagnostics_review_required` | Best row, but high combo similarity and missing target-window/component proof block candidate_exhaustive. |

No candidate_exhaustive run is approved or performed by this audit.
