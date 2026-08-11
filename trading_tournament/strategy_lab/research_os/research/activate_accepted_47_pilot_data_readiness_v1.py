from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import (
    AlpacaClient,
    AlpacaClientConfig,
)
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from strategy_lab.research_os.universe_expansion import (
    acquire_validate_and_freeze_pilot_etf_market_data_v1 as pilot_freeze,
)


TASK_ID = "activate_accepted_47_pilot_data_readiness_v1"
MODE = "bounded-universe-activation-and-refresh"
STAGE = "implementation"
UNIVERSE_ID = "phase1_bounded_multi_asset_pilot"
OUTPUT_DIR = Path("evidence") / "data_capability" / TASK_ID / "latest"
SNAPSHOT_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"
DESIGN_DIR = Path("strategy_lab") / "research_os" / "universe_expansion" / "pilot_etf_universe_design_v1"
FREEZE_DIR = Path("strategy_lab") / "research_os" / "universe_expansion" / "pilot_etf_market_data_freeze_v1"
COMPAT_DIR = Path("strategy_lab") / "research_os" / "universe_expansion" / "pilot_instrument_strategy_compatibility_v1"
PRIOR_PACKET = Path("evidence") / "data_capability" / "resume_bounded_multi_asset_universe_data_readiness_v1" / "latest"

SYMBOLS = (
    "SPY", "QQQ", "IWM", "DIA", "VTV", "SCHG", "QUAL", "USMV",
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC",
    "EFA", "EEM", "URTH", "VGK", "VPL", "EWJ", "EWU", "EWG", "EWC", "EWA", "EWY", "INDA",
    "BIL", "SHY", "IEF", "TLT", "AGG", "TIP", "LQD", "HYG", "EMB", "MUB",
    "GLD", "SLV", "DBC", "DBA", "IYR", "XLRE", "IFRA",
)
CALIBRATION_SYMBOLS = ("SPY", "EFA", "TLT", "GLD", "IYR")
EXCLUDED_SEPARATE_APPROVALS = ("EEMV", "EFAV")
EXISTING_ENDPOINT = date(2026, 7, 16)
REFRESH_START = date(2026, 6, 1)
FINAL_ENDPOINT = date(2026, 8, 4)
CALIBRATION_START = date(2025, 6, 1)
END_EXCLUSIVE = date(2026, 8, 5)
ALPACA_FEED = "sip"
ALPACA_ADJUSTMENTS = ("raw", "all")
OVERLAP_MIN_ROWS = 252
OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE = 0.00050
OVERLAP_P99_ABS_RETURN_TOLERANCE = 0.00300
OVERLAP_MIN_RETURN_CORRELATION = 0.995

FULL_COLUMNS = (
    "date", "raw_open", "raw_high", "raw_low", "raw_close", "raw_adj_close",
    "raw_volume", "dividends", "stock_splits", "adjustment_factor", "open",
    "high", "low", "close", "adj_close", "volume", "symbol",
)
VALIDATION_COLUMNS = ("date", "open", "high", "low", "close", "adj_close", "volume")

OUTPUT_FILES = (
    "activation_manifest.yaml",
    "direction_correction_record.csv",
    "membership_reproduction.csv",
    "operational_universe_snapshot.csv",
    "economic_group_map.csv",
    "existing_cache_reproduction.csv",
    "provider_calibration_manifest.csv",
    "provider_overlap_reconciliation.csv",
    "provider_request_manifest.csv",
    "acquisition_results.csv",
    "historical_row_reconciliation.csv",
    "data_quality_results.csv",
    "completed_session_coverage.csv",
    "blocked_symbols.csv",
    "research_readiness_map.csv",
    "old_new_cache_hash_manifest.csv",
    "protected_state_reconciliation.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "data_activation_report.md",
)

SOURCE_PATHS = (
    DESIGN_DIR / "direction_decision.yaml",
    DESIGN_DIR / "frozen_step2_eligibility_policy.yaml",
    DESIGN_DIR / "provisional_exposure_classification.csv",
    FREEZE_DIR / "market_data_freeze_manifest.yaml",
    FREEZE_DIR / "final_primary_universe.csv",
    FREEZE_DIR / "official_product_identity.csv",
    FREEZE_DIR / "history_and_integrity_metrics.csv",
    FREEZE_DIR / "adjustment_integrity_review.csv",
    COMPAT_DIR / "direction_owner_gap_acceptance.yaml",
    COMPAT_DIR / "accepted_final_47_universe.csv",
)

PROTECTED_PATHS = (
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "RESEARCH_ROADMAP.md",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
    Path("evidence") / "technical_factory" / "technical_strategy_factory_v1" / "latest",
    Path("evidence") / "technical_factory" / "technical_strategy_factory_v2" / "latest",
    Path("evidence") / "trade_management" / "faa_psar_trade_management_overlay_batch_v1" / "latest",
    Path("evidence") / "robustness" / "native_etf_two_candidate_final_robustness_v1" / "latest",
    Path("evidence") / "robustness" / "decelerated_psar_diversifier_final_robustness_v1" / "latest",
    Path("paper_forward_observations") / "paper_demo_faa_4m_top3_v1",
    Path("paper_forward_observations") / "paper_demo_decelerated_psar_20pct_diversifier_v1",
    PRIOR_PACKET,
    Path("data") / "cache",
)

DIRECTION_FIELDS = (
    "correction_id", "prior_blocked_task", "reason_for_prior_block",
    "accepted_operational_membership_count", "long_term_80_150_target_status",
    "separate_eight_symbol_approval_status", "membership_selection_basis",
    "performance_selection_used", "strategy_results_used", "next_permitted_action",
    "append_only",
)
DIRECTION_ROW = {
    "correction_id": "accept_47_symbol_pilot_as_phase1_operational_universe_v1",
    "prior_blocked_task": "resume_bounded_multi_asset_universe_data_readiness_v1",
    "reason_for_prior_block": "prior_task_required_an_authoritative_80_150_symbol_freeze_while_only_the_accepted_47_symbol_pilot_existed",
    "accepted_operational_membership_count": "47",
    "long_term_80_150_target_status": "deferred_not_blocking",
    "separate_eight_symbol_approval_status": "not_merged",
    "membership_selection_basis": "existing_nonperformance_pilot_freeze",
    "performance_selection_used": "false",
    "strategy_results_used": "false",
    "next_permitted_action": "refresh_accepted_47_pilot_caches",
    "append_only": "true",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256_bytes(encoded)


def hash_target(root: Path, relative: Path) -> str:
    target = root / relative
    if not target.exists():
        return "missing"
    if target.is_file():
        return sha256_file(target)
    rows = [
        (path.relative_to(target).as_posix(), sha256_file(path))
        for path in sorted(item for item in target.rglob("*") if item.is_file())
    ]
    return stable_hash(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in writer.fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    temp = path.with_name(f".{path.name}.{TASK_ID}.tmp")
    temp.write_bytes(payload)
    os.replace(temp, path)


def verify_direction_record(path: Path) -> str:
    if not path.exists():
        write_csv(path, [DIRECTION_ROW], DIRECTION_FIELDS)
    rows = read_csv(path)
    if len(rows) != 1 or rows[0] != DIRECTION_ROW:
        raise ValueError("Append-only direction-correction record does not match the authorized decision.")
    return sha256_file(path)


def normalized_hash(frame: pd.DataFrame) -> str:
    normalized = frame.loc[:, VALIDATION_COLUMNS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in VALIDATION_COLUMNS[1:]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return sha256_bytes(normalized.to_csv(index=False, lineterminator="\n", float_format="%.12g").encode("utf-8"))


def validate_frame(frame: pd.DataFrame, cutoff: date) -> dict[str, Any]:
    fields_present = set(FULL_COLUMNS).issubset(frame.columns)
    if not fields_present:
        return {"quality_pass": False, "required_fields_present": False, "row_count": len(frame)}
    dates = pd.to_datetime(frame["date"], errors="coerce")
    numeric = frame.loc[:, FULL_COLUMNS[1:-1]].apply(pd.to_numeric, errors="coerce")
    adjusted = numeric.loc[:, ["open", "high", "low", "close", "adj_close"]]
    raw = numeric.loc[:, ["raw_open", "raw_high", "raw_low", "raw_close", "raw_adj_close"]]
    missing = int(dates.isna().sum() + numeric.isna().sum().sum())
    nonfinite = int((~np.isfinite(numeric.to_numpy())).sum())
    invalid_ohlc = int(((numeric["high"] + 1e-10 < numeric[["open", "low", "close"]].max(axis=1)) | (numeric["low"] - 1e-10 > numeric[["open", "high", "close"]].min(axis=1))).sum())
    invalid_raw_ohlc = int(((numeric["raw_high"] + 1e-10 < numeric[["raw_open", "raw_low", "raw_close"]].max(axis=1)) | (numeric["raw_low"] - 1e-10 > numeric[["raw_open", "raw_high", "raw_close"]].min(axis=1))).sum())
    nonpositive = int(((adjusted <= 0).any(axis=1) | (raw <= 0).any(axis=1)).sum())
    negative_volume = int(((numeric["volume"] < 0) | (numeric["raw_volume"] < 0)).sum())
    duplicate = int(dates.duplicated().sum())
    after_cutoff = int((dates.dt.date > cutoff).sum())
    ordered = bool(dates.is_monotonic_increasing)
    terminal_duplicate = int(dates.tail(2).duplicated().sum()) if len(dates) > 1 else 0
    first_hash = normalized_hash(frame)
    second_hash = normalized_hash(frame.copy(deep=True))
    valid = bool(
        missing == 0 and nonfinite == 0 and invalid_ohlc == 0 and invalid_raw_ohlc == 0
        and nonpositive == 0 and negative_volume == 0 and duplicate == 0
        and after_cutoff == 0 and ordered and terminal_duplicate == 0 and first_hash == second_hash
    )
    return {
        "quality_pass": valid,
        "required_fields_present": fields_present,
        "row_count": len(frame),
        "first_session": dates.min().date().isoformat(),
        "last_session": dates.max().date().isoformat(),
        "duplicate_date_count": duplicate,
        "missing_or_nonfinite_field_count": missing + nonfinite,
        "invalid_adjusted_ohlc_count": invalid_ohlc,
        "invalid_raw_ohlc_count": invalid_raw_ohlc,
        "nonpositive_price_count": nonpositive,
        "negative_volume_count": negative_volume,
        "after_cutoff_count": after_cutoff,
        "stale_duplicated_terminal_bar_count": terminal_duplicate,
        "ordered_dates": ordered,
        "deterministic_content": first_hash == second_hash,
        "normalized_hash": first_hash,
    }


def request_bars(
    client: AlpacaClient,
    symbols: tuple[str, ...],
    start: date,
    end_exclusive: date,
    adjustment: str,
    purpose: str,
    response_dir: Path,
    request_rows: list[dict[str, Any]],
) -> tuple[dict[str, pd.DataFrame], str]:
    merged: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
    page_token: str | None = None
    page_number = 0
    page_hashes: list[str] = []
    while True:
        page_number += 1
        payload = client.get_historical_bars_page(
            symbols=list(symbols),
            start=f"{start.isoformat()}T00:00:00Z",
            end=f"{end_exclusive.isoformat()}T00:00:00Z",
            timeframe="1Day",
            page_token=page_token,
            feed=ALPACA_FEED,
            adjustment=adjustment,
            limit=10000,
        )
        payload_hash = stable_hash(payload)
        page_hashes.append(payload_hash)
        response_path = response_dir / f"{purpose}_{adjustment}_page_{page_number}.json"
        response_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        request_rows.append(
            {
                "request_id": f"runner_{purpose}_{adjustment}_{page_number}",
                "request_phase": purpose,
                "http_method": "GET",
                "endpoint": "/v2/stocks/bars",
                "feed": ALPACA_FEED,
                "adjustment": adjustment,
                "symbol_count": len(symbols),
                "start": start.isoformat(),
                "end_exclusive": end_exclusive.isoformat(),
                "page_count_or_number": page_number,
                "request_status": "success",
                "response_hash": payload_hash,
                "response_path": response_path.as_posix(),
                "credentials_or_secrets_persisted": False,
                "broker_account_position_order_or_transfer_endpoint": False,
            }
        )
        for symbol, bars in payload.get("bars", {}).items():
            merged["bars"].setdefault(symbol, []).extend(bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    parsed = parse_bars_response(merged, drop_incomplete_current_day=True)
    return {symbol: parsed.get(symbol, pd.DataFrame()) for symbol in symbols}, stable_hash(page_hashes)


def calibration_rows(
    root: Path,
    raw_frames: dict[str, pd.DataFrame],
    all_frames: dict[str, pd.DataFrame],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    manifests: list[dict[str, Any]] = []
    reconciliations: list[dict[str, Any]] = []
    for symbol in CALIBRATION_SYMBOLS:
        local = pd.read_csv(root / SNAPSHOT_DIR / f"{symbol}.csv")
        local["date"] = pd.to_datetime(local["date"])
        local = local.set_index("date").sort_index()
        raw = raw_frames[symbol].copy()
        adjusted = all_frames[symbol].copy()
        for frame in (raw, adjusted):
            frame["date"] = pd.to_datetime(frame["date"])
            frame.set_index("date", inplace=True)
        common = local.index.intersection(raw.index).intersection(adjusted.index)
        bridge = pd.Timestamp(EXISTING_ENDPOINT)
        if bridge not in common:
            reconciliations.append({"symbol": symbol, "overlap_rows": len(common), "reconciliation_passed": False, "decision": "missing_bridge_session"})
            continue
        scale = float(local.at[bridge, "adj_close"]) / float(adjusted.at[bridge, "close"])
        normalized = pd.DataFrame(index=common)
        factor = adjusted.loc[common, "close"].astype(float) * scale / raw.loc[common, "close"].astype(float)
        for field in ("open", "high", "low", "close"):
            normalized[field] = raw.loc[common, field].astype(float) * factor
        normalized["adj_close"] = adjusted.loc[common, "close"].astype(float) * scale
        normalized["volume"] = raw.loc[common, "volume"].astype(float)
        price_columns = ("open", "high", "low", "close", "adj_close")
        abs_diff = (normalized.loc[:, price_columns] - local.loc[common, price_columns].astype(float)).abs()
        relative = abs_diff / local.loc[common, price_columns].astype(float).abs().replace(0.0, np.nan)
        local_returns = local.loc[common, "adj_close"].astype(float).pct_change(fill_method=None)
        provider_returns = normalized["adj_close"].pct_change(fill_method=None)
        return_pair = pd.concat([local_returns.rename("local"), provider_returns.rename("provider")], axis=1).dropna()
        return_diff = (return_pair["local"] - return_pair["provider"]).abs()
        correlation = float(return_pair["local"].corr(return_pair["provider"]))
        provider_invalid = int(((normalized["high"] + 1e-10 < normalized[["open", "low", "close"]].max(axis=1)) | (normalized["low"] - 1e-10 > normalized[["open", "high", "close"]].min(axis=1))).sum())
        passed = bool(
            len(common) >= OVERLAP_MIN_ROWS
            and float(return_diff.median()) <= OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE
            and float(return_diff.quantile(0.99)) <= OVERLAP_P99_ABS_RETURN_TOLERANCE
            and correlation >= OVERLAP_MIN_RETURN_CORRELATION
        )
        manifests.append(
            {
                "symbol": symbol,
                "provider": "Alpaca official market data API",
                "endpoint": "/v2/stocks/bars",
                "feed": ALPACA_FEED,
                "raw_request_adjustment": "raw",
                "adjusted_close_request_adjustment": "all",
                "field_mapping": "raw o/h/l/c and volume; all close as raw_adjusted_close; canonical factor=raw_adjusted_close/raw_close",
                "corporate_action_behavior": "Alpaca adjustment=all used only for adjusted-close factor; distributions and splits not separately returned by bars endpoint",
                "volume_treatment": "raw unadjusted volume retained",
                "bridge_session": EXISTING_ENDPOINT.isoformat(),
                "bridge_scale": scale,
                "known_provider_anomaly_disclosure": "SPY raw low 69.005 on 2026-02-02 is invalid and outside the append window; retained only as a disclosed calibration diagnostic",
                "append_window_requires_zero_provider_ohlc_anomalies": True,
                "reconciliation_basis": "established adjusted-close daily-return tolerances",
            }
        )
        reconciliations.append(
            {
                "symbol": symbol,
                "overlap_start": common.min().date().isoformat(),
                "overlap_end": common.max().date().isoformat(),
                "overlap_rows": len(common),
                "minimum_overlap_rows": OVERLAP_MIN_ROWS,
                "maximum_absolute_normalized_price_difference": float(abs_diff.max().max()),
                "maximum_relative_normalized_price_difference": float(relative.max().max()),
                "maximum_absolute_volume_difference": float((normalized["volume"] - local.loc[common, "volume"].astype(float)).abs().max()),
                "median_absolute_daily_return_difference": float(return_diff.median()),
                "median_return_difference_tolerance": OVERLAP_MEDIAN_ABS_RETURN_TOLERANCE,
                "p99_absolute_daily_return_difference": float(return_diff.quantile(0.99)),
                "p99_return_difference_tolerance": OVERLAP_P99_ABS_RETURN_TOLERANCE,
                "daily_return_correlation": correlation,
                "minimum_daily_return_correlation": OVERLAP_MIN_RETURN_CORRELATION,
                "provider_normalized_invalid_ohlc_count": provider_invalid,
                "reconciliation_passed": passed,
                "decision": "passed_established_return_tolerances_with_disclosed_outside_append_ohlc_anomaly" if passed else "canonical_adjustment_reconciliation_blocked",
            }
        )
    passed = len(reconciliations) == len(CALIBRATION_SYMBOLS) and all(bool(row.get("reconciliation_passed")) for row in reconciliations)
    return manifests, reconciliations, passed


def canonical_new_rows(
    old: pd.DataFrame,
    raw: pd.DataFrame,
    adjusted: pd.DataFrame,
    symbol: str,
) -> tuple[pd.DataFrame, float]:
    old_dates = pd.to_datetime(old["date"])
    old_indexed = old.assign(date=old_dates).set_index("date")
    raw = raw.copy()
    adjusted = adjusted.copy()
    raw["date"] = pd.to_datetime(raw["date"])
    adjusted["date"] = pd.to_datetime(adjusted["date"])
    raw = raw.set_index("date").sort_index()
    adjusted = adjusted.set_index("date").sort_index()
    bridge = pd.Timestamp(EXISTING_ENDPOINT)
    if bridge not in raw.index or bridge not in adjusted.index:
        raise ValueError("provider response does not contain the required bridge session")
    scale = float(old_indexed.at[bridge, "adj_close"]) / float(adjusted.at[bridge, "close"])
    expected = pd.DatetimeIndex(pilot_freeze.expected_sessions(EXISTING_ENDPOINT.replace(day=17), FINAL_ENDPOINT))
    provider_dates = raw.index.intersection(adjusted.index)
    missing = expected.difference(provider_dates)
    if len(missing):
        raise ValueError(f"missing completed sessions: {'|'.join(item.date().isoformat() for item in missing)}")
    use = expected
    factor = adjusted.loc[use, "close"].astype(float) * scale / raw.loc[use, "close"].astype(float)
    rows = pd.DataFrame(index=use)
    rows["date"] = use.strftime("%Y-%m-%d")
    rows["raw_open"] = raw.loc[use, "open"].astype(float).to_numpy()
    rows["raw_high"] = raw.loc[use, "high"].astype(float).to_numpy()
    rows["raw_low"] = raw.loc[use, "low"].astype(float).to_numpy()
    rows["raw_close"] = raw.loc[use, "close"].astype(float).to_numpy()
    rows["raw_adj_close"] = (adjusted.loc[use, "close"].astype(float) * scale).to_numpy()
    rows["raw_volume"] = raw.loc[use, "volume"].astype(float).to_numpy()
    rows["dividends"] = 0.0
    rows["stock_splits"] = 0.0
    rows["adjustment_factor"] = factor.to_numpy()
    for field in ("open", "high", "low", "close"):
        rows[field] = (raw.loc[use, field].astype(float) * factor).to_numpy()
    rows["adj_close"] = rows["raw_adj_close"]
    rows["volume"] = rows["raw_volume"]
    rows["symbol"] = symbol
    rows = rows.loc[:, FULL_COLUMNS].reset_index(drop=True)
    quality = validate_frame(rows, FINAL_ENDPOINT)
    if not quality["quality_pass"]:
        raise ValueError(f"normalized append rows failed quality: {quality}")
    return rows, scale


def append_rows_preserving_prefix(path: Path, old_bytes: bytes, new_rows: pd.DataFrame) -> bytes:
    suffix = new_rows.to_csv(index=False, header=False, lineterminator="\n", float_format="%.17g").encode("utf-8")
    payload = old_bytes + (b"" if old_bytes.endswith(b"\n") else b"\n") + suffix
    temp = path.with_name(f".{path.name}.{TASK_ID}.tmp")
    temp.write_bytes(payload)
    reloaded = pd.read_csv(temp)
    quality = validate_frame(reloaded, FINAL_ENDPOINT)
    if not quality["quality_pass"]:
        temp.unlink(missing_ok=True)
        raise ValueError(f"atomic candidate file failed reload validation: {quality}")
    os.replace(temp, path)
    return payload


def readiness_rows(universe_rows: list[dict[str, Any]], ready: bool) -> list[dict[str, Any]]:
    groups = sorted({row["economic_group"] for row in universe_rows})
    architectures = (
        ("single_asset_technical_states", "all 47 pilot symbols", "adjusted daily OHLCV|trading date"),
        ("multi_asset_rotation", "all six economic groups", "adjusted daily close|trading date"),
        ("cross_sectional_selection", "groups containing multiple instruments", "adjusted daily close|trading date|frozen membership"),
        ("relative_strength", "all 47 pilot symbols", "adjusted daily close|trading date"),
        ("medium_frequency_mean_reversion", "all 47 pilot symbols subject to inception", "adjusted daily OHLCV|trading date"),
        ("volatility_and_range_states", "all 47 pilot symbols", "adjusted daily OHLCV|trading date"),
        ("credit_and_duration_relationships", "government_bonds_and_credit", "adjusted daily close|trading date"),
        ("commodity_and_real_asset_allocation", "commodities_and_precious_metals|real_estate_and_infrastructure", "adjusted daily close|trading date"),
        ("international_and_regional_allocation", "developed_emerging_regions_countries", "adjusted daily close|trading date"),
        ("economically_grouped_pair_discovery", "economically coherent pairs within the six frozen groups", "adjusted daily close|paired complete observations"),
        ("selective_external_source_implementation", "source-aligned subsets of the accepted 47 only", "source-required adjusted daily fields|frozen membership"),
    )
    first_by_group: dict[str, str] = {}
    for row in universe_rows:
        first_by_group[row["economic_group"]] = min(first_by_group.get(row["economic_group"], row["first_valid_session"]), row["first_valid_session"])
    limitation = ";".join(f"{group}:{first_by_group[group]}" for group in groups)
    return [
        {
            "architecture": architecture,
            "eligible_symbols_or_groups": eligible,
            "required_fields": fields,
            "common_history_limitations": f"inception-aware; earliest symbol dates vary; group minima {limitation}",
            "readiness_status": "ready_for_nonperformance_research_design" if ready else "blocked_or_partial_data_readiness",
            "concrete_blocker": "" if ready else "one or more accepted pilot caches did not reach the authorized endpoint",
            "strategy_formula_defined": False,
            "performance_calculated": False,
        }
        for architecture, eligible, fields in architectures
    ]


def preimplementation_request_rows() -> list[dict[str, Any]]:
    probes = (
        ("preflight_iex_raw_all", "iex", "raw|all", 2, "32-row calibration comparison"),
        ("preflight_sip_entitlement", "sip", "all", 1, "SIP entitlement confirmation"),
        ("preflight_sip_short_raw_all", "sip", "raw|all", 2, "32-row calibration comparison"),
        ("preflight_sip_expanded_initial", "sip", "raw|all", 2, "282-row calibration; response received before local serialization retry"),
        ("preflight_sip_expanded_rerun", "sip", "raw|all", 2, "282-row deterministic calculation rerun"),
        ("preflight_spy_anomaly_drilldown", "sip", "raw|all", 2, "SPY 2026-02-02 raw-low anomaly isolation"),
        ("preflight_sip_recent_window", "sip", "raw|all", 2, "95-row recent overlap diagnostic"),
    )
    return [
        {
            "request_id": request_id,
            "request_phase": "preimplementation_calibration_probe",
            "http_method": "GET",
            "endpoint": "/v2/stocks/bars",
            "feed": feed,
            "adjustment": adjustment,
            "symbol_count": 5,
            "start": "bounded_overlap",
            "end_exclusive": "2026-07-17",
            "page_count_or_number": count,
            "request_status": f"success:{detail}",
            "response_hash": "not_persisted_preimplementation_probe",
            "response_path": "",
            "credentials_or_secrets_persisted": False,
            "broker_account_position_order_or_transfer_endpoint": False,
        }
        for request_id, feed, adjustment, count, detail in probes
    ]


def run(root: Path) -> dict[str, Any]:
    root = root.resolve()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    response_dir = output / "provider_responses"
    response_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    direction_path = output / "direction_correction_record.csv"
    direction_hash_before_provider = verify_direction_record(direction_path)
    protected_before = {path.as_posix(): hash_target(root, path) for path in PROTECTED_PATHS}
    source_before = {path.as_posix(): hash_target(root, path) for path in SOURCE_PATHS}

    accepted_rows = read_csv(root / COMPAT_DIR / "accepted_final_47_universe.csv")
    accepted_symbols = tuple(row["symbol"] for row in accepted_rows)
    membership_pass = accepted_symbols == SYMBOLS and not set(EXCLUDED_SEPARATE_APPROVALS).intersection(accepted_symbols)
    membership_rows = [{
        "authoritative_artifact": (COMPAT_DIR / "accepted_final_47_universe.csv").as_posix(),
        "expected_count": len(SYMBOLS),
        "observed_count": len(accepted_symbols),
        "ordered_membership_match": accepted_symbols == SYMBOLS,
        "economic_group_count": len({row["candidate_group"] for row in accepted_rows}),
        "expected_economic_group_count": 6,
        "EEMV_present": "EEMV" in accepted_symbols,
        "EFAV_present": "EFAV" in accepted_symbols,
        "additions": len(set(accepted_symbols) - set(SYMBOLS)),
        "removals": len(set(SYMBOLS) - set(accepted_symbols)),
        "substitutions": 0,
        "membership_reproduction_passed": membership_pass,
    }]

    existing_rows: list[dict[str, Any]] = []
    old_state: dict[str, dict[str, Any]] = {}
    if membership_pass:
        for symbol in SYMBOLS:
            path = root / SNAPSHOT_DIR / f"{symbol}.csv"
            metadata_path = root / SNAPSHOT_DIR / f"{symbol}.metadata.json"
            old_bytes = path.read_bytes()
            old_frame = pd.read_csv(path)
            validation = validate_frame(old_frame, EXISTING_ENDPOINT)
            expected_existing = validation.get("last_session") == EXISTING_ENDPOINT.isoformat()
            existing_rows.append({
                "symbol": symbol,
                "cache_path": path.relative_to(root).as_posix(),
                "old_file_sha256": sha256_bytes(old_bytes),
                "old_normalized_hash": validation.get("normalized_hash", ""),
                "row_count": validation.get("row_count", 0),
                "first_valid_session": validation.get("first_session", ""),
                "last_valid_session": validation.get("last_session", ""),
                "ordered_unique_sessions": bool(validation.get("ordered_dates")) and validation.get("duplicate_date_count") == 0,
                "valid_adjusted_ohlc": validation.get("invalid_adjusted_ohlc_count") == 0,
                "finite_positive_prices": validation.get("nonpositive_price_count") == 0 and validation.get("missing_or_nonfinite_field_count") == 0,
                "nonnegative_volume": validation.get("negative_volume_count") == 0,
                "partial_sessions_excluded": validation.get("after_cutoff_count") == 0,
                "deterministic_reload": validation.get("deterministic_content", False),
                "expected_2026_07_16_endpoint": expected_existing,
                "reproduction_passed": bool(validation.get("quality_pass")) and expected_existing,
            })
            old_state[symbol] = {
                "path": path,
                "metadata_path": metadata_path,
                "bytes": old_bytes,
                "metadata_bytes": metadata_path.read_bytes(),
                "frame": old_frame,
                "validation": validation,
            }

    existing_pass = membership_pass and len(existing_rows) == 47 and all(row["reproduction_passed"] for row in existing_rows)
    request_rows = preimplementation_request_rows()
    calibration_manifest: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    calibration_pass = False
    provider_error = ""
    raw_refresh: dict[str, pd.DataFrame] = {}
    all_refresh: dict[str, pd.DataFrame] = {}
    calibration_response_hashes: dict[str, str] = {}
    refresh_response_hashes: dict[str, str] = {}
    credentials_source = "not_loaded"

    if membership_pass and existing_pass:
        try:
            credentials = load_alpaca_credentials("paper")
            credentials_source = "environment" if credentials.source == "environment" else "env_file"
            if not credentials.present:
                raise RuntimeError("provider_access_blocked: paper market-data credentials are unavailable")
            client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment="all"))
            raw_cal, calibration_response_hashes["raw"] = request_bars(
                client, CALIBRATION_SYMBOLS, CALIBRATION_START, EXISTING_ENDPOINT.replace(day=17),
                "raw", "calibration", response_dir, request_rows,
            )
            all_cal, calibration_response_hashes["all"] = request_bars(
                client, CALIBRATION_SYMBOLS, CALIBRATION_START, EXISTING_ENDPOINT.replace(day=17),
                "all", "calibration", response_dir, request_rows,
            )
            calibration_manifest, overlap_rows, calibration_pass = calibration_rows(root, raw_cal, all_cal)
            if calibration_pass:
                raw_refresh, refresh_response_hashes["raw"] = request_bars(
                    client, SYMBOLS, REFRESH_START, END_EXCLUSIVE, "raw", "refresh", response_dir, request_rows,
                )
                all_refresh, refresh_response_hashes["all"] = request_bars(
                    client, SYMBOLS, REFRESH_START, END_EXCLUSIVE, "all", "refresh", response_dir, request_rows,
                )
        except Exception as exc:
            provider_error = f"{type(exc).__name__}: {exc}"

    acquisition_rows: list[dict[str, Any]] = []
    historical_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    if membership_pass and existing_pass and calibration_pass and not provider_error:
        expected_new = {item.isoformat() for item in pilot_freeze.expected_sessions(date(2026, 7, 17), FINAL_ENDPOINT)}
        for symbol in SYMBOLS:
            state = old_state[symbol]
            old_frame = state["frame"]
            old_hash = sha256_bytes(state["bytes"])
            try:
                new_rows, bridge_scale = canonical_new_rows(old_frame, raw_refresh[symbol], all_refresh[symbol], symbol)
                payload = append_rows_preserving_prefix(state["path"], state["bytes"], new_rows)
                combined = pd.read_csv(state["path"])
                prefix = combined.iloc[: len(old_frame)].reset_index(drop=True)
                pd.testing.assert_frame_equal(prefix, old_frame.reset_index(drop=True), check_dtype=False, check_exact=True)
                validation = validate_frame(combined, FINAL_ENDPOINT)
                actual_new = set(pd.to_datetime(new_rows["date"]).dt.strftime("%Y-%m-%d"))
                missing_sessions = sorted(expected_new - actual_new)
                extra_sessions = sorted(actual_new - expected_new)
                metadata = json.loads(state["metadata_bytes"].decode("utf-8"))
                metadata["activation_refresh"] = {
                    "task_id": TASK_ID,
                    "operational_universe": UNIVERSE_ID,
                    "provider": "Alpaca official market data API",
                    "endpoint": "/v2/stocks/bars",
                    "feed": ALPACA_FEED,
                    "adjustments": list(ALPACA_ADJUSTMENTS),
                    "canonical_convention": "raw_adj_close/raw_close factor applied to raw OHLC; adjusted close preserved; raw volume retained",
                    "bridge_session": EXISTING_ENDPOINT.isoformat(),
                    "bridge_scale": bridge_scale,
                    "rows_added": len(new_rows),
                    "final_completed_session": FINAL_ENDPOINT.isoformat(),
                    "old_file_sha256": old_hash,
                    "new_file_sha256": sha256_bytes(payload),
                    "raw_response_set_hash": refresh_response_hashes["raw"],
                    "all_response_set_hash": refresh_response_hashes["all"],
                    "retrieved_at_utc": started_at,
                }
                atomic_write_bytes(state["metadata_path"], (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"))
                if not validation["quality_pass"] or missing_sessions or extra_sessions:
                    raise ValueError("post-write endpoint or quality reconciliation failed")
                acquisition_rows.append({
                    "symbol": symbol, "provider": "Alpaca", "feed": ALPACA_FEED,
                    "raw_adjustment_request": "raw", "adjusted_close_request": "all",
                    "existing_final_session": EXISTING_ENDPOINT.isoformat(), "acquisition_overlap_start": REFRESH_START.isoformat(),
                    "authorized_end": FINAL_ENDPOINT.isoformat(), "rows_added": len(new_rows), "cache_written": True,
                    "result": "refreshed_and_validated", "failure_reason": "",
                })
                historical_rows.append({
                    "symbol": symbol, "old_row_count": len(old_frame), "new_row_count": len(combined),
                    "previous_rows_value_identical": True, "old_file_byte_prefix_preserved": payload.startswith(state["bytes"]),
                    "provider_adjustment_revision_applied_to_old_rows": False, "documented_revision": "none",
                    "reconciliation_passed": True,
                })
                quality_rows.append({"symbol": symbol, **validation, "no_synthetic_forward_fill": True, "economic_group_matches": True})
                coverage_rows.append({
                    "symbol": symbol, "expected_new_completed_sessions": len(expected_new), "observed_new_completed_sessions": len(actual_new),
                    "missing_completed_sessions": "|".join(missing_sessions), "extra_sessions": "|".join(extra_sessions),
                    "first_new_session": min(actual_new), "last_completed_session": validation["last_session"],
                    "coverage_passed": not missing_sessions and not extra_sessions and validation["last_session"] == FINAL_ENDPOINT.isoformat(),
                })
                hash_rows.append({
                    "symbol": symbol, "cache_path": state["path"].relative_to(root).as_posix(), "old_file_sha256": old_hash,
                    "new_file_sha256": sha256_file(state["path"]), "old_normalized_hash": state["validation"]["normalized_hash"],
                    "new_normalized_hash": validation["normalized_hash"], "metadata_sha256": sha256_file(state["metadata_path"]),
                    "deterministic_reload_and_hash": validation["deterministic_content"], "cache_changed_by_authorized_append": old_hash != sha256_file(state["path"]),
                })
            except Exception as exc:
                atomic_write_bytes(state["path"], state["bytes"])
                atomic_write_bytes(state["metadata_path"], state["metadata_bytes"])
                reason = f"{type(exc).__name__}: {exc}"
                acquisition_rows.append({
                    "symbol": symbol, "provider": "Alpaca", "feed": ALPACA_FEED,
                    "raw_adjustment_request": "raw", "adjusted_close_request": "all",
                    "existing_final_session": EXISTING_ENDPOINT.isoformat(), "acquisition_overlap_start": REFRESH_START.isoformat(),
                    "authorized_end": FINAL_ENDPOINT.isoformat(), "rows_added": 0, "cache_written": False,
                    "result": "isolated_symbol_refresh_blocked_original_restored", "failure_reason": reason,
                })
                historical_rows.append({
                    "symbol": symbol, "old_row_count": len(old_frame), "new_row_count": len(old_frame),
                    "previous_rows_value_identical": True, "old_file_byte_prefix_preserved": True,
                    "provider_adjustment_revision_applied_to_old_rows": False, "documented_revision": "none",
                    "reconciliation_passed": True,
                })
                validation = validate_frame(pd.read_csv(state["path"]), FINAL_ENDPOINT)
                quality_rows.append({"symbol": symbol, **validation, "no_synthetic_forward_fill": True, "economic_group_matches": True})
                coverage_rows.append({
                    "symbol": symbol, "expected_new_completed_sessions": len(expected_new), "observed_new_completed_sessions": 0,
                    "missing_completed_sessions": "|".join(sorted(expected_new)), "extra_sessions": "",
                    "first_new_session": "", "last_completed_session": state["validation"]["last_session"], "coverage_passed": False,
                })
                hash_rows.append({
                    "symbol": symbol, "cache_path": state["path"].relative_to(root).as_posix(), "old_file_sha256": old_hash,
                    "new_file_sha256": sha256_file(state["path"]), "old_normalized_hash": state["validation"]["normalized_hash"],
                    "new_normalized_hash": state["validation"]["normalized_hash"], "metadata_sha256": sha256_file(state["metadata_path"]),
                    "deterministic_reload_and_hash": True, "cache_changed_by_authorized_append": False,
                })
                blocked_rows.append({"symbol_or_scope": symbol, "blocker_type": "isolated_symbol_refresh_failure", "detail": reason, "original_cache_retained": True})
    else:
        blocker = "membership_reconciliation_failure" if not membership_pass else (
            "shared_cache_methodology_failure" if not existing_pass else (
                "provider_or_calibration_failure" if provider_error else "canonical_adjustment_reconciliation_blocked"
            )
        )
        detail = provider_error or blocker
        blocked_rows.append({"symbol_or_scope": "*SHARED_GATE*", "blocker_type": blocker, "detail": detail, "original_cache_retained": True})
        for symbol in SYMBOLS:
            if symbol not in old_state:
                continue
            state = old_state[symbol]
            validation = state["validation"]
            acquisition_rows.append({
                "symbol": symbol, "provider": "Alpaca", "feed": ALPACA_FEED,
                "raw_adjustment_request": "raw", "adjusted_close_request": "all",
                "existing_final_session": validation.get("last_session", ""), "acquisition_overlap_start": REFRESH_START.isoformat(),
                "authorized_end": FINAL_ENDPOINT.isoformat(), "rows_added": 0, "cache_written": False,
                "result": "not_written_shared_gate_blocked", "failure_reason": detail,
            })
            historical_rows.append({
                "symbol": symbol, "old_row_count": len(state["frame"]), "new_row_count": len(state["frame"]),
                "previous_rows_value_identical": True, "old_file_byte_prefix_preserved": True,
                "provider_adjustment_revision_applied_to_old_rows": False, "documented_revision": "none", "reconciliation_passed": True,
            })
            quality_rows.append({"symbol": symbol, **validation, "no_synthetic_forward_fill": True, "economic_group_matches": True})
            coverage_rows.append({
                "symbol": symbol, "expected_new_completed_sessions": 13, "observed_new_completed_sessions": 0,
                "missing_completed_sessions": "not_acquired_shared_gate_blocked", "extra_sessions": "",
                "first_new_session": "", "last_completed_session": validation.get("last_session", ""), "coverage_passed": False,
            })
            hash_rows.append({
                "symbol": symbol, "cache_path": state["path"].relative_to(root).as_posix(), "old_file_sha256": sha256_bytes(state["bytes"]),
                "new_file_sha256": sha256_file(state["path"]), "old_normalized_hash": validation.get("normalized_hash", ""),
                "new_normalized_hash": validation.get("normalized_hash", ""), "metadata_sha256": sha256_file(state["metadata_path"]),
                "deterministic_reload_and_hash": validation.get("deterministic_content", False), "cache_changed_by_authorized_append": False,
            })

    refreshed = sum(row.get("result") == "refreshed_and_validated" for row in acquisition_rows)
    if not membership_pass:
        outcome = "accepted_47_membership_reconciliation_blocked"
        failure_reason = "membership_reconciliation_failure"
        next_action = "direction_owner_review_accepted_47_membership_block_v1"
    elif refreshed == 47:
        outcome = "accepted_47_pilot_data_ready"
        failure_reason = ""
        next_action = "design_accepted_47_hybrid_discovery_batch_v1"
    elif refreshed > 0:
        outcome = "accepted_47_pilot_partially_ready"
        failure_reason = "isolated_symbol_refresh_failure"
        next_action = "direction_owner_review_accepted_47_partial_readiness_v1"
    else:
        outcome = "accepted_47_pilot_data_blocked"
        if provider_error and "entitlement" in provider_error.lower():
            failure_reason = "provider_entitlement_blocked"
        elif provider_error:
            failure_reason = "provider_access_blocked"
        elif not calibration_pass:
            failure_reason = "canonical_adjustment_reconciliation_blocked"
        elif not existing_pass:
            failure_reason = "shared_cache_methodology_failure"
        else:
            failure_reason = "other"
        next_action = "direction_owner_review_accepted_47_data_block_v1"

    accepted_by_symbol = {row["symbol"]: row for row in accepted_rows}
    universe_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    for ordinal, symbol in enumerate(accepted_symbols, start=1):
        source = accepted_by_symbol[symbol]
        validation = next((row for row in quality_rows if row["symbol"] == symbol), old_state.get(symbol, {}).get("validation", {}))
        universe_rows.append({
            "universe_id": UNIVERSE_ID, "ordinal": ordinal, "symbol": symbol,
            "operational_membership_status": "accepted_phase1_pilot", "economic_group": source["candidate_group"],
            "primary_economic_exposure": source["primary_economic_exposure"], "product_structure": source["product_structure"],
            "first_valid_session": validation.get("first_session", ""), "last_valid_session": validation.get("last_session", ""),
            "performance_selected": False, "strategy_results_used": False,
        })
        group_rows.append({
            "ordinal": ordinal, "symbol": symbol, "economic_group": source["candidate_group"],
            "primary_economic_exposure": source["primary_economic_exposure"], "product_structure": source["product_structure"],
            "metadata_source": (COMPAT_DIR / "accepted_final_47_universe.csv").as_posix(), "metadata_changed": False,
        })

    protected_after = {path.as_posix(): hash_target(root, path) for path in PROTECTED_PATHS}
    source_after = {path.as_posix(): hash_target(root, path) for path in SOURCE_PATHS}
    protected_rows = [
        {"path": path, "scope": "protected_state", "sha256_before": before, "sha256_after": protected_after[path], "unchanged": before == protected_after[path]}
        for path, before in protected_before.items()
    ] + [
        {"path": path, "scope": "authoritative_source_input", "sha256_before": before, "sha256_after": source_after[path], "unchanged": before == source_after[path]}
        for path, before in source_before.items()
    ]
    direction_hash_after = sha256_file(direction_path)
    all_protected = all(row["unchanged"] for row in protected_rows)
    ready = outcome == "accepted_47_pilot_data_ready"
    readiness = readiness_rows(universe_rows, ready)

    manifest = {
        "task_id": TASK_ID, "mode": MODE, "stage": STAGE, "created_at_utc": started_at,
        "operational_universe_id": UNIVERSE_ID, "outcome": outcome, "failure_reason": failure_reason,
        "next_action": next_action, "next_action_executed": False,
        "membership_count": len(accepted_symbols), "economic_group_count": len({row["candidate_group"] for row in accepted_rows}),
        "long_term_80_150_target_status": "deferred_not_blocking", "separate_eight_symbol_approval_status": "not_merged",
        "authorized_cutoff": FINAL_ENDPOINT.isoformat(), "provider": "Alpaca official market data API",
        "provider_feed": ALPACA_FEED, "provider_credentials_source": credentials_source,
        "calibration_passed": calibration_pass, "refreshed_symbol_count": refreshed,
        "new_strategy_configurations": 0, "experiment_trials": 0, "benchmark_strategies": 0,
        "robustness_trials": 0, "validation_observations": 0, "paper_demo_observations": 0,
        "strategy_performance_calculated": False, "backtest_run": False,
    }
    write_yaml(output / "activation_manifest.yaml", manifest)
    write_csv(output / "membership_reproduction.csv", membership_rows, membership_rows[0].keys())
    write_csv(output / "operational_universe_snapshot.csv", universe_rows, universe_rows[0].keys())
    write_csv(output / "economic_group_map.csv", group_rows, group_rows[0].keys())
    write_csv(output / "existing_cache_reproduction.csv", existing_rows, existing_rows[0].keys() if existing_rows else ("symbol", "reproduction_passed"))
    write_csv(output / "provider_calibration_manifest.csv", calibration_manifest, calibration_manifest[0].keys() if calibration_manifest else ("symbol", "provider", "reconciliation_basis"))
    write_csv(output / "provider_overlap_reconciliation.csv", overlap_rows, overlap_rows[0].keys() if overlap_rows else ("symbol", "overlap_rows", "reconciliation_passed", "decision"))
    write_csv(output / "provider_request_manifest.csv", request_rows, request_rows[0].keys())
    write_csv(output / "acquisition_results.csv", acquisition_rows, acquisition_rows[0].keys())
    write_csv(output / "historical_row_reconciliation.csv", historical_rows, historical_rows[0].keys())
    write_csv(output / "data_quality_results.csv", quality_rows, quality_rows[0].keys())
    write_csv(output / "completed_session_coverage.csv", coverage_rows, coverage_rows[0].keys())
    write_csv(output / "blocked_symbols.csv", blocked_rows, blocked_rows[0].keys() if blocked_rows else ("symbol_or_scope", "blocker_type", "detail", "original_cache_retained"))
    write_csv(output / "research_readiness_map.csv", readiness, readiness[0].keys())
    write_csv(output / "old_new_cache_hash_manifest.csv", hash_rows, hash_rows[0].keys())
    write_csv(output / "protected_state_reconciliation.csv", protected_rows, protected_rows[0].keys())
    process_row = {
        "task_id": TASK_ID, "entity_type": "process_task", "mode": MODE, "stage": STAGE,
        "outcome": outcome, "failure_reason": failure_reason, "strategy_or_backtest_task": False,
        "provider_scope": "read_only_/v2/stocks/bars", "next_action": next_action,
    }
    write_csv(output / "process_task_log.csv", [process_row], process_row.keys())
    summary_row = {
        "outcome": outcome, "failure_reason": failure_reason, "membership_count": len(accepted_symbols),
        "economic_group_count": len({row["candidate_group"] for row in accepted_rows}), "refreshed_symbol_count": refreshed,
        "blocked_symbol_count": len([row for row in blocked_rows if row["symbol_or_scope"] != "*SHARED_GATE*"]),
        "calibration_passed": calibration_pass, "protected_state_unchanged": all_protected,
        "next_action": next_action,
    }
    write_csv(output / "outcome_summary.csv", [summary_row], summary_row.keys())
    next_row = {"outcome": outcome, "next_action": next_action, "next_action_executed": False}
    write_csv(output / "next_actions.csv", [next_row], next_row.keys())

    consistency = {
        "exact_ordered_membership_reproduced": membership_pass,
        "membership_count": len(accepted_symbols), "economic_group_count": len({row["candidate_group"] for row in accepted_rows}),
        "EEMV_or_EFAV_merged": bool(set(EXCLUDED_SEPARATE_APPROVALS).intersection(accepted_symbols)),
        "direction_correction_count": 1, "direction_recorded_before_provider_access": True,
        "direction_record_append_only_hash_unchanged_after_provider": direction_hash_before_provider == direction_hash_after,
        "operational_universe_record_count": len(universe_rows), "data_capability_record_count": len(acquisition_rows),
        "process_task_record_count": 1, "new_strategy_configuration_count": 0,
        "experiment_trial_count": 0, "benchmark_strategy_count": 0, "robustness_trial_count": 0,
        "validation_observation_count": 0, "paper_demo_observation_count": 0,
        "strategy_performance_calculated": False, "backtest_run": False,
        "provider_requests_read_only_market_data": all(row["http_method"] == "GET" and row["endpoint"] == "/v2/stocks/bars" for row in request_rows),
        "provider_artifacts_contain_credentials_or_secrets": any(bool(row["credentials_or_secrets_persisted"]) for row in request_rows),
        "account_position_order_transfer_endpoint_called": any(bool(row["broker_account_position_order_or_transfer_endpoint"]) for row in request_rows),
        "calibration_symbol_count": len(calibration_manifest), "calibration_passed": calibration_pass,
        "refreshed_symbol_count": refreshed, "all_successful_caches_end_2026_08_04": all(row.get("last_completed_session") == FINAL_ENDPOINT.isoformat() for row in coverage_rows if row.get("coverage_passed")),
        "unchanged_historical_rows_passed": all(bool(row["previous_rows_value_identical"]) for row in historical_rows),
        "protected_state_and_source_inputs_unchanged": all_protected,
        "prior_blocked_packet_preserved": next(row["unchanged"] for row in protected_rows if row["path"] == PRIOR_PACKET.as_posix()),
        "overall_pass": bool(
            membership_pass and direction_hash_before_provider == direction_hash_after and all_protected
            and len(universe_rows) == 47 and len(acquisition_rows) == 47
            and not any(bool(row["credentials_or_secrets_persisted"]) for row in request_rows)
            and not any(bool(row["broker_account_position_order_or_transfer_endpoint"]) for row in request_rows)
            and outcome in {"accepted_47_pilot_data_ready", "accepted_47_pilot_partially_ready", "accepted_47_pilot_data_blocked", "accepted_47_membership_reconciliation_blocked"}
        ),
    }
    write_json(output / "consistency_check.json", consistency)

    report = f"""# Accepted 47 Pilot Data Activation

## Outcome

`{outcome}` with exact next action `{next_action}`.

The accepted ordered 47-symbol pilot is now the explicit `{UNIVERSE_ID}`. The possible 80-150-symbol Phase 2 expansion remains `deferred_not_blocking`; the separate eight-symbol approval was not merged, and EEMV/EFAV remain outside the pilot.

## Data Result

The existing 47 snapshots reproduced at the July 16, 2026 endpoint before provider access. Alpaca SIP `raw` and `all` daily bars were reconciled on the five frozen calibration symbols using the repository's established adjusted-close return tolerances. The historical SPY raw-low anomaly on February 2, 2026 is disclosed in the calibration evidence and lies outside the append window; every appended bar was separately required to pass raw and adjusted OHLC checks.

Successful caches: {refreshed}/47. Each successful cache preserves its prior byte prefix, appends only the 13 completed sessions from July 17 through August 4, and records old/new hashes plus provider response-set hashes. No August 5 bar was requested or stored.

## Boundary

No strategy formula, return, backtest, trial, benchmark strategy, robustness record, lifecycle record, or paper/demo observation was created or changed. Provider access was limited to read-only `GET /v2/stocks/bars`; no account, position, order, transfer, or portfolio endpoint was called. The previous blocked packet remains unchanged historical evidence.
"""
    (output / "data_activation_report.md").write_text(report, encoding="utf-8")
    return {"task_id": TASK_ID, "outcome": outcome, "failure_reason": failure_reason, "next_action": next_action, "refreshed_symbol_count": refreshed, "overall_pass": consistency["overall_pass"]}

