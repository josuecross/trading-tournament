# Strategy Lab Registry

This directory is the project-control layer for strategy research. It is not a trading engine, not a backtester, and not a source of real-money recommendations.

Use `strategy_registry.yaml` to track:

- which strategies and memos exist,
- which evidence tier each item belongs to,
- which rules are frozen,
- what can be developed in parallel,
- what is blocked, rejected, or memo-only,
- what evidence is required before promotion.

Active paper-forward rows are frozen. Any improvement must become a new version with a new id and its own evidence path. Exploratory and memo rows must not be mixed into paper-forward evidence.

Run:

```bash
.venv/bin/python run_strategy_lab.py --validate-registry --export-evidence
```

The compact upload-ready registry packet is written to `evidence/strategy_lab/latest/`.

Research-only boundary: no broker integration, no live orders, no order placement, and no real-money recommendation.

## Strategy Evidence Library

The Strategy Evidence Library (SEL) is the generated provenance and lineage
view for this repository. It does not replace the strategy registry or make
strategy decisions.

Canonical inputs:

- Strategy identity and lifecycle: `strategy_lab/strategy_registry.yaml`
- Family lineage: `strategy_lab/research_os/family_lineage/family_ledger.yaml`
- Research queue: `strategy_lab/research_os/research/research_queue.yaml`
- External/public-source intake: `strategy_lab/research_os/public_strategy_sources/intake_candidates/`
- Active observation index: `strategy_lab/research_os/operations/active_observations.yaml`
- Active observation details: `paper_forward_observations/*/active_observation.yaml`
- Frozen evidence: `evidence/**/latest/`

Generated SEL outputs are written to `evidence/strategy_evidence_library/latest/`.
They include linked source, idea, preregistration, implementation, experiment,
and decision records plus duplicate, failure, missing-metadata, and cleanup
reports.

Run:

```bash
.venv/bin/python run_strategy_evidence_library.py
```

Evidence level is cumulative (`E0` through `E7`) and is separate from lifecycle
status (`backlog`, `blocked`, `rejected`, `retest_only_on_new_evidence`,
`eligible`, `active`, `retired`). Positive backtest results do not themselves
promote a strategy or change paper/demo state.
