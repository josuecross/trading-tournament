# Point-In-Time Universe Review

Point-in-time universe membership matters because a historical strategy cannot know today's index members, today's survivors, or future listings at past dates. Using today's S&P 500 or Nasdaq 100 backward creates lookahead and survivorship bias.

## Universe Policies

| universe_policy | allowed_conclusion | forbidden_conclusion |
|---|---|---|
| all listed common stocks with liquidity filter | credible if listing/delisting data are point-in-time | paper-forward readiness without deeper validation |
| Norgate survivorship-free universe | possible Tier 2/Tier 3 after provider verification | real-money recommendation |
| CRSP universe | possible Tier 3 after access and processing review | shortcut around cost/execution modeling |
| Sharadar universe if delisting/universe fields exist | possible Tier 2/Tier 3 after field verification | assuming delisting returns are present without checking |
| current-ticker-only toy universe | code-path and runtime behavior only | serious strategy validation |

Conclusion: a point-in-time universe is mandatory before serious historical evidence. Current-ticker-only universes are toy-only.

