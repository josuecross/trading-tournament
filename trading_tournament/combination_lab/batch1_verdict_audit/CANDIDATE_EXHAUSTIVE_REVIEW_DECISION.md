# Candidate Exhaustive Review Decision

Decision: `more_diagnostics_required_before_candidate_exhaustive_decision`

This audit does not approve a candidate_exhaustive run and does not run candidate_exhaustive.

Rationale:

- `combo_plus_managed_futures_80_20_v1` has the best stop-aware practical rank and a strong 180-day target/drawdown profile, but 30/60-day target rates are 0.0%.
- `top2_plus_managed_futures_80_20_v1` has the strongest 180-day +300/+400 rates, but it is also short-history fund-wrapper proxy evidence and highly correlated with top2.
- `combo_plus_top2_50_50_v1` is too duplicative to justify candidate_exhaustive.
- Target-window co-movement is unavailable.
- Managed-futures rows require short-history labeling and cannot be treated as direct futures strategy evidence.

Future candidate_exhaustive review may be considered only in a separate prompt. That future review must specify:

- exact candidate
- exact horizons
- expected runtime
- short-history label if managed futures is involved
- correlation/co-movement requirements
- failure criteria

