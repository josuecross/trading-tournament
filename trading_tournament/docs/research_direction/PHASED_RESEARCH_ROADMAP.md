# Phased Research Roadmap

The project is currently between Phase 1 and Phase 2. Non-ETF implementation should not start until the opportunity map and gate policy are complete.

## Phase 0 - Project Charter And Opportunity Map

- Purpose: define the research question and prevent uncontrolled expansion.
- Allowed work: charters, opportunity maps, gate policy, evidence standards.
- Forbidden work: new strategy code, broker integration, live trading, parameter optimization.
- Evidence required: completed research-direction packet.
- Exit criteria: scope decision and implementation gates are documented.

## Phase 1 - ETF Research Lab

- Purpose: test daily ETF strategies with adjusted OHLC, realistic stops, and audit files.
- Allowed work: fixed ETF strategies, benchmarks, validation modes, evidence packets.
- Forbidden work: non-ETF implementation, AI gating, high-risk derivatives.
- Evidence required: standard/stress slippage, rolling windows, target-before-stop, benchmarks.
- Exit criteria: small list of ETF candidates or clear ETF rejection.

## Phase 2 - Evidence-Backed ETF Candidate Comparison

- Purpose: compare a small set of plausible ETF families.
- Allowed work: candidate gating, sampled research, finalist exhaustive validation.
- Forbidden work: tuning based on failures, expanding variants to chase profit.
- Evidence required: candidate_exhaustive for finalists.
- Exit criteria: one or more watchlist candidates, or conclusion that ETF approach is insufficient.

## Phase 3 - Paper-Forward ETF Watchlist Test

- Purpose: observe fixed ETF rules prospectively in paper/demo form.
- Allowed work: daily or weekly observation logs, no rule changes.
- Forbidden work: live orders, real-money recommendations, mid-test parameter changes.
- Evidence required: paper-forward log and comparison to historical assumptions.
- Exit criteria: decide whether research remains interesting or should stop.

## Phase 4 - Non-ETF Research Memos

- Purpose: evaluate other market families before code.
- Allowed work: memos for stocks, options, futures, forex, crypto, volatility, intraday, events.
- Forbidden work: prototypes before Gate 1.
- Evidence required: data, execution, cost, benchmark, and risk feasibility review.
- Exit criteria: reject, defer, or approve isolated prototype.

## Phase 5 - Non-ETF Prototype Only If Gates Pass

- Purpose: test a non-ETF family only after feasibility is established.
- Allowed work: isolated experimental module and evidence packet.
- Forbidden work: integration into active tournament before validation.
- Evidence required: Gate 2 and Gate 3 evidence.
- Exit criteria: reject, defer, or move to paper-forward watchlist.

## Phase 6 - Final Audit And Decision

- Purpose: decide what the research actually supports.
- Allowed work: final evidence review and documentation.
- Forbidden work: changing rules to improve the final result.
- Evidence required: final audit packet, no hidden exclusions, no unreported weak results.
- Exit criteria: continue research, paper-forward observe, or stop.
