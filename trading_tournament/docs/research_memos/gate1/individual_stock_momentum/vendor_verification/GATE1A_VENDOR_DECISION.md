# Gate 1A Vendor Decision

## Decision

`continue_defer`

## Rationale

Individual stock momentum remains plausible as a research family, but this vendor verification did not clear the blockers required for serious Gate 2 implementation.

CRSP and Norgate Data appear to be credible serious-research candidates from official pages. However, this review did not verify project access, current cost, license terms, local caching rights, evidence-sharing restrictions, raw schema details, or complete delisting-return/terminal treatment workflows.

yfinance/current-ticker data remains toy-only. Interactive Brokers and Alpaca remain execution/reference sources, not serious historical research databases for this question.

## Serious Gate 2 Prototype

Not approved.

## Toy Demo

Not approved in this packet.

Toy mechanics may be reconsidered later only if explicitly authorized, isolated from validation outputs, labeled non-evidence, and barred from strategy comparison claims.

## What Is Allowed Next

- Continue vendor follow-up.
- Verify CRSP access, cost, license, export format, and local caching terms.
- Verify Norgate Data package contents, delisting treatment, cost, license, and Python/local workflow.
- Verify Sharadar/Nasdaq Data Link dataset contents and license terms.
- Create a Gate 1B cost/access review if vendor terms look realistic.

## What Is Still Blocked

- Stock momentum strategy implementation.
- Stock data loader implementation.
- Historical stock data downloads.
- Backtests.
- Vendor API integration.
- Broker integration.
- AI trading gates.
- Real-money recommendations.

## Evidence Required To Change Decision

- Verified survivorship-free data source.
- Verified active and delisted stock coverage.
- Verified delisting returns or conservative terminal treatment.
- Verified corporate action handling.
- Verified point-in-time universe or acceptable point-in-time universe construction.
- Acceptable cost/access for this project.
- License allowing local research use and reproducible cached runs.
- Runtime/storage estimates from trial/sample exports.
- Fixed execution assumptions and benchmarks.

## No-Real-Money Statement

This decision is for paper/demo research only. It does not recommend real-money trading and does not approve implementation.
