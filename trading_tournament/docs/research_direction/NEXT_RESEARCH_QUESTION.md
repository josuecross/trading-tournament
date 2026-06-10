# Next Research Question

Which market/instrument families are theoretically capable of producing +10% to +13.3% within 30-180 trading days before a -20% stop, and which are disqualified by data quality, execution realism, leverage, or modeling complexity?

This is a non-coding research question. It should be answered with memos and the instrument matrix before any new strategy implementation.

## Template Table

| instrument_or_strategy | can_hit_target_in_theory | stop_risk | data_available | execution_realistic | modeling_complexity | evidence_quality | implementation_status | reason |
|---|---|---|---|---|---|---|---|---|
| Broad ETFs | yes | moderate | yes | high | low/moderate | moderate/strong | active_phase_1 | Good first lab, but may be slow. |
| Individual stocks | yes | high | not yet sufficient | moderate | high | unknown here | defer | Needs survivorship-free data. |
| Options | yes | very high | no | difficult | very high | unknown here | reject_for_now | Needs option-chain and fill framework. |
| Futures | yes | high | no | moderate/difficult | high | unknown here | defer | Needs roll and margin model. |
| Crypto leverage | yes | extreme | no | difficult | very high | unknown here | reject_for_now | Liquidation/funding risks. |

The next research deliverable should classify each row before any new implementation starts.

First Gate 0 memo created: `individual_stock_momentum`, under `docs/research_memos/gate0/individual_stock_momentum/`. It allows only Gate 1 feasibility review and does not approve implementation.

Gate 1 feasibility review now exists at `docs/research_memos/gate1/individual_stock_momentum/`. Decision: defer; Gate 2 implementation remains blocked until credible survivorship-free data and delisting treatment are identified.

Exploratory lane update: `exploratory/crypto_spot_momentum/` now exists as a Tier 1 long-only spot crypto screen. It is non-final, does not validate crypto momentum, excludes leverage/perpetuals/futures/margin/shorting, and does not change the ETF validated lane.
