# Observation Plan Decision

Decision: `approve_future_paper_forward_observation_activation_prompt`

## Meaning

This approves creation of a later paper/demo activation prompt for a separate combo observation track.

It does not activate the combo now. It does not replace `SPY_200d_trend_model`. It does not change strategy rules, risk rules, data rules, paper-forward policy, broker integration, order placement, or real-money status.

## Rationale

The combo remains the practical leader after candidate triage and has already passed promotion review for paper-forward plan review. It improved 90d +300/+400 rates versus SPY_200d and materially improved drawdown/stop behavior, while preserving a simple fixed rule. The correct next step is a separate activation prompt with a rule-hash check and monthly checkpoint policy.

## Conditions For Activation Prompt

A future activation prompt must choose a start date, confirm canonical rule hash, preserve SPY_200d as frozen control, create compact evidence outputs, and keep all broker/live/real-money flags false.

No real-money recommendation is made.

