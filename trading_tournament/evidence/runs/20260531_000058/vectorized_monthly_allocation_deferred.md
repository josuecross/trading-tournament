# Vectorized Monthly Allocation Deferred

A vectorized monthly-allocation rolling path was considered for N1-N4 style strategies, but it was deferred in this pass to avoid introducing a second execution model with subtle fill, stop, cash, or target-timing differences from the audited event engine.

The current validation speedup comes from validation modes, deterministic sampling, candidate gating, rolling cache reuse, chunk checkpointing, and progress logging. Candidate-exhaustive validation still uses the same event-driven backtest simulation as the main evidence path.

No strategy parameters were changed, no optimization was introduced, and no real-money recommendation is made.
