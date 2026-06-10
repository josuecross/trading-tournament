# Exhaustive Rolling Decision

This file is research-only paper/demo evidence. It is not a real-money trading recommendation.

Replay rolling diagnostics are secondary. The table below is based on independent rolling-window simulations.

## 90-Day Summary
                     variant_name slippage_label  number_of_windows          window_sampling_method  pct_windows_target_300_before_stop  pct_windows_target_400_before_stop  pct_windows_any_stop_hit  pct_windows_trailing_stop_hit  median_max_drawdown  worst_max_drawdown
             current_core_only_AB       standard                500 deterministic_stratified_sample                               0.104                               0.042                       0.0                            0.0          -128.511585         -341.372627
             current_core_only_AB         stress                500 deterministic_stratified_sample                               0.086                               0.042                       0.0                            0.0          -147.346770         -342.543542
          current_momentum_only_A       standard                500 deterministic_stratified_sample                               0.004                               0.000                       0.0                            0.0           -98.501433         -258.517647
          current_momentum_only_A         stress                500 deterministic_stratified_sample                               0.004                               0.000                       0.0                            0.0          -103.915527         -265.176373
   current_no_cash_proxy_alpha_AB       standard                500 deterministic_stratified_sample                               0.186                               0.048                       0.0                            0.0          -151.092874         -341.372627
   current_no_cash_proxy_alpha_AB         stress                500 deterministic_stratified_sample                               0.156                               0.052                       0.0                            0.0          -154.243813         -340.726053
              evidence_core_combo       standard                500 deterministic_stratified_sample                               0.202                               0.154                       0.0                            0.0          -154.143864         -374.066549
              evidence_core_combo         stress                500 deterministic_stratified_sample                               0.178                               0.152                       0.0                            0.0          -158.728193         -408.505168
       evidence_dual_momentum_taa       standard                500 deterministic_stratified_sample                               0.154                               0.098                       0.0                            0.0          -128.385371         -235.346167
evidence_dual_momentum_vol_scaled       standard                500 deterministic_stratified_sample                               0.182                               0.098                       0.0                            0.0          -124.418260         -235.346167

## Decision Answers
- Best 90-day +$300 before stop rate: `evidence_dual_momentum_vol_scaled` at 18.20% using the robust minimum across standard/stress slippage.
- Best 90-day +$400 before stop rate: `evidence_core_combo` at 15.20% using the robust minimum across standard/stress slippage.
- Best stress-slippage stability: `current_momentum_only_A`.
- Lowest drawdown risk: `current_momentum_only_A` by the least-bad robust median drawdown.
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
