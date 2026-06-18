# Recovery From Lost Updates

Surviving context: the local repo retained the volatility-managed equity ETF lane review and the Strategy Lab governance skeleton. Work after that review was missing or incomplete in local files.

Reconstructed in this pass:

- active/frozen paper/demo observations for `paper_forward_vm_quality_lowvol_proxy_v1` and `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`
- conversation-recovered activation packets for both active rows
- recovered family/status summaries for volatility-managed ETF, defensive sector rotation ETF, quality/momentum ETF proxy, global risk-on/risk-off ETF, and the profit-family discovery audit
- registry rows for active/frozen, queued/deferred, watchlist, and family-state records
- minimum fixed-rule helpers and focused tests
- runner stubs for recovered review/sample/promotion/activation packet creation

Conversation-recovered evidence:

- all performance, stress, drawdown, target, benchmark delta, overlap, duplicate, and correlation metrics listed in recovered packets

Recomputed evidence:

- none in this recovery pass

Missing evidence:

- original exact ZIP packet bytes
- original full run logs
- exact local-cache recomputation outputs for the recovered metrics
- GROR candidate_exhaustive results, because that run had not occurred before the loss and was not run during recovery

Recovered/frozen active observations:

- `paper_forward_vm_quality_lowvol_proxy_v1`
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`

Manual review checklist:

- verify recovered metrics against any external conversation transcript if available
- decide whether to run `create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1` later
- keep recovered active observations frozen
- do not treat conversation-recovered evidence as recomputed evidence
- do not treat paper/demo observations as real-money readiness
