# Dual Momentum PAA ETF Wrapper Duplicate Risk Plan

Future research_sample must compare against active combo, `paper_forward_vm_quality_lowvol_proxy_v1`, `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`, `SPY_200d`, `gror_balanced_momentum_60_40_v1`, SPY buy-hold, QQQ buy-hold, GLD buy-hold, BIL, IEF/TLT/AGG if available, and an equal-weight global tactical basket if available.

Duplicate risks:

- Simply replicates SPY_200d.
- Becomes GROR under a different name.
- Becomes active-combo-like SPY/GLD blend.
- Becomes BIL-heavy and too slow.
- Becomes QQQ/SPY growth beta.
- Creates many tactical rules without real additive behavior.

Additive proof should include different target windows, different drawdown windows, useful +300/+400 rates, acceptable drawdown, lower overlap with SPY_200d/GROR/active combo, and a clear reason why it is not just another global risk-on/risk-off blend.
