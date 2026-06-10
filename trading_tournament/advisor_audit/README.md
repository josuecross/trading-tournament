# Advisor Audit Upload Pack

This folder defines the compact advisor upload packet system.

The packet builder collects existing research evidence into a small set of zip files under `evidence/advisor_upload/latest/`. It does not run backtests, download data, change strategy rules, connect to brokers, place orders, or make real-money recommendations.

The upload packet is designed for an external advisor or ChatGPT-style reviewer who needs a reliable, compact view of:

- challenge and independent family evidence,
- paper-forward observation evidence,
- risk framework and strategy governance,
- research direction and gate status,
- exploratory lane warnings,
- small reproducibility/debug files.

Raw OHLCV, cache folders, vendor raw data, broker credentials, nested zips, virtual environments, and pycache files are excluded.
