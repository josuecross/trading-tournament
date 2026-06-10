# Exhaustive Rolling Decision

This file is research-only paper/demo evidence. It is not a real-money trading recommendation.

Replay rolling diagnostics are secondary. The table below is based on independent rolling-window simulations.

## 90-Day Summary
            variant_name slippage_label  number_of_windows window_sampling_method  pct_windows_target_300_before_stop  pct_windows_target_400_before_stop  pct_windows_any_stop_hit  pct_windows_trailing_stop_hit  median_max_drawdown  worst_max_drawdown
            core_only_AB       standard               4541           all_possible                            0.072231                            0.016516                       0.0                            0.0          -132.333841         -406.020424
            core_only_AB         stress               4541           all_possible                            0.063642                            0.016736                       0.0                            0.0          -153.014459         -421.315636
         momentum_only_A       standard               4541           all_possible                            0.007267                            0.000881                       0.0                            0.0          -111.233898         -261.963125
         momentum_only_A         stress               4541           all_possible                            0.007267                            0.000000                       0.0                            0.0          -118.131446         -268.612410
  no_cash_proxy_alpha_AB       standard               4541           all_possible                            0.126184                            0.033693                       0.0                            0.0          -155.694076         -406.020424
  no_cash_proxy_alpha_AB         stress               4541           all_possible                            0.111209                            0.035235                       0.0                            0.0          -158.606761         -421.315636
original_full_tournament       standard               4541           all_possible                            0.064964                            0.007487                       0.0                            0.0          -141.967147         -529.734290
original_full_tournament         stress               4541           all_possible                            0.046686                            0.005285                       0.0                            0.0          -177.112118         -518.723982

## Decision Answers
- Best 90-day +$300 before stop rate: `no_cash_proxy_alpha_AB` at 11.12% using the robust minimum across standard/stress slippage.
- Best 90-day +$400 before stop rate: `no_cash_proxy_alpha_AB` at 3.37% using the robust minimum across standard/stress slippage.
- Best stress-slippage stability: `momentum_only_A`.
- Lowest drawdown risk: `momentum_only_A` by the least-bad robust median drawdown.
- Best current candidate: `no_cash_proxy_alpha_AB` with status `leading_watchlist_candidate`.
- Target probability assessment: `very_low_probability_for_400`.
- C/D/E status: `remain_rejected_or_shadow_only`.
- Fragile variants: [].

## Interpretation Rules Applied
- If 90-day +$300 before stop rate is below 10%, mark low-probability.
- If 90-day +$400 before stop rate is below 5%, mark very low-probability.
- If stress slippage materially worsens target rates or drawdown, mark fragile.
- If original_full_tournament is weaker than A/B variants, do not forward-test it.
- If no_cash_proxy_alpha_AB beats momentum_only_A and core_only_AB under both standard and stress, mark it as leading watchlist candidate, not validated.
- Nothing is marked validated unless evidence is strong across both standard and stress.
