# Rule Source Audit

| source_file | source_section_or_line_context | field_or_rule | extracted_value | confidence | notes |
| --- | --- | --- | --- | --- | --- |
| `profit_lab/profit_experiment_specs.yaml` | lines 573-589 | combo experiment declaration | `combo_SPY200d_GLD_50_50_v1`, fixed combination, independent account, starting equity 3000 | high | Declares the combo and its governance metadata. |
| `profit_lab/profit_experiment_specs.yaml` | lines 583-584 | components and rule source | `[SPY_200d_trend_model, GLD_buy_hold]`; `predeclared 50/50 monthly combination` | high | Confirms the intended fixed 50/50 concept. |
| `profit_lab/profit_experiment_specs.yaml` | lines 1-14 | global Profit Lab constraints | research-only, no real-money recommendation, no broker/live, no leverage, no shorting, no margin | high | Applies to Profit Lab experiments. |
| `profit_lab/profit_experiment_specs.yaml` | lines 17-33 | SPY component spec | `SPY_200d_trend_model`, underlying `[SPY, BIL]`, frozen paper-forward candidate | high | Component is separately defined. |
| `profit_lab/profit_experiment_specs.yaml` | lines 53-65 | GLD component spec | `GLD_buy_hold`, benchmark adjusted close buy-and-hold | high | Component is separately defined. |
| `run_profit_exploration.py` | lines 545-561 | component weight functions | `buy_hold_weights`; `trend_200d_weights` shifts SPY/BIL weights one day | high | Confirms GLD buy-hold and SPY 200d/BIL component mechanics. |
| `run_profit_exploration.py` | lines 984-1003 | full-period combo function | `combo_curve` sets fixed sleeve weights on monthly changes and applies component daily returns with cost | high | Confirms fixed monthly combo method. |
| `run_profit_exploration.py` | lines 1065-1110 | rolling combo function | `combo_target_weights`; `simulate_combo_window`; rolling windows start at 3000 and use window-local sleeve returns | high | Confirms fresh-window behavior. |
| `run_profit_exploration.py` | lines 1254-1265 | combo model construction | `{"SPY_200d_trend_model": 0.5, "GLD_buy_hold": 0.5}` for this experiment id | high | This is the exact implemented 50/50 rule branch. |
| `evidence/profit_exploration/latest/assumptions_and_costs.yaml` | lines 15-28 | account/risk/cost settings | starting equity 3000; targets/stops; standard cost 0.0005; stress cost 0.001 | high | Evidence packet confirms run assumptions. |
| `evidence/profit_exploration/latest/assumptions_and_costs.yaml` | lines 34-41 | rolling accounting | fresh starting equity/high-water/target/stop reset; fixed combinations use component daily returns | high | Confirms window accounting convention. |
| `strategy_lab/strategy_registry.yaml` | lines 13-44 | SPY_200d governance | active frozen control; paper-forward active; rules frozen | high | Confirms SPY_200d remains the control. |
| `strategy_lab/strategy_registry.yaml` | lines 2014-2059 | combo governance before this task | activation blocked because rule hash missing; paper_forward_active false | high | Confirms prior blocker state. |

## Audit Questions

1. Where is `combo_SPY200d_GLD_50_50_v1` defined?  
   In `profit_lab/profit_experiment_specs.yaml` and `run_profit_exploration.py`.

2. Is it truly fixed 50/50?  
   Yes. `run_profit_exploration.py` assigns `SPY_200d_trend_model: 0.5` and `GLD_buy_hold: 0.5` for this exact experiment id.

3. What are the components?  
   `SPY_200d_trend_model` and `GLD_buy_hold`.

4. Is `SPY_200d_trend_model` frozen and separately defined?  
   Yes. It is a separately defined SPY/BIL 200-day trend model and remains the frozen paper-forward control.

5. Is `GLD_buy_hold` separately defined?  
   Yes. It is a benchmark adjusted-close GLD buy-and-hold row.

6. What rebalance/timing convention is used for the combo?  
   The combo uses fixed monthly sleeve targets over window-local component daily returns. The SPY trend component shifts its signal one trading day before application.

7. What execution timing applies?  
   Source timing is component-level plus monthly combo target changes. The hash records this as source behavior rather than changing it.

8. What cost/slippage assumptions apply?  
   Profit Exploration uses standard cost `0.0005` and stress cost `0.001`; combo windows apply component and combo turnover costs.

9. What max gross exposure applies?  
   `1.0`.

10. Does the rule require leverage, margin, shorting, or broker execution?  
   No.

11. Is there any ambiguity that should block hash creation?  
   No. Historical hashes are missing, but source/spec evidence is sufficient for a source-spec reconstructed governance hash.
