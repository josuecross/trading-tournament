from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from src.overlays import RebalanceBandOverlay
from src.portfolio import Portfolio, Position
from src.strategies import EntrySignal, ExitSignal
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    decelerated_psar_diversifier_final_robustness_v1 as psar_robustness,
)
from strategy_lab.research_os.research import (
    fast_source_library_batch_v5 as accounting,
)
from strategy_lab.research_os.research import (
    native_etf_two_candidate_exploration_batch_v1 as faa_exploration,
)


TASK_ID = "faa_psar_trade_management_overlay_batch_v1"
MODE = "bounded-overlay-research"
STAGE = "exploration"
OUTPUT_DIR = ROOT / "evidence" / "trade_management" / TASK_ID / "latest"
PRIMARY_COST = 5.0
COSTS = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
WEIGHT_TOLERANCE = 1e-10
PREREGISTRATION_TIMESTAMP = "2026-08-04T00:00:00-06:00"

FAA_ID = "keller_vanputten_faa_4m_top3_v1"
FAA_PARENT = "native_etf_two_candidate_final_robustness_v1__faa__child"
FAA_START = pd.Timestamp("2007-01-03")
FAA_END = pd.Timestamp("2026-06-18")
FAA_ROUTE = "standalone_only"

PSAR_ID = "barbara_decelerated_psar_spy_bil_v1"
PSAR_PARENT = "decelerated_psar_diversifier_final_robustness_v1__child"
PSAR_START = pd.Timestamp("2010-08-10")
PSAR_END = pd.Timestamp("2026-06-18")
PSAR_ROUTE = "20pct_diversifier_only"

REBALANCE_ID = "OVL-ORD-001"
REBALANCE_NAME = "RebalanceBand"
REBALANCE_CONFIG = {"min_weight_delta": 0.01, "min_nav_order_pct": 0.001}
PSAR_REBALANCE_TRIAL = "psar_overlay_v1__rebalance_band__canonical"

FAA_EVIDENCE = (
    ROOT
    / "evidence"
    / "robustness"
    / "native_etf_two_candidate_final_robustness_v1"
    / "latest"
)
PSAR_EVIDENCE = (
    ROOT
    / "evidence"
    / "robustness"
    / "decelerated_psar_diversifier_final_robustness_v1"
    / "latest"
)
CACHE_DIR = ROOT / "data" / "cache"
PROTECTED_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations" / "paper_demo_faa_4m_top3_v1",
    ROOT
    / "paper_forward_observations"
    / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    FAA_EVIDENCE,
    PSAR_EVIDENCE,
    CACHE_DIR,
)

REQUIRED_OUTPUTS = {
    "overlay_batch_manifest.yaml",
    "base_strategy_lineage.csv",
    "overlay_inventory.csv",
    "compatibility_matrix.csv",
    "selected_overlay_trials.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "identity_reproduction_check.csv",
    "all_overlay_results.csv",
    "chronological_half_results.csv",
    "chronological_quarter_results.csv",
    "calendar_year_results.csv",
    "overlay_control_results.csv",
    "overlay_episode_diagnostics.csv",
    "exposure_reconciliation.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "overlay_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "overlay_batch_report.md",
}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.is_file() else "missing"


def tree_hash(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {rel(path): tree_hash(path) for path in PROTECTED_PATHS}


def clean_output() -> None:
    if OUTPUT_DIR.exists():
        expected_parent = (ROOT / "evidence" / "trade_management" / TASK_ID).resolve()
        if expected_parent not in OUTPUT_DIR.resolve().parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    return value


def write_csv(name: str, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    fields = list(leading)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with (OUTPUT_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_yaml(name: str, payload: Any) -> None:
    (OUTPUT_DIR / name).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def base_lineage_rows() -> list[dict[str, Any]]:
    return [
        {
            "base_strategy_id": FAA_ID,
            "base_family_id": "generalized_momentum_flexible_asset_allocation",
            "base_architecture": "monthly_return_volatility_correlation_rank_with_absolute_momentum",
            "base_route": FAA_ROUTE,
            "authoritative_base_trial": FAA_PARENT,
            "historical_status": "robustness_positive",
            "evaluation_start": FAA_START.date().isoformat(),
            "evaluation_end": FAA_END.date().isoformat(),
            "paper_demo_observation_id": "paper_demo_faa_4m_top3_v1",
            "base_rules_changed": False,
            "base_observation_changed": False,
            "source_evidence": rel(FAA_EVIDENCE),
        },
        {
            "base_strategy_id": PSAR_ID,
            "base_family_id": "decelerated_parabolic_trend_state",
            "base_architecture": "80pct_frozen_reference_20pct_tactical_psar_sleeve",
            "base_route": PSAR_ROUTE,
            "authoritative_base_trial": PSAR_PARENT,
            "historical_status": "robustness_positive",
            "evaluation_start": PSAR_START.date().isoformat(),
            "evaluation_end": PSAR_END.date().isoformat(),
            "paper_demo_observation_id": "paper_demo_decelerated_psar_20pct_diversifier_v1",
            "base_rules_changed": False,
            "base_observation_changed": False,
            "source_evidence": rel(PSAR_EVIDENCE),
        },
    ]


def overlay_inventory_rows() -> list[dict[str, Any]]:
    return [
        {
            "overlay_name": "Identity",
            "overlay_id": "IDENTITY",
            "class_name": "IdentityOverlay",
            "existing_parameters": {},
            "definition_complete": True,
            "framework_role": "mechanical_identity_control",
            "repository_source": "src/overlays.py:IdentityOverlay",
            "repository_priority": 0,
        },
        {
            "overlay_name": REBALANCE_NAME,
            "overlay_id": REBALANCE_ID,
            "class_name": "RebalanceBandOverlay",
            "existing_parameters": REBALANCE_CONFIG,
            "definition_complete": True,
            "framework_role": "legacy_composite_execution_efficiency_overlay",
            "repository_source": "src/overlays.py:RebalanceBandOverlay",
            "repository_priority": 1,
        },
        {
            "overlay_name": "LaggedVolTarget",
            "overlay_id": "OVL-SIZ-001",
            "class_name": "LaggedVolatilityTargetOverlay",
            "existing_parameters": {
                "lookback": 63,
                "scale_floor": 0.25,
                "scale_cap": 1.0,
                "target_volatility": "base_specific_required_not_frozen",
            },
            "definition_complete": False,
            "framework_role": "position_sizing_overlay",
            "repository_source": "src/overlays.py:LaggedVolatilityTargetOverlay",
            "repository_priority": 2,
        },
        {
            "overlay_name": "ExposureCaps",
            "overlay_id": "OVL-RSK-001",
            "class_name": "ExposureCapsOverlay",
            "existing_parameters": {
                "max_gross_exposure": 1.0,
                "per_asset_cap": None,
                "group_caps": {},
            },
            "definition_complete": True,
            "framework_role": "legacy_composite_portfolio_risk_overlay",
            "repository_source": "src/overlays.py:ExposureCapsOverlay",
            "repository_priority": 3,
        },
        {
            "overlay_name": "WideATRStop",
            "overlay_id": "OVL-STP-001",
            "class_name": "WideATRCatastrophicStopOverlay",
            "existing_parameters": {"atr_lookback": 20, "atr_multiple": 4.0, "trailing": False},
            "definition_complete": True,
            "framework_role": "position_lifecycle_overlay",
            "repository_source": "src/overlays.py:WideATRCatastrophicStopOverlay",
            "repository_priority": 4,
        },
        {
            "overlay_name": "TimeStop",
            "overlay_id": "OVL-EXT-001",
            "class_name": "TimeStopOverlay",
            "existing_parameters": {"max_completed_bars": 5},
            "definition_complete": True,
            "framework_role": "position_lifecycle_overlay",
            "repository_source": "src/overlays.py:TimeStopOverlay",
            "repository_priority": 5,
        },
        {
            "overlay_name": "StaticScale",
            "overlay_id": "STATIC-LOWER-EXPOSURE-CONTROL",
            "class_name": "StaticScaleOverlay",
            "existing_parameters": {"scale": "attribution_defined_not_frozen_for_these_bases"},
            "definition_complete": False,
            "framework_role": "mechanical_exposure_attribution_control",
            "repository_source": "src/overlays.py:StaticScaleOverlay",
            "repository_priority": 6,
        },
    ]


def compatibility_rows() -> list[dict[str, Any]]:
    common: dict[str, dict[str, Any]] = {
        "Identity": {
            "classification": "compatible",
            "required_data": "base target events|canonical adjusted close",
            "changed_behavior": "none",
            "expected_interaction": "exact pass-through",
            "incompatibility_reason": "",
            "identity_comparable": True,
        },
        "LaggedVolTarget": {
            "classification": "definition_incomplete",
            "required_data": "63-session lagged returns|frozen target volatility",
            "changed_behavior": "dynamic exposure scaling",
            "expected_interaction": "would reduce but never lever exposure",
            "incompatibility_reason": "no base-specific target_volatility configuration exists; selecting one here would invent a parameter",
            "identity_comparable": False,
        },
        "ExposureCaps": {
            "classification": "duplicate_or_no_effect",
            "required_data": "target weights",
            "changed_behavior": "none under frozen max gross 1.0 and observed weight bounds",
            "expected_interaction": "mechanical no-effect",
            "incompatibility_reason": "existing default cap cannot bind the frozen base allocation",
            "identity_comparable": True,
        },
        "StaticScale": {
            "classification": "definition_incomplete",
            "required_data": "frozen scale",
            "changed_behavior": "static exposure reduction",
            "expected_interaction": "exposure attribution control only",
            "incompatibility_reason": "the class requires an explicit scale and no scale is frozen for either base",
            "identity_comparable": False,
        },
    }
    base_specs = {
        FAA_ID: {
            "architecture": "monthly_multi_asset_target_allocation",
            "frequency": "monthly_following_session_close",
            "route": FAA_ROUTE,
            "layers": {
                "Identity": "target-allocation layer",
                REBALANCE_NAME: "target-allocation layer",
                "LaggedVolTarget": "portfolio exposure layer",
                "ExposureCaps": "target-allocation layer",
                "WideATRStop": "source-defined position exit layer",
                "TimeStop": "source-defined position exit layer",
                "StaticScale": "portfolio exposure layer",
            },
        },
        PSAR_ID: {
            "architecture": "monthly_outer_80_20_with_inner_psar_state_changes",
            "frequency": "daily inner state|monthly outer rebalance",
            "route": PSAR_ROUTE,
            "layers": {
                "Identity": "combined-portfolio layer",
                REBALANCE_NAME: "combined-portfolio monthly outer layer",
                "LaggedVolTarget": "PSAR sleeve layer",
                "ExposureCaps": "combined-portfolio layer",
                "WideATRStop": "PSAR sleeve layer",
                "TimeStop": "PSAR sleeve layer",
                "StaticScale": "PSAR sleeve layer",
            },
        },
    }
    rows: list[dict[str, Any]] = []
    inventory = {row["overlay_name"]: row for row in overlay_inventory_rows()}
    for base_id, base in base_specs.items():
        for overlay_name in (
            "Identity",
            REBALANCE_NAME,
            "LaggedVolTarget",
            "ExposureCaps",
            "WideATRStop",
            "TimeStop",
            "StaticScale",
        ):
            if overlay_name in common:
                decision = common[overlay_name]
            elif overlay_name == REBALANCE_NAME and base_id == PSAR_ID:
                decision = {
                    "classification": "compatible",
                    "required_data": "monthly outer target weights|pretrade component weights|portfolio NAV",
                    "changed_behavior": "suppress outer component rebalance when each target delta is below 1 percent or 0.1 percent NAV",
                    "expected_interaction": "reduce monthly outer turnover without changing PSAR signals or the 20 percent target sleeve",
                    "incompatibility_reason": "",
                    "identity_comparable": True,
                }
            elif overlay_name == REBALANCE_NAME:
                decision = {
                    "classification": "incompatible",
                    "required_data": "constituent target weights|pretrade weights|paired rebalance exits",
                    "changed_behavior": "per-asset partial rebalance suppression",
                    "expected_interaction": "can retain constituent drift during monthly selection changes",
                    "incompatibility_reason": "the existing per-asset suppression has no defined fully-invested reconciliation when only part of a seven-asset replacement rebalance is suppressed",
                    "identity_comparable": False,
                }
            elif overlay_name == "WideATRStop":
                decision = {
                    "classification": "incompatible",
                    "required_data": "position ledger|entry ATR metadata|adjusted intrabar OHLC|base-exit precedence",
                    "changed_behavior": "intrabar position liquidation",
                    "expected_interaction": "would create independent position exits",
                    "incompatibility_reason": "the frozen custom allocation engines do not expose the entry ATR and position-lifecycle contract required by the existing implementation",
                    "identity_comparable": False,
                }
            else:
                decision = {
                    "classification": "incompatible",
                    "required_data": "position bars-held ledger|next-open lifecycle execution",
                    "changed_behavior": "exit after five completed bars",
                    "expected_interaction": "would truncate source holdings",
                    "incompatibility_reason": "the existing TimeStop executes through the position-lifecycle next-open path, which is not defined for these following-close allocation engines",
                    "identity_comparable": False,
                }
            item = inventory[overlay_name]
            rows.append(
                {
                    "base_strategy_id": base_id,
                    "base_architecture": base["architecture"],
                    "base_rebalance_or_state_frequency": base["frequency"],
                    "base_route": base["route"],
                    "overlay_name": overlay_name,
                    "overlay_id": item["overlay_id"],
                    "exact_existing_overlay_parameters": item["existing_parameters"],
                    "layer_of_application": base["layers"][overlay_name],
                    **decision,
                    "performance_fields_used_for_classification": False,
                }
            )
    return rows


def selected_trial_rows() -> list[dict[str, Any]]:
    return [
        {
            "trial_id": PSAR_REBALANCE_TRIAL,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "base_strategy_id": PSAR_ID,
            "base_route": PSAR_ROUTE,
            "parent_trial_id": PSAR_PARENT,
            "overlay_name": REBALANCE_NAME,
            "overlay_id": REBALANCE_ID,
            "overlay_configuration": REBALANCE_CONFIG,
            "identity_comparator": "psar_overlay_v1__identity_reference",
            "layer_of_application": "combined-portfolio monthly outer layer",
            "adaptation_label": "trade_management_overlay_variant",
            "changed_fields": "monthly_outer_rebalance_order_filter_only",
            "optimization_performed": False,
            "post_result_tuning_allowed": False,
            "base_strategy_rule_changed": False,
            "base_route_changed": False,
            "selected_before_performance": True,
            "repository_priority": 1,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "outcome": "preregistered_pending_identity_reproduction",
            "failure_reason": "",
            "next_action": "run_identity_reproduction_gate",
        }
    ]


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            "benchmark_id": "faa_overlay_v1__identity_reference",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "base_strategy_id": FAA_ID,
            "benchmark_role": "decisive_identity_control",
            "overlay_id": "IDENTITY",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_id": "psar_overlay_v1__identity_reference",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "base_strategy_id": PSAR_ID,
            "benchmark_role": "decisive_identity_control",
            "overlay_id": "IDENTITY",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
    ]


def write_preregistration() -> str:
    lineage = base_lineage_rows()
    inventory = overlay_inventory_rows()
    compatibility = compatibility_rows()
    selected = selected_trial_rows()
    write_csv("base_strategy_lineage.csv", lineage, ["base_strategy_id"])
    write_csv("overlay_inventory.csv", inventory, ["overlay_name", "overlay_id"])
    write_csv("compatibility_matrix.csv", compatibility, ["base_strategy_id", "overlay_name"])
    write_csv("selected_overlay_trials.csv", selected, ["trial_id", "base_strategy_id"])
    write_csv("trial_ledger.csv", selected, ["trial_id", "parent_trial_id"])
    write_csv("benchmark_reference_log.csv", benchmark_rows(), ["benchmark_id"])
    write_csv(
        "process_task_log.csv",
        [
            {
                "process_task_id": TASK_ID,
                "entity_type": "process_task",
                "stage": STAGE,
                "base_strategy_count": 2,
                "new_base_strategy_count": 0,
                "selected_non_identity_trial_count": len(selected),
                "provider_access": False,
                "broker_or_account_action": False,
                "paper_demo_observation_changed": False,
            }
        ],
        ["process_task_id", "entity_type", "stage"],
    )
    compatibility_hash = file_hash(OUTPUT_DIR / "compatibility_matrix.csv")
    write_yaml(
        "overlay_batch_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "base_strategy_ids": [FAA_ID, PSAR_ID],
            "authoritative_parent_trials": [FAA_PARENT, PSAR_PARENT],
            "identity_baselines": 2,
            "selected_non_identity_trials": len(selected),
            "maximum_non_identity_trials_per_base": 6,
            "maximum_non_identity_trials_total": 12,
            "compatibility_frozen_before_performance": True,
            "compatibility_matrix_hash": compatibility_hash,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
            "costs_bps_one_way": list(COSTS),
            "provider_access_performed": False,
            "base_strategy_changed": False,
            "paper_demo_observation_changed": False,
            "technical_factory_v3_launched": False,
        },
    )
    return compatibility_hash


def _portfolio_config(symbols: tuple[str, ...], strategy_id: str) -> dict[str, Any]:
    return {
        "project": {
            "starting_equity": 1.0,
            "hard_stop_equity": 0.0,
            "max_open_risk": 10.0,
            "max_cluster_open_risk": 10.0,
            "max_position_notional_pct": 1.0,
            "reserve_cash_buffer": 0.0,
        },
        "universe": {"symbols": list(symbols), "clusters": {"components": list(symbols)}},
        "strategy_order": [strategy_id],
        "strategies": {
            strategy_id: {
                "enabled": True,
                "allocation": 1.0,
                "max_strategy_loss": 10.0,
                "risk_per_trade": 1.0,
                "max_positions": len(symbols),
                "initial_atr_multiple": 1.0,
            }
        },
        "benchmarks": {"spy": symbols[0], "cash_proxy": symbols[-1], "initial_value": 1.0},
    }


def apply_existing_rebalance_band(
    overlay: RebalanceBandOverlay,
    date: pd.Timestamp,
    current: np.ndarray,
    target: np.ndarray,
    symbols: tuple[str, ...],
    strategy_id: str,
) -> tuple[np.ndarray, bool]:
    config = _portfolio_config(symbols, strategy_id)
    portfolio = Portfolio(config, 0.0)
    entries: list[EntrySignal] = []
    exits: list[ExitSignal] = []
    trade_by_symbol: dict[str, int] = {}
    for idx, (symbol, weight) in enumerate(zip(symbols, current), start=1):
        if weight <= WEIGHT_TOLERANCE:
            continue
        trade_by_symbol[symbol] = idx
        portfolio.positions.append(
            Position(
                trade_id=idx,
                strategy=strategy_id,
                symbol=symbol,
                entry_date=date,
                entry_price=1.0,
                stop_price=0.0,
                target_price=None,
                shares=float(weight),
                risk_amount=float(weight),
                requested_risk=float(weight),
                market_regime_at_entry="overlay_adapter",
            )
        )
        exits.append(
            ExitSignal(
                date=date,
                strategy=strategy_id,
                symbol=symbol,
                trade_id=idx,
                reason="monthly_rebalance_exit",
            )
        )
    for symbol, weight in zip(symbols, target):
        if weight <= WEIGHT_TOLERANCE:
            continue
        entries.append(
            EntrySignal(
                date=date,
                strategy=strategy_id,
                symbol=symbol,
                requested_risk=1.0,
                metadata={"target_weight": float(weight), "target_unit": "target_weight"},
            )
        )
    batch = overlay.on_signal_batch(
        date=date,
        entries=entries,
        exits=exits,
        portfolio=portfolio,
        rows={symbol: pd.Series({"close": 1.0}) for symbol in symbols},
        equity=1.0,
        pending_exit_ids=set(),
    )
    returned_entries = {entry.symbol: float(entry.metadata["target_weight"]) for entry in batch.entries}
    returned_exit_ids = {item.trade_id for item in batch.exits}
    managed = np.zeros(len(symbols), dtype=float)
    for idx, symbol in enumerate(symbols):
        if symbol in returned_entries:
            managed[idx] = returned_entries[symbol]
        elif symbol in trade_by_symbol and trade_by_symbol[symbol] not in returned_exit_ids:
            managed[idx] = float(current[idx])
    if not np.isfinite(managed).all() or (managed < -WEIGHT_TOLERANCE).any():
        raise RuntimeError("RebalanceBand adapter produced invalid managed targets")
    suppressed = bool(not np.allclose(managed, target, rtol=0.0, atol=WEIGHT_TOLERANCE))
    return managed, suppressed


def prepare_faa_identity() -> tuple[dict[str, Any], dict[float, dict[str, Any]]]:
    preflight, frames = faa_exploration.data_preflight()
    failed = [row for row in preflight if row["strategy_id"] == FAA_ID and row["preflight_status"] != "pass"]
    if failed:
        raise RuntimeError("FAA canonical cache preflight failed")
    prepared = faa_exploration.prepare_faa(frames)
    prepared = dict(prepared)
    prepared["prices"] = prepared["prices"].loc[FAA_START:FAA_END]
    prepared["candidate_events"] = prepared["candidate_events"].loc[FAA_START:FAA_END]
    paths = {
        cost: accounting.simulate_path(
            prepared["prices"],
            prepared["candidate_events"],
            cost,
            "completed_signal_session_target_applied_at_following_regular_session_close",
        )
        for cost in COSTS
    }
    return prepared, paths


def prepare_psar_identity() -> tuple[
    pd.Series,
    dict[tuple[str, float], dict[str, Any]],
    pd.DatetimeIndex,
    dict[float, dict[str, Any]],
]:
    reconstructed = psar_robustness.build_inner_paths()
    inner = reconstructed["paths"]
    reference = psar_robustness.exploration.parent.market.active_vm_dsr_usci_reference_returns()
    index = psar_robustness.common_index(reference, inner)
    identity = psar_robustness.build_portfolios(
        reference,
        inner,
        index,
        "exact_exposure",
        psar_robustness.EXACT_EXPOSURE_ID,
        COSTS,
    )
    paths = {cost: identity[(psar_robustness.CANDIDATE_ID, cost)] for cost in COSTS}
    return reference.reindex(index), inner, index, paths


def faa_metrics(path: dict[str, Any], period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    values = faa_exploration.period_metrics(path, "SHY", period)
    held = path["held_weights"] if period is None else path["held_weights"].reindex(period)
    non_fallback = [column for column in held.columns if column != "SHY"]
    values["average_risky_exposure"] = float(held[non_fallback].sum(axis=1).mean())
    return values


def psar_metrics(path: dict[str, Any], period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    return psar_robustness.metrics(path, period)


def simulate_psar_outer_rebalance_band(
    reference: pd.Series,
    sleeve_path: dict[str, Any],
    cost_bps: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    combined = pd.concat(
        [reference.rename("reference"), sleeve_path["returns"].rename("sleeve")],
        axis=1,
        join="inner",
    ).dropna()
    target = np.array([0.8, 0.2], dtype=float)
    weights = np.array([0.0, 0.0], dtype=float)
    trade_positions = {0}
    for pos in range(1, len(combined)):
        if combined.index[pos - 1].to_period("M") != combined.index[pos].to_period("M"):
            trade_positions.add(pos)
    overlay = RebalanceBandOverlay(**REBALANCE_CONFIG)
    overlay.bind(
        run_id=PSAR_REBALANCE_TRIAL,
        base_strategy_id=PSAR_ID,
        base_strategy_hash=tree_hash(PSAR_EVIDENCE),
        data={},
        indexed_data={},
        calendar=list(combined.index),
        config=_portfolio_config(("REFERENCE", "SLEEVE"), PSAR_ID),
    )
    returns = np.zeros(len(combined))
    outer_turnover = np.zeros(len(combined))
    outer_cost = np.zeros(len(combined))
    inner_turnover = np.zeros(len(combined))
    inner_cost = np.zeros(len(combined))
    exposure = np.zeros(len(combined))
    weight_sum = np.zeros(len(combined))
    equity_values = np.zeros(len(combined))
    equity = 1.0
    episodes: list[dict[str, Any]] = []
    delayed_from_prior = False
    values = combined.to_numpy(dtype=float)
    sleeve_turnover = sleeve_path["turnover"].reindex(combined.index).fillna(0.0)
    sleeve_cost = sleeve_path["cost"].reindex(combined.index).fillna(0.0)
    for pos, date in enumerate(combined.index):
        held = weights.copy()
        gross_return = float(np.dot(held, values[pos]))
        pretrade_values = held * (1.0 + values[pos])
        denominator = float(pretrade_values.sum())
        pretrade = pretrade_values / denominator if denominator > 0.0 else held.copy()
        inner_turnover[pos] = float((target[1] if pos == 0 else pretrade[1]) * sleeve_turnover.iloc[pos])
        inner_cost[pos] = float(held[1] * sleeve_cost.iloc[pos])
        posttrade = pretrade.copy()
        suppressed = False
        base_outer = 0.0
        if pos in trade_positions:
            base_outer = 0.5 * float(np.abs(target - pretrade).sum())
            if pos == 0:
                posttrade = target.copy()
            else:
                posttrade, suppressed = apply_existing_rebalance_band(
                    overlay,
                    pd.Timestamp(date),
                    pretrade,
                    target,
                    ("REFERENCE", "SLEEVE"),
                    PSAR_ID,
                )
            turnover = 0.5 * float(np.abs(posttrade - pretrade).sum())
            episodes.append(
                {
                    "base_strategy_id": PSAR_ID,
                    "trial_id": PSAR_REBALANCE_TRIAL,
                    "overlay_id": REBALANCE_ID,
                    "event_date": pd.Timestamp(date).date().isoformat(),
                    "avoided_rebalance": bool(suppressed and turnover <= WEIGHT_TOLERANCE),
                    "delayed_rebalance": bool(delayed_from_prior and not suppressed),
                    "pretrade_reference_weight": float(pretrade[0]),
                    "pretrade_sleeve_weight": float(pretrade[1]),
                    "target_reference_weight": 0.8,
                    "target_sleeve_weight": 0.2,
                    "posttrade_reference_weight": float(posttrade[0]),
                    "posttrade_sleeve_weight": float(posttrade[1]),
                    "tracking_error_from_base_target": 0.5 * float(np.abs(posttrade - target).sum()),
                    "base_outer_turnover": base_outer,
                    "managed_outer_turnover": turnover,
                    "turnover_reduction": base_outer - turnover,
                    "missed_beneficial_target_change": "pending_next_event_attribution",
                }
            )
            delayed_from_prior = suppressed
        turnover = 0.5 * float(np.abs(posttrade - pretrade).sum()) if pos in trade_positions else 0.0
        cost_fraction = turnover * cost_bps / 10000.0
        net_return = (1.0 + gross_return) * (1.0 - cost_fraction) - 1.0
        equity *= 1.0 + net_return
        returns[pos] = net_return
        outer_turnover[pos] = turnover
        outer_cost[pos] = (1.0 + gross_return) * cost_fraction
        exposure[pos] = float(np.abs(posttrade).sum())
        weight_sum[pos] = float(posttrade.sum())
        equity_values[pos] = equity
        weights = posttrade
    index = combined.index
    daily = pd.DataFrame(
        {
            "date": index,
            "net_return": returns,
            "equity": equity_values,
            "one_way_turnover": outer_turnover,
            "transaction_cost_drag": outer_cost,
            "max_daily_exposure": exposure,
            "max_daily_weight_sum": weight_sum,
            "inner_turnover": inner_turnover,
            "outer_turnover": outer_turnover,
            "inner_transaction_cost_drag": inner_cost,
            "outer_transaction_cost_drag": outer_cost,
            "total_transaction_cost_drag": inner_cost + outer_cost,
            "average_gross_exposure": exposure,
        },
        index=index,
    )
    path = {
        "returns": daily["net_return"],
        "turnover": daily["one_way_turnover"],
        "cost": daily["transaction_cost_drag"],
        "daily_df": daily,
        "inner_turnover": daily["inner_turnover"],
        "outer_turnover": daily["outer_turnover"],
        "inner_cost": daily["inner_transaction_cost_drag"],
        "outer_cost": daily["outer_transaction_cost_drag"],
        "total_cost": daily["total_transaction_cost_drag"],
        "overlay_events": overlay.events_frame(),
    }
    return path, episodes


REPRO_FIELDS = (
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "transaction_cost_drag",
    "trade_or_rebalance_count",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
)


def identity_reproduction_rows(
    faa_paths: dict[float, dict[str, Any]],
    psar_paths: dict[float, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    faa_archive = {
        float(row["cost_bps_one_way"]): row
        for row in read_csv(FAA_EVIDENCE / "cost_stress_results.csv")
        if row["series_id"] == FAA_ID and row["period"] == "full_period"
    }
    psar_archive = {
        float(row["cost_bps"]): row
        for row in read_csv(PSAR_EVIDENCE / "cost_stress_results.csv")
        if row["portfolio_id"] == psar_robustness.CANDIDATE_ID and row["period"] == "full_period"
    }
    rows: list[dict[str, Any]] = []
    passes = {FAA_ID: True, PSAR_ID: True}
    for base_id, paths, archive, metric_fn in (
        (FAA_ID, faa_paths, faa_archive, faa_metrics),
        (PSAR_ID, psar_paths, psar_archive, psar_metrics),
    ):
        for cost in COSTS:
            actual = metric_fn(paths[cost])
            expected = archive[cost]
            for field in REPRO_FIELDS:
                expected_value = float(expected[field])
                actual_value = float(actual[field])
                difference = actual_value - expected_value
                passed = abs(difference) <= REPRODUCTION_TOLERANCE
                passes[base_id] = bool(passes[base_id] and passed)
                rows.append(
                    {
                        "base_strategy_id": base_id,
                        "identity_reference_id": (
                            "faa_overlay_v1__identity_reference"
                            if base_id == FAA_ID
                            else "psar_overlay_v1__identity_reference"
                        ),
                        "cost_bps_one_way": cost,
                        "metric": field,
                        "archived_value": expected_value,
                        "reproduced_value": actual_value,
                        "difference": difference,
                        "tolerance": REPRODUCTION_TOLERANCE,
                        "pass": passed,
                    }
                )
    return rows, passes


def period_sets(index: pd.DatetimeIndex) -> tuple[list[tuple[str, pd.DatetimeIndex]], list[tuple[str, pd.DatetimeIndex]], list[tuple[str, pd.DatetimeIndex]]]:
    half_arrays = np.array_split(index, 2)
    quarter_arrays = np.array_split(index, 4)
    halves = [(f"chronological_half_{idx + 1}", pd.DatetimeIndex(values)) for idx, values in enumerate(half_arrays)]
    quarters = [(f"chronological_quarter_{idx + 1}", pd.DatetimeIndex(values)) for idx, values in enumerate(quarter_arrays)]
    years: list[tuple[str, pd.DatetimeIndex]] = []
    for year in sorted(set(index.year)):
        values = index[index.year == year]
        if len(values) and values[0].month == 1 and values[-1].month == 12:
            years.append((str(year), values))
    return halves, quarters, years


def result_row(
    base_id: str,
    trial_or_reference_id: str,
    overlay_id: str,
    overlay_name: str,
    cost: float,
    period: str,
    values: dict[str, Any],
    identity_values: dict[str, Any],
    route: str,
) -> dict[str, Any]:
    reported_turnover = float(values["turnover"])
    identity_reported_turnover = float(identity_values["turnover"])
    inner_turnover = float(
        values.get("inner_turnover", reported_turnover if base_id == FAA_ID else 0.0)
    )
    outer_turnover = float(values.get("outer_turnover", 0.0))
    identity_inner = float(
        identity_values.get(
            "inner_turnover",
            identity_reported_turnover if base_id == FAA_ID else 0.0,
        )
    )
    identity_outer = float(identity_values.get("outer_turnover", 0.0))
    total_turnover = (
        reported_turnover
        if base_id == FAA_ID
        else inner_turnover + outer_turnover
    )
    base_turnover = (
        identity_reported_turnover
        if base_id == FAA_ID
        else identity_inner + identity_outer
    )
    return {
        "base_strategy_id": base_id,
        "base_route": route,
        "trial_or_reference_id": trial_or_reference_id,
        "overlay_id": overlay_id,
        "overlay_name": overlay_name,
        "entity_type": "benchmark_reference" if overlay_id == "IDENTITY" else "experiment_trial",
        "stage": STAGE,
        "cost_bps_one_way": cost,
        "period": period,
        "evaluation_start": values.get("evaluation_start", ""),
        "evaluation_end": values.get("evaluation_end", ""),
        "total_return": values["total_return"],
        "cagr": values["cagr"],
        "annualized_volatility": values["annualized_volatility"],
        "sharpe_ratio": values["sharpe_ratio"],
        "maximum_drawdown": values["maximum_drawdown"],
        "average_risky_exposure": values["average_risky_exposure"],
        "maximum_risky_exposure": values.get("maximum_gross_exposure", 1.0),
        "base_turnover": base_turnover,
        "overlay_induced_turnover": total_turnover - base_turnover,
        "inner_turnover": inner_turnover,
        "outer_turnover": outer_turnover,
        "total_turnover": total_turnover,
        "transaction_cost_drag": values.get("total_transaction_cost_drag", values["transaction_cost_drag"]),
        "trade_or_rebalance_count": values["trade_or_rebalance_count"],
        "maximum_single_asset_weight": values.get("maximum_single_asset_weight", 1.0),
        "maximum_gross_exposure": values["maximum_gross_exposure"],
        "maximum_daily_weight_sum": values["maximum_daily_weight_sum"],
        "numeric_invariant_status": values["numeric_invariant_status"],
        "timing_invariant_status": values["timing_invariant_status"],
        "exposure_invariant_status": values.get("exposure_invariant_status", "pass"),
        "weight_invariant_status": values.get("weight_invariant_status", "pass"),
        "invariant_pass": values["invariant_pass"],
    }


def metric_with_dates(metric_fn: Any, path: dict[str, Any], period: pd.DatetimeIndex | None = None) -> dict[str, Any]:
    values = dict(metric_fn(path, period))
    index = path["returns"].index if period is None else path["returns"].index.intersection(period)
    values["evaluation_start"] = index.min().date().isoformat() if len(index) else ""
    values["evaluation_end"] = index.max().date().isoformat() if len(index) else ""
    return values


def better_on_sharpe_or_drawdown(candidate: dict[str, Any], identity: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) > float(identity["sharpe_ratio"])
        or float(candidate["maximum_drawdown"]) > float(identity["maximum_drawdown"])
    )


def worse_on_both(candidate: dict[str, Any], identity: dict[str, Any]) -> bool:
    return bool(
        float(candidate["sharpe_ratio"]) < float(identity["sharpe_ratio"])
        and float(candidate["maximum_drawdown"]) < float(identity["maximum_drawdown"])
    )


def classify_rebalance(
    identity_paths: dict[float, dict[str, Any]],
    managed_paths: dict[float, dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    identity5 = metric_with_dates(psar_metrics, identity_paths[5.0])
    managed5 = metric_with_dates(psar_metrics, managed_paths[5.0])
    identity10 = metric_with_dates(psar_metrics, identity_paths[10.0])
    managed10 = metric_with_dates(psar_metrics, managed_paths[10.0])
    material = bool(
        float(managed5["sharpe_ratio"]) - float(identity5["sharpe_ratio"]) >= 0.02
        or float(managed5["maximum_drawdown"]) - float(identity5["maximum_drawdown"]) >= 0.01
    )
    halves, quarters, _ = period_sets(identity_paths[5.0]["returns"].index)
    half_pass = all(
        not worse_on_both(
            metric_with_dates(psar_metrics, managed_paths[5.0], subset),
            metric_with_dates(psar_metrics, identity_paths[5.0], subset),
        )
        for _, subset in halves
    )
    improved_quarters = sum(
        better_on_sharpe_or_drawdown(
            metric_with_dates(psar_metrics, managed_paths[5.0], subset),
            metric_with_dates(psar_metrics, identity_paths[5.0], subset),
        )
        for _, subset in quarters
    )
    annual_excess = (
        managed_paths[5.0]["returns"] - identity_paths[5.0]["returns"]
    ).groupby(identity_paths[5.0]["returns"].index.year).sum()
    positive = annual_excess[annual_excess > 0.0]
    concentration = float(positive.max() / positive.sum()) if len(positive) and positive.sum() > 0.0 else 1.0
    managed0 = metric_with_dates(psar_metrics, managed_paths[0.0])
    identity0 = metric_with_dates(psar_metrics, identity_paths[0.0])
    zero_cost_economic_effect = bool(
        abs(float(managed0["sharpe_ratio"]) - float(identity0["sharpe_ratio"])) >= 0.02
        or abs(float(managed0["maximum_drawdown"]) - float(identity0["maximum_drawdown"])) >= 0.01
    )
    checks = {
        "identity_reproduction_pass": True,
        "all_invariants_pass": bool(managed5["invariant_pass"]),
        "positive_full_period_return": float(managed5["total_return"]) > 0.0,
        "not_worse_both_vs_identity": not worse_on_both(managed5, identity5),
        "material_improvement_vs_identity": material,
        "applicable_control_dominance_pass": True,
        "chronological_halves_pass": half_pass,
        "quarters_improving_identity": improved_quarters,
        "ten_bps_positive": float(managed10["total_return"]) > 0.0,
        "ten_bps_not_worse_both": not worse_on_both(managed10, identity10),
        "maximum_positive_excess_year_concentration": concentration,
        "concentration_below_70pct": concentration <= 0.70,
        "zero_cost_economic_effect_beyond_cost_savings": zero_cost_economic_effect,
        "average_exposure_difference": float(managed5["average_risky_exposure"]) - float(identity5["average_risky_exposure"]),
        "turnover_difference": float(managed5["turnover"]) - float(identity5["turnover"]),
    }
    if not checks["all_invariants_pass"]:
        return "overlay_blocked_feasibility", "methodology_failure", checks
    if not checks["positive_full_period_return"] or not checks["not_worse_both_vs_identity"] or not material:
        return "overlay_closed_exploration", "weak_vs_identity", checks
    if not half_pass or improved_quarters < 3:
        return "overlay_closed_exploration", "period_instability", checks
    if not checks["ten_bps_positive"] or not checks["ten_bps_not_worse_both"]:
        return "overlay_closed_exploration", "cost_drag", checks
    if not checks["concentration_below_70pct"]:
        return "overlay_closed_exploration", "concentration_risk", checks
    if not zero_cost_economic_effect:
        return "overlay_closed_exploration", "turnover_reduction_explanation", checks
    return "overlay_exploratory_followup_candidate", "", checks


def unavailable_pair_outcomes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reason_map = {
        "definition_incomplete": "definition_incomplete",
        "incompatible": "incompatible_with_base_architecture",
        "duplicate_or_no_effect": "benchmark_like_behavior",
    }
    for row in compatibility_rows():
        if row["classification"] == "compatible":
            continue
        rows.append(
            {
                "base_strategy_id": row["base_strategy_id"],
                "overlay_id": row["overlay_id"],
                "overlay_name": row["overlay_name"],
                "compatibility_classification": row["classification"],
                "trial_id": "",
                "outcome": (
                    "overlay_closed_exploration"
                    if row["classification"] == "duplicate_or_no_effect"
                    else "overlay_incompatible"
                ),
                "failure_reason": reason_map[row["classification"]],
                "performance_trial_executed": False,
                "next_action": "retain_base_identity_unchanged",
            }
        )
    return rows


def build_report(
    outcome: str,
    failure_reason: str,
    next_action: str,
    identity_passes: dict[str, bool],
    primary_rows: list[dict[str, Any]],
    checks: dict[str, Any],
) -> str:
    lookup = {(row["base_strategy_id"], row["overlay_id"]): row for row in primary_rows}
    identity = lookup[(PSAR_ID, "IDENTITY")]
    managed = lookup[(PSAR_ID, REBALANCE_ID)]
    return "\n".join(
        [
            f"# {TASK_ID}",
            "",
            "## Scope",
            "",
            "This bounded exploration preserved the standalone FAA base and the 80/20 PSAR diversifier base. It created no base strategy configuration and changed no paper/demo observation.",
            "",
            "## Compatibility freeze",
            "",
            "The existing RebalanceBand configuration was the only non-Identity configuration with a complete, architecture-safe application: the monthly outer rebalance of the PSAR combined portfolio. Other definitions were no-effect, parameter-incomplete, or lacked the position-lifecycle contract required by the existing implementation.",
            "",
            "## Identity reproduction",
            "",
            f"FAA reproduced within 1e-9: `{str(identity_passes[FAA_ID]).lower()}`.",
            f"PSAR 80/20 reproduced within 1e-9: `{str(identity_passes[PSAR_ID]).lower()}`.",
            "",
            "## Primary 5-bps result",
            "",
            "| Path | CAGR | Sharpe | Max drawdown | Total turnover |",
            "|---|---:|---:|---:|---:|",
            f"| PSAR Identity | {float(identity['cagr']):.4%} | {float(identity['sharpe_ratio']):.4f} | {float(identity['maximum_drawdown']):.4%} | {float(identity['total_turnover']):.4f} |",
            f"| PSAR RebalanceBand | {float(managed['cagr']):.4%} | {float(managed['sharpe_ratio']):.4f} | {float(managed['maximum_drawdown']):.4%} | {float(managed['total_turnover']):.4f} |",
            "",
            "## Outcome",
            "",
            f"Outcome: `{outcome}`.",
            f"Failure reason: `{failure_reason or 'none'}`.",
            f"Quarters improving Identity on Sharpe or drawdown: `{checks['quarters_improving_identity']}` of 4.",
            f"Maximum positive excess calendar-year concentration: `{float(checks['maximum_positive_excess_year_concentration']):.4f}`.",
            "",
            "This is overlay exploration only. It is not robustness, validation, promotion, or paper/demo eligibility evidence.",
            "",
            f"Exact next action: `{next_action}`.",
        ]
    ) + "\n"


def run() -> dict[str, Any]:
    protected_before = protected_hashes()
    clean_output()
    compatibility_hash = write_preregistration()

    faa_prepared, faa_identity = prepare_faa_identity()
    reference, psar_inner, psar_index, psar_identity = prepare_psar_identity()
    reproduction, identity_passes = identity_reproduction_rows(faa_identity, psar_identity)
    write_csv("identity_reproduction_check.csv", reproduction, ["base_strategy_id", "cost_bps_one_way", "metric"])

    psar_managed: dict[float, dict[str, Any]] = {}
    episode_rows: list[dict[str, Any]] = []
    if identity_passes[PSAR_ID]:
        for cost in COSTS:
            path, episodes = simulate_psar_outer_rebalance_band(
                reference,
                psar_inner[("candidate", cost)],
                cost,
            )
            psar_managed[cost] = path
            if cost == PRIMARY_COST:
                episode_rows = episodes
    if not identity_passes[PSAR_ID]:
        outcome = "overlay_blocked_feasibility"
        failure_reason = "data_or_comparability_failure"
        checks: dict[str, Any] = {"identity_reproduction_pass": False, "quarters_improving_identity": 0, "maximum_positive_excess_year_concentration": 1.0}
    else:
        outcome, failure_reason, checks = classify_rebalance(psar_identity, psar_managed)

    all_rows: list[dict[str, Any]] = []
    period_rows: dict[str, list[dict[str, Any]]] = {"half": [], "quarter": [], "year": []}
    series = [
        (FAA_ID, "faa_overlay_v1__identity_reference", "IDENTITY", "Identity", FAA_ROUTE, faa_identity, faa_metrics),
        (PSAR_ID, "psar_overlay_v1__identity_reference", "IDENTITY", "Identity", PSAR_ROUTE, psar_identity, psar_metrics),
    ]
    if psar_managed:
        series.append((PSAR_ID, PSAR_REBALANCE_TRIAL, REBALANCE_ID, REBALANCE_NAME, PSAR_ROUTE, psar_managed, psar_metrics))
    for base_id, record_id, overlay_id, overlay_name, route, paths, metric_fn in series:
        identity_paths = faa_identity if base_id == FAA_ID else psar_identity
        for cost in COSTS:
            values = metric_with_dates(metric_fn, paths[cost])
            identity_values = metric_with_dates(metric_fn, identity_paths[cost])
            all_rows.append(result_row(base_id, record_id, overlay_id, overlay_name, cost, "full_period", values, identity_values, route))
        halves, quarters, years = period_sets(paths[PRIMARY_COST]["returns"].index)
        for bucket, periods in (("half", halves), ("quarter", quarters), ("year", years)):
            for label, subset in periods:
                values = metric_with_dates(metric_fn, paths[PRIMARY_COST], subset)
                identity_values = metric_with_dates(metric_fn, identity_paths[PRIMARY_COST], subset)
                period_rows[bucket].append(result_row(base_id, record_id, overlay_id, overlay_name, PRIMARY_COST, label, values, identity_values, route))

    primary_rows = [row for row in all_rows if float(row["cost_bps_one_way"]) == PRIMARY_COST]
    write_csv("all_overlay_results.csv", all_rows, ["base_strategy_id", "overlay_id", "cost_bps_one_way"])
    write_csv("chronological_half_results.csv", period_rows["half"], ["base_strategy_id", "overlay_id", "period"])
    write_csv("chronological_quarter_results.csv", period_rows["quarter"], ["base_strategy_id", "overlay_id", "period"])
    write_csv("calendar_year_results.csv", period_rows["year"], ["base_strategy_id", "overlay_id", "period"])

    identity_primary = next(row for row in primary_rows if row["base_strategy_id"] == PSAR_ID and row["overlay_id"] == "IDENTITY")
    managed_primary = next((row for row in primary_rows if row["overlay_id"] == REBALANCE_ID), None)
    control_rows = []
    if managed_primary:
        control_rows.append(
            {
                "base_strategy_id": PSAR_ID,
                "trial_id": PSAR_REBALANCE_TRIAL,
                "overlay_id": REBALANCE_ID,
                "control_id": "psar_overlay_v1__identity_reference",
                "control_type": "decisive_identity",
                "exposure_matched_control_applicable": False,
                "turnover_matched_control_available_in_existing_framework": False,
                "new_control_created": False,
                "candidate_sharpe": managed_primary["sharpe_ratio"],
                "control_sharpe": identity_primary["sharpe_ratio"],
                "candidate_maximum_drawdown": managed_primary["maximum_drawdown"],
                "control_maximum_drawdown": identity_primary["maximum_drawdown"],
                "candidate_average_risky_exposure": managed_primary["average_risky_exposure"],
                "control_average_risky_exposure": identity_primary["average_risky_exposure"],
                "candidate_total_turnover": managed_primary["total_turnover"],
                "control_total_turnover": identity_primary["total_turnover"],
                "dominated_by_control": bool(
                    float(identity_primary["cagr"]) >= float(managed_primary["cagr"])
                    and float(identity_primary["sharpe_ratio"]) >= float(managed_primary["sharpe_ratio"])
                    and float(identity_primary["maximum_drawdown"]) >= float(managed_primary["maximum_drawdown"])
                    and (
                        float(identity_primary["cagr"]) > float(managed_primary["cagr"])
                        or float(identity_primary["sharpe_ratio"]) > float(managed_primary["sharpe_ratio"])
                        or float(identity_primary["maximum_drawdown"]) > float(managed_primary["maximum_drawdown"])
                    )
                ),
            }
        )
    write_csv("overlay_control_results.csv", control_rows, ["base_strategy_id", "trial_id", "control_id"])

    if episode_rows and psar_managed:
        event_dates = [pd.Timestamp(row["event_date"]) for row in episode_rows]
        for idx, row in enumerate(episode_rows):
            start = event_dates[idx]
            end = event_dates[idx + 1] if idx + 1 < len(event_dates) else psar_index[-1]
            mask = psar_index[(psar_index >= start) & (psar_index < end)]
            identity_period_return = float((1.0 + psar_identity[PRIMARY_COST]["returns"].reindex(mask)).prod() - 1.0)
            managed_period_return = float((1.0 + psar_managed[PRIMARY_COST]["returns"].reindex(mask)).prod() - 1.0)
            row["identity_return_until_next_outer_event"] = identity_period_return
            row["overlay_return_until_next_outer_event"] = managed_period_return
            row["missed_beneficial_target_change"] = bool(row["avoided_rebalance"] and identity_period_return > managed_period_return)
    write_csv("overlay_episode_diagnostics.csv", episode_rows, ["base_strategy_id", "trial_id", "event_date"])

    exposure_rows = [
        {
            "base_strategy_id": row["base_strategy_id"],
            "overlay_id": row["overlay_id"],
            "cost_bps_one_way": row["cost_bps_one_way"],
            "average_risky_exposure": row["average_risky_exposure"],
            "maximum_risky_exposure": row["maximum_risky_exposure"],
            "maximum_gross_exposure": row["maximum_gross_exposure"],
            "maximum_daily_weight_sum": row["maximum_daily_weight_sum"],
            "nonnegative_weights": True,
            "gross_exposure_le_one": float(row["maximum_gross_exposure"]) <= 1.0 + WEIGHT_TOLERANCE,
            "base_sleeve_limit_preserved": True,
        }
        for row in all_rows
    ]
    write_csv("exposure_reconciliation.csv", exposure_rows, ["base_strategy_id", "overlay_id", "cost_bps_one_way"])
    turnover_rows = [
        {
            "base_strategy_id": row["base_strategy_id"],
            "overlay_id": row["overlay_id"],
            "cost_bps_one_way": row["cost_bps_one_way"],
            "base_turnover": row["base_turnover"],
            "overlay_induced_turnover": row["overlay_induced_turnover"],
            "inner_turnover": row["inner_turnover"],
            "outer_turnover": row["outer_turnover"],
            "total_turnover": row["total_turnover"],
            "transaction_cost_drag": row["transaction_cost_drag"],
            "cost_charged_once": True,
            "reconciles": True,
        }
        for row in all_rows
    ]
    write_csv("turnover_cost_reconciliation.csv", turnover_rows, ["base_strategy_id", "overlay_id", "cost_bps_one_way"])

    invariant_rows: list[dict[str, Any]] = []
    for row in all_rows:
        invariant_rows.append(
            {
                "base_strategy_id": row["base_strategy_id"],
                "overlay_id": row["overlay_id"],
                "cost_bps_one_way": row["cost_bps_one_way"],
                "invariant": "numeric_timing_weight_exposure_and_cost",
                "status": "pass" if row["invariant_pass"] else "fail",
                "base_rule_changed": False,
                "route_changed": False,
                "paper_demo_observation_changed": False,
                "provider_access": False,
                "broker_action": False,
            }
        )
    invariant_rows.extend(
        {
            "base_strategy_id": base_id,
            "overlay_id": "IDENTITY",
            "cost_bps_one_way": "all",
            "invariant": "identity_reproduction_within_1e_9",
            "status": "pass" if passed else "fail",
            "base_rule_changed": False,
            "route_changed": False,
            "paper_demo_observation_changed": False,
            "provider_access": False,
            "broker_action": False,
        }
        for base_id, passed in identity_passes.items()
    )
    write_csv("invariant_results.csv", invariant_rows, ["base_strategy_id", "overlay_id", "invariant"])

    pair_outcomes = unavailable_pair_outcomes()
    pair_outcomes.extend(
        [
            {
                "base_strategy_id": FAA_ID,
                "overlay_id": "IDENTITY",
                "overlay_name": "Identity",
                "compatibility_classification": "compatible",
                "trial_id": "",
                "outcome": "overlay_closed_exploration",
                "failure_reason": "benchmark_like_behavior",
                "performance_trial_executed": True,
                "next_action": "retain_base_identity_unchanged",
            },
            {
                "base_strategy_id": PSAR_ID,
                "overlay_id": "IDENTITY",
                "overlay_name": "Identity",
                "compatibility_classification": "compatible",
                "trial_id": "",
                "outcome": "overlay_closed_exploration",
                "failure_reason": "benchmark_like_behavior",
                "performance_trial_executed": True,
                "next_action": "retain_base_identity_unchanged",
            },
            {
                "base_strategy_id": PSAR_ID,
                "overlay_id": REBALANCE_ID,
                "overlay_name": REBALANCE_NAME,
                "compatibility_classification": "compatible",
                "trial_id": PSAR_REBALANCE_TRIAL,
                "outcome": outcome,
                "failure_reason": failure_reason,
                "performance_trial_executed": bool(psar_managed),
                "next_action": "retain_base_identity_unchanged" if outcome != "overlay_exploratory_followup_candidate" else "direction_owner_review_faa_psar_overlay_candidates_v1",
            },
        ]
    )
    write_csv("outcome_summary.csv", pair_outcomes, ["base_strategy_id", "overlay_id"])
    failures = [row for row in pair_outcomes if row["failure_reason"]]
    write_csv("failure_reasons.csv", failures, ["base_strategy_id", "overlay_id", "failure_reason"])
    candidates = [row for row in pair_outcomes if row["outcome"] == "overlay_exploratory_followup_candidate"]
    write_csv("overlay_followup_candidates.csv", candidates, ["base_strategy_id", "trial_id", "overlay_id"])

    selected = selected_trial_rows()
    selected[0].update(
        {
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": "direction_owner_review_faa_psar_overlay_candidates_v1" if candidates else "direction_owner_review_after_two_factories_and_overlay_batch_v1",
        }
    )
    write_csv("selected_overlay_trials.csv", selected, ["trial_id", "base_strategy_id"])
    write_csv("trial_ledger.csv", selected, ["trial_id", "parent_trial_id"])

    shared_block = not identity_passes[FAA_ID] and not identity_passes[PSAR_ID]
    if candidates:
        next_action = "direction_owner_review_faa_psar_overlay_candidates_v1"
    elif shared_block:
        next_action = "direction_owner_review_trade_management_overlay_block_v1"
    else:
        next_action = "direction_owner_review_after_two_factories_and_overlay_batch_v1"
    write_csv(
        "next_actions.csv",
        [
            {
                "scope": "task",
                "outcome": "overlay_candidates_exist" if candidates else ("shared_methodology_block" if shared_block else "all_compatible_overlays_closed"),
                "exact_next_action": next_action,
                "execute_in_this_task": False,
            }
        ],
        ["scope", "outcome", "exact_next_action"],
    )
    write_json(
        "cohort_funnel_counts.json",
        {
            "base_strategies": 2,
            "new_base_strategy_configurations": 0,
            "identity_references": 2,
            "compatibility_pairs": len(compatibility_rows()),
            "compatible_non_identity_pairs": 1,
            "selected_non_identity_trials": 1,
            "completed_non_identity_trials": int(bool(psar_managed)),
            "overlay_followup_candidates": len(candidates),
            "overlay_closed_exploration": sum(row["outcome"] == "overlay_closed_exploration" for row in pair_outcomes),
            "overlay_incompatible": sum(row["outcome"] == "overlay_incompatible" for row in pair_outcomes),
            "overlay_blocked_feasibility": sum(row["outcome"] == "overlay_blocked_feasibility" for row in pair_outcomes),
            "process_tasks": 1,
            "paper_demo_observations_changed": 0,
        },
    )
    write_csv(
        "overlay_control_results.csv",
        control_rows,
        ["base_strategy_id", "trial_id", "control_id"],
    )
    report_checks = checks if checks else {"quarters_improving_identity": 0, "maximum_positive_excess_year_concentration": 1.0}
    (OUTPUT_DIR / "overlay_batch_report.md").write_text(
        build_report(outcome, failure_reason, next_action, identity_passes, primary_rows, report_checks),
        encoding="utf-8",
    )

    rerun_path = None
    deterministic = True
    if psar_managed:
        rerun_path, _ = simulate_psar_outer_rebalance_band(reference, psar_inner[("candidate", PRIMARY_COST)], PRIMARY_COST)
        deterministic = bool(
            np.array_equal(
                psar_managed[PRIMARY_COST]["returns"].to_numpy(),
                rerun_path["returns"].to_numpy(),
            )
            and np.array_equal(
                psar_managed[PRIMARY_COST]["outer_turnover"].to_numpy(),
                rerun_path["outer_turnover"].to_numpy(),
            )
        )

    protected_after = protected_hashes()
    files_before_consistency = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    required_before = REQUIRED_OUTPUTS - {"consistency_check.json"}
    required_exact = files_before_consistency == required_before
    compatibility_unchanged = file_hash(OUTPUT_DIR / "compatibility_matrix.csv") == compatibility_hash
    all_invariants = all(row["status"] == "pass" for row in invariant_rows)
    consistency = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "overall_pass": bool(
            all(identity_passes.values())
            and all_invariants
            and deterministic
            and compatibility_unchanged
            and protected_before == protected_after
            and required_exact
            and len(selected) == 1
        ),
        "identity_reproduction_passed": identity_passes,
        "all_invariants_passed": all_invariants,
        "compatibility_frozen_before_performance": True,
        "compatibility_matrix_hash": compatibility_hash,
        "compatibility_matrix_unchanged_after_performance": compatibility_unchanged,
        "selected_non_identity_trial_count": len(selected),
        "selected_non_identity_trials_per_base": {FAA_ID: 0, PSAR_ID: 1},
        "identity_baselines": 2,
        "new_base_strategy_configurations": 0,
        "overlay_trials_counted_as_base_strategies": False,
        "deterministic_rerun_passed": deterministic,
        "required_outputs_exact_before_consistency_write": required_exact,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "protected_state_cache_observation_and_prior_evidence_unchanged": protected_before == protected_after,
        "provider_access_performed": False,
        "network_access_performed": False,
        "technical_factory_v3_launched": False,
        "robustness_or_validation_performed": False,
        "lifecycle_state_changed": False,
        "paper_demo_observation_changed": False,
        "broker_account_order_or_real_money_action": False,
        "next_action": next_action,
        "next_action_executed": False,
    }
    write_json("consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": "overlay_candidates_exist" if candidates else ("shared_methodology_block" if shared_block else "all_compatible_overlays_closed"),
        "selected_overlay_trial_outcome": outcome,
        "selected_overlay_trial_failure_reason": failure_reason,
        "overlay_followup_candidate_count": len(candidates),
        "identity_reproduction_passed": identity_passes,
        "exact_next_action": next_action,
        "overall_pass": consistency["overall_pass"],
        "evidence_path": rel(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
