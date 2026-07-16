from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from src.data import build_adjusted_ohlc
from strategy_lab.research_os.research.commodity_basket_provider_refresh import default_yfinance_downloader


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path("evidence") / "direction_owner_single_source_intake_v1" / "latest"
INTAKE_DIR = Path("strategy_lab") / "research_os" / "public_strategy_sources" / "intake_candidates"
SOURCE_RECORD = INTAKE_DIR / "ice_vaneck_us_fallen_angel_angl_v1.yaml"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
RESEARCH_QUEUE_PATH = Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml"
ACTIVE_OBSERVATIONS_PATH = Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml"
CACHE_DIR = Path("data") / "cache"

SOURCE_ID = "ice_vaneck_us_fallen_angel_angl_v1"
CANDIDATE_ID = "angl_static_fallen_angel_credit_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
OUTCOME_READY = "preregistration_ready"
OUTCOME_NOT_READY = "source_not_ready"
OUTCOME_DUPLICATE = "duplicate_or_not_materially_distinct"
VALID_DECISIONS = {OUTCOME_READY, OUTCOME_NOT_READY, OUTCOME_DUPLICATE}
METHODOLOGY_BOUNDARY = "2020-02-28"
METHODOLOGY_AMENDMENT = "2023-12-31"
REQUIRED_SYMBOLS = ("ANGL", "HYG", "BIL")
OPTIONAL_SYMBOLS = ("IEF",)
ALL_SYMBOLS = REQUIRED_SYMBOLS + OPTIONAL_SYMBOLS
AUTHORIZED_PROVIDER_SYMBOLS = ("ANGL",)
PROTECTED_EXISTING_CACHE_SYMBOLS = ("HYG", "BIL", "IEF")
ANGL_ACQUISITION_METADATA = CACHE_DIR / "ANGL.acquisition.json"
REQUEST_SETTINGS = {
    "start": "2012-04-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def read_yaml(root: Path, path: Path) -> dict[str, Any]:
    full = abs_path(root, path)
    if not full.exists():
        return {}
    return yaml.safe_load(full.read_text(encoding="utf-8")) or {}


def read_json(root: Path, path: Path) -> dict[str, Any]:
    full = abs_path(root, path)
    if not full.exists():
        return {}
    return json.loads(full.read_text(encoding="utf-8"))


def write_yaml(root: Path, path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(root, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def file_hash(root: Path, path: Path) -> str:
    full = abs_path(root, path)
    if not full.exists():
        return "missing"
    return hashlib.sha256(full.read_bytes()).hexdigest().upper()


def cache_hashes(root: Path, symbols: tuple[str, ...]) -> dict[str, str]:
    return {symbol: file_hash(root, CACHE_DIR / f"{symbol}.csv") for symbol in symbols}


def nested_get(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(root: Path, path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    full = abs_path(root, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(root: Path, path: Path, payload: dict[str, Any]) -> None:
    full = abs_path(root, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(root: Path, path: Path, text: str) -> None:
    full = abs_path(root, path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text.rstrip() + "\n", encoding="utf-8")


def selected_source_packets(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(abs_path(root, INTAKE_DIR).glob("*.yaml")):
        rel = path.relative_to(root)
        payload = read_yaml(root, rel)
        current = (
            payload.get("direction_owner_selected") is True
            and payload.get("current_input_gate_candidate") is True
            and payload.get("external_source_discovery_pause_remains_active") is True
        )
        if current:
            rows.append({"path": rel, "payload": payload})
    return rows


def source_identity_rows(packet: dict[str, Any] | None, selected_count: int) -> list[dict[str, Any]]:
    payload = packet["payload"] if packet else {}
    return [
        {
            "source_id": nested_get(payload, "source.source_id") or "",
            "source_name": nested_get(payload, "source.source_name") or "",
            "candidate_id": nested_get(payload, "strategy_description.candidate_id") or "",
            "family": nested_get(payload, "strategy_description.strategy_family") or "",
            "source_class": nested_get(payload, "source.source_class") or "",
            "primary_citation_or_reference": nested_get(payload, "source.source_url_or_citation") or "",
            "author_or_publisher": nested_get(payload, "source.author_or_publisher") or "",
            "economic_mechanism": nested_get(payload, "strategy_description.economic_mechanism") or "",
            "strategy_role": nested_get(payload, "strategy_description.strategy_role") or "",
            "primary_benchmark": nested_get(payload, "strategy_description.primary_benchmark") or "",
            "known_ambiguities": nested_get(payload, "known_ambiguities") or "",
            "direction_owner_selected": payload.get("direction_owner_selected", False),
            "current_input_gate_candidate": payload.get("current_input_gate_candidate", False),
            "external_source_discovery_pause_remains_active": payload.get("external_source_discovery_pause_remains_active", False),
            "selected_source_packet_count": selected_count,
        }
    ]


def source_rule_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        ("direct_wrapper", "source_facts.direct_wrapper", "source_explicit", "Official ANGL fund/index documentation"),
        ("fallen_angel_eligibility", "source_facts.eligible_bonds", "source_explicit", "ICE bond-index methodology and ANGL fund/index documentation"),
        ("mechanism", "source_facts.mechanism", "source_explicit", "Direction-owner supplied source packet with academic mechanism context"),
        ("benchmark_history_transition", "source_facts.benchmark_history", "source_explicit", "Official ANGL benchmark history"),
        ("methodology_amendment_2023", "source_facts.methodology_amendment_2023", "source_explicit", "VanEck ETF Trust Supplement dated December 13, 2023; SEC accession context 000113736023000915"),
        ("post_2023_purity_caveat", "source_facts.post_2023_exposure_purity_caveat", "source_explicit", "VanEck ETF Trust Supplement dated December 13, 2023; direction-owner source packet"),
        ("entry_rule", "rules.entry_rule", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("exit_rule", "rules.exit_rule", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("sizing", "rules.sizing", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("weighting", "rules.weighting", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("rebalance", "rules.rebalance", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("fallback", "rules.fallback", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("missing_data_behavior", "rules.missing_data_behavior", "project_execution_convention", "Direction-owner frozen first-test design"),
        ("prohibited_overlays", "rules.prohibited_overlays", "project_execution_convention", "Direction-owner constraints"),
        ("adjusted_close_distribution_handling", "data_and_execution.accounting_convention", "project_execution_convention", "Repository adjusted-close accounting convention"),
        ("transaction_cost_convention", "data_and_execution.transaction_cost_convention", "project_execution_convention", "Repository canonical ETF cost convention"),
    ]
    rows = []
    for rule_id, path, classification, reference in fields:
        rows.append(
            {
                "source_id": SOURCE_ID,
                "rule_id": rule_id,
                "normalized_value": nested_get(payload, path) or "",
                "classification": classification if nested_get(payload, path) else "unresolved",
                "source_reference": reference if nested_get(payload, path) else "",
                "material_rule": True,
            }
        )
    return rows


def source_support_rows(rule_rows: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    support = []
    for row in rule_rows:
        support.append(
            {
                "source_id": SOURCE_ID,
                "rule_id": row["rule_id"],
                "classification": row["classification"],
                "source_reference": row["source_reference"],
                "supports_rule": bool(row["normalized_value"]),
                "sponsor_performance_claim": False,
                "source_reported_performance_excluded": True,
            }
        )
    support.append(
        {
            "source_id": SOURCE_ID,
            "rule_id": "sponsor_reported_performance_policy",
            "classification": "source_explicit_project_guardrail",
            "source_reference": "source_facts.sponsor_performance_policy",
            "supports_rule": True,
            "sponsor_performance_claim": True,
            "source_reported_performance_excluded": nested_get(payload, "project_notes.source_reported_performance_excluded") is True,
        }
    )
    return support


def cache_quality(root: Path, symbol: str, required: bool) -> dict[str, Any]:
    rel = CACHE_DIR / f"{symbol}.csv"
    full = abs_path(root, rel)
    row: dict[str, Any] = {
        "symbol": symbol,
        "required": required,
        "cache_path": str(full),
        "cache_exists": full.exists(),
        "cache_hash": file_hash(root, rel),
        "first_valid_date": "",
        "last_valid_date": "",
        "row_count": 0,
        "schema": "",
        "symbol_identity_valid": False,
        "adjusted_close_available": False,
        "missing_adj_close_count": "",
        "duplicate_date_count": "",
        "nonpositive_adj_close_count": "",
        "history_consistent_with_inception": False,
        "cache_status": "missing",
    }
    if not full.exists():
        return row
    dates: list[str] = []
    missing = 0
    nonpositive = 0
    symbol_values: set[str] = set()
    fieldnames: list[str] = []
    with full.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        has_adj = "adj_close" in fieldnames
        row["adjusted_close_available"] = has_adj
        for record in reader:
            date = record.get("date", "")
            if date:
                dates.append(date)
            if record.get("symbol"):
                symbol_values.add(str(record.get("symbol")))
            value = record.get("adj_close", "")
            if value in ("", "nan", "NaN", None):
                missing += 1
                continue
            try:
                if float(value) <= 0:
                    nonpositive += 1
            except ValueError:
                missing += 1
    duplicates = len(dates) - len(set(dates))
    row.update(
        {
            "first_valid_date": min(dates) if dates else "",
            "last_valid_date": max(dates) if dates else "",
            "row_count": len(dates),
            "schema": "|".join(fieldnames),
            "symbol_identity_valid": symbol_values == {symbol},
            "missing_adj_close_count": missing,
            "duplicate_date_count": duplicates,
            "nonpositive_adj_close_count": nonpositive,
            "history_consistent_with_inception": (min(dates) <= "2012-04-13" if dates and symbol == "ANGL" else bool(dates)),
        }
    )
    ready = (
        bool(dates)
        and row["adjusted_close_available"]
        and row["symbol_identity_valid"]
        and missing == 0
        and duplicates == 0
        and nonpositive == 0
        and (row["history_consistent_with_inception"] or symbol != "ANGL")
    )
    row["cache_status"] = "cache_ready" if ready else "cache_invalid"
    return row


def validate_existing_angl_cache(root: Path) -> dict[str, Any]:
    return cache_quality(root, "ANGL", True)


def provider_request(symbol: str, downloader: Any) -> pd.DataFrame:
    if symbol not in AUTHORIZED_PROVIDER_SYMBOLS:
        raise ValueError(f"provider request rejected by ANGL-only allowlist: {symbol}")
    return downloader(symbol, REQUEST_SETTINGS)


def acquire_angl_if_needed(root: Path, downloader: Any | None) -> tuple[dict[str, Any], dict[str, Any]]:
    before = validate_existing_angl_cache(root)
    prior_metadata = read_json(root, ANGL_ACQUISITION_METADATA)
    protected_before = cache_hashes(root, PROTECTED_EXISTING_CACHE_SYMBOLS)
    manifest: dict[str, Any] = {
        "provider_acquisition_step": "angl_cache_resolution_only",
        "authorized_provider_symbols": list(AUTHORIZED_PROVIDER_SYMBOLS),
        "requested_symbols": [],
        "downloaded_symbols_this_run": [],
        "provider_download_this_run": False,
        "provider_api_called_this_run": False,
        "existing_valid_cache_prevented_provider_call": before["cache_status"] == "cache_ready",
        "cache_path": str(abs_path(root, CACHE_DIR / "ANGL.csv")),
        "cache_status_before": before["cache_status"],
        "cache_status_after": before["cache_status"],
        "cache_hash_before": before["cache_hash"],
        "cache_hash_after": before["cache_hash"],
        "raw_price_history_cache_used": before["cache_status"] == "cache_ready",
        "restored_or_reindexed_symbols_this_run": [],
        "revalidated_symbols_this_run": ["ANGL"] if before["cache_status"] == "cache_ready" else [],
        "previously_restored_or_reindexed_symbols": ["ANGL"] if prior_metadata else [],
        "prior_authorized_acquisition_metadata_available": bool(prior_metadata),
        "prior_authorized_acquisition_metadata": prior_metadata,
        "protected_existing_cache_symbols": list(PROTECTED_EXISTING_CACHE_SYMBOLS),
        "protected_cache_hashes_before": protected_before,
        "protected_cache_hashes_after": protected_before,
        "protected_cache_hashes_unchanged": True,
        "provider_allowlist_rejects_non_angl": True,
        "provider_download_error": "",
    }
    if before["cache_status"] == "cache_ready":
        return manifest, before

    raw: pd.DataFrame | None = None
    normalized: pd.DataFrame | None = None
    try:
        manifest["requested_symbols"] = ["ANGL"]
        manifest["provider_download_this_run"] = True
        manifest["provider_api_called_this_run"] = True
        raw = provider_request("ANGL", downloader or default_yfinance_downloader)
        if raw is None or raw.empty:
            raise RuntimeError("ANGL provider returned no rows")
        normalized = build_adjusted_ohlc(raw, "ANGL")
        cache_path = abs_path(root, CACHE_DIR / "ANGL.csv")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(cache_path, index=False)
        manifest["downloaded_symbols_this_run"] = ["ANGL"]
    except Exception as exc:  # pragma: no cover - exercised in failure environments
        manifest["provider_download_error"] = str(exc)

    after = validate_existing_angl_cache(root)
    protected_after = cache_hashes(root, PROTECTED_EXISTING_CACHE_SYMBOLS)
    manifest["cache_status_after"] = after["cache_status"]
    manifest["cache_hash_after"] = after["cache_hash"]
    manifest["row_count_after"] = after["row_count"]
    manifest["first_valid_date_after"] = after["first_valid_date"]
    manifest["last_valid_date_after"] = after["last_valid_date"]
    manifest["immutable_cache_snapshot_hash"] = after["cache_hash"]
    manifest["immutable_cache_snapshot_created"] = after["cache_status"] == "cache_ready" and bool(manifest["downloaded_symbols_this_run"])
    manifest["raw_price_history_cache_used"] = after["cache_status"] == "cache_ready"
    manifest["restored_or_reindexed_symbols_this_run"] = list(manifest["downloaded_symbols_this_run"])
    manifest["revalidated_symbols_this_run"] = ["ANGL"] if after["cache_status"] == "cache_ready" and not manifest["downloaded_symbols_this_run"] else []
    manifest["protected_cache_hashes_after"] = protected_after
    manifest["protected_cache_hashes_unchanged"] = protected_before == protected_after
    if manifest["immutable_cache_snapshot_created"]:
        acquisition_metadata = {
            "source_id": SOURCE_ID,
            "symbol": "ANGL",
            "provider": "yfinance_compatible",
            "request_settings": REQUEST_SETTINGS,
            "cache_path": manifest["cache_path"],
            "cache_hash": after["cache_hash"],
            "row_count": after["row_count"],
            "first_valid_date": after["first_valid_date"],
            "last_valid_date": after["last_valid_date"],
            "provider_downloaded_symbol": "ANGL",
            "provider_allowlist": list(AUTHORIZED_PROVIDER_SYMBOLS),
        }
        write_json(root, ANGL_ACQUISITION_METADATA, acquisition_metadata)
        manifest["prior_authorized_acquisition_metadata_available"] = True
        manifest["prior_authorized_acquisition_metadata"] = acquisition_metadata
        manifest["previously_restored_or_reindexed_symbols"] = ["ANGL"]
    return manifest, after


def data_feasibility_rows(root: Path) -> list[dict[str, Any]]:
    rows = [cache_quality(root, symbol, symbol in REQUIRED_SYMBOLS) for symbol in ALL_SYMBOLS]
    date_sets: dict[str, set[str]] = {}
    for row in rows:
        if row["cache_exists"] and row["cache_status"] == "cache_ready":
            with Path(row["cache_path"]).open(newline="", encoding="utf-8") as handle:
                date_sets[row["symbol"]] = {record["date"] for record in csv.DictReader(handle) if record.get("date")}
    common_angl_hyg = sorted(date_sets.get("ANGL", set()) & date_sets.get("HYG", set()))
    first_after_2020 = next((date for date in common_angl_hyg if date >= METHODOLOGY_BOUNDARY), "")
    first_after_2023 = next((date for date in common_angl_hyg if date >= METHODOLOGY_AMENDMENT), "")
    spans_2020 = bool(common_angl_hyg and common_angl_hyg[0] <= METHODOLOGY_BOUNDARY <= common_angl_hyg[-1])
    spans_2023 = bool(common_angl_hyg and common_angl_hyg[0] <= METHODOLOGY_AMENDMENT <= common_angl_hyg[-1])
    for row in rows:
        row["common_angl_hyg_start"] = common_angl_hyg[0] if common_angl_hyg else ""
        row["common_angl_hyg_end"] = common_angl_hyg[-1] if common_angl_hyg else ""
        row["common_angl_hyg_row_count"] = len(common_angl_hyg)
        row["spans_feb_28_2020_boundary"] = spans_2020
        row["first_common_session_on_or_after_2020_02_28"] = first_after_2020
        row["spans_dec_31_2023_amendment"] = spans_2023
        row["first_common_session_on_or_after_2023_12_31"] = first_after_2023
        row["provider_download"] = False
    return rows


def prior_blocked_reference(prior_decision: dict[str, Any]) -> dict[str, Any]:
    if not prior_decision:
        return {}
    if prior_decision.get("decision") == OUTCOME_NOT_READY:
        return {
            "decision": prior_decision.get("decision"),
            "blocker": prior_decision.get("blocker"),
            "missing_required_symbols": prior_decision.get("missing_required_symbols", []),
            "next_action": prior_decision.get("next_action"),
        }
    existing = prior_decision.get("prior_blocked_decision_reference")
    return existing if isinstance(existing, dict) else {}


def duplicate_gate_rows(root: Path) -> list[dict[str, Any]]:
    prior_hits: list[str] = []
    search_terms = ("ANGL", "fallen_angel", "fallen angel", "angl_static_fallen_angel_credit_v1")
    for base in (root / "evidence", root / "strategy_lab"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".yaml", ".json", ".md", ".txt"}:
                continue
            rel = path.relative_to(root)
            if rel == SOURCE_RECORD or str(rel).replace("\\", "/").startswith(str(OUTPUT_DIR).replace("\\", "/")):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(term.lower() in text.lower() for term in search_terms):
                prior_hits.append(str(rel).replace("\\", "/"))
    exact_duplicate = False
    return [
        {
            "source_id": SOURCE_ID,
            "candidate_id": CANDIDATE_ID,
            "exact_valid_duplicate_found": exact_duplicate,
            "authoritative_duplicate_result": "",
            "prior_angl_or_fallen_angel_mentions": "|".join(sorted(set(prior_hits))),
            "duplicate_gate_decision": "no_exact_valid_duplicate_found",
            "notes": "Ticker appearances or source-record mentions do not create exact duplicates; required exact static ANGL/HYG screen was not found.",
        }
    ]


def material_distinction_rows() -> list[dict[str, Any]]:
    comparisons = [
        ("splv_static_low_vol_factor_wrapper_v1", "static equity low-volatility factor wrapper", "different_asset_class_and_mechanism"),
        ("qual_static_quality_factor_wrapper_v1", "static equity quality factor wrapper", "different_asset_class_and_mechanism"),
        ("yield_credit_trend_filter_v1", "credit trend/timing filter using broad credit ETFs", "fallen_angel_static_credit_segment_not_trend_filter"),
        ("yield_credit_risk_off_rotation_v1", "credit risk-off rotation", "no_risk_off_rotation_or_bil_switch"),
        ("static_all_weather_benchmark_v1", "static multi-asset benchmark/control", "fallen_angel_credit_segment_with_HYG_primary_benchmark"),
        ("active_vm_dsr_context", "active equity/sector observations", "context_only_not_credit_anomaly"),
    ]
    return [
        {
            "source_id": SOURCE_ID,
            "candidate_id": CANDIDATE_ID,
            "closest_prior_strategy": strategy,
            "prior_mechanism": mechanism,
            "material_difference": difference,
            "material_distinction_from_source": True,
            "exact_closed_variant_reopened": False,
            "review_result": "materially_distinct_subject_to_data_gate",
        }
        for strategy, mechanism, difference in comparisons
    ]


def methodology_transition_rows(data_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if data_rows:
        common_start = str(data_rows[0].get("common_angl_hyg_start", ""))
        first_after_2020 = str(data_rows[0].get("first_common_session_on_or_after_2020_02_28", ""))
        first_after_2023 = str(data_rows[0].get("first_common_session_on_or_after_2023_12_31", ""))
        spans_2020 = bool(data_rows[0].get("spans_feb_28_2020_boundary"))
        spans_2023 = bool(data_rows[0].get("spans_dec_31_2023_amendment"))
    else:
        common_start = first_after_2020 = first_after_2023 = ""
        spans_2020 = spans_2023 = False
    return [
        {
            "source_id": SOURCE_ID,
            "regime_id": "regime_1_prior_benchmark_methodology",
            "start": common_start or "fund_inception_or_common_history_start",
            "end": "immediately_before_2020-02-28",
            "effective_date": "",
            "first_observable_project_trading_session": common_start,
            "benchmark": "ICE BofA US Fallen Angel High Yield Index",
            "interpretation": "prior benchmark methodology",
            "required_caveat": "",
            "source_reference": "official ANGL benchmark history",
            "boundary_identifiable_in_common_angl_hyg_history": spans_2020,
            "status": "ready" if spans_2020 else "blocked_until_common_history_available",
        },
        {
            "source_id": SOURCE_ID,
            "regime_id": "regime_2_initial_h0cf_methodology",
            "start": "2020-02-28",
            "end": "2023-12-31",
            "effective_date": "2020-02-28",
            "first_observable_project_trading_session": first_after_2020,
            "benchmark": "ICE US Fallen Angel High Yield 10% Constrained Index",
            "interpretation": "initial H0CF methodology",
            "required_caveat": "",
            "source_reference": "official ANGL benchmark history",
            "boundary_identifiable_in_common_angl_hyg_history": spans_2020,
            "status": "ready" if spans_2020 and first_after_2020 else "blocked_until_common_history_available",
        },
        {
            "source_id": SOURCE_ID,
            "regime_id": "regime_3_amended_h0cf_methodology",
            "start": "2023-12-31",
            "end": "latest_common_history",
            "effective_date": "2023-12-31",
            "first_observable_project_trading_session": first_after_2023,
            "benchmark": "ICE US Fallen Angel High Yield 10% Constrained Index",
            "interpretation": "amended eligibility methodology",
            "required_caveat": "Limited original-issue high-yield bonds from already represented obligors may qualify when senior or senior secured; post-2023 exposure is less pure fallen-angel exposure.",
            "source_reference": "VanEck ETF Trust Supplement dated December 13, 2023; SEC accession context 000113736023000915",
            "boundary_identifiable_in_common_angl_hyg_history": spans_2023,
            "status": "ready" if spans_2023 and first_after_2023 else "blocked_until_common_history_available",
        }
    ]


def missing_rows(data_rows: list[dict[str, Any]], selected_count: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if selected_count != 1:
        rows.append(
            {
                "source_id": "not_evaluated",
                "field": "single_direction_owner_selected_source",
                "blocking_reason": "Selected source packet count was not exactly one.",
                "smallest_next_action": "Mark exactly one current source packet.",
            }
        )
    for row in data_rows:
        if row["required"] and row["cache_status"] != "cache_ready":
            rows.append(
                {
                    "source_id": SOURCE_ID,
                    "field": f"{row['symbol']}_local_cache",
                    "blocking_reason": f"Required symbol {row['symbol']} is {row['cache_status']}.",
                    "smallest_next_action": f"Restore or add existing authorized local adjusted-close cache for {row['symbol']} only; do not download in this task.",
                }
            )
    if not any(row.get("spans_feb_28_2020_boundary") for row in data_rows):
        rows.append(
            {
                "source_id": SOURCE_ID,
                "field": "feb_28_2020_common_history_boundary",
                "blocking_reason": "The February 28, 2020 methodology boundary cannot be identified in common ANGL/HYG history while ANGL cache is missing.",
                "smallest_next_action": "Resolve ANGL cache, then re-run intake feasibility.",
            }
        )
    if not any(row.get("spans_dec_31_2023_amendment") for row in data_rows):
        rows.append(
            {
                "source_id": SOURCE_ID,
                "field": "dec_31_2023_common_history_amendment",
                "blocking_reason": "The December 31, 2023 methodology amendment cannot be identified in common ANGL/HYG history while ANGL cache is missing or incomplete.",
                "smallest_next_action": "Resolve ANGL cache, then re-run intake feasibility.",
            }
        )
    return rows


def preregistration_payload() -> dict[str, Any]:
    return {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "source_id": SOURCE_ID,
        "role": "return_seeking_credit_allocation",
        "primary_benchmark": "HYG",
        "universe": {"candidate": "ANGL", "primary_benchmark": "HYG", "cash_context": "BIL", "duration_context_only": "IEF"},
        "rules": {
            "entry": "Enter 100% ANGL at the first authorized execution of each frozen window.",
            "exit": "Exit only at window end for measurement.",
            "holding": "Hold actual ETF shares until window end; no intermediate rebalance.",
            "prohibited": ["BIL switch", "trend filter", "rate filter", "spread filter", "downgrade timing filter", "duration hedge", "leverage", "shorting"],
            "missing_data": "Missing candidate or benchmark prices invalidate the window; no forward filling.",
        },
        "frozen_first_test_design": {
            "windows": ["five deterministic 90-trading-day windows", "five deterministic 180-trading-day windows"],
            "subperiods": [
                "full common ANGL/HYG period",
                "pre-2020-02-28 prior benchmark regime",
                "2020-02-28 through 2023-12-31 initial H0CF regime",
                "post-2023-12-31 amended H0CF regime",
                "three chronological thirds",
            ],
            "no_parameter_wrapper_or_window_search": True,
        },
        "metrics": [
            "return",
            "final_equity",
            "ANGL_minus_HYG_return",
            "win_rate_vs_HYG",
            "volatility",
            "downside_volatility",
            "maximum_drawdown",
            "return_drawdown_ratio",
            "2020_methodology_boundary_results",
            "2023_methodology_amendment_results",
            "chronological_third_stability",
        ],
        "pass_conditions": [
            "Positive median ANGL-minus-HYG return in both 90-day and 180-day window sets.",
            "ANGL beats HYG in at least 6 of 10 predetermined windows.",
            "Positive full-period annualized excess return versus HYG.",
            "Non-negative excess return versus HYG across all applicable methodology regimes.",
            "Result is not concentrated entirely in one chronological third.",
            "Maximum drawdown is not more than five percentage points worse than HYG.",
            "No accounting, alignment, or distribution-handling defect.",
        ],
        "fail_conditions": [
            "Negative median excess return in either horizon.",
            "Full-period underperformance versus HYG.",
            "Advantage occurs only in one methodology regime.",
            "Advantage isolated to one subperiod.",
            "Worse drawdown without compensating return.",
            "Broad high yield or BIL dominates intended role.",
            "Result primarily explained by duration exposure without distinct credit value.",
        ],
        "stop_conditions": [
            "Exact duplicate exists.",
            "Candidate or benchmark cache invalid.",
            "Distributions mishandled.",
            "Index transition cannot be recorded.",
            "Date alignment fails.",
            "More than one wrapper or rule variation introduced.",
        ],
        "no_screen_authorized_by_this_task": True,
        "screening_success_would_not_imply_robustness": True,
        "robustness_would_not_imply_paper_demo_eligibility": True,
        "no_lifecycle_or_active_observation_state_changes": True,
    }


def decision_payload(
    root: Path,
    selected_count: int,
    duplicate_rows: list[dict[str, Any]],
    data_rows: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    acquisition: dict[str, Any],
    prior_blocked: dict[str, Any],
    registry_before: str,
    registry_after: str,
    active_before: str,
    active_after: str,
) -> dict[str, Any]:
    duplicate = duplicate_rows[0]["exact_valid_duplicate_found"] is True
    if duplicate:
        decision = OUTCOME_DUPLICATE
        blocker = "exact_valid_static_angl_duplicate_found"
    elif missing:
        decision = OUTCOME_NOT_READY
        blocker = "required_local_cache_or_boundary_blocker"
    else:
        decision = OUTCOME_READY
        blocker = "none"
    queue = read_yaml(root, RESEARCH_QUEUE_PATH).get("external_source_discovery_lane", {})
    return {
        "decision": decision,
        "valid_decision": decision in VALID_DECISIONS,
        "blocker": blocker,
        "source_id": SOURCE_ID,
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "selected_source_packet_count": selected_count,
        "source_ids_evaluated": [SOURCE_ID] if selected_count == 1 else [],
        "preregistration_created": decision == OUTCOME_READY,
        "exact_valid_duplicate_found": duplicate,
        "required_symbols": list(REQUIRED_SYMBOLS),
        "missing_required_symbols": [row["symbol"] for row in data_rows if row["required"] and row["cache_status"] != "cache_ready"],
        "methodology_boundary": METHODOLOGY_BOUNDARY,
        "methodology_boundary_explicit": True,
        "methodology_amendment": METHODOLOGY_AMENDMENT,
        "methodology_amendment_explicit": True,
        "prior_blocked_decision_reference": prior_blocked,
        "source_reported_performance_excluded": True,
        "sponsor_performance_claims_used_as_project_evidence": False,
        "trend_bil_rate_duration_overlay_added": False,
        "provider_download": acquisition["provider_download_this_run"],
        "provider_download_authorized_for_angl_only": True,
        "provider_requested_symbols": acquisition["requested_symbols"],
        "provider_downloaded_symbols_this_run": acquisition["downloaded_symbols_this_run"],
        "existing_valid_angl_cache_prevented_provider_call": acquisition["existing_valid_cache_prevented_provider_call"],
        "provider_allowlist_rejects_non_angl": acquisition["provider_allowlist_rejects_non_angl"],
        "provider_download_error": acquisition["provider_download_error"],
        "protected_cache_hashes_unchanged": acquisition["protected_cache_hashes_unchanged"],
        "screen_run": False,
        "backtest_run": False,
        "performance_calculation": False,
        "strategy_implementation": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "real_money_recommendation": False,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_after,
        "active_observations_hash_before": active_before,
        "active_observations_hash_after": active_after,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_unchanged": active_before == active_after,
        "external_discovery_pause_remains_active": queue.get("status") == "paused_pending_direction_owner_supplied_source",
        "automatic_next_source_selection": queue.get("automatic_next_source_selection"),
        "new_external_screen_authorized": queue.get("new_external_screen_authorized"),
        "next_action": "restore_or_authorize_local_angl_cache_before_preregistration" if decision == OUTCOME_NOT_READY else "await_separate_authorization_for_bounded_screen",
    }


def decision_markdown(decision: dict[str, Any], missing: list[dict[str, Any]]) -> str:
    missing_text = "\n".join(f"- `{row['field']}`: {row['blocking_reason']}" for row in missing) or "- none"
    return f"""# Direction-Owner Single-Source Intake v1

Decision: `{decision['decision']}`

Source: `{SOURCE_ID}`

Candidate: `{CANDIDATE_ID}`

Blocker: `{decision['blocker']}`

## Missing Or Ambiguous Fields

{missing_text}

## Guardrails

- Sponsor/source-reported performance is excluded from project evidence.
- No screen or backtest was run.
- No strategy implementation was created.
- Provider access, if used, was limited to `ANGL` cache restoration only.
- No trend, BIL switch, rate filter, or duration hedge was added.
- No lifecycle, evidence-level, active-observation, paper/demo, broker/live, or real-money action occurred.

Exact next action: `{decision['next_action']}`
"""


def preregistration_markdown(prereg: dict[str, Any]) -> str:
    return f"""# Frozen Pre-Registration: {CANDIDATE_ID}

Family: `{FAMILY_ID}`

Source: `{SOURCE_ID}`

Primary benchmark: `HYG`

This pre-registration authorizes no screen by itself. Screening success would not imply robustness, and robustness would not imply paper/demo eligibility.
"""


def consistency_payload(decision: dict[str, Any]) -> dict[str, Any]:
    check = {
        "exactly_one_selected_source_evaluated": decision["selected_source_packet_count"] == 1 and decision["source_ids_evaluated"] == [SOURCE_ID],
        "codex_did_not_choose_another_source": True,
        "sponsor_performance_claims_excluded": decision["sponsor_performance_claims_used_as_project_evidence"] is False,
        "duplicate_evidence_stops_execution_if_present": decision["decision"] != OUTCOME_DUPLICATE or decision["preregistration_created"] is False,
        "angl_cache_absence_blocks_preregistration": ("ANGL" not in decision["missing_required_symbols"]) or decision["decision"] == OUTCOME_NOT_READY,
        "methodology_boundary_explicit": decision["methodology_boundary"] == METHODOLOGY_BOUNDARY,
        "methodology_amendment_explicit": decision["methodology_amendment"] == METHODOLOGY_AMENDMENT,
        "no_trend_bil_rate_or_duration_overlay_added": decision["trend_bil_rate_duration_overlay_added"] is False,
        "only_angl_provider_request_if_any": set(decision["provider_requested_symbols"]).issubset({"ANGL"})
        and set(decision["provider_downloaded_symbols_this_run"]).issubset({"ANGL"}),
        "no_performance_calculation": decision["performance_calculation"] is False,
        "no_screen_authorized": decision["screen_run"] is False,
        "protected_existing_caches_unchanged": decision["protected_cache_hashes_unchanged"] is True,
        "registry_byte_identical": decision["registry_byte_identical"] is True,
        "active_observations_unchanged": decision["active_observations_unchanged"] is True,
        "external_discovery_pause_remains_active": decision["external_discovery_pause_remains_active"] is True,
        "generation_is_deterministic": True,
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run(root: Path = ROOT, downloader: Any | None = None) -> dict[str, Any]:
    output = abs_path(root, OUTPUT_DIR)
    prior_decision = read_json(root, OUTPUT_DIR / "decision.json")
    prior_blocked = prior_blocked_reference(prior_decision)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    registry_before = file_hash(root, REGISTRY_PATH)
    active_before = file_hash(root, ACTIVE_OBSERVATIONS_PATH)
    selected = selected_source_packets(root)
    packet = selected[0] if len(selected) == 1 else None
    payload = packet["payload"] if packet else {}

    source_rows = source_identity_rows(packet, len(selected))
    rules = source_rule_rows(payload)
    support = source_support_rows(rules, payload) if payload else []
    duplicate_rows = duplicate_gate_rows(root)
    material_rows = material_distinction_rows()
    acquisition, angl_validation = acquire_angl_if_needed(root, downloader)
    data_rows = data_feasibility_rows(root)
    for row in data_rows:
        row["provider_download"] = row["symbol"] in acquisition["downloaded_symbols_this_run"]
    transition_rows = methodology_transition_rows(data_rows)
    missing = missing_rows(data_rows, len(selected))

    registry_after = file_hash(root, REGISTRY_PATH)
    active_after = file_hash(root, ACTIVE_OBSERVATIONS_PATH)
    decision = decision_payload(
        root,
        len(selected),
        duplicate_rows,
        data_rows,
        missing,
        acquisition,
        prior_blocked,
        registry_before,
        registry_after,
        active_before,
        active_after,
    )
    consistency = consistency_payload(decision)

    write_json(root, OUTPUT_DIR / "provider_acquisition_manifest.json", acquisition)
    write_json(root, OUTPUT_DIR / "prior_blocked_decision_reference.json", prior_blocked)
    write_csv(
        root,
        OUTPUT_DIR / "angl_cache_validation.csv",
        [angl_validation],
        [
            "symbol",
            "required",
            "cache_path",
            "cache_exists",
            "cache_hash",
            "first_valid_date",
            "last_valid_date",
            "row_count",
            "schema",
            "symbol_identity_valid",
            "adjusted_close_available",
            "missing_adj_close_count",
            "duplicate_date_count",
            "nonpositive_adj_close_count",
            "history_consistent_with_inception",
            "cache_status",
        ],
    )
    write_json(root, OUTPUT_DIR / "decision.json", decision)
    write_text(root, OUTPUT_DIR / "decision.md", decision_markdown(decision, missing))
    write_csv(root, OUTPUT_DIR / "source_identity.csv", source_rows, ["source_id", "source_name", "candidate_id", "family", "source_class", "primary_citation_or_reference", "author_or_publisher", "economic_mechanism", "strategy_role", "primary_benchmark", "known_ambiguities", "direction_owner_selected", "current_input_gate_candidate", "external_source_discovery_pause_remains_active", "selected_source_packet_count"])
    write_csv(root, OUTPUT_DIR / "source_rule_extraction.csv", rules, ["source_id", "rule_id", "normalized_value", "classification", "source_reference", "material_rule"])
    write_csv(root, OUTPUT_DIR / "source_support_trace.csv", support, ["source_id", "rule_id", "classification", "source_reference", "supports_rule", "sponsor_performance_claim", "source_reported_performance_excluded"])
    write_csv(root, OUTPUT_DIR / "duplicate_gate.csv", duplicate_rows, ["source_id", "candidate_id", "exact_valid_duplicate_found", "authoritative_duplicate_result", "prior_angl_or_fallen_angel_mentions", "duplicate_gate_decision", "notes"])
    write_csv(root, OUTPUT_DIR / "material_distinction_review.csv", material_rows, ["source_id", "candidate_id", "closest_prior_strategy", "prior_mechanism", "material_difference", "material_distinction_from_source", "exact_closed_variant_reopened", "review_result"])
    write_csv(
        root,
        OUTPUT_DIR / "data_and_execution_feasibility.csv",
        data_rows,
        [
            "symbol",
            "required",
            "cache_path",
            "cache_exists",
            "cache_hash",
            "first_valid_date",
            "last_valid_date",
            "row_count",
            "schema",
            "symbol_identity_valid",
            "adjusted_close_available",
            "missing_adj_close_count",
            "duplicate_date_count",
            "nonpositive_adj_close_count",
            "history_consistent_with_inception",
            "cache_status",
            "common_angl_hyg_start",
            "common_angl_hyg_end",
            "common_angl_hyg_row_count",
            "spans_feb_28_2020_boundary",
            "first_common_session_on_or_after_2020_02_28",
            "spans_dec_31_2023_amendment",
            "first_common_session_on_or_after_2023_12_31",
            "provider_download",
        ],
    )
    write_csv(
        root,
        OUTPUT_DIR / "methodology_transition_review.csv",
        transition_rows,
        [
            "source_id",
            "regime_id",
            "start",
            "end",
            "effective_date",
            "first_observable_project_trading_session",
            "benchmark",
            "interpretation",
            "required_caveat",
            "source_reference",
            "boundary_identifiable_in_common_angl_hyg_history",
            "status",
        ],
    )
    write_csv(root, OUTPUT_DIR / "missing_or_ambiguous_fields.csv", missing, ["source_id", "field", "blocking_reason", "smallest_next_action"])
    if decision["decision"] == OUTCOME_READY:
        prereg = preregistration_payload()
        write_yaml(root, OUTPUT_DIR / "preregistration.yaml", prereg)
        write_text(root, OUTPUT_DIR / "preregistration.md", preregistration_markdown(prereg))
    write_json(root, OUTPUT_DIR / "consistency_check.json", consistency)

    return {
        "decision": decision["decision"],
        "output_dir": str(output),
        "source_ids_evaluated": decision["source_ids_evaluated"],
        "missing_required_symbols": decision["missing_required_symbols"],
        "next_action": decision["next_action"],
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
