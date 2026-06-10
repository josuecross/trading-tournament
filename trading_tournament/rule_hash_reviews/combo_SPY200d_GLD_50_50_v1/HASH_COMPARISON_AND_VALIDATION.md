# Hash Comparison And Validation

| source | historical_hash_found | value | comparison_result |
| --- | --- | --- | --- |
| `evidence/profit_exploration/latest/profit_rankings.csv` | no | blank / NaN | no historical hash to compare |
| `evidence/profit_exploration/latest/experiment_status.csv` | no | blank / NaN | no historical hash to compare |
| `evidence/profit_exploration/latest/profit_exploration_results.csv` | no | blank / NaN | no historical hash to compare |
| `strategy_lab/strategy_registry.yaml` | no | field absent before this review | no historical hash to compare |
| `evidence/promotion_reviews/combo_SPY200d_GLD_50_50_v1/latest/promotion_review_manifest.json` | no | field absent | no historical hash to compare |
| `evidence/paper_forward_observation_plans/combo_SPY200d_GLD_50_50_v1/latest/observation_plan_manifest.json` | no | field absent | no historical hash to compare |
| `rule_hash_reviews/combo_SPY200d_GLD_50_50_v1/CANONICAL_RULE_SPEC.json` | yes, reconstructed | `6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67` | source-spec reconstruction verified |

## Validation Result

No conflicting historical hash was found.

The reconstructed source/spec hash is accepted as the current canonical governance hash:

`6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67`

## Remaining Activation Gate

The rule hash blocker is resolved, but the requested activation date `2026-06-05` is not supported by the current local cached SPY/GLD/BIL data, whose latest common date is `2026-05-29`.
