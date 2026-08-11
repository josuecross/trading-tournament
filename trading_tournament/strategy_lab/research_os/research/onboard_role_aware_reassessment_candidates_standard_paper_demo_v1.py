from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import (
    record_psar_standard_paper_demo_observation_v1 as standard_obs,
)


TASK_ID = "onboard_role_aware_reassessment_candidates_standard_paper_demo_v1"
MODE = "paper-demo-eligibility-and-standard-onboarding"
STAGE = "paper-demo-onboarding"
OUTCOME_ONBOARDED = "role_aware_candidates_standard_paper_demo_onboarded"
OUTCOME_PARTIAL = "role_aware_candidates_standard_paper_demo_onboarding_partial"
OUTCOME_BLOCKED = "role_aware_candidates_standard_paper_demo_onboarding_blocked"
NEXT_ONBOARDED = "record_role_aware_candidates_standard_paper_demo_observations_v1"
NEXT_PARTIAL = "direction_owner_review_role_aware_onboarding_partial_v1"
NEXT_BLOCKED = "direction_owner_review_role_aware_onboarding_block_v1"
ELIGIBILITY_BASIS = "role_aware_robustness_reassessment_positive_v1"
CURRENT_STATE_LABEL = "standard_observation_current_state_initialization_not_performance"

INITIAL_CAPITAL = 3000.0
PRIMARY_COST_BPS = 5.0
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"
REFERENCE_OBSERVATION_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
REFERENCE_WEIGHT = 0.80
SLEEVE_WEIGHT = 0.20

OUTPUT_DIR = ROOT / "evidence" / "paper_demo_onboarding" / TASK_ID / "latest"
BASELINE_PATH = OUTPUT_DIR / "_baseline_state.json"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = (
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
)
ROLE_STANDARD_PATH = (
    ROOT / "strategy_lab" / "research_os" / "methodology" / "role_aware_robustness_standard_v1.yaml"
)
AUDIT_DIR = (
    ROOT
    / "evidence"
    / "methodology"
    / "audit_and_standardize_role_aware_robustness_gates_v1"
    / "latest"
)
REASSESSMENT_DIR = (
    ROOT
    / "evidence"
    / "methodology"
    / "adopt_role_aware_robustness_standard_and_reassess_v1"
    / "latest"
)

MCA_ID = "varadi_minimum_correlation_8etf_60d_weekly_v1"
HYG_ID = "schwoerer_hyg_ema100_spy_bil_v1"
D1_ID = "factory_v1_spy_trend_quality_state_d1"

MCA_OBSERVATION_ID = "paper_demo_varadi_mca8_weekly_v1"
HYG_OBSERVATION_ID = "paper_demo_schwoerer_hyg_ema100_spy_bil_v1"
D1_OBSERVATION_ID = "paper_demo_factory_v1_trend_quality_20pct_diversifier_v1"

MCA_RISK_ASSETS = ("SPY", "QQQ", "EEM", "IWM", "EFA", "TLT", "IYR", "GLD")
MCA_SYMBOLS = (*MCA_RISK_ASSETS, "BIL")
HYG_SYMBOLS = ("HYG", "SPY", "BIL")
D1_SYMBOLS = ("SPY", "BIL")

STANDARD_FRAMEWORK_OBSERVATIONS = {
    "VM": "paper_forward_vm_quality_lowvol_proxy_v1",
    "DSR": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "USCI": "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    "VM_DSR_USCI_COMBO": REFERENCE_OBSERVATION_ID,
    "FAA": "paper_demo_faa_4m_top3_v1",
    "DECELERATED_PSAR": "paper_demo_decelerated_psar_20pct_diversifier_v1",
}

PROTECTED_PATHS = (
    ROLE_STANDARD_PATH,
    AUDIT_DIR,
    REASSESSMENT_DIR,
    ROOT / "evidence" / "public_source_strategy_intake" / "accepted_47_selective_source_backed_intake_v2" / "latest",
    ROOT / "evidence" / "robustness" / "accepted_47_source_backed_v2_two_candidate_final_robustness_v1" / "latest",
    ROOT / "evidence" / "robustness" / "technical_factory_v1_trend_quality_diversifier_robustness_v1" / "latest",
    ROOT / "evidence" / "paper_demo_onboarding" / "correct_faa_stage_and_onboard_paper_demo_observation_v1" / "latest",
    ROOT / "evidence" / "paper_demo_onboarding" / "correct_psar_stage_and_onboard_paper_demo_observation_v1" / "latest",
    ROOT / "evidence" / "paper_demo_observation" / "record_faa_standard_paper_demo_observation_v1",
    ROOT / "evidence" / "paper_demo_observation" / "record_psar_standard_paper_demo_observation_v1",
    ROOT / "data" / "cache",
    ROOT / "evidence" / "cache",
    ROOT / "paper_forward_observations" / "paper_forward_vm_quality_lowvol_proxy_v1",
    ROOT / "paper_forward_observations" / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
    ROOT / "paper_forward_observations" / REFERENCE_OBSERVATION_ID,
    ROOT / "paper_forward_observations" / "paper_demo_faa_4m_top3_v1",
    ROOT / "paper_forward_observations" / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    ROOT / "paper_forward_observations" / "paper_forward_angl_20pct_diversifier_v1",
    ROOT / "paper_forward_observations" / "paper_forward_ivts_unfiltered_20pct_diversifier_v1",
    ROOT / ".env.local",
    ROOT / "config.yaml",
)

STANDARD_CORE_LEDGER_FIELDS = (
    "observation_id",
    "date",
    "row_type",
    "continuity_from_original_activation",
    "prior_interval_status",
    "initial_virtual_capital",
    "post_cost_equity",
    "initialization_cost",
    "target_weights",
    "holdings",
    "shares",
    "cash",
    "signal_date",
    "rebalance_reference_date",
    "data_snapshot_hashes",
    "strategy_fingerprint",
    "orders_created",
    "broker_calls",
    "status",
)

STANDARD_STANDALONE_LEDGER_FIELDS = STANDARD_CORE_LEDGER_FIELDS + (
    "target_turnover",
    "transaction_cost",
    "intended_execution_date",
    "completed_execution_date",
    "missing_data_events",
    "blocked_execution_reason",
    "rule_deviations",
)

STANDARD_COMPOSITE_LEDGER_FIELDS = STANDARD_CORE_LEDGER_FIELDS + (
    "reference_component_values",
    "reference_component_weights",
    "d1_signal_state",
    "d1_sleeve_target",
    "combined_target_weights",
    "inner_turnover",
    "outer_turnover",
    "total_turnover",
    "transaction_cost",
    "intended_execution_date",
    "completed_execution_date",
    "missing_data_events",
    "blocked_execution_reason",
    "rule_deviations",
)

REQUIRED_OUTPUTS = {
    "onboarding_manifest.yaml",
    "methodology_and_reassessment_reconciliation.csv",
    "candidate_eligibility_before_after.csv",
    "strategy_and_trial_lineage.csv",
    "standard_framework_compatibility.csv",
    "mca_current_state_reconciliation.csv",
    "hyg_current_state_reconciliation.csv",
    "d1_reference_state_reconciliation.csv",
    "d1_sleeve_state_reconciliation.csv",
    "paper_demo_observation_records.csv",
    "virtual_initialization_records.csv",
    "active_observations_before_after.csv",
    "benchmark_reference_reconciliation.csv",
    "state_change_manifest.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "onboarding_report.md",
}


CANDIDATES = (
    {
        "key": "MCA",
        "strategy_id": MCA_ID,
        "observation_id": MCA_OBSERVATION_ID,
        "display_name": "Minimum Correlation Eight-ETF Weekly Allocation",
        "family_id": "minimum_correlation_dynamic_diversification",
        "architecture": "weekly_long_only_correlation_transformation_inverse_volatility_allocation",
        "source_lineage": "varadi_kapler_bee_rittenhouse_minimum_correlation_2012",
        "reassessment_trial_id": "role_aware_robustness_reassessment_v1__mca8__child",
        "parent_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__mca8__child",
        "primary_role": "dynamic_multi_asset_allocation_strategy",
        "route": "standalone_only",
        "instrument_universe": "SPY|QQQ|EEM|IWM|EFA|TLT|IYR|GLD|BIL",
        "eligible_route": "standalone_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "reassessed_outcome": "robustness_positive",
        "parameters": {
            "formation_return_sessions": 60,
            "required_common_daily_returns": 60,
            "rebalance_frequency": "weekly",
            "signal": "final_completed_regular_session_of_week",
            "execution": "following_regular_session_close",
            "fallback_asset": "BIL",
            "reduced_universe_allowed": False,
            "asset_caps": False,
            "leverage": False,
            "shorting": False,
            "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        },
        "benchmarks": (
            "ordinary_inverse_volatility_control",
            "static_mca_average_weight_control",
            "equal_weight_8etf_control",
            "60_40_spy_tlt_control",
            "BIL_cash_control",
        ),
    },
    {
        "key": "HYG",
        "strategy_id": HYG_ID,
        "observation_id": HYG_OBSERVATION_ID,
        "display_name": "HYG 100-Day EMA Credit-State SPY/BIL",
        "family_id": "high_yield_credit_signal_equity_state",
        "architecture": "daily_cross_asset_credit_trend_equity_cash_state",
        "source_lineage": "martin_schwoerer_hyg_credit_signal_2025",
        "reassessment_trial_id": "role_aware_robustness_reassessment_v1__hyg_ema100__child",
        "parent_trial_id": "accepted_47_source_backed_v2_two_candidate_final_robustness_v1__hyg_ema100__child",
        "primary_role": "defensive_equity_timing_strategy",
        "route": "standalone_only",
        "instrument_universe": "HYG|SPY|BIL",
        "eligible_route": "standalone_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "reassessed_outcome": "robustness_positive",
        "parameters": {
            "ema_sessions": 100,
            "ema_alpha": 2.0 / 101.0,
            "ema_initialization": "mean_first_100_valid_closes",
            "strict_above_target": {"SPY": 1.0, "BIL": 0.0},
            "strict_below_target": {"SPY": 0.0, "BIL": 1.0},
            "equality": "retain_current_target",
            "buffer": False,
            "hysteresis": False,
            "spy_confirmation": False,
            "btal": False,
            "weekly_filter": False,
            "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        },
        "benchmarks": (
            "SPY_EMA100_self_trend_control",
            "HYG_SMA100_control",
            "static_exposure_match_control",
            "SPY_buy_and_hold_control",
            "BIL_cash_control",
        ),
    },
    {
        "key": "D1",
        "strategy_id": D1_ID,
        "observation_id": D1_OBSERVATION_ID,
        "display_name": "Factory V1 SPY Trend-Quality D1 20% Diversifier",
        "family_id": "regression_trend_quality",
        "architecture": "long_only_log_price_regression_slope_and_r2_state",
        "source_lineage": "internal_technical_strategy_factory_v1:factory_v1_spy_trend_quality_state",
        "reassessment_trial_id": "role_aware_robustness_reassessment_v1__d1_diversifier__child",
        "parent_trial_id": "technical_factory_v1_trend_quality_diversifier_robustness_v1__child",
        "primary_role": "20pct_diversifier_sleeve",
        "route": "20pct_diversifier_only",
        "instrument_universe": "SPY|BIL",
        "eligible_route": "20pct_diversifier_only",
        "original_outcome": "robustness_mixed",
        "original_failure_reason": "concentration_risk",
        "reassessed_outcome": "robustness_positive",
        "parameters": {
            "lookback_adjusted_closes": 60,
            "regression": "log_SPY_close_on_session_index_0_to_59",
            "annualized_slope": "exp(slope*252)-1",
            "minimum_r_squared": 0.25,
            "positive_slope_required": True,
            "reference_id": REFERENCE_ID,
            "reference_weight": REFERENCE_WEIGHT,
            "candidate_sleeve_weight": SLEEVE_WEIGHT,
            "outer_rebalance": "monthly",
            "inner_state_change": "independent_daily_completed_close_signal",
            "primary_cost_bps_per_one_way_turnover": PRIMARY_COST_BPS,
        },
        "benchmarks": (
            "100pct_frozen_reference",
            "80pct_reference_20pct_D1_slope_only_control",
            "80pct_reference_20pct_static_exposure_control",
            "80pct_reference_20pct_SPY_buy_and_hold",
            "80pct_reference_20pct_BIL",
        ),
    },
)


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return sha256_bytes(path.read_bytes())


def tree_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return file_hash(path)
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def map_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {relative(path): tree_hash(path) for path in paths}


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(inner) for inner in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return value
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def csv_value(value: Any) -> str:
    value = canonicalize(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def fields_for(rows: list[dict[str, Any]], leading: Iterable[str]) -> list[str]:
    fields = list(leading)
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]], leading: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields_for(rows, leading)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def write_yaml_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(canonicalize(payload), sort_keys=False, width=110, allow_unicode=False),
        encoding="utf-8",
    )


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(canonicalize(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def active_entries(text: str | None = None) -> list[dict[str, Any]]:
    payload = yaml.safe_load(
        ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8") if text is None else text
    ) or {}
    return list(payload.get("active_observations", []))


def registry_entries(text: str | None = None) -> list[dict[str, Any]]:
    payload = yaml.safe_load(
        REGISTRY_PATH.read_text(encoding="utf-8") if text is None else text
    ) or {}
    return list(payload.get("strategies", []))


def observation_dir(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id


def ledger_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / "component_forward_ledger.csv"


def active_yaml_path(observation_id: str) -> Path:
    return observation_dir(observation_id) / "active_observation.yaml"


def ordered_union(*groups: Iterable[str]) -> tuple[str, ...]:
    symbols: list[str] = []
    for group in groups:
        for symbol in group:
            if symbol not in symbols:
                symbols.append(symbol)
    return tuple(symbols)


def load_or_create_baseline(started: datetime) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    active_text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry = registry_entries(registry_text)
    active = active_entries(active_text)
    payload = {
        "created_utc": started.isoformat(),
        "registry_hash_before": file_hash(REGISTRY_PATH),
        "active_observations_hash_before": file_hash(ACTIVE_OBSERVATIONS_PATH),
        "registry_present_before": {
            candidate["strategy_id"]: any(
                row.get("strategy_id") == candidate["strategy_id"]
                for row in registry
            )
            for candidate in CANDIDATES
        },
        "active_observation_present_before": {
            candidate["observation_id"]: any(
                row.get("observation_id") == candidate["observation_id"]
                for row in active
            )
            for candidate in CANDIDATES
        },
        "observation_dir_present_before": {
            candidate["observation_id"]: observation_dir(candidate["observation_id"]).exists()
            for candidate in CANDIDATES
        },
        "protected_hashes_before": map_hashes(PROTECTED_PATHS),
    }
    write_json_file(BASELINE_PATH, payload)
    return payload


def latest_regular_session_before_or_equal(value: date) -> date:
    cursor = value
    while not standard_obs.repair.prior_activation.is_regular_session(cursor):
        cursor -= timedelta(days=1)
    return cursor


def is_final_regular_session_of_week(value: date) -> bool:
    next_session = standard_obs.repair.prior_activation.next_regular_session(value)
    return value.isocalendar()[:2] != next_session.isocalendar()[:2]


def latest_weekly_signal_on_or_before(value: date) -> date:
    cursor = latest_regular_session_before_or_equal(value)
    while not is_final_regular_session_of_week(cursor):
        cursor = standard_obs.repair.prior_activation.previous_regular_session(cursor)
    return cursor


def next_weekly_signal_after(value: date) -> date:
    cursor = standard_obs.repair.prior_activation.next_regular_session(value)
    while not is_final_regular_session_of_week(cursor):
        cursor = standard_obs.repair.prior_activation.next_regular_session(cursor)
    return cursor


def next_execution_after_signal(signal_date: date) -> date:
    return standard_obs.repair.prior_activation.next_regular_session(signal_date)


def first_performance_after_execution(execution_date: date) -> date:
    return standard_obs.repair.prior_activation.next_regular_session(execution_date)


def close_series(frames: dict[str, pd.DataFrame], symbol: str) -> pd.Series:
    frame = frames[symbol]
    return pd.Series(
        pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(frame["date"]),
        name=symbol,
    ).sort_index()


def close_matrix(frames: dict[str, pd.DataFrame], symbols: Iterable[str]) -> pd.DataFrame:
    return pd.concat([close_series(frames, symbol) for symbol in symbols], axis=1).sort_index()


def source_hash_for_symbols(
    frames: dict[str, pd.DataFrame], symbols: Iterable[str], through_date: date
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    cutoff = through_date.isoformat()
    for symbol in symbols:
        frame = frames[symbol]
        subset = frame.loc[frame["date"] <= cutoff].to_dict(orient="records")
        hashes[symbol] = canonical_hash(subset)
    return hashes


def symbol_has_session(frames: dict[str, pd.DataFrame], symbol: str, session: date) -> bool:
    frame = frames.get(symbol, pd.DataFrame())
    return not frame.empty and bool((frame["date"] == session.isoformat()).any())


def latest_symbol_session(frames: dict[str, pd.DataFrame], symbol: str) -> date | None:
    frame = frames.get(symbol, pd.DataFrame())
    if frame.empty:
        return None
    return date.fromisoformat(str(frame.iloc[-1]["date"]))


def load_reused_normalized_market_data(symbols: tuple[str, ...]) -> dict[str, Any] | None:
    normalized_dir = OUTPUT_DIR / "normalized"
    raw_dir = OUTPUT_DIR / "raw"
    if not normalized_dir.exists():
        return None
    frames: dict[str, pd.DataFrame] = {}
    normalized_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        path = normalized_dir / f"{symbol}.csv"
        if not path.exists():
            return None
        frame = pd.read_csv(path)
        if not frame.empty:
            frame = frame[["date", "timestamp", "open", "high", "low", "close", "volume"]]
            frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        frames[symbol] = frame
        normalized_rows.append(
            {
                "symbol": symbol,
                "path": relative(path),
                "normalized_hash": file_hash(path),
                "row_count": len(frame),
                "first_date": "" if frame.empty else frame.iloc[0]["date"],
                "last_date": "" if frame.empty else frame.iloc[-1]["date"],
                "reused_current_task_snapshot": True,
            }
        )
        coverage_rows.append(
            {
                "symbol": symbol,
                "first_date": "" if frame.empty else frame.iloc[0]["date"],
                "last_date": "" if frame.empty else frame.iloc[-1]["date"],
                "row_count": len(frame),
                "reused_current_task_snapshot": True,
            }
        )
    return {
        "attempt": {
            "provider": "alpaca_market_data",
            "provider_role": "existing_standard_read_only_paper_demo_data_path",
            "attempted": False,
            "reused_current_task_normalized_snapshot": True,
            "bounded_cycles": 0,
            "bounded_cycles_total_for_task": 1 if raw_dir.exists() else 0,
            "symbols": list(symbols),
            "status": "reused_current_task_normalized_data_snapshot",
            "row_count": sum(len(frame) for frame in frames.values()),
            "account_endpoint_called": False,
            "position_endpoint_called": False,
            "order_endpoint_called": False,
            "broker_calls": 0,
            "orders_created": 0,
        },
        "raw_rows": [],
        "normalized_rows": normalized_rows,
        "coverage_rows": coverage_rows,
        "frames": frames,
        "success": True,
    }


def market_data_ready_for_onboarding(
    market_data: dict[str, Any], latest_completed: date
) -> tuple[bool, list[str]]:
    frames = market_data.get("frames", {})
    missing: list[str] = []
    for symbol in ordered_union(MCA_SYMBOLS, HYG_SYMBOLS, D1_SYMBOLS):
        if not symbol_has_session(frames, symbol, latest_completed):
            missing.append(symbol)
    return not missing, missing


def normal_cdf(value: float, mean: float, std: float) -> float:
    if std <= 0 or not math.isfinite(std):
        return 0.5
    z = (value - mean) / (std * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def mca_target(
    frames: dict[str, pd.DataFrame], signal_date: date
) -> tuple[dict[str, float], dict[str, Any]]:
    prices = close_matrix(frames, MCA_RISK_ASSETS).loc[: pd.Timestamp(signal_date)]
    common = prices.dropna().tail(61)
    if len(common) < 61:
        return (
            {"BIL": 1.0},
            {
                "status": "fallback_insufficient_common_daily_closes",
                "common_close_count": int(len(common)),
                "target": {"BIL": 1.0},
            },
        )
    returns = common.pct_change().dropna()
    if len(returns) != 60:
        return (
            {"BIL": 1.0},
            {
                "status": "fallback_insufficient_common_daily_returns",
                "common_return_count": int(len(returns)),
                "target": {"BIL": 1.0},
            },
        )
    correlation = returns.corr().to_numpy(dtype=float)
    off_diag = correlation[~np.eye(correlation.shape[0], dtype=bool)]
    mu = float(np.mean(off_diag))
    sigma = float(np.std(off_diag, ddof=1))
    adjusted = np.zeros_like(correlation)
    for row in range(correlation.shape[0]):
        for column in range(correlation.shape[1]):
            if row == column:
                adjusted[row, column] = 0.0
            else:
                adjusted[row, column] = 1.0 - normal_cdf(float(correlation[row, column]), mu, sigma)
    row_scores = adjusted.sum(axis=1) / (adjusted.shape[1] - 1)
    ranks = pd.Series(-row_scores, index=MCA_RISK_ASSETS).rank(method="average").to_numpy(dtype=float)
    q_vector = ranks / ranks.sum()
    transformed = q_vector @ adjusted
    volatilities = returns.std(ddof=1).reindex(MCA_RISK_ASSETS).to_numpy(dtype=float)
    raw = transformed / volatilities
    if not np.isfinite(raw).all() or float(raw.sum()) <= 0:
        target = {"BIL": 1.0}
        status = "fallback_invalid_minimum_correlation_transform"
    else:
        weights = raw / raw.sum()
        target = {symbol: float(weights[index]) for index, symbol in enumerate(MCA_RISK_ASSETS)}
        status = "diagnostic_target_calculated_for_expired_weekly_signal"
    return (
        target,
        {
            "status": status,
            "signal_date": signal_date.isoformat(),
            "formation_first_close": common.index[0].date().isoformat(),
            "formation_last_close": common.index[-1].date().isoformat(),
            "common_return_count": int(len(returns)),
            "mu_rho": mu,
            "sigma_rho": sigma,
            "row_scores": {symbol: float(row_scores[index]) for index, symbol in enumerate(MCA_RISK_ASSETS)},
            "rank_weights": {symbol: float(q_vector[index]) for index, symbol in enumerate(MCA_RISK_ASSETS)},
            "asset_volatilities": {
                symbol: float(volatilities[index]) for index, symbol in enumerate(MCA_RISK_ASSETS)
            },
            "target": target,
            "asset_caps_added": False,
            "reduced_universe_used": False,
            "state_role": CURRENT_STATE_LABEL,
        },
    )


def hyg_ema100_state(frames: dict[str, pd.DataFrame], signal_date: date) -> dict[str, Any]:
    series = close_series(frames, "HYG").dropna().loc[: pd.Timestamp(signal_date)]
    if len(series) < 100:
        raise ValueError("HYG EMA100 requires at least 100 completed closes")
    alpha = 2.0 / 101.0
    ema = float(series.iloc[:100].mean())
    target = {"SPY": 0.0, "BIL": 1.0}
    relation = "warming_up"
    last_date = series.index[99]
    last_close = float(series.iloc[99])
    if last_close > ema:
        target = {"SPY": 1.0, "BIL": 0.0}
        relation = "strictly_above"
    elif last_close < ema:
        target = {"SPY": 0.0, "BIL": 1.0}
        relation = "strictly_below"
    else:
        relation = "equal_retain_current_target"
    for timestamp, close in series.iloc[100:].items():
        ema = alpha * float(close) + (1.0 - alpha) * ema
        last_date = timestamp
        last_close = float(close)
        if last_close > ema:
            target = {"SPY": 1.0, "BIL": 0.0}
            relation = "strictly_above"
        elif last_close < ema:
            target = {"SPY": 0.0, "BIL": 1.0}
            relation = "strictly_below"
        else:
            relation = "equal_retain_current_target"
    return {
        "strategy_id": HYG_ID,
        "signal_date": last_date.date().isoformat(),
        "hyg_close": last_close,
        "ema100": float(ema),
        "ema_alpha": alpha,
        "comparison": relation,
        "target": target,
        "state_role": CURRENT_STATE_LABEL,
        "formula_changed": False,
        "parameters_changed": False,
        "source_hash": canonical_hash(series.reset_index().to_dict(orient="records")),
    }


def d1_state(frames: dict[str, pd.DataFrame], signal_date: date) -> dict[str, Any]:
    spy = close_series(frames, "SPY").dropna().loc[: pd.Timestamp(signal_date)].tail(60)
    if len(spy) < 60:
        raise ValueError("D1 requires 60 SPY adjusted closes")
    y = np.log(spy.to_numpy(dtype=float))
    x = np.arange(len(spy), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    annualized_slope = math.exp(float(slope) * 252.0) - 1.0
    risk_on = bool(annualized_slope > 0.0 and r_squared >= 0.25)
    target = {"SPY": 1.0, "BIL": 0.0} if risk_on else {"SPY": 0.0, "BIL": 1.0}
    return {
        "strategy_id": D1_ID,
        "signal_date": signal_date.isoformat(),
        "lookback_first_session": spy.index[0].date().isoformat(),
        "lookback_last_session": spy.index[-1].date().isoformat(),
        "lookback_close_count": int(len(spy)),
        "regression_slope": float(slope),
        "annualized_slope": annualized_slope,
        "r_squared": float(r_squared),
        "slope_positive": bool(annualized_slope > 0.0),
        "r_squared_threshold_pass": bool(r_squared >= 0.25),
        "target": target,
        "state_role": CURRENT_STATE_LABEL,
        "source_hash": canonical_hash(spy.reset_index().to_dict(orient="records")),
    }


def aggregate_d1_target(reference_target: dict[str, float], sleeve_target: dict[str, float]) -> dict[str, float]:
    symbols = sorted(set(reference_target) | set(sleeve_target) | {"SPY", "BIL"})
    target = {
        symbol: REFERENCE_WEIGHT * reference_target.get(symbol, 0.0)
        + SLEEVE_WEIGHT * sleeve_target.get(symbol, 0.0)
        for symbol in symbols
    }
    target = {symbol: float(weight) for symbol, weight in target.items() if abs(weight) > 1e-15}
    if not math.isclose(sum(target.values()), 1.0, abs_tol=1e-12):
        raise ValueError("D1 combined target does not sum to one")
    if not all(weight >= -1e-15 for weight in target.values()):
        raise ValueError("D1 combined target contains a negative weight")
    return target


def current_state_reconciliation(
    started: datetime, market_data: dict[str, Any]
) -> dict[str, Any]:
    latest_completed = standard_obs.latest_fully_completed_session(started)
    next_daily_execution = standard_obs.next_initialization_close(started, latest_completed)
    first_daily_performance = first_performance_after_execution(next_daily_execution)
    next_weekly_signal = next_weekly_signal_after(latest_completed)
    next_weekly_execution = next_execution_after_signal(next_weekly_signal)
    latest_expired_weekly_signal = latest_weekly_signal_on_or_before(latest_completed)
    latest_expired_weekly_execution = next_execution_after_signal(latest_expired_weekly_signal)
    frames = market_data["frames"]
    latest_ts = pd.Timestamp(latest_completed)

    reference_symbols = tuple(standard_obs.REQUIRED_SYMBOLS)
    missing_reference_symbols = [
        symbol for symbol in reference_symbols if not symbol_has_session(frames, symbol, latest_completed)
    ]
    reference_current_state_available = not missing_reference_symbols
    reference_rows: list[dict[str, Any]]
    component_targets: dict[str, dict[str, float]]
    reference_target: dict[str, float]
    reference_diagnostic_target: dict[str, float] = {}
    reference_diagnostic_component_targets: dict[str, dict[str, float]] = {}
    reference_diagnostic_date = ""
    if reference_current_state_available:
        reference_target, reference_rows, component_targets = standard_obs.reference_current_target(
            frames, latest_ts
        )
        reference_status = "current_reference_target_reconciled"
    else:
        latest_dates = [
            latest_symbol_session(frames, symbol)
            for symbol in reference_symbols
            if latest_symbol_session(frames, symbol) is not None
        ]
        if not latest_dates:
            raise ValueError("no reusable reference component market data available")
        common_reference_date = min(latest_dates)
        (
            reference_diagnostic_target,
            reference_rows,
            reference_diagnostic_component_targets,
        ) = standard_obs.reference_current_target(frames, pd.Timestamp(common_reference_date))
        reference_target = {}
        component_targets = {}
        reference_diagnostic_date = common_reference_date.isoformat()
        reference_status = "pending_latest_reference_common_session"
    d1 = d1_state(frames, latest_completed)
    d1_target = (
        aggregate_d1_target(reference_target, d1["target"])
        if reference_current_state_available
        else {}
    )
    d1_diagnostic_target = (
        aggregate_d1_target(reference_diagnostic_target, d1["target"])
        if reference_diagnostic_target
        else {}
    )
    hyg = hyg_ema100_state(frames, latest_completed)
    expired_mca_target, expired_mca = mca_target(frames, latest_expired_weekly_signal)

    return {
        "latest_completed_session": latest_completed,
        "next_daily_execution": next_daily_execution,
        "first_daily_performance": first_daily_performance,
        "next_weekly_signal": next_weekly_signal,
        "next_weekly_execution": next_weekly_execution,
        "latest_expired_weekly_signal": latest_expired_weekly_signal,
        "latest_expired_weekly_execution": latest_expired_weekly_execution,
        "reference_current_state_available": reference_current_state_available,
        "reference_status": reference_status,
        "missing_reference_symbols": missing_reference_symbols,
        "reference_diagnostic_date": reference_diagnostic_date,
        "reference_target": reference_target,
        "reference_diagnostic_target": reference_diagnostic_target,
        "reference_rows": reference_rows,
        "component_targets": component_targets,
        "reference_diagnostic_component_targets": reference_diagnostic_component_targets,
        "hyg": hyg,
        "d1": d1,
        "d1_combined_target": d1_target,
        "d1_diagnostic_combined_target": d1_diagnostic_target,
        "mca_expired_target": expired_mca_target,
        "mca_expired_state": expired_mca,
        "source_hashes": source_hash_for_symbols(
            frames,
            ordered_union(standard_obs.REQUIRED_SYMBOLS, MCA_SYMBOLS, HYG_SYMBOLS),
            latest_completed,
        ),
    }


def strategy_fingerprint(candidate: dict[str, Any]) -> str:
    payload = {
        "strategy_id": candidate["strategy_id"],
        "family_id": candidate["family_id"],
        "architecture": candidate["architecture"],
        "route": candidate["route"],
        "parameters": candidate["parameters"],
        "eligibility_basis": ELIGIBILITY_BASIS,
        "observation_id": candidate["observation_id"],
    }
    return canonical_hash(payload)


def registry_record(candidate: dict[str, Any], timestamp: str, current: dict[str, Any]) -> dict[str, Any]:
    init_status = initialization_status(candidate, current)
    return {
        "id": candidate["strategy_id"],
        "strategy_id": candidate["strategy_id"],
        "display_name": candidate["display_name"],
        "entity_type": "strategy_lifecycle_record",
        "stage": "paper-demo-eligibility",
        "outcome": "paper_demo_eligible",
        "eligibility": "paper_demo_eligible",
        "eligible_route": candidate["eligible_route"],
        "route": candidate["route"],
        "family_id": candidate["family_id"],
        "strategy_family": candidate["family_id"],
        "strategy_architecture": candidate["architecture"],
        "source_or_research_lineage": candidate["source_lineage"],
        "instrument_universe": candidate["instrument_universe"],
        "exact_source_replication_claimed": False,
        "eligibility_basis": ELIGIBILITY_BASIS,
        "paper_demo_recommendation": "standard_virtual_observation",
        "paper_demo_eligible": True,
        "paper_demo_active": True,
        "paper_forward_active": True,
        "paper_forward_allowed_by_risk_framework": True,
        "status": "active_paper_demo_observation",
        "initialization_status": init_status,
        "rules_frozen": True,
        "parameters": candidate["parameters"],
        "trial_lineage": [
            candidate["parent_trial_id"],
            candidate["reassessment_trial_id"],
        ],
        "historical_original_outcome": candidate["original_outcome"],
        "historical_original_failure_reason": candidate["original_failure_reason"],
        "historical_original_outcome_preserved": True,
        "role_aware_reassessment_trial_id": candidate["reassessment_trial_id"],
        "role_aware_reassessment_outcome": candidate["reassessed_outcome"],
        "role_aware_reassessment_interpretation": "current_authoritative_promotion_evidence",
        "formula_changed": False,
        "parameters_changed": False,
        "universes_changed": False,
        "routes_changed": False,
        "historical_returns_recalculated": False,
        "independent_validation_completed": False,
        "prospective_validation_required": False,
        "paper_demo_observation_id": candidate["observation_id"],
        "latest_evidence_path": relative(OUTPUT_DIR),
        "latest_lifecycle_update_utc": timestamp,
        "real_money_authorized": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "automatic_real_money_promotion": False,
        "next_action": NEXT_ONBOARDED,
        "allowed_next_action": NEXT_ONBOARDED,
        "forbidden_next_actions": [
            "create_new_strategy_configuration",
            "create_new_experiment_trial",
            "create_prospective_validation_stage",
            "create_validation_observation",
            "historical_paper_demo_backfill",
            "change_strategy_rule",
            "change_parameters",
            "change_universe",
            "change_route",
            "add_broker_integration",
            "place_orders",
            "promote_to_real_money",
        ],
        "frozen": True,
        "configuration_fingerprint": strategy_fingerprint(candidate),
    }


def initialization_status(candidate: dict[str, Any], current: dict[str, Any]) -> str:
    if candidate["strategy_id"] == MCA_ID:
        return "pending_first_valid_signal_or_execution"
    if candidate["strategy_id"] == D1_ID and not current.get("reference_current_state_available", False):
        return "pending_first_valid_signal_or_execution"
    return "scheduled_for_first_prospective_execution"


def active_observation_record(
    candidate: dict[str, Any], timestamp: str, current: dict[str, Any]
) -> dict[str, Any]:
    record = {
        "observation_id": candidate["observation_id"],
        "strategy_id": candidate["strategy_id"],
        "entity_type": "paper_demo_observation",
        "stage": STAGE,
        "outcome": OUTCOME_ONBOARDED,
        "state": "active_accepted_frozen_observation",
        "paper_forward_active": True,
        "paper_demo_active": True,
        "protected": True,
        "route": candidate["route"],
        "mode": "virtual_observation",
        "status": "active_paper_demo_observation",
        "initialization_status": initialization_status(candidate, current),
        "activation_timestamp": timestamp,
        "historical_backfill": False,
        "performance_rows": 0,
        "broker_orders": False,
        "paper_broker_orders": False,
        "real_money_authorization": False,
        "next_action": NEXT_ONBOARDED,
    }
    if candidate["strategy_id"] == MCA_ID:
        record.update(
            {
                "pending_reason": "waiting_for_next_completed_weekly_signal_after_current_task_timestamp_no_late_execution",
                "latest_completed_session": current["latest_completed_session"].isoformat(),
                "latest_expired_signal_date": current["latest_expired_weekly_signal"].isoformat(),
                "latest_expired_execution_date": current["latest_expired_weekly_execution"].isoformat(),
                "next_valid_signal_date": current["next_weekly_signal"].isoformat(),
                "next_valid_execution_date": current["next_weekly_execution"].isoformat(),
                "expired_signal_execution_authorized": False,
            }
        )
    elif candidate["strategy_id"] == D1_ID:
        if current.get("reference_current_state_available", False):
            record.update(
                {
                    "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
                    "target_freeze_timestamp": timestamp,
                    "target_freeze_event_label": CURRENT_STATE_LABEL,
                    "scheduled_first_execution_date": current["next_daily_execution"].isoformat(),
                    "first_eligible_performance_date": current["first_daily_performance"].isoformat(),
                    "reference_id": REFERENCE_ID,
                    "reference_observation_id": REFERENCE_OBSERVATION_ID,
                    "reference_weight": REFERENCE_WEIGHT,
                    "sleeve_weight": SLEEVE_WEIGHT,
                }
            )
        else:
            record.update(
                {
                    "pending_reason": "reference_current_state_unavailable_for_latest_completed_session_no_late_execution",
                    "latest_completed_session": current["latest_completed_session"].isoformat(),
                    "reference_status": current["reference_status"],
                    "missing_reference_symbols": current["missing_reference_symbols"],
                    "reference_diagnostic_date": current["reference_diagnostic_date"],
                    "reference_id": REFERENCE_ID,
                    "reference_observation_id": REFERENCE_OBSERVATION_ID,
                    "reference_weight": REFERENCE_WEIGHT,
                    "sleeve_weight": SLEEVE_WEIGHT,
                    "latest_d1_signal_date": current["d1"]["signal_date"],
                    "next_action": NEXT_ONBOARDED,
                }
            )
    else:
        record.update(
            {
                "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
                "target_freeze_timestamp": timestamp,
                "target_freeze_event_label": CURRENT_STATE_LABEL,
                "scheduled_first_execution_date": current["next_daily_execution"].isoformat(),
                "first_eligible_performance_date": current["first_daily_performance"].isoformat(),
            }
        )
    return record


def observation_payload(
    candidate: dict[str, Any], timestamp: str, current: dict[str, Any]
) -> dict[str, Any]:
    base = {
        "observation_id": candidate["observation_id"],
        "base_strategy_id": candidate["strategy_id"],
        "strategy_id": candidate["strategy_id"],
        "family": candidate["family_id"],
        "display_name": candidate["display_name"],
        "strategy_architecture": candidate["architecture"],
        "source_or_research_lineage": candidate["source_lineage"],
        "route": candidate["route"],
        "status": "active_paper_demo_observation",
        "initialization_status": initialization_status(candidate, current),
        "account_type": "simulated_paper_demo_only",
        "observation_mode": "virtual_observation",
        "evidence_source": TASK_ID,
        "frozen": True,
        "rules_frozen": True,
        "paper_forward_active": True,
        "paper_demo_active": True,
        "real_money_authorization": False,
        "real_money_recommendation": False,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "order_placement": False,
        "leverage": False,
        "margin": False,
        "shorting": False,
        "historical_backfill": False,
        "historical_performance_rows_imported": 0,
        "activation_timestamp": timestamp,
        "initial_virtual_capital": INITIAL_CAPITAL,
        "pre_execution_virtual_cash": INITIAL_CAPITAL,
        "pre_execution_virtual_positions": {},
        "pre_execution_virtual_shares": {},
        "current_virtual_equity": INITIAL_CAPITAL,
        "current_target_allocation": {},
        "performance_rows": 0,
        "standard_virtual_accounting": {
            "component_forward_ledger": relative(ledger_path(candidate["observation_id"])),
            "explicit_target_allocations": True,
            "explicit_virtual_positions": True,
            "explicit_virtual_shares": True,
            "explicit_virtual_cash": True,
            "virtual_equity_recorded": True,
            "turnover_recorded": True,
            "transaction_cost_recorded": True,
            "missing_data_events_recorded": True,
            "blocked_virtual_executions_recorded": True,
            "rule_deviations_recorded": True,
            "periodic_observation_reports": True,
        },
        "benchmark_references": list(candidate["benchmarks"]),
        "observation_interpretation": {
            "historical_robustness_complete": True,
            "original_mixed_outcome_preserved_under_original_gate": True,
            "role_aware_reassessment_is_current_promotion_evidence": True,
            "future_evidence_gathering_only": True,
            "future_results_guaranteed": False,
            "automatic_real_money_promotion": False,
        },
        "strategy_fingerprint": strategy_fingerprint(candidate),
        "latest_operational_update_id": TASK_ID,
        "latest_operational_update_evidence_path": relative(OUTPUT_DIR),
        "next_action": NEXT_ONBOARDED,
    }
    if candidate["strategy_id"] == MCA_ID:
        base.update(
            {
                "current_checkpoint_status": "onboarded_pending_first_valid_weekly_signal_or_execution",
                "pending_reason": "waiting_for_next_completed_weekly_signal_after_current_task_timestamp_no_late_execution",
                "latest_completed_session": current["latest_completed_session"].isoformat(),
                "latest_expired_weekly_signal_date": current["latest_expired_weekly_signal"].isoformat(),
                "latest_expired_weekly_execution_date": current["latest_expired_weekly_execution"].isoformat(),
                "latest_expired_diagnostic_target": current["mca_expired_target"],
                "latest_expired_diagnostic_state": current["mca_expired_state"],
                "expired_signal_execution_authorized": False,
                "scheduled_target_allocation": {},
                "scheduled_first_execution_date": "",
                "first_eligible_performance_date": "",
                "next_valid_weekly_signal_date": current["next_weekly_signal"].isoformat(),
                "next_valid_weekly_execution_date": current["next_weekly_execution"].isoformat(),
                "formation_rule": "use_60_common_daily_returns_after_final_completed_regular_session_of_week",
                "fallback_asset": "BIL",
                "asset_caps_added": False,
                "reduced_universe_used": False,
            }
        )
    elif candidate["strategy_id"] == HYG_ID:
        base.update(
            {
                "current_checkpoint_status": "target_frozen_pending_execution",
                "pending_reason": "target_frozen_before_next_eligible_regular_session_close",
                "target_freeze_timestamp": timestamp,
                "target_freeze_event_label": CURRENT_STATE_LABEL,
                "latest_current_state_date": current["latest_completed_session"].isoformat(),
                "latest_hyg_ema100_state": current["hyg"],
                "scheduled_target_allocation": current["hyg"]["target"],
                "scheduled_first_execution_date": current["next_daily_execution"].isoformat(),
                "first_eligible_performance_date": current["first_daily_performance"].isoformat(),
                "target_freeze_hash": canonical_hash(current["hyg"]["target"]),
                "data_snapshot_hashes": {
                    symbol: current["source_hashes"][symbol] for symbol in HYG_SYMBOLS
                },
            }
        )
    else:
        d1_ready = current.get("reference_current_state_available", False)
        base.update(
            {
                "current_checkpoint_status": "target_frozen_pending_execution"
                if d1_ready
                else "onboarded_pending_first_valid_reference_or_execution",
                "pending_reason": "target_frozen_before_next_eligible_regular_session_close"
                if d1_ready
                else "reference_current_state_unavailable_for_latest_completed_session_no_late_execution",
                "latest_current_state_date": current["latest_completed_session"].isoformat(),
                "reference_portfolio": {
                    "reference_id": REFERENCE_ID,
                    "observation_id": REFERENCE_OBSERVATION_ID,
                    "weight": REFERENCE_WEIGHT,
                    "reference_status": current["reference_status"],
                    "missing_reference_symbols": current["missing_reference_symbols"],
                    "target": current["reference_target"] if d1_ready else {},
                    "component_targets": current["component_targets"] if d1_ready else {},
                    "last_stale_diagnostic_reference_date": current["reference_diagnostic_date"],
                    "last_stale_diagnostic_reference_target": current["reference_diagnostic_target"],
                    "last_stale_diagnostic_component_targets": current[
                        "reference_diagnostic_component_targets"
                    ],
                    "diagnostic_target_execution_authorized": False,
                },
                "candidate_sleeve": {
                    "strategy_id": candidate["strategy_id"],
                    "weight": SLEEVE_WEIGHT,
                    "active_asset": "SPY",
                    "defensive_asset": "BIL",
                    "latest_reconciled_signal_date": current["d1"]["signal_date"],
                    "latest_reconciled_target": current["d1"]["target"],
                    "latest_reconciled_state_role": CURRENT_STATE_LABEL,
                },
                "combined_target_status": "target_frozen_pending_execution"
                if d1_ready
                else "pending_current_reference_state_no_late_execution",
                "scheduled_target_allocation": current["d1_combined_target"] if d1_ready else {},
                "scheduled_reference_target": current["reference_target"] if d1_ready else {},
                "scheduled_d1_sleeve_target": current["d1"]["target"] if d1_ready else {},
                "scheduled_first_execution_date": current["next_daily_execution"].isoformat()
                if d1_ready
                else "",
                "first_eligible_performance_date": current["first_daily_performance"].isoformat()
                if d1_ready
                else "",
                "last_stale_diagnostic_combined_target": current["d1_diagnostic_combined_target"],
                "last_stale_diagnostic_target_execution_authorized": False,
                "outer_rebalance_frequency": "monthly",
                "execution": "following_regular_session_close",
                "natural_drift": True,
                "inner_turnover_recorded_separately": True,
                "outer_turnover_recorded_separately": True,
                "transaction_cost_charged_once": True,
                "latest_d1_signal_state": current["d1"],
                "target_freeze_timestamp": timestamp if d1_ready else "",
                "target_freeze_event_label": CURRENT_STATE_LABEL if d1_ready else "",
                "target_freeze_hash": canonical_hash(current["d1_combined_target"])
                if d1_ready
                else "",
                "data_snapshot_hashes": {
                    symbol: current["source_hashes"][symbol] for symbol in ("SPY", "BIL")
                },
            }
        )
    return base


def ledger_fields_for(candidate: dict[str, Any]) -> tuple[str, ...]:
    if candidate["strategy_id"] == D1_ID:
        return STANDARD_COMPOSITE_LEDGER_FIELDS
    return STANDARD_STANDALONE_LEDGER_FIELDS


def write_empty_ledger(path: Path, fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(fields)


def ledger_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _row in csv.reader(handle)) - 1, 0)


def materialize_observation_files(
    candidates: Iterable[dict[str, Any]], timestamp: str, current: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        obs_dir = observation_dir(candidate["observation_id"])
        obs_yaml = active_yaml_path(candidate["observation_id"])
        ledger = ledger_path(candidate["observation_id"])
        before_exists = obs_dir.exists()
        existing_rows = ledger_row_count(ledger)
        if existing_rows > 0:
            action = "preserved_existing_nonempty_standard_observation"
        else:
            obs_dir.mkdir(parents=True, exist_ok=True)
            write_yaml_file(obs_yaml, observation_payload(candidate, timestamp, current))
            write_empty_ledger(ledger, ledger_fields_for(candidate))
            action = "created_or_refreshed_empty_standard_observation"
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "observation_dir": relative(obs_dir),
                "active_observation_yaml": relative(obs_yaml),
                "component_forward_ledger": relative(ledger),
                "dir_existed_before_write": before_exists,
                "ledger_rows_after": ledger_row_count(ledger),
                "historical_backfill": False,
                "performance_rows_created": 0,
                "broker_calls": 0,
                "orders_created": 0,
                "action": action,
            }
        )
    return rows


def prepare_registry_text(
    before: str, records: Iterable[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    entries_before = registry_entries(before)
    updated = before.rstrip()
    rows: list[dict[str, Any]] = []
    for record in records:
        strategy_id = record["strategy_id"]
        count_before = sum(row.get("strategy_id") == strategy_id for row in entries_before)
        if count_before > 1:
            raise ValueError(f"duplicate lifecycle records already present for {strategy_id}")
        if count_before == 0:
            updated += "\n" + yaml.safe_dump(
                [record], sort_keys=False, width=110, allow_unicode=False
            ).rstrip()
            updated += "\n"
            action = "appended_lifecycle_record"
        else:
            action = "verified_existing_lifecycle_record"
        rows.append(
            {
                "strategy_id": strategy_id,
                "before_present": count_before == 1,
                "after_expected_present": True,
                "action": action,
            }
        )
    entries_after = registry_entries(updated)
    for record in records:
        if sum(row.get("strategy_id") == record["strategy_id"] for row in entries_after) != 1:
            raise ValueError(f"lifecycle record count not exactly one for {record['strategy_id']}")
    return updated, rows


def prepare_active_text(
    before: str, records: Iterable[dict[str, Any]], timestamp: str
) -> tuple[str, list[dict[str, Any]]]:
    records = list(records)
    entries_before = active_entries(before)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for record in records:
        observation_id = record["observation_id"]
        count_before = sum(row.get("observation_id") == observation_id for row in entries_before)
        if count_before > 1:
            raise ValueError(f"duplicate active observations already present for {observation_id}")
        if count_before == 0:
            missing.append(record)
            action = "inserted_active_observation"
        else:
            action = "verified_existing_active_observation"
        rows.append(
            {
                "strategy_id": record["strategy_id"],
                "observation_id": observation_id,
                "before_present": count_before == 1,
                "after_expected_present": True,
                "action": action,
            }
        )
    updated = before
    if missing:
        marker = "benchmark_controls:\n"
        if marker not in updated:
            raise ValueError("active observation insertion marker is absent")
        block = yaml.safe_dump(missing, sort_keys=False, width=110, allow_unicode=False)
        updated = updated.replace(marker, block + marker, 1)
    latest_key = "latest_role_aware_reassessment_candidates_standard_paper_demo_onboarding"
    if latest_key not in updated:
        latest = {
            latest_key: {
                "created_utc": timestamp,
                "evidence_path": relative(OUTPUT_DIR),
                "outcome": OUTCOME_ONBOARDED,
                "strategy_ids": [candidate["strategy_id"] for candidate in CANDIDATES],
                "observation_ids": [candidate["observation_id"] for candidate in CANDIDATES],
                "paper_demo_eligible": True,
                "paper_forward_active": True,
                "standard_framework_used": True,
                "custom_prospective_validation_created": False,
                "broker_integration": False,
                "paper_orders": False,
                "live_orders": False,
                "real_money_authorization": False,
                "next_action": NEXT_ONBOARDED,
            }
        }
        updated = updated.rstrip() + "\n" + yaml.safe_dump(
            latest, sort_keys=False, width=110, allow_unicode=False
        )
    entries_after = active_entries(updated)
    for record in records:
        if sum(row.get("observation_id") == record["observation_id"] for row in entries_after) != 1:
            raise ValueError(f"active observation count not exactly one for {record['observation_id']}")
    return updated, rows


def apply_lifecycle_and_active_state(
    timestamp: str, current: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    registry_text = REGISTRY_PATH.read_text(encoding="utf-8")
    active_text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    registry_records = [registry_record(candidate, timestamp, current) for candidate in CANDIDATES]
    active_records = [active_observation_record(candidate, timestamp, current) for candidate in CANDIDATES]
    registry_updated, registry_rows = prepare_registry_text(registry_text, registry_records)
    active_updated, active_rows = prepare_active_text(active_text, active_records, timestamp)
    if registry_updated != registry_text:
        atomic_write_text(REGISTRY_PATH, registry_updated)
    if active_updated != active_text:
        atomic_write_text(ACTIVE_OBSERVATIONS_PATH, active_updated)
    return registry_rows, active_rows


def reconcile_methodology_and_reassessment() -> tuple[list[dict[str, Any]], bool, list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    standard = read_yaml(ROLE_STANDARD_PATH)
    audit_summary = read_csv(AUDIT_DIR / "outcome_summary.csv")
    adoption = read_csv(REASSESSMENT_DIR / "standard_adoption_record.csv")
    reassessment = read_csv(REASSESSMENT_DIR / "reassessment_outcome_summary.csv")
    lineage = read_csv(REASSESSMENT_DIR / "strategy_and_trial_lineage.csv")
    original = read_csv(REASSESSMENT_DIR / "original_vs_reassessed_outcomes.csv")
    eligibility = read_csv(REASSESSMENT_DIR / "paper_demo_eligibility_candidates.csv")

    audit_outcome = audit_summary[0]["outcome"] if audit_summary else ""
    standard_adopted = bool(adoption) and truthy(adoption[0].get("standard_adopted_before_reassessment_metrics_loaded"))
    candidate_ids = [row.get("strategy_id") for row in reassessment]
    expected_ids = [candidate["strategy_id"] for candidate in CANDIDATES]
    rows.append(
        {
            "source": relative(ROLE_STANDARD_PATH),
            "check_id": "authoritative_standard_adopted",
            "expected": "authoritative_project_wide_standard",
            "observed": standard.get("status", ""),
            "status": "pass" if standard.get("status") == "authoritative_project_wide_standard" else "fail",
            "hash": file_hash(ROLE_STANDARD_PATH),
        }
    )
    rows.append(
        {
            "source": relative(AUDIT_DIR / "outcome_summary.csv"),
            "check_id": "methodology_audit_outcome",
            "expected": "robustness_gate_standardization_required",
            "observed": audit_outcome,
            "status": "pass" if audit_outcome == "robustness_gate_standardization_required" else "fail",
            "hash": file_hash(AUDIT_DIR / "outcome_summary.csv"),
        }
    )
    rows.append(
        {
            "source": relative(REASSESSMENT_DIR / "standard_adoption_record.csv"),
            "check_id": "standard_adopted_before_reassessment",
            "expected": "true",
            "observed": standard_adopted,
            "status": "pass" if standard_adopted else "fail",
            "hash": file_hash(REASSESSMENT_DIR / "standard_adoption_record.csv"),
        }
    )
    rows.append(
        {
            "source": relative(REASSESSMENT_DIR / "reassessment_outcome_summary.csv"),
            "check_id": "exactly_three_reassessment_candidates",
            "expected": expected_ids,
            "observed": candidate_ids,
            "status": "pass" if candidate_ids == expected_ids else "fail",
            "hash": file_hash(REASSESSMENT_DIR / "reassessment_outcome_summary.csv"),
        }
    )

    reassessment_by_id = {row["strategy_id"]: row for row in reassessment}
    lineage_by_id = {row["strategy_id"]: row for row in lineage}
    original_by_id = {row["strategy_id"]: row for row in original}
    eligibility_by_id = {row["strategy_id"]: row for row in eligibility}
    unchanged_fields = (
        "formula_changed",
        "parameters_changed",
        "instruments_changed",
        "route_changed",
        "historical_returns_recalculated",
    )
    for candidate in CANDIDATES:
        strategy_id = candidate["strategy_id"]
        reassessed = reassessment_by_id.get(strategy_id, {})
        source_lineage = lineage_by_id.get(strategy_id, {})
        original_row = original_by_id.get(strategy_id, {})
        eligibility_row = eligibility_by_id.get(strategy_id, {})
        candidate_pass = (
            reassessed.get("reassessed_outcome") == "robustness_positive"
            and original_row.get("original_outcome") == candidate["original_outcome"]
            and original_row.get("original_failure_reason") == candidate["original_failure_reason"]
            and truthy(original_row.get("original_outcome_preserved"))
            and all(not truthy(source_lineage.get(field)) for field in unchanged_fields)
            and truthy(eligibility_row.get("eligible_for_direction_owner_paper_demo_review"))
            and not truthy(eligibility_row.get("paper_demo_observation_created"))
            and not truthy(eligibility_row.get("validation_observation_created"))
        )
        rows.append(
            {
                "source": relative(REASSESSMENT_DIR),
                "check_id": f"{candidate['key']}_role_aware_reassessment_eligibility",
                "strategy_id": strategy_id,
                "reassessment_trial_id": candidate["reassessment_trial_id"],
                "expected_reassessed_outcome": "robustness_positive",
                "observed_reassessed_outcome": reassessed.get("reassessed_outcome", ""),
                "original_outcome": original_row.get("original_outcome", ""),
                "original_failure_reason": original_row.get("original_failure_reason", ""),
                "original_outcome_preserved": original_row.get("original_outcome_preserved", ""),
                "formula_changed": source_lineage.get("formula_changed", ""),
                "parameters_changed": source_lineage.get("parameters_changed", ""),
                "universes_changed": source_lineage.get("instruments_changed", ""),
                "routes_changed": source_lineage.get("route_changed", ""),
                "historical_returns_recalculated": source_lineage.get("historical_returns_recalculated", ""),
                "status": "pass" if candidate_pass else "fail",
            }
        )
    for row in rows:
        if row.get("status") != "pass":
            failures.append(str(row.get("check_id")))
    return rows, not failures, failures


def standard_framework_compatibility_rows() -> tuple[list[dict[str, Any]], bool]:
    active = active_entries()
    framework_rows: list[dict[str, Any]] = []
    framework_presence: dict[str, bool] = {}
    for label, observation_id in STANDARD_FRAMEWORK_OBSERVATIONS.items():
        directory = observation_dir(observation_id)
        active_present = any(
            row.get("strategy_id") == observation_id or row.get("observation_id") == observation_id
            for row in active
        )
        framework_presence[label] = active_present and directory.exists()

    faa_ledger = ledger_path("paper_demo_faa_4m_top3_v1")
    psar_ledger = ledger_path("paper_demo_decelerated_psar_20pct_diversifier_v1")
    faa_fields = tuple(next(csv.reader(faa_ledger.open("r", encoding="utf-8-sig", newline=""))))
    psar_fields = tuple(next(csv.reader(psar_ledger.open("r", encoding="utf-8-sig", newline=""))))
    core_schema = all(
        field in faa_fields
        for field in ("target_weights", "holdings", "shares", "cash", "post_cost_equity", "status")
    )
    composite_schema = all(
        field in psar_fields
        for field in (
            "combined_target_weights",
            "inner_turnover",
            "outer_turnover",
            "transaction_cost",
            "missing_data_events",
            "blocked_execution_reason",
            "rule_deviations",
        )
    )
    base_framework_available = all(framework_presence.values()) and core_schema and composite_schema
    candidate_tests = {
        MCA_ID: {
            "supports_weekly_multi_asset_target_vectors": core_schema,
            "supports_eight_risky_plus_bil_fallback": core_schema,
            "supports_explicit_weights": "target_weights" in faa_fields,
            "supports_weekly_virtual_execution": "intended_execution_date" in psar_fields,
            "supports_turnover_and_cost_accounting": "transaction_cost" in psar_fields,
        },
        HYG_ID: {
            "supports_daily_signal_evaluation": "signal_date" in faa_fields,
            "supports_spy_bil_state_changes": core_schema,
            "supports_following_session_execution": "intended_execution_date" in psar_fields,
            "supports_virtual_equity": "post_cost_equity" in faa_fields,
            "supports_missing_data_events": "missing_data_events" in psar_fields,
        },
        D1_ID: {
            "supports_80_20_composite_observation": composite_schema,
            "supports_reference_and_sleeve_aggregation": "combined_target_weights" in psar_fields,
            "supports_independent_inner_outer_changes": all(
                field in psar_fields for field in ("inner_turnover", "outer_turnover")
            ),
            "supports_explicit_holdings_and_costs": all(
                field in psar_fields for field in ("holdings", "shares", "cash", "transaction_cost")
            ),
        },
    }
    for candidate in CANDIDATES:
        checks = candidate_tests[candidate["strategy_id"]]
        framework_rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "framework_examples_inspected": list(STANDARD_FRAMEWORK_OBSERVATIONS.values()),
                "framework_presence": framework_presence,
                "core_ledger_schema_from_faa": core_schema,
                "composite_ledger_schema_from_psar": composite_schema,
                "candidate_requirements": checks,
                "custom_framework_required": False,
                "status": "pass" if base_framework_available and all(checks.values()) else "fail",
            }
        )
    return framework_rows, all(row["status"] == "pass" for row in framework_rows)


def candidate_eligibility_rows(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    registry = registry_entries()
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        after_rows = [row for row in registry if row.get("strategy_id") == candidate["strategy_id"]]
        after = after_rows[0] if after_rows else {}
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "before_lifecycle_record_present": baseline["registry_present_before"][candidate["strategy_id"]],
                "before_stage": "",
                "before_eligibility": "",
                "after_lifecycle_record_count": len(after_rows),
                "after_stage": after.get("stage", ""),
                "after_eligibility": after.get("eligibility", ""),
                "eligibility_basis": after.get("eligibility_basis", ""),
                "paper_demo_recommendation": after.get("paper_demo_recommendation", ""),
                "route": after.get("route", ""),
                "original_outcome_preserved": after.get("historical_original_outcome_preserved", ""),
                "original_outcome": after.get("historical_original_outcome", ""),
                "original_failure_reason": after.get("historical_original_failure_reason", ""),
                "role_aware_reassessment_trial_id": after.get("role_aware_reassessment_trial_id", ""),
                "role_aware_reassessment_outcome": after.get("role_aware_reassessment_outcome", ""),
                "real_money_authorized": after.get("real_money_authorized", ""),
                "broker_integration": after.get("broker_integration", ""),
                "paper_orders": after.get("paper_orders", ""),
                "status": "pass"
                if (
                    len(after_rows) == 1
                    and after.get("stage") == "paper-demo-eligibility"
                    and after.get("eligibility") == "paper_demo_eligible"
                    and after.get("eligibility_basis") == ELIGIBILITY_BASIS
                    and after.get("paper_demo_recommendation") == "standard_virtual_observation"
                    and after.get("real_money_authorized") is False
                )
                else "fail",
            }
        )
    return rows


def lineage_rows_from_reassessment() -> list[dict[str, Any]]:
    lineage = {row["strategy_id"]: row for row in read_csv(REASSESSMENT_DIR / "strategy_and_trial_lineage.csv")}
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        row = lineage.get(candidate["strategy_id"], {})
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "family_id": candidate["family_id"],
                "strategy_architecture": candidate["architecture"],
                "source_or_research_lineage": candidate["source_lineage"],
                "primary_role": candidate["primary_role"],
                "eligible_route": candidate["eligible_route"],
                "parent_trial_id": candidate["parent_trial_id"],
                "reassessment_trial_id": candidate["reassessment_trial_id"],
                "existing_strategy_configuration_carried_forward": row.get(
                    "existing_strategy_configuration_carried_forward", "true"
                ),
                "new_strategy_configuration": row.get("new_strategy_configuration", "false"),
                "formula_changed": row.get("formula_changed", "false"),
                "parameters_changed": row.get("parameters_changed", "false"),
                "universes_changed": row.get("instruments_changed", "false"),
                "routes_changed": row.get("route_changed", "false"),
                "historical_returns_recalculated": row.get(
                    "historical_returns_recalculated", "false"
                ),
                "new_experiment_trial": False,
                "strategy_fingerprint": strategy_fingerprint(candidate),
            }
        )
    return rows


def mca_current_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": MCA_ID,
            "observation_id": MCA_OBSERVATION_ID,
            "latest_completed_session": current["latest_completed_session"].isoformat(),
            "latest_expired_weekly_signal_date": current["latest_expired_weekly_signal"].isoformat(),
            "latest_expired_weekly_execution_date": current["latest_expired_weekly_execution"].isoformat(),
            "latest_expired_diagnostic_target": current["mca_expired_target"],
            "expired_signal_execution_authorized": False,
            "next_valid_weekly_signal_date": current["next_weekly_signal"].isoformat(),
            "next_valid_weekly_execution_date": current["next_weekly_execution"].isoformat(),
            "initialization_status": "pending_first_valid_signal_or_execution",
            "pending_reason": "waiting_for_next_completed_weekly_signal_after_current_task_timestamp_no_late_execution",
            "historical_backfill": False,
            "performance_rows_created": 0,
            "broker_calls": 0,
            "orders_created": 0,
            "state_role": CURRENT_STATE_LABEL,
            "status": "pass",
        }
    ]


def hyg_current_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": HYG_ID,
            "observation_id": HYG_OBSERVATION_ID,
            "latest_completed_session": current["latest_completed_session"].isoformat(),
            "signal_date": current["hyg"]["signal_date"],
            "hyg_close": current["hyg"]["hyg_close"],
            "ema100": current["hyg"]["ema100"],
            "comparison": current["hyg"]["comparison"],
            "target": current["hyg"]["target"],
            "target_freeze_event_label": CURRENT_STATE_LABEL,
            "scheduled_first_execution_date": current["next_daily_execution"].isoformat(),
            "first_eligible_performance_date": current["first_daily_performance"].isoformat(),
            "initialization_status": "scheduled_for_first_prospective_execution",
            "historical_backfill": False,
            "performance_rows_created": 0,
            "broker_calls": 0,
            "orders_created": 0,
            "status": "pass",
        }
    ]


def d1_reference_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    targets = (
        current["component_targets"]
        if current.get("reference_current_state_available", False)
        else current["reference_diagnostic_component_targets"]
    )
    for component_id, target in targets.items():
        rows.append(
            {
                "strategy_id": D1_ID,
                "observation_id": D1_OBSERVATION_ID,
                "reference_id": REFERENCE_ID,
                "reference_observation_id": REFERENCE_OBSERVATION_ID,
                "reference_component_id": component_id,
                "signal_date": current["latest_completed_session"].isoformat()
                if current.get("reference_current_state_available", False)
                else current["reference_diagnostic_date"],
                "component_target": target,
                "reference_current_state_available": current["reference_current_state_available"],
                "missing_reference_symbols": current["missing_reference_symbols"],
                "reference_weight": REFERENCE_WEIGHT,
                "state_role": CURRENT_STATE_LABEL,
                "target_execution_authorized": current["reference_current_state_available"],
                "status": "pass"
                if current.get("reference_current_state_available", False)
                else "valid_pending_reference_latest_session_missing",
            }
        )
    rows.append(
        {
            "strategy_id": D1_ID,
            "observation_id": D1_OBSERVATION_ID,
            "reference_id": REFERENCE_ID,
            "reference_observation_id": REFERENCE_OBSERVATION_ID,
            "reference_component_id": "combined_reference_target",
            "signal_date": current["latest_completed_session"].isoformat()
            if current.get("reference_current_state_available", False)
            else current["reference_diagnostic_date"],
            "component_target": current["reference_target"]
            if current.get("reference_current_state_available", False)
            else current["reference_diagnostic_target"],
            "reference_current_state_available": current["reference_current_state_available"],
            "missing_reference_symbols": current["missing_reference_symbols"],
            "reference_weight": REFERENCE_WEIGHT,
            "state_role": CURRENT_STATE_LABEL,
            "target_execution_authorized": current["reference_current_state_available"],
            "status": "pass"
            if current.get("reference_current_state_available", False)
            else "valid_pending_reference_latest_session_missing",
        }
    )
    return rows


def d1_sleeve_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    d1_ready = current.get("reference_current_state_available", False)
    return [
        {
            "strategy_id": D1_ID,
            "observation_id": D1_OBSERVATION_ID,
            "signal_date": current["d1"]["signal_date"],
            "lookback_first_session": current["d1"]["lookback_first_session"],
            "lookback_last_session": current["d1"]["lookback_last_session"],
            "annualized_slope": current["d1"]["annualized_slope"],
            "r_squared": current["d1"]["r_squared"],
            "sleeve_target": current["d1"]["target"],
            "reference_weight": REFERENCE_WEIGHT,
            "sleeve_weight": SLEEVE_WEIGHT,
            "combined_target": current["d1_combined_target"] if d1_ready else {},
            "diagnostic_combined_target": current["d1_diagnostic_combined_target"],
            "target_freeze_event_label": CURRENT_STATE_LABEL if d1_ready else "",
            "scheduled_first_execution_date": current["next_daily_execution"].isoformat()
            if d1_ready
            else "",
            "first_eligible_performance_date": current["first_daily_performance"].isoformat()
            if d1_ready
            else "",
            "pending_reason": ""
            if d1_ready
            else "reference_current_state_unavailable_for_latest_completed_session_no_late_execution",
            "historical_backfill": False,
            "performance_rows_created": 0,
            "broker_calls": 0,
            "orders_created": 0,
            "status": "pass" if d1_ready else "valid_pending_reference_latest_session_missing",
        }
    ]


def paper_demo_record_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    active = active_entries()
    registry = registry_entries()
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        active_rows = [
            row for row in active if row.get("observation_id") == candidate["observation_id"]
        ]
        registry_rows = [
            row for row in registry if row.get("strategy_id") == candidate["strategy_id"]
        ]
        observation = read_yaml(active_yaml_path(candidate["observation_id"]))
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "entity_type": "paper_demo_observation",
                "mode": observation.get("observation_mode", ""),
                "route": candidate["route"],
                "status": observation.get("status", ""),
                "initialization_status": observation.get("initialization_status", ""),
                "active_registry_count": len(active_rows),
                "lifecycle_registry_count": len(registry_rows),
                "historical_backfill": observation.get("historical_backfill", ""),
                "broker_orders": observation.get("paper_orders", ""),
                "real_money_authorization": observation.get("real_money_authorization", ""),
                "performance_rows": observation.get("performance_rows", ""),
                "next_action": observation.get("next_action", ""),
                "status_check": "pass"
                if (
                    len(active_rows) == 1
                    and len(registry_rows) == 1
                    and observation.get("status") == "active_paper_demo_observation"
                    and observation.get("historical_backfill") is False
                    and observation.get("real_money_authorization") is False
                    and observation.get("performance_rows") == 0
                )
                else "fail",
            }
        )
    return rows


def virtual_initialization_rows(current: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        observation = read_yaml(active_yaml_path(candidate["observation_id"]))
        if candidate["strategy_id"] == MCA_ID:
            target = {}
            execution_date = ""
            first_perf = ""
            status = "validly_pending_first_prospective_weekly_signal"
        elif candidate["strategy_id"] == HYG_ID:
            target = current["hyg"]["target"]
            execution_date = current["next_daily_execution"].isoformat()
            first_perf = current["first_daily_performance"].isoformat()
            status = "target_frozen_pending_first_prospective_execution"
        else:
            if current.get("reference_current_state_available", False):
                target = current["d1_combined_target"]
                execution_date = current["next_daily_execution"].isoformat()
                first_perf = current["first_daily_performance"].isoformat()
                status = "target_frozen_pending_first_prospective_execution"
            else:
                target = {}
                execution_date = ""
                first_perf = ""
                status = "validly_pending_first_current_reference_state_or_execution"
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "initial_virtual_capital": observation.get("initial_virtual_capital", INITIAL_CAPITAL),
                "current_target_allocation": observation.get("current_target_allocation", {}),
                "scheduled_target_allocation": target,
                "scheduled_first_execution_date": execution_date,
                "first_eligible_performance_date": first_perf,
                "completed_virtual_execution_date": "",
                "virtual_positions_created": False,
                "virtual_shares_created": False,
                "virtual_cash_after_execution": "",
                "target_freeze_event_label": observation.get("target_freeze_event_label", ""),
                "historical_backfill": False,
                "ledger_rows_after_onboarding": ledger_row_count(ledger_path(candidate["observation_id"])),
                "performance_rows_created": 0,
                "broker_calls": 0,
                "orders_created": 0,
                "status": status,
            }
        )
    return rows


def active_before_after_rows(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    active = active_entries()
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        matching = [row for row in active if row.get("observation_id") == candidate["observation_id"]]
        after = matching[0] if matching else {}
        rows.append(
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "before_present": baseline["active_observation_present_before"][candidate["observation_id"]],
                "after_present": len(matching) == 1,
                "after_count": len(matching),
                "after_status": after.get("status", ""),
                "after_initialization_status": after.get("initialization_status", ""),
                "after_historical_backfill": after.get("historical_backfill", ""),
                "after_performance_rows": after.get("performance_rows", ""),
                "after_broker_orders": after.get("broker_orders", ""),
                "after_real_money_authorization": after.get("real_money_authorization", ""),
                "status": "pass" if len(matching) == 1 else "fail",
            }
        )
    return rows


def benchmark_reference_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        for benchmark in candidate["benchmarks"]:
            rows.append(
                {
                    "strategy_id": candidate["strategy_id"],
                    "observation_id": candidate["observation_id"],
                    "benchmark_reference_id": benchmark,
                    "carried_forward_as": "benchmark_reference_only",
                    "paper_demo_observation_created": False,
                    "promoted": False,
                    "counts_as_strategy": False,
                    "status": "pass",
                }
            )
    return rows


def state_change_rows(
    baseline: dict[str, Any],
    protected_after: dict[str, str],
    observation_materialization_rows: list[dict[str, Any]],
    registry_rows: list[dict[str, Any]],
    active_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "path": relative(REGISTRY_PATH),
            "change_class": "allowed_minimum_lifecycle_eligibility_update",
            "before_hash": baseline["registry_hash_before"],
            "after_hash": file_hash(REGISTRY_PATH),
            "records": registry_rows,
            "status": "changed_or_already_verified",
        },
        {
            "path": relative(ACTIVE_OBSERVATIONS_PATH),
            "change_class": "allowed_standard_active_observation_registry_update",
            "before_hash": baseline["active_observations_hash_before"],
            "after_hash": file_hash(ACTIVE_OBSERVATIONS_PATH),
            "records": active_rows,
            "status": "changed_or_already_verified",
        },
    ]
    for row in observation_materialization_rows:
        obs_dir = ROOT / row["observation_dir"]
        rows.append(
            {
                "path": row["observation_dir"],
                "change_class": "allowed_new_standard_paper_demo_observation_dir",
                "before_exists": baseline["observation_dir_present_before"][row["observation_id"]],
                "after_hash": tree_hash(obs_dir),
                "ledger_rows_after": row["ledger_rows_after"],
                "status": "created_or_already_verified",
            }
        )
    for path_text, before_hash in baseline["protected_hashes_before"].items():
        after_hash = protected_after.get(path_text, "missing")
        rows.append(
            {
                "path": path_text,
                "change_class": "protected_state_hash_reconciliation",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "status": "pass" if before_hash == after_hash else "fail",
            }
        )
    rows.append(
        {
            "path": relative(OUTPUT_DIR),
            "change_class": "required_evidence_packet_written",
            "after_hash": tree_hash(OUTPUT_DIR),
            "status": "pass",
        }
    )
    return rows


def process_log_rows(
    started: datetime,
    ended: datetime,
    outcome: str,
    market_data: dict[str, Any] | None,
    failures: list[str],
) -> list[dict[str, Any]]:
    attempt = {} if market_data is None else market_data.get("attempt", {})
    market_data_cycle_count = attempt.get(
        "bounded_cycles_total_for_task",
        1 if attempt.get("attempted", False) else 0,
    )
    return [
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "started_utc": started.isoformat(),
            "ended_utc": ended.isoformat(),
            "market_data_cycle_count": market_data_cycle_count,
            "market_data_provider_role": ""
            if not market_data
            else market_data.get("attempt", {}).get("provider_role", ""),
            "market_data_reused_from_current_task_snapshot": attempt.get(
                "reused_current_task_normalized_snapshot", False
            ),
            "account_endpoint_called": False
            if not market_data
            else market_data.get("attempt", {}).get("account_endpoint_called", False),
            "position_endpoint_called": False
            if not market_data
            else market_data.get("attempt", {}).get("position_endpoint_called", False),
            "order_endpoint_called": False
            if not market_data
            else market_data.get("attempt", {}).get("order_endpoint_called", False),
            "broker_calls": 0 if not market_data else market_data.get("attempt", {}).get("broker_calls", 0),
            "orders_created": 0 if not market_data else market_data.get("attempt", {}).get("orders_created", 0),
            "historical_backtests_run": 0,
            "prospective_validation_created": False,
            "outcome": outcome,
            "failure_count": len(failures),
        }
    ]


def outcome_rows(outcome: str, next_action: str, failures: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "outcome": outcome,
            "primary_reason": "" if not failures else failures[0],
            "exact_next_action": next_action,
            "next_action_executed": False,
            "existing_strategy_configurations_used": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_strategy_configurations": 0,
            "lifecycle_eligibility_records_updated": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_experiment_trials": 0,
            "paper_demo_observations_created": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "validation_observations_created": 0,
            "benchmark_references_carried_forward": sum(len(candidate["benchmarks"]) for candidate in CANDIDATES)
            if outcome == OUTCOME_ONBOARDED
            else 0,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
        }
    ]


def failure_rows(failures: list[str]) -> list[dict[str, Any]]:
    if not failures:
        return [
            {
                "task_id": TASK_ID,
                "failure_reason": "",
                "blocked_candidate": "",
                "status": "none",
            }
        ]
    return [
        {
            "task_id": TASK_ID,
            "failure_reason": failure,
            "blocked_candidate": "shared" if failure.startswith("shared_") else "",
            "status": "active_failure",
        }
        for failure in failures
    ]


def next_action_rows(outcome: str, next_action: str) -> list[dict[str, Any]]:
    return [
        {
            "task_id": TASK_ID,
            "outcome": outcome,
            "next_action": next_action,
            "next_action_executed": False,
            "allowed_scope": "record_standard_virtual_paper_demo_observations_only",
            "forbidden_scope": [
                "prospective_validation",
                "strategy_rule_change",
                "new_experiment_trial",
                "broker_order",
                "real_money_action",
                "historical_backfill",
            ],
        }
    ]


def required_output_hashes_excluding_consistency() -> dict[str, str]:
    return {
        name: file_hash(OUTPUT_DIR / name)
        for name in sorted(REQUIRED_OUTPUTS - {"consistency_check.json"})
    }


def consistency_check(
    outcome: str,
    next_action: str,
    reconciliation_pass: bool,
    compatibility_rows: list[dict[str, Any]],
    market_data: dict[str, Any] | None,
    baseline: dict[str, Any],
    protected_after: dict[str, str],
    failures: list[str],
) -> dict[str, Any]:
    required_present = sorted(name for name in REQUIRED_OUTPUTS if (OUTPUT_DIR / name).exists() or name == "consistency_check.json")
    missing = sorted(REQUIRED_OUTPUTS - set(required_present))
    active = active_entries()
    registry = registry_entries()
    candidate_active_counts = {
        candidate["observation_id"]: sum(
            row.get("observation_id") == candidate["observation_id"] for row in active
        )
        for candidate in CANDIDATES
    }
    candidate_registry_counts = {
        candidate["strategy_id"]: sum(
            row.get("strategy_id") == candidate["strategy_id"] for row in registry
        )
        for candidate in CANDIDATES
    }
    ledger_rows = {
        candidate["observation_id"]: ledger_row_count(ledger_path(candidate["observation_id"]))
        for candidate in CANDIDATES
    }
    protected_pass = all(
        protected_after.get(path_text, "missing") == before_hash
        for path_text, before_hash in baseline["protected_hashes_before"].items()
    )
    market_attempt = {} if market_data is None else market_data.get("attempt", {})
    latest_completed = standard_obs.latest_fully_completed_session(datetime.now(timezone.utc))
    market_data_admitted, missing_direct_symbols = (
        market_data_ready_for_onboarding(market_data, latest_completed)
        if market_data
        else (False, [])
    )
    no_broker = (
        not market_attempt.get("account_endpoint_called", False)
        and not market_attempt.get("position_endpoint_called", False)
        and not market_attempt.get("order_endpoint_called", False)
        and market_attempt.get("broker_calls", 0) == 0
        and market_attempt.get("orders_created", 0) == 0
    )
    observations_pass = (
        all(count == 1 for count in candidate_active_counts.values())
        and all(count == 1 for count in candidate_registry_counts.values())
        and all(count == 0 for count in ledger_rows.values())
    )
    payload = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "outcome": outcome,
        "exact_next_action": next_action,
        "overall_pass": (
            outcome == OUTCOME_ONBOARDED
            and reconciliation_pass
            and all(row.get("status") == "pass" for row in compatibility_rows)
            and market_data_admitted
            and protected_pass
            and observations_pass
            and no_broker
            and not missing
            and not failures
        ),
        "required_output_reconciliation": {
            "required_count": len(REQUIRED_OUTPUTS),
            "present": required_present,
            "missing": missing,
            "hashes_excluding_consistency_check": required_output_hashes_excluding_consistency(),
        },
        "methodology_and_reassessment_reconciliation_pass": reconciliation_pass,
        "standard_framework_compatibility_pass": all(
            row.get("status") == "pass" for row in compatibility_rows
        ),
        "current_state_market_data": {
            "attempted": bool(market_attempt.get("attempted", False)),
            "bounded_cycles": market_attempt.get("bounded_cycles", 0),
            "bounded_cycles_total_for_task": market_attempt.get(
                "bounded_cycles_total_for_task",
                1 if market_attempt.get("attempted", False) else 0,
            ),
            "reused_current_task_normalized_snapshot": market_attempt.get(
                "reused_current_task_normalized_snapshot", False
            ),
            "status": market_attempt.get("status", ""),
            "provider_role": market_attempt.get("provider_role", ""),
            "row_count": market_attempt.get("row_count", 0),
            "candidate_direct_symbols_current": market_data_admitted,
            "missing_candidate_direct_symbols": missing_direct_symbols,
            "account_endpoint_called": market_attempt.get("account_endpoint_called", False),
            "position_endpoint_called": market_attempt.get("position_endpoint_called", False),
            "order_endpoint_called": market_attempt.get("order_endpoint_called", False),
            "broker_calls": market_attempt.get("broker_calls", 0),
            "orders_created": market_attempt.get("orders_created", 0),
        },
        "candidate_active_observation_counts": candidate_active_counts,
        "candidate_registry_counts": candidate_registry_counts,
        "candidate_forward_ledger_rows": ledger_rows,
        "entity_count_reconciliation": {
            "existing_strategy_configurations_used": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_strategy_configurations": 0,
            "lifecycle_eligibility_records_updated": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_experiment_trials": 0,
            "paper_demo_observations": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "validation_observations": 0,
            "benchmark_references_carried_forward": sum(len(candidate["benchmarks"]) for candidate in CANDIDATES)
            if outcome == OUTCOME_ONBOARDED
            else 0,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
        },
        "protected_state_reconciliation": {
            "overall_pass": protected_pass,
            "before": baseline["protected_hashes_before"],
            "after": protected_after,
        },
        "no_backfill_tests": {
            "ledger_rows_zero_after_onboarding": all(count == 0 for count in ledger_rows.values()),
            "historical_performance_rows_imported": 0,
            "performance_row_on_virtual_initialization_date": False,
        },
        "failures": failures,
    }
    return payload


def onboarding_manifest(
    started: datetime,
    ended: datetime,
    outcome: str,
    next_action: str,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "outcome": outcome,
        "next_action": next_action,
        "eligibility_basis": ELIGIBILITY_BASIS,
        "current_state_label": CURRENT_STATE_LABEL,
        "latest_fully_completed_session": ""
        if current is None
        else current["latest_completed_session"].isoformat(),
        "candidates": [
            {
                "strategy_id": candidate["strategy_id"],
                "observation_id": candidate["observation_id"],
                "route": candidate["route"],
                "status": "active_paper_demo_observation" if outcome == OUTCOME_ONBOARDED else "",
                "initialization_status": ""
                if current is None
                else initialization_status(candidate, current),
            }
            for candidate in CANDIDATES
        ],
        "entity_separation": {
            "existing_strategy_configurations_used": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_strategy_configurations": 0,
            "lifecycle_eligibility_records_updated": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "new_experiment_trials": 0,
            "paper_demo_observations_created": 3 if outcome == OUTCOME_ONBOARDED else 0,
            "validation_observations_created": 0,
            "benchmark_references_carried_forward": sum(len(candidate["benchmarks"]) for candidate in CANDIDATES)
            if outcome == OUTCOME_ONBOARDED
            else 0,
            "process_tasks": 1,
            "broker_or_paper_orders": 0,
        },
        "protected_state_policy": {
            "methodology_packets_modified": False,
            "original_robustness_packets_modified": False,
            "existing_observation_histories_modified": False,
            "canonical_historical_caches_modified": False,
            "broker_or_account_config_modified": False,
        },
    }


def onboarding_report(outcome: str, next_action: str, current: dict[str, Any] | None) -> str:
    if outcome == OUTCOME_ONBOARDED and current is not None:
        d1_detail = (
            f"D1 has a frozen combined target for {current['next_daily_execution'].isoformat()}."
            if current.get("reference_current_state_available", False)
            else (
                "D1 is active but pending because the frozen VM/DSR/USCI reference combo "
                f"does not have a latest common {current['latest_completed_session'].isoformat()} "
                f"state; missing latest symbols: {', '.join(current['missing_reference_symbols'])}."
            )
        )
        status_detail = (
            f"MCA is active but pending the next completed weekly signal on "
            f"{current['next_weekly_signal'].isoformat()}, because the prior weekly signal "
            f"({current['latest_expired_weekly_signal'].isoformat()}) already had its execution "
            f"boundary on {current['latest_expired_weekly_execution'].isoformat()}. HYG and D1 "
            f"were evaluated from the {current['latest_completed_session'].isoformat()} completed "
            f"session; HYG has a target frozen for the {current['next_daily_execution'].isoformat()} "
            f"close. {d1_detail}"
        )
    else:
        status_detail = "The onboarding could not complete for the shared scope."
    return f"""# Role-Aware Reassessment Candidate Standard Paper/Demo Onboarding

## Outcome

**`{outcome}`**

Exactly three role-aware reassessment-positive candidates were reconciled against the adopted standard
and onboarded through the existing standard virtual paper/demo framework. No strategy configuration,
experiment trial, prospective-validation stage, validation observation, broker order, paper-broker order,
or real-money action was created.

{status_detail}

Original `robustness_mixed` / `concentration_risk` outcomes remain preserved under their original gate
contracts. The reassessment child trials are the current promotion evidence, and the new observations are
forward evidence collection only.

Exact next action: `{next_action}`.
"""


def write_blocked_outputs(
    started: datetime,
    reconciliation_rows: list[dict[str, Any]],
    compatibility_rows: list[dict[str, Any]],
    market_data: dict[str, Any] | None,
    baseline: dict[str, Any],
    failures: list[str],
) -> dict[str, Any]:
    ended = datetime.now(timezone.utc)
    outcome = OUTCOME_BLOCKED
    next_action = NEXT_BLOCKED
    protected_after = map_hashes(PROTECTED_PATHS)
    empty: list[dict[str, Any]] = []
    write_yaml_file(OUTPUT_DIR / "onboarding_manifest.yaml", onboarding_manifest(started, ended, outcome, next_action, None))
    write_csv(OUTPUT_DIR / "methodology_and_reassessment_reconciliation.csv", reconciliation_rows, ("source", "check_id", "status"))
    write_csv(OUTPUT_DIR / "candidate_eligibility_before_after.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "strategy_and_trial_lineage.csv", empty, ("strategy_id", "reassessment_trial_id"))
    write_csv(OUTPUT_DIR / "standard_framework_compatibility.csv", compatibility_rows, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "mca_current_state_reconciliation.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "hyg_current_state_reconciliation.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "d1_reference_state_reconciliation.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "d1_sleeve_state_reconciliation.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "paper_demo_observation_records.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "virtual_initialization_records.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "active_observations_before_after.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(OUTPUT_DIR / "benchmark_reference_reconciliation.csv", empty, ("strategy_id", "observation_id", "status"))
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_change_rows(baseline, protected_after, [], [], []),
        ("path", "change_class", "status"),
    )
    write_csv(OUTPUT_DIR / "process_task_log.csv", process_log_rows(started, ended, outcome, market_data, failures), ("task_id", "outcome"))
    write_csv(OUTPUT_DIR / "outcome_summary.csv", outcome_rows(outcome, next_action, failures), ("task_id", "outcome", "exact_next_action"))
    write_csv(OUTPUT_DIR / "failure_reasons.csv", failure_rows(failures), ("task_id", "failure_reason", "status"))
    write_csv(OUTPUT_DIR / "next_actions.csv", next_action_rows(outcome, next_action), ("task_id", "next_action"))
    write_json_file(
        OUTPUT_DIR / "consistency_check.json",
        consistency_check(
            outcome,
            next_action,
            not failures,
            compatibility_rows,
            market_data,
            baseline,
            protected_after,
            failures,
        ),
    )
    (OUTPUT_DIR / "onboarding_report.md").write_text(
        onboarding_report(outcome, next_action, None), encoding="utf-8"
    )
    return {"outcome": outcome, "next_action": next_action, "failures": failures}


def run(now: datetime | None = None) -> dict[str, Any]:
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    started = started.astimezone(timezone.utc)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = load_or_create_baseline(started)

    reconciliation_rows, reconciliation_pass, reconciliation_failures = (
        reconcile_methodology_and_reassessment()
    )
    compatibility_rows, compatibility_pass = standard_framework_compatibility_rows()
    failures: list[str] = []
    if not reconciliation_pass:
        failures.append("role_aware_reassessment_reconciliation_failure")
    if not compatibility_pass:
        failures.append("standard_observation_schema_incompatible")
    if failures:
        return write_blocked_outputs(
            started, reconciliation_rows, compatibility_rows, None, baseline, failures
        )

    latest_completed = standard_obs.latest_fully_completed_session(started)
    symbols = ordered_union(standard_obs.REQUIRED_SYMBOLS, MCA_SYMBOLS, HYG_SYMBOLS, D1_SYMBOLS)
    market_data = load_reused_normalized_market_data(symbols)
    if market_data is None:
        market_data = standard_obs.retrieve_alpaca(
            OUTPUT_DIR,
            symbols,
            date(2018, 1, 1),
            latest_completed + timedelta(days=1),
        )
    data_ready, missing_direct_symbols = market_data_ready_for_onboarding(
        market_data, latest_completed
    )
    if not data_ready:
        failures.append("shared_market_data_unavailable")
        if missing_direct_symbols:
            failures[-1] += ":" + ",".join(missing_direct_symbols)
        return write_blocked_outputs(
            started, reconciliation_rows, compatibility_rows, market_data, baseline, failures
        )

    try:
        current = current_state_reconciliation(started, market_data)
        registry_rows, active_rows = apply_lifecycle_and_active_state(started.isoformat(), current)
        observation_materialization_rows = materialize_observation_files(
            CANDIDATES, started.isoformat(), current
        )
        outcome = OUTCOME_ONBOARDED
        next_action = NEXT_ONBOARDED
    except BaseException as exc:  # noqa: BLE001 - current-state failures are recorded as task evidence.
        failures.append("shared_market_data_unavailable:" + standard_obs.sanitize_error(exc))
        return write_blocked_outputs(
            started, reconciliation_rows, compatibility_rows, market_data, baseline, failures
        )

    ended = datetime.now(timezone.utc)
    protected_after = map_hashes(PROTECTED_PATHS)

    write_yaml_file(
        OUTPUT_DIR / "onboarding_manifest.yaml",
        onboarding_manifest(started, ended, outcome, next_action, current),
    )
    write_csv(
        OUTPUT_DIR / "methodology_and_reassessment_reconciliation.csv",
        reconciliation_rows,
        ("source", "check_id", "strategy_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "candidate_eligibility_before_after.csv",
        candidate_eligibility_rows(baseline),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "strategy_and_trial_lineage.csv",
        lineage_rows_from_reassessment(),
        ("strategy_id", "reassessment_trial_id", "parent_trial_id"),
    )
    write_csv(
        OUTPUT_DIR / "standard_framework_compatibility.csv",
        compatibility_rows,
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "mca_current_state_reconciliation.csv",
        mca_current_rows(current),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "hyg_current_state_reconciliation.csv",
        hyg_current_rows(current),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "d1_reference_state_reconciliation.csv",
        d1_reference_rows(current),
        ("strategy_id", "observation_id", "reference_component_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "d1_sleeve_state_reconciliation.csv",
        d1_sleeve_rows(current),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observation_records.csv",
        paper_demo_record_rows(current),
        ("strategy_id", "observation_id", "status_check"),
    )
    write_csv(
        OUTPUT_DIR / "virtual_initialization_records.csv",
        virtual_initialization_rows(current),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "active_observations_before_after.csv",
        active_before_after_rows(baseline),
        ("strategy_id", "observation_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_reconciliation.csv",
        benchmark_reference_rows(),
        ("strategy_id", "observation_id", "benchmark_reference_id", "status"),
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_change_rows(
            baseline, protected_after, observation_materialization_rows, registry_rows, active_rows
        ),
        ("path", "change_class", "status"),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_log_rows(started, ended, outcome, market_data, failures),
        ("task_id", "outcome"),
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows(outcome, next_action, failures),
        ("task_id", "outcome", "exact_next_action"),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows(failures),
        ("task_id", "failure_reason", "status"),
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_action_rows(outcome, next_action),
        ("task_id", "next_action"),
    )
    (OUTPUT_DIR / "onboarding_report.md").write_text(
        onboarding_report(outcome, next_action, current), encoding="utf-8"
    )
    check = consistency_check(
        outcome,
        next_action,
        reconciliation_pass,
        compatibility_rows,
        market_data,
        baseline,
        protected_after,
        failures,
    )
    write_json_file(OUTPUT_DIR / "consistency_check.json", check)
    return {
        "outcome": outcome,
        "next_action": next_action,
        "output_dir": relative(OUTPUT_DIR),
        "overall_pass": check["overall_pass"],
        "latest_completed_session": current["latest_completed_session"].isoformat(),
        "hyg_target": current["hyg"]["target"],
        "d1_target": current["d1_combined_target"],
        "mca_status": "pending_first_valid_signal_or_execution",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now-utc", default="")
    args = parser.parse_args(argv)
    now = None
    if args.now_utc:
        now = datetime.fromisoformat(args.now_utc.replace("Z", "+00:00"))
    result = run(now)
    print(json.dumps(canonicalize(result), indent=2, sort_keys=True))
    return 0 if result.get("outcome") == OUTCOME_ONBOARDED else 1


if __name__ == "__main__":
    raise SystemExit(main())
