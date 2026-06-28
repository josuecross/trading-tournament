from __future__ import annotations

from dataclasses import dataclass


CANDIDATE_IDS = (
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
)


@dataclass(frozen=True)
class InfrastructureStatus:
    data_schema_contract: bool
    cache_contract: bool
    session_timing_contract: bool
    fill_model_contract: bool
    risk_engine_contract: bool
    kill_switch_contract: bool
    event_logging_contract: bool
    intraday_data_present: bool
    intraday_data_source_approved: bool

    @property
    def core_contracts_present(self) -> bool:
        return all(
            [
                self.data_schema_contract,
                self.cache_contract,
                self.session_timing_contract,
                self.fill_model_contract,
                self.risk_engine_contract,
                self.kill_switch_contract,
                self.event_logging_contract,
            ]
        )


def evaluate_candidate_readiness(status: InfrastructureStatus) -> dict[str, str]:
    if status.core_contracts_present and status.intraday_data_present and status.intraday_data_source_approved:
        value = "ready_for_harness_preregistration"
    else:
        value = "research_concept_not_ready"
    return {candidate_id: value for candidate_id in CANDIDATE_IDS}
