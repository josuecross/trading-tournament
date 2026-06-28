# Tested Strategy Review

This review exists to prevent the expansion registry from repeating already-tested ETF-wrapper ideas while still allowing structurally different research families.

| Area | Classification | Benchmark use | Duplication risk for new candidates | Exhausted/open status | Future hypothesis requirement |
|---|---|---|---|---|---|
| `paper_forward_vm_quality_lowvol_proxy_v1` active VM strategy | active / accepted | Yes, primary active reference | Volatility-managed candidates must prove they are not active VM clones | Open only for structurally different volatility management | Required before any variant |
| `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` active DSR strategy | active / accepted | Yes, primary active reference | Sector rotation candidates must compare holdings and cash behavior against active DSR | Open only for different sector timing or risk model | Required before any variant |
| `active_combo_vm_dsr_equal_weight_v1` active combo | diagnostic / benchmark_watchlist | Yes, benchmark only | Ensemble and blended sleeves are high duplication risk | Not an active strategy; useful as reference | Required for any combo-like idea |
| `SPY_200d_trend_model` | active / benchmark control | Yes | Trend filters must show value beyond this simple control | Open as benchmark, not as new alpha | Required for modifications |
| breadth-state regime lane | archived / rejected | No, except as archived evidence | Do not repeat the same market breadth/state ETF-wrapper mechanics | Exhausted under current mechanics after no promotion candidates | New hypothesis required |
| ETF-wrapper track overall | archived / stopped | Historical reference only | High risk of repeating saturated top-N, defensive, and ensemble mechanics | Stopped after repeated no-candidate results | Structurally different family required |
| active-sleeve ensemble | diagnostic / benchmark_watchlist | Yes for equal-weight active combo comparison | Ensemble tilts mostly duplicated active combo | Exhausted unless a new structural thesis appears | Required |
| QVM variants | rejected | Diagnostic only | Upside rows had thin risk buffer and drawdown issues | Exact tested variants closed | Required |
| LVQ variants | rejected | Diagnostic only | Safer rows lagged active references | Exact tested variants closed | Required |
| DSR variants | rejected / duplicate_or_near_duplicate | Diagnostic only | Near-duplicate risk against active DSR | Exact tested variants closed | Required |
| approved-cache batch 2 | rejected | Diagnostic only | Safe but weak rows should not be repeated cosmetically | Exact tested batch closed | Required |
| approved-cache batch 3 | rejected | Diagnostic only | Risk-controlled variants lagged references | Exact tested batch closed | Required |
| expanded-universe batch 1 | rejected | Diagnostic only | Regional upside failed risk gate; safer rows too slow | Exact tested batch closed | Required |

Conclusion: the expansion registry is allowed because it moves into pre-registered mean-reversion, breakout, volatility-management, compact relative-strength, calendar, overlay, intraday, and later event-data families. It does not approve any row and does not restart the archived ETF-wrapper track.
