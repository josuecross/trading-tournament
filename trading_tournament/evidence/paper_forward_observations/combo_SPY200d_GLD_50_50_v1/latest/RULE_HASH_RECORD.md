# Rule Hash Record

strategy_id: `combo_SPY200d_GLD_50_50_v1`

canonical_rule_hash: `6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67`

hash_source_type: `source_spec_reconstructed_hash`

hash_verified: `true`

## Sources Checked

| hash_source_file | hash_source_field | result |
| --- | --- | --- |
| `evidence/profit_exploration/latest/profit_rankings.csv` | `canonical_rule_hash` | field present, combo value missing |
| `evidence/profit_exploration/latest/experiment_status.csv` | `canonical_rule_hash` | field present, combo value missing |
| `evidence/profit_exploration/latest/profit_exploration_results.csv` | `canonical_rule_hash` | field present, combo value missing |
| `strategy_lab/strategy_registry.yaml` | `canonical_rule_hash` | field absent |
| `evidence/promotion_reviews/combo_SPY200d_GLD_50_50_v1/latest/promotion_review_manifest.json` | `canonical_rule_hash` | field absent |
| `evidence/paper_forward_observation_plans/combo_SPY200d_GLD_50_50_v1/latest/observation_plan_manifest.json` | `canonical_rule_hash` | field absent |
| `rule_hash_reviews/combo_SPY200d_GLD_50_50_v1/CANONICAL_RULE_SPEC.json` | full canonical source/spec object | reconstructed hash verified |

## Current Action

The rule-hash blocker is resolved. The prior cache-date blocker is superseded by the controlled SPY/GLD/BIL cache update, which recorded latest common cached date `2026-06-05` and activation-date support `true`.

Current authoritative state: combo is active as a separate simulated paper/demo observation, SPY_200d remains the frozen control, and SPY_200d is not replaced.

## Cache Freshness Update

Controlled SPY/GLD/BIL cache update run `20260606_040551` recorded latest common cached date `2026-06-05` and activation-date support `true`. The canonical rule hash remains `6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67`.
