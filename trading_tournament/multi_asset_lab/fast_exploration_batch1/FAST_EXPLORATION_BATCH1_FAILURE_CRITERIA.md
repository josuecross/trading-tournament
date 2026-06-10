# Fast Exploration Batch 1 Failure Criteria

A row should be rejected or left on watchlist if it breaches the -$600 drawdown budget, has materially worse stop-hit behavior than combo/top2, loses meaningful +$300/+400 target power, or mostly duplicates combo/top2/SPY_200d/GLD behavior without incremental target windows.

The defensive 50% BIL row fails as a candidate if it becomes too slow after drawdown improvement.

The combo+global multi-asset 80/20 row fails as a candidate if it is mostly combo behavior with a small noisy tilt, if its score improvement versus combo is immaterial, or if it lags top2/SPY_200d/GLD without clear incremental target evidence.

Any row with incomplete cache QA, unapproved symbols, leverage, margin, shorting, futures contracts, options, forex, intraday logic, broker behavior, paper-forward activation, or real-money recommendation fails this batch.
