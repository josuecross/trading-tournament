# Next Actions

Gate 1A decision: `continue_defer`.

## Required Follow-Up Before Any Gate 2 Decision

1. Contact or inspect CRSP access options, pricing, export workflow, and local caching rights.
2. Contact or inspect Norgate Data package details, including active/delisted coverage, delisting-return or terminal treatment, Python workflow, and license terms.
3. Verify whether Sharadar/Nasdaq Data Link provides active and delisted stock coverage, delisting returns or terminal treatment, point-in-time universe support, and acceptable license terms.
4. Confirm whether any candidate vendor permits local cached research runs.
5. Confirm whether summary metrics can be shared in evidence packets without exposing raw licensed data.
6. Identify an earnings date source only if the first stock momentum prototype would avoid earnings.
7. Estimate storage and runtime from vendor sample exports.
8. Decide whether the cost/access burden is justified relative to the project's learning and research value.

## If Gate 1B Is Created

Gate 1B should be a focused cost/access and trial-data review. It should not write code, ingest data, or run backtests unless a later explicit approval changes scope.

## If A Toy Demo Is Reconsidered

A toy demo must be isolated, non-evidence, excluded from validation tables, and labeled as mechanics-only. This Gate 1A packet does not approve it.

## Research Boundary

No stock momentum implementation, no stock data loader, no backtest, no historical stock data download, no vendor API integration, no broker integration, and no real-money recommendation are allowed as a result of this packet.
