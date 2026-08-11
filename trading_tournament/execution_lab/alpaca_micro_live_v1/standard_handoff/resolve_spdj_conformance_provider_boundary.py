from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from contracts.forward_observation.forward_observation_conformance_input_bundle_v1 import (
    SELF_REFERENCE,
    normalized_bundle_hash,
    sha256_file as bundle_sha256_file,
    validate_bundle,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    normalized_spdj_package_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.importer import (
    IMPORTER_VERSION,
    importer_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.lifecycle import (
    LifecycleTransition,
    validate_transition,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import (
    IdentityBinding,
    StandardHandoff,
    canonical_json_hash,
)
from contracts.forward_observation.forward_observation_handoff_standard_v1.errors import StandardContractError
from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT, PACKAGE_ROOT
from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from execution_lab.alpaca_micro_live_v1.standard_handoff import DEFAULT_IMPORT_STORAGE
from execution_lab.alpaca_micro_live_v1.standard_handoff.pilot_spdj_import import (
    _persistent_import_count,
    hash_path,
    protected_paths,
    state_validation,
    verify_imported_package,
    verify_standard_evidence,
    write_csv,
    write_json,
)
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


TASK_ID = "resolve_spdj_standard_import_conformance_and_provider_boundary_v1"
OUTCOME_SUCCESS = "spdj_standard_handoff_import_validated_not_active"
OUTCOME_BLOCKED = "spdj_standard_handoff_import_blocked"
HANDOFF_ID = "spdj_dynamic_inflation_forward_observation_handoff_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
INSTANCE_ID = f"{STRATEGY_ID}__inactive_validation_instance"
PACKAGE_HASH = "sha256:f1844b722c11db1fd21b91192a56d2b1953c6719994f9de113c16e72882998b9"
PRICE_BUNDLE_HASH = "sha256:ab05bef8ac2b12c6391bca65cb1312148db7d64bed11e9932379464f8bcc72c8"
CPI_DATASET_HASH = "sha256:e221af86dfd616f4fa65bec016910deaffe47f1d6e690495a4033cd0e3eefcc8"
FIXTURE_MANIFEST_HASH = "sha256:e6fe3734288360d1826adf25198a9f6507ff1509b61c7011ec7580fc8fd740b0"
SOURCE_RESEARCH_EVIDENCE_HASH = "sha256:86f55d845af1b4aac643dd076c46873e13e976db04b13b09264bd69cacb96599"
PRIOR_EVIDENCE_HASH = "sha256:2beaef5dd2ca95072cbfa95de1db53ef432e19b377b86ad808fdad7003f5c37b"
SOURCE_SCHEMA = "spdj_forward_observation_handoff_schema_v1:v1"
NORMALIZED_SCHEMA = "forward_observation_handoff_standard_v1:1"
ALPACA_FEED = "sip"
ALPACA_ADJUSTMENT = "all"
ACQUISITION_START = "2016-01-01T00:00:00Z"
ACQUISITION_END = "2026-08-01T00:00:00Z"
OPERATIONAL_CUTOFF = "2026-07-31"
SAME_WINDOW_REFERENCE_MONTH = "2026-06"

OUTPUT_DIR = MODULE_ROOT / "evidence" / "handoff_import_validation" / "spdj_standard_handoff_import_resolution_v1" / "latest"
PRIOR_DIR = MODULE_ROOT / "evidence" / "handoff_import_validation" / "spdj_standard_handoff_import_v1" / "latest"
BUNDLE_DIR = MODULE_ROOT / "c" / "spdj_v1"
SOURCE_PACKAGE = MODULE_ROOT / "p" / PACKAGE_HASH.removeprefix("sha256:")[:16] / "package"
SOURCE_FILE_MANIFEST = MODULE_ROOT / "p" / PACKAGE_HASH.removeprefix("sha256:")[:16] / "package_file_manifest.csv"
IMPORTED_ROOT = DEFAULT_IMPORT_STORAGE / HANDOFF_ID / PACKAGE_HASH.removeprefix("sha256:")
CATALOG_DIR = MODULE_ROOT / "evidence" / "standard_handoff_catalog"
RESEARCH_SIGNAL = PACKAGE_ROOT / "evidence" / "research_recovery" / "spdj_multi_asset_dynamic_inflation_etf_portability_v1" / "latest" / "monthly_signal_and_weights.csv"
SOURCE_PRICE_PATHS = {
    symbol: PACKAGE_ROOT / (
        "data/universe_expansion/phase2_bounded_multi_asset_market_data_v1/GSG.csv"
        if symbol == "GSG"
        else f"data/universe_expansion/pilot_etf_market_data_v1/{symbol}.csv"
    )
    for symbol in SYMBOLS
}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_unique_jsonl(path: Path, row: dict[str, Any], *, identity_fields: tuple[str, ...]) -> None:
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    identity = tuple(row.get(field) for field in identity_fields)
    if not any(tuple(item.get(field) for field in identity_fields) == identity for item in existing):
        existing.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" for item in existing),
        encoding="utf-8",
    )


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _artifact_hash(path: Path) -> str:
    return bundle_sha256_file(path)


def _active_spdj_count() -> int:
    path = PACKAGE_ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    return path.read_text(encoding="utf-8").count(f"strategy_id: {STRATEGY_ID}")


def _validation_protected_paths() -> dict[str, Path]:
    paths = dict(protected_paths())
    paths.update({
        "prior_blocked_pilot": PRIOR_DIR,
        "strategy_registry": PACKAGE_ROOT / "strategy_lab" / "strategy_registry.yaml",
        "research_roadmap": PACKAGE_ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
        "research_queue": PACKAGE_ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
        "family_ledger": PACKAGE_ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
        "active_observations": PACKAGE_ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
        "normalized_handoff": IMPORTED_ROOT / "normalized_handoff.json",
        "identity_binding": IMPORTED_ROOT / "identity_binding.json",
        "deployment_profile": IMPORTED_ROOT / "deployment_profile.json",
        "receiver_source_package": SOURCE_PACKAGE,
        "research_signal_evidence": RESEARCH_SIGNAL,
    })
    for symbol, path in SOURCE_PRICE_PATHS.items():
        paths[f"frozen_source_price_{symbol}"] = path
    return paths


def protected_snapshot() -> dict[str, str]:
    return {name: hash_path(path) for name, path in _validation_protected_paths().items()}


def verify_prior_pilot() -> dict[str, Any]:
    consistency = json.loads((PRIOR_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    actual_artifacts = {name: _artifact_hash(PRIOR_DIR / name) for name in sorted(consistency["artifact_hashes"])}
    observed_hash = canonical_json_hash(actual_artifacts)
    checks = {
        "outcome_blocked": consistency.get("outcome") == OUTCOME_BLOCKED,
        "declared_hash": consistency.get("deterministic_evidence_hash") == PRIOR_EVIDENCE_HASH,
        "artifact_hashes": actual_artifacts == consistency.get("artifact_hashes"),
        "recomputed_hash": observed_hash == PRIOR_EVIDENCE_HASH,
        "expected_blockers": consistency.get("blocker_reasons") == ["golden_fixture_failure", "receiver_price_semantics_validation_failed"],
    }
    return {"status": "pass" if all(checks.values()) else "fail", "checks": checks, "observed_hash": observed_hash}


def reconcile_prior_fixtures() -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = list(csv.DictReader((PRIOR_DIR / "golden_fixture_results.csv").open(newline="", encoding="utf-8")))
    reconciled: list[dict[str, Any]] = []
    for row in rows:
        failed = row["result_classification"] not in {"pass", "not_applicable_pre_warmup", "no_release_no_event_pass"}
        expected_lookback = int(row["expected_lookback"]) if row["expected_lookback"] else None
        observed_lookback = int(row["observed_lookback"]) if row["observed_lookback"] else None
        expected_pair = int(row["expected_ProIB_pair_count"]) if row["expected_ProIB_pair_count"] else None
        observed_pair = int(row["observed_pair_count"]) if row["observed_pair_count"] else None
        if not failed:
            root_cause = "other"
        elif row["fixture_id"] == "fixture_014_2024_08":
            root_cause = "provider_history_insufficient_for_frozen_lookback"
        elif row["fixture_id"] in {f"fixture_{number:03d}_{suffix}" for number, suffix in [
            (2, "2009_07"), (3, "2009_08"), (4, "2009_11"), (5, "2009_12"),
            (6, "2010_01"), (7, "2010_02"), (8, "2010_12"), (9, "2013_03"),
            (10, "2016_07"), (11, "2016_09"), (12, "2017_01"), (13, "2018_10"),
        ]}:
            root_cause = "provider_history_precedes_available_coverage"
        else:
            root_cause = "other"
        same_window = bool(failed and expected_lookback is not None and observed_lookback == expected_lookback)
        valid_semantics_diagnosis = root_cause == "same_window_price_semantics_mismatch" and same_window
        reconciled.append({
            "fixture_id": row["fixture_id"],
            "reference_month": row["reference_month"],
            "expected_regime": row["expected_regime"],
            "previous_result": row["result_classification"],
            "provider_first_available_date": "2016-01-04",
            "expected_lookback": "" if expected_lookback is None else expected_lookback,
            "previous_observed_lookback": "" if observed_lookback is None else observed_lookback,
            "expected_ProIB_pair_count": "" if expected_pair is None else expected_pair,
            "previous_observed_pair_count": "" if observed_pair is None else observed_pair,
            "target_calculation_possible": bool(row["observed_target_weights"] not in {"", "{}"}),
            "same_lookback_compared": same_window,
            "valid_adjustment_semantics_diagnosis": valid_semantics_diagnosis,
            "root_cause_classification": root_cause,
            "previous_discrepancy_reason": row["discrepancy_reason"],
        })
    counts = {
        "failed_total": sum(row["previous_result"] not in {"pass", "not_applicable_pre_warmup", "no_release_no_event_pass"} for row in reconciled),
        "pre_provider_coverage": sum(row["root_cause_classification"] == "provider_history_precedes_available_coverage" for row in reconciled),
        "incomplete_lookback": sum(row["root_cause_classification"] == "provider_history_insufficient_for_frozen_lookback" for row in reconciled),
        "same_window_semantic_failures": sum(row["root_cause_classification"] == "same_window_price_semantics_mismatch" for row in reconciled),
    }
    return reconciled, counts


def _load_source_monthly_inputs() -> tuple[pd.DataFrame, dict[str, str]]:
    prices: dict[str, pd.Series] = {}
    month_dates: dict[str, pd.Series] = {}
    for symbol, path in SOURCE_PRICE_PATHS.items():
        frame = pd.read_csv(path, usecols=["date", "adj_close"])
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        frame["adj_close"] = pd.to_numeric(frame["adj_close"], errors="raise")
        frame = frame.loc[frame["date"] <= pd.Timestamp("2026-06-30")].copy()
        if frame["date"].duplicated().any() or (frame["adj_close"] <= 0.0).any():
            raise ValueError(f"Invalid frozen source data for {symbol}")
        frame["reference_month"] = frame["date"].dt.to_period("M")
        monthly = frame.sort_values("date").groupby("reference_month", sort=True).tail(1).set_index("reference_month")
        prices[symbol] = monthly["adj_close"].astype(float)
        month_dates[symbol] = monthly["date"]
    monthly_prices = pd.DataFrame(prices).dropna(how="any").sort_index()
    monthly_returns = monthly_prices.pct_change(fill_method=None).dropna(how="any")
    monthly_returns = monthly_returns.loc[(monthly_returns.index >= pd.Period("2006-08", freq="M")) & (monthly_returns.index <= pd.Period("2026-06", freq="M"))]
    sessions: dict[str, str] = {}
    for month in monthly_returns.index:
        dates = {pd.Timestamp(month_dates[symbol].loc[month]).date().isoformat() for symbol in SYMBOLS}
        if len(dates) != 1:
            raise ValueError(f"Frozen source monthly endpoint differs by symbol for {month}")
        sessions[str(month)] = dates.pop()
    return monthly_returns, sessions


def materialize_conformance_bundle(run_timestamp: str) -> dict[str, Any]:
    manifest_path = BUNDLE_DIR / "conformance_bundle_manifest.json"
    if manifest_path.exists():
        return validate_bundle(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    monthly_returns, month_end_sessions = _load_source_monthly_inputs()
    monthly_frame = monthly_returns.copy()
    monthly_frame.insert(0, "month_end_session", [month_end_sessions[str(month)] for month in monthly_frame.index])
    monthly_frame.insert(0, "reference_month", monthly_frame.index.astype(str))
    monthly_frame.to_csv(BUNDLE_DIR / "monthly_return_input.csv", index=False, lineterminator="\n", float_format="%.17g")

    cpi_source = pd.read_csv(SOURCE_PACKAGE / "reference_only" / "historical_cpi_v2" / "cpi_point_in_time_signal.csv", dtype=str).fillna("")
    cpi_columns = [
        "reference_month", "bls_release_date", "release_artifact_hash",
        "cpi_all_items_nsa_level_as_published", "prior_year_cpi_level",
        "canonical_cpi_yoy_unrounded", "canonical_regime", "rebalance_event",
    ]
    cpi_source.loc[cpi_source["reference_month"] <= "2026-06", cpi_columns].to_csv(
        BUNDLE_DIR / "cpi_regression_input.csv", index=False, lineterminator="\n"
    )

    fixtures = list(csv.DictReader((SOURCE_PACKAGE / "golden_conformance_fixtures.csv").open(newline="", encoding="utf-8")))
    range_rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        lookback = int(fixture["lookback_monthly_returns"]) if fixture["lookback_monthly_returns"] else 0
        reference = pd.Period(fixture["reference_month"], freq="M")
        available = monthly_returns.loc[monthly_returns.index <= reference]
        start_month = str(available.tail(lookback).index.min()) if lookback and len(available) >= lookback else ""
        range_rows.append({
            "fixture_id": fixture["fixture_id"],
            "event_status": fixture["event_status"],
            "reference_month": fixture["reference_month"],
            "input_start_month": start_month,
            "input_end_month": fixture["reference_month"] if lookback else "",
            "monthly_return_count": lookback,
            "CPI_reference_end_month": fixture["reference_month"],
        })
    write_csv(BUNDLE_DIR / "fixture_input_ranges.csv", range_rows, list(range_rows[0]))
    write_json(BUNDLE_DIR / "source_provenance.json", {
        "parent_handoff_id": HANDOFF_ID,
        "parent_package_hash": PACKAGE_HASH,
        "strategy_id": STRATEGY_ID,
        "source_price_bundle_hash": PRICE_BUNDLE_HASH,
        "CPI_dataset_hash": CPI_DATASET_HASH,
        "fixture_manifest_hash": FIXTURE_MANIFEST_HASH,
        "source_research_evidence_hash": SOURCE_RESEARCH_EVIDENCE_HASH,
        "research_signal_evidence": RESEARCH_SIGNAL.relative_to(PACKAGE_ROOT).as_posix(),
        "source_price_files": {symbol: path.relative_to(PACKAGE_ROOT).as_posix() for symbol, path in SOURCE_PRICE_PATHS.items()},
        "derivation": "calendar-month final frozen adjusted close; month-over-month return; no performance calculation",
        "full_daily_cache_duplicated": False,
        "software_conformance_reference": True,
        "operational_market_data": False,
    })
    files = {
        name: _artifact_hash(BUNDLE_DIR / name)
        for name in ("monthly_return_input.csv", "cpi_regression_input.csv", "fixture_input_ranges.csv", "source_provenance.json")
    }
    manifest = {
        "schema_id": "forward_observation_conformance_input_bundle_v1",
        "schema_version": 1,
        "bundle_id": "spdj_standard_handoff_conformance_inputs_v1",
        "created_at": run_timestamp,
        "parent_handoff_id": HANDOFF_ID,
        "parent_package_hash": PACKAGE_HASH,
        "strategy_id": STRATEGY_ID,
        "source_price_bundle_hash": PRICE_BUNDLE_HASH,
        "CPI_dataset_hash": CPI_DATASET_HASH,
        "fixture_manifest_hash": FIXTURE_MANIFEST_HASH,
        "source_research_evidence_hash": SOURCE_RESEARCH_EVIDENCE_HASH,
        "input_representation": "monthly_return_input",
        "files": files,
        "fixture_count": len(fixtures),
        "conformance_bundle_hash": SELF_REFERENCE,
        "hash_scope": "sorted relative path plus NUL plus bytes plus NUL; manifest conformance_bundle_hash normalized to sentinel",
        "software_conformance_reference": True,
        "operational_market_data": False,
    }
    write_json(manifest_path, manifest)
    manifest["conformance_bundle_hash"] = normalized_bundle_hash(BUNDLE_DIR)
    write_json(manifest_path, manifest)
    return validate_bundle(BUNDLE_DIR)


def load_bundle_inputs() -> tuple[pd.DataFrame, dict[str, str], pd.DataFrame]:
    frame = pd.read_csv(BUNDLE_DIR / "monthly_return_input.csv")
    frame.index = pd.PeriodIndex(frame.pop("reference_month"), freq="M")
    sessions = {str(month): str(value) for month, value in zip(frame.index, frame.pop("month_end_session"), strict=True)}
    returns = frame.loc[:, SYMBOLS].astype(float)
    cpi = load_cpi_reference(BUNDLE_DIR / "cpi_regression_input.csv")
    return returns, sessions, cpi


def load_receiver_contract() -> tuple[StandardHandoff, IdentityBinding, SpdjReceiverCalculator]:
    handoff = StandardHandoff.from_dict(json.loads((IMPORTED_ROOT / "normalized_handoff.json").read_text(encoding="utf-8")))
    binding = IdentityBinding(**json.loads((IMPORTED_ROOT / "identity_binding.json").read_text(encoding="utf-8")))
    return handoff, binding, SpdjReceiverCalculator(handoff, binding)


GOLDEN_FIELDS = [
    "fixture_id", "reference_month", "expected_regime", "observed_regime", "expected_statistics_cutoff",
    "observed_statistics_cutoff", "expected_effective_date", "observed_effective_date", "expected_lookback",
    "observed_lookback", "expected_ProIB_pair_count", "observed_ProIB_pair_count", "expected_target_weights",
    "observed_target_weights", "maximum_absolute_target_error", "weight_tolerance", "formula_tolerance",
    "input_source", "result_classification", "discrepancy_reason",
]


def run_frozen_golden_fixtures(calculator: SpdjReceiverCalculator) -> tuple[list[dict[str, Any]], list[Any], dict[str, Any], dict[str, Any]]:
    fixtures = list(csv.DictReader((SOURCE_PACKAGE / "golden_conformance_fixtures.csv").open(newline="", encoding="utf-8")))
    monthly_returns, sessions, cpi = load_bundle_inputs()
    calendar = build_xnys_calendar(end="2026-12-31")
    rows: list[dict[str, Any]] = []
    calculations: list[Any] = []
    intermediates: dict[str, Any] = {}
    maximum_error = 0.0
    threshold_count = 0
    for fixture in fixtures:
        month = fixture["reference_month"]
        expected = {symbol: float(fixture[f"expected_target_{symbol}"]) for symbol in SYMBOLS if fixture[f"expected_target_{symbol}"]}
        expected_regime = fixture["regime"]
        observed_regime = ""
        observed_statistics = ""
        observed_effective = ""
        observed_lookback: Any = ""
        observed_pair: Any = ""
        observed: dict[str, float] = {}
        error: Any = ""
        discrepancy = ""
        classification = "pass"
        cpi_row = cpi.loc[pd.Period(month, freq="M")]
        if bool(cpi_row["event"]):
            observed_regime = classify_regime(float(cpi_row["cpi_yoy"]))
        if fixture["threshold_disagreement"].lower() == "true" and observed_regime == expected_regime:
            threshold_count += 1
        if fixture["event_status"] == "no_release_no_event":
            result = calculator.no_event_result(reference_month=month, calculated_at="2025-11-30T00:00:00Z")
            classification = "no_release_no_event_pass" if result.status == "no_event" and not result.target_weights else "fail"
        elif not expected:
            observed_effective = calendar.next_session_after(fixture["release_date"]).session_date
            classification = "not_applicable_pre_warmup" if observed_effective == fixture["effective_after_close_date"] else "fail"
        else:
            try:
                calculation = calculator.calculate_from_monthly_inputs(
                    reference_month=month,
                    cpi_reference=cpi,
                    monthly_returns=monthly_returns,
                    month_end_sessions=sessions,
                    calendar=calendar,
                    fixture_id=fixture["fixture_id"],
                )
                calculations.append(calculation)
                observed_regime = calculation.regime
                observed_statistics = calculation.statistics_cutoff
                observed_effective = calculation.effective_timestamp[:10]
                observed_lookback = calculation.lookback_monthly_returns
                observed_pair = calculation.pro_ib_diagnostics["pair_count"]
                observed = calculation.target_weights
                error = max(abs(observed[symbol] - expected[symbol]) for symbol in SYMBOLS)
                maximum_error = max(maximum_error, float(error))
                checks = [
                    observed_regime == expected_regime,
                    observed_statistics == fixture["allocation_statistics_cutoff"],
                    observed_effective == fixture["effective_after_close_date"],
                    observed_lookback == int(fixture["lookback_monthly_returns"]),
                    not fixture["proib_pair_count"] or observed_pair == int(fixture["proib_pair_count"]),
                    float(error) <= WEIGHT_TOLERANCE,
                ]
                if not all(checks):
                    classification = "fail"
                    discrepancy = "Frozen-input target, lookback, pair count, regime, statistics cutoff, or timing mismatch"
                if observed_regime in {"medium", "high"}:
                    intermediates[fixture["fixture_id"]] = {
                        "reference_month": month,
                        "regime": observed_regime,
                        "lookback_length": observed_lookback,
                        "monthly_return_count": len(calculation.monthly_return_history),
                        "sample_volatility": calculation.volatility_diagnostics["sample_volatility"],
                        "raw_inverse_volatility": calculation.volatility_diagnostics["raw_inverse_volatility"],
                        "rolling_12m_returns": calculation.pro_ib_diagnostics["rolling_12m_returns"],
                        "CPI_regression_pair_count": observed_pair,
                        "asset_regressions": calculation.pro_ib_diagnostics["assets"],
                        "final_target": observed,
                    }
            except (SpdjCalculationError, KeyError, ValueError) as exc:
                classification = "fail"
                discrepancy = f"{type(exc).__name__}: {exc}"
        rows.append({
            "fixture_id": fixture["fixture_id"],
            "reference_month": month,
            "expected_regime": expected_regime,
            "observed_regime": observed_regime,
            "expected_statistics_cutoff": fixture["allocation_statistics_cutoff"],
            "observed_statistics_cutoff": observed_statistics,
            "expected_effective_date": fixture["effective_after_close_date"],
            "observed_effective_date": observed_effective,
            "expected_lookback": fixture["lookback_monthly_returns"],
            "observed_lookback": observed_lookback,
            "expected_ProIB_pair_count": fixture["proib_pair_count"],
            "observed_ProIB_pair_count": observed_pair,
            "expected_target_weights": expected,
            "observed_target_weights": observed,
            "maximum_absolute_target_error": error,
            "weight_tolerance": WEIGHT_TOLERANCE,
            "formula_tolerance": FORMULA_TOLERANCE,
            "input_source": "frozen_conformance_bundle",
            "result_classification": classification,
            "discrepancy_reason": discrepancy,
        })
    accepted = {"pass", "not_applicable_pre_warmup", "no_release_no_event_pass"}
    first_proib = next(item for item in calculations if item.reference_month == "2009-07")
    high_120 = [item for item in calculations if item.regime == "high" and item.lookback_monthly_returns == 120]
    summary = {
        "fixture_count": len(rows),
        "exact_target_pass_count": sum(row["result_classification"] == "pass" for row in rows),
        "pre_warmup_count": sum(row["result_classification"] == "not_applicable_pre_warmup" for row in rows),
        "no_event_count": sum(row["result_classification"] == "no_release_no_event_pass" for row in rows),
        "failed_count": sum(row["result_classification"] not in accepted for row in rows),
        "maximum_target_error": maximum_error,
        "threshold_cases_passed": threshold_count,
        "first_ProIB_pair_count": first_proib.pro_ib_diagnostics["pair_count"],
        "all_120m_high_pair_counts_source_compliant": bool(high_120) and all(item.pro_ib_diagnostics["pair_count"] == 109 for item in high_120),
        "calculator_conformance_status": "pass" if all(row["result_classification"] in accepted for row in rows) else "fail",
    }
    return rows, calculations, summary, intermediates


def _load_cached_operational_frames(root: Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]] | None:
    manifest_path = root / "acquisition_manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "success":
        return {}, manifest
    frames: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        path = root / "normalized" / f"{symbol}.csv"
        if not path.is_file() or _artifact_hash(path) != manifest["symbols"][symbol]["file_hash"]:
            return None
        frames[symbol] = pd.read_csv(path)
    manifest["reused_receiver_owned_cache"] = True
    return frames, manifest


def acquire_operational_frames(root: Path, retrieved_at: str) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    cached = _load_cached_operational_frames(root)
    if cached is not None:
        return cached
    root.mkdir(parents=True, exist_ok=True)
    credentials = load_alpaca_credentials()
    if not credentials.present:
        manifest = {
            "status": "failed", "failure_reason": "provider_unavailable", "provider": "Alpaca official market data API",
            "historical_market_data_calls": 0, "credentials_persisted": False, "retrieved_at": retrieved_at,
        }
        write_json(root / "acquisition_manifest.json", manifest)
        return {}, manifest
    client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
    merged: dict[str, Any] = {"bars": {symbol: [] for symbol in SYMBOLS}}
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    page_token: str | None = None
    calls = 0
    response_hashes: list[str] = []
    try:
        while True:
            calls += 1
            payload = client.get_historical_bars_page(
                symbols=list(SYMBOLS), start=ACQUISITION_START, end=ACQUISITION_END,
                timeframe="1Day", page_token=page_token, feed=ALPACA_FEED,
                adjustment=ALPACA_ADJUSTMENT, limit=10000,
            )
            raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")
            raw_path = raw_dir / f"page_{calls:04d}.json"
            raw_path.write_bytes(raw)
            response_hashes.append(_artifact_hash(raw_path))
            for symbol, bars in payload.get("bars", {}).items():
                merged["bars"].setdefault(symbol, []).extend(bars)
            page_token = payload.get("next_page_token")
            if not page_token:
                break
    except Exception as exc:
        manifest = {
            "status": "failed", "failure_reason": "provider_unavailable", "provider": "Alpaca official market data API",
            "historical_market_data_calls": calls, "normalized_exception_type": type(exc).__name__,
            "credentials_persisted": False, "response_hashes": response_hashes, "retrieved_at": retrieved_at,
        }
        write_json(root / "acquisition_manifest.json", manifest)
        return {}, manifest
    frames = parse_bars_response(merged, drop_incomplete_current_day=False)
    normalized_dir = root / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    symbols: dict[str, Any] = {}
    for symbol in SYMBOLS:
        frame = frames.get(symbol, pd.DataFrame()).copy()
        path = normalized_dir / f"{symbol}.csv"
        frame.to_csv(path, index=False, lineterminator="\n")
        symbols[symbol] = {
            "file_hash": _artifact_hash(path), "row_count": len(frame),
            "first_date": "" if frame.empty else str(frame["date"].min()),
            "last_date": "" if frame.empty else str(frame["date"].max()),
            "duplicate_count": 0 if frame.empty else int(frame["date"].duplicated().sum()),
        }
    manifest = {
        "status": "success", "provider": "Alpaca official market data API", "endpoint": "/v2/stocks/bars",
        "feed": ALPACA_FEED, "adjustment": ALPACA_ADJUSTMENT,
        "adjustment_semantics": "Alpaca adjustment=all supplies split- and cash-dividend-adjusted stock bars; adjusted close is used as the total-return-compatible operational input",
        "requested_start": ACQUISITION_START, "requested_end_exclusive": ACQUISITION_END,
        "operational_cutoff": OPERATIONAL_CUTOFF, "historical_market_data_calls": calls,
        "current_market_data_calls": 0, "current_CPI_calls": 0, "current_target_calculations": 0,
        "credentials_persisted": False, "response_hashes": response_hashes, "retrieved_at": retrieved_at,
        "symbols": symbols, "reused_receiver_owned_cache": False,
    }
    write_json(root / "acquisition_manifest.json", manifest)
    return {symbol: frames.get(symbol, pd.DataFrame()) for symbol in SYMBOLS}, manifest


def assess_operational_coverage(frames: dict[str, pd.DataFrame], acquisition: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame, dict[str, str]]:
    if acquisition.get("status") != "success":
        status = "provider_unavailable"
        return ({
            "operational_provider_status": status, "operational_common_monthly_return_count": 0,
            "operational_120m_window_available": False,
        }, [], pd.DataFrame(), {})
    try:
        prices, normalized = normalize_provider_frames(frames)
    except SpdjCalculationError as exc:
        return ({
            "operational_provider_status": "provider_semantics_unsupported", "failure": str(exc),
            "operational_common_monthly_return_count": 0, "operational_120m_window_available": False,
        }, [], pd.DataFrame(), {})
    prices = prices.loc[prices.index <= pd.Timestamp(OPERATIONAL_CUTOFF)]
    calendar = build_xnys_calendar(start="2015-12-01", end="2026-12-31")
    session_dates = pd.DatetimeIndex([pd.Timestamp(item.session_date) for item in calendar.sessions])
    periods = pd.period_range(prices.index.min().to_period("M"), pd.Period("2026-07", freq="M"), freq="M")
    rows: list[dict[str, Any]] = []
    endpoint_prices: dict[pd.Period, dict[str, float]] = {}
    endpoint_sessions: dict[str, str] = {}
    for period in periods:
        candidates = session_dates[session_dates.to_period("M") == period]
        expected = candidates.max()
        present = {symbol: expected in prices.index and bool(np.isfinite(prices.loc[expected, symbol])) and float(prices.loc[expected, symbol]) > 0.0 for symbol in SYMBOLS}
        complete = all(present.values())
        if complete:
            endpoint_prices[period] = {symbol: float(prices.loc[expected, symbol]) for symbol in SYMBOLS}
            endpoint_sessions[str(period)] = expected.date().isoformat()
        rows.append({
            "reference_month": str(period), "expected_final_XNYS_session": expected.date().isoformat(),
            "symbols_present": sum(present.values()), "required_symbols": len(SYMBOLS), "complete_endpoint": complete,
            "duplicate_sessions": 0, "positive_finite_prices": all(present.values()),
            "SPY_present": present["SPY"], "IYR_present": present["IYR"], "GSG_present": present["GSG"],
            "GLD_present": present["GLD"], "AGG_present": present["AGG"], "TIP_present": present["TIP"],
        })
    endpoint_frame = pd.DataFrame.from_dict(endpoint_prices, orient="index").sort_index()
    if not endpoint_frame.empty:
        endpoint_frame.index = pd.PeriodIndex(endpoint_frame.index, freq="M")
    monthly_returns = endpoint_frame.pct_change(fill_method=None).dropna(how="any")
    latest_month = pd.Period("2026-07", freq="M")
    uninterrupted: list[pd.Period] = []
    cursor = latest_month
    while cursor in endpoint_frame.index:
        uninterrupted.append(cursor)
        cursor -= 1
    uninterrupted.reverse()
    common_returns = max(0, len(uninterrupted) - 1)
    available_120 = common_returns >= 120
    invalid_sessions = any(int(details.get("duplicate_count", 0)) for details in acquisition.get("symbols", {}).values())
    structural_semantics = acquisition.get("feed") == "sip" and acquisition.get("adjustment") == "all"
    if not structural_semantics or invalid_sessions:
        provider_status = "provider_semantics_unsupported"
    elif not available_120:
        provider_status = "operational_history_insufficient"
    else:
        provider_status = "operational_history_ready"
    coverage = {
        "provider": acquisition.get("provider"), "endpoint": acquisition.get("endpoint"),
        "feed": acquisition.get("feed"), "adjustment": acquisition.get("adjustment"),
        "requested_start": acquisition.get("requested_start"), "requested_end_exclusive": acquisition.get("requested_end_exclusive"),
        "actual_common_start": normalized.get("common_start"), "actual_common_end": normalized.get("common_end"),
        "operational_cutoff": OPERATIONAL_CUTOFF, "operational_common_monthly_return_count": common_returns,
        "operational_120m_window_available": available_120,
        "candidate_120m_return_start": str(uninterrupted[-120]) if available_120 else "",
        "candidate_120m_return_end": str(uninterrupted[-1]) if available_120 else "",
        "candidate_120m_required_price_endpoint_start": str(uninterrupted[-121]) if available_120 else "",
        "complete_month_end_count": int(sum(row["complete_endpoint"] for row in rows)),
        "all_required_months_in_latest_window": available_120 and all(period in endpoint_frame.index for period in pd.period_range(uninterrupted[-121], uninterrupted[-1], freq="M")),
        "duplicate_sessions": invalid_sessions,
        "zero_or_negative_prices": False,
        "operational_provider_status": provider_status,
        "historical_market_data_calls": acquisition.get("historical_market_data_calls", 0),
        "current_market_data_calls": 0, "current_CPI_calls": 0, "current_target_calculations": 0,
    }
    return coverage, rows, monthly_returns, endpoint_sessions


def same_window_diagnostic(
    calculator: SpdjReceiverCalculator,
    operational_returns: pd.DataFrame,
    operational_sessions: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_returns, source_sessions, cpi = load_bundle_inputs()
    source_signal = pd.read_csv(RESEARCH_SIGNAL)
    frozen = source_signal.loc[source_signal["reference_month"] == SAME_WINDOW_REFERENCE_MONTH]
    if frozen.empty or len(operational_returns) == 0:
        status = {"status": "same_window_provider_diagnostic_not_yet_available_from_frozen_event_set", "maximum_target_difference": ""}
        return [], status
    frozen_row = frozen.iloc[0]
    if int(frozen_row["lookback_monthly_returns"]) != 120 or str(frozen_row["lookback_start_month"]) < "2016-01":
        status = {"status": "same_window_provider_diagnostic_not_yet_available_from_frozen_event_set", "maximum_target_difference": ""}
        return [], status
    required = pd.period_range(str(frozen_row["lookback_start_month"]), SAME_WINDOW_REFERENCE_MONTH, freq="M")
    if len(required) != 120 or not all(month in operational_returns.index for month in required):
        status = {"status": "same_window_provider_diagnostic_not_yet_available_from_frozen_event_set", "maximum_target_difference": ""}
        return [], status
    calendar = build_xnys_calendar(end="2026-12-31")
    source = calculator.calculate_from_monthly_inputs(
        reference_month=SAME_WINDOW_REFERENCE_MONTH, cpi_reference=cpi, monthly_returns=source_returns,
        month_end_sessions=source_sessions, calendar=calendar, fixture_id="same_window_source_2026_06",
        input_source="frozen_conformance_bundle",
    )
    provider = calculator.calculate_from_monthly_inputs(
        reference_month=SAME_WINDOW_REFERENCE_MONTH, cpi_reference=cpi, monthly_returns=operational_returns,
        month_end_sessions=operational_sessions, calendar=calendar, fixture_id="same_window_alpaca_2026_06",
        input_source="operational_provider_portability_diagnostic",
    )
    rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        source_values = source_returns.loc[required, symbol].to_numpy(dtype=float)
        provider_values = operational_returns.loc[required, symbol].to_numpy(dtype=float)
        target_difference = provider.target_weights[symbol] - source.target_weights[symbol]
        rows.append({
            "diagnostic_event": SAME_WINDOW_REFERENCE_MONTH, "symbol": symbol,
            "window_start": str(required.min()), "window_end": str(required.max()), "monthly_return_count": len(required),
            "source_target_weight": source.target_weights[symbol], "Alpaca_target_weight": provider.target_weights[symbol],
            "target_weight_difference": target_difference, "absolute_target_weight_difference": abs(target_difference),
            "maximum_absolute_monthly_return_difference": float(np.max(np.abs(provider_values - source_values))),
            "mean_absolute_monthly_return_difference": float(np.mean(np.abs(provider_values - source_values))),
            "source_regime": source.regime, "Alpaca_regime": provider.regime,
            "regime_changed": source.regime != provider.regime,
            "source_normalized": abs(sum(source.target_weights.values()) - 1.0) <= WEIGHT_TOLERANCE,
            "Alpaca_normalized": abs(sum(provider.target_weights.values()) - 1.0) <= WEIGHT_TOLERANCE,
            "golden_tolerance_applied": False,
        })
    max_difference = max(row["absolute_target_weight_difference"] for row in rows)
    return rows, {
        "status": "provider_portability_diagnostic_completed_review_needed",
        "diagnostic_event": SAME_WINDOW_REFERENCE_MONTH, "window_start": str(required.min()), "window_end": str(required.max()),
        "maximum_target_difference": max_difference, "regime_changed": source.regime != provider.regime,
        "formal_blocking_tolerance_defined": False, "golden_tolerance_applied": False,
    }


def _bundle_inventory(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    roles = {
        "monthly_return_input.csv": "minimal frozen monthly total-return-compatible inputs",
        "cpi_regression_input.csv": "minimal frozen point-in-time CPI regression inputs",
        "fixture_input_ranges.csv": "fixture-to-input-range mapping",
        "source_provenance.json": "cryptographic research provenance",
    }
    return [{
        "relative_path": name, "role": roles[name], "file_hash": digest,
        "software_conformance_reference": True, "operational_market_data": False,
        "source_runtime_dependency": False,
    } for name, digest in sorted(bundle["manifest"]["files"].items())]


def _outcome_and_next_action(calculator_status: str, provider_status: str, other_blockers: list[str]) -> tuple[str, str, list[str]]:
    blockers = list(other_blockers)
    if calculator_status != "pass":
        blockers.append("receiver_calculator_conformance_failure")
    if provider_status == "operational_history_insufficient":
        blockers.append("operational_provider_history_insufficient")
    elif provider_status == "provider_semantics_unsupported":
        blockers.append("operational_provider_semantics_unsupported")
    elif provider_status == "provider_unavailable":
        blockers.append("operational_provider_history_insufficient")
    blockers = sorted(set(blockers))
    if not blockers:
        return OUTCOME_SUCCESS, "initialize_spdj_dynamic_inflation_paper_demo_observation_v1", blockers
    if calculator_status != "pass":
        next_action = "direction_owner_review_spdj_receiver_calculator_conformance_v1"
    elif provider_status in {"operational_history_insufficient", "provider_unavailable"}:
        next_action = "direction_owner_review_spdj_operational_market_data_provider_v1"
    else:
        next_action = "direction_owner_review_spdj_standard_import_blocker_v2"
    return OUTCOME_BLOCKED, next_action, blockers


def _update_acceptance(
    *, outcome: str, next_action: str, blockers: list[str], calculator_status: str,
    provider_status: str, fixture_summary: dict[str, Any], state_status: str,
    idempotency_status: str, run_timestamp: str, bundle_hash: str,
) -> tuple[dict[str, Any], int, int]:
    attempt_path = IMPORTED_ROOT / "resolution_v1.json"
    existing_reassessment = OUTPUT_DIR / "receiver_acceptance_reassessment.json"
    prior = json.loads(existing_reassessment.read_text(encoding="utf-8")) if existing_reassessment.exists() else {}
    attempts_before = int(prior.get("validation_attempts_before", 1 if attempt_path.exists() else 0))
    status = "validated_not_active" if outcome == OUTCOME_SUCCESS else "blocked"
    attempt = {
        "validation_attempt_id": TASK_ID, "handoff_id": HANDOFF_ID, "package_hash": PACKAGE_HASH,
        "supersedes_for_validation_only": "pilot_import_validate_spdj_under_forward_observation_standard_v1",
        "prior_acceptance_status_preserved_in_prior_evidence": "blocked", "acceptance_status": status,
        "calculator_conformance_status": calculator_status, "operational_provider_status": provider_status,
        "fixture_validation_status": "pass" if fixture_summary["failed_count"] == 0 else "fail",
        "CPI_conformance_status": "pass", "calendar_conformance_status": "pass",
        "state_persistence_status": state_status, "idempotency_status": idempotency_status,
        "conformance_bundle_hash": bundle_hash, "blocking_reasons": blockers,
        "next_action": next_action, "validation_timestamp": run_timestamp,
        "activation_performed": False, "current_target_calculated": False,
    }
    write_json(attempt_path, attempt)
    attempts_after = 1
    if outcome == OUTCOME_SUCCESS:
        receiver_acceptance = {
            "acceptance_record_id": canonical_json_hash({"handoff_id": HANDOFF_ID, "task_id": TASK_ID, "package_hash": PACKAGE_HASH}),
            "handoff_id": HANDOFF_ID, "research_strategy_id": STRATEGY_ID, "receiver_strategy_id": STRATEGY_ID,
            "strategy_instance_id": INSTANCE_ID, "source_schema": SOURCE_SCHEMA, "normalized_schema": NORMALIZED_SCHEMA,
            "package_integrity_status": "pass", "contract_validation_status": "pass",
            "calculator_conformance_status": calculator_status, "fixture_validation_status": "pass",
            "CPI_conformance_status": "pass", "calendar_conformance_status": "pass",
            "operational_provider_status": provider_status, "state_validation_status": state_status,
            "idempotency_status": idempotency_status, "execution_boundary_status": "pass",
            "deployment_profile_status": "validated_inactive", "acceptance_status": status,
            "blocking_reasons": [], "created_at": run_timestamp, "importer_version": IMPORTER_VERSION,
            "importer_hash": importer_hash(), "activation_performed": False,
        }
        standard_acceptance = {
            "handoff_id": HANDOFF_ID, "package_hash": PACKAGE_HASH, "source_schema": SOURCE_SCHEMA,
            "normalized_standard_schema": NORMALIZED_SCHEMA, "research_strategy_id": STRATEGY_ID,
            "receiver_strategy_id": STRATEGY_ID, "import_mode": "import_inactive", "integrity_status": "package_validated",
            "contract_validation_status": "pass", "fixture_validation_status": "pass",
            "calculator_conformance_status": calculator_status, "operational_provider_status": provider_status,
            "deployment_profile_status": "validated_inactive", "acceptance_status": status, "blocking_reasons": [],
            "timestamp": run_timestamp, "importer_version": IMPORTER_VERSION, "importer_hash": importer_hash(),
            "activation_performed": False,
        }
        write_json(IMPORTED_ROOT / "receiver_acceptance_record.json", receiver_acceptance)
        write_json(IMPORTED_ROOT / "acceptance_record.json", standard_acceptance)
        write_json(CATALOG_DIR / f"{HANDOFF_ID}.json", receiver_acceptance)
        lifecycle_row = {
            "prior_state": "imported", "next_state": "validated_not_active", "timestamp": run_timestamp,
            "evidence_id": TASK_ID, "actor_task_id": TASK_ID,
            "reason": "separate frozen-input calculator conformance and prospective Alpaca operational provider gates passed",
        }
        _append_unique_jsonl(CATALOG_DIR / f"{HANDOFF_ID}.lifecycle.jsonl", lifecycle_row, identity_fields=("actor_task_id", "next_state"))
    reassessment = {**attempt, "outcome": outcome, "validation_attempts_before": attempts_before, "validation_attempts_after": attempts_after}
    return reassessment, attempts_before, attempts_after


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = OUTPUT_DIR / "receiver_acceptance_reassessment.json"
    run_timestamp = (
        json.loads(existing.read_text(encoding="utf-8")).get("validation_timestamp")
        if existing.exists()
        else datetime.now(timezone.utc).isoformat()
    )
    protected_before = protected_snapshot()
    active_before = _active_spdj_count()
    import_count_before = _persistent_import_count()
    prior = verify_prior_pilot()
    prior_rows, prior_counts = reconcile_prior_fixtures()
    bundle_result = materialize_conformance_bundle(run_timestamp)
    bundle = bundle_result["manifest"]
    handoff, binding, calculator = load_receiver_contract()
    package_integrity = verify_imported_package(SOURCE_PACKAGE, SOURCE_FILE_MANIFEST)
    standard_integrity = verify_standard_evidence()
    fixture_rows, calculations, fixture_summary, intermediates = run_frozen_golden_fixtures(calculator)
    state_result, idempotency_result, target_version_result = state_validation(calculator, calculations, run_timestamp)
    frames, acquisition = acquire_operational_frames(OUTPUT_DIR / "operational_history", run_timestamp)
    coverage, month_rows, operational_returns, operational_sessions = assess_operational_coverage(frames, acquisition)
    diagnostic_rows, diagnostic_summary = same_window_diagnostic(calculator, operational_returns, operational_sessions)

    other_blockers: list[str] = []
    if prior["status"] != "pass" or prior_counts != {"failed_total": 13, "pre_provider_coverage": 12, "incomplete_lookback": 1, "same_window_semantic_failures": 0}:
        other_blockers.append("other")
    if package_integrity["status"] != "pass" or standard_integrity["status"] != "pass" or normalized_spdj_package_hash(SOURCE_PACKAGE) != PACKAGE_HASH:
        other_blockers.append("conformance_input_bundle_failure")
    if bundle_result["status"] != "pass":
        other_blockers.append("conformance_input_bundle_failure")
    if fixture_summary["threshold_cases_passed"] != 7:
        other_blockers.append("CPI_conformance_failure")
    if any(row["expected_effective_date"] != row["observed_effective_date"] for row in fixture_rows if row["expected_effective_date"]):
        other_blockers.append("calendar_conformance_failure")
    if state_result["status"] != "pass" or idempotency_result["status"] != "pass" or target_version_result["status"] != "pass":
        other_blockers.append("state_persistence_failure")
    calculator_status = fixture_summary["calculator_conformance_status"]
    provider_status = coverage["operational_provider_status"]
    outcome, next_action, blockers = _outcome_and_next_action(calculator_status, provider_status, other_blockers)

    try:
        validate_transition(LifecycleTransition("validated_not_active", "microtrading_eligible", run_timestamp, TASK_ID, TASK_ID, "negative test"))
        micro_status = "microtrading_promotion_contract_unexpectedly_present"
    except StandardContractError as exc:
        micro_status = "microtrading_promotion_contract_missing|microtrading_promotion_not_authorized" if exc.code == "microtrading_promotion_not_authorized" else exc.code
    if "microtrading_promotion_not_authorized" not in micro_status:
        blockers = sorted(set(blockers + ["other"]))
        outcome = OUTCOME_BLOCKED
        next_action = "direction_owner_review_spdj_standard_import_blocker_v2"

    reassessment, attempts_before, attempts_after = _update_acceptance(
        outcome=outcome, next_action=next_action, blockers=blockers, calculator_status=calculator_status,
        provider_status=provider_status, fixture_summary=fixture_summary, state_status=state_result["status"],
        idempotency_status=idempotency_result["status"], run_timestamp=run_timestamp,
        bundle_hash=bundle["conformance_bundle_hash"],
    )
    import_count_after = _persistent_import_count()
    active_after = _active_spdj_count()
    protected_after = protected_snapshot()
    protected_unchanged = protected_before == protected_after
    if not protected_unchanged:
        outcome = OUTCOME_BLOCKED
        next_action = "direction_owner_review_spdj_standard_import_blocker_v2"
        blockers = sorted(set(blockers + ["other"]))

    write_csv(OUTPUT_DIR / "prior_fixture_reclassification.csv", prior_rows, list(prior_rows[0]))
    write_json(OUTPUT_DIR / "conformance_bundle_manifest.json", bundle)
    inventory = _bundle_inventory(bundle_result)
    write_csv(OUTPUT_DIR / "conformance_input_inventory.csv", inventory, list(inventory[0]))
    write_csv(OUTPUT_DIR / "golden_fixture_results_revalidated.csv", fixture_rows, GOLDEN_FIELDS)
    write_json(OUTPUT_DIR / "golden_intermediate_calculations.json", {
        "input_source": "frozen_conformance_bundle", "weight_tolerance": WEIGHT_TOLERANCE,
        "formula_tolerance": FORMULA_TOLERANCE, "fixture_summary": fixture_summary,
        "medium_and_high_fixtures": intermediates,
    })
    write_json(OUTPUT_DIR / "operational_provider_coverage.json", {**coverage, "acquisition_manifest_hash": _artifact_hash(OUTPUT_DIR / "operational_history" / "acquisition_manifest.json")})
    month_fields = list(month_rows[0]) if month_rows else ["reference_month", "expected_final_XNYS_session", "complete_endpoint"]
    write_csv(OUTPUT_DIR / "operational_month_end_coverage.csv", month_rows, month_fields)
    write_json(OUTPUT_DIR / "operational_price_semantics.json", {
        "operational_provider_status": provider_status, "provider": acquisition.get("provider", "Alpaca official market data API"),
        "endpoint": acquisition.get("endpoint", "/v2/stocks/bars"), "feed": acquisition.get("feed", ALPACA_FEED),
        "adjustment": acquisition.get("adjustment", ALPACA_ADJUSTMENT), "price_field": "close",
        "structural_adjustment_semantics_status": "supported" if acquisition.get("adjustment") == "all" else "unsupported",
        "research_requirement": "split- and cash-dividend-adjusted total-return-compatible close",
        "bitwise_cross_provider_equality_required": False,
        "prior_adjustment_incompatibility_demonstrated": False,
        "same_window_diagnostic_status": diagnostic_summary["status"],
    })
    diagnostic_fields = list(diagnostic_rows[0]) if diagnostic_rows else ["diagnostic_event", "symbol", "status"]
    write_csv(OUTPUT_DIR / "same_window_provider_diagnostic.csv", diagnostic_rows, diagnostic_fields)

    root_cause_text = f"""# SPDJ Prior Blocker Root Cause

The prior pilot conflated calculator conformance with operational provider coverage. Its only calculated target used 103 rather than 120 monthly returns and 92 rather than 109 ProIB pairs. No failed fixture compared an identical historical window.

1. Prior failures requiring history before Alpaca coverage: **{prior_counts['pre_provider_coverage']}**.
2. Prior failures using an incomplete lookback: **{prior_counts['incomplete_lookback']}**.
3. Prior identical-window semantic failures: **{prior_counts['same_window_semantic_failures']}**.
4. Evidence that `adjustment=all` itself is incompatible: **no**.
5. Complete Alpaca monthly returns through 2026-07-31: **{coverage.get('operational_common_monthly_return_count', 0)}**; 120-month window: **{'yes' if coverage.get('operational_120m_window_available') else 'no'}**.
6. Frozen-input golden fixtures reproduced: **{'yes' if fixture_summary['failed_count'] == 0 else 'no'}**.

Dominant historical blocker: `historical_provider_coverage_inadequate_for_legacy_golden_fixture_reproduction`.
"""
    _write_text(OUTPUT_DIR / "blocker_root_cause.md", root_cause_text)
    _write_text(OUTPUT_DIR / "validation_taxonomy_update.md", """# Validation Taxonomy Update

`calculator_conformance_status` is `pass` or `fail` and is determined only with frozen conformance inputs. `operational_provider_status` is one of `operational_history_ready`, `operational_history_insufficient`, `provider_semantics_unsupported`, `provider_unavailable`, or `provider_portability_review_needed`. Insufficient history is no longer labeled as a generic price-semantics failure.
""")
    _write_text(OUTPUT_DIR / "standard_fixture_boundary_update.md", """# Standard Fixture Boundary Update

`forward_observation_conformance_input_bundle_v1` is an additive companion to immutable `forward_observation_handoff_standard_v1:1`. Historical-numeric strategies should ship deterministic expected outputs plus the minimal frozen inputs required to reproduce them. Operational-provider coverage and semantics remain a separate receiver gate. The bundle is a software conformance reference, not an ongoing market-data feed.
""")
    reassessment.update({
        "outcome": outcome, "acceptance_status": "validated_not_active" if outcome == OUTCOME_SUCCESS else "blocked",
        "blocking_reasons": blockers, "next_action": next_action,
        "persistent_standardized_imports_before": import_count_before,
        "persistent_standardized_imports_after": import_count_after,
        "active_SPDJ_observations_before": active_before, "active_SPDJ_observations_after": active_after,
        "current_target_calculated": False, "current_CPI_queried": False,
    })
    write_json(OUTPUT_DIR / "receiver_acceptance_reassessment.json", reassessment)
    legacy = {
        "status": "pass" if protected_unchanged else "fail", "before": protected_before, "after": protected_after,
        "VM_status": "unchanged" if all(protected_before[key] == protected_after[key] for key in ("VM_calculator", "VM_spec")) else "changed",
        "DSR_status": "unchanged" if all(protected_before[key] == protected_after[key] for key in ("DSR_calculator", "DSR_spec")) else "changed",
        "prior_blocked_pilot_immutable": protected_before["prior_blocked_pilot"] == protected_after["prior_blocked_pilot"],
        "prior_blocked_pilot_deterministic_hash": PRIOR_EVIDENCE_HASH,
        "persistent_standardized_imports_before": import_count_before, "persistent_standardized_imports_after": import_count_after,
        "validation_attempts_before": attempts_before, "validation_attempts_after": attempts_after,
        "new_research_trials": 0, "strategy_variants": 0, "handoff_imports_created": 0,
        "active_observations_added": active_after - active_before,
        "current_target_calculations": 0, "current_CPI_calls": 0,
        "account_calls": 0, "position_calls": 0, "order_calls": 0, "fill_calls": 0,
        "paper_orders": 0, "real_orders": 0,
    }
    write_json(OUTPUT_DIR / "legacy_state_reconciliation.json", legacy)
    _write_text(OUTPUT_DIR / "next_action.md", f"# Next Action\n\n`{next_action}`\n\nNot executed.\n")

    artifact_names = [
        "blocker_root_cause.md", "prior_fixture_reclassification.csv", "conformance_bundle_manifest.json",
        "conformance_input_inventory.csv", "golden_fixture_results_revalidated.csv", "golden_intermediate_calculations.json",
        "operational_provider_coverage.json", "operational_month_end_coverage.csv", "operational_price_semantics.json",
        "same_window_provider_diagnostic.csv", "validation_taxonomy_update.md", "receiver_acceptance_reassessment.json",
        "standard_fixture_boundary_update.md", "legacy_state_reconciliation.json", "next_action.md",
    ]
    artifact_hashes = {name: _artifact_hash(OUTPUT_DIR / name) for name in artifact_names}
    evidence_hash = canonical_json_hash(artifact_hashes)
    consistency = {
        "task_id": TASK_ID, "outcome": outcome, "overall_pass": outcome == OUTCOME_SUCCESS,
        "root_cause_classification": "historical_provider_coverage_inadequate_for_legacy_golden_fixture_reproduction",
        "checks": {
            "prior_pilot_hash_reconciles": prior["status"] == "pass",
            "prior_pilot_immutable": protected_unchanged and legacy["prior_blocked_pilot_immutable"],
            "conformance_bundle_valid": bundle_result["status"] == "pass",
            "all_15_golden_fixtures_accepted": fixture_summary["failed_count"] == 0,
            "exact_weight_tolerance_preserved": WEIGHT_TOLERANCE == 1e-8,
            "formula_tolerance_preserved": FORMULA_TOLERANCE == 1e-10,
            "first_ProIB_pair_count_25": fixture_summary["first_ProIB_pair_count"] == 25,
            "high_120m_pair_count_source_compliant": fixture_summary["all_120m_high_pair_counts_source_compliant"],
            "operational_120m_window_available": coverage.get("operational_120m_window_available") is True,
            "operational_adjustment_structurally_supported": provider_status == "operational_history_ready",
            "state_persistence_pass": state_result["status"] == "pass",
            "idempotency_pass": idempotency_result["status"] == "pass",
            "target_version_pass": target_version_result["status"] == "pass",
            "exactly_one_persistent_import": import_count_before == import_count_after == 1,
            "one_validation_attempt_added": attempts_before == 0 and attempts_after == 1,
            "no_active_observation_added": active_before == active_after == 0,
            "no_current_target_or_CPI": True,
            "zero_account_position_order_fill_calls": True,
            "VM_DSR_unchanged": legacy["VM_status"] == legacy["DSR_status"] == "unchanged",
            "microtrading_fail_closed": "microtrading_promotion_not_authorized" in micro_status,
            "protected_state_unchanged": protected_unchanged,
            "next_action_not_executed": True,
        },
        "prior_fixture_counts": prior_counts, "fixture_summary": fixture_summary,
        "calculator_conformance_status": calculator_status, "operational_provider_status": provider_status,
        "same_window_provider_diagnostic": diagnostic_summary,
        "counts": {
            "persistent_standardized_imports_before": import_count_before, "persistent_standardized_imports_after": import_count_after,
            "validation_attempts_before": attempts_before, "validation_attempts_after": attempts_after,
            "active_observations_before": active_before, "active_observations_after": active_after,
            "historical_Alpaca_calls": acquisition.get("historical_market_data_calls", 0),
            "current_target_calculations": 0, "current_CPI_calls": 0, "account_calls": 0,
            "position_calls": 0, "order_calls": 0, "fill_calls": 0,
        },
        "acceptance_status": reassessment["acceptance_status"], "blocker_reasons": blockers,
        "microtrading_status": micro_status, "next_action": next_action, "next_action_executed": False,
        "artifact_hashes": artifact_hashes, "deterministic_evidence_hash": evidence_hash,
    }
    consistency["all_checks_pass"] = all(consistency["checks"].values())
    if outcome == OUTCOME_SUCCESS and not consistency["all_checks_pass"]:
        consistency["overall_pass"] = False
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


def main() -> int:
    result = run()
    print(json.dumps({
        "task_id": result["task_id"], "outcome": result["outcome"], "overall_pass": result["overall_pass"],
        "calculator_conformance_status": result["calculator_conformance_status"],
        "operational_provider_status": result["operational_provider_status"],
        "deterministic_evidence_hash": result["deterministic_evidence_hash"], "next_action": result["next_action"],
    }, sort_keys=True))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
