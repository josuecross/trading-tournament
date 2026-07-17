from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "evidence" / "usci_paper_forward_eligibility_review_v1" / "latest"
BOUNDED_SCREEN_DIR = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
VALIDATION_DIR = ROOT / "evidence" / "usci_current_methodology_validation_v1" / "latest"
ACTIVE_COMBO_DIR = ROOT / "evidence" / "active_combo_benchmark" / "latest"
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
OBSERVATION_DIR = ROOT / "paper_forward_observations" / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"

CANDIDATE_ID = "usci_dynamic_commodity_curve_selection_wrapper_v1"
OBSERVATION_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
FAMILY_ID = "commodity_curve_selection"
ROLE = "commodity_curve_selection_diversifier"
PRIMARY_BENCHMARK = "DBC"
SECONDARY_REFERENCES = ("BIL", "SPY")
ACTIVE_VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
ACTIVE_DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
SYMBOLS = ("USCI", "DBC", "BIL", "SPY")
REVIEW_DECISIONS = {
    "approve_usci_paper_forward_observation",
    "usci_paper_forward_blocked_by_operational_gap",
    "usci_evidence_insufficient_close_exact_candidate",
    "invalid_evidence_requires_correction",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def directory_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {rel(item): sha256_path(item) for item in sorted(path.rglob("*")) if item.is_file()}


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def clean_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def read_adjusted_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return clean.set_index("date")[symbol].astype(float)


def load_price_frame(symbols: tuple[str, ...] = SYMBOLS) -> pd.DataFrame:
    series = {symbol: read_adjusted_close(symbol) for symbol in symbols}
    common = series[symbols[0]].index
    for symbol in symbols[1:]:
        common = common.intersection(series[symbol].index)
    common = pd.DatetimeIndex(common).sort_values()
    return pd.DataFrame({symbol: series[symbol].reindex(common) for symbol in symbols}).dropna()


def pct_returns(series: pd.Series) -> pd.Series:
    return series.astype(float).pct_change().dropna()


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1, join="inner").dropna()
    if len(aligned) < 3:
        return float("nan")
    return float(aligned["left"].corr(aligned["right"]))


def evidence_integrity_gate() -> tuple[list[dict[str, Any]], bool]:
    bounded_consistency = read_json(BOUNDED_SCREEN_DIR / "consistency_check.json")
    validation_consistency = read_json(VALIDATION_DIR / "consistency_check.json")
    cache_verification = read_json(VALIDATION_DIR / "cache_hash_verification.json")
    validation_manifest = read_json(VALIDATION_DIR / "validation_manifest.json")
    prior_lineage = read_json(VALIDATION_DIR / "prior_screen_lineage.json")
    current_invariants = read_csv_rows(VALIDATION_DIR / "accounting_data_and_alignment_invariants.csv")
    transition = read_csv_rows(VALIDATION_DIR / "frozen_transition_interval.csv")
    bounded_outcome = read_json(BOUNDED_SCREEN_DIR / "screening_outcome.json")
    validation_outcome = read_json(VALIDATION_DIR / "validation_outcome.json")
    prior_fingerprint = read_json(BOUNDED_SCREEN_DIR / "candidate_fingerprint.json")

    checks = [
        {
            "gate": "bounded_screen_consistency",
            "required": "consistency_passed true",
            "observed": bounded_consistency.get("consistency_passed"),
            "passed": bounded_consistency.get("consistency_passed") is True,
        },
        {
            "gate": "current_validation_consistency",
            "required": "consistency_passed true",
            "observed": validation_consistency.get("consistency_passed"),
            "passed": validation_consistency.get("consistency_passed") is True,
        },
        {
            "gate": "formal_bounded_outcome_preserved",
            "required": "methodology_regime_instability",
            "observed": bounded_outcome.get("outcome"),
            "passed": bounded_outcome.get("outcome") == "methodology_regime_instability",
        },
        {
            "gate": "formal_validation_outcome_preserved",
            "required": "historical_edge_recently_weakened",
            "observed": validation_outcome.get("outcome"),
            "passed": validation_outcome.get("outcome") == "historical_edge_recently_weakened",
        },
        {
            "gate": "cache_hashes_match_prior",
            "required": "validation cache hashes match bounded screen lineage",
            "observed": cache_verification.get("cache_hash_verification_passed"),
            "passed": cache_verification.get("cache_hash_verification_passed") is True
            and cache_verification.get("hash_mismatches") == [],
        },
        {
            "gate": "candidate_fingerprint_unchanged",
            "required": "same candidate fingerprint",
            "observed": prior_lineage.get("prior_candidate_fingerprint", {}).get("strategy_fingerprint"),
            "passed": prior_lineage.get("prior_candidate_fingerprint") == prior_fingerprint
            and validation_consistency.get("candidate_fingerprint_unchanged") is True,
        },
        {
            "gate": "dbc_primary_benchmark",
            "required": "DBC_buy_and_hold",
            "observed": validation_manifest.get("primary_benchmark"),
            "passed": validation_manifest.get("primary_benchmark") == "DBC_buy_and_hold",
        },
        {
            "gate": "adjusted_total_return_prices",
            "required": "adjusted prices used",
            "observed": validation_consistency.get("adjusted_total_return_prices_used"),
            "passed": validation_consistency.get("adjusted_total_return_prices_used") is True,
        },
        {
            "gate": "research_runs_did_not_change_registry_or_observations",
            "required": "registry and existing observations unchanged by research packets",
            "observed": {
                "registry_byte_identical": validation_consistency.get("registry_byte_identical"),
                "vm_dsr_active_combo_unchanged": validation_consistency.get("vm_dsr_active_combo_unchanged"),
            },
            "passed": validation_consistency.get("registry_byte_identical") is True
            and validation_consistency.get("vm_dsr_active_combo_unchanged") is True,
        },
        {
            "gate": "accounting_methodology_invariants",
            "required": "invariants passed",
            "observed": current_invariants[0].get("invariants_passed") if current_invariants else "",
            "passed": bool(current_invariants) and current_invariants[0].get("invariants_passed") == "true",
        },
        {
            "gate": "december_2020_methodology_boundary",
            "required": "transition documented and excluded",
            "observed": transition[0] if transition else {},
            "passed": bool(transition)
            and transition[0].get("start_date") == "2020-12-24"
            and transition[0].get("end_date") == "2020-12-31"
            and transition[0].get("included_in_validation_metrics") == "false",
        },
    ]
    return checks, all(bool(row["passed"]) for row in checks)


def historical_evidence_gate() -> tuple[list[dict[str, Any]], bool]:
    full = {row["symbol"]: row for row in read_csv_rows(VALIDATION_DIR / "full_current_regime_metrics.csv")}
    rolling = {
        (row["window_type"], int(row["horizon_days"])): row
        for row in read_csv_rows(VALIDATION_DIR / "rolling_summary.csv")
        if row.get("horizon_days")
    }
    thirds = read_csv_rows(VALIDATION_DIR / "chronological_thirds_results.csv")
    calendar = read_csv_rows(VALIDATION_DIR / "calendar_year_results.csv")
    usci = full["USCI"]
    complete_years = [row for row in calendar if row.get("period_type") == "complete_calendar_year"]
    complete_year_wins = sum(row.get("USCI_beats_DBC") == "true" for row in complete_years)
    positive_thirds = sum(float(row["excess_return_versus_DBC"]) > 0 for row in thirds)
    latest_252 = float(rolling[("monthly_start_overlapping", 252)]["latest_window_excess_return"])
    latest_504 = float(rolling[("monthly_start_overlapping", 504)]["latest_window_excess_return"])
    checks = [
        {
            "gate": "full_current_excess_positive",
            "threshold": "> 0",
            "observed": float(usci["excess_total_return_versus_DBC"]),
            "passed": float(usci["excess_total_return_versus_DBC"]) > 0,
        },
        {
            "gate": "annualized_excess_positive",
            "threshold": "> 0",
            "observed": float(usci["annualized_excess_return_versus_DBC"]),
            "passed": float(usci["annualized_excess_return_versus_DBC"]) > 0,
        },
        *[
            {
                "gate": f"median_{horizon}d_excess_positive",
                "threshold": "> 0",
                "observed": float(rolling[("monthly_start_overlapping", horizon)]["median_excess_versus_DBC"]),
                "passed": float(rolling[("monthly_start_overlapping", horizon)]["median_excess_versus_DBC"]) > 0,
            }
            for horizon in (180, 252, 504)
        ],
        *[
            {
                "gate": f"win_rate_{horizon}d_above_50pct",
                "threshold": "> 0.5",
                "observed": float(rolling[("monthly_start_overlapping", horizon)]["USCI_win_rate_versus_DBC"]),
                "passed": float(rolling[("monthly_start_overlapping", horizon)]["USCI_win_rate_versus_DBC"]) > 0.5,
            }
            for horizon in (252, 504)
        ],
        {
            "gate": "at_least_two_chronological_thirds_beat_DBC",
            "threshold": ">= 2",
            "observed": positive_thirds,
            "passed": positive_thirds >= 2,
        },
        {
            "gate": "at_least_three_complete_calendar_years_beat_DBC",
            "threshold": ">= 3 of 5",
            "observed": f"{complete_year_wins} of {len(complete_years)}",
            "passed": complete_year_wins >= 3 and len(complete_years) == 5,
        },
        {
            "gate": "max_drawdown_not_more_than_five_points_worse_than_DBC",
            "threshold": "drawdown_difference >= -0.05",
            "observed": float(usci["drawdown_difference_versus_DBC"]),
            "passed": float(usci["drawdown_difference_versus_DBC"]) >= -0.05,
        },
        {
            "gate": "at_least_one_latest_252_or_504_positive",
            "threshold": "latest 252d > 0 or latest 504d > 0",
            "observed": {"latest_252d": latest_252, "latest_504d": latest_504},
            "passed": latest_252 > 0 or latest_504 > 0,
        },
    ]
    return checks, all(bool(row["passed"]) for row in checks)


def recent_weakness_disclosure() -> dict[str, Any]:
    rolling = {
        int(row["horizon_days"]): row
        for row in read_csv_rows(VALIDATION_DIR / "rolling_summary.csv")
        if row.get("window_type") == "monthly_start_overlapping"
    }
    negative = {
        f"latest_{horizon}d_excess": float(rolling[horizon]["latest_window_excess_return"])
        for horizon in (90, 180, 252, 504)
        if float(rolling[horizon]["latest_window_excess_return"]) < 0
    }
    return {
        "risk_label": "current_short_horizon_relative_weakness",
        "formal_validation_outcome_remains": "historical_edge_recently_weakened",
        "negative_latest_horizons": negative,
        "latest_504d_excess": float(rolling[504]["latest_window_excess_return"]),
        "interpretation": "Recent 90d, 180d, and 252d relative weakness is retained as monitoring risk; it does not override the broader frozen historical evidence gate.",
    }


def diversification_and_redundancy() -> tuple[list[dict[str, Any]], bool]:
    prices = load_price_frame(SYMBOLS).loc["2021-01-04":"2026-06-18"]
    usci_returns = pct_returns(prices["USCI"]).rename("USCI")
    spy_returns = pct_returns(prices["SPY"]).rename("SPY")
    spy_drawdown = prices["SPY"] / prices["SPY"].cummax() - 1.0
    combo = pd.read_csv(ACTIVE_COMBO_DIR / "active_combo_equity_series.csv")
    combo["date"] = pd.to_datetime(combo["date"], errors="coerce").dt.tz_localize(None)
    combo = combo.dropna(subset=["date"]).set_index("date").sort_index()
    references = {
        ACTIVE_VM_ID: combo["vm_standalone_equity"].astype(float).pct_change().dropna(),
        ACTIVE_DSR_ID: combo["dsr_standalone_equity"].astype(float).pct_change().dropna(),
        ACTIVE_COMBO_ID: combo["active_combo_daily_return"].astype(float).dropna(),
        "SPY": spy_returns,
    }
    rows: list[dict[str, Any]] = []
    for ref_id, ref_returns in references.items():
        aligned = pd.concat(
            [
                usci_returns.rename("USCI"),
                ref_returns.rename(ref_id),
                spy_returns.rename("SPY_context_return"),
                spy_drawdown.rename("SPY_drawdown"),
            ],
            axis=1,
            join="inner",
        ).dropna()
        spy_drawdown_subset = aligned[aligned["SPY_drawdown"] < 0.0]
        downside_subset = aligned[aligned["SPY_context_return"] < 0.0]
        simultaneous_negative = float(((aligned["USCI"] < 0.0) & (aligned[ref_id] < 0.0)).mean()) if len(aligned) else float("nan")
        corr = safe_corr(aligned["USCI"], aligned[ref_id])
        row = {
            "candidate_id": CANDIDATE_ID,
            "reference_id": ref_id,
            "common_start": aligned.index.min().date().isoformat() if len(aligned) else "",
            "common_end": aligned.index.max().date().isoformat() if len(aligned) else "",
            "aligned_daily_return_count": int(len(aligned)),
            "daily_return_correlation": corr,
            "correlation_during_SPY_drawdowns": safe_corr(spy_drawdown_subset["USCI"], spy_drawdown_subset[ref_id])
            if len(spy_drawdown_subset)
            else float("nan"),
            "downside_period_correlation_SPY_negative_days": safe_corr(downside_subset["USCI"], downside_subset[ref_id])
            if len(downside_subset)
            else float("nan"),
            "simultaneous_negative_day_pct": simultaneous_negative,
            "clear_operational_redundancy": bool(ref_id in {ACTIVE_VM_ID, ACTIVE_DSR_ID} and abs(corr) >= 0.90),
            "different_market_and_return_mechanism": ref_id in {ACTIVE_VM_ID, ACTIVE_DSR_ID, ACTIVE_COMBO_ID, "SPY"},
            "gate_passed_for_reference": not bool(ref_id in {ACTIVE_VM_ID, ACTIVE_DSR_ID} and abs(corr) >= 0.90),
        }
        rows.append(row)
    clearly_redundant_with_both = all(
        row["clear_operational_redundancy"] is True for row in rows if row["reference_id"] in {ACTIVE_VM_ID, ACTIVE_DSR_ID}
    )
    gate_passed = not clearly_redundant_with_both
    return rows, gate_passed


def operational_eligibility() -> tuple[list[dict[str, Any]], bool]:
    active_state = load_yaml(ACTIVE_OBSERVATIONS_PATH)
    existing_ids = {str(row.get("strategy_id")) for row in active_state.get("active_observations", [])}
    conflicting_duplicate = OBSERVATION_ID in existing_ids and not (OBSERVATION_DIR / "active_observation.yaml").exists()
    cache_rows = []
    for symbol in SYMBOLS:
        series = read_adjusted_close(symbol)
        cache_rows.append(
            {
                "symbol": symbol,
                "cache_exists": cache_path(symbol).exists(),
                "cache_path": rel(cache_path(symbol)),
                "latest_cache_date": series.index.max().date().isoformat(),
                "adjusted_close_ready": bool(len(series) > 0 and (series > 0).all()),
            }
        )
    checks = [
        ("static_long_only_usci_position", True, "100% USCI target can be represented"),
        ("no_leverage", True, "configuration freezes leverage false"),
        ("no_shorting", True, "configuration freezes shorting false"),
        ("no_tactical_switching", True, "configuration freezes timing signal none and BIL switch none"),
        ("no_internal_futures_reconstruction", True, "configuration freezes futures reconstruction false"),
        ("dbc_primary_benchmark", True, "DBC benchmark specified"),
        ("observation_only_tracking", True, "paper-forward active observation only; no promotion or orders"),
        ("current_price_mark_to_market", all(row["adjusted_close_ready"] for row in cache_rows), "local adjusted-close cache can mark current virtual equity"),
        ("distribution_aware_return_handling", all(row["adjusted_close_ready"] for row in cache_rows), "adjusted close includes distributions/corporate actions"),
        ("approved_local_data_path", all(row["cache_exists"] for row in cache_rows), "existing local cache only"),
        ("no_conflicting_duplicate_active_usci_observation", not conflicting_duplicate, "idempotent same observation allowed; conflicting duplicate disallowed"),
    ]
    rows = [
        {
            "check": name,
            "passed": passed,
            "notes": notes,
            "cache_symbols": "|".join(row["symbol"] for row in cache_rows) if "cache" in name or "data" in name else "",
        }
        for name, passed, notes in checks
    ]
    return rows, all(row["passed"] for row in rows)


def latest_common_snapshot() -> dict[str, Any]:
    prices = load_price_frame(SYMBOLS)
    latest_date = prices.index.max()
    latest = prices.loc[latest_date]
    usci_price = float(latest["USCI"])
    initial_capital = float(active.STARTING_EQUITY)
    initial_cost = initial_capital * float(active.SLIPPAGE)
    invested = initial_capital - initial_cost
    shares = invested / usci_price
    return {
        "activation_date": latest_date.date().isoformat(),
        "snapshot_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_data_source": "existing_local_adjusted_close_cache",
        "snapshot_common_date": latest_date.date().isoformat(),
        "initial_virtual_capital": initial_capital,
        "initial_transaction_cost_pct": float(active.SLIPPAGE),
        "initial_transaction_cost_dollars": initial_cost,
        "initial_observed_price": usci_price,
        "initial_virtual_shares": shares,
        "initial_virtual_cash": 0.0,
        "target": "100% USCI",
        "benchmark_starting_prices": {symbol: float(latest[symbol]) for symbol in SYMBOLS if symbol != "USCI"},
        "candidate_starting_price": usci_price,
        "provider_download": False,
        "broker_order_placed": False,
        "live_order_placed": False,
        "paper_order_placed": False,
    }


def observation_configuration(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "observation_id": OBSERVATION_ID,
        "source_candidate": CANDIDATE_ID,
        "family": FAMILY_ID,
        "role": ROLE,
        "candidate_instrument": "USCI",
        "primary_benchmark": PRIMARY_BENCHMARK,
        "secondary_references": list(SECONDARY_REFERENCES),
        "target": "100% USCI",
        "rebalance": "none after observation initialization",
        "leverage": False,
        "shorting": False,
        "timing_signal": "none",
        "BIL_switch": "none",
        "futures_reconstruction": False,
        "paper_forward_active": True,
        "real_money_recommendation": False,
        "live_money_trading": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "automatic_promotion": False,
        "initial_virtual_capital": snapshot["initial_virtual_capital"],
        "minimum_days_before_judgment": 30,
        "monitoring_fields": [
            "USCI_virtual_equity",
            "DBC_benchmark_equity",
            "SPY_reference_equity",
            "BIL_reference_equity",
            "excess_return_versus_DBC",
            "drawdown",
            "drawdown_difference_versus_DBC",
            "rolling_30_calendar_day_relative_return",
            "rolling_90_calendar_day_relative_return",
            "rolling_180_calendar_day_relative_return",
            "rolling_252_calendar_day_relative_return",
            "data_freshness",
            "missing_price_status",
            "corporate_action_status",
            "observation_age",
        ],
    }


def registry_row_block() -> str:
    return f"""
- id: {OBSERVATION_ID}
  display_name: Paper Forward USCI Dynamic Commodity Curve Selection Wrapper v1
  lane: paper_forward
  instrument_family: ETF
  strategy_family: {FAMILY_ID}
  version: v1
  parent_id: {CANDIDATE_ID}
  credibility_tier: tier4_paper_forward
  status: active_paper_demo_observation
  role: {ROLE}
  rules_frozen: true
  paper_forward_active: true
  implementation_status: implemented
  data_source: existing_adjusted_etf_cache
  evidence_source: usci_paper_forward_eligibility_review_v1
  latest_evidence_path: evidence/usci_paper_forward_eligibility_review_v1/latest/
  latest_known_result_summary: Direction-owner override preserves formal historical_edge_recently_weakened validation label but approves observation-only paper-forward monitoring for exact static USCI wrapper versus DBC.
  allowed_next_action: observe_only
  forbidden_next_actions:
  - change_rules
  - tune_parameters
  - run_candidate_exhaustive
  - promote_to_real_money
  - add_broker_integration
  - place_orders
  - place_live_orders
  risk_framework_status: paper_forward_allowed_direction_owner_override_observation_only
  paper_forward_allowed_by_risk_framework: true
  real_money_recommendation: false
  promotion_blockers: no_real_money_promotion;observation_only;recent_short_horizon_relative_weakness
  promotion_requirements: Observation-only monitoring and future independent review before any promotion.
  demotion_or_kill_criteria: Persistent relative weakness versus DBC, data quality failure, redundancy, or owner decision.
  notes: Static investable-wrapper observation only. Buy-and-hold USCI versus DBC; no timing, futures reconstruction, leverage, shorting, broker path, orders, or real-money recommendation.
  strategy_id: {OBSERVATION_ID}
  family: {FAMILY_ID}
  instrument_lane: ETF
  evidence_tier: tier4_paper_forward
  current_status: active_paper_demo_observation
  allowed_next_actions:
  - observe_only
  candidate_exhaustive_run: false
  candidate_exhaustive_recommended: false
  promotion_review_required: false
  promotion_decision: paper_forward_observation_approved_direction_owner_override
  promotion_reason: Historical evidence gate passed using frozen current-methodology packet; recent weakness disclosed as monitoring risk.
  primary_failure_mode: current_short_horizon_relative_weakness
  duplication_risk: not_redundant_with_active_vm_or_dsr
  risk_budget_status: active_observation
  evidence_needed: observation evidence only; no real-money conclusion
  duplicate_of: ''
  blocked_reason: ''
  frozen: true
  latest_active_evidence_recompute_path: ''
  active_evidence_audit_decision: usci_observation_only_not_recomputed_active_strategy
  active_evidence_recompute_completed: false
  manual_review_required: false
  no_candidate_exhaustive_run: true
  no_paper_forward_checkpoint: true
  no_real_money_recommendation: true
"""


def ensure_registry_row() -> str:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    if "active_observations_count: 2" in text:
        text = text.replace("active_observations_count: 2", "active_observations_count: 3", 1)
    if f"id: {OBSERVATION_ID}" in text:
        REGISTRY_PATH.write_text(text, encoding="utf-8")
        return "ensured_present_existing"
    REGISTRY_PATH.write_text(text.rstrip() + "\n" + registry_row_block().lstrip(), encoding="utf-8")
    return "ensured_present_added"


def active_observation_block() -> str:
    return f"""- strategy_id: {OBSERVATION_ID}
  state: active_accepted_frozen_observation
  paper_forward_active: true
  protected: true
"""


def ensure_active_observations_record() -> str:
    text = ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    changed = False
    if OBSERVATION_ID not in text:
        marker = "benchmark_controls:\n"
        if marker not in text:
            raise RuntimeError("active_observations.yaml missing benchmark_controls marker")
        text = text.replace(marker, active_observation_block() + marker, 1)
        changed = True
    if "latest_usci_paper_forward_eligibility_review:" not in text:
        text = text.rstrip() + f"""
latest_usci_paper_forward_eligibility_review:
  evidence_path: {rel(OUTPUT_DIR)}
  observation_id: {OBSERVATION_ID}
  source_candidate: {CANDIDATE_ID}
  direction_owner_override: true
  formal_validation_label_unchanged: historical_edge_recently_weakened
  paper_forward_active: true
  broker_integration: false
  live_orders: false
  real_money_recommendation: false
  next_action: observe_usci_paper_forward_without_orders
"""
        changed = True
    if changed:
        ACTIVE_OBSERVATIONS_PATH.write_text(text, encoding="utf-8")
        return "ensured_present_added"
    return "ensured_present_existing"


def write_observation_yaml(config: dict[str, Any], snapshot: dict[str, Any]) -> str:
    OBSERVATION_DIR.mkdir(parents=True, exist_ok=True)
    target = OBSERVATION_DIR / "active_observation.yaml"
    existing = load_yaml(target) if target.exists() else {}
    payload = {
        "observation_id": OBSERVATION_ID,
        "base_strategy_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "role": ROLE,
        "status": "active_paper_demo_observation",
        "account_type": "simulated_paper_demo_only",
        "evidence_source": "usci_paper_forward_eligibility_review_v1",
        "frozen": True,
        "rules_frozen": True,
        "paper_forward_active": True,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "leverage": False,
        "margin": False,
        "shorting": False,
        "options": False,
        "futures": False,
        "forex": False,
        "crypto": False,
        "intraday": False,
        "minimum_days_before_judgment": 30,
        "current_checkpoint_status": "activated_observation_only_no_conclusion",
        "candidate_instrument": "USCI",
        "primary_benchmark": "DBC",
        "secondary_references": ["BIL", "SPY"],
        "initial_virtual_capital": snapshot["initial_virtual_capital"],
        "initial_observation_date": snapshot["activation_date"],
        "initial_observed_price": snapshot["initial_observed_price"],
        "initial_virtual_shares": snapshot["initial_virtual_shares"],
        "initial_virtual_cash": snapshot["initial_virtual_cash"],
        "rule_summary": [
            "Static observation-only wrapper.",
            "Hold 100% USCI after observation initialization.",
            "No external rebalance, timing signal, BIL switch, futures reconstruction, leverage, or shorting.",
            "DBC is the frozen primary benchmark; BIL and SPY are secondary references.",
        ],
        "universe": ["USCI", "DBC", "BIL", "SPY"],
        "monitoring_risks": ["current_short_horizon_relative_weakness"],
    }
    merged_payload = dict(existing)
    merged_payload.update(payload)
    previous = target.read_text(encoding="utf-8") if target.exists() else ""
    text = yaml.safe_dump(merged_payload, sort_keys=False)
    target.write_text(text, encoding="utf-8")
    return "ensured_present_existing" if previous == text else "ensured_present_written"


def source_of_truth_updates(config: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    registry_action = ensure_registry_row()
    active_action = ensure_active_observations_record()
    obs_action = write_observation_yaml(config, snapshot)
    return [
        {
            "source_of_truth": rel(REGISTRY_PATH),
            "change": "ensure_active_usci_observation_registry_row",
            "action": registry_action,
            "changes_existing_vm_dsr_or_combo": False,
        },
        {
            "source_of_truth": rel(ACTIVE_OBSERVATIONS_PATH),
            "change": "ensure_usci_active_observation_list_entry_and_direction_record",
            "action": active_action,
            "changes_existing_vm_dsr_or_combo": False,
        },
        {
            "source_of_truth": rel(OBSERVATION_DIR / "active_observation.yaml"),
            "change": "ensure_usci_observation_configuration",
            "action": obs_action,
            "changes_existing_vm_dsr_or_combo": False,
        },
    ]


def protected_state_paths() -> list[Path]:
    return [
        ROOT / "paper_forward_observations" / ACTIVE_VM_ID / "active_observation.yaml",
        ROOT / "paper_forward_observations" / ACTIVE_DSR_ID / "active_observation.yaml",
        ACTIVE_COMBO_DIR / "active_combo_benchmark_definition.yaml",
        ACTIVE_COMBO_DIR / "active_combo_manifest.json",
        ACTIVE_COMBO_DIR / "active_combo_equity_series.csv",
    ]


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bounded_before = directory_snapshot(BOUNDED_SCREEN_DIR)
    validation_before = directory_snapshot(VALIDATION_DIR)
    cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    protected_before = file_snapshot(protected_state_paths())

    integrity_rows, integrity_passed = evidence_integrity_gate()
    historical_rows, historical_passed = historical_evidence_gate()
    diversification_rows, diversification_passed = diversification_and_redundancy()
    operational_rows, operational_passed = operational_eligibility()
    weakness = recent_weakness_disclosure()

    if not integrity_passed:
        decision = "invalid_evidence_requires_correction"
        reason = "one_or_more_evidence_integrity_gates_failed"
    elif not historical_passed:
        decision = "usci_evidence_insufficient_close_exact_candidate"
        reason = "one_or_more_frozen_historical_evidence_gates_failed"
    elif not diversification_passed:
        decision = "usci_paper_forward_blocked_by_operational_gap"
        reason = "usci_redundant_with_both_active_observations"
    elif not operational_passed:
        decision = "usci_paper_forward_blocked_by_operational_gap"
        reason = "paper_forward_architecture_or_data_path_gap"
    else:
        decision = "approve_usci_paper_forward_observation"
        reason = "all_frozen_eligibility_gates_passed"

    snapshot: dict[str, Any] = {}
    config: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    if decision == "approve_usci_paper_forward_observation":
        snapshot = latest_common_snapshot()
        config = observation_configuration(snapshot)
        changes = source_of_truth_updates(config, snapshot)

    bounded_after = directory_snapshot(BOUNDED_SCREEN_DIR)
    validation_after = directory_snapshot(VALIDATION_DIR)
    cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    protected_after = file_snapshot(protected_state_paths())

    historical_packets_unchanged = bounded_before == bounded_after and validation_before == validation_after
    cache_unchanged = cache_before == cache_after
    protected_unchanged = protected_before == protected_after

    write_json(
        OUTPUT_DIR / "review_manifest.json",
        {
            "review_id": "usci_paper_forward_eligibility_review_v1",
            "candidate_id": CANDIDATE_ID,
            "observation_id": OBSERVATION_ID,
            "family": FAMILY_ID,
            "role": ROLE,
            "combined_promotion_review_and_paper_forward_eligibility_review": True,
            "historical_backtest_run": False,
            "historical_validation_run": False,
            "candidate_exhaustive_run": False,
            "provider_download": False,
            "cache_refresh": False,
            "blended_portfolio_constructed": False,
            "broker_integration": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
            "decision": decision,
            "next_action": "observe_usci_paper_forward_without_orders"
            if decision == "approve_usci_paper_forward_observation"
            else "resolve_usci_paper_forward_review_blocker",
        },
    )
    write_json(
        OUTPUT_DIR / "authoritative_evidence_lineage.json",
        {
            "bounded_screen_path": rel(BOUNDED_SCREEN_DIR),
            "bounded_screen_outcome": "methodology_regime_instability",
            "bounded_screen_hashes_before": bounded_before,
            "bounded_screen_hashes_after": bounded_after,
            "current_validation_path": rel(VALIDATION_DIR),
            "current_validation_outcome": "historical_edge_recently_weakened",
            "current_validation_hashes_before": validation_before,
            "current_validation_hashes_after": validation_after,
            "historical_packets_byte_identical_after_review": historical_packets_unchanged,
        },
    )
    write_csv(OUTPUT_DIR / "evidence_integrity_gate.csv", integrity_rows)
    write_csv(OUTPUT_DIR / "historical_evidence_gate.csv", historical_rows)
    write_json(OUTPUT_DIR / "recent_weakness_disclosure.json", weakness)
    write_csv(OUTPUT_DIR / "diversification_and_redundancy.csv", diversification_rows)
    write_csv(OUTPUT_DIR / "operational_eligibility.csv", operational_rows)
    write_json(
        OUTPUT_DIR / "paper_forward_decision.json",
        {
            "candidate_id": CANDIDATE_ID,
            "observation_id": OBSERVATION_ID if decision == "approve_usci_paper_forward_observation" else "",
            "decision": decision,
            "decision_reason": reason,
            "allowed_decisions": sorted(REVIEW_DECISIONS),
            "paper_forward_active": decision == "approve_usci_paper_forward_observation",
            "promotion_authorized": False,
            "automatic_promotion": False,
            "candidate_exhaustive_authorized": False,
            "broker_integration": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
            "next_action": "observe_usci_paper_forward_without_orders"
            if decision == "approve_usci_paper_forward_observation"
            else "resolve_usci_paper_forward_review_blocker",
        },
    )
    write_json(
        OUTPUT_DIR / "direction_owner_override.json",
        {
            "candidate_id": CANDIDATE_ID,
            "formal_validation_label_remains_unchanged": "historical_edge_recently_weakened",
            "recent_short_horizon_weakness_acknowledged": True,
            "automatic_exact_candidate_closure_overridden": True,
            "candidate_current_handling": "paper_forward_review_candidate",
            "broader_current_methodology_evidence_supports_paper_forward_review": historical_passed,
            "paper_forward_observation_is_evidence_gathering_not_proof_or_promotion": True,
            "historical_results_retroactively_changed": False,
            "historical_labels_retroactively_changed": False,
        },
    )
    if config:
        write_json(OUTPUT_DIR / "observation_configuration.json", config)
        write_json(OUTPUT_DIR / "observation_initialization.json", snapshot)
    write_json(
        OUTPUT_DIR / "protected_state_verification.json",
        {
            "existing_vm_dsr_active_combo_unchanged": protected_unchanged,
            "protected_hashes_before": protected_before,
            "protected_hashes_after": protected_after,
            "existing_observation_capital_changed": False,
            "active_vm_id": ACTIVE_VM_ID,
            "active_dsr_id": ACTIVE_DSR_ID,
            "active_combo_id": ACTIVE_COMBO_ID,
            "new_usci_observation_added": decision == "approve_usci_paper_forward_observation",
        },
    )
    write_csv(
        OUTPUT_DIR / "source_of_truth_changes.csv",
        changes
        or [
            {
                "source_of_truth": "",
                "change": "none",
                "action": "not_approved",
                "changes_existing_vm_dsr_or_combo": False,
            }
        ],
        ["source_of_truth", "change", "action", "changes_existing_vm_dsr_or_combo"],
    )
    consistency = {
        "historical_packets_byte_identical": historical_packets_unchanged,
        "formal_historical_labels_unchanged": all(
            row["passed"]
            for row in integrity_rows
            if row["gate"] in {"formal_bounded_outcome_preserved", "formal_validation_outcome_preserved"}
        ),
        "candidate_closure_overridden_only_in_new_direction_record": True,
        "historical_gate_passed": historical_passed,
        "negative_latest_252_alone_did_not_force_closure": decision == "approve_usci_paper_forward_observation"
        and weakness["negative_latest_horizons"].get("latest_252d_excess", 1.0) < 0,
        "usci_rules_and_fingerprint_unchanged": any(row["gate"] == "candidate_fingerprint_unchanged" and row["passed"] for row in integrity_rows),
        "no_historical_backtest_rerun": True,
        "no_research_cache_refreshed_or_rewritten": cache_unchanged,
        "no_blended_portfolio_constructed": True,
        "vm_dsr_active_combo_unchanged": protected_unchanged,
        "dbc_primary_benchmark": config.get("primary_benchmark", PRIMARY_BENCHMARK) == "DBC",
        "no_broker_integration_or_order_placement": True,
        "no_real_money_flag_true": True,
        "no_existing_observation_capital_changes": True,
        "observation_initialization_does_not_alter_historical_evidence": historical_packets_unchanged,
        "decision_valid": decision in REVIEW_DECISIONS,
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(
        bool(value) for key, value in consistency.items() if key != "consistency_passed" and value is not None
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    write_text(
        OUTPUT_DIR / "review_summary.md",
        f"""# USCI Paper-Forward Eligibility Review v1

Decision: `{decision}`

Reason: `{reason}`

This packet performs a combined direction-owner promotion-review and paper-forward eligibility review for `{CANDIDATE_ID}` using only the already accepted USCI evidence packets. It does not run another USCI backtest or validation.

Historical labels remain unchanged:

- Original bounded screen: `methodology_regime_instability`
- Current-methodology validation: `historical_edge_recently_weakened`

The direction-owner override is recorded only in this review packet. Recent short-horizon weakness is retained as `current_short_horizon_relative_weakness`.

If approved, the activated observation is `{OBSERVATION_ID}`. It is observation-only, uses `DBC` as the primary benchmark, and has no broker integration, no orders, no automatic promotion, and no real-money recommendation.
""",
    )

    return {
        "candidate_id": CANDIDATE_ID,
        "observation_id": OBSERVATION_ID if decision == "approve_usci_paper_forward_observation" else "",
        "decision": decision,
        "evidence_dir": rel(OUTPUT_DIR),
        "historical_packets_byte_identical": historical_packets_unchanged,
        "consistency_passed": consistency["consistency_passed"],
        "next_action": "observe_usci_paper_forward_without_orders"
        if decision == "approve_usci_paper_forward_observation"
        else "resolve_usci_paper_forward_review_blocker",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
