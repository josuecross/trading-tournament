# Trade Management Research Policy

Trade-management infrastructure is preserved for research and audit, but optional overlays are not a default extension of new strategy tests.

## Default New-Strategy Workflow

```text
1. Source-exact base
2. Identity control
3. Standard costs and benchmarks
4. Determine whether the strategy shows useful evidence
5. Diagnose one management weakness
6. Select one compatible purpose-specific primitive
7. Run one overlay with one attribution control
8. Close or advance the exact combination
```

## Standing Rules

- New strategies are not automatically tested against all overlays.
- Weak strategies are not subjected to repeated management searches to rescue them.
- Source-defined management remains part of the base.
- Optional overlays require a diagnosed weakness.
- One optional overlay is allowed per experiment.
- Complex source-defined systems remain separate holistic lanes.
- Performance cannot be used to select compatible overlays.
- Failed overlays remain visible.
- No optional overlay is currently approved as a universal default.

## Source-Defined Management

Stops, sizing methods, exits, rebalance rules, and portfolio controls that are part of the original source strategy must be implemented inside the source-exact base definition. They are recorded as `source_defined_base_management`, not as optional overlays.

An optional management overlay is downstream research. It must cite one stable diagnosed-weakness code, one selected primitive, a compatibility reason, and one negative or attribution control in a `ManagementExperimentPlan`.

Attribution controls such as `IdentityOverlay` and static scale controls are controls. They are not promoted overlays and do not authorize follow-up management searches.

## Purpose-Specific Gate

The enforced workflow is:

```text
source-exact base
-> Identity control
-> weakness diagnosis
-> one compatible purpose-specific overlay
-> attribution control
-> exact-combination decision
```

The default optional-management count is `0`. A valid plan may request `1` compatible optional primitive. More than one optional primitive is combination research and is outside this task.

Compatibility reporting is structural only: intent kind, required data, lifecycle state, and declared incompatibilities. Compatibility is not authorization, and compatibility reports must not include returns, drawdowns, Sharpe ratios, registry scores, promotion status, or historical overlay performance.

## Legacy And Holistic Status

`OVL-ORD-001` remains available only as a legacy composite reproducing the old combination of target-weight band suppression and minimum-notional filtering. Future work must select either `OVL-ORD-WEIGHT-BAND-V1` or `OVL-ORD-MIN-NOTIONAL-V1`, not the composite.

`OVL-RSK-001` remains available only as a legacy combined cap wrapper. Future work must select one of `OVL-RISK-GROSS-CAP-V1`, `OVL-RISK-ASSET-CAP-V1`, or `OVL-RISK-GROUP-CAP-V1` when the diagnosed weakness calls for it.

`OVL-PRISK-CPPI-M3-5Y-MONTHLY-V1` remains a holistic source-defined complete portfolio-insurance system. It is not decomposed into floor, cushion, cash-lock, multiplier, or synthetic-safe candidate overlays. The exact N4-CPPI combination remains `MIXED_ACROSS_EPISODES_CONCENTRATED_NO_ADVANCEMENT`.
