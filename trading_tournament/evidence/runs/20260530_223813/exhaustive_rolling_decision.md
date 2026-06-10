# Exhaustive Rolling Decision

This file is research-only paper/demo evidence. It is not a real-money trading recommendation.

Replay rolling diagnostics are secondary. The table below is based on independent rolling-window simulations.

## 90-Day Summary
                  variant_name slippage_label  number_of_windows          window_sampling_method  pct_windows_target_300_before_stop  pct_windows_target_400_before_stop  pct_windows_any_stop_hit  pct_windows_trailing_stop_hit  median_max_drawdown  worst_max_drawdown
current_no_cash_proxy_alpha_AB       standard                 24 deterministic_stratified_sample                            0.166667                               0.125                       0.0                            0.0          -135.862590         -277.367915
    evidence_dual_momentum_taa       standard                 24 deterministic_stratified_sample                            0.000000                               0.000                       0.0                            0.0          -113.753971         -201.958266

## Decision Answers
- Best 90-day +$300 before stop rate: `current_no_cash_proxy_alpha_AB` at 16.67% using the robust minimum across standard/stress slippage.
- Best 90-day +$400 before stop rate: `current_no_cash_proxy_alpha_AB` at 12.50% using the robust minimum across standard/stress slippage.
- Best stress-slippage stability: ``.
- Lowest drawdown risk: `evidence_dual_momentum_taa` by the least-bad robust median drawdown.
- Best current candidate: `current_no_cash_proxy_alpha_AB` with status `leading_watchlist_candidate`.
- Target probability assessment: `watchlist_not_validated`.
- C/D/E status: `remain_rejected_or_shadow_only`.
- Fragile variants: [].

## Interpretation Rules Applied
- If 90-day +$300 before stop rate is below 10%, mark low-probability.
- If 90-day +$400 before stop rate is below 5%, mark very low-probability.
- If stress slippage materially worsens target rates or drawdown, mark fragile.
- If original_full_tournament is weaker than A/B variants, do not forward-test it.
- If current_no_cash_proxy_alpha_AB beats current_momentum_only_A and current_core_only_AB under both standard and stress, mark it as leading watchlist candidate, not validated.
- Nothing is marked validated unless evidence is strong across both standard and stress.
