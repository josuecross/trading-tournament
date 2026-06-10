# Provider Security And Secret Handling

Security rules for any future provider path:

- no API keys in the repo,
- no secrets in evidence,
- no tokens in logs,
- use environment variables or ignored local secret files only,
- `.env` and secret files must be gitignored before any keyed workflow,
- advisor packets must not include API keys, raw vendor data, credentials, or account identifiers,
- no provider API call before a controlled acquisition prompt,
- provider metadata may be stored only if terms allow,
- raw OHLCV must stay in an approved local cache only,
- if paid provider terms forbid cache/evidence metadata, defer.

## Provider-Specific Security Notes

Norgate may reduce API-key risk if used through local desktop/plugin workflows, but installation path, database path, export rights, and personal-use licensing must be documented.

Sharadar/Nasdaq Data Link, Polygon/Massive, Tiingo, and EODHD likely require API-key workflows. Gate 1E must define environment-variable names, `.gitignore` coverage, log redaction, cache-root boundaries, and no raw data in advisor packets before any call.

CRSP likely depends on institutional access. Gate 1E must not copy credentials, institutional files, or restricted raw data into this repository unless the license clearly permits local research cache use.

## Current Task Confirmation

No API key was created. No provider account was used. No provider API was called. No credentials were written. No stock data was downloaded.

