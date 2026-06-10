# Issuer And Fund Identity Review

This file confirms only wrapper identity and methodology suitability for research gating. It does not include raw OHLCV and does not authorize implementation.

## Identity Table

| ticker | fund name | issuer / sponsor | fund type | inception date | expense ratio | active or index-based | wrapper identity confirmed | intended proxy role | ticker identity risk | identity review result |
|---|---|---|---|---|---|---|---|---|---|---|
| DBMF | iMGP DBi Managed Futures Strategy ETF | iM Global Partner US / Dynamic Beta investments | ETF/fund wrapper, alternatives managed-futures style | 2019-05-08 in acquired data; public secondary metadata reports May 08, 2019 | 0.85% from public secondary metadata and DBi material | Active/proprietary managed-futures replication style | true | managed-futures/CTA wrapper proxy | low | acceptable for research_sample proxy review, subject to short-history label |
| KMLM | KraneShares Mount Lucas Managed Futures Index Strategy ETF | KraneShares / KFA Funds; sub-advised by Mount Lucas Management | ETF/fund wrapper, managed-futures index strategy | 2020-12-01 on issuer page; acquired data starts 2020-12-02 | 0.90% on issuer page | Index-based/rules-based KFA MLM Index exposure | true | managed-futures/CTA wrapper proxy | low | acceptable for research_sample proxy review, subject to short-history label |

## DBMF Notes

DBMF identity is confirmed as an ETF wrapper for managed-futures style exposure. The primary public fund page was unavailable during review due scheduled maintenance, so the review used iMGP/DBi public presentation material for methodology and ETFDB as secondary identity metadata. This is sufficient for a research-sample gate, but a future implementation packet should recheck the current prospectus or fund page before any broader validation.

Public methodology notes describe DBMF as seeking to replicate pre-fee performance of a representative basket of leading managed-futures hedge funds, using active positions in highly liquid futures and a lower-correlation objective. That makes it a fund-wrapper proxy, not direct futures strategy evidence.

Sources/local notes:

- iMGP/DBi presentation: https://www.imgp.com/wp-content/uploads/Presentation-iMGP-DBi-Managed-Futures-Strategy-ETF.pdf
- ETFDB DBMF identity metadata: https://etfdb.com/etf/DBMF/
- Local acquired data evidence: `evidence/data_acquisition_runs/managed_futures_proxy_etf_trend_v1/latest/`

## KMLM Notes

KMLM identity is confirmed from the KraneShares fund page. The issuer page identifies KMLM as the KraneShares Mount Lucas Managed Futures Index Strategy ETF, with exposure to twenty-two liquid futures contracts traded on U.S. and foreign exchanges and an expense ratio of 0.90%. The same page lists the underlying KFA MLM Index and an inception date of 12/1/2020.

Issuer FAQ material describes the index as rules-based, with long/short trend signals, monthly rebalances, futures rolls, and exposure to commodities, currencies, and global bond markets. KMLM excludes equity futures by methodology, which may make it a cleaner diversifier proxy than equity-heavy alternatives, but the ETF wrapper has only a short public fund history.

Sources/local notes:

- KraneShares KMLM fund page: https://kraneshares.com/etf/kmlm/
- KraneShares KMLM FAQ: https://kraneshares.com/kmlm-managed-futures-faq/
- Local acquired data evidence: `evidence/data_acquisition_runs/managed_futures_proxy_etf_trend_v1/latest/`

## Blocker Review

No ticker identity blocker remains for DBMF or KMLM at the research_sample prompt stage. Remaining blockers are not identity blockers; they are short-history, fund-specific methodology, and wrapper-modeling limitations.
