# Forward Observation Handoff Standard V1

Schema ID: `forward_observation_handoff_standard_v1`  
Schema version: `1`

## Ownership Boundary

The research producer owns the frozen strategy identity, lineage, tradable universe, signal dependencies, calculator contract, timing semantics, targets, claims, caveats, and conformance fixtures. It emits target weights and never emits quantities, orders, fills, broker instructions, account identifiers, credentials, notional approval, or live authorization.

The receiver owns package acceptance, explicit research-to-receiver identity binding, provider/calendar capability binding, current signal acquisition, persistent strategy state, virtual observation, deployment sleeves, capital limits, order sizing, execution risk, and any broker boundary.

## Dual-Path Transition

`existing_manual_runtime_registration` and `standardized_handoff_import` coexist. Existing VM/DSR registry entries, runtime specs, calculators, session state, and execution behavior do not depend on this standard and are not migrated by its introduction.

## Package and Import Lifecycle

A standard package contains `handoff.json` and `package_manifest.json`. Every payload file is hashed, and `package_content_hash` is the canonical hash of the file-hash map. To avoid a circular self-reference, the `handoff.json` file hash is calculated from canonical JSON with `envelope.package_content_hash` replaced by `__NORMALIZED_SELF_REFERENCE__`. The generic importer supports `validate_only` and `import_inactive`. Import requires an explicit identity binding and separate inactive deployment profile; neither mode activates a strategy.

Source adapters normalize supported immutable source schemas into the common model. Adapters may rename and expose fields but may not invent missing strategy rules. Missing material fields produce `contract_materialization_required` or an enrichment-gap result.

## Calculation and Execution

The standard calculation request carries validated signal/history inputs, event identity, calendar, state, and calculator configuration. The result carries target weights, cash weight, effective timestamp, deterministic target version, provenance, and status. Execution positions and orders remain separate receiver objects.

Target versions bind package identity, strategy instance, event, normalized weights, cash, and effective time, so they remain stable across process sessions.

## Timing and State

Timing declares information and availability cutoffs, calendar ID, session offset, and effective boundary. The receiver resolves an explicit effective timestamp against an offline authoritative session table. Strategy state persists outside weekly sessions and distinguishes pending from current targets. Event IDs remain handled across restarts.

No external release creates `no_event`, not a synthetic event or a newly forward-filled target. Existing current targets remain unchanged.

## Lifecycle and Microtrading

The lifecycle vocabulary covers research eligibility through paper/demo activity and recognizes microtrading states. Standard v1 rejects transitions into either microtrading state with `microtrading_promotion_not_authorized`. Live submission remains false.

## Fixtures

Supported fixture types include signal formula, target weight, threshold/tie, timing, missing event, restart, duplicate event, and stale event. Packages declare the fixture types their calculator and timing contract require. The receiver fixture runner compares status, targets, and effective timestamps without invoking execution.

Strategies whose targets depend on historical numeric inputs may attach the separately versioned `forward_observation_conformance_input_bundle_v1` companion. That bundle supplies the minimal frozen inputs needed to reproduce golden outputs without an operational-provider call or research-runtime dependency. It is a software conformance reference, not operational market data; provider history and price semantics remain an independent receiver acceptance gate.

## Versioning

Unknown schema IDs and unsupported major versions fail with `unsupported_schema`; they are never parsed permissively. Additive compatible fields require a later explicit schema revision policy.
