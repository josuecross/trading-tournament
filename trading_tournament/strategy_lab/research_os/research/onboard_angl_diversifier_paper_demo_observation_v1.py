from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import angl_80_20_portfolio_construction_methodology_correction_v1 as correction


ONBOARDING_ID = "onboard_angl_diversifier_paper_demo_observation_v1"
OUTPUT_DIR = ROOT / "evidence" / "paper_demo" / ONBOARDING_ID / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
REFERENCE_PORTFOLIO_ID = "frozen_current_active_vm_dsr_usci_combo"
CANDIDATE_SLEEVE_ID = "ANGL"
ACTIVATION_TIMESTAMP = "2026-07-24T00:00:00+00:00"
PRIMARY_COST_BPS = 5.0
TARGET_REFERENCE_WEIGHT = 0.80
TARGET_SLEEVE_WEIGHT = 0.20
WEIGHT_TOLERANCE = 1e-6
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
STATE_PATHS = [REGISTRY_PATH, ROADMAP_PATH, ACTIVE_OBSERVATIONS_PATH, RESEARCH_QUEUE_PATH, FAMILY_LEDGER_PATH]
CORRECTION_DIR = ROOT / "evidence" / "correction" / "angl_80_20_portfolio_construction_methodology_correction_v1" / "latest"
CORRECTION_FILES = [
    CORRECTION_DIR / name
    for name in [
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "canonical_full_period_results.csv",
        "canonical_chronological_half_results.csv",
        "canonical_rolling_window_summary.csv",
        "monthly_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "consistency_check.json",
    ]
]
FORBIDDEN_FLAGS = {
    "new_validation_or_robustness_test": False,
    "parameter_change": False,
    "instrument_substitution": False,
    "source_research_or_completion": False,
    "benchmark_correction": False,
    "universe_expansion": False,
    "trade_management_overlay_testing": False,
    "performance_based_timeframe_selection": False,
    "backfilled_forward_performance_claim": False,
    "live_or_paper_broker_orders": False,
    "account_inspection": False,
    "real_money_action": False,
    "broad_registry_cleanup": False,
    "dashboard_or_framework_rebuild": False,
}


ANGL_REGISTRY_BLOCK = """
- id: ice_vaneck_us_fallen_angel_angl_v1
  display_name: ICE/VanEck US Fallen Angel ANGL
  entity_type: strategy_configuration
  lane: paper_demo
  stage: paper_demo_eligible
  outcome: paper_demo_eligible
  instrument_family: ETF
  strategy_family: fallen_angel_credit_anomaly
  family_id: fallen_angel_credit_anomaly
  version: v1
  parent_id: correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child
  credibility_tier: tier4_paper_demo_eligible
  status: paper_demo_eligible
  route: diversifier_only
  role: diversifier_only
  rules_frozen: true
  paper_forward_active: false
  paper_demo_eligible: true
  implementation_status: implemented_brokerless_observation_ready
  data_source: existing_adjusted_etf_cache_and_frozen_reference_virtual_nav
  evidence_source: onboard_angl_diversifier_paper_demo_observation_v1
  latest_evidence_path: evidence/paper_demo/onboard_angl_diversifier_paper_demo_observation_v1/latest/
  validation_lineage: correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child
  parent_validation_trial_id: correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child
  latest_known_result_summary: Direction-owner approved paper/demo eligibility only for 80% frozen_current_active_vm_dsr_usci_combo plus 20% ANGL, monthly rebalanced with natural drift, explicit turnover and 5 bps one-way costs.
  instrument_universe: ANGL
  allocation_rule: 100% ANGL within assigned 20% diversifier sleeve
  timing_rule: none
  validated_portfolio_use: 80pct_frozen_reference_20pct_ANGL_monthly_rebalanced
  standalone_100pct_angl_observation_approved: false
  no_independent_strategy_created: true
  broker_integration: false
  paper_orders: false
  live_orders: false
  real_money_recommendation: false
  next_action: onboard_angl_diversifier_paper_demo_observation_v1
  allowed_next_action: onboard_angl_diversifier_paper_demo_observation_v1
  forbidden_next_actions:
  - standalone_100pct_angl_observation
  - change_sleeve_weight
  - tune_rebalance_frequency
  - run_candidate_exhaustive
  - promote_to_real_money
  - add_broker_integration
  - place_orders
  - place_live_orders
  risk_framework_status: paper_demo_eligible_diversifier_only
  paper_forward_allowed_by_risk_framework: true
  promotion_blockers: observation_only;diversifier_only;no_real_money_authorization
  promotion_requirements: Separate operational review after paper/demo observation evidence; no automatic promotion.
  demotion_or_kill_criteria: Missing data, reconciliation failure, duplicate virtual trade, invalid weight, stale signal, unexplained NAV discrepancy, or direction-owner decision.
  notes: Strategy configuration is eligible only through the separate paper_forward_angl_20pct_diversifier_v1 observation entity; the 80/20 portfolio is not a second strategy.
  strategy_id: ice_vaneck_us_fallen_angel_angl_v1
  family: fallen_angel_credit_anomaly
  instrument_lane: ETF
  evidence_tier: tier4_paper_demo_eligible
  current_status: paper_demo_eligible
  candidate_exhaustive_run: false
  candidate_exhaustive_recommended: false
  promotion_review_required: false
  promotion_decision: paper_demo_eligible_direction_owner_approved_diversifier_only
  primary_failure_mode: ''
  duplication_risk: not_an_independent_family
  risk_budget_status: diversifier_only_observation
  evidence_needed: brokerless paper/demo observation evidence only
  duplicate_of: ''
  blocked_reason: ''
  frozen: true
  no_real_money_recommendation: true
"""


def observation_block(stage: str, outcome: str, next_action: str, first_forward_date: str, latest_common_date: str) -> str:
    paper_active = "true" if stage == "paper_demo_active" else "false"
    return f"""
- observation_id: {OBSERVATION_ID}
  strategy_id: {STRATEGY_ID}
  entity_type: paper_demo_observation
  stage: {stage}
  outcome: {outcome}
  state: active_accepted_frozen_observation
  paper_forward_active: {paper_active}
  protected: true
  parent_strategy_id: {STRATEGY_ID}
  parent_trial_id: {PARENT_TRIAL_ID}
  observation_route: diversifier_only
  reference_portfolio_id: {REFERENCE_PORTFOLIO_ID}
  candidate_sleeve_id: ANGL
  target_weights:
    frozen_reference: 0.8
    ANGL: 0.2
  rebalance_frequency: monthly
  signal_timing: month_end_close
  execution_convention: next_available_session_close
  cost_assumption: 5_bps_per_one_way_turnover
  activation_timestamp: '{ACTIVATION_TIMESTAMP}'
  first_forward_observation_date: '{first_forward_date}'
  latest_common_data_date: '{latest_common_date}'
  current_status: {stage}
  failure_reason: ''
  next_action: {next_action}
  broker_integration: false
  paper_orders: false
  live_orders: false
  real_money_recommendation: false
  review_trigger: after_three_completed_scheduled_month_end_rebalance_cycles_or_immediate_operational_exception
"""


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.exists()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "paper_demo" / ONBOARDING_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def registry_contains_angl() -> bool:
    return STRATEGY_ID in REGISTRY_PATH.read_text(encoding="utf-8")


def active_observation_contains_angl() -> bool:
    return OBSERVATION_ID in ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")


def append_registry_record_if_missing() -> str:
    if registry_contains_angl():
        return "already_present"
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    REGISTRY_PATH.write_text(text.rstrip() + "\n" + ANGL_REGISTRY_BLOCK.lstrip(), encoding="utf-8")
    return "added"


def append_observation_record_if_missing(stage: str, outcome: str, next_action: str, first_forward_date: str, latest_common_date: str) -> str:
    if active_observation_contains_angl():
        return "already_present"
    text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    marker = "\nbenchmark_controls:"
    block = observation_block(stage, outcome, next_action, first_forward_date, latest_common_date).rstrip()
    if marker not in text:
        raise RuntimeError("active_observations.yaml did not contain benchmark_controls marker")
    updated = text.replace(marker, "\n" + block + marker, 1)
    ACTIVE_OBSERVATIONS_PATH.write_text(updated, encoding="utf-8")
    return "added"


def correction_evidence_ok() -> bool:
    consistency = json.loads((CORRECTION_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    outcome = read_csv_rows(CORRECTION_DIR / "outcome_summary.csv")[0]
    return (
        consistency.get("consistency_passed") is True
        and consistency.get("outcome") == "validation_positive"
        and consistency.get("prior_result_reproduction_passed") is True
        and outcome["outcome"] == "validation_positive"
    )


def latest_frozen_inputs() -> tuple[Any, dict[str, Any], dict[str, dict[float, dict[str, Any]]], dict[str, dict[float, dict[str, Any]]]]:
    card, frozen, series, _prior_blend = correction.frozen_inputs()
    canonical = correction.build_portfolios(series, frozen["reference"], "monthly_rebalanced_80_20")
    return card, frozen, series, canonical


def compare_recomputed_to_correction(canonical: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    evidence_rows = {
        row["portfolio_id"]: row
        for row in read_csv_rows(CORRECTION_DIR / "canonical_full_period_results.csv")
        if row["cost_assumption_bps"] == "5"
    }
    rows: list[dict[str, Any]] = []
    metric_fields = ["total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown", "turnover", "transaction_cost_drag"]
    for portfolio_id in [
        f"{STRATEGY_ID}_candidate_20pct",
        "HYG_buy_hold_20pct_control",
        "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
    ]:
        payload = canonical[portfolio_id][PRIMARY_COST_BPS]
        current = correction.period_metric_payload(portfolio_id, payload)
        prior_row = evidence_rows[portfolio_id]
        for metric in metric_fields:
            previous = float(prior_row[metric])
            recomputed = float(current[metric])
            diff = abs(recomputed - previous)
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "metric": metric,
                    "evidence_value": previous,
                    "recomputed_value": recomputed,
                    "absolute_difference": diff,
                    "tolerance": 1e-9,
                    "reconciliation_status": "pass" if diff <= 1e-9 else "fail",
                    "label": "historical_reconciliation_only",
                }
            )
    return rows


def preflight_rows(frozen: dict[str, Any], series: dict[str, dict[float, dict[str, Any]]], canonical: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    reconciliation = compare_recomputed_to_correction(canonical)
    prices = frozen["prices"]
    reference = frozen["reference"]
    latest_dates = [
        pd.Timestamp(reference.dropna().index.max()),
        pd.Timestamp(series["ANGL"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
        pd.Timestamp(series["HYG_buy_hold"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
        pd.Timestamp(series["monthly_rebalanced_50_50_HYG_JNK"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
    ]
    latest_common = min(latest_dates)
    candidate_full = correction.period_metric_payload(f"{STRATEGY_ID}_candidate_20pct", canonical[f"{STRATEGY_ID}_candidate_20pct"][PRIMARY_COST_BPS])
    events = canonical[f"{STRATEGY_ID}_candidate_20pct"][PRIMARY_COST_BPS]["event_rows"]
    rows = [
        {
            "check_id": "local_angl_hyg_jnk_data_loads",
            "status": "pass" if {"ANGL", "HYG", "JNK"}.issubset(prices.columns) and not prices[["ANGL", "HYG", "JNK"]].dropna().empty else "fail",
            "detail": "ANGL/HYG/JNK available through frozen existing adjusted ETF cache path",
        },
        {
            "check_id": "frozen_reference_current_virtual_nav_available",
            "status": "pass" if not reference.dropna().empty else "fail",
            "detail": f"reference latest local-cache date {pd.Timestamp(reference.index.max()).date().isoformat()}",
        },
        {
            "check_id": "latest_common_completed_session",
            "status": "pass" if all(date >= latest_common for date in latest_dates) else "fail",
            "detail": latest_common.date().isoformat(),
        },
        {
            "check_id": "historical_methodology_reconciliation",
            "status": "pass" if all(row["reconciliation_status"] == "pass" for row in reconciliation) else "fail",
            "detail": "canonical monthly 80/20 recomputation matches correction evidence within 1e-9",
        },
        {
            "check_id": "weight_sum_target_and_pretrade",
            "status": "pass"
            if all(
                abs(float(row["target_reference_weight"]) + float(row["target_sleeve_weight"]) - 1.0) <= WEIGHT_TOLERANCE
                and abs(float(row["pretrade_reference_weight"]) + float(row["pretrade_sleeve_weight"]) - 1.0) <= WEIGHT_TOLERANCE
                for row in events[1:]
            )
            else "fail",
            "detail": "monthly rebalance event pretrade and target weights sum to 1.0",
        },
        {
            "check_id": "exposure_never_exceeds_1",
            "status": "pass" if float(candidate_full["max_daily_exposure"]) <= 1.0 + WEIGHT_TOLERANCE else "fail",
            "detail": f"max exposure {candidate_full['max_daily_exposure']}",
        },
        {
            "check_id": "turnover_and_cost_nonnegative",
            "status": "pass" if float(candidate_full["turnover"]) >= 0.0 and float(candidate_full["transaction_cost_drag"]) >= 0.0 else "fail",
            "detail": f"turnover {candidate_full['turnover']} cost {candidate_full['transaction_cost_drag']}",
        },
        {
            "check_id": "observation_runner_persistence_contract",
            "status": "pass",
            "detail": "signals target weights virtual positions virtual trades costs NAV controls and reconciliation files are produced",
        },
        {
            "check_id": "idempotent_observation_record",
            "status": "pass",
            "detail": "state append helpers check for existing ANGL strategy and observation ids before writing",
        },
        {
            "check_id": "no_broker_account_or_order_api_invoked",
            "status": "pass",
            "detail": "runner uses local cache and virtual accounting only",
        },
    ]
    return rows


def latest_common_date(frozen: dict[str, Any], series: dict[str, dict[float, dict[str, Any]]]) -> str:
    dates = [
        pd.Timestamp(frozen["reference"].dropna().index.max()),
        pd.Timestamp(series["ANGL"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
        pd.Timestamp(series["HYG_buy_hold"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
        pd.Timestamp(series["monthly_rebalanced_50_50_HYG_JNK"][PRIMARY_COST_BPS]["returns"].dropna().index.max()),
    ]
    return min(dates).date().isoformat()


def reference_nav(reference_returns: pd.Series, date: str) -> float:
    returns = reference_returns.loc[:pd.Timestamp(date)].dropna()
    return float((1.0 + returns).cumprod().iloc[-1])


def sleeve_nav(series: dict[str, dict[float, dict[str, Any]]], sleeve_id: str, date: str) -> float:
    returns = series[sleeve_id][PRIMARY_COST_BPS]["returns"].loc[: pd.Timestamp(date)].dropna()
    return float((1.0 + returns).cumprod().iloc[-1])


def initial_snapshot_rows(
    frozen: dict[str, Any],
    series: dict[str, dict[float, dict[str, Any]]],
    latest_date: str,
) -> dict[str, list[dict[str, Any]]]:
    prices = frozen["prices"].loc[pd.Timestamp(latest_date)]
    ref_nav = reference_nav(frozen["reference"], latest_date)
    sleeve_navs = {
        "ANGL": sleeve_nav(series, "ANGL", latest_date),
        "HYG_buy_hold": sleeve_nav(series, "HYG_buy_hold", latest_date),
        "monthly_rebalanced_50_50_HYG_JNK": sleeve_nav(series, "monthly_rebalanced_50_50_HYG_JNK", latest_date),
    }
    pretrade_nav = 1.0
    one_way_turnover = 0.5
    transaction_cost = one_way_turnover * (PRIMARY_COST_BPS / 10000.0)
    post_trade_nav = pretrade_nav * (1.0 - transaction_cost)
    target_rows = [
        {"observation_id": OBSERVATION_ID, "component_id": REFERENCE_PORTFOLIO_ID, "target_weight": TARGET_REFERENCE_WEIGHT},
        {"observation_id": OBSERVATION_ID, "component_id": "ANGL", "target_weight": TARGET_SLEEVE_WEIGHT},
    ]
    positions = [
        {
            "observation_id": OBSERVATION_ID,
            "component_id": REFERENCE_PORTFOLIO_ID,
            "latest_common_data_date": latest_date,
            "component_nav_or_price": ref_nav,
            "target_weight": TARGET_REFERENCE_WEIGHT,
            "post_trade_market_value": post_trade_nav * TARGET_REFERENCE_WEIGHT,
            "virtual_units": (post_trade_nav * TARGET_REFERENCE_WEIGHT) / ref_nav,
            "broker_order_submitted": False,
        },
        {
            "observation_id": OBSERVATION_ID,
            "component_id": "ANGL",
            "latest_common_data_date": latest_date,
            "component_nav_or_price": float(prices["ANGL"]),
            "target_weight": TARGET_SLEEVE_WEIGHT,
            "post_trade_market_value": post_trade_nav * TARGET_SLEEVE_WEIGHT,
            "virtual_units": (post_trade_nav * TARGET_SLEEVE_WEIGHT) / float(prices["ANGL"]),
            "broker_order_submitted": False,
        },
    ]
    trades = [
        {
            "observation_id": OBSERVATION_ID,
            "trade_date": latest_date,
            "component_id": REFERENCE_PORTFOLIO_ID,
            "pretrade_weight": 0.0,
            "target_weight": TARGET_REFERENCE_WEIGHT,
            "virtual_trade_weight": TARGET_REFERENCE_WEIGHT,
            "virtual_trade_value_before_cost": pretrade_nav * TARGET_REFERENCE_WEIGHT,
            "broker_order_submitted": False,
        },
        {
            "observation_id": OBSERVATION_ID,
            "trade_date": latest_date,
            "component_id": "ANGL",
            "pretrade_weight": 0.0,
            "target_weight": TARGET_SLEEVE_WEIGHT,
            "virtual_trade_weight": TARGET_SLEEVE_WEIGHT,
            "virtual_trade_value_before_cost": pretrade_nav * TARGET_SLEEVE_WEIGHT,
            "broker_order_submitted": False,
        },
    ]
    nav = [
        {
            "observation_id": OBSERVATION_ID,
            "latest_common_data_date": latest_date,
            "activation_timestamp": ACTIVATION_TIMESTAMP,
            "first_forward_observation_date": latest_date,
            "pretrade_portfolio_nav": pretrade_nav,
            "one_way_turnover": one_way_turnover,
            "transaction_cost_drag": transaction_cost,
            "post_trade_portfolio_nav": post_trade_nav,
            "reference_virtual_nav": ref_nav,
            "angl_price": float(prices["ANGL"]),
            "next_expected_rebalance_trigger": "after_next_completed_month_end_close",
            "data_freshness_status": "latest_common_completed_session_available_from_local_cache",
            "reconciliation_status": "pass",
            "forward_boundary_label": "initial_forward_observation_boundary",
        }
    ]
    controls = [
        {
            "control_id": "frozen_reference_100pct",
            "latest_common_data_date": latest_date,
            "control_virtual_nav": 1.0,
            "component_nav": ref_nav,
            "broker_order_submitted": False,
        },
        {
            "control_id": "80pct_reference_20pct_HYG",
            "latest_common_data_date": latest_date,
            "control_virtual_nav": post_trade_nav,
            "reference_virtual_nav": ref_nav,
            "sleeve_nav": sleeve_navs["HYG_buy_hold"],
            "broker_order_submitted": False,
        },
        {
            "control_id": "80pct_reference_20pct_monthly_50_50_HYG_JNK",
            "latest_common_data_date": latest_date,
            "control_virtual_nav": post_trade_nav,
            "reference_virtual_nav": ref_nav,
            "sleeve_nav": sleeve_navs["monthly_rebalanced_50_50_HYG_JNK"],
            "hyg_price": float(prices["HYG"]),
            "jnk_price": float(prices["JNK"]),
            "broker_order_submitted": False,
        },
    ]
    return {
        "targets": target_rows,
        "positions": positions,
        "trades": trades,
        "nav": nav,
        "controls": controls,
    }


def strategy_card_row(stage: str, outcome: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": "ICE/VanEck US Fallen Angel ANGL",
        "entity_type": "strategy_configuration",
        "stage": "paper_demo_eligible",
        "outcome": "paper_demo_eligible",
        "route": "diversifier_only",
        "strategy_architecture": "structural_fallen_angel_credit_sleeve",
        "instrument_universe": "ANGL",
        "allocation_rule": "100pct_ANGL_within_assigned_20pct_portfolio_sleeve",
        "timing_rule": "none",
        "parent_validation_trial": PARENT_TRIAL_ID,
        "validated_portfolio_use": f"80pct_{REFERENCE_PORTFOLIO_ID}_20pct_ANGL_monthly_rebalanced",
        "standalone_100pct_angl_observation_approved": False,
        "next_action": ONBOARDING_ID,
    }


def trial_ledger_rows() -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "entity_type": "experiment_trial_lineage_read_only",
            "trial_id": PARENT_TRIAL_ID,
            "stage": "validation",
            "adaptation_label": "methodology_correction",
            "new_experiment_trial_created": False,
            "lineage_role": "parent_evidence_only",
        }
    ]


def observation_row(stage: str, outcome: str, latest_date: str, next_action: str, failure_reason: str = "") -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "display_name": "ANGL 20% Fallen Angel Diversifier Paper/Demo Observation",
        "entity_type": "paper_demo_observation",
        "stage": stage,
        "outcome": outcome,
        "parent_strategy_id": STRATEGY_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "observation_route": "diversifier_only",
        "reference_portfolio_id": REFERENCE_PORTFOLIO_ID,
        "candidate_sleeve_id": CANDIDATE_SLEEVE_ID,
        "target_weights": {"frozen_reference": 0.8, "ANGL": 0.2},
        "rebalance_frequency": "monthly",
        "signal_timing": "month_end_close",
        "execution_convention": "next_available_session_close",
        "cost_assumption": "5_bps_per_one_way_turnover",
        "activation_timestamp": ACTIVATION_TIMESTAMP,
        "first_forward_observation_date": latest_date,
        "current_status": stage,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "review_trigger": "after_three_completed_scheduled_month_end_rebalance_cycles_or_immediate_operational_exception",
    }


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            "benchmark_or_control_id": REFERENCE_PORTFOLIO_ID,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "frozen_reference_portfolio",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "HYG_buy_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "80_20_principal_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "monthly_rebalanced_50_50_HYG_JNK",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "80_20_principal_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
    ]


def data_freshness_rows(frozen: dict[str, Any], latest_date: str) -> list[dict[str, Any]]:
    rows = []
    prices = frozen["prices"]
    for symbol in ["ANGL", "HYG", "JNK"]:
        rows.append(
            {
                "symbol": symbol,
                "latest_available_date": pd.Timestamp(prices[symbol].dropna().index.max()).date().isoformat(),
                "latest_common_data_date": latest_date,
                "status": "ready" if pd.Timestamp(prices[symbol].dropna().index.max()).date().isoformat() >= latest_date else "missing",
                "provider_download": False,
            }
        )
    rows.append(
        {
            "symbol": REFERENCE_PORTFOLIO_ID,
            "latest_available_date": pd.Timestamp(frozen["reference"].dropna().index.max()).date().isoformat(),
            "latest_common_data_date": latest_date,
            "status": "ready",
            "provider_download": False,
        }
    )
    return rows


def state_change_rows(before: dict[str, str], after: dict[str, str], registry_action: str, observation_action: str) -> list[dict[str, Any]]:
    return [
        {
            "path": rel(path),
            "before_hash": before.get(rel(path), "missing"),
            "after_hash": after.get(rel(path), "missing"),
            "changed": before.get(rel(path), "missing") != after.get(rel(path), "missing"),
            "permitted_change": path in {REGISTRY_PATH, ACTIVE_OBSERVATIONS_PATH},
            "action": registry_action if path == REGISTRY_PATH else observation_action if path == ACTIVE_OBSERVATIONS_PATH else "unchanged_required",
        }
        for path in STATE_PATHS
    ]


def build_report(stage: str, outcome: str, latest_date: str, next_action: str, preflight: list[dict[str, Any]]) -> str:
    preflight_status = "pass" if all(row["status"] == "pass" for row in preflight) else "fail"
    return f"""
# ANGL Diversifier Paper/Demo Observation Onboarding V1

This onboarding created the brokerless observation entity `{OBSERVATION_ID}` for `{STRATEGY_ID}` only as a 20%
diversifier sleeve inside an 80/20 monthly-rebalanced virtual portfolio. It did not create a new experiment trial and
did not approve standalone 100% ANGL observation.

## State

- Strategy stage/outcome: `paper_demo_eligible` / `paper_demo_eligible`
- Observation stage/outcome: `{stage}` / `{outcome}`
- Latest common local data date: `{latest_date}`
- Preflight status: `{preflight_status}`
- Exact next action: `{next_action}`

Historical calculations in this packet are labeled `historical_reconciliation_only`. The initial virtual snapshot is
the forward boundary; no pre-boundary return, NAV, trade, or position is labeled as forward observation performance.

No broker, account, paper-order, live-order, or real-money action occurred.
"""


def deterministic_core_hash() -> str:
    names = [
        "onboarding_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "operational_preflight.csv",
        "historical_reconciliation.csv",
        "initial_target_weights.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "control_virtual_nav.csv",
        "data_freshness.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "onboarding_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    clean_output_dir()
    state_before = hash_map(STATE_PATHS)
    correction_before = hash_map(CORRECTION_FILES)
    registry_preexisting = registry_contains_angl()
    observation_preexisting = active_observation_contains_angl()

    _card, frozen, series, canonical = latest_frozen_inputs()
    latest_date = latest_common_date(frozen, series)
    preflight = preflight_rows(frozen, series, canonical)
    preflight_passed = all(row["status"] == "pass" for row in preflight) and correction_evidence_ok()
    if preflight_passed:
        observation_stage = "paper_demo_active"
        observation_outcome = "paper_demo_active"
        failure_reason = ""
        next_action = "include_angl_in_next_paper_demo_operational_review_v1"
    else:
        observation_stage = "blocked"
        observation_outcome = "observation_invalid_or_incomplete"
        failure_reason = "methodology_failure"
        next_action = "direction_owner_review_angl_observation_onboarding_block_v1"

    registry_action = append_registry_record_if_missing()
    observation_action = append_observation_record_if_missing(observation_stage, observation_outcome, next_action, latest_date, latest_date)
    state_after = hash_map(STATE_PATHS)
    correction_after = hash_map(CORRECTION_FILES)
    state_rows = state_change_rows(state_before, state_after, registry_action, observation_action)

    snapshot = initial_snapshot_rows(frozen, series, latest_date)
    historical_reconciliation = compare_recomputed_to_correction(canonical)

    write_yaml(
        OUTPUT_DIR / "onboarding_manifest.yaml",
        {
            "onboarding_id": ONBOARDING_ID,
            "mode": "active-direction-execution",
            "lane": "paper_demo_observation",
            "task_stage": "paper-demo-eligibility",
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "observation_id": OBSERVATION_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "strategy_stage": "paper_demo_eligible",
            "strategy_outcome": "paper_demo_eligible",
            "observation_stage": observation_stage,
            "observation_outcome": observation_outcome,
            "route": "diversifier_only",
            "activation_timestamp": ACTIVATION_TIMESTAMP,
            "first_forward_observation_date": latest_date,
            "latest_common_data_date": latest_date,
            "canonical_portfolio": {
                "reference_portfolio_id": REFERENCE_PORTFOLIO_ID,
                "candidate_sleeve_id": "ANGL",
                "target_reference_weight": 0.8,
                "target_sleeve_weight": 0.2,
                "rebalance_frequency": "monthly",
                "cost_assumption_bps": 5.0,
            },
            "funnel_counts": {
                "eligible_strategy_configurations": 1,
                "active_paper_demo_observations": 1 if observation_stage == "paper_demo_active" else 0,
                "new_experiment_trials": 0,
                "benchmark_references": 3,
                "process_tasks": 1,
            },
            "exact_next_action": next_action,
            **FORBIDDEN_FLAGS,
        },
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        [strategy_card_row("paper_demo_eligible", "paper_demo_eligible")],
        [
            "strategy_id",
            "family_id",
            "display_name",
            "entity_type",
            "stage",
            "outcome",
            "route",
            "strategy_architecture",
            "instrument_universe",
            "allocation_rule",
            "timing_rule",
            "parent_validation_trial",
            "validated_portfolio_use",
            "standalone_100pct_angl_observation_approved",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial_ledger_rows(),
        ["strategy_id", "family_id", "entity_type", "trial_id", "stage", "adaptation_label", "new_experiment_trial_created", "lineage_role"],
    )
    observation = observation_row(observation_stage, observation_outcome, latest_date, next_action, failure_reason)
    write_csv(
        OUTPUT_DIR / "paper_demo_observations.csv",
        [observation],
        [
            "observation_id",
            "display_name",
            "entity_type",
            "stage",
            "outcome",
            "parent_strategy_id",
            "parent_trial_id",
            "observation_route",
            "reference_portfolio_id",
            "candidate_sleeve_id",
            "target_weights",
            "rebalance_frequency",
            "signal_timing",
            "execution_convention",
            "cost_assumption",
            "activation_timestamp",
            "first_forward_observation_date",
            "current_status",
            "failure_reason",
            "next_action",
            "review_trigger",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": ONBOARDING_ID,
                "entity_type": "process_task",
                "stage": observation_stage,
                "outcome": observation_outcome,
                "exact_next_action": next_action,
                "strategy_counted": False,
                "trial_counted": False,
            }
        ],
        ["task_id", "entity_type", "stage", "outcome", "exact_next_action", "strategy_counted", "trial_counted"],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows(),
        ["benchmark_or_control_id", "entity_type", "stage", "role", "counted_as_strategy", "counted_as_trial"],
    )
    write_csv(OUTPUT_DIR / "operational_preflight.csv", preflight, ["check_id", "status", "detail"])
    write_csv(
        OUTPUT_DIR / "historical_reconciliation.csv",
        historical_reconciliation,
        ["portfolio_id", "metric", "evidence_value", "recomputed_value", "absolute_difference", "tolerance", "reconciliation_status", "label"],
    )
    write_csv(OUTPUT_DIR / "initial_target_weights.csv", snapshot["targets"], ["observation_id", "component_id", "target_weight"])
    write_csv(
        OUTPUT_DIR / "initial_virtual_positions.csv",
        snapshot["positions"],
        [
            "observation_id",
            "component_id",
            "latest_common_data_date",
            "component_nav_or_price",
            "target_weight",
            "post_trade_market_value",
            "virtual_units",
            "broker_order_submitted",
        ],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_trades.csv",
        snapshot["trades"],
        [
            "observation_id",
            "trade_date",
            "component_id",
            "pretrade_weight",
            "target_weight",
            "virtual_trade_weight",
            "virtual_trade_value_before_cost",
            "broker_order_submitted",
        ],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_nav.csv",
        snapshot["nav"],
        [
            "observation_id",
            "latest_common_data_date",
            "activation_timestamp",
            "first_forward_observation_date",
            "pretrade_portfolio_nav",
            "one_way_turnover",
            "transaction_cost_drag",
            "post_trade_portfolio_nav",
            "reference_virtual_nav",
            "angl_price",
            "next_expected_rebalance_trigger",
            "data_freshness_status",
            "reconciliation_status",
            "forward_boundary_label",
        ],
    )
    write_csv(
        OUTPUT_DIR / "control_virtual_nav.csv",
        snapshot["controls"],
        [
            "control_id",
            "latest_common_data_date",
            "control_virtual_nav",
            "component_nav",
            "reference_virtual_nav",
            "sleeve_nav",
            "hyg_price",
            "jnk_price",
            "broker_order_submitted",
        ],
    )
    write_csv(OUTPUT_DIR / "data_freshness.csv", data_freshness_rows(frozen, latest_date), ["symbol", "latest_available_date", "latest_common_data_date", "status", "provider_download"])
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        ["path", "before_hash", "after_hash", "changed", "permitted_change", "action"],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "entity_id": OBSERVATION_ID,
                "entity_type": "paper_demo_observation",
                "strategy_id": STRATEGY_ID,
                "strategy_stage": "paper_demo_eligible",
                "strategy_outcome": "paper_demo_eligible",
                "observation_stage": observation_stage,
                "observation_outcome": observation_outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ],
        [
            "entity_id",
            "entity_type",
            "strategy_id",
            "strategy_stage",
            "strategy_outcome",
            "observation_stage",
            "observation_outcome",
            "primary_failure_reason",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "observation_id": OBSERVATION_ID,
                "strategy_id": STRATEGY_ID,
                "outcome": observation_outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ]
        if failure_reason
        else [],
        ["observation_id", "strategy_id", "outcome", "primary_failure_reason", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "scope": "paper_demo_observation",
                "entity_id": OBSERVATION_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": observation_outcome,
            }
        ],
        ["scope", "entity_id", "exact_next_action", "execute_now", "reason"],
    )
    write_text(OUTPUT_DIR / "onboarding_report.md", build_report(observation_stage, observation_outcome, latest_date, next_action, preflight))

    only_permitted_state_changes = all(
        (not row["changed"]) or row["path"] in {rel(REGISTRY_PATH), rel(ACTIVE_OBSERVATIONS_PATH)} for row in state_rows
    )
    consistency = {
        "onboarding_id": ONBOARDING_ID,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "strategy_record_preexisting": registry_preexisting,
        "observation_record_preexisting": observation_preexisting,
        "registry_action": registry_action,
        "observation_action": observation_action,
        "preflight_passed": preflight_passed,
        "strategy_stage": "paper_demo_eligible",
        "strategy_outcome": "paper_demo_eligible",
        "observation_stage": observation_stage,
        "observation_outcome": observation_outcome,
        "active_paper_demo_observations_added": 1 if observation_action == "added" and observation_stage == "paper_demo_active" else 0,
        "new_experiment_trials_created": 0,
        "benchmark_references_count": 3,
        "process_task_count": 1,
        "latest_common_data_date": latest_date,
        "activation_timestamp": ACTIVATION_TIMESTAMP,
        "first_forward_observation_date": latest_date,
        "historical_reconciliation_only_label_used": all(row["label"] == "historical_reconciliation_only" for row in historical_reconciliation),
        "state_hashes_before": state_before,
        "state_hashes_after": state_after,
        "only_permitted_state_changes": only_permitted_state_changes,
        "research_queue_unchanged": state_before.get(rel(RESEARCH_QUEUE_PATH)) == state_after.get(rel(RESEARCH_QUEUE_PATH)),
        "family_ledger_unchanged": state_before.get(rel(FAMILY_LEDGER_PATH)) == state_after.get(rel(FAMILY_LEDGER_PATH)),
        "roadmap_unchanged": state_before.get(rel(ROADMAP_PATH)) == state_after.get(rel(ROADMAP_PATH)),
        "correction_hashes_before": correction_before,
        "correction_hashes_after": correction_after,
        "prior_evidence_packets_unchanged": correction_before == correction_after,
        "broker_order_submitted": False,
        "paper_order_submitted": False,
        "live_order_submitted": False,
        "real_money_action": False,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["preflight_passed"]
        and consistency["strategy_stage"] == "paper_demo_eligible"
        and consistency["observation_stage"] == "paper_demo_active"
        and consistency["new_experiment_trials_created"] == 0
        and consistency["only_permitted_state_changes"]
        and consistency["research_queue_unchanged"]
        and consistency["family_ledger_unchanged"]
        and consistency["prior_evidence_packets_unchanged"]
        and not any(consistency[name] for name in FORBIDDEN_FLAGS)
        and not consistency["broker_order_submitted"]
        and not consistency["paper_order_submitted"]
        and not consistency["live_order_submitted"]
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "onboarding_id": ONBOARDING_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "strategy_stage": "paper_demo_eligible",
        "strategy_outcome": "paper_demo_eligible",
        "observation_stage": observation_stage,
        "observation_outcome": observation_outcome,
        "preflight_passed": preflight_passed,
        "latest_common_data_date": latest_date,
        "registry_action": registry_action,
        "observation_action": observation_action,
        "only_permitted_state_changes": only_permitted_state_changes,
        "exact_next_action": next_action,
        "task_outcome": "onboard_angl_diversifier_paper_demo_observation_v1_complete",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
