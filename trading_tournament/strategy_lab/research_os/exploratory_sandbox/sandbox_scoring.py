from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringCategory:
    score_id: str
    purpose: str
    required_future_inputs: tuple[str, ...]
    computes_now: bool = False


SCORING_CATEGORIES = (
    ScoringCategory(
        "family_robustness_score",
        "Assess whether behavior survives nearby parameters, related symbols, and related universes.",
        ("same-window family variants", "nearby parameter sets", "symbol/universe breadth"),
    ),
    ScoringCategory(
        "risk_score",
        "Assess drawdown, stop-risk, volatility, and stress sensitivity if a future batch is authorized.",
        ("future drawdown diagnostics", "future stop-risk diagnostics", "future slippage/cost stress"),
    ),
    ScoringCategory(
        "benchmark_score",
        "Compare future sandbox outputs against same-window references.",
        ("SPY/QQQ/BIL", "active VM", "active DSR", "active combo", "static all-weather control"),
    ),
    ScoringCategory(
        "diversification_score",
        "Separate portfolio contribution from standalone alpha claims.",
        ("future correlation matrix", "future contribution attribution", "active-reference overlap"),
    ),
    ScoringCategory(
        "practicality_score",
        "Assess operational simplicity, turnover, data depth, and instrument availability.",
        ("future turnover estimate", "future trade frequency", "cache depth", "ETF wrapper constraints"),
    ),
    ScoringCategory(
        "overfitting_risk_score",
        "Penalize parameter sensitivity, outlier dependence, and excessive variant volume.",
        ("variant count", "parameter sensitivity", "regime concentration", "limited-history labels"),
    ),
)


def scoring_framework_rows() -> list[dict[str, object]]:
    return [
        {
            "score_id": item.score_id,
            "purpose": item.purpose,
            "required_future_inputs": list(item.required_future_inputs),
            "computes_now": item.computes_now,
        }
        for item in SCORING_CATEGORIES
    ]


def scoring_framework_report() -> str:
    lines = [
        "# Sandbox Scoring Framework",
        "",
        "This task defines score structure only. It does not calculate strategy performance metrics.",
        "",
    ]
    for row in scoring_framework_rows():
        lines.append(f"## `{row['score_id']}`")
        lines.append(f"- Purpose: {row['purpose']}")
        lines.append(f"- Required future inputs: `{', '.join(row['required_future_inputs'])}`")
        lines.append(f"- Computes now: `{row['computes_now']}`")
        lines.append("")
    return "\n".join(lines)
