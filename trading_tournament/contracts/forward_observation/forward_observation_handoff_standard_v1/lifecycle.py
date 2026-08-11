from __future__ import annotations

from dataclasses import asdict, dataclass

from .errors import StandardContractError


STATES = {
    "research_eligible",
    "handoff_exported",
    "imported",
    "validated_not_active",
    "paper_demo_initialized",
    "paper_demo_active",
    "paper_demo_paused",
    "paper_demo_disabled",
    "microtrading_eligible",
    "microtrading_active",
}
ALLOWED = {
    ("research_eligible", "handoff_exported"),
    ("handoff_exported", "imported"),
    ("imported", "validated_not_active"),
    ("validated_not_active", "paper_demo_initialized"),
    ("paper_demo_initialized", "paper_demo_active"),
    ("paper_demo_active", "paper_demo_paused"),
    ("paper_demo_paused", "paper_demo_active"),
    ("validated_not_active", "paper_demo_disabled"),
    ("paper_demo_initialized", "paper_demo_disabled"),
    ("paper_demo_active", "paper_demo_disabled"),
    ("paper_demo_paused", "paper_demo_disabled"),
}


@dataclass(frozen=True)
class LifecycleTransition:
    prior_state: str
    next_state: str
    timestamp: str
    evidence_id: str
    actor_task_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_transition(transition: LifecycleTransition) -> LifecycleTransition:
    if transition.prior_state not in STATES or transition.next_state not in STATES:
        raise StandardContractError("state_contract_failure", "Unknown lifecycle state")
    if transition.next_state in {"microtrading_eligible", "microtrading_active"}:
        raise StandardContractError(
            "microtrading_promotion_not_authorized",
            "Microtrading transition requires a future explicit promotion contract",
        )
    if (transition.prior_state, transition.next_state) not in ALLOWED:
        raise StandardContractError(
            "state_contract_failure",
            f"Lifecycle transition is not allowed: {transition.prior_state} -> {transition.next_state}",
        )
    if not all([transition.timestamp, transition.evidence_id, transition.actor_task_id, transition.reason]):
        raise StandardContractError("state_contract_failure", "Lifecycle transition evidence is incomplete")
    return transition
