# Ticker Identity Review

No provider lookup or issuer page fetch was performed in this task.

| symbol | intended_proxy_role | ticker_identity_risk | issuer_or_fund_identity_must_be_verified | acquisition_priority | notes |
|---|---|---|---:|---|---|
| DBMF | managed-futures ETF proxy | medium | true | high | High-priority symbol for first controlled prompt, but future metadata should still confirm the fund identity before cache acceptance. |
| KMLM | managed-futures ETF proxy | medium | true | high | High-priority symbol for first controlled prompt, but future metadata should still confirm the fund identity before cache acceptance. |
| CTA | CTA/managed-futures ETF proxy | high | true | defer | Ticker identity review required before download. Do not include CTA in first prompt unless a separate review resolves identity. |
| FMF | managed-futures ETF/fund proxy | medium | true | optional | Optional/lower priority until methodology and fund status are clear. |
| WTMF | managed-futures ETF/fund proxy | medium | true | optional | Optional/lower priority until methodology and fund status are clear. |

CTA remains excluded from the first approved download scope because ticker identity has not been resolved locally.

