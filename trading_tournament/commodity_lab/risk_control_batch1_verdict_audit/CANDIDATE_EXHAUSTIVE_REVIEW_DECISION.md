# Candidate Exhaustive Review Decision

Decision: `more_diagnostics_required_before_candidate_exhaustive_decision`

No candidate_exhaustive run is performed by this task.

## Rationale

`combo_plus_commodity_basket_80_20_v1` is the best risk-control candidate, but the case for candidate_exhaustive is not complete:

- It improved the stop-aware score versus base commodity by +93.73.
- It improved the score versus combo by only +4.98, which may be noise without window-level attribution.
- It lagged top2, SPY_200d, and GLD on reported score.
- It has high correlation to combo at 0.962 and high correlation to GLD at 0.816.
- Target-window co-movement is unavailable.
- Exact component contribution is unavailable.
- It is 80% combo sleeve, so the result may be mostly inherited combo behavior with a small commodity tilt.

## Future Review Requirements

Before a future candidate_exhaustive review prompt, require:

- target-window co-movement export for +300/+400/+600 windows versus base commodity, combo, top2, SPY_200d, and GLD.
- component contribution export for combo sleeve, commodity sleeve, and BIL/cash where applicable.
- drawdown-overlap detail with worst drawdown window IDs.
- product/wrapper labels preserved: `commodity_wrapper_evidence_research_sample_only`, `exploratory_public_data`, `not_validated`, `not_paper_forward`, `not_real_money`.
- fixed rule only; no weight tuning, no new symbols, no futures contract logic.

If future diagnostics show truly incremental target windows and non-duplicative drawdown behavior, `combo_plus_commodity_basket_80_20_v1` may be reconsidered for a candidate_exhaustive review prompt. The active combo paper-forward observation remains unchanged.
