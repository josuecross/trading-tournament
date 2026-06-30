from __future__ import annotations


LEVERAGE_DIAGNOSTIC_LEVELS = ("1.0x", "1.25x", "1.5x", "2.0x")


def allowed_leverage_policy_values() -> tuple[str, ...]:
    return tuple(f"{level}_research_only_non_promotable" for level in LEVERAGE_DIAGNOSTIC_LEVELS)


def validate_leverage_policy(value: str) -> str:
    if value not in allowed_leverage_policy_values():
        raise ValueError(f"leverage policy is not sandbox-approved: {value}")
    return value


def leverage_policy_report() -> str:
    levels = "\n".join(f"- `{level}`" for level in LEVERAGE_DIAGNOSTIC_LEVELS)
    policies = "\n".join(f"- `{policy}`" for policy in allowed_leverage_policy_values())
    return f"""# Sandbox Research-Only Leverage Policy

Allowed future diagnostic levels:

{levels}

Allowed variant-plan policy labels:

{policies}

Rules:

- Simulation-only.
- Non-promotable.
- No broker, margin, live, or real-money use.
- Must report drawdown amplification if executed later.
- Must report stop-risk breach sensitivity if executed later.
- Cannot convert a weak strategy into a promotion candidate.
"""
