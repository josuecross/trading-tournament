# Research Memos

Research memos are required before non-ETF implementation. They are scope-control documents, not strategy approvals.

Gate 0 memos are research-only. They describe the instrument or strategy family, data needs, execution risks, modeling risks, and whether the idea deserves Gate 1 feasibility review.

Gate 1 is feasibility review. It must identify data sources, execution assumptions, risk models, benchmark requirements, validation design, and failure criteria before any prototype is considered.

Current Gate 1 memo:

- `gate1/individual_stock_momentum/` - decision: defer. Serious Gate 2 implementation remains blocked until survivorship-free data, delistings, point-in-time universe construction, costs, and runtime are resolved.
- `gate1/individual_stock_momentum/vendor_verification/` - Gate 1A decision: continue_defer. CRSP and Norgate Data are the main follow-up candidates, but Gate 2 remains blocked.

No memo validates a strategy. No memo recommends real-money trading. No memo authorizes broker integration, live orders, AI trading gates, or parameter optimization.

Exploratory lane pointer: `exploratory/crypto_spot_momentum/` is a Tier 1 long-only crypto spot screen. It is non-final, separate from research memos and ETF validation, and makes no real-money recommendation.
