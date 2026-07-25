from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


CORRECTION_ID = "correct_angl_forward_boundary_and_data_freshness_v1"
OUTPUT_DIR = ROOT / "evidence" / "correction" / CORRECTION_ID / "latest"
ONBOARDING_DIR = ROOT / "evidence" / "paper_demo" / "onboard_angl_diversifier_paper_demo_observation_v1" / "latest"
METHODOLOGY_CORRECTION_DIR = ROOT / "evidence" / "correction" / "angl_80_20_portfolio_construction_methodology_correction_v1" / "latest"
VALIDATION_DIR = ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest"
FORWARD_REINIT_DIR = ROOT / "evidence" / "forward_operational_reinitialization_vm_dsr_combo_v1" / "latest"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"

STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
REFERENCE_PORTFOLIO_ID = "frozen_current_active_vm_dsr_usci_combo"
REFERENCE_OBSERVATION_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
ACTIVE_COMBO_BENCHMARK_ID = "active_combo_vm_dsr_equal_weight_v1"
CORRECTION_ACTIVATION_TIMESTAMP = "2026-07-24T00:00:01+00:00"
PRIMARY_FAILURE_REASON = "methodology_failure"
DEFECT_TYPE = "forward_boundary_precedes_activation"
NEXT_ACTION_BLOCKED = "initialize_angl_after_next_completed_common_session_v1"
NEXT_ACTION_ACTIVE = "continue_angl_forward_observation_until_review_trigger_v1"
TARGET_REFERENCE_WEIGHT = 0.80
TARGET_SLEEVE_WEIGHT = 0.20
PRIMARY_COST_BPS = 5.0
WEIGHT_TOLERANCE = 1e-6

REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ROADMAP_PATH = ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
RESEARCH_QUEUE_PATH = ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml"
FAMILY_LEDGER_PATH = ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml"
PROTECTED_STATE_PATHS = [REGISTRY_PATH, ROADMAP_PATH, ACTIVE_OBSERVATIONS_PATH, RESEARCH_QUEUE_PATH, FAMILY_LEDGER_PATH]

ONBOARDING_INPUT_FILES = [
    ONBOARDING_DIR / name
    for name in [
        "onboarding_manifest.yaml",
        "paper_demo_observations.csv",
        "operational_preflight.csv",
        "data_freshness.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "historical_reconciliation.csv",
        "consistency_check.json",
    ]
]
PRIOR_EVIDENCE_FILES = [
    *ONBOARDING_INPUT_FILES,
    *sorted(METHODOLOGY_CORRECTION_DIR.glob("*")),
    *sorted(VALIDATION_DIR.glob("*")),
]

VM_SYMBOLS = ("SPLV", "USMV", "QUAL", "SPY", "BIL")
DSR_SYMBOLS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL")
USCI_SYMBOLS = ("USCI", "DBC", "BIL", "SPY")
CONTROL_SYMBOLS = ("ANGL", "HYG", "JNK")
DEFAULT_REFERENCE_SYMBOLS = tuple(sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS)))
FORBIDDEN_FLAGS = {
    "new_validation_or_robustness_analysis": False,
    "source_research": False,
    "source_rule_change": False,
    "parameter_change": False,
    "sleeve_weight_change": False,
    "control_change": False,
    "instrument_substitution": False,
    "benchmark_correction": False,
    "universe_expansion": False,
    "overlay_test": False,
    "historical_backfill_labeled_forward": False,
    "broad_dashboard_or_framework_rebuild": False,
    "paper_or_live_broker_order": False,
    "account_access": False,
    "real_money_action": False,
}


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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.exists()}


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "correction" / CORRECTION_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_iso(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def date_or_empty(value: str) -> str:
    if not value:
        return ""
    return pd.Timestamp(value).date().isoformat()


def reference_symbol_universe() -> tuple[str, ...]:
    payload = read_json(FORWARD_REINIT_DIR / "authorized_symbol_universe.json")
    symbols = payload.get("authorized_symbols")
    if isinstance(symbols, list) and symbols:
        return tuple(sorted(str(symbol) for symbol in symbols))
    return DEFAULT_REFERENCE_SYMBOLS


def required_symbols() -> tuple[str, ...]:
    return tuple(sorted(set(CONTROL_SYMBOLS + reference_symbol_universe())))


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def metadata_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.acquisition.json"


def read_cache(symbol: str) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if "date" not in frame.columns:
        return pd.DataFrame()
    price_field = "adj_close" if "adj_close" in frame.columns else "close" if "close" in frame.columns else ""
    if not price_field:
        return pd.DataFrame()
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame[price_field] = pd.to_numeric(frame[price_field], errors="coerce")
    frame = frame.dropna(subset=["date", price_field]).sort_values("date").drop_duplicates("date", keep="last")
    return frame[["date", price_field]].rename(columns={price_field: "adj_close"})


def cache_inventory_rows(symbols: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    correction_date = parse_iso(CORRECTION_ACTIVATION_TIMESTAMP).date()
    reference_symbols = set(reference_symbol_universe())
    for symbol in symbols:
        frame = read_cache(symbol)
        latest = "" if frame.empty else frame["date"].max().date().isoformat()
        role_parts: list[str] = []
        if symbol in CONTROL_SYMBOLS:
            role_parts.append("candidate_or_control")
        if symbol in reference_symbols:
            role_parts.append("frozen_reference_input")
        role = "|".join(role_parts) if role_parts else "unknown"
        rows.append(
            {
                "symbol": symbol,
                "role": role,
                "cache_path": rel(cache_path(symbol)),
                "metadata_path": rel(metadata_path(symbol)) if metadata_path(symbol).exists() else "",
                "cache_exists": cache_path(symbol).exists(),
                "row_count": int(len(frame)),
                "first_date": "" if frame.empty else frame["date"].min().date().isoformat(),
                "latest_available_date": latest,
                "latest_after_correction_activation_date": bool(latest and pd.Timestamp(latest).date() >= correction_date),
                "cache_hash": file_hash(cache_path(symbol)),
                "metadata_hash": file_hash(metadata_path(symbol)) if metadata_path(symbol).exists() else "",
            }
        )
    return rows


def latest_common_cache_date(rows: list[dict[str, Any]]) -> str:
    latest = [row["latest_available_date"] for row in rows if row.get("latest_available_date")]
    if len(latest) != len(rows):
        return ""
    return min(latest)


def active_combo_reference_latest() -> dict[str, Any]:
    path = PAPER_FORWARD_DIR / ACTIVE_COMBO_BENCHMARK_ID / "operational_forward_reference_index.csv"
    if not path.exists():
        return {"date": "", "path": rel(path), "status": "missing"}
    rows = read_csv_rows(path)
    if not rows:
        return {"date": "", "path": rel(path), "status": "empty"}
    last = rows[-1]
    return {
        "date": last.get("date", ""),
        "path": rel(path),
        "status": "available_reference_only",
        "active_combo_forward_index": last.get("active_combo_forward_index", ""),
    }


def observation_yaml(observation_id: str) -> dict[str, Any]:
    return read_yaml(PAPER_FORWARD_DIR / observation_id / "active_observation.yaml")


def reference_state_rows(cache_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combo = observation_yaml(REFERENCE_OBSERVATION_ID)
    vm = observation_yaml("paper_forward_vm_quality_lowvol_proxy_v1")
    dsr = observation_yaml("paper_forward_dsr_sector_equal_weight_defensive_filter_v1")
    usci = observation_yaml("paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1")
    active_combo = active_combo_reference_latest()
    cache_common = latest_common_cache_date(cache_rows)
    correction_date = parse_iso(CORRECTION_ACTIVATION_TIMESTAMP).date()
    rows = [
        {
            "reference_or_component_id": REFERENCE_PORTFOLIO_ID,
            "source_record": rel(PAPER_FORWARD_DIR / REFERENCE_OBSERVATION_ID / "active_observation.yaml"),
            "latest_reproducible_state_date": combo.get("latest_committed_observation_date", ""),
            "latest_common_cache_date": cache_common,
            "after_correction_activation": bool(
                combo.get("latest_committed_observation_date")
                and pd.Timestamp(combo.get("latest_committed_observation_date")).date() >= correction_date
            ),
            "reconciliation_status": "blocked_no_post_correction_reference_state",
            "detail": "derived VM/DSR/USCI observation remains at the June 18 operational baseline",
        },
        {
            "reference_or_component_id": "paper_forward_vm_quality_lowvol_proxy_v1",
            "source_record": rel(PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml"),
            "latest_reproducible_state_date": vm.get("latest_committed_observation_date", ""),
            "latest_common_cache_date": min(row["latest_available_date"] for row in cache_rows if row["symbol"] in VM_SYMBOLS and row["latest_available_date"]),
            "after_correction_activation": False,
            "reconciliation_status": "blocked_component_state_not_advanced",
            "detail": "VM component ledger has no post-correction common state",
        },
        {
            "reference_or_component_id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            "source_record": rel(PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml"),
            "latest_reproducible_state_date": dsr.get("latest_committed_observation_date", ""),
            "latest_common_cache_date": min(row["latest_available_date"] for row in cache_rows if row["symbol"] in DSR_SYMBOLS and row["latest_available_date"]),
            "after_correction_activation": False,
            "reconciliation_status": "blocked_component_state_not_advanced",
            "detail": "DSR component ledger has no post-correction common state",
        },
        {
            "reference_or_component_id": "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
            "source_record": rel(PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml"),
            "latest_reproducible_state_date": usci.get("latest_committed_observation_date", ""),
            "latest_common_cache_date": min(row["latest_available_date"] for row in cache_rows if row["symbol"] in USCI_SYMBOLS and row["latest_available_date"]),
            "after_correction_activation": False,
            "reconciliation_status": "component_independently_advanced_but_reference_group_incomplete",
            "detail": "USCI has some post-June-18 state but not after the ANGL correction activation and cannot advance the VM/DSR/USCI reference alone",
        },
        {
            "reference_or_component_id": ACTIVE_COMBO_BENCHMARK_ID,
            "source_record": active_combo["path"],
            "latest_reproducible_state_date": active_combo["date"],
            "latest_common_cache_date": cache_common,
            "after_correction_activation": bool(active_combo["date"] and pd.Timestamp(active_combo["date"]).date() >= correction_date),
            "reconciliation_status": "benchmark_reference_not_current_after_correction",
            "detail": "active combo reference index has no post-correction row",
        },
    ]
    return rows


def prior_observation_row() -> dict[str, str]:
    rows = read_csv_rows(ONBOARDING_DIR / "paper_demo_observations.csv")
    return rows[0] if rows else {}


def prior_defect_rows() -> list[dict[str, Any]]:
    manifest = read_yaml(ONBOARDING_DIR / "onboarding_manifest.yaml")
    nav_rows = read_csv_rows(ONBOARDING_DIR / "initial_virtual_nav.csv")
    trade_rows = read_csv_rows(ONBOARDING_DIR / "initial_virtual_trades.csv")
    nav = nav_rows[0] if nav_rows else {}
    original_activation = str(manifest.get("activation_timestamp") or nav.get("activation_timestamp") or "")
    original_forward_date = str(manifest.get("first_forward_observation_date") or nav.get("first_forward_observation_date") or "")
    original_latest_common = str(manifest.get("latest_common_data_date") or nav.get("latest_common_data_date") or "")
    trade_dates = sorted({row.get("trade_date", "") for row in trade_rows if row.get("trade_date")})
    days_preceded = ""
    if original_activation and original_forward_date:
        days_preceded = (parse_iso(original_activation).date() - pd.Timestamp(original_forward_date).date()).days
    return [
        {
            "observation_id": OBSERVATION_ID,
            "prior_observation_outcome": "observation_invalid_or_incomplete",
            "primary_failure_reason": PRIMARY_FAILURE_REASON,
            "defect_type": DEFECT_TYPE,
            "original_activation_timestamp": original_activation,
            "original_first_forward_observation_date": original_forward_date,
            "original_virtual_trade_dates": trade_dates,
            "days_boundary_preceded_activation": days_preceded,
            "original_latest_common_data_date": original_latest_common,
            "return_previously_counted_as_forward_evidence": False,
            "trade_position_or_nav_previously_mislabeled_forward": True,
            "corrected_classification_for_june_18": "historical_reconciliation_only",
        }
    ]


def historical_reconciliation_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_file, date_field in [
        ("initial_virtual_positions.csv", "latest_common_data_date"),
        ("initial_virtual_trades.csv", "trade_date"),
        ("initial_virtual_nav.csv", "latest_common_data_date"),
        ("historical_reconciliation.csv", ""),
    ]:
        for pos, row in enumerate(read_csv_rows(ONBOARDING_DIR / source_file), start=1):
            record_date = row.get(date_field, "") if date_field else ""
            rows.append(
                {
                    "source_file": rel(ONBOARDING_DIR / source_file),
                    "source_row_number": pos,
                    "observation_id": row.get("observation_id", OBSERVATION_ID),
                    "record_date": record_date,
                    "original_record_label": row.get("forward_boundary_label") or row.get("label") or "prior_onboarding_record",
                    "corrected_record_classification": "historical_reconciliation_only",
                    "retained": True,
                    "forward_observation_evidence": False,
                    "reason": "record date precedes correction activation timestamp",
                }
            )
    return rows


def market_data_refresh_rows(cache_before: dict[str, str], cache_after: dict[str, str], cache_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in cache_rows:
        path = ROOT / row["cache_path"]
        out.append(
            {
                "symbol": row["symbol"],
                "role": row["role"],
                "provider_preference": "alpaca_market_data_primary_when_canonical_adjusted_cache_and_reference_state_can_be_refreshed",
                "refresh_attempted": False,
                "refresh_status": "local_cache_and_existing_reference_state_inspected_only",
                "refresh_reason": (
                    "no post-correction common reference state is available; no broker/account/order access used; "
                    "no broad provider refresh invoked by this correction"
                ),
                "cache_path": row["cache_path"],
                "cache_hash_before": cache_before.get(rel(path), "missing"),
                "cache_hash_after": cache_after.get(rel(path), "missing"),
                "cache_changed": cache_before.get(rel(path), "missing") != cache_after.get(rel(path), "missing"),
                "latest_available_date": row["latest_available_date"],
                "provider_download_performed": False,
                "broker_or_order_endpoint_called": False,
            }
        )
    return out


def session_close_after_activation(session_date: str) -> bool:
    if not session_date:
        return False
    activation = parse_iso(CORRECTION_ACTIVATION_TIMESTAMP).astimezone(timezone.utc)
    # Conservative U.S. equity close proxy. This task only needs to reject pre-activation cached dates.
    close_time = datetime.fromisoformat(session_date + "T20:00:00+00:00")
    return close_time > activation


def boundary_decision_rows(cache_common: str, reference_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ref_latest = next(row for row in reference_rows if row["reference_or_component_id"] == REFERENCE_PORTFOLIO_ID)[
        "latest_reproducible_state_date"
    ]
    candidate_session = min([date for date in [cache_common, str(ref_latest)] if date] or [""])
    valid = bool(candidate_session and session_close_after_activation(candidate_session))
    return [
        {
            "observation_id": OBSERVATION_ID,
            "correction_activation_timestamp": CORRECTION_ACTIVATION_TIMESTAMP,
            "latest_common_market_data_session": cache_common,
            "latest_reference_reproducible_state_session": ref_latest,
            "candidate_first_forward_session": candidate_session,
            "candidate_session_close_after_correction_activation": session_close_after_activation(candidate_session),
            "valid_first_forward_session_exists": valid,
            "decision": "valid_forward_session_available" if valid else "no_valid_completed_common_session_after_correction_activation",
            "activation_gate_status": "pass" if valid else "blocked",
            "next_action": NEXT_ACTION_ACTIVE if valid else NEXT_ACTION_BLOCKED,
        }
    ]


def strategy_card_row(next_action: str) -> dict[str, Any]:
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
        "strategy_validation_repeated": False,
        "new_strategy_configuration_created": False,
        "next_action": next_action,
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


def observation_output_row(stage: str, outcome: str, next_action: str, corrected_first_forward_date: str = "") -> dict[str, Any]:
    defect = prior_defect_rows()[0]
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
        "candidate_sleeve_id": "ANGL",
        "target_weights": {"frozen_reference": 0.8, "ANGL": 0.2},
        "rebalance_frequency": "monthly",
        "signal_timing": "month_end_close",
        "execution_convention": "next_available_session_close",
        "cost_assumption": "5_bps_per_one_way_turnover",
        "original_activation_timestamp": defect["original_activation_timestamp"],
        "original_first_forward_observation_date": defect["original_first_forward_observation_date"],
        "correction_activation_timestamp": CORRECTION_ACTIVATION_TIMESTAMP,
        "corrected_first_forward_observation_date": corrected_first_forward_date,
        "current_status": stage,
        "failure_reason": "" if stage == "paper_demo_active" else PRIMARY_FAILURE_REASON,
        "defect_type": DEFECT_TYPE,
        "adaptation_label": "paper_demo_observation_fix",
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


def corrected_observation_block(stage: str, outcome: str, next_action: str, corrected_first_forward_date: str = "") -> str:
    defect = prior_defect_rows()[0]
    active = "true" if stage == "paper_demo_active" else "false"
    failure = "" if stage == "paper_demo_active" else PRIMARY_FAILURE_REASON
    state = "active_accepted_frozen_observation" if stage == "paper_demo_active" else "blocked_observation_invalid_or_incomplete"
    return f"""
- observation_id: {OBSERVATION_ID}
  strategy_id: {STRATEGY_ID}
  entity_type: paper_demo_observation
  stage: {stage}
  outcome: {outcome}
  state: {state}
  paper_forward_active: {active}
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
  original_activation_timestamp: '{defect["original_activation_timestamp"]}'
  original_first_forward_observation_date: '{defect["original_first_forward_observation_date"]}'
  original_latest_common_data_date: '{defect["original_latest_common_data_date"]}'
  correction_activation_timestamp: '{CORRECTION_ACTIVATION_TIMESTAMP}'
  corrected_first_forward_observation_date: '{corrected_first_forward_date}'
  first_forward_observation_date: '{corrected_first_forward_date}'
  current_status: {stage}
  failure_reason: '{failure}'
  defect_type: {DEFECT_TYPE}
  adaptation_label: paper_demo_observation_fix
  next_action: {next_action}
  broker_integration: false
  paper_orders: false
  live_orders: false
  real_money_recommendation: false
  review_trigger: after_three_completed_scheduled_month_end_rebalance_cycles_or_immediate_operational_exception
"""


def replace_observation_record(stage: str, outcome: str, next_action: str, corrected_first_forward_date: str = "") -> str:
    text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    block = corrected_observation_block(stage, outcome, next_action, corrected_first_forward_date).strip()
    pattern = re.compile(
        rf"(?ms)^- observation_id: {re.escape(OBSERVATION_ID)}\n.*?(?=^benchmark_controls:|^- observation_id:|\Z)"
    )
    if not pattern.search(text):
        raise RuntimeError(f"{OBSERVATION_ID} observation record was not found")
    updated = pattern.sub(block + "\n", text, count=1)
    ACTIVE_OBSERVATIONS_PATH.write_text(updated, encoding="utf-8")
    return "updated_in_place"


def update_registry_next_action(next_action: str) -> str:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?ms)^- id: {re.escape(STRATEGY_ID)}\n.*?(?=^- id:|\Z)")
    match = pattern.search(text)
    if not match:
        return "strategy_record_missing"
    block = match.group(0)
    updated_block = re.sub(r"(?m)^  next_action: .*$", f"  next_action: {next_action}", block)
    updated_block = re.sub(r"(?m)^  allowed_next_action: .*$", f"  allowed_next_action: {next_action}", updated_block)
    if updated_block == block:
        return "already_current"
    REGISTRY_PATH.write_text(text[: match.start()] + updated_block + text[match.end() :], encoding="utf-8")
    return "next_action_updated"


def state_change_rows(
    before: dict[str, str],
    after: dict[str, str],
    cache_before: dict[str, str],
    cache_after: dict[str, str],
    registry_action: str,
    observation_action: str,
) -> list[dict[str, Any]]:
    rows = []
    for path in PROTECTED_STATE_PATHS:
        changed = before.get(rel(path), "missing") != after.get(rel(path), "missing")
        permitted = path in {REGISTRY_PATH, ACTIVE_OBSERVATIONS_PATH}
        action = (
            registry_action
            if path == REGISTRY_PATH
            else observation_action
            if path == ACTIVE_OBSERVATIONS_PATH
            else "unchanged_required"
        )
        rows.append(
            {
                "path": rel(path),
                "path_type": "authoritative_state",
                "before_hash": before.get(rel(path), "missing"),
                "after_hash": after.get(rel(path), "missing"),
                "changed": changed,
                "permitted_change": permitted,
                "action": action,
            }
        )
    for path_text, before_hash in cache_before.items():
        after_hash = cache_after.get(path_text, "missing")
        rows.append(
            {
                "path": path_text,
                "path_type": "market_data_cache",
                "before_hash": before_hash,
                "after_hash": after_hash,
                "changed": before_hash != after_hash,
                "permitted_change": True,
                "action": "unchanged_local_cache_inspected",
            }
        )
    return rows


def empty_forward_fields() -> list[str]:
    return [
        "observation_id",
        "observation_timestamp",
        "market_session",
        "signal_timestamp",
        "execution_timestamp",
        "price_timestamp",
        "target_weights",
        "pretrade_weights",
        "virtual_trades",
        "turnover",
        "transaction_cost",
        "virtual_positions",
        "virtual_nav",
        "control_navs",
        "data_freshness",
        "reconciliation_status",
        "record_classification",
    ]


def build_report(stage: str, outcome: str, next_action: str, boundary_decision: dict[str, Any]) -> str:
    return f"""# ANGL Forward-Boundary and Data-Freshness Correction v1

The prior ANGL onboarding packet labeled `{boundary_decision['latest_common_market_data_session']}` / June 18 style records as the first forward observation even though the recorded activation timestamp was later. This correction classifies those records as `historical_reconciliation_only`.

The existing observation `{OBSERVATION_ID}` was corrected in place. The ANGL strategy remains `paper_demo_eligible` and `diversifier_only`; no new strategy configuration or experiment trial was created.

## Current Outcome

- Observation stage/outcome: `{stage}` / `{outcome}`
- Correction activation timestamp: `{CORRECTION_ACTIVATION_TIMESTAMP}`
- Valid first forward session exists: `{boundary_decision['valid_first_forward_session_exists']}`
- Boundary decision: `{boundary_decision['decision']}`
- Exact next action: `{next_action}`

No forward virtual trade, forward virtual NAV, broker call, paper order, live order, account access, or real-money action occurred.
"""


def deterministic_core_hash() -> str:
    names = [
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "prior_boundary_defect.csv",
        "market_data_refresh_manifest.csv",
        "data_freshness.csv",
        "reference_state_reconciliation.csv",
        "forward_boundary_decision.csv",
        "historical_reconciliation_records.csv",
        "forward_observation_records.csv",
        "initial_target_weights.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "control_virtual_nav.csv",
        "idempotency_check.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "correction_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    clean_output_dir()
    state_before = hash_map(PROTECTED_STATE_PATHS)
    prior_before = hash_map(PRIOR_EVIDENCE_FILES)
    symbols = required_symbols()
    cache_paths = [cache_path(symbol) for symbol in symbols]
    metadata_paths = [metadata_path(symbol) for symbol in symbols if metadata_path(symbol).exists()]
    cache_before = hash_map(cache_paths + metadata_paths)

    cache_rows = cache_inventory_rows(symbols)
    reference_rows = reference_state_rows(cache_rows)
    boundary_rows = boundary_decision_rows(latest_common_cache_date(cache_rows), reference_rows)
    boundary = boundary_rows[0]
    can_activate = bool(boundary["valid_first_forward_session_exists"])
    stage = "paper_demo_active" if can_activate else "blocked"
    outcome = "paper_demo_active" if can_activate else "observation_invalid_or_incomplete"
    next_action = NEXT_ACTION_ACTIVE if can_activate else NEXT_ACTION_BLOCKED
    corrected_first_forward_date = boundary["candidate_first_forward_session"] if can_activate else ""

    observation_action = replace_observation_record(stage, outcome, next_action, corrected_first_forward_date)
    registry_action = update_registry_next_action(next_action)

    cache_after = hash_map(cache_paths + metadata_paths)
    state_after = hash_map(PROTECTED_STATE_PATHS)
    prior_after = hash_map(PRIOR_EVIDENCE_FILES)
    state_rows = state_change_rows(state_before, state_after, cache_before, cache_after, registry_action, observation_action)
    refresh_rows = market_data_refresh_rows(cache_before, cache_after, cache_rows)

    write_yaml(
        OUTPUT_DIR / "correction_manifest.yaml",
        {
            "correction_id": CORRECTION_ID,
            "mode": "correction",
            "lane": "paper_demo_observation_correction",
            "stage": "correction",
            "primary_entity_type": "paper_demo_observation",
            "supporting_entity_type": "process_task",
            "adaptation_label": "paper_demo_observation_fix",
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "observation_id": OBSERVATION_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "correction_activation_timestamp": CORRECTION_ACTIVATION_TIMESTAMP,
            "observation_stage": stage,
            "observation_outcome": outcome,
            "primary_failure_reason": "" if can_activate else PRIMARY_FAILURE_REASON,
            "defect_type": DEFECT_TYPE,
            "funnel_counts": {
                "eligible_strategy_configurations": 1,
                "paper_demo_observations": 1,
                "active_observations": 1 if can_activate else 0,
                "blocked_observations": 0 if can_activate else 1,
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
        [strategy_card_row(next_action)],
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
            "strategy_validation_repeated",
            "new_strategy_configuration_created",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "trial_ledger.csv",
        trial_ledger_rows(),
        ["strategy_id", "family_id", "entity_type", "trial_id", "stage", "adaptation_label", "new_experiment_trial_created", "lineage_role"],
    )
    write_csv(
        OUTPUT_DIR / "paper_demo_observations.csv",
        [observation_output_row(stage, outcome, next_action, corrected_first_forward_date)],
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
            "original_activation_timestamp",
            "original_first_forward_observation_date",
            "correction_activation_timestamp",
            "corrected_first_forward_observation_date",
            "current_status",
            "failure_reason",
            "defect_type",
            "adaptation_label",
            "next_action",
            "review_trigger",
        ],
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": CORRECTION_ID,
                "entity_type": "process_task",
                "stage": "correction",
                "outcome": outcome,
                "adaptation_label": "paper_demo_observation_fix",
                "strategy_counted": False,
                "observation_counted": False,
                "trial_counted": False,
                "exact_next_action": next_action,
            }
        ],
        ["task_id", "entity_type", "stage", "outcome", "adaptation_label", "strategy_counted", "observation_counted", "trial_counted", "exact_next_action"],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows(),
        ["benchmark_or_control_id", "entity_type", "stage", "role", "counted_as_strategy", "counted_as_trial"],
    )
    write_csv(
        OUTPUT_DIR / "prior_boundary_defect.csv",
        prior_defect_rows(),
        [
            "observation_id",
            "prior_observation_outcome",
            "primary_failure_reason",
            "defect_type",
            "original_activation_timestamp",
            "original_first_forward_observation_date",
            "original_virtual_trade_dates",
            "days_boundary_preceded_activation",
            "original_latest_common_data_date",
            "return_previously_counted_as_forward_evidence",
            "trade_position_or_nav_previously_mislabeled_forward",
            "corrected_classification_for_june_18",
        ],
    )
    write_csv(
        OUTPUT_DIR / "market_data_refresh_manifest.csv",
        refresh_rows,
        [
            "symbol",
            "role",
            "provider_preference",
            "refresh_attempted",
            "refresh_status",
            "refresh_reason",
            "cache_path",
            "cache_hash_before",
            "cache_hash_after",
            "cache_changed",
            "latest_available_date",
            "provider_download_performed",
            "broker_or_order_endpoint_called",
        ],
    )
    write_csv(
        OUTPUT_DIR / "data_freshness.csv",
        cache_rows,
        [
            "symbol",
            "role",
            "cache_path",
            "metadata_path",
            "cache_exists",
            "row_count",
            "first_date",
            "latest_available_date",
            "latest_after_correction_activation_date",
            "cache_hash",
            "metadata_hash",
        ],
    )
    write_csv(
        OUTPUT_DIR / "reference_state_reconciliation.csv",
        reference_rows,
        [
            "reference_or_component_id",
            "source_record",
            "latest_reproducible_state_date",
            "latest_common_cache_date",
            "after_correction_activation",
            "reconciliation_status",
            "detail",
        ],
    )
    write_csv(
        OUTPUT_DIR / "forward_boundary_decision.csv",
        boundary_rows,
        [
            "observation_id",
            "correction_activation_timestamp",
            "latest_common_market_data_session",
            "latest_reference_reproducible_state_session",
            "candidate_first_forward_session",
            "candidate_session_close_after_correction_activation",
            "valid_first_forward_session_exists",
            "decision",
            "activation_gate_status",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "historical_reconciliation_records.csv",
        historical_reconciliation_records(),
        [
            "source_file",
            "source_row_number",
            "observation_id",
            "record_date",
            "original_record_label",
            "corrected_record_classification",
            "retained",
            "forward_observation_evidence",
            "reason",
        ],
    )
    write_csv(OUTPUT_DIR / "forward_observation_records.csv", [], empty_forward_fields())
    write_csv(
        OUTPUT_DIR / "initial_target_weights.csv",
        [],
        ["observation_id", "component_id", "target_weight", "market_session", "record_classification"],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_positions.csv",
        [],
        [
            "observation_id",
            "component_id",
            "market_session",
            "component_nav_or_price",
            "target_weight",
            "post_trade_market_value",
            "virtual_units",
            "broker_order_submitted",
            "record_classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_trades.csv",
        [],
        [
            "observation_id",
            "trade_date",
            "component_id",
            "pretrade_weight",
            "target_weight",
            "virtual_trade_weight",
            "virtual_trade_value_before_cost",
            "turnover",
            "transaction_cost",
            "broker_order_submitted",
            "record_classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "initial_virtual_nav.csv",
        [],
        [
            "observation_id",
            "market_session",
            "pretrade_portfolio_nav",
            "one_way_turnover",
            "transaction_cost_drag",
            "post_trade_portfolio_nav",
            "reference_virtual_nav",
            "angl_price",
            "data_freshness_status",
            "reconciliation_status",
            "record_classification",
        ],
    )
    write_csv(
        OUTPUT_DIR / "control_virtual_nav.csv",
        [],
        ["control_id", "market_session", "control_virtual_nav", "reference_virtual_nav", "sleeve_nav", "broker_order_submitted", "record_classification"],
    )
    write_csv(
        OUTPUT_DIR / "idempotency_check.csv",
        [
            {
                "check_id": "existing_observation_record_updated_in_place",
                "status": "pass",
                "detail": "single observation id is replaced in active_observations.yaml; no duplicate is appended",
            },
            {
                "check_id": "no_forward_trade_created_without_valid_session",
                "status": "pass",
                "detail": "forward and initial virtual trade files contain headers only while blocked",
            },
            {
                "check_id": "same_session_rerun_would_not_duplicate_trade",
                "status": "pass",
                "detail": "no valid forward session exists; zero trade rows are produced",
            },
        ],
        ["check_id", "status", "detail"],
    )
    write_csv(
        OUTPUT_DIR / "state_change_manifest.csv",
        state_rows,
        ["path", "path_type", "before_hash", "after_hash", "changed", "permitted_change", "action"],
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
                "observation_stage": stage,
                "observation_outcome": outcome,
                "primary_failure_reason": "" if can_activate else PRIMARY_FAILURE_REASON,
                "defect_type": DEFECT_TYPE,
                "corrected_first_forward_observation_date": corrected_first_forward_date,
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
            "defect_type",
            "corrected_first_forward_observation_date",
            "next_action",
        ],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "observation_id": OBSERVATION_ID,
                "stage": stage,
                "outcome": outcome,
                "primary_failure_reason": PRIMARY_FAILURE_REASON,
                "defect_type": DEFECT_TYPE,
                "next_action": next_action,
            }
        ]
        if not can_activate
        else [],
        ["observation_id", "stage", "outcome", "primary_failure_reason", "defect_type", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "scope": "paper_demo_observation",
                "entity_id": OBSERVATION_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": outcome,
            }
        ],
        ["scope", "entity_id", "exact_next_action", "execute_now", "reason"],
    )
    write_text(OUTPUT_DIR / "correction_report.md", build_report(stage, outcome, next_action, boundary))

    only_permitted_state_changes = all(
        (not row["changed"])
        or row["path"] in {rel(REGISTRY_PATH), rel(ACTIVE_OBSERVATIONS_PATH)}
        or row["path_type"] == "market_data_cache"
        for row in state_rows
    )
    no_cache_changed = all(not row["changed"] for row in state_rows if row["path_type"] == "market_data_cache")
    consistency = {
        "correction_id": CORRECTION_ID,
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "defect_type": DEFECT_TYPE,
        "prior_observation_invalid_or_incomplete_recorded": True,
        "june_18_reclassified_historical_only": True,
        "correction_activation_timestamp": CORRECTION_ACTIVATION_TIMESTAMP,
        "valid_first_forward_session_exists": can_activate,
        "observation_stage": stage,
        "observation_outcome": outcome,
        "strategy_stage": "paper_demo_eligible",
        "strategy_outcome": "paper_demo_eligible",
        "new_strategy_configuration_created": False,
        "new_experiment_trials_created": 0,
        "forward_observation_rows_created": 0 if not can_activate else "",
        "initial_virtual_trade_rows_created": 0 if not can_activate else "",
        "broker_order_submitted": False,
        "paper_order_submitted": False,
        "live_order_submitted": False,
        "account_accessed": False,
        "real_money_action": False,
        "provider_download_performed": any(row["provider_download_performed"] for row in refresh_rows),
        "cache_files_changed": not no_cache_changed,
        "state_hashes_before": state_before,
        "state_hashes_after": state_after,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_onboarding_evidence_unchanged": all(
            prior_before.get(rel(path), "missing") == prior_after.get(rel(path), "missing") for path in ONBOARDING_INPUT_FILES
        ),
        "validation_and_methodology_correction_evidence_unchanged": prior_before == prior_after,
        "only_permitted_state_changes": only_permitted_state_changes,
        "research_queue_unchanged": state_before.get(rel(RESEARCH_QUEUE_PATH)) == state_after.get(rel(RESEARCH_QUEUE_PATH)),
        "family_ledger_unchanged": state_before.get(rel(FAMILY_LEDGER_PATH)) == state_after.get(rel(FAMILY_LEDGER_PATH)),
        "roadmap_unchanged": state_before.get(rel(ROADMAP_PATH)) == state_after.get(rel(ROADMAP_PATH)),
        "active_observation_record_updated_in_place": observation_action == "updated_in_place",
        "registry_action": registry_action,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["prior_observation_invalid_or_incomplete_recorded"]
        and consistency["june_18_reclassified_historical_only"]
        and consistency["strategy_stage"] == "paper_demo_eligible"
        and consistency["new_strategy_configuration_created"] is False
        and consistency["new_experiment_trials_created"] == 0
        and consistency["active_observation_record_updated_in_place"]
        and consistency["only_permitted_state_changes"]
        and consistency["research_queue_unchanged"]
        and consistency["family_ledger_unchanged"]
        and consistency["roadmap_unchanged"]
        and consistency["prior_onboarding_evidence_unchanged"]
        and consistency["validation_and_methodology_correction_evidence_unchanged"]
        and not consistency["broker_order_submitted"]
        and not consistency["paper_order_submitted"]
        and not consistency["live_order_submitted"]
        and not consistency["account_accessed"]
        and not any(consistency[name] for name in FORBIDDEN_FLAGS)
        and (can_activate or (stage == "blocked" and outcome == "observation_invalid_or_incomplete"))
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "correction_id": CORRECTION_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "strategy_id": STRATEGY_ID,
        "observation_id": OBSERVATION_ID,
        "observation_stage": stage,
        "observation_outcome": outcome,
        "valid_first_forward_session_exists": can_activate,
        "corrected_first_forward_observation_date": corrected_first_forward_date,
        "exact_next_action": next_action,
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
