# Sharadar Terms Security Review

No account was created, no API key was created, and no provider API was called.

## Security Rules

- API key required: likely yes for practical Nasdaq Data Link / Sharadar access.
- No API keys in repo.
- No secrets in evidence.
- Use environment variables or ignored local secret files only.
- `.env` and secret files must be gitignored before any keyed workflow.
- No raw vendor data in advisor packets.
- Local cache only if terms permit.
- No redistribution of raw paid/vendor data.
- Package/subscription required before any serious sample.
- No API call before controlled acquisition prompt.
- No raw row previews in evidence unless terms explicitly allow.
- Advisor evidence must be metadata-only.

## Cache And Terms Unknowns

The project must verify whether selected package terms permit local research caching, cache hashing, metadata summaries, coverage summaries, and advisor-packet references that exclude raw rows.

## Current Task Confirmation

No Sharadar/Nasdaq API call occurred. No key or secret was written. No stock data was downloaded. No stock loader was created.

