# Security And Secret Handling

This review creates no API keys and writes no secrets.

Rules for any future keyed provider work:

- API keys must never be committed.
- API keys must not appear in evidence.
- API keys must be supplied via environment variables or a local ignored secrets file.
- `.env` or secrets files must be gitignored.
- Logs must not print keys.
- Advisor packets must not include secrets.
- If no key is available, keyed provider acquisition is not allowed.
- Provider responses containing raw market data must remain in approved cache paths only and must not enter advisor upload packets.

Any future data acquisition task must include a secret scan or manifest confirmation showing no API key or token was written.
