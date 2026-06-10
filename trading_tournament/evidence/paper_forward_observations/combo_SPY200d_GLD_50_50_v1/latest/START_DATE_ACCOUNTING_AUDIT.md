# Combo Start-Date Accounting Audit

Subject: combo_SPY200d_GLD_50_50_v1

Observation id: combo_SPY200d_GLD_50_50_v1_observation_v1

Audit date: 2026-06-05

Decision: start_date_accounting_bug_fixed

This is a paper/demo accounting audit only. It does not change strategy rules, run a backtest, run Profit Exploration, download data, replace SPY_200d, connect to brokers, place orders, or make a real-money recommendation.

## Audit Questions

1. What does paper-forward --start-date mean in the current runner?

The runner parses `--start-date` with `normalize_date()` and slices cached adjusted-price rows in `select_observation_prices()` where `prices.index >= start_date`. The start date is therefore the first included paper/demo observation date.

2. Does the observation begin at the start of the trading day or at the close/end of the trading day?

The current compact runner is close-based. The first included row initializes the observation account on that date. It must not import returns that occurred before the observation window. First-row equity can include initialization/rebalance costs, but not a prior close-to-start-date close market return.

3. Is the first active equity allowed to differ from $3,000 on the activation date?

Yes. The paper/demo accounting applies the existing initialization/rebalance cost convention when target weights are entered. A first-row active equity below $3,000 can be valid when it reflects only that cost convention. It is not valid if it includes returns from before the observation began.

4. Is the combo equity $2,904.97 produced from a valid first-day return calculation?

No. The $2,904.97 value was produced by the combo helper using full-history SPY_200d and GLD sleeve return streams, then reindexing those returns to the one-row observation window. That imported the prior close-to-2026-06-05 close sleeve return into the first active row. This differed from the SPY_200d control convention and overstated the first-day accounting movement.

5. Is the SPY_200d control using the same timing convention?

Before this fix, no. SPY_200d sliced the price window first and then called `simulate_weighted_curve()`, which makes the first row price return zero and applies only entry/rebalance costs. The combo path used full-history sleeve returns and therefore included a pre-start return on the first row. After the fix, the combo first row also excludes pre-start returns.

6. Are target distances calculated from active equity, not placeholder equity?

Yes when the combo is active. The status and risk tables calculate +$300/+400 distances from the active equity row. After this fix, those distances are based on corrected active equity rather than the invalid $2,904.97 value.

7. Are stop distances calculated from active equity, not placeholder equity?

Yes when the combo is active. The absolute stop distance uses active equity minus the $2,400 floor, and the trailing stop distance uses the observation high-water mark. Blocked or waiting rows remain governance placeholders and must be labeled as such.

8. Is max drawdown calculated correctly from the observation start/high-water mark?

Yes after the start-date boundary fix. The first active observation row becomes the initial high-water mark for the active window, so no pre-start drawdown is inherited. With only one active row, max drawdown is zero unless the initialized equity itself is later exceeded and then drawn down.

9. Are same-day signals or future returns accidentally used?

The identified bug was not a future-return issue. It was a pre-start return leak caused by reindexing full-history sleeve returns onto the first observation row. SPY_200d weights remain shifted by the existing signal timing convention, and the combo rule itself is unchanged.

10. Should first-day metrics be labeled active, partial-day, or initialization?

First-day metrics should be treated as active initialization-day metrics. They are active paper/demo metrics when the rule hash and data-date gates pass, but the summary now states that the first row excludes pre-start returns and may reflect initialization/rebalance costs only.

11. Does the paper-forward summary clearly document the timing convention?

It now does. `paper_forward_summary.md` includes a combo start-date accounting note, and `warnings_and_limitations.md` states that pre-start returns are excluded and first-row active equity may reflect initialization/rebalance costs only.

12. If there is a bug, what needs to be patched?

The combo sleeve return stream needed an observation-boundary patch. `combo_curve_from_sleeves()` now zeroes the first sleeve-return row after reindexing to `observation_prices.index`, preventing pre-start returns from entering the active observation window.

## Runner Logic Inspected

- `run_paper_forward_observation.py`: `normalize_date()` parses the requested start date.
- `run_paper_forward_observation.py`: `select_observation_prices()` slices cached prices with `prices.index >= start_date`.
- `run_paper_forward_observation.py`: `build_benchmark_outputs()` calculates SPY_200d on the observation slice, giving the first row zero price return plus entry/rebalance cost.
- `run_paper_forward_observation.py`: `combo_curve_from_sleeves()` previously reindexed full-history sleeve returns to the observation slice, allowing a pre-start return on the first combo row.
- `paper_forward_observations/combo_SPY200d_GLD_50_50_v1/observation_config.yaml`: activation date is 2026-06-05, rule hash is verified, broker/live/order/real-money flags are false.
- `evidence/paper_forward_runs/latest/paper_forward_status.csv`: pre-audit combo equity was $2,904.97, while SPY_200d was $2,998.50 under the same one-row observation period.

## Fixed Convention

- `--start-date` is the first included paper/demo observation date.
- The first active row initializes the paper/demo account.
- No pre-start price return is applied on the first active row.
- First-row active equity may differ from $3,000 because initialization/rebalance costs are applied.
- Combo and SPY_200d now use the same first-row accounting convention.
- SPY_200d remains the frozen control and is not replaced.

## Governance Confirmation

- Strategy rules changed: false
- Backtest run: false
- Profit Exploration run: false
- Data downloaded: false
- Broker integration: false
- Live orders: false
- Order placement: false
- Real-money recommendation: false
