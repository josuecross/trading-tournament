from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSpec:
    indicator_id: str
    display_name: str
    validated: bool = True
    source: str = "current_custom_indicators"
    allowed_for_sandbox: bool = True
    future_parity_required: bool = False
    forbidden_for_promotion_directly: bool = True


ALLOWED_INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec("sma", "SMA"),
    IndicatorSpec("ema", "EMA"),
    IndicatorSpec("atr", "ATR"),
    IndicatorSpec("rsi", "RSI"),
    IndicatorSpec("bollinger_bands", "Bollinger bands"),
    IndicatorSpec("realized_volatility", "realized volatility"),
    IndicatorSpec("roc_rolling_return", "ROC / rolling return"),
    IndicatorSpec("donchian_prior_high", "Donchian prior high"),
    IndicatorSpec("volume_sma_filter_alignment", "volume SMA / filter alignment"),
    IndicatorSpec("rolling_percentile_rank", "rolling percentile rank"),
    IndicatorSpec("moving_average_regime", "moving-average regime"),
    IndicatorSpec("spy_regime_features", "SPY regime features"),
)

FORBIDDEN_INDICATORS: dict[str, str] = {
    "macd": "not validated under the current custom-indicator policy",
    "keltner_channel": "not validated under the current custom-indicator policy",
    "obv": "not validated under the current custom-indicator policy",
    "external_indicator_library_outputs": "no indicator-library dependency is authorized",
    "candlestick_pattern_mining": "pattern mining is outside the preregistered sandbox scope",
    "ai_selected_formulas": "formula mining creates false confidence and overfitting risk",
    "genetic_search": "genetic search is not a fixed-rule bounded research lane",
    "broad_unconstrained_indicator_voting_systems": "unconstrained voting systems are not allowed",
}


def normalize_indicator_id(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("  ", " ")
        .replace(" ", "_")
    )


def indicator_by_id() -> dict[str, IndicatorSpec]:
    by_id = {item.indicator_id: item for item in ALLOWED_INDICATORS}
    by_id.update({normalize_indicator_id(item.display_name): item for item in ALLOWED_INDICATORS})
    return by_id


def validate_indicator_concept(indicator_id: str) -> IndicatorSpec:
    normalized = normalize_indicator_id(indicator_id)
    if normalized in FORBIDDEN_INDICATORS:
        raise ValueError(f"forbidden indicator blocked: {indicator_id}")
    spec = indicator_by_id().get(normalized)
    if spec is None or not spec.allowed_for_sandbox or not spec.validated:
        raise ValueError(f"indicator is not allowed for sandbox use: {indicator_id}")
    return spec


def indicator_registry_rows() -> list[dict[str, object]]:
    return [
        {
            "indicator_id": item.indicator_id,
            "display_name": item.display_name,
            "validated": item.validated,
            "source": item.source,
            "allowed_for_sandbox": item.allowed_for_sandbox,
            "future_parity_required": item.future_parity_required,
            "forbidden_for_promotion_directly": item.forbidden_for_promotion_directly,
        }
        for item in ALLOWED_INDICATORS
    ]


def indicator_registry_report() -> str:
    lines = [
        "# Sandbox Indicator Registry",
        "",
        "Only validated custom indicators are allowed. No indicator-library dependency is added.",
        "",
        "## Allowed",
    ]
    for row in indicator_registry_rows():
        lines.append(f"- `{row['indicator_id']}`: {row['display_name']} (source: `{row['source']}`)")
    lines.extend(["", "## Forbidden"])
    for indicator_id, reason in FORBIDDEN_INDICATORS.items():
        lines.append(f"- `{indicator_id}`: {reason}")
    return "\n".join(lines)
