# Cleanup Policy

Delete obvious local junk such as Python caches, pytest caches, temporary logs, and throwaway generated files.

Archive rather than delete when a file may contain lineage, historical decisions, or source-of-truth strategy context.

Do not delete active registries, accepted active strategy definitions, benchmark/control registration definitions, tests, broker safety guardrails, or evidence summaries that preserve lineage unless a compact replacement summary exists.

Tracked generated files should be removed from the Git index with `git rm --cached` only after human review in a dirty worktree.
