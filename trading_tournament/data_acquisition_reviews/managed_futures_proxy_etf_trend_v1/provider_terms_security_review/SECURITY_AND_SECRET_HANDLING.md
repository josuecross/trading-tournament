# Security And Secret Handling

- API keys must never be committed.
- API keys must not appear in evidence.
- API keys must be supplied via environment variables or a local ignored secrets file.
- `.env` or secrets files must be gitignored.
- Logs must not print keys.
- Advisor packets must not include secrets.
- If no key is available, keyed provider acquisition is not allowed.
- Future acquisition must include manifest confirmation that no API key or token was written.

The approved first path does not require an API key because it uses the yfinance-compatible project path for `DBMF` and `KMLM` only.

