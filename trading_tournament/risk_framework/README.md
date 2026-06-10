# Project Risk Framework

This folder defines the canonical risk-governance layer for the paper/demo research project.

`risk_framework.yaml` is the source of truth for the $3,000 challenge assumptions, +$300/+400 targets, -10%/-15%/-20% risk bands, exposure policy, instrument risk budgets, and promotion blocks.

The framework is research-only. It does not validate any strategy, recommend real-money trading, connect to brokers, or place orders.

Use:

```bash
.venv/bin/python run_risk_framework_audit.py
```

The audit exports a compact packet to `evidence/risk_framework/latest/` with no more than 10 files.
