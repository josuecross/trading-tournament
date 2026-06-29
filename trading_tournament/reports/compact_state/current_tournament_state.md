# Current Tournament State

Created UTC: `2026-06-29T01:22:56.014181+00:00`

Current research mode: `next_family_discovery_after_indicator_validation_completed`

Current next action: `pause_expansion_and_wait_for_manual_direction`

Selected family: `managed_futures_etf_wrapper`

Candidate evaluated: `mfv_equal_weight_trend_filter_v1`

Candidate outcome: `discovery_reject`

Promotion candidates count: `0`

Limited-history label: `limited_history_common_window_short`

Decision label: `weaker_than_active_references`

Discovery evidence: `C:\Users\te3442\Documents\GitHub\trading-tournament\trading_tournament\evidence\parallel_research_discovery\next_family_after_indicator_validation\latest`

## Active Accepted / Paper-Demo Observations

- `paper_forward_vm_quality_lowvol_proxy_v1` remains active/accepted/frozen.
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` remains active/accepted/frozen.

## Benchmark Controls

- `static_all_weather_benchmark_v1` remains benchmark/control only.
- Active combo, active VM, active DSR, SPY, QQQ, BIL, GLD, TLT, AGG, and static all-weather remain references/controls, not new promotions.

## Rejected / Paused State

- `mfv_equal_weight_trend_filter_v1` is a discovery reject.
- Promotion candidates count remains `0`.
- Exact rejected variants remain closed.
- Old managed-futures top1/top2 rows remain historical context only and are not replayed.
- Intraday research remains paused.

## Forbidden Actions

- No strategy discovery is authorized by this state sync.
- No backtest or new strategy performance metric computation is authorized by this state sync.
- No new candidates, variants, tuning, or rejected-row rescue.
- No candidate_exhaustive.
- No paper-forward review or activation.
- No provider download.
- No intraday data use.
- No indicator library dependency.
- No broker/live-order path activation or order action.
- No real-money recommendation.
