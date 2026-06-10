# Exploratory Research Lanes

Exploratory lanes are separate from the ETF validated lane.

They exist to screen new market hypotheses before any credible-prototype or candidate-validation work. Exploratory outputs are non-final, must not be mixed into ETF candidate validation, and must not be treated as paper-forward evidence.

Every exploratory lane must declare:

- `credibility_tier`
- `final_validation`
- `candidate_validation`
- `paper_forward_ready`
- `real_money_recommendation`

No exploratory result is a real-money recommendation. No exploratory lane may add broker integration, live orders, trade execution APIs, leverage, margin, shorting, or strategy tuning unless a later scope document explicitly authorizes it.

Current exploratory lanes:

- `crypto_spot_momentum/` - Tier 1 exploratory screen for long-only daily crypto spot momentum. Non-final and not paper-forward ready.
