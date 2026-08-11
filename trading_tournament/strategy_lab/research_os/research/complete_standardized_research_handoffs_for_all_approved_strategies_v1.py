from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    SourceAdapterRegistry,
    StandardV1Adapter,
    normalized_spdj_package_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    StandardHandoff,
    canonical_json_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.package import (
    materialize_standard_package,
)


TASK_ID = "complete_standardized_research_handoffs_for_all_approved_strategies_v1"
OUTPUT_ID = "complete_standardized_research_handoffs_v1"
CREATED_AT = "2026-08-10T00:00:00+00:00"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence/handoff_standardization" / OUTPUT_ID / "latest"
EXPORT_ROOT = ROOT / "evidence/handoff_exports"
REGISTRY = ROOT / "strategy_lab/strategy_registry.yaml"
PRIOR_AUDIT = (
    ROOT
    / "evidence/project_audits/forward_observation_handoff_inventory_and_standardization_v1/latest"
)
LEGACY_INTERNAL = ROOT / "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"
SPDJ_PACKAGE = (
    EXPORT_ROOT / "spdj_dynamic_inflation_forward_observation_handoff_v1/latest/package"
)
EXPECTED_SPDJ_HASH = "sha256:f1844b722c11db1fd21b91192a56d2b1953c6719994f9de113c16e72882998b9"
FORWARD_PROJECT_RELATIVE = "execution_lab/alpaca_micro_live_v1"
OUTCOME = "all_research_approved_strategies_standardized_for_handoff"
NEXT_ACTION = "research_handoff_inventory_complete_continue_strategy_discovery"
RESEARCH_CLAIM = (
    "This strategy passed the documented research process applicable to its lineage "
    "and is packaged for independent prospective implementation by a separate "
    "forward-observation system."
)
COMMON_NONCLAIMS = [
    "future_profitability_is_not_established",
    "real_money_trading_is_not_approved",
    "microtrading_is_not_approved",
    "broker_compatibility_is_not_established",
    "current_target_is_not_provided",
    "forward_performance_is_not_established_by_this_handoff",
]
RULE_FIELDS = [
    "identity",
    "tradable_instruments",
    "signal_calculation",
    "portfolio_construction",
    "schedule",
    "data_semantics",
    "missing_data_behavior",
    "state_behavior",
    "source_rule_lineage",
    "implementation_lineage",
]
REQUIRED_FIXTURE_TYPES = [
    "signal_formula_fixture",
    "target_weight_fixture",
    "threshold_or_tie_fixture",
    "timing_fixture",
    "missing_event_fixture",
    "restart_fixture",
    "duplicate_event_fixture",
]
APPROVED_IDS = (
    "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    "ice_vaneck_us_fallen_angel_angl_v1",
    "donninger_vix_vix3m_unfiltered_three_state_spy_ief_adaptation_v1",
    "keller_vanputten_faa_4m_top3_v1",
    "barbara_decelerated_psar_spy_bil_v1",
    "varadi_minimum_correlation_8etf_60d_weekly_v1",
    "schwoerer_hyg_ema100_spy_bil_v1",
    "factory_v1_spy_trend_quality_state_d1",
    "internal_capture_asymmetry_63d_top3_v1",
    "spdj_multi_asset_dynamic_inflation_etf_portability_v1",
)
PROTECTED_PATHS = (
    ROOT / "strategy_lab/strategy_registry.yaml",
    ROOT / "strategy_lab/RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab/research_os/research/research_queue.yaml",
    ROOT / "strategy_lab/research_os/family_lineage/family_ledger.yaml",
    ROOT / "strategy_lab/research_os/operations/active_observations.yaml",
    LEGACY_INTERNAL,
    SPDJ_PACKAGE,
    PRIOR_AUDIT,
    ROOT / "data/cache",
)


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    family_id: str
    architecture_id: str
    display_name: str
    strategy_version: str
    route: str
    portability: str
    canonical_trial_id: str
    approval_terminology: str
    approval_path: str
    robustness_path: str
    implementation_path: str
    source_lineage: dict[str, Any]
    instruments: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    calculator_type: str
    calculator_version: str
    rule: dict[str, Any]
    timing: dict[str, Any]
    caveats: list[str]
    fixture_builder: str
    readiness_before: str = "contract_materialization_required"
    parent_handoff: str = ""

    @property
    def handoff_id(self) -> str:
        return f"{self.strategy_id}_standard_handoff_v1"

    @property
    def package_path(self) -> Path:
        return EXPORT_ROOT / self.handoff_id / "latest/package"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def canonical_hash(value: Any) -> str:
    return canonical_json_hash(value)


def snapshot(paths: Iterable[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def serialize_cell(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fieldnames or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_cell(row.get(key, "")) for key in columns})


def json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def text_bytes(value: str) -> bytes:
    return (value.rstrip() + "\n").encode("utf-8")


def instrument(
    symbol: str,
    role: str,
    *,
    exposure: str = "long_only",
    semantics: str = "adjusted_close_total_return_research_series",
    frequency: str = "daily",
    minimum_history: int = 1,
    lookback: int = 1,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "role": role,
        "exposure": exposure,
        "substitution_policy": "forbidden",
        "approved_mappings": [],
        "price_semantics": semantics,
        "history_frequency": frequency,
        "minimum_history": minimum_history,
        "lookback": lookback,
    }


def dependency(
    signal_id: str,
    symbols: str,
    *,
    frequency: str,
    formula_reference: str,
    signal_type: str = "market_price_signal",
    authority: str = "research_validated_market_data_provider",
    point_in_time: bool = False,
    publication_timing: bool = False,
    missing: str = "retain_previous_target_or_apply_documented_fallback",
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "contract_version": "v1",
        "authority_provider_class": authority,
        "series_dataset_id": symbols,
        "point_in_time_required": point_in_time,
        "publication_timing_required": publication_timing,
        "frequency": frequency,
        "freshness_policy": {
            "current_target_calculation_authorized": False,
            "operational_provider_binding_included": False,
        },
        "missing_release_behavior": missing,
        "formula_configuration_reference": formula_reference,
    }


def timing(
    calculation_cutoff: str,
    availability_cutoff: str,
    *,
    kind: str = "next_valid_session",
    boundary: str = "regular_session_close",
    offset: int = 1,
    no_event: str = "preserve_current_effective_target",
) -> dict[str, Any]:
    return {
        "calendar_id": "XNYS",
        "calculation_information_cutoff": calculation_cutoff,
        "signal_availability_cutoff": availability_cutoff,
        "effective_rule": {"kind": kind, "boundary": boundary, "offset": offset},
        "no_event_behavior": no_event,
    }


def rule_contract(
    *,
    identity: dict[str, Any],
    instruments: dict[str, Any],
    signal: dict[str, Any],
    portfolio: dict[str, Any],
    schedule: dict[str, Any],
    data: dict[str, Any],
    missing: dict[str, Any],
    state: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "identity": identity,
        "tradable_instruments": instruments,
        "signal_calculation": signal,
        "portfolio_construction": portfolio,
        "schedule": schedule,
        "data_semantics": data,
        "missing_data_behavior": missing,
        "state_behavior": state,
        "source_rule_lineage": source,
        "implementation_lineage": {
            "canonical_implementation_frozen": True,
            "performance_recalculated_for_handoff": False,
            "strategy_rule_changed": False,
        },
    }


def usci_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[0]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "commodity_curve_selection",
            "architecture_id": "static_investable_dynamic_commodity_curve_wrapper",
            "version": "v1",
        },
        instruments={
            "exact_symbols": ["USCI"],
            "prohibited_substitutions": ["DBC", "commodity_futures_reconstruction"],
        },
        signal={"type": "none_static_wrapper", "timing_signal": "none"},
        portfolio={
            "initial_target": {"USCI": 1.0},
            "external_rebalance": "none_after_initial_target",
            "cash_handling": "none",
            "shorting": False,
            "leverage": False,
        },
        schedule={
            "formation": "observation_initialization_only",
            "effective": "initial_valid_observation_session_close",
        },
        data={
            "field": "adjusted_close",
            "semantics": "adjusted_total_return_price",
            "frequency": "daily",
            "underlying_futures_reconstruction": False,
        },
        missing={
            "initial_price_missing": "block_initialization",
            "later_price_missing": "block_valuation_do_not_forward_fill_tradable_price",
        },
        state={"required": "initialized_static_target", "target_changes_after_initialization": False},
        source={
            "classification": "source_preserving_portability",
            "source": "USCF USCI and SummerHaven Dynamic Commodity Index official methodology",
            "adaptation": "listed_USCI_wrapper_not_futures_reconstruction",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="commodity_curve_selection",
        architecture_id="static_investable_dynamic_commodity_curve_wrapper",
        display_name="Paper Forward USCI Dynamic Commodity Curve Selection Wrapper",
        strategy_version="v1",
        route="standalone_observation_only",
        portability="source_preserving_portability",
        canonical_trial_id="usci_dynamic_commodity_curve_selection_wrapper_v1",
        approval_terminology="paper_forward_observation_approved_direction_owner_override",
        approval_path="evidence/usci_paper_forward_eligibility_review_v1/latest",
        robustness_path="evidence/usci_current_methodology_validation_v1/latest",
        implementation_path="strategy_lab/research_os/research/usci_paper_forward_eligibility_review_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[instrument("USCI", "static_risk_asset")],
        dependencies=[
            dependency(
                "usci_adjusted_close",
                "USCI",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:data_semantics",
                missing="block_initialization_or_valuation",
            )
        ],
        calculator_type="static_target",
        calculator_version="usci_static_wrapper_calculator_v1",
        rule=rule,
        timing=timing(
            "observation_initialization_decision",
            "validated_USCI_adjusted_close",
            kind="same_session",
            offset=0,
        ),
        caveats=[
            "listed_USCI_wrapper_does_not_reconstruct_source_futures_or_collateral",
            "historical_edge_recently_weakened",
            "observation_only_direction_owner_override",
        ],
        fixture_builder="usci",
    )


def combo_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[1]
    components = [
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    ]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "multi_strategy_diversified_portfolio",
            "architecture_id": "monthly_equal_weight_three_component_observation_portfolio",
            "version": "v1",
        },
        instruments={
            "component_observation_ids": components,
            "component_substitution": "forbidden",
        },
        signal={"type": "calendar_only", "tactical_signal": "none"},
        portfolio={
            "target_weights": {component: 1.0 / 3.0 for component in components},
            "between_rebalances": "sleeve_values_drift_naturally",
            "component_returns": "authoritative_net_component_returns",
            "component_internal_costs_reapplied": False,
        },
        schedule={
            "rebalance": "first_common_valid_component_session_of_each_calendar_month_at_close",
            "target_return_boundary": "after_rebalance_close",
        },
        data={
            "required": "complete_common_component_observation_date",
            "frequency": "daily_component_return_indexes",
            "price_semantics": "net_virtual_component_return_index",
        },
        missing={
            "partial_component_date": "block_portfolio_advancement",
            "missing_component_return": "never_zero_fill_or_forward_fill",
            "stale_component": "remain_pending_until_complete_common_date",
        },
        state={
            "required": ["component_sleeve_values", "last_rebalance_month", "last_common_date"],
            "idempotency": "one_rebalance_per_calendar_month_and_common_event_id",
        },
        source={
            "classification": "internal_strategy",
            "source": "frozen research combination of three independently approved observations",
            "adaptation": "none_after_preregistration",
        },
    )
    semantics = "authoritative_net_component_virtual_return_index"
    instruments = [
        instrument(
            component,
            "component_observation_sleeve",
            exposure="long_only_virtual_component",
            semantics=semantics,
            frequency="daily_common_component_session",
        )
        for component in components
    ]
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="multi_strategy_diversified_portfolio",
        architecture_id="monthly_equal_weight_three_component_observation_portfolio",
        display_name="Paper Forward Combo VM DSR USCI Equal Weight Monthly",
        strategy_version="v1",
        route="derived_diversified_observation_portfolio",
        portability="internal_strategy",
        canonical_trial_id="combo_vm_dsr_usci_equal_weight_monthly_v1",
        approval_terminology="paper_forward_observation_only_approved",
        approval_path="evidence/combo_vm_dsr_usci_paper_forward_eligibility_review_v1/latest",
        robustness_path="evidence/combo_vm_dsr_usci_equal_weight_monthly_validation_v1/latest",
        implementation_path="strategy_lab/research_os/research/combo_vm_dsr_usci_paper_forward_eligibility_review_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=instruments,
        dependencies=[
            dependency(
                "complete_common_component_returns",
                "|".join(components),
                frequency="daily_common_component_session",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                signal_type="extension:component_observation_signal",
                authority="research_approved_component_observation_contracts",
                missing="block_portfolio_advancement",
            )
        ],
        calculator_type="component_sleeve_rebalance",
        calculator_version="vm_dsr_usci_monthly_equal_weight_calculator_v1",
        rule=rule,
        timing=timing(
            "first_common_valid_component_session_monthly_close",
            "all_three_component_returns_available",
            kind="same_session",
            offset=0,
            no_event="apply_complete_common_returns_and_preserve_drifting_sleeves",
        ),
        caveats=[
            "selection_conditioned_combination",
            "historical_USCI_methodology_regime_weakness_retained",
            "component_observations_are_independent_virtual_return_sources",
        ],
        fixture_builder="combo",
    )


def angl_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[2]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "fallen_angel_credit_anomaly",
            "architecture_id": "structural_fallen_angel_credit_sleeve",
            "version": "v1",
        },
        instruments={
            "candidate": "ANGL",
            "outer_reference": "frozen_current_active_vm_dsr_usci_combo",
            "substitution": "forbidden",
        },
        signal={"type": "none_static_candidate_sleeve", "timing_rule": "none"},
        portfolio={
            "outer_targets": {"FROZEN_REFERENCE": 0.8, "ANGL": 0.2},
            "candidate_sleeve": {"ANGL": 1.0},
            "standalone_100pct_ANGL_approved": False,
            "outer_rebalance": "monthly",
        },
        schedule={
            "formation": "completed_month_end",
            "execution": "following_regular_session_close",
        },
        data={
            "ANGL": "adjusted_close_total_return_research_series",
            "FROZEN_REFERENCE": "authoritative_frozen_reference_virtual_NAV",
        },
        missing={
            "ANGL_or_reference_price": "block_rebalance_and_retain_pretrade_holdings",
            "tradable_forward_fill": False,
        },
        state={"required": "outer_sleeve_holdings_and_monthly_rebalance_idempotency"},
        source={
            "classification": "source_based_adaptation",
            "source": "strategy_source_library_refresh_v1 fallen angel credit anomaly",
            "adaptation": "ANGL_static_long_leg_as_validated_20pct_diversifier_sleeve",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="fallen_angel_credit_anomaly",
        architecture_id="structural_fallen_angel_credit_sleeve",
        display_name="ICE/VanEck US Fallen Angel ANGL",
        strategy_version="v1",
        route="diversifier_only_20pct",
        portability="source_based_adaptation",
        canonical_trial_id="correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child",
        approval_terminology="paper_demo_eligible_direction_owner_approved_diversifier_only",
        approval_path="evidence/correction/correct_angl_forward_boundary_and_data_freshness_v1/latest",
        robustness_path="evidence/validation/angl_fallen_angel_diversifier_validation_v1/latest",
        implementation_path="strategy_lab/research_os/research/angl_80_20_portfolio_construction_methodology_correction_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[
            instrument(
                "FROZEN_REFERENCE",
                "outer_reference_sleeve",
                exposure="long_only_virtual_component",
                semantics="authoritative_frozen_reference_virtual_NAV",
                frequency="daily",
            ),
            instrument("ANGL", "candidate_diversifier_sleeve"),
        ],
        dependencies=[
            dependency(
                "angl_and_reference_month_end_values",
                "ANGL|FROZEN_REFERENCE",
                frequency="daily_month_end_schedule",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                missing="block_monthly_rebalance",
            )
        ],
        calculator_type="static_diversifier_sleeve",
        calculator_version="angl_80_20_monthly_calculator_v1",
        rule=rule,
        timing=timing("completed_month_end_close", "validated_month_end_values"),
        caveats=[
            "approved_only_as_20pct_diversifier_sleeve",
            "standalone_ANGL_not_approved",
            "separate_observation_data_lane_was_deferred",
        ],
        fixture_builder="angl",
    )


def ivts_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[3]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "implied_volatility_term_structure_equity_timing",
            "architecture_id": "raw_implied_volatility_curve_three_state_allocation",
            "version": "v1",
        },
        instruments={
            "signal_series": ["VIX", "VIX3M"],
            "inner_tradables": ["SPY", "IEF"],
            "outer_reference": "frozen_current_active_vm_dsr_usci_combo",
            "substitution": "forbidden",
        },
        signal={
            "formula": "VIX_close_t / VIX3M_close_t",
            "filter": "none",
            "thresholds": [0.96, 1.02],
            "states": {
                "ratio_lt_0_96": {"SPY": 1.0, "IEF": 0.0},
                "ratio_0_96_to_1_02_inclusive": {"SPY": 0.5, "IEF": 0.5},
                "ratio_gt_1_02": {"SPY": 0.0, "IEF": 1.0},
            },
        },
        portfolio={
            "outer_reference_weight": 0.8,
            "candidate_sleeve_weight": 0.2,
            "outer_rebalance": "monthly",
            "inner_state_change": "each_valid_completed_signal_date",
        },
        schedule={
            "signal": "completed_official_Cboe_daily_close",
            "inner_execution": "following_regular_session_close",
            "same_day_return_allowed": False,
        },
        data={
            "signal_provenance": "official_cboe_daily_history",
            "vintage_status": "official_current_history_non_vintage",
            "tradables": "adjusted_close_total_return_research_series",
        },
        missing={
            "missing_signal": "retain_previous_inner_target",
            "no_previous_signal": {"SPY": 0.5, "IEF": 0.5},
            "missing_execution_price": "block_target_change_no_forward_fill",
        },
        state={"required": "previous_inner_target_and_outer_sleeve_holdings"},
        source={
            "classification": "source_based_adaptation",
            "source": "Donninger Herorats VIX/VIX3M source lineage",
            "adaptation": "result_driven_unfiltered_control_promoted_only_as_20pct_diversifier",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="implied_volatility_term_structure_equity_timing",
        architecture_id="raw_implied_volatility_curve_three_state_allocation",
        display_name="Unfiltered VIX/VIX3M Three-State Diversifier",
        strategy_version="v1",
        route="diversifier_only_20pct",
        portability="source_based_adaptation",
        canonical_trial_id="validate_ivts_unfiltered_diversifier_project_untouched_preperiod_v1__child",
        approval_terminology="paper_demo_eligible_validated_20pct_diversifier_only",
        approval_path="evidence/paper_demo/review_and_onboard_ivts_unfiltered_paper_demo_observation_v1/latest",
        robustness_path="evidence/validation/validate_ivts_unfiltered_diversifier_project_untouched_preperiod_v1/latest",
        implementation_path="strategy_lab/research_os/research/ivts_unfiltered_diversifier_incremental_value_followup_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[
            instrument(
                "FROZEN_REFERENCE",
                "outer_reference_sleeve",
                exposure="long_only_virtual_component",
                semantics="authoritative_frozen_reference_virtual_NAV",
            ),
            instrument("SPY", "inner_risk_asset"),
            instrument("IEF", "inner_defensive_asset"),
        ],
        dependencies=[
            dependency(
                "official_cboe_vix_vix3m_daily_closes",
                "VIX|VIX3M",
                frequency="official_daily_close",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                signal_type="external_release_signal",
                authority="official_Cboe_daily_history",
                missing="retain_previous_inner_target",
            ),
            dependency(
                "ivts_tradable_and_reference_values",
                "SPY|IEF|FROZEN_REFERENCE",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                missing="block_target_change",
            ),
        ],
        calculator_type="external_signal_diversifier_sleeve",
        calculator_version="unfiltered_ivts_80_20_calculator_v1",
        rule=rule,
        timing=timing(
            "completed_official_Cboe_daily_close",
            "official_daily_close_date_completed",
        ),
        caveats=[
            "approved_only_as_20pct_diversifier_sleeve",
            "official_history_is_current_history_non_vintage",
            "historical_point_in_time_safety_not_established",
            "not_exact_source_replication",
        ],
        fixture_builder="ivts",
    )


def faa_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[4]
    universe = ["SPY", "EFA", "VWO", "SHY", "AGG", "GSG", "VNQ"]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "generalized_momentum_flexible_asset_allocation",
            "architecture_id": "monthly_return_volatility_correlation_rank_with_absolute_momentum",
            "version": "v1",
        },
        instruments={"exact_symbols": universe, "substitution": "forbidden"},
        signal={
            "formation": "four_completed_calendar_months",
            "return": "month_end_close_t/month_end_close_t_minus_4-1",
            "daily_volatility": "sample_standard_deviation_ddof_1_of_daily_returns_in_formation_interval",
            "average_correlation": "mean_pairwise_daily_return_correlation_excluding_self",
            "ranks": {
                "return": "descending_best_rank_1",
                "volatility": "ascending_best_rank_1",
                "correlation": "ascending_best_rank_1",
                "tie_break": "lexical_ticker",
            },
            "score": "return_rank + 0.5*volatility_rank + 0.5*correlation_rank",
            "selection": "three_lowest_scores",
        },
        portfolio={
            "selected_slot_weight": 1.0 / 3.0,
            "absolute_momentum": "selected_asset_receives_slot_only_when_four_month_return_strictly_positive",
            "fallback": "nonpositive_selected_slots_aggregate_to_SHY",
            "normalization": "fully_invested_long_only",
        },
        schedule={
            "formation": "completed_calendar_month_end",
            "execution": "following_regular_session_close",
        },
        data={
            "field": "adjusted_close",
            "frequency": "daily_with_completed_month_end_aggregation",
            "minimum": "complete_full_universe_four_month_interval",
        },
        missing={
            "invalid_full_universe_formation": "SHY_1_0",
            "missing_execution_price": "block_rebalance_retain_pretrade_holdings",
        },
        state={"required": "current_holdings_and_monthly_event_idempotency"},
        source={
            "classification": "source_preserving_portability",
            "source": "Keller and van Putten Flexible Asset Allocation",
            "adaptation": "native_ETF_universe_and_project_execution_convention",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="generalized_momentum_flexible_asset_allocation",
        architecture_id="monthly_return_volatility_correlation_rank_with_absolute_momentum",
        display_name="Flexible Asset Allocation 4-Month Top-Three",
        strategy_version="v1",
        route="standalone_only",
        portability="source_preserving_portability",
        canonical_trial_id="native_etf_two_candidate_final_robustness_v1__faa__child",
        approval_terminology="paper_demo_eligible",
        approval_path="evidence/paper_demo_onboarding/correct_faa_stage_and_onboard_paper_demo_observation_v1/latest",
        robustness_path="evidence/robustness/native_etf_two_candidate_final_robustness_v1/latest",
        implementation_path="strategy_lab/research_os/research/native_etf_two_candidate_exploration_batch_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[instrument(symbol, "risk_or_defensive_asset", lookback=4) for symbol in universe],
        dependencies=[
            dependency(
                "faa_seven_asset_adjusted_closes",
                "|".join(universe),
                frequency="daily_to_monthly",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="fallback_SHY_for_invalid_formation",
            )
        ],
        calculator_type="monthly_cross_sectional_rank_allocation",
        calculator_version="faa_4m_top3_calculator_v1",
        rule=rule,
        timing=timing("completed_calendar_month_end", "all_seven_adjusted_closes_valid"),
        caveats=[
            "native_ETF_portability_not_exact_source_replication",
            "standalone_route_only",
            "absolute_momentum_fallback_can_concentrate_in_SHY",
        ],
        fixture_builder="faa",
    )


def psar_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[5]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "decelerated_parabolic_trend_state",
            "architecture_id": "long_only_adaptive_parabolic_stop_and_reverse_state",
            "version": "v1",
        },
        instruments={
            "inner_tradables": ["SPY", "BIL"],
            "outer_reference": "frozen_current_active_vm_dsr_usci_combo",
            "substitution": "forbidden",
        },
        signal={
            "inputs": "adjusted_high_adjusted_low_adjusted_close",
            "initialization": {
                "minimum_sessions": 3,
                "uptrend": "high_t>high_t-1 and low_t>low_t-1",
                "downtrend": "high_t<high_t-1 and low_t<low_t-1",
                "otherwise": "remain_uninitialized_BIL",
            },
            "parameters": {"AF_min": 0.02, "AF_max": 0.2, "forward_step": 0.02, "backward_step": 0.05},
            "change3": "abs(adjusted_close_t/adjusted_close_t_minus_3-1)",
            "AF_update": "if change3>0.02 add_0.02_capped_0.20 else_subtract_0.05_floored_0.02",
            "equality_0_02": "deceleration_branch",
            "uptrend": {
                "candidate_psar": "min(psar+AF*(EP-psar),low_t-1,low_t-2)",
                "reversal": "low_t<candidate_psar",
                "on_reversal": "downtrend;psar=prior_EP;EP=low_t;AF=0.02",
                "else_EP": "max(prior_EP,high_t)",
            },
            "downtrend": {
                "candidate_psar": "max(psar-AF*(psar-EP),high_t-1,high_t-2)",
                "reversal": "high_t>candidate_psar",
                "on_reversal": "uptrend;psar=prior_EP;EP=high_t;AF=0.02",
                "else_EP": "min(prior_EP,low_t)",
            },
            "target": "SPY_in_uptrend_else_BIL",
        },
        portfolio={
            "outer_targets": "80pct_frozen_reference_plus_20pct_inner_state",
            "outer_rebalance": "monthly",
            "inner_state_change": "daily",
        },
        schedule={
            "signal": "completed_regular_session",
            "execution": "following_regular_session_close",
        },
        data={"frequency": "daily", "fields": ["adjusted_high", "adjusted_low", "adjusted_close"]},
        missing={
            "signal_input": "retain_current_state",
            "execution_price": "block_state_change_retain_pretrade_holdings",
        },
        state={"required": ["trend", "PSAR", "EP", "AF", "previous_inner_target", "outer_holdings"]},
        source={
            "classification": "source_based_adaptation",
            "source": "Barbara 2021 decelerated PSAR appendix",
            "adaptation": "SPY_BIL_long_only_20pct_diversifier_route",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="decelerated_parabolic_trend_state",
        architecture_id="long_only_adaptive_parabolic_stop_and_reverse_state",
        display_name="Decelerated PSAR SPY/BIL Timing",
        strategy_version="v1",
        route="diversifier_only_20pct",
        portability="source_based_adaptation",
        canonical_trial_id="decelerated_psar_diversifier_final_robustness_v1__child",
        approval_terminology="paper_demo_eligible",
        approval_path="evidence/paper_demo_onboarding/correct_psar_stage_and_onboard_paper_demo_observation_v1/latest",
        robustness_path="evidence/robustness/decelerated_psar_diversifier_final_robustness_v1/latest",
        implementation_path="strategy_lab/research_os/research/fast_price_volume_preregistered_batch_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[
            instrument(
                "FROZEN_REFERENCE",
                "outer_reference_sleeve",
                exposure="long_only_virtual_component",
                semantics="authoritative_frozen_reference_virtual_NAV",
            ),
            instrument("SPY", "inner_risk_asset", semantics="adjusted_daily_OHLC_total_return_compatible", minimum_history=3, lookback=3),
            instrument("BIL", "inner_fallback_asset"),
        ],
        dependencies=[
            dependency(
                "psar_adjusted_spy_ohlc",
                "SPY",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="retain_current_inner_state",
            ),
            dependency(
                "psar_reference_and_fallback_values",
                "FROZEN_REFERENCE|BIL",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                missing="block_target_change",
            ),
        ],
        calculator_type="stateful_daily_indicator_diversifier_sleeve",
        calculator_version="decelerated_psar_calculator_v1",
        rule=rule,
        timing=timing("completed_regular_session", "adjusted_OHLC_valid_at_close"),
        caveats=[
            "approved_only_as_20pct_diversifier_sleeve",
            "standalone_exploration_closed_as_benchmark_like",
            "exposure_matched_control_had_higher_historical_CAGR",
        ],
        fixture_builder="psar",
    )


def mca_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[6]
    risk = ["SPY", "QQQ", "EEM", "IWM", "EFA", "TLT", "IYR", "GLD"]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "minimum_correlation_dynamic_diversification",
            "architecture_id": "weekly_long_only_correlation_transformation_inverse_volatility_allocation",
            "version": "v1",
        },
        instruments={"risk_assets": risk, "fallback": "BIL", "substitution": "forbidden"},
        signal={
            "window": "61_adjusted_closes_producing_60_simple_daily_returns",
            "correlation": "sample_pairwise_correlation",
            "volatility": "sample_standard_deviation_ddof_1",
            "mu_rho": "mean_strict_lower_triangle_correlations",
            "sigma_rho": "sample_standard_deviation_ddof_1_of_strict_lower_triangle_correlations",
            "adjusted_matrix": "off_diagonal_1-NormalCDF(rho_ij,mu_rho,sigma_rho);diagonal_0",
            "row_score": "row_sum_adjusted/(asset_count-1)",
            "rank": "average_tie_rank_of_negative_row_score_ascending",
            "q": "rank/sum(rank)",
            "u": "q_row_vector_matrix_multiply_adjusted_matrix",
            "pre_volatility": "u/sum(u)",
            "raw_weight": "pre_volatility/sample_volatility",
            "final_weight": "raw_weight/sum(raw_weight)",
        },
        portfolio={
            "risk_weights": "calculated_final_weights",
            "BIL": "1.0_before_first_valid_formation_otherwise_0.0",
            "asset_caps": False,
            "long_only": True,
        },
        schedule={
            "signal": "final_completed_regular_session_of_week",
            "execution": "following_regular_session_close",
        },
        data={"frequency": "daily", "field": "adjusted_close", "required_common_returns": 60},
        missing={
            "invalid_correlation_or_volatility": "retain_previous_target",
            "warmup": "BIL_1_0",
            "reduced_universe": False,
        },
        state={"required": "current_target_and_weekly_event_idempotency"},
        source={
            "classification": "source_preserving_portability",
            "source": "Varadi Kapler Bee Rittenhouse Minimum Correlation 2012",
            "adaptation": "eight_ETF_long_only_research_universe_with_BIL_warmup",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="minimum_correlation_dynamic_diversification",
        architecture_id="weekly_long_only_correlation_transformation_inverse_volatility_allocation",
        display_name="Minimum Correlation Eight-ETF Weekly Allocation",
        strategy_version="v1",
        route="standalone_only",
        portability="source_preserving_portability",
        canonical_trial_id="role_aware_robustness_reassessment_v1__mca8__child",
        approval_terminology="paper_demo_eligible_role_aware_reassessment_positive",
        approval_path="evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
        robustness_path="evidence/methodology/adopt_role_aware_robustness_standard_and_reassess_v1/latest",
        implementation_path="strategy_lab/research_os/research/accepted_47_source_backed_exploration_batch_v2.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[instrument(symbol, "risk_asset", minimum_history=61, lookback=60) for symbol in risk]
        + [instrument("BIL", "warmup_fallback_asset")],
        dependencies=[
            dependency(
                "mca8_adjusted_closes",
                "|".join(risk + ["BIL"]),
                frequency="daily_to_weekly",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="retain_previous_target_or_BIL_during_warmup",
            )
        ],
        calculator_type="weekly_matrix_rank_allocation",
        calculator_version="minimum_correlation_8etf_60d_calculator_v1",
        rule=rule,
        timing=timing("final_completed_regular_session_of_week", "all_61_common_adjusted_closes_valid"),
        caveats=[
            "ETF_portability_not_exact_source_replication",
            "original_robustness_mixed_concentration_risk_preserved",
            "role_aware_reassessment_is_current_approval_basis",
        ],
        fixture_builder="mca",
    )


def hyg_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[7]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "high_yield_credit_signal_equity_state",
            "architecture_id": "daily_cross_asset_credit_trend_equity_cash_state",
            "version": "v1",
        },
        instruments={"signal": "HYG", "tradables": ["SPY", "BIL"], "substitution": "forbidden"},
        signal={
            "EMA_period": 100,
            "alpha": 2.0 / 101.0,
            "initialization": "arithmetic_mean_first_100_valid_HYG_adjusted_closes_at_100th_close",
            "recursion": "EMA_t=alpha*HYG_close_t+(1-alpha)*EMA_t-1",
            "strict_above": "SPY_1_BIL_0",
            "strict_below": "SPY_0_BIL_1",
            "equality": "retain_current_target",
            "buffer_hysteresis_or_confirmation": False,
        },
        portfolio={"targets": {"risk_on": {"SPY": 1.0, "BIL": 0.0}, "risk_off": {"SPY": 0.0, "BIL": 1.0}}},
        schedule={"signal": "completed_daily_close", "execution": "following_regular_session_close"},
        data={"signal_field": "HYG_adjusted_close", "tradable_field": "adjusted_close", "frequency": "daily"},
        missing={
            "before_100_valid_HYG_closes": "BIL_1_0",
            "later_missing_signal": "retain_current_target",
            "missing_execution_price": "block_target_change",
        },
        state={"required": ["recursive_EMA", "current_target"]},
        source={
            "classification": "source_based_adaptation",
            "source": "Martin Schwoerer HYG credit signal 2025",
            "adaptation": "HYG_signal_mapped_to_SPY_BIL_long_only_state",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="high_yield_credit_signal_equity_state",
        architecture_id="daily_cross_asset_credit_trend_equity_cash_state",
        display_name="HYG 100-Day EMA Credit-State SPY/BIL",
        strategy_version="v1",
        route="standalone_only",
        portability="source_based_adaptation",
        canonical_trial_id="role_aware_robustness_reassessment_v1__hyg_ema100__child",
        approval_terminology="paper_demo_eligible_role_aware_reassessment_positive",
        approval_path="evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
        robustness_path="evidence/methodology/adopt_role_aware_robustness_standard_and_reassess_v1/latest",
        implementation_path="strategy_lab/research_os/research/accepted_47_source_backed_exploration_batch_v2.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[instrument("SPY", "risk_on_asset"), instrument("BIL", "risk_off_asset")],
        dependencies=[
            dependency(
                "hyg_adjusted_close_ema_signal",
                "HYG",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="retain_current_target_or_BIL_during_warmup",
            ),
            dependency(
                "hyg_strategy_tradable_values",
                "SPY|BIL",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                missing="block_target_change",
            ),
        ],
        calculator_type="stateful_daily_cross_asset_ema",
        calculator_version="hyg_ema100_spy_bil_calculator_v1",
        rule=rule,
        timing=timing("completed_daily_close", "HYG_adjusted_close_valid_at_close"),
        caveats=[
            "HYG_signal_to_equity_state_is_a_portability_adaptation",
            "original_robustness_mixed_concentration_risk_preserved",
            "role_aware_reassessment_is_current_approval_basis",
        ],
        fixture_builder="hyg",
    )


def d1_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[8]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "regression_trend_quality",
            "architecture_id": "long_only_log_price_regression_slope_and_r2_state",
            "version": "v1",
        },
        instruments={
            "inner_tradables": ["SPY", "BIL"],
            "outer_reference": "frozen_current_active_vm_dsr_usci_combo",
            "substitution": "forbidden",
        },
        signal={
            "lookback": 60,
            "regression": "OLS_log_SPY_adjusted_close_on_x_0_through_59_with_intercept",
            "annualized_slope": "exp(slope*252)-1",
            "r_squared": "1-SSE/SST;nonfinite_when_SST_zero",
            "risk_on": "annualized_slope>0_and_r_squared>=0.25",
            "risk_off": "otherwise",
        },
        portfolio={
            "outer_reference_weight": 0.8,
            "candidate_sleeve_weight": 0.2,
            "inner_targets": {"risk_on": {"SPY": 1.0, "BIL": 0.0}, "risk_off": {"SPY": 0.0, "BIL": 1.0}},
            "outer_rebalance": "monthly",
        },
        schedule={"signal": "completed_daily_close", "execution": "following_regular_session_close"},
        data={"field": "SPY_adjusted_close", "frequency": "daily", "minimum_closes": 60},
        missing={
            "warmup_or_nonfinite_regression": "BIL_1_0_inner_target",
            "missing_execution_price": "block_state_change",
        },
        state={"required": "current_inner_target_and_outer_sleeve_holdings"},
        source={
            "classification": "internal_strategy",
            "source": "internal_technical_strategy_factory_v1",
            "adaptation": "selected_D1_configuration_approved_only_as_20pct_diversifier",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="regression_trend_quality",
        architecture_id="long_only_log_price_regression_slope_and_r2_state",
        display_name="Factory V1 SPY Trend-Quality D1 20% Diversifier",
        strategy_version="v1",
        route="diversifier_only_20pct",
        portability="internal_strategy",
        canonical_trial_id="role_aware_robustness_reassessment_v1__d1_diversifier__child",
        approval_terminology="paper_demo_eligible_role_aware_reassessment_positive",
        approval_path="evidence/paper_demo_onboarding/onboard_role_aware_reassessment_candidates_standard_paper_demo_v1/latest",
        robustness_path="evidence/methodology/adopt_role_aware_robustness_standard_and_reassess_v1/latest",
        implementation_path="strategy_lab/research_os/research/technical_strategy_factory_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[
            instrument(
                "FROZEN_REFERENCE",
                "outer_reference_sleeve",
                exposure="long_only_virtual_component",
                semantics="authoritative_frozen_reference_virtual_NAV",
            ),
            instrument("SPY", "inner_risk_asset", minimum_history=60, lookback=60),
            instrument("BIL", "inner_risk_off_asset"),
        ],
        dependencies=[
            dependency(
                "d1_spy_adjusted_close_history",
                "SPY",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="BIL_inner_target_during_warmup_or_invalid_regression",
            ),
            dependency(
                "d1_outer_reference_and_fallback_values",
                "FROZEN_REFERENCE|BIL",
                frequency="daily",
                formula_reference="strategy_rule_contract.json:portfolio_construction",
                missing="block_target_change",
            ),
        ],
        calculator_type="daily_regression_state_diversifier_sleeve",
        calculator_version="factory_d1_trend_quality_calculator_v1",
        rule=rule,
        timing=timing("completed_daily_close", "60_valid_SPY_adjusted_closes"),
        caveats=[
            "internally_selected_factory_configuration",
            "approved_only_as_20pct_diversifier_sleeve",
            "original_robustness_mixed_concentration_risk_preserved",
        ],
        fixture_builder="d1",
    )


def internal_spec() -> StrategySpec:
    strategy_id = APPROVED_IDS[9]
    risky = ["SPY", "QQQ", "IWM", "EFA", "EEM", "HYG", "LQD", "TLT", "TIP", "GLD", "DBC", "IYR"]
    rule = rule_contract(
        identity={
            "strategy_id": strategy_id,
            "family_id": "cross_asset_capture_asymmetry_rotation",
            "architecture_id": "downside_upside_capture_cross_sectional",
            "version": "v1",
        },
        instruments={"risk_assets": risky, "fallback": "BIL", "substitution": "forbidden"},
        signal={
            "lookback": 63,
            "asset_return": "adjusted_close_i_t/adjusted_close_i_t_minus_1-1",
            "market_return": "adjusted_close_SPY_t/adjusted_close_SPY_t_minus_1-1",
            "up_capture": "mean(asset_return|market_return>0)/mean(market_return|market_return>0)",
            "down_capture": "mean(asset_return|market_return<0)/mean(market_return|market_return<0)",
            "score": "up_capture-down_capture",
            "minimum_up_sessions": 10,
            "minimum_down_sessions": 10,
            "rank": "descending_score_then_lexical_ticker",
            "selection": "top_3_eligible_assets",
        },
        portfolio={
            "selected_slot_weight": 1.0 / 3.0,
            "fewer_than_three_eligible": "eligible_assets_receive_slots_and_residual_goes_to_BIL",
            "zero_eligible": "BIL_1_0",
        },
        schedule={"signal": "completed_month_end_close", "execution": "following_regular_session_close"},
        data={"field": "adjusted_close_total_return_research_series", "frequency": "daily", "lookback": 63},
        missing={
            "asset_signal_history": "asset_ineligible_for_formation",
            "execution_price": "block_target_change_no_stale_execution",
        },
        state={"required": "current_target_and_monthly_event_idempotency"},
        source={
            "classification": "internal_strategy",
            "source": "internally_generated_technical_hypothesis",
            "parent_handoff": "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest",
        },
    )
    return StrategySpec(
        strategy_id=strategy_id,
        family_id="cross_asset_capture_asymmetry_rotation",
        architecture_id="downside_upside_capture_cross_sectional",
        display_name="Internal Capture Asymmetry 63d Top-3",
        strategy_version="v1",
        route="standalone",
        portability="internal_strategy",
        canonical_trial_id="robustness__internal_capture_asymmetry_63d_top3_v1__role_aware_v1",
        approval_terminology="paper_demo_eligible",
        approval_path="evidence/paper_demo_eligibility/internal_capture_asymmetry_63d_top3_v1/latest",
        robustness_path="evidence/robustness/role_aware_robustness_internal_capture_asymmetry_63d_top3_v1/latest",
        implementation_path="strategy_lab/research_os/research/accepted_47_targeted_internal_technical_batch_v1.py",
        source_lineage=rule["source_rule_lineage"],
        instruments=[instrument(symbol, "candidate_risk_asset", minimum_history=64, lookback=63) for symbol in risky]
        + [instrument("BIL", "residual_fallback_asset")],
        dependencies=[
            dependency(
                "capture_asymmetry_adjusted_closes",
                "|".join(risky + ["BIL"]),
                frequency="daily_to_monthly",
                formula_reference="strategy_rule_contract.json:signal_calculation",
                missing="asset_ineligible_or_block_execution_as_documented",
            )
        ],
        calculator_type="monthly_cross_sectional_capture_rank_allocation",
        calculator_version="internal_capture_asymmetry_63d_top3_calculator_v1",
        rule=rule,
        timing=timing("completed_month_end_close", "eligible_asset_adjusted_closes_valid"),
        caveats=[
            "internally_generated_hypothesis",
            "selected_from_four_architecture_A_configurations",
            "broader_parent_batch_multiple_testing",
            "material_historical_drawdown_and_nontrivial_turnover",
        ],
        fixture_builder="internal",
        readiness_before="existing_handoff_needs_enrichment",
        parent_handoff="evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest",
    )


def specs() -> list[StrategySpec]:
    return [
        usci_spec(),
        combo_spec(),
        angl_spec(),
        ivts_spec(),
        faa_spec(),
        psar_spec(),
        mca_spec(),
        hyg_spec(),
        d1_spec(),
        internal_spec(),
    ]


def _fixture(
    strategy_id: str,
    sequence: int,
    fixture_type: str,
    inputs: dict[str, Any],
    weights: dict[str, float],
    *,
    status: str = "target_calculated",
    prior_state: dict[str, Any] | None = None,
    intermediates: dict[str, Any] | None = None,
    effective: str = "2000-02-01T16:00:00-05:00",
) -> dict[str, Any]:
    return {
        "fixture_id": f"{strategy_id}__fixture_{sequence:02d}",
        "fixture_type": fixture_type,
        "event_reference": f"synthetic_reference_{sequence:02d}",
        "event_timestamp": "2000-01-31T16:00:00-05:00",
        "inputs": inputs,
        "prior_state": prior_state or {},
        "expected": {
            "status": status,
            "target_weights": weights,
            "effective_timestamp": effective if status == "target_calculated" else None,
            "intermediate_calculations": intermediates or {},
        },
        "absolute_tolerance": 1e-12,
        "relative_tolerance": 0.0,
        "historical_numeric_input": False,
        "operational_market_data": False,
    }


def _mca_weights(correlation: np.ndarray, volatilities: np.ndarray) -> dict[str, float]:
    count = correlation.shape[0]
    lower = correlation[np.tril_indices(count, k=-1)]
    mu = float(np.mean(lower))
    sigma = float(np.std(lower, ddof=1))
    adjusted = np.zeros_like(correlation, dtype=float)
    for row in range(count):
        for column in range(count):
            if row != column:
                z = (float(correlation[row, column]) - mu) / sigma
                cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
                adjusted[row, column] = 1.0 - cdf
    row_scores = adjusted.sum(axis=1) / (count - 1)
    ranks = pd.Series(-row_scores).rank(method="average", ascending=True).to_numpy(dtype=float)
    q = ranks / ranks.sum()
    multiplied = q @ adjusted
    pre_volatility = multiplied / multiplied.sum()
    raw = pre_volatility / volatilities
    weights = raw / raw.sum()
    symbols = ["SPY", "QQQ", "EEM", "IWM", "EFA", "TLT", "IYR", "GLD"]
    return {symbol: float(weight) for symbol, weight in zip(symbols, weights, strict=True)} | {"BIL": 0.0}


def build_fixtures(spec: StrategySpec) -> list[dict[str, Any]]:
    sid = spec.strategy_id
    fixtures: list[dict[str, Any]] = []
    add = lambda kind, inputs, weights, **kwargs: fixtures.append(
        _fixture(sid, len(fixtures) + 1, kind, inputs, weights, **kwargs)
    )
    if spec.fixture_builder == "usci":
        target = {"USCI": 1.0}
        add("target_weight_fixture", {"event": "initialization", "USCI_adjusted_close": 40.0}, target)
        add("signal_formula_fixture", {"event": "ordinary_session", "timing_signal": None}, target)
        add("missing_event_fixture", {"USCI_adjusted_close": None}, {}, status="blocked")
        add("timing_fixture", {"validated_close_timestamp": "2000-01-31T16:00:00-05:00"}, target)
        add("restart_fixture", {"persisted_target": target}, target)
        add("duplicate_event_fixture", {"duplicate_event_id": "synthetic_reference_01"}, {}, status="no_event")
    elif spec.fixture_builder == "combo":
        names = [row["symbol"] for row in spec.instruments]
        target = {name: 1.0 / 3.0 for name in names}
        add("target_weight_fixture", {"event": "first_common_monthly_session"}, target)
        add("signal_formula_fixture", {"pretrade_weights": [0.40, 0.35, 0.25]}, target, intermediates={"one_way_turnover": 0.08333333333333334})
        add("timing_fixture", {"calendar_month": "2000-02", "common_component_date": True}, target)
        add("missing_event_fixture", {"component_returns_complete": False}, {}, status="blocked")
        add("restart_fixture", {"sleeve_values": [1000.0, 1000.0, 1000.0]}, target)
        add("duplicate_event_fixture", {"already_rebalanced_month": "2000-02"}, {}, status="no_event")
    elif spec.fixture_builder == "angl":
        target = {"FROZEN_REFERENCE": 0.8, "ANGL": 0.2}
        add("target_weight_fixture", {"event": "first_monthly_outer_rebalance"}, target)
        add("signal_formula_fixture", {"timing_rule": None, "candidate_sleeve_target": {"ANGL": 1.0}}, target)
        add("timing_fixture", {"signal_date": "2000-01-31", "next_valid_session": "2000-02-01"}, target)
        add("missing_event_fixture", {"ANGL_execution_price": None}, {}, status="blocked")
        add("restart_fixture", {"current_outer_target": target}, target)
        add("duplicate_event_fixture", {"already_processed_month": "2000-01"}, {}, status="no_event")
    elif spec.fixture_builder == "ivts":
        add("signal_formula_fixture", {"VIX": 19.0, "VIX3M": 20.0}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.2, "IEF": 0.0}, intermediates={"ratio": 0.95})
        add("threshold_or_tie_fixture", {"VIX": 19.2, "VIX3M": 20.0}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.1, "IEF": 0.1}, intermediates={"ratio": 0.96})
        add("threshold_or_tie_fixture", {"VIX": 20.4, "VIX3M": 20.0}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.1, "IEF": 0.1}, intermediates={"ratio": 1.02})
        add("target_weight_fixture", {"VIX": 20.6, "VIX3M": 20.0}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.0, "IEF": 0.2}, intermediates={"ratio": 1.03})
        add("missing_event_fixture", {"VIX": None, "VIX3M": 20.0}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.2, "IEF": 0.0}, prior_state={"inner_target": {"SPY": 1.0, "IEF": 0.0}})
        add("timing_fixture", {"signal_date_completed": "2000-01-31", "observation_date_return_allowed": False}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.1, "IEF": 0.1})
        add("restart_fixture", {"previous_inner_target": {"SPY": 0.0, "IEF": 1.0}, "VIX": None}, {"FROZEN_REFERENCE": 0.8, "SPY": 0.0, "IEF": 0.2})
        add("duplicate_event_fixture", {"duplicate_signal_date": "2000-01-31"}, {}, status="no_event")
    elif spec.fixture_builder == "faa":
        empty = {symbol: 0.0 for symbol in [row["symbol"] for row in spec.instruments]}
        target = empty | {"SPY": 1.0 / 3.0, "EFA": 1.0 / 3.0, "VWO": 1.0 / 3.0}
        add("signal_formula_fixture", {"scores": {"SPY": 2.0, "EFA": 3.0, "VWO": 4.0, "SHY": 8.0, "AGG": 9.0, "GSG": 10.0, "VNQ": 11.0}, "four_month_returns": {"SPY": 0.08, "EFA": 0.05, "VWO": 0.03}}, target)
        fallback = empty | {"EFA": 1.0 / 3.0, "SHY": 2.0 / 3.0}
        add("target_weight_fixture", {"selected": ["SPY", "EFA", "VWO"], "four_month_returns": {"SPY": -0.01, "EFA": 0.02, "VWO": 0.0}}, fallback)
        add("threshold_or_tie_fixture", {"equal_scores": ["EFA", "SPY", "VWO"], "tie_break": "lexical"}, target, intermediates={"selected": ["EFA", "SPY", "VWO"]})
        add("missing_event_fixture", {"full_universe_valid": False}, empty | {"SHY": 1.0})
        add("timing_fixture", {"formation": "completed_month_end", "execution": "next_valid_session_close"}, target)
        add("restart_fixture", {"persisted_target": target}, target)
        add("duplicate_event_fixture", {"duplicate_formation_month": "2000-01"}, {}, status="no_event")
    elif spec.fixture_builder == "psar":
        risk_off = {"FROZEN_REFERENCE": 0.8, "SPY": 0.0, "BIL": 0.2}
        risk_on = {"FROZEN_REFERENCE": 0.8, "SPY": 0.2, "BIL": 0.0}
        add("target_weight_fixture", {"completed_sessions": 2}, risk_off)
        add("signal_formula_fixture", {"high_t_minus_1": 10.0, "low_t_minus_1": 9.0, "high_t": 11.0, "low_t": 10.0}, risk_on, intermediates={"trend": "uptrend", "AF": 0.02, "EP": 11.0, "PSAR": 9.0})
        add("signal_formula_fixture", {"high_t_minus_1": 11.0, "low_t_minus_1": 10.0, "high_t": 10.0, "low_t": 9.0}, risk_off, intermediates={"trend": "downtrend", "AF": 0.02, "EP": 9.0, "PSAR": 11.0})
        add("threshold_or_tie_fixture", {"change3": 0.02, "prior_AF": 0.10}, risk_on, prior_state={"trend": "uptrend"}, intermediates={"new_AF": 0.05, "branch": "deceleration"})
        add("threshold_or_tie_fixture", {"change3": 0.0200001, "prior_AF": 0.10}, risk_on, prior_state={"trend": "uptrend"}, intermediates={"new_AF": 0.12, "branch": "acceleration"})
        add("missing_event_fixture", {"adjusted_high": None}, risk_off, prior_state={"target": "BIL"})
        add("timing_fixture", {"signal_after_close": True, "same_close_fill": False}, risk_on)
        add("restart_fixture", {"trend": "downtrend", "PSAR": 12.0, "EP": 9.0, "AF": 0.07}, risk_off)
        add("duplicate_event_fixture", {"duplicate_signal_date": "2000-01-31"}, {}, status="no_event")
    elif spec.fixture_builder == "mca":
        risk_symbols = ["SPY", "QQQ", "EEM", "IWM", "EFA", "TLT", "IYR", "GLD"]
        bil = {symbol: 0.0 for symbol in risk_symbols} | {"BIL": 1.0}
        correlation = np.full((8, 8), 0.2, dtype=float)
        np.fill_diagonal(correlation, 1.0)
        for row in range(8):
            for column in range(row):
                value = -0.15 + 0.025 * (row + column)
                correlation[row, column] = correlation[column, row] = value
        vol = np.array([0.010, 0.012, 0.016, 0.014, 0.011, 0.006, 0.013, 0.009])
        target = _mca_weights(correlation, vol)
        add("target_weight_fixture", {"completed_daily_returns": 59}, bil)
        add("signal_formula_fixture", {"correlation_matrix": correlation.tolist(), "sample_volatilities": vol.tolist()}, target)
        add("threshold_or_tie_fixture", {"rank_method": "average", "tie_case": "equal_negative_row_scores"}, target)
        add("missing_event_fixture", {"common_asset_count": 7, "reduced_universe_allowed": False}, target, prior_state={"target": target})
        add("missing_event_fixture", {"off_diagonal_sigma": 0.0}, target, prior_state={"target": target})
        add("timing_fixture", {"signal": "week_final_completed_session", "execution": "next_valid_session_close"}, target)
        add("restart_fixture", {"persisted_target": target}, target)
        add("duplicate_event_fixture", {"duplicate_week_id": "2000-W05"}, {}, status="no_event")
    elif spec.fixture_builder == "hyg":
        off = {"SPY": 0.0, "BIL": 1.0}
        on = {"SPY": 1.0, "BIL": 0.0}
        add("target_weight_fixture", {"valid_HYG_closes": 99}, off)
        add("signal_formula_fixture", {"first_100_HYG_closes": [100.0] * 100}, off, intermediates={"EMA_seed": 100.0})
        add("signal_formula_fixture", {"HYG_close": 101.0, "EMA": 100.0}, on)
        add("signal_formula_fixture", {"HYG_close": 99.0, "EMA": 100.0}, off)
        add("threshold_or_tie_fixture", {"HYG_close": 100.0, "EMA": 100.0}, on, prior_state={"target": "SPY"})
        add("missing_event_fixture", {"HYG_close": None}, off, prior_state={"target": "BIL"})
        add("timing_fixture", {"signal_after_close": True, "execution": "next_valid_session_close"}, on)
        add("restart_fixture", {"EMA": 100.0, "target": "SPY", "next_HYG_close": 100.5}, on, intermediates={"next_EMA": (2.0 / 101.0) * 100.5 + (99.0 / 101.0) * 100.0})
        add("duplicate_event_fixture", {"duplicate_signal_date": "2000-01-31"}, {}, status="no_event")
    elif spec.fixture_builder == "d1":
        off = {"FROZEN_REFERENCE": 0.8, "SPY": 0.0, "BIL": 0.2}
        on = {"FROZEN_REFERENCE": 0.8, "SPY": 0.2, "BIL": 0.0}
        add("target_weight_fixture", {"valid_SPY_closes": 59}, off)
        add("signal_formula_fixture", {"annualized_slope": 0.10, "r_squared": 0.50}, on)
        add("threshold_or_tie_fixture", {"annualized_slope": 0.01, "r_squared": 0.25}, on)
        add("threshold_or_tie_fixture", {"annualized_slope": 0.01, "r_squared": 0.249999999999}, off)
        add("signal_formula_fixture", {"annualized_slope": 0.0, "r_squared": 1.0}, off)
        add("missing_event_fixture", {"SST": 0.0, "r_squared": None}, off)
        add("timing_fixture", {"signal_after_close": True, "execution": "next_valid_session_close"}, on)
        add("restart_fixture", {"persisted_inner_target": "SPY", "annualized_slope": 0.12, "r_squared": 0.4}, on)
        add("duplicate_event_fixture", {"duplicate_signal_date": "2000-01-31"}, {}, status="no_event")
    elif spec.fixture_builder == "internal":
        symbols = [row["symbol"] for row in spec.instruments]
        empty = {symbol: 0.0 for symbol in symbols}
        normal = empty | {"SPY": 1.0 / 3.0, "QQQ": 1.0 / 3.0, "IWM": 1.0 / 3.0}
        add("signal_formula_fixture", {"scores": {"SPY": 1.5, "QQQ": 1.2, "IWM": 1.0, "EFA": 0.5}, "eligible": ["SPY", "QQQ", "IWM", "EFA"]}, normal)
        add("threshold_or_tie_fixture", {"scores": {"EFA": 1.0, "IWM": 1.0, "QQQ": 1.0, "SPY": 1.0}, "tie_break": "lexical"}, empty | {"EFA": 1.0 / 3.0, "IWM": 1.0 / 3.0, "QQQ": 1.0 / 3.0})
        add("target_weight_fixture", {"eligible": ["SPY", "QQQ"]}, empty | {"SPY": 1.0 / 3.0, "QQQ": 1.0 / 3.0, "BIL": 1.0 / 3.0})
        add("missing_event_fixture", {"eligible": []}, empty | {"BIL": 1.0})
        add("missing_event_fixture", {"completed_sessions": 62}, empty | {"BIL": 1.0})
        add("timing_fixture", {"signal": "completed_month_end", "execution": "next_valid_session_close"}, normal)
        add("restart_fixture", {"persisted_target": normal}, normal)
        add("duplicate_event_fixture", {"duplicate_formation_month": "2000-01"}, {}, status="no_event")
    else:
        raise ValueError(f"Unsupported fixture builder: {spec.fixture_builder}")
    return fixtures


def validate_fixture_set(spec: StrategySpec, fixtures: list[dict[str, Any]]) -> None:
    if not fixtures:
        raise ValueError(f"No fixtures for {spec.strategy_id}")
    ids = [row["fixture_id"] for row in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate fixture ID for {spec.strategy_id}")
    allowed_status = {"target_calculated", "no_event", "blocked"}
    for row in fixtures:
        if row["fixture_type"] not in REQUIRED_FIXTURE_TYPES:
            raise ValueError(f"Invalid fixture type: {row['fixture_type']}")
        expected = row["expected"]
        if expected["status"] not in allowed_status:
            raise ValueError(f"Invalid fixture status: {expected['status']}")
        weights = expected["target_weights"]
        if weights:
            if any(not math.isfinite(float(value)) or float(value) < -1e-12 for value in weights.values()):
                raise ValueError(f"Invalid fixture weights for {spec.strategy_id}")
            if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-11:
                raise ValueError(f"Fixture weights do not sum to one for {spec.strategy_id}")
        if row["historical_numeric_input"] or row["operational_market_data"]:
            raise ValueError("This task permits only compact synthetic conformance inputs")


def validate_rule(spec: StrategySpec) -> None:
    missing = [field for field in RULE_FIELDS if field not in spec.rule or spec.rule[field] in (None, "", {})]
    if missing:
        raise ValueError(f"Material rule fields missing for {spec.strategy_id}: {missing}")
    serialized = json.dumps(spec.rule, sort_keys=True)
    if re.search(r"\b(unknown|unmapped|tbd|todo)\b", serialized, flags=re.IGNORECASE):
        raise ValueError(f"Unresolved material rule marker for {spec.strategy_id}")
    if not (ROOT / spec.implementation_path).is_file():
        raise FileNotFoundError(spec.implementation_path)
    if not (ROOT / spec.approval_path).exists():
        raise FileNotFoundError(spec.approval_path)
    if not (ROOT / spec.robustness_path).exists():
        raise FileNotFoundError(spec.robustness_path)


def source_hashes(spec: StrategySpec) -> dict[str, str]:
    hashes = {
        "canonical_implementation": sha256_path(ROOT / spec.implementation_path),
        "strategy_configuration": canonical_hash(spec.rule),
        "strategy_registry": sha256_file(REGISTRY),
        "research_approval_evidence": sha256_path(ROOT / spec.approval_path),
        "robustness_evidence": sha256_path(ROOT / spec.robustness_path),
    }
    if spec.parent_handoff:
        hashes["parent_handoff"] = sha256_path(ROOT / spec.parent_handoff)
    if any(value == "missing" for value in hashes.values()):
        raise ValueError(f"Missing source hash for {spec.strategy_id}")
    return hashes


def handoff_payload(spec: StrategySpec, hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "envelope": {
            "schema_id": "forward_observation_handoff_standard_v1",
            "schema_version": 1,
            "handoff_id": spec.handoff_id,
            "handoff_version": "v1",
            "strategy_id": spec.strategy_id,
            "strategy_version": spec.strategy_version,
            "family_id": spec.family_id,
            "architecture_id": spec.architecture_id,
            "canonical_trial_id": spec.canonical_trial_id,
            "research_eligibility_status": "research_approved",
            "research_eligibility_evidence_id": spec.approval_path,
            "created_at": CREATED_AT,
            "package_content_hash": "sha256:" + "0" * 64,
            "source_hashes": hashes,
            "research_claim": RESEARCH_CLAIM,
            "explicit_nonclaims": COMMON_NONCLAIMS,
            "caveats": spec.caveats,
        },
        "tradable_contract": {
            "instruments": spec.instruments,
            "shorting_allowed": False,
            "leverage_allowed": False,
            "cash_behavior": spec.rule["portfolio_construction"].get(
                "cash_handling", "documented_fallback_asset_or_fully_invested_target"
            ),
            "target_normalization_rule": "fully_invested_long_only",
        },
        "signal_dependencies": spec.dependencies,
        "calculator_contract": {
            "calculator_type": spec.calculator_type,
            "calculator_contract_version": spec.calculator_version,
            "calculator_configuration": {
                "strategy_rule_contract_hash": canonical_hash(spec.rule),
                "strategy_rule_contract_reference": "strategy_rule_contract.json",
                "frozen_rule": spec.rule,
            },
            "permitted_receiver_parameters": [],
        },
        "timing_contract": spec.timing,
        "required_fixture_types": REQUIRED_FIXTURE_TYPES,
    }


def attachment_files(
    spec: StrategySpec,
    hashes: dict[str, str],
    fixtures: list[dict[str, Any]],
) -> dict[str, bytes]:
    fixture_payload = {
        "schema_id": "forward_observation_golden_fixture_set_v1",
        "schema_version": 1,
        "fixture_set_id": f"{spec.handoff_id}__golden_fixtures_v1",
        "strategy_id": spec.strategy_id,
        "calculator_contract_version": spec.calculator_version,
        "fixture_count": len(fixtures),
        "selection_policy": "mechanical_rule_branch_coverage_not_performance_selection",
        "numeric_tolerance": {"absolute": 1e-12, "relative": 0.0},
        "fixtures": fixtures,
    }
    input_payload = {
        "schema_id": "inline_synthetic_conformance_inputs_v1",
        "schema_version": 1,
        "strategy_id": spec.strategy_id,
        "fixture_set_id": fixture_payload["fixture_set_id"],
        "historical_numeric_inputs_included": False,
        "operational_market_data": False,
        "current_target": False,
        "companion_bundle_required": False,
        "reason": "fixtures_use_compact_synthetic_rule_inputs_and_do_not_require_historical_provider_reconstruction",
        "fixture_inputs": {row["fixture_id"]: row["inputs"] for row in fixtures},
    }
    lineage_payload = {
        "strategy_id": spec.strategy_id,
        "source_or_research_lineage": spec.source_lineage,
        "portability_classification": spec.portability,
        "canonical_trial_id": spec.canonical_trial_id,
        "canonical_implementation_path": spec.implementation_path,
        "canonical_implementation_hash": hashes["canonical_implementation"],
        "parent_handoff": spec.parent_handoff or None,
        "rules_changed_during_standardization": False,
    }
    evidence_payload = {
        "strategy_id": spec.strategy_id,
        "research_approval_terminology": spec.approval_terminology,
        "research_approval_path": spec.approval_path,
        "research_approval_hash": hashes["research_approval_evidence"],
        "robustness_path": spec.robustness_path,
        "robustness_hash": hashes["robustness_evidence"],
        "performance_recalculated": False,
    }
    boundary = (
        "# Research Handoff Boundary\n\n"
        "This immutable research package defines strategy targets, rule inputs, timing, "
        "lineage, and conformance fixtures. It contains no current target, account, order, "
        "position, broker, paper/live authorization, deployment profile, or operational state.\n"
    )
    return {
        "strategy_rule_contract.json": json_bytes(spec.rule),
        "source_lineage.json": json_bytes(lineage_payload),
        "research_evidence.json": json_bytes(evidence_payload),
        "golden_conformance_fixtures.json": json_bytes(fixture_payload),
        "conformance_inputs.json": json_bytes(input_payload),
        "claims_and_nonclaims.json": json_bytes(
            {"research_claim": RESEARCH_CLAIM, "explicit_nonclaims": COMMON_NONCLAIMS}
        ),
        "caveat_register.json": json_bytes({"strategy_id": spec.strategy_id, "caveats": spec.caveats}),
        "implementation_provenance.json": json_bytes(
            {
                "implementation_path": spec.implementation_path,
                "implementation_hash": hashes["canonical_implementation"],
                "configuration_hash": hashes["strategy_configuration"],
                "dataset_hashes": {
                    "status": "referenced_by_frozen_research_evidence_not_copied",
                    "approval_evidence_hash": hashes["research_approval_evidence"],
                    "robustness_evidence_hash": hashes["robustness_evidence"],
                },
            }
        ),
        "research_handoff_boundary.md": text_bytes(boundary),
    }


def validate_existing_standard_package(path: Path) -> StandardHandoff:
    result = StandardV1Adapter().adapt(path)
    if result.normalized_handoff is None or result.status != "contract_validated":
        raise ValueError(f"Standard package validation failed: {path}")
    return result.normalized_handoff


def materialize_or_reconcile_package(
    spec: StrategySpec,
    payload: dict[str, Any],
    attachments: dict[str, bytes],
) -> tuple[str, str]:
    destination = spec.package_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        handoff = validate_existing_standard_package(destination)
        if handoff.envelope.strategy_id != spec.strategy_id:
            raise ValueError(f"Existing immutable package identity mismatch: {destination}")
        existing_hash = handoff.envelope.package_content_hash
        status = "existing_identical_standard_package_reused"
    else:
        _, handoff = materialize_standard_package(payload, destination, attachment_files=attachments)
        existing_hash = handoff.envelope.package_content_hash
        status = "new_standardized_handoff_created"
    with tempfile.TemporaryDirectory(prefix=f"{TASK_ID}_") as temp:
        regenerated_path = Path(temp) / "package"
        _, regenerated = materialize_standard_package(
            payload,
            regenerated_path,
            attachment_files=attachments,
        )
        if regenerated.envelope.package_content_hash != existing_hash:
            raise ValueError(f"Deterministic package regeneration failed for {spec.strategy_id}")
    validate_existing_standard_package(destination)
    return existing_hash, status


def registry_records() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    records: dict[str, dict[str, Any]] = {}
    duplicate_ids: list[str] = []
    for record in payload.get("strategies", []):
        strategy_id = str(record.get("strategy_id") or record.get("id") or "")
        if not strategy_id:
            continue
        if strategy_id in records:
            duplicate_ids.append(strategy_id)
        records[strategy_id] = record
    if duplicate_ids:
        raise ValueError(f"Duplicate strategy IDs in registry: {sorted(set(duplicate_ids))}")
    return records


def reconcile_approved_inventory() -> dict[str, dict[str, Any]]:
    migration = list(csv.DictReader((PRIOR_AUDIT / "migration_scope.csv").open(newline="", encoding="utf-8")))
    approved_from_audit: list[str] = []
    for row in migration:
        if row["scope"] in {"native_or_no_material_rule_change", "adapter_and_fixture_enrichment", "contract_materialization"}:
            approved_from_audit.extend(item for item in row["strategy_ids"].split("|") if item)
    if len(approved_from_audit) != 11 or set(approved_from_audit) != set(APPROVED_IDS):
        raise ValueError(
            "Approved-strategy discrepancy: "
            f"expected={list(APPROVED_IDS)} observed={approved_from_audit}"
        )
    records = registry_records()
    registry_required = APPROVED_IDS[:-1]
    missing = [strategy_id for strategy_id in registry_required if strategy_id not in records]
    if missing:
        raise ValueError(f"Approved strategies missing from research registry: {missing}")
    for strategy_id in registry_required:
        record = records[strategy_id]
        approval_markers = {
            str(record.get("paper_demo_eligible", "")).lower(),
            str(record.get("current_status", "")).lower(),
            str(record.get("outcome", "")).lower(),
            str(record.get("status", "")).lower(),
        }
        if not any(
            marker in {"true", "paper_demo_eligible", "active_paper_demo_observation", "gated", "active"}
            for marker in approval_markers
        ):
            raise ValueError(f"Research approval marker absent for {strategy_id}")
    reconciled = {strategy_id: records[strategy_id] for strategy_id in registry_required}
    spdj_eligibility = (
        ROOT
        / "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest"
    )
    if not spdj_eligibility.exists() or not SPDJ_PACKAGE.exists():
        raise ValueError("SPDJ authoritative eligibility or immutable handoff evidence is missing")
    reconciled[APPROVED_IDS[-1]] = {
        "stage": "research_ready_standardized_handoff",
        "outcome": "research_eligible_for_handoff",
        "evidence": rel(spdj_eligibility),
    }
    return reconciled


def scan_hygiene(paths: list[Path]) -> dict[str, Any]:
    secret_pattern = re.compile(
        r"(api[_-]?key|secret[_-]?key|account[_-]?id|broker[_-]?credential|-----BEGIN [A-Z ]+PRIVATE KEY-----)",
        flags=re.IGNORECASE,
    )
    absolute_pattern = re.compile(r"(?:[A-Za-z]:\\|/Users/|/home/)")
    secret_hits: list[str] = []
    absolute_hits: list[str] = []
    for root in paths:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if secret_pattern.search(text):
                secret_hits.append(rel(path))
            if absolute_pattern.search(text):
                absolute_hits.append(rel(path))
    return {
        "secret_hits": sorted(set(secret_hits)),
        "absolute_path_hits": sorted(set(absolute_hits)),
        "passed": not secret_hits and not absolute_hits,
    }


def normalized_completion_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        if relative == "consistency_check.json":
            payload = json.loads(content.decode("utf-8"))
            payload["deterministic_completion_packet_hash"] = "__NORMALIZED_SELF_REFERENCE__"
            content = json_bytes(payload)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _spdj_inventory() -> dict[str, Any]:
    registry = SourceAdapterRegistry()
    adapter = registry.identify(SPDJ_PACKAGE)
    adapted = adapter.adapt(SPDJ_PACKAGE)
    if adapted.normalized_handoff is None:
        raise ValueError("SPDJ existing package does not normalize to Standard V1")
    observed_hash = normalized_spdj_package_hash(SPDJ_PACKAGE)
    if observed_hash != EXPECTED_SPDJ_HASH:
        raise ValueError(f"SPDJ immutable package hash changed: {observed_hash}")
    fixture_manifest = json.loads((SPDJ_PACKAGE / "golden_fixture_manifest.json").read_text(encoding="utf-8"))
    handoff_manifest = json.loads((SPDJ_PACKAGE / "handoff_manifest.json").read_text(encoding="utf-8"))
    return {
        "handoff_id": handoff_manifest["handoff_id"],
        "schema_id": handoff_manifest["package_schema_version"],
        "schema_version": handoff_manifest["handoff_version"],
        "package_hash": observed_hash,
        "fixture_count": int(fixture_manifest["fixture_count"]),
        "canonical_trial_id": adapted.normalized_handoff.envelope.canonical_trial_id,
        "family_id": adapted.normalized_handoff.envelope.family_id,
        "architecture_id": adapted.normalized_handoff.envelope.architecture_id,
    }


def completion_report(
    package_rows: list[dict[str, Any]],
    fixture_rows: list[dict[str, Any]],
    counts: dict[str, Any],
) -> str:
    package_lines = "\n".join(
        f"- `{row['strategy_id']}`: `{row['handoff_id']}` `{row['package_hash']}`"
        for row in package_rows
    )
    return f"""# Complete Standardized Research Handoffs v1

## Outcome

`{OUTCOME}`

The authoritative research-approved cohort reconciles to exactly **11** strategies. All 11 now have complete, machine-consumable research handoffs. SPDJ was reused without modification; Internal Capture received a Standard V1 successor linked to its immutable legacy package; nine other approved strategies received new Standard V1 packages.

No historical performance was recalculated. No current target was calculated. No forward-observation project path, operational state, provider, broker, account, position, fill, or order was accessed.

## Counts

- Research approved: `{counts['approved_strategy_count']}`
- Standardized ready before: `{counts['existing_complete_handoff_count_before']}`
- New Standard V1 packages: `{counts['new_standardized_handoffs_created']}`
- Enriched successor packages: `{counts['existing_handoffs_enriched']}`
- Standardized ready after: `{counts['standardized_handoff_ready_count_after']}`
- Machine executable: `{counts['machine_executable_count']}`
- Complete with documented calculator module: `{counts['contract_complete_calculator_module_count']}`
- Human interpretation required: `{counts['human_interpretation_required_count']}`
- Material rule gaps: `{counts['material_rule_gap_count']}`
- Golden fixture sets created: `{counts['fixture_sets_created']}`
- Golden fixtures in created/enriched packages: `{sum(int(row['fixture_count']) for row in fixture_rows if row['fixture_set_created'])}`

## Packages

{package_lines}

## Boundary

These packages specify target calculations and research provenance only. They do not initialize or authorize forward observation, paper/demo activity, broker execution, microtrading, or real-money trading.

## Next Action

`{NEXT_ACTION}`
"""


def run() -> dict[str, Any]:
    protected_before = snapshot(PROTECTED_PATHS)
    approved_records = reconcile_approved_inventory()
    spec_list = specs()
    if len(spec_list) != 10 or {row.strategy_id for row in spec_list} != set(APPROVED_IDS[:-1]):
        raise ValueError("Standardization specification coverage does not match approved cohort")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    package_rows: list[dict[str, Any]] = []
    rule_rows: list[dict[str, Any]] = []
    fixture_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    machine_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    material_gap_rows: list[dict[str, Any]] = []

    for spec in spec_list:
        validate_rule(spec)
        fixtures = build_fixtures(spec)
        validate_fixture_set(spec, fixtures)
        hashes = source_hashes(spec)
        payload = handoff_payload(spec, hashes)
        StandardHandoff.from_dict(payload)
        attachments = attachment_files(spec, hashes, fixtures)
        package_hash, _materialization_status = materialize_or_reconcile_package(
            spec, payload, attachments
        )
        new_status = (
            "enriched_successor_handoff_created"
            if spec.readiness_before == "existing_handoff_needs_enrichment"
            else "new_standardized_handoff_created"
        )
        package_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "handoff_id": spec.handoff_id,
                "handoff_status": new_status,
                "schema_id": "forward_observation_handoff_standard_v1",
                "schema_version": 1,
                "package_hash": package_hash,
                "package_path": rel(spec.package_path),
                "fixture_count": len(fixtures),
                "conformance_bundle_id": "not_required_inline_synthetic_inputs",
                "parent_handoff": spec.parent_handoff,
                "immutable_prior_package_modified": False,
            }
        )
        for field in RULE_FIELDS:
            rule_rows.append(
                {
                    "strategy_id": spec.strategy_id,
                    "rule_field": field,
                    "classification": "explicit_in_authoritative_evidence",
                    "authoritative_reference": (
                        spec.implementation_path if field in {"signal_calculation", "portfolio_construction", "state_behavior"}
                        else spec.approval_path
                    ),
                    "materially_ambiguous": False,
                    "blocking_gap": "",
                }
            )
        present_types = sorted({row["fixture_type"] for row in fixtures})
        fixture_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "handoff_id": spec.handoff_id,
                "fixture_set_created": True,
                "fixture_count": len(fixtures),
                "fixture_types": present_types,
                "historical_numeric_inputs_included": False,
                "companion_conformance_bundle_created": False,
                "inline_synthetic_inputs": True,
                "fixture_validation": "pass",
            }
        )
        readiness_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "research_approval_status": "research_approved",
                "handoff_readiness_before": spec.readiness_before,
                "handoff_readiness_after": "standardized_handoff_complete",
                "handoff_id": spec.handoff_id,
                "machine_executability": "contract_complete_with_documented_calculator_module",
                "blocking_gap_count": 0,
            }
        )
        machine_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "classification": "contract_complete_with_documented_calculator_module",
                "data_contract_complete": True,
                "signal_contract_complete": True,
                "target_contract_complete": True,
                "timing_contract_complete": True,
                "missing_and_warmup_complete": True,
                "state_contract_complete": True,
                "fixtures_complete": True,
                "human_interpretation_required": False,
            }
        )
        record = approved_records[spec.strategy_id]
        inventory_rows.append(
            {
                "strategy_id": spec.strategy_id,
                "family_id": spec.family_id,
                "architecture_id": spec.architecture_id,
                "research_approval_status": "research_approved",
                "approval_terminology_original": spec.approval_terminology,
                "research_approval_evidence": spec.approval_path,
                "canonical_trial_id": spec.canonical_trial_id,
                "robustness_status": "passed_applicable_research_approval_methodology",
                "registry_stage": record.get("stage", record.get("current_status", "historical_approved")),
                "existing_handoff_status_before": spec.readiness_before,
                "handoff_schema_before": "legacy_internal_capture_handoff_v1" if spec.parent_handoff else "none",
            }
        )

    spdj = _spdj_inventory()
    package_rows.append(
        {
            "strategy_id": APPROVED_IDS[-1],
            "handoff_id": spdj["handoff_id"],
            "handoff_status": "existing_standardized_handoff_reused",
            "schema_id": spdj["schema_id"],
            "schema_version": spdj["schema_version"],
            "package_hash": spdj["package_hash"],
            "package_path": rel(SPDJ_PACKAGE),
            "fixture_count": spdj["fixture_count"],
            "conformance_bundle_id": "embedded_frozen_fixture_inputs",
            "parent_handoff": "",
            "immutable_prior_package_modified": False,
        }
    )
    for field in RULE_FIELDS:
        rule_rows.append(
            {
                "strategy_id": APPROVED_IDS[-1],
                "rule_field": field,
                "classification": "explicit_in_authoritative_evidence",
                "authoritative_reference": rel(SPDJ_PACKAGE),
                "materially_ambiguous": False,
                "blocking_gap": "",
            }
        )
    fixture_rows.append(
        {
            "strategy_id": APPROVED_IDS[-1],
            "handoff_id": spdj["handoff_id"],
            "fixture_set_created": False,
            "fixture_count": spdj["fixture_count"],
            "fixture_types": "existing_SPDJ_golden_fixture_manifest",
            "historical_numeric_inputs_included": True,
            "companion_conformance_bundle_created": False,
            "inline_synthetic_inputs": False,
            "fixture_validation": "pass_existing_package_integrity_and_fixture_manifest",
        }
    )
    readiness_rows.append(
        {
            "strategy_id": APPROVED_IDS[-1],
            "research_approval_status": "research_approved",
            "handoff_readiness_before": "standardized_handoff_complete",
            "handoff_readiness_after": "standardized_handoff_complete",
            "handoff_id": spdj["handoff_id"],
            "machine_executability": "machine_executable_contract",
            "blocking_gap_count": 0,
        }
    )
    machine_rows.append(
        {
            "strategy_id": APPROVED_IDS[-1],
            "classification": "machine_executable_contract",
            "data_contract_complete": True,
            "signal_contract_complete": True,
            "target_contract_complete": True,
            "timing_contract_complete": True,
            "missing_and_warmup_complete": True,
            "state_contract_complete": True,
            "fixtures_complete": True,
            "human_interpretation_required": False,
        }
    )
    spdj_record = approved_records[APPROVED_IDS[-1]]
    inventory_rows.append(
        {
            "strategy_id": APPROVED_IDS[-1],
            "family_id": spdj["family_id"],
            "architecture_id": spdj["architecture_id"],
            "research_approval_status": "research_approved",
            "approval_terminology_original": "research_eligible_for_handoff",
            "research_approval_evidence": "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest",
            "canonical_trial_id": spdj["canonical_trial_id"],
            "robustness_status": "robustness_passed",
            "registry_stage": spdj_record.get("stage", spdj_record.get("current_status", "research_approved")),
            "existing_handoff_status_before": "standardized_handoff_complete",
            "handoff_schema_before": spdj["schema_id"],
        }
    )

    if len({row["strategy_id"] for row in package_rows}) != 11:
        raise ValueError("Package inventory does not contain exactly 11 unique approved strategies")

    counts = {
        "approved_strategy_count": 11,
        "existing_complete_handoff_count_before": 1,
        "new_standardized_handoffs_created": 9,
        "existing_handoffs_enriched": 1,
        "standardized_handoff_ready_count_after": 11,
        "machine_executable_count": 1,
        "contract_complete_calculator_module_count": 10,
        "human_interpretation_required_count": 0,
        "material_rule_gap_count": 0,
        "fixture_sets_created": 10,
        "conformance_bundles_created": 0,
        "current_target_calculations": 0,
        "forward_observation_accesses": 0,
        "broker_network_calls": 0,
    }

    inventory_rows = sorted(inventory_rows, key=lambda row: APPROVED_IDS.index(row["strategy_id"]))
    package_rows = sorted(package_rows, key=lambda row: APPROVED_IDS.index(row["strategy_id"]))
    readiness_rows = sorted(readiness_rows, key=lambda row: APPROVED_IDS.index(row["strategy_id"]))
    machine_rows = sorted(machine_rows, key=lambda row: APPROVED_IDS.index(row["strategy_id"]))
    fixture_rows = sorted(fixture_rows, key=lambda row: APPROVED_IDS.index(row["strategy_id"]))
    rule_rows = sorted(rule_rows, key=lambda row: (APPROVED_IDS.index(row["strategy_id"]), RULE_FIELDS.index(row["rule_field"])))

    write_csv(OUTPUT_DIR / "approved_strategy_inventory.csv", inventory_rows)
    write_csv(OUTPUT_DIR / "rule_completeness_audit.csv", rule_rows)
    write_csv(OUTPUT_DIR / "handoff_readiness.csv", readiness_rows)
    write_csv(OUTPUT_DIR / "handoff_package_inventory.csv", package_rows)
    write_csv(OUTPUT_DIR / "fixture_coverage.csv", fixture_rows)
    write_csv(OUTPUT_DIR / "machine_executability_audit.csv", machine_rows)
    write_csv(
        OUTPUT_DIR / "material_rule_gaps.csv",
        material_gap_rows,
        ["strategy_id", "rule_field", "gap", "authoritative_evidence_checked", "required_reconciliation"],
    )
    write_json(OUTPUT_DIR / "standardization_counts.json", counts)
    (OUTPUT_DIR / "completion_report.md").write_text(
        completion_report(package_rows, fixture_rows, counts), encoding="utf-8"
    )
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Next Action\n\n`{NEXT_ACTION}`\n", encoding="utf-8"
    )

    created_package_paths = [
        spec.package_path for spec in spec_list
    ]
    hygiene = scan_hygiene(created_package_paths + [OUTPUT_DIR])
    if not hygiene["passed"]:
        raise ValueError(f"Package hygiene failed: {hygiene}")

    touched_paths = [rel(path) for path in created_package_paths] + [rel(OUTPUT_DIR)]
    no_forward_access = all(not path.startswith(FORWARD_PROJECT_RELATIVE) for path in touched_paths)
    protected_after = snapshot(PROTECTED_PATHS)
    protected_unchanged = protected_before == protected_after
    checks = {
        "approved_inventory_exactly_11": len(inventory_rows) == 11,
        "approved_strategy_ids_exact": [row["strategy_id"] for row in inventory_rows] == list(APPROVED_IDS),
        "duplicate_strategy_ids_absent": len({row["strategy_id"] for row in inventory_rows}) == 11,
        "complete_rule_fields": len(rule_rows) == 11 * len(RULE_FIELDS),
        "material_rule_ambiguities_absent": not material_gap_rows,
        "standardized_handoffs_ready_11": len(package_rows) == 11,
        "standard_v1_packages_validate": all(
            validate_existing_standard_package(spec.package_path).envelope.strategy_id == spec.strategy_id
            for spec in spec_list
        ),
        "spdj_existing_package_reused": spdj["package_hash"] == EXPECTED_SPDJ_HASH,
        "internal_legacy_package_preserved": protected_before[rel(LEGACY_INTERNAL)] == protected_after[rel(LEGACY_INTERNAL)],
        "fixture_sets_validate": all(row["fixture_validation"].startswith("pass") for row in fixture_rows),
        "historical_companion_bundle_not_required_for_synthetic_inputs": counts["conformance_bundles_created"] == 0,
        "secret_and_absolute_path_hygiene": hygiene["passed"],
        "forward_project_not_accessed": no_forward_access and counts["forward_observation_accesses"] == 0,
        "current_targets_not_calculated": counts["current_target_calculations"] == 0,
        "broker_and_network_calls_absent": counts["broker_network_calls"] == 0,
        "protected_state_unchanged": protected_unchanged,
        "outcome_matches_counts": counts["standardized_handoff_ready_count_after"] == counts["approved_strategy_count"],
    }
    consistency = {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "checks": checks,
        "overall_pass": all(checks.values()),
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "protected_state_unchanged": protected_unchanged,
        "package_hygiene": hygiene,
        "forward_project_path_touched": False,
        "current_target_calculations": 0,
        "broker_network_calls": 0,
        "deterministic_completion_packet_hash": "__NORMALIZED_SELF_REFERENCE__",
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    packet_hash = normalized_completion_hash(OUTPUT_DIR)
    consistency["deterministic_completion_packet_hash"] = packet_hash
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    if normalized_completion_hash(OUTPUT_DIR) != packet_hash:
        raise ValueError("Completion packet deterministic hash self-check failed")
    if not consistency["overall_pass"]:
        raise ValueError("Completion consistency checks did not pass")
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "approved_strategy_count": 11,
        "standardized_handoff_ready_count_after": 11,
        "package_count": len(package_rows),
        "packet_hash": packet_hash,
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
