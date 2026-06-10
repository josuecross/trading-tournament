# Checkpoint Policy

## Timing

- first checkpoint: after 30 trading days
- recurring checkpoint: monthly after the first checkpoint

## Checkpoint Statuses

- `active_observation`
- `target_300_hit`
- `target_400_hit`
- `risk_warning`
- `review_required`
- `stop_hit`
- `observation_failed`
- `inconclusive_too_early`

## Minimum Evidence Before Judgment

No conclusion should be drawn from fewer than 30 trading days. The minimum initial review threshold is 30 trading days, and 60/90/180 observation days are preferred for stronger claims.

## Output Discipline

Every checkpoint must preserve the combo-versus-SPY_200d comparison and must state that the account is simulated paper/demo only.

