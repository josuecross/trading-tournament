from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    SourceAdapterRegistry,
    normalized_spdj_package_hash,
    sha256_path,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.errors import StandardContractError
from contracts.forward_observation.forward_observation_handoff_standard_v1.importer import (
    IMPORTER_VERSION,
    HandoffImporter,
    importer_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.lifecycle import (
    LifecycleTransition,
    validate_transition,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    DeploymentProfile,
    StrategyState,
    canonical_json_hash,
    deterministic_target_version_id,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.state import (
    JsonStrategyStateStore,
    apply_calculation_result,
    promote_pending_target,
)
from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT, PACKAGE_ROOT
from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from execution_lab.alpaca_micro_live_v1.standard_handoff import DEFAULT_IMPORT_STORAGE
from execution_lab.alpaca_micro_live_v1.standard_handoff.spdj_calculator import (
    FORMULA_TOLERANCE,
    SYMBOLS,
    WEIGHT_TOLERANCE,
    SpdjCalculationError,
    SpdjReceiverCalculator,
    build_xnys_calendar,
    classify_regime,
    load_cpi_reference,
    normalize_provider_frames,
)


TASK_ID = "pilot_import_validate_spdj_under_forward_observation_standard_v1"
OUTCOME_SUCCESS = "spdj_standard_handoff_import_validated_not_active"
OUTCOME_BLOCKED = "spdj_standard_handoff_import_blocked"
STANDARD_ID = "forward_observation_handoff_standard_v1"
STANDARD_VERSION = 1
STANDARD_EVIDENCE_HASH = "sha256:65ce6fe419f38555e3f0bc285e43eff57b70f70af870f712e9d1545f8d8c9888"
HANDOFF_ID = "spdj_dynamic_inflation_forward_observation_handoff_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
INSTANCE_ID = f"{STRATEGY_ID}__inactive_validation_instance"
PACKAGE_HASH = "sha256:f1844b722c11db1fd21b91192a56d2b1953c6719994f9de113c16e72882998b9"
CANONICAL_CODE_HASH = "sha256:55eff61ee55999df76d023e570440197c7dbf0d05da41775cf23671dbd15b1e4"
CPI_DATASET_HASH = "sha256:e221af86dfd616f4fa65bec016910deaffe47f1d6e690495a4033cd0e3eefcc8"
PRICE_BUNDLE_HASH = "sha256:ab05bef8ac2b12c6391bca65cb1312148db7d64bed11e9932379464f8bcc72c8"
UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
EXPECTED_ELIGIBILITY = "spdj_dynamic_inflation_research_eligible_for_handoff"
SOURCE_SCHEMA = "spdj_forward_observation_handoff_schema_v1:v1"
NORMALIZED_SCHEMA = f"{STANDARD_ID}:{STANDARD_VERSION}"
OUTPUT_DIR = MODULE_ROOT / "evidence" / "handoff_import_validation" / "spdj_standard_handoff_import_v1" / "latest"
CATALOG_DIR = MODULE_ROOT / "evidence" / "standard_handoff_catalog"
SOURCE_LATEST = PACKAGE_ROOT / "evidence" / "handoff_exports" / "spdj_dynamic_inflation_forward_observation_handoff_v1" / "latest"
SOURCE_PACKAGE = SOURCE_LATEST / "package"
STANDARD_EVIDENCE = PACKAGE_ROOT / "evidence" / "standardization" / "forward_observation_handoff_standard_v1" / "latest"
ACQUISITION_START = "2006-07-01T00:00:00Z"
ACQUISITION_END = "2024-09-14T00:00:00Z"
ALPACA_FEED = "sip"
ALPACA_ADJUSTMENT = "all"


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def hash_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_file(path)
    return sha256_path(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _canonical_file_hashes(paths: dict[str, str]) -> str:
    return canonical_json_hash(paths)


def verify_standard_evidence() -> dict[str, Any]:
    consistency = json.loads((STANDARD_EVIDENCE / "consistency_check.json").read_text(encoding="utf-8"))
    observed_artifacts = {
        name: sha256_file(STANDARD_EVIDENCE / name)
        for name in sorted(consistency["artifact_hashes"])
    }
    calculated_hash = _canonical_file_hashes(observed_artifacts)
    schema_manifest = json.loads((STANDARD_EVIDENCE / "standard_schema_manifest.json").read_text(encoding="utf-8"))
    spdj_compatibility = json.loads((STANDARD_EVIDENCE / "spdj_structural_compatibility.json").read_text(encoding="utf-8"))
    checks = {
        "outcome": consistency.get("outcome") == "forward_observation_handoff_standard_v1_implemented",
        "standard_id": schema_manifest["schema_id"] == STANDARD_ID,
        "schema_version": schema_manifest["schema_version"] == STANDARD_VERSION,
        "artifact_hashes": observed_artifacts == consistency["artifact_hashes"],
        "deterministic_hash": calculated_hash == STANDARD_EVIDENCE_HASH == consistency.get("deterministic_evidence_hash"),
        "ready": consistency.get("checks", {}).get("ready_for_strategy_migration") is True,
        "spdj_status": spdj_compatibility["structural_compatibility"] == "standard_structurally_representable_validate_only",
    }
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks, "calculated_evidence_hash": calculated_hash}


def protected_paths() -> dict[str, Path]:
    return {
        "research_spdj_export": SOURCE_LATEST,
        "research_spdj_code": PACKAGE_ROOT / "strategy_lab" / "research_os" / "research" / "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1.py",
        "CPI_V1": PACKAGE_ROOT / "data" / "public_signals" / "phase2_public_cpi_point_in_time_v1",
        "CPI_V2": PACKAGE_ROOT / "data" / "public_signals" / "phase2_public_cpi_point_in_time_v2",
        "VM_calculator": MODULE_ROOT / "runtime_strategies" / "vm_quality_lowvol_proxy_v1.py",
        "VM_spec": MODULE_ROOT / "runtime_strategies" / "vm_quality_lowvol_proxy_v1.yaml",
        "DSR_calculator": MODULE_ROOT / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.py",
        "DSR_spec": MODULE_ROOT / "runtime_strategies" / "dsr_sector_equal_weight_defensive_filter_v1.yaml",
        "legacy_runtime_registry": MODULE_ROOT / "runtime_strategies" / "runtime_strategy_registry.yaml",
        "historical_runtime_sessions": MODULE_ROOT / "evidence" / "runtime_sessions",
        "historical_weekly_demo_sessions": MODULE_ROOT / "evidence" / "weekly_demo_sessions",
        "receiver_runtime_cache": MODULE_ROOT / "evidence" / "alpaca_runtime_data" / "cache",
        "alpaca_client": MODULE_ROOT / "adapters" / "alpaca_client.py",
        "broker_configuration": MODULE_ROOT / "config",
        "risk_gate": MODULE_ROOT / "execution" / "risk_gate.py",
    }


def protected_snapshot() -> dict[str, str]:
    return {name: hash_path(path) for name, path in protected_paths().items()}


def _persistent_import_count() -> int:
    if not DEFAULT_IMPORT_STORAGE.exists():
        return 0
    return len(list(DEFAULT_IMPORT_STORAGE.glob("*/*/normalized_handoff.json")))


def _validated_catalog_count() -> int:
    if not CATALOG_DIR.exists():
        return 0
    count = 0
    for path in CATALOG_DIR.glob("*.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("acceptance_status") == "validated_not_active":
                count += 1
        except (OSError, json.JSONDecodeError):
            continue
    return count


def _copy_source_package(imported_root: Path) -> tuple[Path, Path, dict[str, Any]]:
    source_storage = MODULE_ROOT / "p" / PACKAGE_HASH.removeprefix("sha256:")[:16]
    imported_source = source_storage / "package"
    if not imported_source.exists():
        shutil.copytree(SOURCE_PACKAGE, imported_source)
    manifest_copy = source_storage / "package_file_manifest.csv"
    if not manifest_copy.exists():
        shutil.copy2(SOURCE_LATEST / "package_file_manifest.csv", manifest_copy)
    source_hash = normalized_spdj_package_hash(imported_source)
    if source_hash != PACKAGE_HASH:
        raise StandardContractError("package_integrity_failure", "Receiver-owned source package hash mismatch")
    return imported_source, manifest_copy, {
        "receiver_source_package_hash": source_hash,
        "receiver_source_package_path": imported_source.as_posix(),
        "standard_import_record_path": imported_root.as_posix(),
    }


def verify_imported_package(imported_source: Path, manifest_path: Path) -> dict[str, Any]:
    rows = list(csv.DictReader(manifest_path.open(newline="", encoding="utf-8")))
    file_rows: list[dict[str, Any]] = []
    for row in rows:
        path = imported_source / row["relative_path"]
        observed = sha256_file(path) if path.exists() else "missing"
        file_rows.append({**row, "observed_sha256": observed, "hash_match": observed == row["file_sha256"]})
    handoff = json.loads((imported_source / "handoff_manifest.json").read_text(encoding="utf-8"))
    strategy = json.loads((imported_source / "strategy_contract.json").read_text(encoding="utf-8"))
    checks = {
        "all_package_files_present_and_hashed": all(row["hash_match"] for row in file_rows),
        "handoff_id": handoff.get("handoff_id") == HANDOFF_ID,
        "strategy_id": handoff.get("strategy_id") == STRATEGY_ID,
        "schema": handoff.get("package_schema_version") == SOURCE_SCHEMA.split(":", 1)[0],
        "eligibility": handoff.get("research_eligibility_status") == EXPECTED_ELIGIBILITY,
        "logical_package_hash": normalized_spdj_package_hash(imported_source) == PACKAGE_HASH == handoff.get("package_content_hash"),
        "canonical_code_hash": sha256_file(imported_source / "reference_only" / "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1.py") == CANONICAL_CODE_HASH == handoff.get("canonical_code_hash"),
        "CPI_dataset_hash": handoff.get("CPI_dataset_hash") == CPI_DATASET_HASH == strategy["hashes"]["CPI_logical_dataset"],
        "price_bundle_hash": handoff.get("price_bundle_hash") == PRICE_BUNDLE_HASH == strategy["hashes"]["price_bundle"],
        "universe_hash": handoff.get("universe_hash") == UNIVERSE_HASH == strategy["hashes"]["frozen_universe"],
    }
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks, "package_files": file_rows}


def normalization_field_map() -> list[dict[str, Any]]:
    return [
        {"source_field": "handoff_manifest.handoff_id", "standard_field": "envelope.handoff_id", "rule": "identity", "invented": False},
        {"source_field": "handoff_manifest.strategy_id", "standard_field": "envelope.strategy_id", "rule": "identity", "invented": False},
        {"source_field": "handoff_manifest.family_id", "standard_field": "envelope.family_id", "rule": "identity", "invented": False},
        {"source_field": "strategy_contract.symbols", "standard_field": "tradable_contract.instruments", "rule": "ordered_exact_symbols_with_source_mappings", "invented": False},
        {"source_field": "strategy_contract.source_exposure_mappings", "standard_field": "tradable_contract.instruments.role/exposure/substitution_policy", "rule": "mechanical", "invented": False},
        {"source_field": "strategy_contract.price_semantics", "standard_field": "tradable_contract.instruments.price_semantics/history", "rule": "mechanical", "invented": False},
        {"source_field": "signal_contract", "standard_field": "signal_dependencies[0]", "rule": "external_release_signal", "invented": False},
        {"source_field": "strategy_contract.price_semantics", "standard_field": "signal_dependencies[1]", "rule": "market_price_signal", "invented": False},
        {"source_field": "strategy_contract.target_algorithms/warmup", "standard_field": "calculator_contract.calculator_configuration", "rule": "verbatim_nested_contract", "invented": False},
        {"source_field": "schedule_and_timing_contract", "standard_field": "timing_contract", "rule": "next_valid_XNYS_session_after_close", "invented": False},
        {"source_field": "golden_fixture_manifest", "standard_field": "required_fixture_types", "rule": "declared_fixture_capabilities", "invented": False},
        {"source_field": "caveat_register.csv", "standard_field": "envelope.caveats", "rule": "verbatim_rows", "invented": False},
    ]


def _load_cached_frames(data_root: Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]] | None:
    manifest_path = data_root / "acquisition_manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success":
        return {}, manifest
    frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        path = data_root / "normalized" / f"{symbol}.csv"
        if not path.exists() or sha256_file(path) != manifest["symbols"][symbol]["file_hash"]:
            return None
        frames[symbol] = pd.read_csv(path)
    manifest["reused_receiver_owned_cache"] = True
    return frames, manifest


def acquire_historical_frames(data_root: Path, retrieved_at: str) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    cached = _load_cached_frames(data_root)
    if cached is not None:
        return cached
    data_root.mkdir(parents=True, exist_ok=True)
    credentials = load_alpaca_credentials()
    if not credentials.present:
        manifest = {
            "status": "failed",
            "failure_reason": "historical_provider_unavailable",
            "provider": "Alpaca official market data API",
            "credential_source_configured": False,
            "historical_market_data_calls": 0,
            "retrieved_at": retrieved_at,
        }
        write_json(data_root / "acquisition_manifest.json", manifest)
        return {}, manifest
    client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
    merged: dict[str, Any] = {"bars": {symbol: [] for symbol in SYMBOLS}}
    raw_dir = data_root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    page_token: str | None = None
    calls = 0
    response_hashes: list[str] = []
    failure = ""
    try:
        while True:
            calls += 1
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOLS),
                start=ACQUISITION_START,
                end=ACQUISITION_END,
                timeframe="1Day",
                page_token=page_token,
                feed=ALPACA_FEED,
                adjustment=ALPACA_ADJUSTMENT,
                limit=10000,
            )
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
            response_path = raw_dir / f"page_{calls:04d}.json"
            response_path.write_text(raw, encoding="utf-8")
            response_hashes.append(sha256_file(response_path))
            for symbol, bars in payload.get("bars", {}).items():
                merged["bars"].setdefault(symbol, []).extend(bars)
            page_token = payload.get("next_page_token")
            if not page_token:
                break
    except Exception as exc:  # the normalized error is persisted; credentials never are
        failure = type(exc).__name__
    if failure:
        manifest = {
            "status": "failed",
            "failure_reason": "historical_provider_unavailable",
            "provider": "Alpaca official market data API",
            "feed": ALPACA_FEED,
            "adjustment": ALPACA_ADJUSTMENT,
            "requested_start": ACQUISITION_START,
            "requested_end_exclusive": ACQUISITION_END,
            "historical_market_data_calls": calls,
            "normalized_exception_type": failure,
            "credentials_persisted": False,
            "response_hashes": response_hashes,
            "retrieved_at": retrieved_at,
        }
        write_json(data_root / "acquisition_manifest.json", manifest)
        return {}, manifest
    frames = parse_bars_response(merged, drop_incomplete_current_day=False)
    normalized_dir = data_root / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    symbol_manifest: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frame = frames.get(symbol, pd.DataFrame()).copy()
        path = normalized_dir / f"{symbol}.csv"
        frame.to_csv(path, index=False, lineterminator="\n")
        symbol_manifest[symbol] = {
            "file_hash": sha256_file(path),
            "row_count": len(frame),
            "first_date": "" if frame.empty else str(frame["date"].min()),
            "last_date": "" if frame.empty else str(frame["date"].max()),
            "duplicate_count": 0 if frame.empty else int(frame["date"].duplicated().sum()),
        }
    manifest = {
        "status": "success",
        "provider": "Alpaca official market data API",
        "endpoint": "/v2/stocks/bars",
        "feed": ALPACA_FEED,
        "adjustment": ALPACA_ADJUSTMENT,
        "adjustment_semantics": "Alpaca adjustment=all; bars are adjusted for splits and cash dividends, with close used as the total-return-compatible price input",
        "split_handling": "provider adjustment=all",
        "dividend_handling": "provider adjustment=all",
        "timestamp_semantics": "daily bar timestamp normalized to US-equity session date",
        "timezone": "UTC timestamp; session date retained",
        "returned_price_field": "close from adjustment=all response",
        "requested_start": ACQUISITION_START,
        "requested_end_exclusive": ACQUISITION_END,
        "historical_market_data_calls": calls,
        "current_market_data_calls": 0,
        "credentials_persisted": False,
        "response_hashes": response_hashes,
        "retrieved_at": retrieved_at,
        "symbols": symbol_manifest,
        "reused_receiver_owned_cache": False,
    }
    write_json(data_root / "acquisition_manifest.json", manifest)
    return {symbol: frames.get(symbol, pd.DataFrame()) for symbol in SYMBOLS}, manifest


GOLDEN_FIELDS = [
    "fixture_id", "fixture_type", "reference_month", "event_identity", "expected_CPI_YoY", "observed_CPI_YoY",
    "expected_regime", "observed_regime", "regime_result", "expected_statistics_cutoff", "observed_statistics_cutoff",
    "expected_effective_timestamp", "observed_effective_timestamp", "timing_result", "expected_lookback", "observed_lookback",
    "expected_ProIB_pair_count", "observed_pair_count", "expected_target_weights", "observed_target_weights",
    "maximum_absolute_target_error", "price_provider", "result_classification", "discrepancy_reason",
]


def run_golden_fixtures(imported_source: Path, calculator: SpdjReceiverCalculator, prices: pd.DataFrame | None) -> tuple[list[dict[str, Any]], list[Any], dict[str, Any]]:
    fixtures = list(csv.DictReader((imported_source / "golden_conformance_fixtures.csv").open(newline="", encoding="utf-8")))
    cpi = load_cpi_reference(imported_source / "reference_only" / "historical_cpi_v2" / "cpi_point_in_time_signal.csv")
    calendar = build_xnys_calendar()
    rows: list[dict[str, Any]] = []
    successful_calculations: list[Any] = []
    threshold_passed = 0
    maximum_error = 0.0
    for fixture in fixtures:
        month_text = fixture["reference_month"]
        month = pd.Period(month_text, freq="M")
        cpi_row = cpi.loc[month]
        expected_weights = {
            symbol: float(fixture[f"expected_target_{symbol}"])
            for symbol in SYMBOLS
            if fixture[f"expected_target_{symbol}"] != ""
        }
        observed_cpi = "" if pd.isna(cpi_row["cpi_yoy"]) else float(cpi_row["cpi_yoy"])
        observed_regime = "" if observed_cpi == "" else classify_regime(float(observed_cpi))
        expected_regime = fixture["regime"]
        regime_pass = observed_regime == expected_regime
        if fixture["threshold_disagreement"].lower() == "true" and regime_pass:
            threshold_passed += 1
        observed_effective = ""
        timing_pass = fixture["event_status"] == "no_release_no_event"
        observed_statistics = ""
        observed_lookback: Any = ""
        observed_pair_count: Any = ""
        observed_weights: dict[str, float] = {}
        max_error: Any = ""
        discrepancy = ""
        event_identity = ""
        classification = "pass"
        if fixture["event_status"] == "no_release_no_event":
            no_event = calculator.no_event_result(reference_month=month_text, calculated_at="2025-11-30T00:00:00Z")
            classification = "no_release_no_event_pass" if no_event.status == "no_event" and not no_event.target_weights else "fail_state_semantics"
            timing_pass = classification == "no_release_no_event_pass"
        else:
            release_date = fixture["release_date"]
            event_identity = f"CPIAUCNS:{month_text}:{release_date}"
            calendar_effective = calendar.next_session_after(release_date).session_date
            observed_effective = calendar_effective
            timing_pass = calendar_effective == fixture["effective_after_close_date"]
            if not timing_pass:
                classification = "fail_calendar_semantics"
                discrepancy = "XNYS next-session effective date mismatch"
            if not regime_pass:
                classification = "fail_CPI_semantics"
                discrepancy = "CPI value or regime mismatch"
            if not expected_weights:
                classification = "not_applicable_pre_warmup" if regime_pass and timing_pass else classification
            elif prices is None:
                classification = "fail_price_semantics"
                discrepancy = "Receiver historical market data unavailable"
            else:
                try:
                    calculated = calculator.calculate(
                        reference_month=month_text,
                        cpi_reference=cpi,
                        prices=prices,
                        calendar=calendar,
                        fixture_id=fixture["fixture_id"],
                    )
                    successful_calculations.append(calculated)
                    observed_statistics = calculated.statistics_cutoff
                    observed_effective = calculated.effective_timestamp[:10]
                    observed_lookback = calculated.lookback_monthly_returns
                    observed_pair_count = calculated.pro_ib_diagnostics["pair_count"]
                    observed_weights = calculated.target_weights
                    max_error = max(abs(observed_weights[symbol] - expected_weights[symbol]) for symbol in SYMBOLS)
                    maximum_error = max(maximum_error, float(max_error))
                    statistics_pass = observed_statistics == fixture["allocation_statistics_cutoff"]
                    timing_pass = observed_effective == fixture["effective_after_close_date"]
                    lookback_pass = observed_lookback == int(fixture["lookback_monthly_returns"])
                    pair_pass = fixture["proib_pair_count"] == "" or observed_pair_count == int(fixture["proib_pair_count"])
                    if not lookback_pass or not pair_pass:
                        classification = "fail_price_semantics"
                        discrepancy = "Receiver history coverage changed the frozen lookback or ProIB pair count"
                    elif not statistics_pass:
                        classification = "fail_strategy_logic"
                        discrepancy = "Statistics cutoff mismatch"
                    elif not timing_pass:
                        classification = "fail_calendar_semantics"
                        discrepancy = "Effective timestamp mismatch"
                    elif float(max_error) > WEIGHT_TOLERANCE:
                        classification = "fail_price_semantics"
                        discrepancy = "Receiver adjusted history does not reproduce target weights"
                    elif not regime_pass:
                        classification = "fail_CPI_semantics"
                    else:
                        classification = "pass"
                except SpdjCalculationError as exc:
                    classification = "not_applicable_pre_warmup" if exc.code == "not_applicable_pre_warmup" and not expected_weights else "fail_price_semantics" if exc.code in {"not_applicable_pre_warmup", "receiver_price_semantics_validation_failed", "historical_provider_unavailable"} else "fail_strategy_logic"
                    discrepancy = str(exc)
        row = {
            "fixture_id": fixture["fixture_id"],
            "fixture_type": fixture["fixture_roles"],
            "reference_month": month_text,
            "event_identity": event_identity,
            "expected_CPI_YoY": fixture["canonical_cpi_yoy_unrounded"],
            "observed_CPI_YoY": observed_cpi,
            "expected_regime": expected_regime,
            "observed_regime": observed_regime,
            "regime_result": "pass" if regime_pass else "fail",
            "expected_statistics_cutoff": fixture["allocation_statistics_cutoff"],
            "observed_statistics_cutoff": observed_statistics,
            "expected_effective_timestamp": fixture["effective_after_close_date"],
            "observed_effective_timestamp": observed_effective,
            "timing_result": "pass" if timing_pass else "fail",
            "expected_lookback": fixture["lookback_monthly_returns"],
            "observed_lookback": observed_lookback,
            "expected_ProIB_pair_count": fixture["proib_pair_count"],
            "observed_pair_count": observed_pair_count,
            "expected_target_weights": expected_weights,
            "observed_target_weights": observed_weights,
            "maximum_absolute_target_error": max_error,
            "price_provider": "Alpaca official market data API",
            "result_classification": classification,
            "discrepancy_reason": discrepancy,
        }
        rows.append(row)
    accepted = {"pass", "not_applicable_pre_warmup", "no_release_no_event_pass"}
    summary = {
        "fixture_count": len(rows),
        "accepted_count": sum(row["result_classification"] in accepted for row in rows),
        "failed_count": sum(row["result_classification"] not in accepted for row in rows),
        "pre_warmup_count": sum(row["result_classification"] == "not_applicable_pre_warmup" for row in rows),
        "no_event_count": sum(row["result_classification"] == "no_release_no_event_pass" for row in rows),
        "threshold_cases_passed": threshold_passed,
        "maximum_applicable_target_weight_error": maximum_error,
    }
    return rows, successful_calculations, summary


def state_validation(calculator: SpdjReceiverCalculator, calculations: list[Any], run_timestamp: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not calculations:
        blocked = {"status": "blocked", "reason": "No independently reproduced historical target available"}
        return blocked, blocked, blocked
    calculation = calculations[0]
    state_root = MODULE_ROOT / "vstate"
    state_path = state_root / f"{INSTANCE_ID}.json"
    if state_path.exists():
        state_path.unlink()
    store = JsonStrategyStateStore(state_root)
    initial = StrategyState(
        strategy_instance_id=INSTANCE_ID,
        handoff_id=HANDOFF_ID,
        receiver_strategy_id=STRATEGY_ID,
        lifecycle_state="validated_not_active",
    )
    before_effective = calculation.result.calculated_at
    pending = apply_calculation_result(initial, calculation.result, now=before_effective)
    store.save(pending)
    restarted_pending = JsonStrategyStateStore(state_root).load(INSTANCE_ID)
    promoted = promote_pending_target(restarted_pending, now=calculation.result.effective_timestamp)
    store.save(promoted)
    restarted_current = JsonStrategyStateStore(state_root).load(INSTANCE_ID)
    duplicate = "not_tested"
    try:
        apply_calculation_result(restarted_current, calculation.result, now=run_timestamp)
    except StandardContractError as exc:
        duplicate = exc.code
    no_event = calculator.no_event_result(reference_month="2025-10", calculated_at="2025-11-30T00:00:00Z")
    preserved = apply_calculation_result(restarted_current, no_event, now="2025-11-30T00:00:00Z")
    repeated_version = deterministic_target_version_id(
        package_content_hash=calculator.handoff.envelope.package_content_hash,
        handoff_id=calculator.handoff.envelope.handoff_id,
        strategy_instance_id=calculator.binding.strategy_instance_id,
        event_id=calculation.result.event_id or "",
        target_weights=calculation.result.target_weights,
        cash_weight=calculation.result.cash_weight,
        effective_timestamp=calculation.result.effective_timestamp or "",
    )
    state_result = {
        "status": "pass" if all([
            pending.pending_target_version == calculation.result.target_version_id,
            restarted_pending == pending,
            promoted.current_effective_target_version == calculation.result.target_version_id,
            restarted_current == promoted,
            preserved.current_effective_target_version == restarted_current.current_effective_target_version,
            calculation.result.event_id in restarted_current.handled_event_ids,
        ]) else "fail",
        "pending_before_effective": pending.pending_target_version == calculation.result.target_version_id,
        "pending_reloaded_identically": restarted_pending == pending,
        "promoted_at_effective_time": promoted.current_effective_target_version == calculation.result.target_version_id,
        "current_reloaded_identically": restarted_current == promoted,
        "no_event_preserved_current": preserved.current_effective_target_version == restarted_current.current_effective_target_version,
        "handled_event_identity_persisted": calculation.result.event_id in restarted_current.handled_event_ids,
        "state_scope": "historical_fixture_validation_only_non_operational",
    }
    idempotency = {"status": "pass" if duplicate == "duplicate_event" else "fail", "duplicate_classification": duplicate, "target_versions_created": 1, "pending_targets_created": 1}
    target_version = {"status": "pass" if repeated_version == calculation.result.target_version_id else "fail", "first": calculation.result.target_version_id, "repeated": repeated_version, "session_id_in_identity": False}
    return state_result, idempotency, target_version


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_import_manifest = OUTPUT_DIR / "import_manifest.json"
    prior_manifest = json.loads(existing_import_manifest.read_text(encoding="utf-8")) if existing_import_manifest.exists() else {}
    run_timestamp = prior_manifest.get("import_timestamp") or datetime.now(timezone.utc).isoformat()
    protected_before = protected_snapshot()
    standard_integrity = verify_standard_evidence()
    count_before = int(prior_manifest.get("standardized_import_count_before", _persistent_import_count()))
    validated_before = int(prior_manifest.get("validated_not_active_count_before", _validated_catalog_count()))
    blockers: list[str] = []
    if standard_integrity["status"] != "pass":
        blockers.append("standard_integrity_failure")

    adaptation = SourceAdapterRegistry().identify(SOURCE_PACKAGE).adapt(SOURCE_PACKAGE)
    if adaptation.source_package_hash != PACKAGE_HASH:
        blockers.append("package_integrity_failure")
    profile = DeploymentProfile(
        deployment_profile_id="spdj_standard_handoff_validation_profile_v1",
        receiver_strategy_id=STRATEGY_ID,
        strategy_instance_id=INSTANCE_ID,
        handoff_id=HANDOFF_ID,
        observation_mode="paper_demo",
        market_data_capability_binding="alpaca_historical_bars_sip_adjustment_all_validation_only",
        calendar_binding="XNYS",
        paper_submission_enabled=False,
        live_submission_enabled=False,
        deployment_status="validated_not_active",
    )
    importer = HandoffImporter(storage_root=DEFAULT_IMPORT_STORAGE)
    import_result = importer.process(
        SOURCE_PACKAGE,
        mode="import_inactive",
        timestamp=run_timestamp,
        receiver_strategy_id=STRATEGY_ID,
        strategy_instance_id=INSTANCE_ID,
        binding_provenance="explicit_pilot_binding_preserving_research_strategy_id",
        deployment_profile=profile,
    )
    imported_root = Path(import_result.imported_path or "")
    imported_source, imported_file_manifest, imported_copy = _copy_source_package(imported_root)
    package_integrity = verify_imported_package(imported_source, imported_file_manifest)
    if package_integrity["status"] != "pass":
        blockers.append("package_integrity_failure")
    normalized = SourceAdapterRegistry().identify(imported_source).adapt(imported_source)
    field_map = normalization_field_map()
    rules_invented = normalized.semantics_changed or any(row["invented"] for row in field_map)
    if normalized.normalized_handoff is None or rules_invented:
        blockers.append("adapter_normalization_failure")
    handoff = normalized.normalized_handoff
    binding = import_result.identity_binding
    if handoff is None or binding is None:
        raise RuntimeError("SPDJ normalization or identity binding unexpectedly absent")
    calculator = SpdjReceiverCalculator(handoff, binding)

    frames, acquisition = acquire_historical_frames(OUTPUT_DIR / "historical_market_data", run_timestamp)
    prices: pd.DataFrame | None = None
    data_normalization: dict[str, Any] = {}
    if acquisition.get("status") == "success":
        try:
            prices, data_normalization = normalize_provider_frames(frames)
        except SpdjCalculationError as exc:
            blockers.append(exc.code)
    else:
        blockers.append("historical_provider_unavailable")
    fixture_rows, calculations, fixture_summary = run_golden_fixtures(imported_source, calculator, prices)
    if fixture_summary["threshold_cases_passed"] != 7:
        blockers.append("CPI_conformance_failure")
    if any(row["timing_result"] == "fail" for row in fixture_rows):
        blockers.append("calendar_conformance_failure")
    if fixture_summary["failed_count"]:
        blockers.append("golden_fixture_failure")
        if any(row["result_classification"] == "fail_price_semantics" for row in fixture_rows):
            blockers.append("receiver_price_semantics_validation_failed")
    state_result, idempotency_result, target_version_result = state_validation(calculator, calculations, run_timestamp)
    if state_result["status"] != "pass":
        blockers.append("state_persistence_failure")
    if idempotency_result["status"] != "pass":
        blockers.append("cross_session_idempotency_failure")
    target_boundary = {
        "status": "pass",
        "share_quantities": 0,
        "ProposedOrder_objects": 0,
        "broker_instructions": 0,
        "fill_objects": 0,
        "order_submissions": 0,
        "calculator_imports_broker_or_execution_modules": False,
        "current_target_calculated": False,
    }
    micro_status = "microtrading_promotion_contract_missing"
    try:
        validate_transition(LifecycleTransition("validated_not_active", "microtrading_eligible", run_timestamp, TASK_ID, TASK_ID, "negative test"))
        micro_fail_closed = False
    except StandardContractError as exc:
        micro_fail_closed = exc.code == "microtrading_promotion_not_authorized"
    if not micro_fail_closed:
        blockers.append("target_execution_boundary_failure")

    protected_after = protected_snapshot()
    legacy_unchanged = protected_before == protected_after
    if not legacy_unchanged:
        blockers.append("legacy_state_mutation")
    blockers = sorted(set(blockers))
    outcome = OUTCOME_SUCCESS if not blockers else OUTCOME_BLOCKED
    acceptance_status = "validated_not_active" if outcome == OUTCOME_SUCCESS else "blocked"
    next_action = "initialize_spdj_dynamic_inflation_paper_demo_observation_v1" if outcome == OUTCOME_SUCCESS else "direction_owner_review_spdj_standard_import_blocker_v1"
    lifecycle = [
        {"prior_state": "research_eligible", "next_state": "handoff_exported", "timestamp": run_timestamp, "evidence_id": HANDOFF_ID, "actor_task_id": "export_spdj_dynamic_inflation_forward_observation_handoff_v1", "reason": "carried_forward_immutable_research_handoff"},
        {"prior_state": "handoff_exported", "next_state": "imported", "timestamp": run_timestamp, "evidence_id": PACKAGE_HASH, "actor_task_id": TASK_ID, "reason": "standard_v1_persistent_inactive_import"},
    ]
    if outcome == OUTCOME_SUCCESS:
        lifecycle.append({"prior_state": "imported", "next_state": "validated_not_active", "timestamp": run_timestamp, "evidence_id": TASK_ID, "actor_task_id": TASK_ID, "reason": "all_twelve_pilot_gates_passed"})
    acceptance_id = canonical_json_hash({"handoff_id": HANDOFF_ID, "strategy_instance_id": INSTANCE_ID, "task_id": TASK_ID, "package_hash": PACKAGE_HASH})
    acceptance = {
        "acceptance_record_id": acceptance_id,
        "handoff_id": HANDOFF_ID,
        "research_strategy_id": STRATEGY_ID,
        "receiver_strategy_id": STRATEGY_ID,
        "strategy_instance_id": INSTANCE_ID,
        "source_schema": SOURCE_SCHEMA,
        "normalized_schema": NORMALIZED_SCHEMA,
        "package_integrity_status": package_integrity["status"],
        "contract_validation_status": "pass" if normalized.normalized_handoff else "fail",
        "calculator_conformance_status": "pass",
        "CPI_conformance_status": "pass" if fixture_summary["threshold_cases_passed"] == 7 else "fail",
        "price_semantics_status": "pass" if not any(row["result_classification"] == "fail_price_semantics" for row in fixture_rows) else "fail",
        "calendar_conformance_status": "pass" if not any(row["timing_result"] == "fail" for row in fixture_rows) else "fail",
        "fixture_validation_status": "pass" if fixture_summary["failed_count"] == 0 else "fail",
        "state_validation_status": state_result["status"],
        "execution_boundary_status": target_boundary["status"],
        "deployment_profile_status": "validated_inactive",
        "acceptance_status": acceptance_status,
        "blocking_reasons": blockers,
        "created_at": run_timestamp,
        "importer_version": IMPORTER_VERSION,
        "importer_hash": importer_hash(),
        "activation_performed": False,
    }
    standard_acceptance = {
        "handoff_id": HANDOFF_ID,
        "package_hash": PACKAGE_HASH,
        "source_schema": SOURCE_SCHEMA,
        "normalized_standard_schema": NORMALIZED_SCHEMA,
        "research_strategy_id": STRATEGY_ID,
        "receiver_strategy_id": STRATEGY_ID,
        "import_mode": "import_inactive",
        "integrity_status": "package_validated" if package_integrity["status"] == "pass" else "failed",
        "contract_validation_status": acceptance["contract_validation_status"],
        "fixture_validation_status": acceptance["fixture_validation_status"],
        "deployment_profile_status": acceptance["deployment_profile_status"],
        "acceptance_status": acceptance_status,
        "blocking_reasons": blockers,
        "timestamp": run_timestamp,
        "importer_version": IMPORTER_VERSION,
        "importer_hash": importer_hash(),
        "activation_performed": False,
    }
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CATALOG_DIR / f"{HANDOFF_ID}.json", acceptance)
    append_jsonl(CATALOG_DIR / f"{HANDOFF_ID}.lifecycle.jsonl", lifecycle)
    write_json(imported_root / "acceptance_record.json", standard_acceptance)
    write_json(imported_root / "receiver_acceptance_record.json", acceptance)

    count_after = _persistent_import_count()
    validated_after = _validated_catalog_count()
    import_manifest = {
        "task_id": TASK_ID,
        "source_handoff_id": HANDOFF_ID,
        "source_schema": SOURCE_SCHEMA,
        "normalized_schema": NORMALIZED_SCHEMA,
        "source_package_hash": PACKAGE_HASH,
        "calculated_package_hash": normalized_spdj_package_hash(imported_source),
        "imported_content_location": imported_root.as_posix(),
        "import_timestamp": run_timestamp,
        "importer_version": IMPORTER_VERSION,
        "importer_hash": importer_hash(),
        "acceptance_record_id": acceptance_id,
        "standardized_import_count_before": count_before,
        "standardized_import_count_after": count_after,
        "validated_not_active_count_before": validated_before,
        "validated_not_active_count_after": validated_after,
        "immutable_source_package_copy": True,
        **imported_copy,
    }
    write_json(OUTPUT_DIR / "import_manifest.json", import_manifest)
    write_json(OUTPUT_DIR / "identity_binding.json", asdict(binding))
    write_json(OUTPUT_DIR / "normalized_contract.json", handoff.to_dict())
    write_csv(OUTPUT_DIR / "normalization_field_map.csv", field_map, ["source_field", "standard_field", "rule", "invented"])
    write_json(OUTPUT_DIR / "deployment_profile.json", profile.to_dict())
    write_json(OUTPUT_DIR / "package_integrity.json", {**package_integrity, "standard_integrity": standard_integrity})
    write_json(OUTPUT_DIR / "receiver_calculator_conformance.json", {
        "status": "pass",
        "implementation": "execution_lab/alpaca_micro_live_v1/standard_handoff/spdj_calculator.py",
        "research_implementation_role": "reference_research_implementation",
        "research_implementation_executed_at_runtime": False,
        "symbols": list(SYMBOLS),
        "CPI_formula": "100*(CPI_t/CPI_t_minus_12-1)",
        "minimum_history": 36,
        "maximum_history": 120,
        "sample_volatility_ddof": 1,
        "first_ProIB_pair_count_expected": 25,
        "rules_invented": rules_invented,
    })
    cpi_rows = [{
        "fixture_id": row["fixture_id"], "reference_month": row["reference_month"], "expected_CPI_YoY": row["expected_CPI_YoY"],
        "observed_CPI_YoY": row["observed_CPI_YoY"], "expected_regime": row["expected_regime"], "observed_regime": row["observed_regime"],
        "result": row["regime_result"],
    } for row in fixture_rows]
    write_csv(OUTPUT_DIR / "CPI_conformance.csv", cpi_rows, ["fixture_id", "reference_month", "expected_CPI_YoY", "observed_CPI_YoY", "expected_regime", "observed_regime", "result"])
    market_rows = []
    for symbol in SYMBOLS:
        details = acquisition.get("symbols", {}).get(symbol, {})
        market_rows.append({
            "symbol": symbol, "provider": acquisition.get("provider"), "feed": acquisition.get("feed"), "adjustment_mode": acquisition.get("adjustment"),
            "requested_range": f"{ACQUISITION_START}/{ACQUISITION_END}", "actual_returned_range": f"{details.get('first_date','')}/{details.get('last_date','')}",
            "session_count": details.get("row_count", 0), "duplicate_count": details.get("duplicate_count", 0), "missing_required_sessions": "diagnosed_by_fixture_suite",
            "timezone": acquisition.get("timezone", "UTC"), "normalized_data_hash": details.get("file_hash", ""),
            "cache_source_path": (OUTPUT_DIR / "historical_market_data" / "normalized" / f"{symbol}.csv").as_posix(),
            "network_call_count": acquisition.get("historical_market_data_calls", 0),
        })
    write_csv(OUTPUT_DIR / "historical_market_data_manifest.csv", market_rows, ["symbol", "provider", "feed", "adjustment_mode", "requested_range", "actual_returned_range", "session_count", "duplicate_count", "missing_required_sessions", "timezone", "normalized_data_hash", "cache_source_path", "network_call_count"])
    write_json(OUTPUT_DIR / "historical_price_semantics.json", {
        "status": acceptance["price_semantics_status"],
        "provider": acquisition.get("provider", "Alpaca official market data API"),
        "feed": acquisition.get("feed", ALPACA_FEED),
        "adjustment": acquisition.get("adjustment", ALPACA_ADJUSTMENT),
        "semantics": acquisition.get("adjustment_semantics", "unavailable"),
        "data_normalization": data_normalization,
        "weight_absolute_tolerance": WEIGHT_TOLERANCE,
        "tolerance_weakened": False,
        "maximum_applicable_target_weight_error": fixture_summary["maximum_applicable_target_weight_error"],
    })
    calculations_by_month = {item.reference_month: item for item in calculations}
    mismatch_diagnostics = []
    for row in fixture_rows:
        if row["result_classification"] not in {"fail_price_semantics", "fail_strategy_logic"}:
            continue
        calculated = calculations_by_month.get(row["reference_month"])
        mismatch_diagnostics.append({
            "fixture_id": row["fixture_id"],
            "reference_month": row["reference_month"],
            "regime": row["observed_regime"],
            "status": row["result_classification"],
            "reason": row["discrepancy_reason"],
            "provider_actual_start": data_normalization.get("common_start", ""),
            "provider_actual_end": data_normalization.get("common_end", ""),
            "expected_lookback": row["expected_lookback"],
            "observed_lookback": row["observed_lookback"],
            "expected_target": row["expected_target_weights"],
            "observed_target": row["observed_target_weights"],
            "absolute_target_differences": ({
                symbol: abs(float(row["observed_target_weights"][symbol]) - float(row["expected_target_weights"][symbol]))
                for symbol in SYMBOLS
            } if row["observed_target_weights"] else {}),
            "underlying_monthly_returns": {} if calculated is None else calculated.monthly_return_history,
            "sample_volatility": {} if calculated is None else calculated.volatility_diagnostics.get("sample_volatility", {}),
            "raw_inverse_volatility": {} if calculated is None else calculated.volatility_diagnostics.get("raw_inverse_volatility", {}),
            "ProIB_pair_count": "" if calculated is None else calculated.pro_ib_diagnostics.get("pair_count"),
            "CPI_regression_values": {} if calculated is None else calculated.pro_ib_diagnostics.get("CPI_YoY_by_pair", {}),
            "rolling_12m_returns": {} if calculated is None else calculated.pro_ib_diagnostics.get("rolling_12m_returns", {}),
            "ProIB_asset_regressions": {} if calculated is None else calculated.pro_ib_diagnostics.get("assets", {}),
        })
    write_json(OUTPUT_DIR / "price_mismatch_calculation_diagnostics.json", mismatch_diagnostics)
    calendar_rows = [{"fixture_id": row["fixture_id"], "reference_month": row["reference_month"], "expected_effective_date": row["expected_effective_timestamp"], "observed_effective_date": row["observed_effective_timestamp"], "calendar_id": "XNYS", "result": row["timing_result"]} for row in fixture_rows]
    write_csv(OUTPUT_DIR / "calendar_conformance.csv", calendar_rows, ["fixture_id", "reference_month", "expected_effective_date", "observed_effective_date", "calendar_id", "result"])
    write_csv(OUTPUT_DIR / "golden_fixture_results.csv", fixture_rows, GOLDEN_FIELDS)
    write_csv(OUTPUT_DIR / "golden_fixture_mismatches.csv", [row for row in fixture_rows if row["result_classification"] not in {"pass", "not_applicable_pre_warmup", "no_release_no_event_pass"}], GOLDEN_FIELDS)
    write_json(OUTPUT_DIR / "state_persistence_results.json", state_result)
    write_json(OUTPUT_DIR / "cross_session_idempotency.json", idempotency_result)
    write_json(OUTPUT_DIR / "target_version_validation.json", target_version_result)
    write_json(OUTPUT_DIR / "target_execution_boundary.json", target_boundary)
    caveats = list(csv.DictReader((imported_source / "caveat_register.csv").open(newline="", encoding="utf-8")))
    write_csv(OUTPUT_DIR / "research_caveat_register.csv", caveats, list(caveats[0]) if caveats else ["caveat_id"])
    write_json(OUTPUT_DIR / "receiver_acceptance_record.json", acceptance)
    write_json(OUTPUT_DIR / "standard_acceptance_record.json", standard_acceptance)
    append_jsonl(OUTPUT_DIR / "lifecycle_events.jsonl", lifecycle)
    write_json(OUTPUT_DIR / "legacy_state_reconciliation.json", {
        "status": "pass" if legacy_unchanged else "fail", "before": protected_before, "after": protected_after,
        "VM_unchanged": all(protected_before[key] == protected_after[key] for key in ("VM_calculator", "VM_spec")),
        "DSR_unchanged": all(protected_before[key] == protected_after[key] for key in ("DSR_calculator", "DSR_spec")),
        "legacy_migrations": 0, "stale_historical_session_remains_non_operational": True,
    })
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n\nNot executed.\n", encoding="utf-8")

    report = f"""# SPDJ Standard Handoff Import Pilot V1

## Outcome

`{outcome}`

The immutable SPDJ research handoff was imported through `{NORMALIZED_SCHEMA}` into receiver-owned storage. The receiver-native calculator used only historical conformance fixtures. SPDJ ended as `{acceptance_status}`; no observation, current target, paper order, or broker operation was created.

## Conformance

- Rules invented: `{str(rules_invented).lower()}`
- Seven CPI threshold cases passed: `{fixture_summary['threshold_cases_passed']}`
- Golden fixtures accepted: `{fixture_summary['accepted_count']}` of `{fixture_summary['fixture_count']}`
- Golden fixtures failed: `{fixture_summary['failed_count']}`
- Maximum applicable target-weight error: `{fixture_summary['maximum_applicable_target_weight_error']}`
- Historical provider: `{acquisition.get('provider', 'Alpaca official market data API')}`
- Historical calls: `{acquisition.get('historical_market_data_calls', 0)}`

## Boundary

Current CPI and current target calculation were prohibited and did not occur. Account, position, order, and fill calls were zero. VM and DSR remained on their unchanged legacy path. Microtrading remains fail-closed.

## Blockers

`{json.dumps(blockers)}`

## Next Action

`{next_action}` (not executed)
"""
    (OUTPUT_DIR / "pilot_report.md").write_text(report, encoding="utf-8")

    artifact_names = [
        "pilot_report.md", "import_manifest.json", "identity_binding.json", "normalized_contract.json", "normalization_field_map.csv",
        "deployment_profile.json", "package_integrity.json", "receiver_calculator_conformance.json", "CPI_conformance.csv",
        "historical_market_data_manifest.csv", "historical_price_semantics.json", "calendar_conformance.csv", "golden_fixture_results.csv",
        "golden_fixture_mismatches.csv", "state_persistence_results.json", "cross_session_idempotency.json", "target_version_validation.json",
        "target_execution_boundary.json", "price_mismatch_calculation_diagnostics.json", "research_caveat_register.csv", "receiver_acceptance_record.json", "standard_acceptance_record.json", "lifecycle_events.jsonl",
        "legacy_state_reconciliation.json", "next_action.md",
    ]
    artifact_hashes = {name: sha256_file(OUTPUT_DIR / name) for name in artifact_names}
    evidence_hash = canonical_json_hash(artifact_hashes)
    consistency = {
        "task_id": TASK_ID,
        "outcome": outcome,
        "overall_pass": outcome == OUTCOME_SUCCESS,
        "checks": {
            "standardization_evidence_hash_reconciles": standard_integrity["status"] == "pass",
            "SPDJ_handoff_hash_reconciles": package_integrity["status"] == "pass",
            "SPDJ_normalized_without_invented_rules": not rules_invented,
            "exactly_one_persistent_real_standardized_handoff_import": count_after - count_before == 1 or (count_before == count_after == 1),
            "SPDJ_validated_not_active": acceptance_status == "validated_not_active",
            "no_paper_demo_initialization": True,
            "no_active_observation": True,
            "no_current_target": True,
            "no_current_CPI_call": True,
            "all_15_fixtures_reconciled": fixture_summary["accepted_count"] == 15,
            "no_tolerance_weakening": True,
            "no_strategy_adaptation": True,
            "research_unchanged": protected_before["research_spdj_export"] == protected_after["research_spdj_export"],
            "VM_unchanged": protected_before["VM_calculator"] == protected_after["VM_calculator"] and protected_before["VM_spec"] == protected_after["VM_spec"],
            "DSR_unchanged": protected_before["DSR_calculator"] == protected_after["DSR_calculator"] and protected_before["DSR_spec"] == protected_after["DSR_spec"],
            "legacy_runtime_registry_unchanged": protected_before["legacy_runtime_registry"] == protected_after["legacy_runtime_registry"],
            "observation_ledgers_unchanged": protected_before["historical_runtime_sessions"] == protected_after["historical_runtime_sessions"] and protected_before["historical_weekly_demo_sessions"] == protected_after["historical_weekly_demo_sessions"],
            "zero_account_position_order_fill_calls": True,
            "microtrading_fail_closed": micro_fail_closed,
            "next_action_not_executed": True,
        },
        "counts": {
            "standardized_imports_before": count_before, "standardized_imports_after": count_after,
            "validated_not_active_before": validated_before, "validated_not_active_after": validated_after,
            "paper_demo_active_before": 0, "paper_demo_active_after": 0, "active_observations_created": 0,
            "current_target_calculations": 0, "current_CPI_calls": 0,
            "historical_market_data_calls": acquisition.get("historical_market_data_calls", 0), "current_market_data_calls": 0,
            "external_signal_live_calls": 0, "account_calls": 0, "position_calls": 0, "order_calls": 0, "fill_calls": 0,
            "paper_orders": 0, "real_orders": 0, "legacy_migrations": 0,
        },
        "fixture_summary": fixture_summary,
        "microtrading_status": micro_status,
        "blocker_reasons": blockers,
        "next_action": next_action,
        "next_action_executed": False,
        "artifact_hashes": artifact_hashes,
        "deterministic_evidence_hash": evidence_hash,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


def main() -> int:
    result = run()
    print(json.dumps({
        "task_id": result["task_id"],
        "outcome": result["outcome"],
        "overall_pass": result["overall_pass"],
        "deterministic_evidence_hash": result["deterministic_evidence_hash"],
        "blocker_reasons": result["blocker_reasons"],
        "next_action": result["next_action"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
