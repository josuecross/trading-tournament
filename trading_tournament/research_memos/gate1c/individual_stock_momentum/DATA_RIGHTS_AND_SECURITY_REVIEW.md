# Data Rights And Security Review

## Rules

- No API keys in the repo.
- No secrets in evidence.
- No raw vendor data in advisor packets.
- No redistribution of paid/vendor raw data.
- Local cache metadata is allowed only if provider terms permit.
- Provider terms must be reviewed before acquisition.
- Raw OHLCV should stay in approved cache only.
- Evidence packets should contain metadata, coverage summaries, quality summaries, hashes, and decision notes only.

## Security Boundary

Future acquisition must use environment variables or ignored local secret files if keys are required. Logs must not print keys. Advisor packets must not contain tokens, raw paid data, or redistributable vendor content.

No provider call, API key creation, or secret storage occurred in this task.

