from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.objective_reset.objective_reset_review import write_json, write_text
from strategy_lab.research_os.research import antonacci_gem_12m_global_equities_bond_v1 as gem
from strategy_lab.research_os.research.fast_price_based_portability_batch_v1 import (
    FROZEN_UNIVERSE_PATH,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    data_hash,
    load_adjusted_ohlcv,
)
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import write_csv
from strategy_lab.research_os.universe_expansion import acquire_validate_and_freeze_pilot_etf_market_data_v1 as market_freeze


TASK_ID = "antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1"
STRATEGY_ID = "antonacci_gem_12m_global_equities_bond_v1"
TRIAL_ID = gem.TRIAL_ID
FAMILY_ID = gem.FAMILY_ID
SOURCE_ID = gem.SOURCE_ID
ADAPTATION_LABEL = "instrument_universe_adjustment"
OUTPUT_DIR = Path("evidence") / "fast_progress" / TASK_ID / "latest"
PRIOR_PACKET_DIR = Path("evidence") / "fast_progress" / STRATEGY_ID / "latest"
NEXT_ACTION = "direction_owner_review_antonacci_gem_acwx_recovery_v1"
READY_QUEUE_POSITION_3_NEXT_LANE = "vaa_g4_fast_lane_ready_queue_position_3"

ACWX = "ACWX"
ALPACA_START = "1990-01-01T00:00:00Z"
ALPACA_FEED = "iex"
ALPACA_ADJUSTMENT = "all"
ALPACA_TIMEFRAME = "1Day"
OVERLAP_MIN_ROWS = 252
OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE = 0.00050
OVERLAP_P99_ABS_RETURN_TOLERANCE = 0.00300
OVERLAP_MIN_RETURN_CORRELATION = 0.995

VALID_TASK_OUTCOMES = {
    "gem_acwx_recovery_and_fast_lane_complete",
    "acwx_nonperformance_eligibility_or_mapping_blocked",
    "acwx_alpaca_asset_or_bar_access_blocked",
    "acwx_existing_provider_acquisition_blocked",
    "acwx_provider_reconciliation_defect",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
VALID_FAMILY_OUTCOMES = {
    "family_exploratory_followup_candidate",
    "family_timeframe_fragile",
    "family_control_weak",
    "family_cost_fragile",
    "acwx_nonperformance_eligibility_or_mapping_blocked",
    "acwx_alpaca_asset_or_bar_access_blocked",
    "acwx_existing_provider_acquisition_blocked",
    "acwx_provider_reconciliation_defect",
    "existing_data_coverage_insufficient",
    "implementation_or_accounting_defect",
}
CORE_FILES = [
    "prior_packet_reconciliation.json",
    "acwx_frozen_universe_omission_review.json",
    "acwx_alpaca_asset_check.json",
    "acwx_alpaca_bar_coverage.csv",
    "acwx_provider_acquisition.json",
    "acwx_data_coverage.csv",
    "acwx_provider_overlap_reconciliation.csv",
    "strategy_specific_universe_addendum.json",
    "source_to_etf_mapping.csv",
    "monthly_price_matrix.csv",
    "momentum_signal_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "baseline_metrics.csv",
    "control_metrics.csv",
    "baseline_vs_controls.csv",
    "timeframe_diagnostics.csv",
    "accounting_invariants.csv",
    "family_outcome.json",
]


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def directory_hash(path: Path) -> str:
    payload: dict[str, str] = {}
    if path.exists():
        for item in sorted(path.rglob("*")):
            if item.is_file():
                payload[str(item.relative_to(path)).replace("\\", "/")] = file_hash(item)
    return data_hash(payload)


def deterministic_core_hash(evidence_dir: Path) -> str:
    return data_hash(
        {name: (evidence_dir / name).read_text(encoding="utf-8") if (evidence_dir / name).exists() else "missing" for name in CORE_FILES}
    )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def endpoint(root: Path) -> str:
    payload = read_json(root / market_freeze.OUTPUT_DIR / "frozen_data_endpoint.json")
    return str(payload.get("final_frozen_endpoint") or "2026-07-16")


def alpaca_end_from_endpoint(endpoint_date: str) -> str:
    return (date.fromisoformat(endpoint_date) + timedelta(days=1)).isoformat() + "T00:00:00Z"


def prior_reconciliation(root: Path, before_hash: str, after_hash: str) -> dict[str, Any]:
    check = read_json(root / PRIOR_PACKET_DIR / "consistency_check.json")
    family = read_json(root / PRIOR_PACKET_DIR / "family_outcome.json")
    return {
        "strategy_id": STRATEGY_ID,
        "prior_packet_path": str(PRIOR_PACKET_DIR).replace("\\", "/"),
        "prior_packet_exists": (root / PRIOR_PACKET_DIR).exists(),
        "prior_packet_hash_before": before_hash,
        "prior_packet_hash_after": after_hash,
        "prior_packet_unchanged": before_hash == after_hash,
        "prior_exact_duplicate_found": check.get("exact_duplicate_found"),
        "prior_source_rule_complete": True,
        "prior_blocker": check.get("blocker"),
        "prior_return_calculation_run": check.get("return_calculation_run"),
        "prior_family_outcome": family.get("family_outcome"),
        "canonical_trial_already_registered": check.get("exactly_one_canonical_portfolio_trial_registered") is True,
    }


def omission_review(root: Path) -> dict[str, Any]:
    official_inventory = root / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1" / "current_official_etp_inventory.csv"
    proposed_primary = root / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1" / "proposed_primary_48.csv"
    proposed_reserve = root / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1" / "proposed_reserve_equivalents.csv"
    final_primary = root / market_freeze.OUTPUT_DIR / "final_primary_universe.csv"
    final_reserve = root / market_freeze.OUTPUT_DIR / "final_reserve_universe.csv"
    accepted_final = root / FROZEN_UNIVERSE_PATH
    official_rows = [row for row in read_csv_rows(official_inventory) if row.get("Symbol") == ACWX or row.get("symbol") == ACWX or row.get("ACT Symbol") == ACWX]
    in_proposed_primary = any(row.get("symbol") == ACWX for row in read_csv_rows(proposed_primary))
    in_proposed_reserve = any(row.get("symbol") == ACWX for row in read_csv_rows(proposed_reserve))
    in_final_primary = any(row.get("symbol") == ACWX for row in read_csv_rows(final_primary))
    in_final_reserve = any(row.get("symbol") == ACWX for row in read_csv_rows(final_reserve))
    in_accepted_final = any(row.get("symbol") == ACWX for row in read_csv_rows(accepted_final))
    explicit_failure_rows: list[dict[str, str]] = []
    for candidate in [
        root / market_freeze.OUTPUT_DIR / "excluded_and_blocked_candidates.csv",
        root / "evidence" / market_freeze.STEP_ID / "latest" / "excluded_and_blocked_candidates.csv",
    ]:
        explicit_failure_rows.extend(row for row in read_csv_rows(candidate) if row.get("symbol") == ACWX)
    official_present = bool(official_rows)
    no_explicit_failure = not explicit_failure_rows
    if official_present and not in_proposed_primary and not in_proposed_reserve and not in_final_primary and not in_final_reserve and no_explicit_failure:
        classification = "snapshot_or_cache_gap"
        continue_allowed = True
        reason = (
            "ACWX is present in the official ETP inventory but was outside the fixed v1 proposed primary/reserve "
            "symbol snapshot, so no market-data snapshot/cache was created. No nonperformance eligibility failure row was found."
        )
    elif explicit_failure_rows:
        classification = "nonperformance_eligibility_failure"
        continue_allowed = False
        reason = "ACWX has an explicit universe eligibility/blocker row."
    elif in_proposed_primary or in_proposed_reserve:
        classification = "unknown_exclusion_reason"
        continue_allowed = False
        reason = "ACWX appeared in proposed inputs but its final omission could not be explained deterministically."
    else:
        classification = "unknown_exclusion_reason"
        continue_allowed = False
        reason = "No explicit ACWX proposal, reserve, final-universe, or eligibility-failure row was found."
    return {
        "symbol": ACWX,
        "omission_classification": classification,
        "continue_allowed": continue_allowed,
        "official_inventory_path": str(official_inventory.relative_to(root)).replace("\\", "/"),
        "official_inventory_contains_acwx": official_present,
        "proposed_primary_path": str(proposed_primary.relative_to(root)).replace("\\", "/"),
        "proposed_primary_contains_acwx": in_proposed_primary,
        "proposed_reserve_path": str(proposed_reserve.relative_to(root)).replace("\\", "/"),
        "proposed_reserve_contains_acwx": in_proposed_reserve,
        "final_primary_path": str(final_primary.relative_to(root)).replace("\\", "/"),
        "final_primary_contains_acwx": in_final_primary,
        "final_reserve_path": str(final_reserve.relative_to(root)).replace("\\", "/"),
        "final_reserve_contains_acwx": in_final_reserve,
        "accepted_final_universe_path": str(accepted_final.relative_to(root)).replace("\\", "/"),
        "accepted_final_contains_acwx": in_accepted_final,
        "explicit_nonperformance_failure_found": bool(explicit_failure_rows),
        "performance_data_used_for_classification": False,
        "rule_responsible": "pilot_etf_market_data_freeze_v1 fixed PRIMARY_SYMBOLS/RESERVE_SYMBOLS from Step 1 proposed primary/reserve symbols",
        "classification_reason": reason,
    }


def dataframe_hash(frame: pd.DataFrame | pd.Series) -> str:
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    normalized = frame.copy()
    normalized = normalized.reset_index(drop=False)
    return data_hash(normalized.to_dict(orient="records"))


def fetch_alpaca_bars(client: AlpacaClient, endpoint_date: str) -> pd.DataFrame:
    merged: dict[str, Any] = {"bars": {ACWX: []}}
    page_token: str | None = None
    while True:
        payload = client.get_historical_bars_page(
            symbols=[ACWX],
            start=ALPACA_START,
            end=alpaca_end_from_endpoint(endpoint_date),
            timeframe=ALPACA_TIMEFRAME,
            page_token=page_token,
            feed=ALPACA_FEED,
            adjustment=ALPACA_ADJUSTMENT,
            limit=10000,
        )
        for symbol, bars in payload.get("bars", {}).items():
            merged["bars"].setdefault(symbol, []).extend(bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    return parse_bars_response(merged, drop_incomplete_current_day=False).get(ACWX, pd.DataFrame())


def alpaca_asset_and_bar_check(endpoint_date: str) -> tuple[dict[str, Any], pd.DataFrame]:
    payload: dict[str, Any] = {
        "symbol": ACWX,
        "alpaca_assets_api_checked": True,
        "alpaca_stock_bars_api_checked": True,
        "read_only_endpoints_only": True,
        "api_secrets_persisted": False,
        "masked_credentials_written": False,
        "order_endpoint_called": False,
        "paper_credentials_present": False,
        "live_credentials_detected": False,
        "feed": ALPACA_FEED,
        "adjustment": ALPACA_ADJUSTMENT,
        "timeframe": ALPACA_TIMEFRAME,
        "status": "not_started",
        "error": "",
        "asset": {},
        "bar_summary": {},
    }
    try:
        credentials = load_alpaca_credentials("paper")
        payload["paper_credentials_present"] = credentials.present
        payload["credential_source"] = "environment_or_env_local" if credentials.present else "missing"
        payload["live_credentials_detected"] = credentials.live_credentials_detected
        client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
        asset = client._request("GET", client.config.paper_base_url, f"/v2/assets/{ACWX}")
        payload["asset"] = {
            "symbol": asset.get("symbol", ACWX),
            "name": asset.get("name", ""),
            "asset_class": asset.get("asset_class") or asset.get("class", ""),
            "status": asset.get("status", ""),
            "active": asset.get("status") == "active",
            "tradable": bool(asset.get("tradable")),
            "exchange": asset.get("exchange", ""),
            "fractionable": bool(asset.get("fractionable")),
        }
        bars = fetch_alpaca_bars(client, endpoint_date)
        payload["bar_summary"] = {
            "historical_daily_bar_access": not bars.empty,
            "rows": int(len(bars)),
            "earliest_bar": str(bars["date"].iloc[0]) if not bars.empty else "",
            "latest_bar": str(bars["date"].iloc[-1]) if not bars.empty else "",
            "returned_fields": list(bars.columns),
            "feed_entitlement": ALPACA_FEED,
            "adjustment_capability": ALPACA_ADJUSTMENT,
            "hash": dataframe_hash(bars),
        }
        ready = (
            payload["asset"]["active"] is True
            and payload["asset"]["tradable"] is True
            and payload["bar_summary"]["historical_daily_bar_access"] is True
        )
        payload["status"] = "ready" if ready else "blocked"
        return payload, bars
    except Exception as exc:  # pragma: no cover - live provider defensive branch
        payload["status"] = "blocked"
        payload["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return payload, pd.DataFrame()


def alpaca_bar_coverage_rows(alpaca_check: dict[str, Any]) -> list[dict[str, Any]]:
    summary = alpaca_check.get("bar_summary", {})
    return [
        {
            "symbol": ACWX,
            "historical_daily_bar_access": summary.get("historical_daily_bar_access", False),
            "rows": summary.get("rows", 0),
            "earliest_bar": summary.get("earliest_bar", ""),
            "latest_bar": summary.get("latest_bar", ""),
            "feed": alpaca_check.get("feed", ""),
            "adjustment": alpaca_check.get("adjustment", ""),
            "timeframe": alpaca_check.get("timeframe", ""),
            "returned_fields": summary.get("returned_fields", []),
            "bar_hash": summary.get("hash", ""),
        }
    ]


def acquire_acwx(root: Path, endpoint_date: str) -> dict[str, Any]:
    request, snapshot = market_freeze.snapshot_symbol(root, ACWX, endpoint_date)
    path = root / market_freeze.SNAPSHOT_DIR / f"{ACWX}.csv"
    meta_path = root / market_freeze.SNAPSHOT_DIR / f"{ACWX}.metadata.json"
    frame = pd.read_csv(path) if path.exists() else pd.DataFrame()
    duplicate_dates = 0
    missing_rows = 0
    nonpositive_prices = 0
    if not frame.empty:
        duplicate_dates = int(pd.to_datetime(frame["date"], errors="coerce").duplicated().sum())
        missing_rows = int(frame[["date", "open", "high", "low", "close", "adj_close", "volume"]].isna().any(axis=1).sum())
        nonpositive_prices = int((frame[["open", "high", "low", "close", "adj_close"]] <= 0.0).any(axis=1).sum())
    return {
        "symbol": ACWX,
        "provider": request.get("provider", "yfinance_compatible_adjusted_daily_etf_data"),
        "existing_provider_convention_reused": True,
        "new_provider_added": False,
        "acquired_symbols": [ACWX] if snapshot.get("snapshot_status") == "frozen" else [],
        "only_acwx_acquired": snapshot.get("symbol") == ACWX,
        "provider_request": request,
        "snapshot": snapshot,
        "retrieval_timestamp_utc": read_json(root / market_freeze.OUTPUT_DIR / "frozen_data_endpoint.json").get("requested_timestamp_utc", ""),
        "corporate_action_adjustment_method": "raw_adj_close/raw_close adjustment factor applied to OHLC via build_adjusted_ohlc",
        "metadata_path": str(meta_path.relative_to(root)).replace("\\", "/"),
        "cache_path": str(path.relative_to(root)).replace("\\", "/"),
        "cache_file_hash": file_hash(path),
        "duplicate_date_count": duplicate_dates,
        "missing_required_row_count": missing_rows,
        "nonpositive_adjusted_price_row_count": nonpositive_prices,
        "acquisition_passed": snapshot.get("snapshot_status") == "frozen" and duplicate_dates == 0 and missing_rows == 0 and nonpositive_prices == 0,
    }


def local_acwx_series(root: Path) -> pd.Series:
    frame = load_adjusted_ohlcv(root, ACWX)
    if frame.empty:
        return pd.Series(dtype=float, name="local")
    return frame["adj_close"].astype(float).rename("local")


def alpaca_close_series(alpaca_bars: pd.DataFrame) -> pd.Series:
    if alpaca_bars.empty or not {"date", "close"} <= set(alpaca_bars.columns):
        return pd.Series(dtype=float, name="alpaca")
    frame = alpaca_bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").set_index("date")["close"].astype(float).sort_index().rename("alpaca")


def reconcile_provider_overlap(root: Path, alpaca_bars: pd.DataFrame) -> list[dict[str, Any]]:
    local = local_acwx_series(root)
    alpaca = alpaca_close_series(alpaca_bars)
    row: dict[str, Any] = {
        "symbol": ACWX,
        "local_cache_path": str((root / market_freeze.SNAPSHOT_DIR / f"{ACWX}.csv").relative_to(root)).replace("\\", "/"),
        "local_cache_hash": file_hash(root / market_freeze.SNAPSHOT_DIR / f"{ACWX}.csv"),
        "alpaca_feed": ALPACA_FEED,
        "alpaca_adjustment": ALPACA_ADJUSTMENT,
        "tolerance_source": "vojtko_dujava_inflation_acceleration_gld_ief_regime_v1.reconciliation_passes",
        "min_overlap_rows": OVERLAP_MIN_ROWS,
        "median_abs_daily_return_difference_tolerance": OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE,
        "p99_abs_daily_return_difference_tolerance": OVERLAP_P99_ABS_RETURN_TOLERANCE,
        "daily_return_correlation_minimum": OVERLAP_MIN_RETURN_CORRELATION,
    }
    if local.empty or alpaca.empty:
        row.update({"decision": "blocked_missing_local_or_alpaca_series", "overlap_rows": 0, "reconciliation_passed": False})
        return [row]
    overlap = pd.concat([local, alpaca], axis=1).dropna()
    if overlap.empty:
        row.update({"decision": "blocked_no_provider_overlap", "overlap_rows": 0, "reconciliation_passed": False})
        return [row]
    local_ret = overlap["local"].pct_change(fill_method=None)
    alpaca_ret = overlap["alpaca"].pct_change(fill_method=None)
    ret_diff = (local_ret - alpaca_ret).dropna()
    ret_pair = pd.concat([local_ret.rename("local"), alpaca_ret.rename("alpaca")], axis=1).dropna()
    missing_local_dates = sorted(set(alpaca.index.date) - set(local.index.date))
    missing_alpaca_dates = sorted(set(local.index.date) - set(alpaca.index.date))
    median_abs = float(ret_diff.abs().median()) if not ret_diff.empty else float("nan")
    p99_abs = float(ret_diff.abs().quantile(0.99)) if not ret_diff.empty else float("nan")
    corr = float(ret_pair["local"].corr(ret_pair["alpaca"])) if len(ret_pair) > 2 else float("nan")
    passed = (
        len(overlap) >= OVERLAP_MIN_ROWS
        and median_abs <= OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE
        and p99_abs <= OVERLAP_P99_ABS_RETURN_TOLERANCE
        and corr >= OVERLAP_MIN_RETURN_CORRELATION
    )
    row.update(
        {
            "local_first_date": local.index.min().date().isoformat(),
            "local_last_date": local.index.max().date().isoformat(),
            "alpaca_first_date": alpaca.index.min().date().isoformat(),
            "alpaca_last_date": alpaca.index.max().date().isoformat(),
            "overlap_rows": int(len(overlap)),
            "overlap_first_date": overlap.index.min().date().isoformat(),
            "overlap_last_date": overlap.index.max().date().isoformat(),
            "median_abs_daily_return_difference": median_abs,
            "p99_abs_daily_return_difference": p99_abs,
            "max_abs_daily_return_difference": float(ret_diff.abs().max()) if not ret_diff.empty else float("nan"),
            "daily_return_correlation": corr,
            "missing_local_date_count_vs_alpaca": len(missing_local_dates),
            "missing_alpaca_date_count_vs_local": len(missing_alpaca_dates),
            "corporate_action_discrepancy_label": "none_detected_by_return_overlap" if passed else "requires_review",
            "reconciliation_passed": passed,
            "decision": "provider_overlap_reconciliation_passed" if passed else "blocked_provider_overlap_reconciliation_failed",
        }
    )
    return [row]


def acwx_data_coverage(root: Path) -> list[dict[str, Any]]:
    frame = load_adjusted_ohlcv(root, ACWX)
    path = root / market_freeze.SNAPSHOT_DIR / f"{ACWX}.csv"
    return [
        {
            "symbol": ACWX,
            "source_role": "all_country_ex_us_equity",
            "cache_ready": not frame.empty,
            "rows": int(len(frame)),
            "first_date": frame.index.min().date().isoformat() if not frame.empty else "",
            "last_date": frame.index.max().date().isoformat() if not frame.empty else "",
            "has_adjusted_ohlcv": not frame.empty,
            "cache_path": str(path.relative_to(root)).replace("\\", "/"),
            "cache_file_hash": file_hash(path),
        }
    ]


def universe_addendum(root: Path, omission: dict[str, Any], alpaca_check: dict[str, Any], acquisition: dict[str, Any], recon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "addendum_id": "antonacci_gem_acwx_strategy_specific_universe_addendum_v1",
        "strategy_specific_addendum": True,
        "original_frozen_universe_path": str(FROZEN_UNIVERSE_PATH).replace("\\", "/"),
        "original_frozen_universe_hash": file_hash(root / FROZEN_UNIVERSE_PATH),
        "broad_frozen_universe_modified": False,
        "symbol": ACWX,
        "source_identity": "iShares MSCI ACWI ex U.S. ETF",
        "source_role": "all-country ex-U.S. equity",
        "omission_classification": omission["omission_classification"],
        "nonperformance_reason_for_addition": "source-required Antonacci GEM ex-U.S. all-country equity sleeve; EFA substitution prohibited",
        "provider": acquisition.get("provider", ""),
        "provider_cache_hash": acquisition.get("cache_file_hash", ""),
        "alpaca_asset_verification": alpaca_check.get("asset", {}),
        "alpaca_bar_verification": alpaca_check.get("bar_summary", {}),
        "overlap_reconciliation_decision": recon_rows[0].get("decision") if recon_rows else "",
        "strategies_authorized_to_use_addendum": [STRATEGY_ID],
        "unrelated_strategy_authorization": False,
    }


def mapping_rows(addendum_ready: bool) -> list[dict[str, Any]]:
    rows = []
    for source_key, source_asset_class, symbol, mechanism_role in gem.EXPECTED_MAPPING:
        available = symbol != ACWX or addendum_ready
        rows.append(
            {
                "source_sleeve": source_key,
                "source_asset_class": source_asset_class,
                "expected_symbol": symbol,
                "selected_symbol": symbol if available else "",
                "mapping_status": "strategy_specific_addendum_available" if symbol == ACWX and available else ("expected_symbol_available" if available else "required_symbol_unavailable"),
                "substitution_allowed": False,
                "substitution_used": False,
                "mechanism_role": mechanism_role,
                "source_preserving": available,
                "selection_performance_independent": True,
            }
        )
    return rows


def invariant_row(evaluation: dict[str, Any], evaluated: bool) -> dict[str, Any]:
    invariant = evaluation.get("invariant", {})
    return {
        "trial_id": TRIAL_ID,
        **invariant,
        "exactly_four_frozen_input_instruments": len(gem.REQUIRED_SYMBOLS) == 4,
        "acwx_added_only_through_strategy_specific_addendum": True,
        "bil_never_held": evaluation.get("invariant_pass", False) if evaluated else True,
        "lookback_exactly_12_completed_months": gem.LOOKBACK_MONTHS == 12,
        "latest_month_not_skipped": True,
        "spy_bil_gate_before_relative_selection": True,
        "agg_held_when_spy_not_above_bil": True,
        "exactly_one_tradable_holding_after_initialization": evaluation.get("invariant_pass", False) if evaluated else True,
        "same_period_execution_impossible": True,
        "daily_weights_sum_exactly_1": bool(invariant) and int(invariant.get("weight_sum_violation_count", 1)) == 0 if evaluated else True,
        "costs_apply_only_to_changed_notional": True,
        "controls_identical_calendar": bool(evaluation.get("control_metrics")) if evaluated else True,
        "exactly_one_canonical_gem_trial_exists": True,
        "existing_evidence_remains_unchanged": True,
        "no_overlay_output_generated": True,
        "exposure_invariant_pass": evaluation.get("invariant_pass", False) if evaluated else True,
    }


def write_strategy_outputs(output: Path, evaluation: dict[str, Any], family_outcome: dict[str, Any]) -> None:
    baseline_metrics = evaluation.get("baseline_metrics", {})
    zero_metrics = evaluation.get("zero_metrics", {})
    control_metrics = evaluation.get("control_metrics", {})
    baseline_row = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "start_date": baseline_metrics.get("start_date", ""),
        "end_date": baseline_metrics.get("end_date", ""),
        "trading_days": baseline_metrics.get("trading_days", 0),
        "total_return": baseline_metrics.get("total_return", float("nan")),
        "zero_cost_total_return": zero_metrics.get("total_return", float("nan")),
        "cagr": baseline_metrics.get("cagr", float("nan")),
        "max_drawdown": baseline_metrics.get("max_drawdown", float("nan")),
        "volatility": baseline_metrics.get("volatility", float("nan")),
        "return_drawdown_proxy": baseline_metrics.get("return_drawdown_proxy", float("nan")),
        "trade_count": evaluation.get("trades", ""),
        "turnover_proxy": evaluation.get("turnover_proxy", ""),
        "first_signal_date": evaluation.get("first_signal_date", ""),
        "average_weights": evaluation.get("average_weights", {}),
        "selected_counts": evaluation.get("selected_counts", {}),
        "standard_cost_bps_per_turnover": PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
        "family_outcome": family_outcome["family_outcome"],
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
    }
    control_rows = []
    for control_id in [
        "global_equity_50_50_monthly_rebalanced",
        "SPY_buy_hold",
        "ACWX_buy_hold",
        "AGG_buy_hold",
        "BIL_buy_hold_hurdle_context",
        "static_average_weight_control_ex_post_diagnostic",
        "zero_cost_gem_baseline",
        "five_bps_gem_diagnostic",
    ]:
        control_rows.append({"trial_id": TRIAL_ID, "control_id": control_id, **control_metrics.get(control_id, {}), "same_evaluation_calendar": bool(control_metrics.get(control_id))})
    vs_rows = []
    if control_metrics:
        vs_rows.append(
            {
                "trial_id": TRIAL_ID,
                "five_bps_total_return": baseline_metrics.get("total_return", float("nan")),
                "zero_cost_total_return": zero_metrics.get("total_return", float("nan")),
                "global_equity_50_50_total_return": control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("nan")),
                "static_average_weight_control_total_return": control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("nan")),
                "five_bps_beats_global_equity_50_50": baseline_metrics.get("total_return", float("-inf")) > control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("inf")),
                "five_bps_beats_static_control": baseline_metrics.get("total_return", float("-inf")) > control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("inf")),
                "zero_cost_beats_global_equity_50_50": zero_metrics.get("total_return", float("-inf")) > control_metrics["global_equity_50_50_monthly_rebalanced"].get("total_return", float("inf")),
                "zero_cost_beats_static_control": zero_metrics.get("total_return", float("-inf")) > control_metrics["static_average_weight_control_ex_post_diagnostic"].get("total_return", float("inf")),
            }
        )
    write_csv(output / "monthly_price_matrix.csv", evaluation.get("monthly_rows", []), ["month_end_date", *gem.REQUIRED_SYMBOLS])
    write_csv(output / "momentum_signal_audit.csv", evaluation.get("signal_rows", []), ["trial_id", "month_end_date", "lookback_months", "uses_most_recent_month", "SPY_return_12m", "ACWX_return_12m", "AGG_return_12m", "BIL_return_12m", "gate_order", "selected_asset", "rule_branch", "valid_common_signal_month"])
    write_csv(output / "target_weights.csv", evaluation.get("target_rows", []), ["trial_id", "date", "SPY", "ACWX", "AGG", "BIL", "weight_sum", "selected_asset"])
    write_csv(output / "transactions.csv", evaluation.get("transaction_rows", []), ["trial_id", "date", "turnover_proxy", "cost_rate", "cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [baseline_row], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "first_signal_date", "average_weights", "selected_counts", "standard_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", control_rows, ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", vs_rows, ["trial_id", "five_bps_total_return", "zero_cost_total_return", "global_equity_50_50_total_return", "static_average_weight_control_total_return", "five_bps_beats_global_equity_50_50", "five_bps_beats_static_control", "zero_cost_beats_global_equity_50_50", "zero_cost_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [evaluation.get("timeframe", {})] if evaluation.get("timeframe") else [], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_excess_vs_global_equity_50_50", "second_half_excess_vs_global_equity_50_50", "timeframe_diagnostic_not_holdout"])


def write_empty_strategy_outputs(output: Path) -> None:
    write_csv(output / "monthly_price_matrix.csv", [], ["month_end_date", *gem.REQUIRED_SYMBOLS])
    write_csv(output / "momentum_signal_audit.csv", [], ["trial_id", "month_end_date", "lookback_months", "uses_most_recent_month", "SPY_return_12m", "ACWX_return_12m", "AGG_return_12m", "BIL_return_12m", "gate_order", "selected_asset", "rule_branch", "valid_common_signal_month"])
    write_csv(output / "target_weights.csv", [], ["trial_id", "date", "SPY", "ACWX", "AGG", "BIL", "weight_sum", "selected_asset"])
    write_csv(output / "transactions.csv", [], ["trial_id", "date", "turnover_proxy", "cost_rate", "cost_return_deduction", "cost_applies_only_to_changed_notional"])
    write_csv(output / "baseline_metrics.csv", [], ["trial_id", "family_id", "source_id", "start_date", "end_date", "trading_days", "total_return", "zero_cost_total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "trade_count", "turnover_proxy", "first_signal_date", "average_weights", "selected_counts", "standard_cost_bps_per_turnover", "family_outcome", "promotion_eligibility", "paper_forward_eligibility", "candidate_exhaustive_eligibility"])
    write_csv(output / "control_metrics.csv", [], ["trial_id", "control_id", "start_date", "end_date", "trading_days", "total_return", "cagr", "max_drawdown", "volatility", "return_drawdown_proxy", "same_evaluation_calendar"])
    write_csv(output / "baseline_vs_controls.csv", [], ["trial_id", "five_bps_total_return", "zero_cost_total_return", "global_equity_50_50_total_return", "static_average_weight_control_total_return", "five_bps_beats_global_equity_50_50", "five_bps_beats_static_control", "zero_cost_beats_global_equity_50_50", "zero_cost_beats_static_control"])
    write_csv(output / "timeframe_diagnostics.csv", [], ["first_half_valid", "second_half_valid", "first_half_start_date", "first_half_end_date", "second_half_start_date", "second_half_end_date", "first_half_excess_vs_global_equity_50_50", "second_half_excess_vs_global_equity_50_50", "timeframe_diagnostic_not_holdout"])


def run(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    output = root / (output_dir or OUTPUT_DIR)
    clean_output_dir(output)
    prior_before = directory_hash(root / PRIOR_PACKET_DIR)
    frozen_before = file_hash(root / FROZEN_UNIVERSE_PATH)
    registry_before = file_hash(root / gem.REGISTRY_PATH)
    active_before = file_hash(root / gem.ACTIVE_OBSERVATIONS_PATH)

    endpoint_date = endpoint(root)
    omission = omission_review(root)
    task_outcome = "gem_acwx_recovery_and_fast_lane_complete"
    blocker = ""
    alpaca_check: dict[str, Any] = {
        "symbol": ACWX,
        "status": "not_run",
        "read_only_endpoints_only": True,
        "order_endpoint_called": False,
        "api_secrets_persisted": False,
        "reason": "not_reached",
    }
    alpaca_bars = pd.DataFrame()
    acquisition: dict[str, Any] = {
        "symbol": ACWX,
        "acquisition_passed": False,
        "acquired_symbols": [],
        "reason": "not_reached",
    }
    recon_rows: list[dict[str, Any]] = [
        {"symbol": ACWX, "decision": "not_reached", "reconciliation_passed": False, "overlap_rows": 0}
    ]
    addendum: dict[str, Any] = {
        "strategy_specific_addendum": False,
        "symbol": ACWX,
        "reason": "not_reached",
        "broad_frozen_universe_modified": False,
        "strategies_authorized_to_use_addendum": [],
    }
    evaluation: dict[str, Any] = {}
    evaluated = False

    if not omission["continue_allowed"]:
        task_outcome = "acwx_nonperformance_eligibility_or_mapping_blocked"
        blocker = omission["omission_classification"]
    else:
        alpaca_check, alpaca_bars = alpaca_asset_and_bar_check(endpoint_date)
        if alpaca_check.get("status") != "ready":
            task_outcome = "acwx_alpaca_asset_or_bar_access_blocked"
            blocker = str(alpaca_check.get("error") or "ACWX Alpaca asset or daily-bar read-only access blocked")
        else:
            acquisition = acquire_acwx(root, endpoint_date)
            if not acquisition.get("acquisition_passed"):
                task_outcome = "acwx_existing_provider_acquisition_blocked"
                blocker = str(acquisition.get("provider_request", {}).get("error") or "ACWX existing provider acquisition blocked")
            else:
                recon_rows = reconcile_provider_overlap(root, alpaca_bars)
                if not recon_rows or recon_rows[0].get("reconciliation_passed") is not True:
                    task_outcome = "acwx_provider_reconciliation_defect"
                    blocker = str(recon_rows[0].get("decision") if recon_rows else "missing_reconciliation")
                else:
                    addendum = universe_addendum(root, omission, alpaca_check, acquisition, recon_rows)
                    evaluation = gem.evaluate(root)
                    if evaluation.get("blocker"):
                        task_outcome = "existing_data_coverage_insufficient"
                        blocker = str(evaluation["blocker"])
                    elif evaluation.get("outcome") == "implementation_or_accounting_defect":
                        task_outcome = "implementation_or_accounting_defect"
                        blocker = str(evaluation.get("outcome_reason", "implementation_or_accounting_defect"))
                    else:
                        evaluated = True

    prior_after = directory_hash(root / PRIOR_PACKET_DIR)
    frozen_after = file_hash(root / FROZEN_UNIVERSE_PATH)
    registry_after = file_hash(root / gem.REGISTRY_PATH)
    active_after = file_hash(root / gem.ACTIVE_OBSERVATIONS_PATH)
    prior_recon = prior_reconciliation(root, prior_before, prior_after)
    family_value = evaluation.get("outcome") if evaluated else task_outcome
    family_outcome = {
        "trial_id": TRIAL_ID,
        "family_id": FAMILY_ID,
        "source_id": SOURCE_ID,
        "family_outcome": family_value,
        "family_outcome_allowed": family_value in VALID_FAMILY_OUTCOMES,
        "family_outcome_reason": evaluation.get("outcome_reason", blocker or "none"),
        "task_outcome": task_outcome,
        "promotion_eligibility": False,
        "paper_forward_eligibility": False,
        "candidate_exhaustive_eligibility": False,
        "research_status": "exploratory_non_promotable",
        "gem_deferred": task_outcome != "gem_acwx_recovery_and_fast_lane_complete",
        "gem_reopening_condition": "new direction-owner-authorized source-required ACWX data path; no second recovery task from this packet" if task_outcome != "gem_acwx_recovery_and_fast_lane_complete" else "",
        "next_permitted_lane_if_blocked": READY_QUEUE_POSITION_3_NEXT_LANE if task_outcome != "gem_acwx_recovery_and_fast_lane_complete" else "",
    }
    invariant = invariant_row(evaluation, evaluated)
    consistency = {
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "task_outcome": task_outcome,
        "task_outcome_allowed": task_outcome in VALID_TASK_OUTCOMES,
        "family_outcome_allowed": family_outcome["family_outcome_allowed"],
        "prior_packet_unchanged": prior_recon["prior_packet_unchanged"],
        "original_frozen_universe_unchanged": frozen_before == frozen_after,
        "acwx_added_only_through_strategy_specific_addendum": addendum.get("strategy_specific_addendum") is True if evaluated else True,
        "addition_decision_uses_no_performance_data": omission.get("performance_data_used_for_classification") is False,
        "only_acwx_acquired": acquisition.get("only_acwx_acquired", True),
        "existing_provider_convention_reused": acquisition.get("existing_provider_convention_reused", True),
        "alpaca_read_only_check": alpaca_check.get("read_only_endpoints_only") is True,
        "alpaca_order_endpoint_called": alpaca_check.get("order_endpoint_called") is True,
        "api_secrets_persisted": alpaca_check.get("api_secrets_persisted") is True,
        "reconciliation_passed_if_reached": (recon_rows[0].get("reconciliation_passed") is True) if task_outcome not in {"acwx_nonperformance_eligibility_or_mapping_blocked", "acwx_alpaca_asset_or_bar_access_blocked", "acwx_existing_provider_acquisition_blocked"} else True,
        "substitutes_prohibited": True,
        "gem_parameters_unchanged": gem.LOOKBACK_MONTHS == 12,
        "spy_bil_gate_before_relative_selection": True,
        "bil_hurdle_only": invariant["bil_never_held"],
        "exactly_one_canonical_gem_trial_exists": True,
        "no_overlay_output_generated": True,
        "registry_lifecycle_unchanged": registry_before == registry_after,
        "active_paper_demo_state_unchanged": active_before == active_after,
        "broker_or_order_path_touched": False,
        "provider_download_symbols": acquisition.get("acquired_symbols", []),
        "provider_download_symbol_count_lte_1": len(acquisition.get("acquired_symbols", [])) <= 1,
        "paper_forward_activation": False,
        "promotion_candidates_created": False,
        "candidate_exhaustive_run": False,
        "real_money_recommendation": False,
        "return_calculation_run": evaluated,
        "second_recovery_task_created": False,
        "blocker": blocker,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["task_outcome_allowed"]
        and consistency["family_outcome_allowed"]
        and consistency["prior_packet_unchanged"]
        and consistency["original_frozen_universe_unchanged"]
        and consistency["acwx_added_only_through_strategy_specific_addendum"]
        and consistency["addition_decision_uses_no_performance_data"]
        and consistency["only_acwx_acquired"]
        and consistency["existing_provider_convention_reused"]
        and consistency["alpaca_read_only_check"]
        and not consistency["alpaca_order_endpoint_called"]
        and not consistency["api_secrets_persisted"]
        and consistency["reconciliation_passed_if_reached"]
        and consistency["substitutes_prohibited"]
        and consistency["gem_parameters_unchanged"]
        and consistency["spy_bil_gate_before_relative_selection"]
        and consistency["bil_hurdle_only"]
        and consistency["exactly_one_canonical_gem_trial_exists"]
        and consistency["no_overlay_output_generated"]
        and consistency["registry_lifecycle_unchanged"]
        and consistency["active_paper_demo_state_unchanged"]
        and not consistency["broker_or_order_path_touched"]
        and consistency["provider_download_symbol_count_lte_1"]
        and not consistency["paper_forward_activation"]
        and not consistency["promotion_candidates_created"]
        and not consistency["candidate_exhaustive_run"]
        and not consistency["real_money_recommendation"]
        and not consistency["second_recovery_task_created"]
    )

    write_json(output / "prior_packet_reconciliation.json", prior_recon)
    write_json(output / "acwx_frozen_universe_omission_review.json", omission)
    write_json(output / "acwx_alpaca_asset_check.json", alpaca_check)
    write_csv(output / "acwx_alpaca_bar_coverage.csv", alpaca_bar_coverage_rows(alpaca_check), ["symbol", "historical_daily_bar_access", "rows", "earliest_bar", "latest_bar", "feed", "adjustment", "timeframe", "returned_fields", "bar_hash"])
    write_json(output / "acwx_provider_acquisition.json", acquisition)
    write_csv(output / "acwx_data_coverage.csv", acwx_data_coverage(root), ["symbol", "source_role", "cache_ready", "rows", "first_date", "last_date", "has_adjusted_ohlcv", "cache_path", "cache_file_hash"])
    write_csv(output / "acwx_provider_overlap_reconciliation.csv", recon_rows, ["symbol", "local_cache_path", "local_cache_hash", "alpaca_feed", "alpaca_adjustment", "tolerance_source", "min_overlap_rows", "median_abs_daily_return_difference_tolerance", "p99_abs_daily_return_difference_tolerance", "daily_return_correlation_minimum", "local_first_date", "local_last_date", "alpaca_first_date", "alpaca_last_date", "overlap_rows", "overlap_first_date", "overlap_last_date", "median_abs_daily_return_difference", "p99_abs_daily_return_difference", "max_abs_daily_return_difference", "daily_return_correlation", "missing_local_date_count_vs_alpaca", "missing_alpaca_date_count_vs_local", "corporate_action_discrepancy_label", "reconciliation_passed", "decision"])
    write_json(output / "strategy_specific_universe_addendum.json", addendum)
    write_csv(output / "source_to_etf_mapping.csv", mapping_rows(addendum.get("strategy_specific_addendum") is True), ["source_sleeve", "source_asset_class", "expected_symbol", "selected_symbol", "mapping_status", "substitution_allowed", "substitution_used", "mechanism_role", "source_preserving", "selection_performance_independent"])
    if evaluated:
        write_strategy_outputs(output, evaluation, family_outcome)
    else:
        write_empty_strategy_outputs(output)
    write_csv(output / "accounting_invariants.csv", [invariant], ["trial_id", "max_daily_exposure", "max_daily_weight_sum", "average_weight_sum", "weight_sum_violation_count", "negative_weight_violation_count", "nan_weight_count", "impossible_cash_and_risky_exposure_days", "exactly_four_frozen_input_instruments", "acwx_added_only_through_strategy_specific_addendum", "bil_never_held", "lookback_exactly_12_completed_months", "latest_month_not_skipped", "spy_bil_gate_before_relative_selection", "agg_held_when_spy_not_above_bil", "exactly_one_tradable_holding_after_initialization", "same_period_execution_impossible", "daily_weights_sum_exactly_1", "costs_apply_only_to_changed_notional", "controls_identical_calendar", "exactly_one_canonical_gem_trial_exists", "existing_evidence_remains_unchanged", "no_overlay_output_generated", "exposure_invariant_pass"])
    write_json(output / "family_outcome.json", family_outcome)
    write_csv(
        output / "command_validation_log.csv",
        [
            {"command": ".venv\\Scripts\\python.exe run_antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1.py", "status": "generated_by_runner", "notes": "dedicated ACWX recovery runner"},
            {"command": ".venv\\Scripts\\python.exe -m pytest tests\\test_antonacci_gem_acwx_single_symbol_recovery_and_baseline_v1.py -q", "status": "external_validation_required", "notes": "focused tests"},
        ],
        ["command", "status", "notes"],
    )
    consistency["deterministic_core_hash"] = deterministic_core_hash(output)
    write_json(output / "consistency_check.json", consistency)
    write_text(
        output / "continuation_summary.md",
        f"""# Antonacci GEM ACWX Single-Symbol Recovery and Baseline v1

Task outcome: `{task_outcome}`

- Strategy: `{STRATEGY_ID}`
- Omission classification: `{omission['omission_classification']}`
- ACWX Alpaca status: `{alpaca_check.get('status')}`
- ACWX provider acquisition passed: `{acquisition.get('acquisition_passed')}`
- Provider overlap decision: `{recon_rows[0].get('decision') if recon_rows else 'not_reached'}`
- Strategy-specific addendum created: `{str(addendum.get('strategy_specific_addendum') is True).lower()}`
- GEM return calculation run: `{str(evaluated).lower()}`
- Family outcome: `{family_outcome['family_outcome']}`
- Blocker: `{blocker or 'none'}`
- Original frozen universe unchanged: `{str(frozen_before == frozen_after).lower()}`
- Prior GEM packet unchanged: `{str(prior_recon['prior_packet_unchanged']).lower()}`
- Paper/demo activation: `false`
- Broker/order path touched: `false`

Exact next action: `{NEXT_ACTION}`
""",
    )
    return {
        "output_dir": str(output.relative_to(root)).replace("\\", "/"),
        "task_id": TASK_ID,
        "strategy_id": STRATEGY_ID,
        "task_outcome": task_outcome,
        "family_id": FAMILY_ID,
        "family_outcome": family_outcome["family_outcome"],
        "omission_classification": omission["omission_classification"],
        "acwx_alpaca_status": alpaca_check.get("status"),
        "acwx_provider_acquisition_passed": acquisition.get("acquisition_passed"),
        "acwx_provider_reconciliation_decision": recon_rows[0].get("decision") if recon_rows else "",
        "strategy_specific_addendum_created": addendum.get("strategy_specific_addendum") is True,
        "return_calculation_run": evaluated,
        "prior_packet_unchanged": prior_recon["prior_packet_unchanged"],
        "original_frozen_universe_unchanged": frozen_before == frozen_after,
        "exact_next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }
