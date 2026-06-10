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
