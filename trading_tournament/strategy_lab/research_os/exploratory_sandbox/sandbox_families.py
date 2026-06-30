from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    purpose: str
    allowed_indicators: tuple[str, ...]
    allowed_universe_groups: tuple[str, ...]
    allowed_parameter_concepts: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    sandbox_only_status: bool = True


COMMON_FORBIDDEN_USES = (
    "direct promotion",
    "candidate_exhaustive",
    "paper_forward_activation",
    "broker_live_path",
    "real_money_recommendation",
    "post-result threshold tuning",
)

ALLOWED_FAMILIES: dict[str, FamilySpec] = {
    "trend_momentum": FamilySpec(
        "trend_momentum",
        "Map fixed trend and momentum behavior across ETF wrappers without choosing a best backtest.",
        ("sma", "ema", "roc_rolling_return", "moving_average_regime", "spy_regime_features"),
        ("core_equity", "sector", "factor_style", "international_regional", "managed_futures_wrappers"),
        ("trend_lookback", "rank_lookback", "risk_filter_state", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "mean_reversion": FamilySpec(
        "mean_reversion",
        "Map whether bounded pullback/reversion behavior exists after explicit risk filtering.",
        ("rsi", "bollinger_bands", "rolling_percentile_rank", "realized_volatility"),
        ("core_equity", "sector", "factor_style", "international_regional"),
        ("reversion_window", "oversold_band", "exit_state", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "breakout_continuation": FamilySpec(
        "breakout_continuation",
        "Map prior-high and volatility-compression continuation concepts with no tuned breakout rescue.",
        ("donchian_prior_high", "atr", "realized_volatility", "roc_rolling_return"),
        ("core_equity", "sector", "macro", "managed_futures_wrappers"),
        ("breakout_window", "volatility_filter", "confirmation_window", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "volatility_regime": FamilySpec(
        "volatility_regime",
        "Map volatility and market-state filters as research components, not standalone promotion claims.",
        ("realized_volatility", "atr", "rolling_percentile_rank", "moving_average_regime", "spy_regime_features"),
        ("core_equity", "sector", "macro", "factor_style", "credit_income"),
        ("volatility_window", "state_percentile", "defensive_shift", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "factor_style_rotation": FamilySpec(
        "factor_style_rotation",
        "Map style/factor ETF rotation robustness without reopening rejected QVM/LVQ variants.",
        ("roc_rolling_return", "sma", "rolling_percentile_rank", "moving_average_regime"),
        ("factor_style", "core_equity"),
        ("rank_window", "top_n_bucket", "defensive_filter", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "macro_portfolio_contribution": FamilySpec(
        "macro_portfolio_contribution",
        "Map whether macro sleeves contribute diversification versus active VM/DSR references.",
        ("roc_rolling_return", "sma", "realized_volatility", "spy_regime_features"),
        ("macro", "credit_income", "managed_futures_wrappers", "core_equity"),
        ("sleeve_weight", "risk_state", "contribution_window", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES,
    ),
    "portfolio_combination_sleeve_ensemble": FamilySpec(
        "portfolio_combination_sleeve_ensemble",
        "Map sleeve-combination contribution while distinguishing benchmark value from standalone alpha.",
        ("realized_volatility", "roc_rolling_return", "moving_average_regime", "spy_regime_features"),
        ("core_equity", "macro", "managed_futures_wrappers", "factor_style", "credit_income"),
        ("sleeve_mix", "risk_overlay", "cash_weight", "rebalance_frequency"),
        COMMON_FORBIDDEN_USES + ("duplicate active combo promotion",),
    ),
}


def family_registry_rows() -> list[dict[str, object]]:
    return [
        {
            "family_id": item.family_id,
            "purpose": item.purpose,
            "allowed_indicators": list(item.allowed_indicators),
            "allowed_universe_groups": list(item.allowed_universe_groups),
            "allowed_parameter_concepts": list(item.allowed_parameter_concepts),
            "forbidden_uses": list(item.forbidden_uses),
            "sandbox_only_status": item.sandbox_only_status,
        }
        for item in ALLOWED_FAMILIES.values()
    ]


def family_registry_report() -> str:
    lines = ["# Sandbox Family Registry", ""]
    for row in family_registry_rows():
        lines.append(f"## `{row['family_id']}`")
        lines.append(f"- Purpose: {row['purpose']}")
        lines.append(f"- Allowed indicators: `{', '.join(row['allowed_indicators'])}`")
        lines.append(f"- Allowed universe groups: `{', '.join(row['allowed_universe_groups'])}`")
        lines.append(f"- Allowed parameter concepts: `{', '.join(row['allowed_parameter_concepts'])}`")
        lines.append(f"- Sandbox-only status: `{row['sandbox_only_status']}`")
        lines.append("- Forbidden uses: " + "; ".join(row["forbidden_uses"]))
        lines.append("")
    return "\n".join(lines)
