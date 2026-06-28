# Sector Rotation Family

- Tested variants: active DSR, top-N DSR variants, sector relative-strength variants
- Active variants: `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`
- Rejected variants: DSR top-N and sector RS rows that failed duplication, risk, or same-window gates
- Benchmark/control variants: SPY, BIL, active combo
- Last audit conclusion: active DSR remains protected; same-family rescue is closed unless a distinct hypothesis is pre-registered.

## Governance

- Exact rejected variants closed: true
- Allowed future work: family-level audit or pre-registered distinct hypothesis only
- Forbidden repeats: exact replay, post-result parameter tuning, direct candidate_exhaustive, paper/demo activation, provider download, broker/live path, real-money recommendation
