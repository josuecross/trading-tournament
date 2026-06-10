# AI Policy

AI is deferred. It may be used later as report-audit only. It should not influence trades.

## Allowed Later

- Summarize evidence packets.
- Check consistency across evidence files.
- Generate audit questions.
- Help write research memos.
- Compare strategy assumptions.
- Identify missing documentation.

These uses are allowed only if they do not alter trades, risk, position sizing, or strategy rules.

## Forbidden Now

- Trade gating.
- Trade permission.
- Position sizing.
- Parameter tuning.
- Market condition scoring that affects trades.
- Override stops.
- Changing strategy rules.
- Live execution.
- Broker integration.

## Rationale

AI explanations can be persuasive without being valid. If AI affects entries, exits, sizing, stops, or risk gates, the system becomes discretionary and harder to validate. The current project needs audit clarity before any AI-assisted report review is considered.

Conclusion: no AI trading layer, no AI gate, no AI parameter tuning, and no AI live execution.
