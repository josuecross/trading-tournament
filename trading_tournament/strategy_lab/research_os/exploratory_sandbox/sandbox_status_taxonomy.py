from __future__ import annotations

from .sandbox_config import INITIAL_SANDBOX_STATUS


ALLOWED_SANDBOX_STATUSES = (
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


def assert_status_allowed(status: str, *, allow_initial_status: bool = True) -> str:
    if status in FORBIDDEN_STATUSES:
        raise ValueError(f"forbidden sandbox status blocked: {status}")
    if allow_initial_status and status == INITIAL_SANDBOX_STATUS:
        return status
    if status not in ALLOWED_SANDBOX_STATUSES:
        raise ValueError(f"unknown sandbox status: {status}")
    return status


def forbidden_statuses_blocked() -> bool:
    for status in FORBIDDEN_STATUSES:
        try:
            assert_status_allowed(status)
        except ValueError:
            continue
        return False
    return True


def status_taxonomy_report() -> str:
    allowed = "\n".join(f"- `{status}`" for status in ALLOWED_SANDBOX_STATUSES)
    forbidden = "\n".join(f"- `{status}`" for status in FORBIDDEN_STATUSES)
    return f"""# Sandbox Status Taxonomy

Initial variant-plan status:

- `{INITIAL_SANDBOX_STATUS}`

Allowed future sandbox result statuses:

{allowed}

Forbidden statuses:

{forbidden}

Forbidden statuses are rejected by code before sandbox output is written.
"""
