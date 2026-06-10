# Paper-Forward Observation Cache Update

This folder contains a controlled cache-freshness updater for the combo paper/demo observation activation gate.

Allowed symbols are only `SPY`, `GLD`, and `BIL`.

This updater does not change strategy rules, does not run a backtest, does not run Profit Exploration, does not connect to brokers, does not place orders, and does not make a real-money recommendation.

Raw OHLCV remains only in the local cache convention. Compact evidence excludes raw OHLCV.
