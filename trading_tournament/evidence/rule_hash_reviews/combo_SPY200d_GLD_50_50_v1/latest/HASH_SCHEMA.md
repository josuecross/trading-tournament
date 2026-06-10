# Hash Schema

Schema id: `rule_hash_schema_v1`

## Canonicalization

The hash is computed from `CANONICAL_RULE_SPEC.json`:

1. Parse the JSON object.
2. Serialize with sorted keys.
3. Use compact separators with no whitespace dependency.
4. Preserve stable JSON numeric representation.
5. Compute SHA256 over the canonical JSON bytes.

Equivalent Python expression:

```python
canonical_json = json.dumps(spec, sort_keys=True, separators=(",", ":"))
canonical_rule_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

## Fields Included

The hash includes strategy id, schema id, account type, components, component weights, component hash status, component rule summaries, combination method, execution timing, cash handling, cost/slippage references, max gross exposure, leverage/shorting/margin flags, broker/live/real-money flags, source files, and reconstruction label.

## Fields Excluded

The hash excludes review prose, generated packet paths, timestamps, zip names, current activation status, current cache date, paper-forward checkpoint values, and any market data.

## Source Type

Hash source type: `source_spec_reconstructed_hash`

This is not a recovered historical Profit Exploration hash. Historical evidence had blank or absent `canonical_rule_hash` fields for this combo. The hash is reconstructed from current source/spec evidence and versioned as `reconstruction_from_source_spec_v1`.

## Governance Use

This hash is sufficient for paper/demo observation governance because it pins the fixed rule identity before activation. It does not validate performance, authorize real-money trading, replace SPY_200d, or permit rule changes.
