# Methodology Review

This review is skeptical by design. Fund marketing claims are treated as descriptions of exposure, not proof of edge.

## DBMF

DBMF claims managed-futures style exposure through an ETF wrapper. Public iMGP/DBi material describes the fund as seeking to replicate the pre-fee performance of a representative basket of leading managed-futures hedge funds. It uses active positions in liquid futures and aims for lower correlation to major asset classes.

Methodology answers:

1. Strategy exposure: managed-futures/CTA hedge-fund replication style exposure.
2. Managed-futures, CTA, trend-following, or futures-like exposure: yes, futures-like managed-futures proxy exposure.
3. Holds futures internally: yes, public methodology material references active futures positions.
4. Active/index/rules-based: active/proprietary replication style rather than a transparent index replication strategy.
5. Markets included: public material references futures exposures across fixed income, currencies, commodities, and equities.
6. Risk or volatility target: not accepted as fully transparent from this review; future implementation must not assume a stable volatility target unless prospectus/fact-sheet evidence is captured.
7. Internal leverage: likely futures notional exposure exists through the wrapper; the project will not model internal leverage directly.
8. Collateral/T-bill exposure: likely collateral/cash management exists inside the wrapper; future methodology review should capture current holdings/collateral notes if needed.
9. Key risks: proprietary replication opacity, manager/model risk, hidden futures notional behavior, tracking risk versus managed-futures universe, and limited public ETF history.
10. Transparency enough for project use: enough for research_sample wrapper-proxy testing only, not enough for direct managed-futures strategy claims.
11. Evidence scope: likely fund-specific and wrapper-specific, not strategy-family-wide evidence.

## KMLM

KMLM claims managed-futures exposure through the KFA MLM Index. The KraneShares page says the index holds twenty-two liquid futures contracts, including commodity, currency, and global bond market futures. The FAQ describes a rules-based daily trend signal, monthly rebalance, and futures roll process.

Methodology answers:

1. Strategy exposure: managed-futures trend-following index exposure.
2. Managed-futures, CTA, trend-following, or futures-like exposure: yes, rules-based long/short managed-futures proxy exposure.
3. Holds futures internally: yes, via the ETF wrapper.
4. Active/index/rules-based: index-based/rules-based, with Mount Lucas sub-advisor involvement.
5. Markets included: commodities, currencies, and global fixed income futures; equity futures are intentionally excluded by the stated methodology.
6. Risk or volatility target: FAQ material indicates expected volatility behavior from fixed exposures rather than an explicit volatility target; future implementation must preserve this nuance.
7. Internal leverage: futures exposure implies internal notional/leverage mechanics that are hidden at wrapper-price level.
8. Collateral/T-bill exposure: issuer FAQ notes cash/collateral management and T-bill related tracking considerations.
9. Key risks: short ETF history, index/fund tracking difference, futures roll/collateral behavior, fund expenses, and methodology changes.
10. Transparency enough for project use: better than DBMF for rule transparency, but still wrapper-price evidence only.
11. Evidence scope: fund/index-wrapper evidence, not direct futures strategy evidence.

## Cross-Fund Judgment

DBMF and KMLM are acceptable as two different managed-futures proxy wrappers for a future research_sample prompt. The evidence must be labeled limited-inception, wrapper-level, fund-specific, and not direct futures-contract strategy evidence.
