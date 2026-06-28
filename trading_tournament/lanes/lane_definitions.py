"""Lane definitions for the family-first research OS."""

LANES = {
    "conservative_etf_allocation_lane": {"roles": ["risk_reducer", "profit_engine"]},
    "moderate_tactical_etf_lane": {"roles": ["profit_engine", "risk_reducer"]},
    "macro_gld_duration_risk_off_lane": {"roles": ["diversifier", "risk_reducer", "profit_engine"]},
    "diversifier_contribution_lane": {"roles": ["diversifier", "benchmark_control"]},
    "intraday_research_only_lane": {"roles": ["execution_research_only", "data_methodology_only"]},
    "benchmark_control_lane": {"roles": ["benchmark_control"]},
}
