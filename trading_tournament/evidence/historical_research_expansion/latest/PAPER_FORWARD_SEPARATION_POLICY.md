# Paper-Forward Separation Policy

## Lanes

Paper-forward observation lane:

- observes active simulated paper/demo rows,
- currently includes combo beside `SPY_200d_trend_model`,
- forbids judgment before 30 trading days,
- forbids rule changes,
- forbids promotion/demotion until checkpoint evidence exists.

Historical research lane:

- may continue historical tests when explicitly approved,
- may review new candidate families,
- may create implementation prompts after gates pass,
- may run research_sample or candidate_exhaustive only under the right gate,
- must not mutate active paper-forward rules.

Candidate discovery lane:

- holds ideas, queues, and reviews,
- does not imply implementation or backtesting.

Data acquisition lane:

- may review or acquire data only under explicit controlled scope,
- must not trigger backtests or strategy implementation.

Implementation-review lane:

- decides whether a future fixed-rule research_sample implementation prompt is allowed,
- does not itself implement the strategy.

Candidate_exhaustive lane:

- allowed only after explicit review,
- must remain separate from paper-forward observation.

## Separation Table

| Action | Allowed now? | Lane | Notes |
| --- | --- | --- | --- |
| run historical research_sample for new approved candidate | conditional | historical research | Allowed only after implementation gate approves a fixed rule. |
| create data acquisition review | yes | data acquisition | Review only; no download unless a later controlled prompt allows it. |
| create combination-design review | yes | implementation-review | Current preferred historical path. |
| run paper-forward checkpoint before 30 days | no | paper-forward observation | Observation is too early for judgment. |
| tune active combo | no | paper-forward observation | Active combo rules remain frozen. |
| replace SPY_200d | no | paper-forward governance | Requires separate governance decision. |
| run candidate_exhaustive for finalist | conditional | candidate_exhaustive | Allowed only after explicit candidate_exhaustive review. |
| add new strategy variant without review | no | candidate discovery | Prevent strategy shopping. |
| update dashboard | yes | governance evidence | Reads existing latest evidence only. |
| improve diagnostics | yes | historical research support | Plan/design work is allowed; scoring code changes require separate scoped task. |

## Key Rule

The paper-forward checkpoint clock does not freeze historical research. It only prevents judgment about the active forward observation before enough forward days exist.

