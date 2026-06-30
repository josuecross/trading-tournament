from __future__ import annotations

from dataclasses import dataclass


BATCH_ID = "batch_002_revised_objective"
REVISED_OBJECTIVE_PROFILE = "realistic_etf_wrapper_growth_objective"
INITIAL_STATUS = "non_promotable_exploration"

MAX_TOTAL_VARIANTS = 100
MAX_FAMILIES = 5
MAX_VARIANTS_PER_FAMILY = 20
MAX_PARAMETER_CHOICES_PER_INDICATOR = 4
MAX_PORTFOLIO_COMBINATION_VARIANTS = 30

OLD_DOLLAR_TARGET_IS_HARD_GATE = False
STRETCH_DIAGNOSTICS_ARE_PROMOTION_GATES = False
SANDBOX_RESULTS_CAN_PROMOTE = False
PAPER_CANDIDATES_CAN_BE_CREATED = False

ALLOWED_INDICATORS = (
    "sma",
    "ema",
    "atr",
    "rsi",
    "bollinger_bands",
    "realized_volatility",
    "roc_rolling_return",
    "donchian_prior_high",
    "volume_sma_filter_alignment",
    "rolling_percentile_rank",
    "moving_average_regime",
    "spy_regime_features",
)

FORBIDDEN_INDICATORS = (
    "macd",
    "keltner_channel",
    "obv",
    "external_indicator_libraries",
    "candlestick_pattern_mining",
    "ai_generated_formulas",
    "genetic_search",
)

ALLOWED_RESULT_STATUSES = (
    "sandbox_discard",
    "sandbox_family_weak",
    "sandbox_family_interesting",
    "sandbox_component_candidate",
    "sandbox_portfolio_sleeve_candidate",
    "sandbox_needs_objective_reset",
    "sandbox_data_blocked",
    "sandbox_future_preregistration_candidate",
)

FORBIDDEN_STATUSES = (
    "promotion_review_candidate",
    "candidate_exhaustive",
    "paper_forward",
    "paper_forward_active",
    "demo_active",
    "live_ready",
)

INCLUDED_FAMILIES = (
    "breakout_continuation",
    "portfolio_combination_sleeve_ensemble",
    "volatility_regime",
    "trend_momentum",
    "macro_portfolio_contribution",
)

EXCLUDED_FAMILIES = (
    "mean_reversion",
    "factor_style_rotation",
)


@dataclass(frozen=True)
class RevisedFamilyDefinition:
    family_id: str
    objective_lane: str
    planned_variant_cap: int
    purpose: str
    batch_001_lesson: str
    implementation_requirement: str
    universe_groups: tuple[str, ...]
    indicator_concepts: tuple[str, ...]
    variant_roles: tuple[str, ...]


FAMILY_DEFINITIONS: dict[str, RevisedFamilyDefinition] = {
    "breakout_continuation": RevisedFamilyDefinition(
        family_id="breakout_continuation",
        objective_lane="portfolio_contribution_sleeve",
        planned_variant_cap=18,
        purpose="Potential low-correlation sleeve or drawdown-controlled component.",
        batch_001_lesson="Low correlation and gentler drawdown were useful, but objective progress was weak.",
        implementation_requirement=(
            "Represent with contribution-aware fields; do not treat as standalone alpha unless future execution "
            "shows realistic objective progress."
        ),
        universe_groups=("core_equity", "sector", "macro"),
        indicator_concepts=("donchian_prior_high", "atr", "moving_average_regime"),
        variant_roles=("low_correlation_sleeve", "drawdown_control_component", "cash_drag_reduction_probe"),
    ),
    "portfolio_combination_sleeve_ensemble": RevisedFamilyDefinition(
        family_id="portfolio_combination_sleeve_ensemble",
        objective_lane="portfolio_contribution_sleeve",
        planned_variant_cap=18,
        purpose="Test whether combinations improve active VM/DSR portfolio behavior.",
        batch_001_lesson="Too correlated with active combo; contribution claim was weak.",
        implementation_requirement=(
            "Add explicit high active-combo correlation and duplicate active-combo behavior penalties."
        ),
        universe_groups=("core_equity", "macro", "factor_style"),
        indicator_concepts=("realized_volatility", "rolling_percentile_rank", "spy_regime_features"),
        variant_roles=("active_combo_penalty_probe", "vm_dsr_sleeve_mix", "static_all_weather_contribution_probe"),
    ),
    "volatility_regime": RevisedFamilyDefinition(
        family_id="volatility_regime",
        objective_lane="standalone_growth",
        planned_variant_cap=16,
        purpose="High-upside/high-risk diagnostic under revised scoring.",
        batch_001_lesson="Some upside, but drawdown failures.",
        implementation_requirement=(
            "Keep diagnostic unless future execution shows drawdown and risk-integrity improvement; stretch "
            "diagnostics alone cannot make it actionable."
        ),
        universe_groups=("core_equity", "sector", "factor_style"),
        indicator_concepts=("realized_volatility", "atr", "spy_regime_features"),
        variant_roles=("risk_buffer_probe", "high_vol_defense_probe", "upside_with_drawdown_penalty"),
    ),
    "trend_momentum": RevisedFamilyDefinition(
        family_id="trend_momentum",
        objective_lane="standalone_growth",
        planned_variant_cap=16,
        purpose="Risk-adjusted trend/momentum map under the realistic objective.",
        batch_001_lesson="Some active-combo beats, but drawdown failures.",
        implementation_requirement=(
            "Require risk-integrity and overfit-risk scoring; high-return/high-drawdown rows cannot dominate."
        ),
        universe_groups=("core_equity", "sector", "factor_style"),
        indicator_concepts=("roc_rolling_return", "sma", "ema", "moving_average_regime"),
        variant_roles=("risk_adjusted_momentum", "drawdown_filtered_trend", "active_reference_relevance_probe"),
    ),
    "macro_portfolio_contribution": RevisedFamilyDefinition(
        family_id="macro_portfolio_contribution",
        objective_lane="portfolio_contribution_sleeve",
        planned_variant_cap=12,
        purpose="Contribution and benchmark-context family.",
        batch_001_lesson="Low correlation/diversification but weak standalone progress.",
        implementation_requirement=(
            "Score primarily as portfolio contribution or benchmark context, not standalone alpha unless objective "
            "progress is materially improved."
        ),
        universe_groups=("macro", "core_equity", "factor_style"),
        indicator_concepts=("rolling_percentile_rank", "realized_volatility", "spy_regime_features"),
        variant_roles=("benchmark_context_probe", "drawdown_contribution_probe", "risk_adjusted_contribution_probe"),
    ),
}

EXCLUDED_FAMILY_REASONS = {
    "mean_reversion": (
        "daily ETF version was weak and likely needs intraday/shorter horizon, which remains blocked"
    ),
    "factor_style_rotation": (
        "likely equity-beta heavy and not sufficiently distinct under the current objective"
    ),
}


def assert_status_allowed(status: str) -> str:
    if status in FORBIDDEN_STATUSES:
        raise ValueError(f"forbidden revised-objective sandbox status blocked: {status}")
    if status == INITIAL_STATUS or status in ALLOWED_RESULT_STATUSES:
        return status
    raise ValueError(f"unknown revised-objective sandbox status: {status}")


def forbidden_statuses_blocked() -> bool:
    for status in FORBIDDEN_STATUSES:
        try:
            assert_status_allowed(status)
        except ValueError:
            continue
        return False
    return True
