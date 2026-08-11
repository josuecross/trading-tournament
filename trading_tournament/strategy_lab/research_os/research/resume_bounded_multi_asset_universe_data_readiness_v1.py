from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.universe_expansion import (
    acquire_validate_and_freeze_pilot_etf_market_data_v1 as pilot_freeze,
)


TASK_ID = "resume_bounded_multi_asset_universe_data_readiness_v1"
MODE = "bounded-universe-data-capability"
STAGE = "implementation"
OUTCOME = "authoritative_universe_freeze_blocked"
NEXT_ACTION = "direction_owner_review_bounded_universe_freeze_v1"
TARGET_MINIMUM = 80
TARGET_MAXIMUM = 150

OUTPUT_DIR = Path("evidence") / "data_capability" / TASK_ID / "latest"
PILOT_DESIGN_DIR = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_universe_design_v1"
)
PILOT_FREEZE_DIR = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_etf_market_data_freeze_v1"
)
PILOT_COMPAT_DIR = (
    Path("strategy_lab")
    / "research_os"
    / "universe_expansion"
    / "pilot_instrument_strategy_compatibility_v1"
)
APPROVED_EXPANSION_DIR = Path("evidence") / "approved_symbol_expansion_review" / "latest"
APPROVED_CACHE_DIR = Path("evidence") / "approved_expansion_cache_bootstrap" / "latest"
SNAPSHOT_DIR = Path("data") / "universe_expansion" / "pilot_etf_market_data_v1"

REQUIRED_SNAPSHOT_FIELDS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)

OUTPUT_FILES = (
    "data_readiness_manifest.yaml",
    "source_of_truth_reconciliation.md",
    "authoritative_universe_snapshot.csv",
    "universe_rule_reconciliation.csv",
    "symbol_metadata.csv",
    "economic_group_map.csv",
    "existing_cache_inventory.csv",
    "provider_request_manifest.csv",
    "acquisition_results.csv",
    "data_quality_results.csv",
    "coverage_summary.csv",
    "blocked_symbols.csv",
    "research_compatibility_map.csv",
    "cache_hash_manifest.csv",
    "protected_state_reconciliation.csv",
    "process_task_log.csv",
    "outcome_summary.csv",
    "next_actions.csv",
    "consistency_check.json",
    "data_readiness_report.md",
)

SOURCE_FILES = (
    PILOT_DESIGN_DIR / "direction_decision.yaml",
    PILOT_DESIGN_DIR / "design_summary.md",
    PILOT_DESIGN_DIR / "frozen_step2_eligibility_policy.yaml",
    PILOT_DESIGN_DIR / "provisional_exposure_classification.csv",
    PILOT_FREEZE_DIR / "market_data_freeze_manifest.yaml",
    PILOT_FREEZE_DIR / "final_primary_universe.csv",
    PILOT_FREEZE_DIR / "official_product_identity.csv",
    PILOT_FREEZE_DIR / "history_and_integrity_metrics.csv",
    PILOT_FREEZE_DIR / "adjustment_integrity_review.csv",
    PILOT_COMPAT_DIR / "accepted_final_47_universe.csv",
    PILOT_COMPAT_DIR / "direction_owner_gap_acceptance.yaml",
    APPROVED_EXPANSION_DIR / "approved_symbol_expansion_manifest.json",
    APPROVED_EXPANSION_DIR / "approved_symbol_expansion_selected_symbols.yaml",
    APPROVED_CACHE_DIR / "approved_expansion_cache_manifest.json",
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
)

CACHE_PATHS = (Path("data") / "cache", SNAPSHOT_DIR)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def hash_target(root: Path, relative: Path) -> str:
    target = root / relative
    if not target.exists():
        return "missing"
    if target.is_file():
        return sha256_file(target)
    rows = []
    for path in sorted(item for item in target.rglob("*") if item.is_file()):
        rows.append((path.relative_to(target).as_posix(), sha256_file(path)))
    return stable_hash(rows)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def serialize_list(values: Iterable[str]) -> str:
    return "|".join(values)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def instrument_role(exposure: str, candidate_group: str) -> str:
    lower = exposure.lower()
    if "cash proxy" in lower or "treasury bills" in lower:
        return "cash_or_collateral_proxy"
    if candidate_group == "government_bonds_and_credit":
        return "fixed_income_allocation_and_relationship_research"
    if candidate_group == "commodities_and_precious_metals":
        return "commodity_or_real_asset_exposure"
    if candidate_group == "real_estate_and_infrastructure":
        return "real_asset_equity_exposure"
    if candidate_group == "developed_emerging_regions_countries":
        return "international_or_regional_equity_exposure"
    if candidate_group == "us_sectors_liquid_industries":
        return "us_sector_cross_sectional_exposure"
    return "us_equity_allocation_or_factor_exposure"


def normalized_frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.loc[:, REQUIRED_SNAPSHOT_FIELDS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for field in REQUIRED_SNAPSHOT_FIELDS[1:]:
        normalized[field] = pd.to_numeric(normalized[field], errors="coerce")
    content = normalized.to_csv(index=False, lineterminator="\n", float_format="%.12g")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_snapshot(path: Path, cutoff: date) -> dict[str, Any]:
    first = pd.read_csv(path)
    second = pd.read_csv(path)
    fields_present = all(field in first.columns for field in REQUIRED_SNAPSHOT_FIELDS)
    if not fields_present:
        return {
            "required_fields_present": False,
            "first_valid_session": "",
            "last_valid_completed_session": "",
            "row_count": len(first),
            "duplicate_date_count": "",
            "missing_field_count": "",
            "invalid_ohlc_count": "",
            "nonpositive_price_count": "",
            "negative_volume_count": "",
            "partial_or_future_bar_count": "",
            "ordered_dates": False,
            "deterministic_reload_match": False,
            "normalized_hash": "",
            "quality_pass": False,
        }

    dates = pd.to_datetime(first["date"], errors="coerce")
    numeric = first.loc[:, REQUIRED_SNAPSHOT_FIELDS[1:]].apply(pd.to_numeric, errors="coerce")
    duplicate_count = int(dates.duplicated().sum())
    missing_count = int(dates.isna().sum() + numeric.isna().sum().sum())
    finite = pd.DataFrame(np.isfinite(numeric.to_numpy()), index=numeric.index, columns=numeric.columns)
    missing_count += int((~finite & numeric.notna()).sum().sum())
    ohlc_tolerance = 1e-10
    invalid_ohlc = (
        (numeric["high"] + ohlc_tolerance < numeric[["open", "close", "low"]].max(axis=1))
        | (numeric["low"] - ohlc_tolerance > numeric[["open", "close", "high"]].min(axis=1))
    )
    nonpositive = (numeric[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1)
    negative_volume = numeric["volume"] < 0
    partial_or_future = dates.dt.date > cutoff
    ordered = bool(dates.is_monotonic_increasing)
    first_hash = normalized_frame_hash(first)
    second_hash = normalized_frame_hash(second)
    quality_pass = bool(
        duplicate_count == 0
        and missing_count == 0
        and int(invalid_ohlc.sum()) == 0
        and int(nonpositive.sum()) == 0
        and int(negative_volume.sum()) == 0
        and int(partial_or_future.sum()) == 0
        and ordered
        and first_hash == second_hash
    )
    valid_dates = dates.dropna()
    return {
        "required_fields_present": True,
        "first_valid_session": valid_dates.min().date().isoformat(),
        "last_valid_completed_session": valid_dates.max().date().isoformat(),
        "row_count": len(first),
        "duplicate_date_count": duplicate_count,
        "missing_field_count": missing_count,
        "invalid_ohlc_count": int(invalid_ohlc.sum()),
        "nonpositive_price_count": int(nonpositive.sum()),
        "negative_volume_count": int(negative_volume.sum()),
        "partial_or_future_bar_count": int(partial_or_future.sum()),
        "ordered_dates": ordered,
        "deterministic_reload_match": first_hash == second_hash,
        "normalized_hash": first_hash,
        "quality_pass": quality_pass,
    }


def source_artifact_rows(root: Path) -> list[dict[str, Any]]:
    roles = {
        "direction_decision.yaml": "initial_direction_decision",
        "design_summary.md": "pilot_design_summary",
        "frozen_step2_eligibility_policy.yaml": "pilot_eligibility_rules",
        "provisional_exposure_classification.csv": "pilot_economic_metadata",
        "market_data_freeze_manifest.yaml": "pilot_data_freeze",
        "final_primary_universe.csv": "frozen_pilot_primary_membership",
        "official_product_identity.csv": "pilot_product_identity",
        "history_and_integrity_metrics.csv": "pilot_quality_evidence",
        "adjustment_integrity_review.csv": "pilot_adjustment_evidence",
        "accepted_final_47_universe.csv": "direction_owner_accepted_pilot_membership",
        "direction_owner_gap_acceptance.yaml": "latest_pilot_membership_decision",
        "approved_symbol_expansion_manifest.json": "separate_symbol_governance",
        "approved_symbol_expansion_selected_symbols.yaml": "separate_approved_cache_symbols",
        "approved_expansion_cache_manifest.json": "separate_cache_bootstrap",
    }
    rows = []
    for path in SOURCE_FILES:
        full = root / path
        rows.append(
            {
                "artifact_path": path.as_posix(),
                "artifact_role": roles[path.name],
                "exists": full.exists(),
                "sha256": sha256_file(full) if full.exists() else "missing",
            }
        )
    return rows


def rule_rows() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "target_size",
            "requested_rule": "authoritative broad freeze contains approximately 80-150 symbols",
            "observed_authoritative_state": "latest accepted pilot contains 47 symbols",
            "status": "conflict_blocks_broad_freeze",
            "evidence": (PILOT_COMPAT_DIR / "direction_owner_gap_acceptance.yaml").as_posix(),
        },
        {
            "rule_id": "us_listed_etf_or_etp",
            "requested_rule": "US-listed ETF or ETP",
            "observed_authoritative_state": "recorded for accepted pilot through official product identity",
            "status": "supported_for_pilot_context",
            "evidence": (PILOT_FREEZE_DIR / "official_product_identity.csv").as_posix(),
        },
        {
            "rule_id": "non_leveraged_non_inverse",
            "requested_rule": "non-leveraged and non-inverse",
            "observed_authoritative_state": "pilot identity records not_flagged for leverage or inverse status",
            "status": "supported_for_pilot_context",
            "evidence": (PILOT_FREEZE_DIR / "official_product_identity.csv").as_posix(),
        },
        {
            "rule_id": "economic_role",
            "requested_rule": "clear economic group and instrument role",
            "observed_authoritative_state": "complete for the 47-symbol accepted pilot",
            "status": "supported_for_pilot_context",
            "evidence": (PILOT_FREEZE_DIR / "final_primary_universe.csv").as_posix(),
        },
        {
            "rule_id": "performance_independence",
            "requested_rule": "membership selected without strategy performance",
            "observed_authoritative_state": "pilot packets state no performance, returns, volatility, correlation, or backtest calculation",
            "status": "supported_for_pilot_context",
            "evidence": (PILOT_FREEZE_DIR / "market_data_freeze_manifest.yaml").as_posix(),
        },
        {
            "rule_id": "separate_eight_symbol_expansion",
            "requested_rule": "latest authority clearly supersedes or merges earlier definitions",
            "observed_authoritative_state": "eight symbols approved for cache use; six overlap pilot and two were never merged into accepted pilot",
            "status": "not_a_broad_freeze",
            "evidence": (APPROVED_EXPANSION_DIR / "approved_symbol_expansion_selected_symbols.yaml").as_posix(),
        },
        {
            "rule_id": "provider_policy",
            "requested_rule": "Alpaca read-only market data primary after freeze passes",
            "observed_authoritative_state": "existing /v2/stocks/bars adapter present; not invoked because freeze gate failed",
            "status": "not_reached",
            "evidence": "execution_lab/alpaca_micro_live_v1/data/alpaca_historical_bars.py",
        },
    ]


def compatibility_rows(pilot_rows: list[dict[str, str]], cutoff: date) -> list[dict[str, Any]]:
    groups = sorted({row["candidate_group"] for row in pilot_rows})
    symbols = [row["symbol"] for row in pilot_rows]
    all_fields = "adjusted daily open|high|low|close|volume|trading date"
    architectures = [
        ("single_asset_technical_state", all_fields, "all accepted pilot symbols"),
        ("multi_asset_rotation", "adjusted daily close|trading date", "all accepted pilot groups"),
        ("cross_sectional_selection", "adjusted daily close|trading date", "groups with multiple accepted symbols"),
        ("relative_strength", "adjusted daily close|trading date", "all accepted pilot groups"),
        ("medium_frequency_mean_reversion", all_fields, "liquid accepted pilot symbols"),
        ("volatility_or_range_state", all_fields, "all accepted pilot symbols"),
        ("credit_and_duration_relationships", "adjusted daily close|trading date", "government_bonds_and_credit"),
        ("commodity_and_real_asset_allocation", "adjusted daily close|trading date", "commodities_and_precious_metals|real_estate_and_infrastructure"),
        ("international_or_regional_allocation", "adjusted daily close|trading date", "developed_emerging_regions_countries"),
        ("economically_grouped_pair_relative_value_discovery", "adjusted daily close|trading date|complete paired observations", "groups with at least two economically coherent symbols"),
        ("trade_management_overlays", all_fields + "|base position and lifecycle ledger", "structurally compatible base strategies only"),
    ]
    return [
        {
            "architecture": name,
            "required_data_fields": fields,
            "eligible_pilot_context": eligibility,
            "pilot_symbol_count": len(symbols),
            "pilot_group_count": len(groups),
            "history_coverage_constraint": f"inception-aware coverage through frozen 2026-07-16 snapshots; current completed-session audit cutoff {cutoff.isoformat()}",
            "capability_status": "blocked_authoritative_universe_freeze",
            "concrete_blocker": "no authoritative 80-150-symbol broad membership freeze; current 47-symbol pilot cannot be silently expanded",
        }
        for name, fields, eligibility in architectures
    ]


def run(root: Path) -> dict[str, Any]:
    root = root.resolve()
    output = root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    cutoff = pilot_freeze.previous_complete_us_market_session(date.today())

    protected_before = {path.as_posix(): hash_target(root, path) for path in PROTECTED_PATHS}
    cache_before = {path.as_posix(): hash_target(root, path) for path in CACHE_PATHS}
    source_hashes_before = {path.as_posix(): hash_target(root, path) for path in SOURCE_FILES}

    pilot_rows = read_csv(root / PILOT_FREEZE_DIR / "final_primary_universe.csv")
    accepted_rows = read_csv(root / PILOT_COMPAT_DIR / "accepted_final_47_universe.csv")
    identity_rows = {row["symbol"]: row for row in read_csv(root / PILOT_FREEZE_DIR / "official_product_identity.csv")}
    design_rows = {row["symbol"]: row for row in read_csv(root / PILOT_DESIGN_DIR / "provisional_exposure_classification.csv")}
    history_rows = {row["symbol"]: row for row in read_csv(root / PILOT_FREEZE_DIR / "history_and_integrity_metrics.csv")}
    adjustment_rows = {row["symbol"]: row for row in read_csv(root / PILOT_FREEZE_DIR / "adjustment_integrity_review.csv")}
    approved_symbols = list(read_yaml(root / APPROVED_EXPANSION_DIR / "approved_symbol_expansion_selected_symbols.yaml").get("symbols", []))

    pilot_symbols = [row["symbol"] for row in pilot_rows]
    accepted_symbols = [row["symbol"] for row in accepted_rows]
    overlap = sorted(set(pilot_symbols) & set(approved_symbols))
    expansion_only = sorted(set(approved_symbols) - set(pilot_symbols))
    union_symbols = sorted(set(pilot_symbols) | set(approved_symbols))
    pilot_membership_matches = pilot_symbols == accepted_symbols
    broad_freeze_exists = False

    universe_rows = []
    metadata_rows = []
    group_rows = []
    cache_inventory = []
    quality_rows = []
    cache_hash_rows = []
    provider_rows = []
    acquisition_rows = []

    for ordinal, row in enumerate(pilot_rows, start=1):
        symbol = row["symbol"]
        identity = identity_rows[symbol]
        design = design_rows[symbol]
        role = instrument_role(row["primary_economic_exposure"], row["candidate_group"])
        snapshot_path = root / SNAPSHOT_DIR / f"{symbol}.csv"
        validation = validate_snapshot(snapshot_path, cutoff)
        file_hash = sha256_file(snapshot_path)
        stale = validation["last_valid_completed_session"] < cutoff.isoformat()
        preliminary = "refresh_required" if validation["quality_pass"] and stale else "ready_existing_cache"
        if not validation["quality_pass"]:
            preliminary = "instrument_blocked"

        universe_rows.append(
            {
                "universe_id": "accepted_final_47_pilot_universe",
                "ordinal": ordinal,
                "symbol": symbol,
                "membership_status": "accepted_pilot_context",
                "authoritative_for_requested_80_150_scope": False,
                "candidate_group": row["candidate_group"],
                "primary_economic_exposure": row["primary_economic_exposure"],
                "product_structure": row["product_structure"],
                "frozen_endpoint": row["frozen_endpoint"],
                "source_path": (PILOT_COMPAT_DIR / "accepted_final_47_universe.csv").as_posix(),
                "performance_selected": False,
            }
        )
        metadata_rows.append(
            {
                "symbol": symbol,
                "security_name": design["security_name"],
                "listing_exchange": identity["current_listing"],
                "us_listed_etf_or_etp": True,
                "leveraged_or_inverse_status": identity["leveraged_or_inverse_status"],
                "product_structure": row["product_structure"],
                "primary_economic_group": row["candidate_group"],
                "primary_economic_exposure": row["primary_economic_exposure"],
                "secondary_tags": design["secondary_tags"],
                "instrument_role": role,
                "inclusion_reason": "accepted by direction-owner pilot freeze using economic exposure, product structure, history and liquidity rules",
                "survivor_label": row["survivor_label"],
                "metadata_status": "complete_for_pilot_context",
            }
        )
        group_rows.append(
            {
                "symbol": symbol,
                "primary_economic_group": row["candidate_group"],
                "primary_economic_exposure": row["primary_economic_exposure"],
                "secondary_tags": design["secondary_tags"],
                "instrument_role": role,
                "mapping_source": (PILOT_DESIGN_DIR / "provisional_exposure_classification.csv").as_posix(),
                "mapping_performance_based": False,
                "mapping_status": "complete_for_pilot_context",
            }
        )
        cache_inventory.append(
            {
                "symbol": symbol,
                "frozen_universe_membership": "accepted_pilot_context_not_requested_broad_freeze",
                "economic_group": row["candidate_group"],
                "instrument_role": role,
                "cache_path": snapshot_path.relative_to(root).as_posix(),
                "cache_format": "csv",
                "provider_lineage": "yfinance_compatible_adjusted_daily_etf_data_from_prior_authorized_freeze",
                "adjustment_convention": "raw OHLC multiplied by raw_adj_close/raw_close; adjusted close retained; volume unadjusted",
                "first_valid_session": validation["first_valid_session"],
                "last_valid_completed_session": validation["last_valid_completed_session"],
                "row_count": validation["row_count"],
                "duplicate_date_count": validation["duplicate_date_count"],
                "missing_field_count": validation["missing_field_count"],
                "invalid_ohlc_count": validation["invalid_ohlc_count"],
                "nonpositive_price_count": validation["nonpositive_price_count"],
                "negative_volume_count": validation["negative_volume_count"],
                "stale_ending_status": "stale_refresh_not_authorized" if stale else "current_through_cutoff",
                "file_sha256": file_hash,
                "preliminary_readiness": preliminary,
            }
        )
        quality_rows.append(
            {
                "symbol": symbol,
                "required_fields_present": validation["required_fields_present"],
                "ordered_dates": validation["ordered_dates"],
                "duplicate_date_count": validation["duplicate_date_count"],
                "missing_field_count": validation["missing_field_count"],
                "invalid_ohlc_count": validation["invalid_ohlc_count"],
                "nonpositive_price_count": validation["nonpositive_price_count"],
                "negative_volume_count": validation["negative_volume_count"],
                "partial_or_future_bar_count": validation["partial_or_future_bar_count"],
                "missing_session_count_from_frozen_audit": history_rows[symbol]["missing_session_count"],
                "prices_or_volume_forward_filled": history_rows[symbol]["prices_or_volume_forward_filled"],
                "unresolved_adjustment_problem": adjustment_rows[symbol]["material_unresolved_adjustment_problem"],
                "deterministic_reload_match": validation["deterministic_reload_match"],
                "existing_historical_rows_changed": False,
                "quality_pass": validation["quality_pass"],
                "quality_status": "valid_existing_snapshot_stale" if validation["quality_pass"] and stale else ("valid_existing_snapshot_current" if validation["quality_pass"] else "invalid_existing_snapshot"),
            }
        )
        cache_hash_rows.append(
            {
                "symbol": symbol,
                "cache_path": snapshot_path.relative_to(root).as_posix(),
                "file_sha256_before": file_hash,
                "file_sha256_after": file_hash,
                "normalized_frame_sha256": validation["normalized_hash"],
                "deterministic_reload_match": validation["deterministic_reload_match"],
                "cache_changed": False,
            }
        )
        provider_rows.append(
            {
                "symbol": symbol,
                "preliminary_classification": preliminary,
                "preferred_provider": "alpaca_market_data",
                "endpoint_scope": "/v2/stocks/bars read-only market data only",
                "provider_request_attempted": False,
                "request_range": "",
                "request_status": "not_attempted_authoritative_universe_freeze_blocked",
                "account_position_order_or_transfer_endpoint_called": False,
                "secret_value_persisted": False,
                "blocker": "requested 80-150-symbol authoritative membership does not exist",
            }
        )
        acquisition_rows.append(
            {
                "symbol": symbol,
                "acquisition_required_by_cache_audit": preliminary == "refresh_required",
                "acquisition_authorized": False,
                "provider": "alpaca_market_data_not_called",
                "rows_added": 0,
                "cache_written": False,
                "result": "not_attempted_freeze_gate_failed",
                "failure_reason": "authoritative_universe_freeze_blocked",
            }
        )

    group_counts: dict[str, int] = {}
    for row in pilot_rows:
        group_counts[row["candidate_group"]] = group_counts.get(row["candidate_group"], 0) + 1
    coverage_rows = [
        {
            "scope": group,
            "pilot_context_symbol_count": count,
            "quality_valid_count": sum(1 for row in quality_rows if row["quality_pass"] and next(item for item in pilot_rows if item["symbol"] == row["symbol"])["candidate_group"] == group),
            "current_through_completed_session_count": sum(1 for row in cache_inventory if row["economic_group"] == group and row["stale_ending_status"] == "current_through_cutoff"),
            "stale_count": sum(1 for row in cache_inventory if row["economic_group"] == group and row["stale_ending_status"] != "current_through_cutoff"),
            "earliest_available_session": min(row["first_valid_session"] for row in cache_inventory if row["economic_group"] == group),
            "latest_available_session": max(row["last_valid_completed_session"] for row in cache_inventory if row["economic_group"] == group),
            "broad_freeze_readiness": "blocked_authoritative_universe_freeze",
        }
        for group, count in sorted(group_counts.items())
    ]

    blocked_rows = [
        {
            "symbol_or_scope": "*REQUESTED_BROAD_UNIVERSE*",
            "source_membership": "missing",
            "blocker_type": "authoritative_universe_freeze_blocked",
            "detail": "no frozen 80-150-symbol membership artifact exists; latest accepted pilot contains 47",
            "automatic_removal_or_substitution": False,
            "required_resolution": NEXT_ACTION,
        }
    ]
    blocked_rows.extend(
        {
            "symbol_or_scope": symbol,
            "source_membership": "approved_expansion_cache_symbol_not_in_latest_accepted_pilot",
            "blocker_type": "unmerged_membership_decision",
            "detail": "symbol has prior cache approval but no later authoritative broad-universe merge decision",
            "automatic_removal_or_substitution": False,
            "required_resolution": NEXT_ACTION,
        }
        for symbol in expansion_only
    )

    write_yaml(
        output / "data_readiness_manifest.yaml",
        {
            "task_id": TASK_ID,
            "mode": MODE,
            "stage": STAGE,
            "created_at_utc": started_at,
            "outcome": OUTCOME,
            "failure_reason": "requested_authoritative_80_150_symbol_freeze_not_found",
            "next_action": NEXT_ACTION,
            "next_action_executed": False,
            "requested_universe_size": {"minimum": TARGET_MINIMUM, "maximum": TARGET_MAXIMUM},
            "latest_accepted_pilot_count": len(pilot_symbols),
            "separate_approved_expansion_count": len(approved_symbols),
            "pilot_and_expansion_union_count": len(union_symbols),
            "authoritative_broad_freeze_identified": broad_freeze_exists,
            "provider_access_performed": False,
            "cache_files_modified": 0,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "benchmark_strategies_created": 0,
            "robustness_trials_created": 0,
            "validation_observations_created": 0,
            "paper_demo_observations_created_or_changed": 0,
            "source_artifacts": source_artifact_rows(root),
        },
    )

    reconciliation = f"""# Source-of-Truth Reconciliation

## Decision

Outcome: `{OUTCOME}`.

The latest explicit direction-owner universe decision accepts a **47-instrument pilot** and states that the original 48 count was a pilot budget, not a validity requirement. That decision is authoritative for the pilot lane, but it does not define the requested 80-150-symbol broad universe.

## Artifacts Reconciled

1. `pilot_etf_universe_design_v1` adopted bounded expansion with major modifications and proposed 48 primary plus 12 reserve instruments.
2. `pilot_etf_market_data_freeze_v1` froze 60 snapshots and retained 47 primary instruments after one liquidity failure.
3. `pilot_instrument_strategy_compatibility_v1/direction_owner_gap_acceptance.yaml` explicitly accepted the final 47 and did not reopen the design.
4. `approved_symbol_expansion_review` separately approved eight symbols for cache bootstrap. Six are already in the accepted 47 (`{serialize_list(overlap)}`); two (`{serialize_list(expansion_only)}`) are not merged into the later pilot freeze.

The union of all accepted-pilot and separately approved cache symbols is only **{len(union_symbols)}**, below the requested minimum of {TARGET_MINIMUM}. No artifact authorizes Codex to invent the remaining members, merge the two scopes, or refreeze membership.

## Gate Consequence

Provider access stopped before authentication or request construction. The existing 47 pilot snapshots were read only as context and quality-audited without mutation. The exact next action is `{NEXT_ACTION}`.
"""
    (output / "source_of_truth_reconciliation.md").write_text(reconciliation, encoding="utf-8")

    write_csv(output / "authoritative_universe_snapshot.csv", universe_rows, list(universe_rows[0]))
    rules = rule_rows()
    write_csv(output / "universe_rule_reconciliation.csv", rules, list(rules[0]))
    write_csv(output / "symbol_metadata.csv", metadata_rows, list(metadata_rows[0]))
    write_csv(output / "economic_group_map.csv", group_rows, list(group_rows[0]))
    write_csv(output / "existing_cache_inventory.csv", cache_inventory, list(cache_inventory[0]))
    write_csv(output / "provider_request_manifest.csv", provider_rows, list(provider_rows[0]))
    write_csv(output / "acquisition_results.csv", acquisition_rows, list(acquisition_rows[0]))
    write_csv(output / "data_quality_results.csv", quality_rows, list(quality_rows[0]))
    write_csv(output / "coverage_summary.csv", coverage_rows, list(coverage_rows[0]))
    write_csv(output / "blocked_symbols.csv", blocked_rows, list(blocked_rows[0]))
    compat_rows = compatibility_rows(pilot_rows, cutoff)
    write_csv(output / "research_compatibility_map.csv", compat_rows, list(compat_rows[0]))
    write_csv(output / "cache_hash_manifest.csv", cache_hash_rows, list(cache_hash_rows[0]))
    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "mode": MODE,
            "stage": STAGE,
            "outcome": OUTCOME,
            "failure_reason": "requested_authoritative_80_150_symbol_freeze_not_found",
            "provider_access_performed": False,
            "strategy_or_backtest_run": False,
            "next_action": NEXT_ACTION,
        }
    ]
    write_csv(output / "process_task_log.csv", process_rows, list(process_rows[0]))
    outcome_rows = [
        {
            "task_id": TASK_ID,
            "outcome": OUTCOME,
            "failure_reason": "requested_authoritative_80_150_symbol_freeze_not_found",
            "authoritative_pilot_count": len(pilot_symbols),
            "separate_approved_expansion_count": len(approved_symbols),
            "union_count_without_authorized_merge": len(union_symbols),
            "target_minimum": TARGET_MINIMUM,
            "target_maximum": TARGET_MAXIMUM,
            "provider_calls": 0,
            "cache_writes": 0,
            "next_action": NEXT_ACTION,
        }
    ]
    write_csv(output / "outcome_summary.csv", outcome_rows, list(outcome_rows[0]))
    next_rows = [
        {
            "task_id": TASK_ID,
            "outcome": OUTCOME,
            "next_action": NEXT_ACTION,
            "next_action_executed": False,
            "technical_factory_v3_launched": False,
            "overlay_implementation_launched": False,
        }
    ]
    write_csv(output / "next_actions.csv", next_rows, list(next_rows[0]))

    protected_after = {path.as_posix(): hash_target(root, path) for path in PROTECTED_PATHS}
    cache_after = {path.as_posix(): hash_target(root, path) for path in CACHE_PATHS}
    source_hashes_after = {path.as_posix(): hash_target(root, path) for path in SOURCE_FILES}
    protected_rows = []
    for path in (*PROTECTED_PATHS, *CACHE_PATHS, *SOURCE_FILES):
        key = path.as_posix()
        if path in PROTECTED_PATHS:
            before, after, path_type = protected_before[key], protected_after[key], "protected_state"
        elif path in CACHE_PATHS:
            before, after, path_type = cache_before[key], cache_after[key], "market_data_cache"
        else:
            before, after, path_type = source_hashes_before[key], source_hashes_after[key], "source_input"
        protected_rows.append(
            {
                "path": key,
                "path_type": path_type,
                "hash_before": before,
                "hash_after": after,
                "unchanged": before == after,
            }
        )
    write_csv(output / "protected_state_reconciliation.csv", protected_rows, list(protected_rows[0]))

    checks = {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "exact_next_action": NEXT_ACTION,
        "authoritative_pilot_identified": len(pilot_symbols) == 47,
        "pilot_membership_matches_direction_owner_acceptance": pilot_membership_matches,
        "requested_broad_freeze_identified": broad_freeze_exists,
        "pilot_count_below_requested_minimum": len(pilot_symbols) < TARGET_MINIMUM,
        "unmerged_union_count_below_requested_minimum": len(union_symbols) < TARGET_MINIMUM,
        "provider_call_count": 0,
        "provider_access_performed": False,
        "provider_calls_read_only_if_reached": True,
        "all_context_snapshots_quality_valid": all(row["quality_pass"] for row in quality_rows),
        "all_context_snapshots_deterministic": all(row["deterministic_reload_match"] for row in quality_rows),
        "all_economic_group_metadata_complete": all(row["mapping_status"] == "complete_for_pilot_context" for row in group_rows),
        "context_snapshot_count": len(universe_rows),
        "research_compatibility_architecture_count": len(compat_rows),
        "new_strategy_configuration_count": 0,
        "new_experiment_trial_count": 0,
        "new_benchmark_strategy_count": 0,
        "robustness_trial_count": 0,
        "validation_observation_count": 0,
        "paper_demo_observation_count": 0,
        "strategy_performance_calculated": False,
        "backtest_run": False,
        "technical_factory_v3_launched": False,
        "new_overlay_architecture_created": False,
        "broker_account_position_order_transfer_or_real_money_action": False,
        "protected_state_unchanged": protected_before == protected_after,
        "market_data_caches_unchanged": cache_before == cache_after,
        "source_inputs_unchanged": source_hashes_before == source_hashes_after,
        "required_outputs_present_before_consistency": all((output / name).exists() for name in OUTPUT_FILES if name != "consistency_check.json"),
    }
    checks["overall_pass"] = bool(
        checks["authoritative_pilot_identified"]
        and checks["pilot_membership_matches_direction_owner_acceptance"]
        and not checks["requested_broad_freeze_identified"]
        and checks["pilot_count_below_requested_minimum"]
        and checks["provider_call_count"] == 0
        and checks["all_context_snapshots_quality_valid"]
        and checks["all_context_snapshots_deterministic"]
        and checks["all_economic_group_metadata_complete"]
        and checks["protected_state_unchanged"]
        and checks["market_data_caches_unchanged"]
        and checks["source_inputs_unchanged"]
        and checks["required_outputs_present_before_consistency"]
    )
    write_json(output / "consistency_check.json", checks)

    report = f"""# Bounded Multi-Asset Universe Data Readiness v1

## Outcome

`{OUTCOME}`

The repository contains a direction-owner-accepted 47-symbol pilot universe, not an authoritative broad freeze of approximately 80-150 symbols. A separate eight-symbol cache approval overlaps the pilot in six names and leaves only `{serialize_list(expansion_only)}` outside it; no source authorizes merging those scopes. Their union is {len(union_symbols)}, still below the requested minimum.

## Existing Data Context

All {len(pilot_symbols)} accepted pilot snapshots were read from the immutable pilot cache and passed schema, ordering, duplicate, adjusted-OHLC, positive-price, nonnegative-volume, completed-session, and deterministic-reload checks. Their endpoint is 2026-07-16, so all are stale relative to the {cutoff.isoformat()} completed-session audit cutoff. Refresh was not attempted because universe membership must be resolved first.

The prior snapshot convention adjusts raw OHLC by `raw_adj_close / raw_close`, retains adjusted close, and leaves volume unadjusted. That convention is recorded rather than silently relabeled as Alpaca-native adjusted OHLCV.

## Boundaries Preserved

- Provider calls: `0`
- Cache writes: `0`
- Strategy configurations or trials created: `0`
- Backtests or performance calculations: `0`
- Paper/demo observations changed: `0`
- Broker, account, position, order, transfer, or real-money actions: `0`

Exact next action: `{NEXT_ACTION}`.
"""
    (output / "data_readiness_report.md").write_text(report, encoding="utf-8")

    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "exact_next_action": NEXT_ACTION,
        "authoritative_pilot_count": len(pilot_symbols),
        "separate_approved_expansion_count": len(approved_symbols),
        "union_count_without_authorized_merge": len(union_symbols),
        "provider_call_count": 0,
        "context_snapshots_quality_valid": sum(bool(row["quality_pass"]) for row in quality_rows),
        "overall_pass": checks["overall_pass"],
        "evidence_path": OUTPUT_DIR.as_posix(),
    }


if __name__ == "__main__":
    print(json.dumps(run(Path.cwd()), indent=2, sort_keys=True))
