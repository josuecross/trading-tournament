# Correlation And Diversification Review Plan

No correlations are run in this review. Future research_sample implementation must report the following diagnostics before any stronger gate can be considered.

Required correlation and co-movement diagnostics:

- Daily return correlation versus `combo_SPY200d_GLD_50_50_v1`.
- Daily return correlation versus `asset_class_tsmom_top2_v1`.
- Daily return correlation versus `SPY_200d_trend_model`.
- Daily return correlation versus `GLD_buy_hold`.
- Daily return correlation versus `BIL_cash_proxy`.
- Rolling correlation in stress periods.
- Drawdown co-incidence with combo/top2/SPY_200d.
- Target-window co-movement with current finalists.
- Stop-hit co-incidence.

Required allocation diagnostics:

- DBMF allocation frequency.
- KMLM allocation frequency.
- BIL fallback frequency.
- DBMF allocation share.
- KMLM allocation share.
- Cash/Treasury fallback allocation share.
- Max single proxy allocation.
- Concentration warning if one proxy dominates.
- Too-slow warning if diversification comes with weak +300/+400 target rates.

Required interpretation:

- State whether DBMF/KMLM behave as genuine diversifiers or simply slow-return wrappers.
- State whether any result depends on one fund only.
- State whether target improvements come with worse stop/drawdown behavior.
- State that this is fund-wrapper proxy evidence, not direct futures strategy evidence.
