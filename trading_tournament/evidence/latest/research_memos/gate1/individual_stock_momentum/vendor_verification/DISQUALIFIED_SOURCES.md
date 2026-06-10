# Disqualified And Toy-Only Sources

## yfinance / Current Tickers

yfinance/current-ticker data is toy-only for individual stock momentum. It should not be used as serious research evidence because it does not provide:

- Survivorship-free historical universe construction.
- Active and delisted stock coverage.
- Delisting returns or conservative terminal treatment.
- Point-in-time index membership.
- Reliable treatment of bankruptcies and disappeared tickers.

Any yfinance stock-momentum work would have to be isolated as a mechanics-only toy demo and excluded from validation tables. This packet does not approve that toy demo.

## Interactive Brokers

Interactive Brokers is disqualified as a primary research database for stock momentum unless separate evidence proves survivorship-free historical universe and delisting treatment. It may be useful as execution/reference documentation, but this project is not adding broker integration.

## Alpaca

Alpaca is disqualified as a primary serious research database unless separate evidence proves survivorship-free coverage and delisting treatment. It may be a broker/API reference source, but this task does not add broker integration and does not approve stock data ingestion.

## Sources Without Active And Delisted Coverage

Any source that cannot provide active and delisted stock coverage should be considered unsuitable for serious individual-stock momentum validation.

## Sources Without Delisting Returns Or Terminal Treatment

Any source that cannot provide delisting returns or a conservative terminal treatment for bankruptcies, mergers, and disappearances should not be approved for serious Gate 2.

## Sources With Unclear License Or Cache Rights

Any source that prohibits local cached research use, cannot be audited reproducibly, or cannot support summary evidence packets without exposing raw proprietary data should remain blocked.
