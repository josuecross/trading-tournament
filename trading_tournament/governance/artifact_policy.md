# Artifact Policy

Tracked source of truth: registry YAML, roadmap Markdown, canonical specs, family status summaries, lane policies, indicator governance, tests, and compact state reports.

Generated local-only artifacts: evidence packets, zip files, `latest/` evidence exports, provider caches, logs, JSONL progress, pytest caches, Python bytecode, and temporary outputs.

Bulky generated evidence should be retained locally or regenerated, not treated as primary source code. Compact summaries should be promoted into `reports/compact_state/` or `family_registry/family_status/` when they become canonical.
