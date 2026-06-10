# Exhaustive Rolling Decision

This file is research-only paper/demo evidence. It is not a real-money trading recommendation.

Replay rolling diagnostics are secondary. The table below is based on independent rolling-window simulations.

## 90-Day Summary
No 90-day rows.

## Decision Answers
- Best 90-day +$300 before stop rate: `` at 0.00% using the robust minimum across standard/stress slippage.
- Best 90-day +$400 before stop rate: `` at 0.00% using the robust minimum across standard/stress slippage.
- Best stress-slippage stability: ``.
- Lowest drawdown risk: `` by the least-bad robust median drawdown.
- Best current candidate: `` with status `not_available`.
- Target probability assessment: `not_available`.
- C/D/E status: `shadow_only_or_rejected`.
- Fragile variants: [].

## Interpretation Rules Applied
- If 90-day +$300 before stop rate is below 10%, mark low-probability.
- If 90-day +$400 before stop rate is below 5%, mark very low-probability.
- If stress slippage materially worsens target rates or drawdown, mark fragile.
- If original_full_tournament is weaker than A/B variants, do not forward-test it.
- If current_no_cash_proxy_alpha_AB beats current_momentum_only_A and current_core_only_AB under both standard and stress, mark it as leading watchlist candidate, not validated.
- Nothing is marked validated unless evidence is strong across both standard and stress.
