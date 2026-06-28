"""Lane-specific gate expectations.

These helpers are policy metadata only; they do not run strategy research.
"""

LANE_GATES = {
    "profit_engine": ["standalone_edge", "risk_buffer_pass", "stress_survival"],
    "risk_reducer": ["drawdown_improvement", "objective_not_destroyed", "duplication_review"],
    "diversifier": ["portfolio_contribution", "same_window_controls", "not_promoted_as_benchmark_only"],
    "benchmark_control": ["comparison_value", "not_promotion_eligible"],
    "execution_research_only": ["data_source_approved", "fill_contract_ready", "no_strategy_testing_while_blocked"],
}
