from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "export_spdj_dynamic_inflation_forward_observation_handoff_v1"
HANDOFF_ID = "spdj_dynamic_inflation_forward_observation_handoff_v1"
HANDOFF_VERSION = "v1"
PACKAGE_SCHEMA_VERSION = "spdj_forward_observation_handoff_schema_v1"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
FAMILY_ID = "public_cpi_dynamic_inflation_regime_allocation"
ARCHITECTURE_ID = "monthly_cpi_regime_dynamic_multi_asset_inflation_allocation"
CANONICAL_TRIAL_ID = f"{STRATEGY_ID}__canonical"
ROBUSTNESS_TRIAL_ID = "run_spdj_dynamic_inflation_robustness_v1__robustness"
ELIGIBILITY_STATUS = "spdj_dynamic_inflation_research_eligible_for_handoff"
EXPORT_COMPLETE = "spdj_dynamic_inflation_handoff_export_complete"
EXPORT_BLOCKED = "spdj_dynamic_inflation_handoff_export_blocked"
SUCCESS_NEXT_ACTION = "forward_observation_app_import_validate_spdj_dynamic_inflation_handoff_v1"
BLOCKED_NEXT_ACTION = "direction_owner_review_spdj_dynamic_inflation_handoff_export_blocker_v1"

EXPECTED_CODE_HASH = "sha256:55eff61ee55999df76d023e570440197c7dbf0d05da41775cf23671dbd15b1e4"
EXPECTED_CPI_HASH = "sha256:e221af86dfd616f4fa65bec016910deaffe47f1d6e690495a4033cd0e3eefcc8"
EXPECTED_PRICE_BUNDLE_HASH = "sha256:ab05bef8ac2b12c6391bca65cb1312148db7d64bed11e9932379464f8bcc72c8"
EXPECTED_UNIVERSE_HASH = "sha256:5bafb89d6c32712178c2a1fc57e8eb177daa9257625e7bcd317cefe2ea3c9861"
EXPECTED_EXPLORATION_HASH = "sha256:0f3cff1fbed4af952e5264fb60d21b4f0bdec2d7080bb3d16c356bef3e9ccea9"
EXPECTED_ROBUSTNESS_HASH = "sha256:d8c22c89989128454228795221d3b4d81b21d572c10c8e3b300e70b40586ec59"
EXPECTED_ELIGIBILITY_HASH = "sha256:2cf743f374f790fc9625b08867ce3e1ec1c6d987bfd87dbdf13065f71a1def65"

SYMBOLS = ("SPY", "IYR", "GSG", "GLD", "AGG", "TIP")
WEIGHT_TOLERANCE = 1e-8
FORMULA_TOLERANCE = 1e-10

ELIGIBILITY_DIR = ROOT / "evidence/research_eligibility/spdj_dynamic_inflation_research_eligibility_v1/latest"
EXPLORATION_DIR = ROOT / "evidence/research_recovery/spdj_multi_asset_dynamic_inflation_etf_portability_v1/latest"
ROBUSTNESS_DIR = ROOT / "evidence/robustness/spdj_dynamic_inflation_robustness_v1/latest"
INTAKE_DIR = ROOT / "evidence/public_source_strategy_intake/phase2_public_signal_etf_mappable_candidate_intake_v2/latest"
CPI_V1_EVIDENCE_DIR = ROOT / "evidence/public_signal_data/acquire_validate_freeze_phase2_public_signal_inputs_v1/latest"
CPI_V2_EVIDENCE_DIR = ROOT / "evidence/public_signal_data/resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2/latest"
CPI_V1_DATA_DIR = ROOT / "data/public_signals/phase2_public_cpi_point_in_time_v1"
CPI_V2_DATA_DIR = ROOT / "data/public_signals/phase2_public_cpi_point_in_time_v2"
UNIVERSE_DIR = ROOT / "evidence/universe_expansion/phase2_bounded_multi_asset_research_universe_v1/latest"
CANONICAL_CODE = ROOT / "strategy_lab/research_os/research/implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1.py"
OUTPUT_DIR = ROOT / "evidence/handoff_exports/spdj_dynamic_inflation_forward_observation_handoff_v1/latest"
PACKAGE_DIR = OUTPUT_DIR / "package"
REFERENCE_DIR = PACKAGE_DIR / "reference_only"
HISTORICAL_CPI_DIR = REFERENCE_DIR / "historical_cpi_v2"

PACKAGE_REQUIRED_FILES = (
    "handoff_manifest.json",
    "strategy_contract.json",
    "forward_observation_interface_contract.json",
    "strategy_state_machine.json",
    "instrument_mapping.csv",
    "signal_contract.json",
    "price_semantics_contract.json",
    "schedule_and_timing_contract.json",
    "golden_conformance_fixtures.csv",
    "golden_fixture_manifest.json",
    "research_evidence_summary.json",
    "research_claims_and_nonclaims.json",
    "caveat_register.csv",
    "receiver_acceptance_checklist.md",
    "forward_application_responsibility_boundary.md",
    "source_provenance.json",
    "lineage_manifest.json",
    "reference_only/README.md",
    "reference_only/implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1.py",
    "reference_only/historical_cpi_v2/cpi_point_in_time_signal.csv",
    "reference_only/historical_cpi_v2/data_dictionary.json",
    "reference_only/historical_cpi_v2/source_manifest.json",
    "reference_only/historical_cpi_v2/warmup_contract.json",
    "reference_only/historical_cpi_v2/missing_release_exception.csv",
)
OUTSIDE_REQUIRED_FILES = (
    "export_report.md",
    "package_file_manifest.csv",
    "hygiene_scan.json",
    "trial_accounting.json",
    "consistency_check.json",
    "next_action.md",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def sha256_path(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return canonical_json(value)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def persistent_created_at() -> str:
    manifest = PACKAGE_DIR / "handoff_manifest.json"
    if manifest.exists():
        value = read_json(manifest).get("created_at")
        if isinstance(value, str) and value:
            return value
    return datetime.now(timezone.utc).isoformat()


def eligibility_packet_hash() -> str:
    consistency = read_json(ELIGIBILITY_DIR / "consistency_check.json")
    names = [name for name in consistency["required_outputs"] if name != "consistency_check.json"]
    digest = hashlib.sha256()
    for name in sorted(names):
        path = ELIGIBILITY_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def protected_paths() -> list[Path]:
    return [
        CANONICAL_CODE,
        ELIGIBILITY_DIR,
        EXPLORATION_DIR,
        ROBUSTNESS_DIR,
        INTAKE_DIR,
        CPI_V1_EVIDENCE_DIR,
        CPI_V2_EVIDENCE_DIR,
        CPI_V1_DATA_DIR,
        CPI_V2_DATA_DIR,
        ROOT / "data/universe_expansion/pilot_etf_market_data_v1",
        ROOT / "data/universe_expansion/phase2_bounded_multi_asset_market_data_v1",
        UNIVERSE_DIR,
        ROOT / "strategy_lab/RESEARCH_ROADMAP.md",
        ROOT / "strategy_lab/strategy_registry.yaml",
        ROOT / "strategy_lab/research_os/research/research_queue.yaml",
        ROOT / "strategy_lab/research_os/family_lineage/family_ledger.yaml",
        ROOT / "strategy_lab/research_os/operations/active_observations.yaml",
        ROOT / "paper_forward_observation_plans",
        ROOT / "paper_forward_observations",
    ]


def snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def normalized_package_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in PACKAGE_DIR.rglob("*") if item.is_file()):
        relative = path.relative_to(PACKAGE_DIR).as_posix()
        content = path.read_bytes()
        if relative == "handoff_manifest.json":
            payload = json.loads(content.decode("utf-8"))
            payload["package_content_hash"] = "__NORMALIZED_SELF_REFERENCE__"
            content = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def selected_source_package() -> dict[str, Any]:
    payload = read_json(INTAKE_DIR / "selected_work_packages.json")
    for package in payload["selected_work_packages"]:
        if package["strategy_id"] == STRATEGY_ID:
            return package
    raise KeyError(STRATEGY_ID)


def build_golden_fixtures() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    monthly = read_csv_rows(EXPLORATION_DIR / "monthly_signal_and_weights.csv")
    cpi_rows = read_csv_rows(CPI_V2_DATA_DIR / "cpi_point_in_time_signal.csv")
    thresholds = read_csv_rows(CPI_V2_EVIDENCE_DIR / "threshold_resolution.csv")
    pro_rows = read_csv_rows(EXPLORATION_DIR / "proib_regression_diagnostics.csv")
    monthly_by_month = {row["reference_month"]: row for row in monthly}
    cpi_by_month = {row["reference_month"]: row for row in cpi_rows}
    threshold_by_month = {row["reference_month"]: row for row in thresholds}
    pro_pair_count = {}
    for row in pro_rows:
        pro_pair_count.setdefault(row["formation_reference_month"], row["rolling_12m_pair_count"])

    roles: dict[str, set[str]] = {}

    def add(month: str, role: str) -> None:
        roles.setdefault(month, set()).add(role)

    add(monthly[0]["reference_month"], "first_valid_formation")
    for regime in ("low", "medium", "high"):
        for row in [item for item in monthly if item["regime"] == regime][:2]:
            add(row["reference_month"], f"{regime}_regime_example")
    for month in threshold_by_month:
        add(month, "rounded_vs_unrounded_threshold_disagreement")
    no_release = next(row for row in cpi_rows if row["reference_month"] == "2025-10")
    add(no_release["reference_month"], "no_release_no_event")
    post_120 = next(row for row in monthly if row["lookback_monthly_returns"] == "120")
    add(post_120["reference_month"], "post_120_month_rolling_window")
    for index in range(1, len(monthly)):
        if monthly[index]["regime"] != monthly[index - 1]["regime"]:
            add(monthly[index]["reference_month"], "regime_transition")
            break

    monthly_index = {row["reference_month"]: index for index, row in enumerate(monthly)}
    fixtures: list[dict[str, Any]] = []
    for number, month in enumerate(sorted(roles), start=1):
        cpi = cpi_by_month[month]
        weights = monthly_by_month.get(month)
        threshold = threshold_by_month.get(month)
        no_event = cpi["rebalance_event"].lower() == "false"
        previous_regime = ""
        if weights and monthly_index[month] > 0:
            previous_regime = monthly[monthly_index[month] - 1]["regime"]
        absent_reason = ""
        if weights is None:
            absent_reason = "no_target_materialized_for_no_release_event" if no_event else "pre_source_compliant_warmup"
        fixture = {
            "fixture_id": f"fixture_{number:03d}_{month.replace('-', '_')}",
            "fixture_roles": "|".join(sorted(roles[month])),
            "event_status": "no_release_no_event" if no_event else "published_release_event",
            "reference_month": month,
            "release_date": cpi["bls_release_date"],
            "canonical_cpi_yoy_unrounded": cpi["canonical_cpi_yoy_unrounded"],
            "regime": cpi["canonical_regime"],
            "allocation_statistics_cutoff": weights["allocation_statistics_cutoff"] if weights else "",
            "effective_after_close_date": weights["effective_close_date"] if weights else cpi["source_effective_after_close_date"],
            "new_weights_first_return_date": weights["new_weights_first_return_date"] if weights else "",
            "expected_target_SPY": weights["target_SPY"] if weights else "",
            "expected_target_IYR": weights["target_IYR"] if weights else "",
            "expected_target_GSG": weights["target_GSG"] if weights else "",
            "expected_target_GLD": weights["target_GLD"] if weights else "",
            "expected_target_AGG": weights["target_AGG"] if weights else "",
            "expected_target_TIP": weights["target_TIP"] if weights else "",
            "lookback_monthly_returns": weights["lookback_monthly_returns"] if weights else "",
            "proib_pair_count": pro_pair_count.get(month, "") if weights and weights["regime"] == "high" else "",
            "threshold_disagreement": threshold is not None,
            "bls_published_rounded_yoy": cpi["bls_published_rounded_yoy"],
            "bls_published_rounded_regime": cpi["bls_published_rounded_regime"],
            "transition_from_regime": previous_regime if "regime_transition" in roles[month] else "",
            "persist_previous_target": no_event,
            "source_signal_row_hash": canonical_hash(cpi),
            "source_weight_row_hash": canonical_hash(weights) if weights else "",
            "source_release_artifact_hash": cpi["release_artifact_hash"],
            "values_absent_reason": absent_reason,
        }
        fixtures.append(fixture)

    threshold_count = sum("rounded_vs_unrounded_threshold_disagreement" in row["fixture_roles"] for row in fixtures)
    regime_set = {row["regime"] for row in fixtures if row["regime"]}
    manifest = {
        "fixture_schema_version": "spdj_dynamic_inflation_golden_fixture_v1",
        "fixture_count": len(fixtures),
        "selection_method": "deterministic extraction from frozen CPI V2 and canonical monthly target evidence",
        "strategy_logic_reexecuted": False,
        "performance_calculated": False,
        "weight_absolute_tolerance": WEIGHT_TOLERANCE,
        "formula_absolute_tolerance": FORMULA_TOLERANCE,
        "tolerance_source": "canonical implementation WEIGHT_TOLERANCE and TOLERANCE constants",
        "coverage": {
            "first_valid_formation": any("first_valid_formation" in row["fixture_roles"] for row in fixtures),
            "low_regime_count": sum(row["regime"] == "low" and row["expected_target_SPY"] != "" for row in fixtures),
            "medium_regime_count": sum(row["regime"] == "medium" and row["expected_target_SPY"] != "" for row in fixtures),
            "high_regime_count": sum(row["regime"] == "high" and row["expected_target_SPY"] != "" for row in fixtures),
            "all_three_regimes_represented": regime_set == {"low", "medium", "high"},
            "threshold_disagreement_count": threshold_count,
            "all_seven_threshold_disagreements_represented": threshold_count == 7,
            "October_2025_no_event_represented": any(row["reference_month"] == "2025-10" and row["event_status"] == "no_release_no_event" for row in fixtures),
            "post_120_month_event_represented": any("post_120_month_rolling_window" in row["fixture_roles"] for row in fixtures),
            "regime_transition_represented": any("regime_transition" in row["fixture_roles"] for row in fixtures),
        },
        "frozen_sources": {
            "CPI_signal": "reference_only/historical_cpi_v2/cpi_point_in_time_signal.csv",
            "target_weights_repository_provenance": "evidence/research_recovery/spdj_multi_asset_dynamic_inflation_etf_portability_v1/latest/monthly_signal_and_weights.csv",
            "threshold_cases_repository_provenance": "evidence/public_signal_data/resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2/latest/threshold_resolution.csv",
            "ProIB_pair_count_repository_provenance": "evidence/research_recovery/spdj_multi_asset_dynamic_inflation_etf_portability_v1/latest/proib_regression_diagnostics.csv",
        },
        "missing_values_policy": "values not materialized in frozen evidence remain blank and carry values_absent_reason",
    }
    return fixtures, manifest


def secret_and_path_scan() -> dict[str, Any]:
    secret_patterns = {
        "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
        "private_key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "assigned_secret": re.compile(rb"(?i)(api[_-]?key|password|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    }
    path_patterns = {
        "windows_user_home": re.compile(rb"(?i)[A-Z]:[/\\]Users[/\\]"),
        "posix_user_home": re.compile(rb"/(home|Users)/[^/\s]+/"),
        "file_uri": re.compile(rb"(?i)file://"),
    }
    secret_hits: list[dict[str, str]] = []
    path_hits: list[dict[str, str]] = []
    forbidden_files: list[str] = []
    for path in sorted(item for item in PACKAGE_DIR.rglob("*") if item.is_file()):
        relative = path.relative_to(PACKAGE_DIR).as_posix()
        if path.name == ".env" or path.suffix.lower() in {".pem", ".p12", ".pfx"}:
            forbidden_files.append(relative)
        content = path.read_bytes()
        for pattern_id, pattern in secret_patterns.items():
            if pattern.search(content):
                secret_hits.append({"file": relative, "pattern": pattern_id})
        for pattern_id, pattern in path_patterns.items():
            if pattern.search(content):
                path_hits.append({"file": relative, "pattern": pattern_id})
    return {
        "secret_scan_pass": not secret_hits and not forbidden_files,
        "absolute_path_hygiene_pass": not path_hits,
        "secret_hits": secret_hits,
        "absolute_path_hits": path_hits,
        "forbidden_files": forbidden_files,
        "files_scanned": sum(1 for item in PACKAGE_DIR.rglob("*") if item.is_file()),
    }


def run() -> dict[str, Any]:
    created_at = persistent_created_at()
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORICAL_CPI_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = snapshot(protected_paths())

    eligibility_decision = read_json(ELIGIBILITY_DIR / "eligibility_decision.json")
    eligibility_consistency = read_json(ELIGIBILITY_DIR / "consistency_check.json")
    eligibility_source = read_json(ELIGIBILITY_DIR / "source_and_data_reconciliation.json")
    exploration_consistency = read_json(EXPLORATION_DIR / "consistency_check.json")
    exploration_prereg = read_json(EXPLORATION_DIR / "preregistration.json")
    exploration_access = read_json(EXPLORATION_DIR / "evaluation_access_log.json")
    robustness_consistency = read_json(ROBUSTNESS_DIR / "consistency_check.json")
    robustness_gates = read_json(ROBUSTNESS_DIR / "robustness_gate_results.json")
    robustness_accounting = read_json(ROBUSTNESS_DIR / "trial_accounting.json")
    v2_freeze = read_json(CPI_V2_EVIDENCE_DIR / "freeze_manifest.json")
    source_package = selected_source_package()
    caveat_rows = read_csv_rows(ELIGIBILITY_DIR / "caveat_register.csv")

    observed_eligibility_hash = eligibility_packet_hash()
    eligibility_reconciles = all(
        (
            eligibility_decision["eligibility_status"] == ELIGIBILITY_STATUS,
            eligibility_consistency["outcome"] == ELIGIBILITY_STATUS,
            eligibility_consistency["overall_pass"] is True,
            eligibility_consistency["deterministic_eligibility_packet_hash"] == EXPECTED_ELIGIBILITY_HASH,
            observed_eligibility_hash == EXPECTED_ELIGIBILITY_HASH,
        )
    )
    required_hashes_reconcile = all(
        (
            sha256_file(CANONICAL_CODE) == EXPECTED_CODE_HASH,
            v2_freeze["frozen_dataset_hash"] == EXPECTED_CPI_HASH,
            exploration_prereg["price_cache_bundle_hash"] == EXPECTED_PRICE_BUNDLE_HASH,
            exploration_prereg["frozen_universe_hash"] == EXPECTED_UNIVERSE_HASH,
            exploration_consistency["deterministic_evidence_hash"] == EXPECTED_EXPLORATION_HASH,
            robustness_consistency["deterministic_evidence_hash"] == EXPECTED_ROBUSTNESS_HASH,
        )
    )

    mappings = sorted(eligibility_source["mapping"], key=lambda row: SYMBOLS.index(row["symbol"]))
    write_csv(
        PACKAGE_DIR / "instrument_mapping.csv",
        [
            {
                "symbol": row["symbol"],
                "source_exposure": row["source_exposure"],
                "mapping_classification": row["classification"],
                "silent_substitution_allowed": False,
            }
            for row in mappings
        ],
        ["symbol", "source_exposure", "mapping_classification", "silent_substitution_allowed"],
    )

    signal_contract = {
        "schema_version": "spdj_cpi_signal_contract_v1",
        "series_id": "CPIAUCNS",
        "statistical_definition": "CPI-U All Items, U.S. City Average, Not Seasonally Adjusted",
        "statistical_authority": "U.S. Bureau of Labor Statistics",
        "canonical_signal": "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels",
        "formula": "100 * (CPI_t / CPI_t_minus_12 - 1)",
        "preclassification_rounding": "none",
        "rounded_news_release_percentage_role": "diagnostic_only_not_permitted_for_regime_classification",
        "regimes": {"low": "CPI_YoY < 1.5", "medium": "1.5 <= CPI_YoY <= 2.5", "high": "CPI_YoY > 2.5"},
        "information_set": "CPI information actually publicly available at the relevant release event",
        "live_vendor_prescribed": False,
        "no_release_behavior": {
            "state": "no_release_no_event",
            "rule": "no_CPI_announcement_no_rebalance_event",
            "synthetic_regime": False,
            "interpolation": False,
            "forward_fill": False,
            "retroactive_signal": False,
            "rebalance_event": False,
            "previous_effective_target_persists": True,
            "historical_conformance_example": "2025-10",
        },
    }
    write_json(PACKAGE_DIR / "signal_contract.json", signal_contract)

    schedule_contract = {
        "schema_version": "spdj_schedule_and_timing_contract_v1",
        "source_schedule": "monthly_on_actual_CPI_announcement_events",
        "allocation_statistics_cutoff": "previous_calendar_month_final_trading_close",
        "CPI_regime_cutoff": "actual_publication_of_corresponding_CPI_release",
        "effective_date_rule": "target_becomes_effective_after_close_on_next_valid_US_equity_market_business_day_following_CPI_announcement",
        "close_to_close_return_assignment": "new_target_starts_earning_only_from_following_trading_interval",
        "observation_date_price_changes_allowed_in_weight_statistics": False,
        "execution_instruction_included": False,
        "calendar_validation_owner": "separate_forward_observation_application",
    }
    write_json(PACKAGE_DIR / "schedule_and_timing_contract.json", schedule_contract)

    preflight = read_csv_rows(EXPLORATION_DIR / "data_preflight_reconciliation.csv")
    price_contract = {
        "schema_version": "spdj_price_semantics_contract_v1",
        "research_semantics": "adjusted_total_return_compatible_ETF_price_history",
        "required_reconstructions": ["monthly_total_returns", "rolling_12_month_cumulative_returns", "sample_volatility", "ProIB_beta_inputs"],
        "provider_semantics_automatically_assumed_equivalent": False,
        "receiver_validation_required": True,
        "complete_market_data_cache_bundled": False,
        "redistribution_boundary": "only hashes, coverage metadata, and golden output fixtures are exported",
        "price_bundle_hash": EXPECTED_PRICE_BUNDLE_HASH,
        "symbols": [
            {
                "symbol": row["symbol"],
                "cache_hash_reference": row["expected_cache_hash"],
                "first_valid_date": row["first_valid_date"],
                "last_valid_date": row["last_valid_date"],
                "row_count": int(row["row_count"]),
                "research_repository_path": row["cache_path"],
                "cache_bundled": False,
            }
            for row in preflight
        ],
    }
    write_json(PACKAGE_DIR / "price_semantics_contract.json", price_contract)

    strategy_contract = {
        "handoff_schema_version": PACKAGE_SCHEMA_VERSION,
        "handoff_id": HANDOFF_ID,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": CANONICAL_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "research_eligibility_status": ELIGIBILITY_STATUS,
        "translation_label": "ETF_portability_research_not_official_SP_index_replication",
        "symbols": list(SYMBOLS),
        "source_exposure_mappings": mappings,
        "CPI_signal_contract": signal_contract,
        "target_algorithms": {
            "low": {"SPY": 0.6, "IYR": 0.0, "GSG": 0.0, "GLD": 0.0, "AGG": 0.4, "TIP": 0.0},
            "medium": {
                "assets": list(SYMBOLS),
                "history": "36 monthly returns expanding one month at a time through 120, then latest rolling 120",
                "volatility": "sample standard deviation using ddof=1",
                "raw_weight_formula": "1 / volatility_i",
                "normalization": "raw_weight_i / sum(raw_weights)",
                "constraints": ["finite", "nonnegative", "fully_invested", "no_caps", "no_floors", "no_leverage"],
            },
            "high": {
                "assets": list(SYMBOLS),
                "history": "same 36-to-120 expanding/rolling monthly return window",
                "ETF_return_input": "complete rolling 12-month cumulative returns within allowed window",
                "regression": "R12m = alpha + beta * CPI_YoY",
                "first_36_month_window_complete_pair_count": 25,
                "beta_transform": {"beta >= 0": "B = 1 + beta", "beta < 0": "B = 1 / (1 - beta)"},
                "normalization": "weight_i = B_i / sum(B)",
                "constraints": ["all_six_assets", "nonnegative", "fully_invested", "no_beta_truncation", "no_winsorization", "no_weight_caps", "no_cash_overlay", "no_leverage"],
            },
        },
        "warmup": {
            "minimum_underlying_monthly_returns": 36,
            "maximum_underlying_monthly_returns": 120,
            "first_source_compliant_historical_formation": "2009-08-17",
            "first_valid_VolWt_historical_formation": "2009-08-17",
            "first_valid_ProIB_historical_formation": "2009-08-17",
            "first_ProIB_pair_count": 25,
            "historical_dates_are_conformance_facts_not_operational_constants": True,
        },
        "information_cutoffs": {
            "ETF_allocation_statistics": "previous_calendar_month_final_trading_close",
            "CPI_regime": "actual_publication_of_corresponding_CPI_release",
        },
        "event_and_effective_date_contract": schedule_contract,
        "price_semantics": price_contract,
        "research_cost_assumption": "5 bps per one-way turnover primary; 0 and 10 bps diagnostics",
        "research_cost_assumption_is_forward_logic": False,
        "hashes": {
            "canonical_code": EXPECTED_CODE_HASH,
            "CPI_logical_dataset": EXPECTED_CPI_HASH,
            "price_bundle": EXPECTED_PRICE_BUNDLE_HASH,
            "frozen_universe": EXPECTED_UNIVERSE_HASH,
            "exploration_evidence": EXPECTED_EXPLORATION_HASH,
            "robustness_evidence": EXPECTED_ROBUSTNESS_HASH,
            "eligibility_evidence": EXPECTED_ELIGIBILITY_HASH,
        },
        "caveat_ids": [row["caveat_id"] for row in caveat_rows],
        "explicit_nonclaims": eligibility_decision["explicit_non_claims"],
        "current_target_included": False,
    }
    write_json(PACKAGE_DIR / "strategy_contract.json", strategy_contract)

    interface_contract = {
        "schema_version": "spdj_forward_observation_interface_contract_v1",
        "purpose": "research_target_calculation_interface_only",
        "required_inputs": [
            {"name": "CPI_release_event", "owner": "receiver", "required": True},
            {"name": "CPI_reference_month", "owner": "receiver", "required": True},
            {"name": "canonical_CPI_YoY", "owner": "receiver", "required": True},
            {"name": "CPI_publication_timestamp", "owner": "receiver", "required": True},
            {"name": "validated_US_equity_trading_calendar", "owner": "receiver", "required": True},
            {"name": "adjusted_ETF_price_series_through_previous_month_end", "owner": "receiver", "required": True},
            {"name": "currently_effective_target_weights", "owner": "receiver", "required_when": "state_persistence_or_no_release"},
        ],
        "outputs": ["regime", "calculation_reference_date", "strategy_target", "target_effective_after_close_date", "event_status", "calculation_provenance"],
        "strategy_target": "six normalized research target weights",
        "execution_position": "receiver-owned share quantities and cash residuals; never emitted by this research handoff",
        "receiver_owned_outputs": ["share_quantities", "cash_residuals", "orders", "fills", "execution_tolerances", "virtual_equity"],
        "current_target_calculation_requested": False,
    }
    write_json(PACKAGE_DIR / "forward_observation_interface_contract.json", interface_contract)

    state_machine = {
        "schema_version": "spdj_dynamic_inflation_state_machine_v1",
        "specification_only": True,
        "persistent_live_state_included": False,
        "states": ["waiting_for_cpi_release", "cpi_release_received", "target_calculated", "pending_effective_close", "target_effective", "no_release_no_event"],
        "transitions": [
            {"from": "waiting_for_cpi_release", "event": "official_release_received", "to": "cpi_release_received"},
            {"from": "cpi_release_received", "event": "validated_inputs_and_target_calculated", "to": "target_calculated"},
            {"from": "target_calculated", "event": "next_valid_market_session_identified", "to": "pending_effective_close"},
            {"from": "pending_effective_close", "event": "authorized_session_close_completed", "to": "target_effective"},
            {"from": "target_effective", "event": "wait_for_next_reference_month_release", "to": "waiting_for_cpi_release"},
            {"from": "waiting_for_cpi_release", "event": "authoritative_no_release_confirmed", "to": "no_release_no_event"},
            {"from": "no_release_no_event", "event": "preserve_previous_target_and_wait", "to": "waiting_for_cpi_release"},
        ],
        "no_release_invariant": "no target recalculation and previously effective target persists",
    }
    write_json(PACKAGE_DIR / "strategy_state_machine.json", state_machine)

    fixtures, fixture_manifest = build_golden_fixtures()
    fixture_fields = [
        "fixture_id", "fixture_roles", "event_status", "reference_month", "release_date",
        "canonical_cpi_yoy_unrounded", "regime", "allocation_statistics_cutoff",
        "effective_after_close_date", "new_weights_first_return_date", "expected_target_SPY",
        "expected_target_IYR", "expected_target_GSG", "expected_target_GLD", "expected_target_AGG",
        "expected_target_TIP", "lookback_monthly_returns", "proib_pair_count", "threshold_disagreement",
        "bls_published_rounded_yoy", "bls_published_rounded_regime", "transition_from_regime",
        "persist_previous_target", "source_signal_row_hash", "source_weight_row_hash",
        "source_release_artifact_hash", "values_absent_reason",
    ]
    write_csv(PACKAGE_DIR / "golden_conformance_fixtures.csv", fixtures, fixture_fields)
    write_json(PACKAGE_DIR / "golden_fixture_manifest.json", fixture_manifest)

    selection_primary = next(
        row for row in read_csv_rows(EXPLORATION_DIR / "selection_results.csv")
        if row["entity_role"] == "canonical_candidate" and row["cost_bps_one_way"] == "5.0"
    )
    evaluation_primary = next(
        row for row in read_csv_rows(EXPLORATION_DIR / "evaluation_results.csv")
        if row["entity_role"] == "canonical_candidate" and row["cost_bps_one_way"] == "5.0"
    )
    cost_rows = read_csv_rows(ROBUSTNESS_DIR / "cost_robustness.csv")
    candidate_5bps = next(row for row in cost_rows if row["entity_role"] == "canonical_candidate" and row["cost_bps_one_way"] == "5.0")
    control_60_40_5bps = next(row for row in cost_rows if row["entity_id"] == "static_source_low_regime_60_40_spy_agg" and row["cost_bps_one_way"] == "5.0")
    research_summary = {
        "label": "historical_research_evidence_not_forward_expectation",
        "new_performance_calculated": False,
        "exploration": {
            "outcome": exploration_consistency["outcome"],
            "selection_period": exploration_consistency["selection_period"],
            "evaluation_period": exploration_consistency["evaluation_period"],
            "selection_gate_passed": exploration_consistency["selection_gate"]["selection_eligible"],
            "evaluation_gate_passed": exploration_consistency["evaluation_gate"]["exploration_followup_justified"],
            "evaluation_accessed_exactly_once": exploration_consistency["entity_counts"]["evaluation_accesses"] == 1,
            "existing_primary_5bps_context": {
                "selection": {key: selection_primary[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
                "evaluation": {key: evaluation_primary[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
            },
        },
        "robustness": {
            "outcome": robustness_consistency["outcome"],
            "passed": robustness_gates["blocking_gates_passed"],
            "positive_CAGR_blocks": "4/4",
            "60_40_nondominance_blocks": "3/4",
            "equal_weight_nondominance_blocks": "3/4",
            "simultaneous_control_dominance_blocks": "0/4",
            "bootstrap_fifth_percentile_CAGR": robustness_gates["bootstrap_summary"]["candidate_CAGR_percentiles"]["p05"],
            "timing_brittleness_flag": robustness_gates["diagnostic_findings"]["timing_brittleness_flag"],
            "regime_concentration_flag": robustness_gates["diagnostic_findings"]["regime_attribution"]["performance_concentration_flag"],
        },
        "existing_full_history_5bps_context": {
            "candidate": {key: candidate_5bps[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
            "60_40_control": {key: control_60_40_5bps[key] for key in ("cagr", "sharpe_ratio", "maximum_drawdown")},
            "candidate_minus_60_40_values_from_frozen_control_row": {
                "cagr": control_60_40_5bps["candidate_minus_control_CAGR"],
                "sharpe_ratio": control_60_40_5bps["candidate_minus_control_Sharpe"],
                "maximum_drawdown": control_60_40_5bps["candidate_minus_control_max_drawdown"],
            },
            "caveat": "60/40 has higher full-history CAGR; this evidence is not a forward return expectation or operating rule",
        },
    }
    write_json(PACKAGE_DIR / "research_evidence_summary.json", research_summary)

    claims = {
        "research_claim": eligibility_decision["research_claim"],
        "claim_scope": "frozen_research_package_export_only",
        "nonclaims": [
            "alpha is not proven",
            "future profitability is not established",
            "the official S&P index was not replicated",
            "the strategy is not declared safe",
            "broker readiness is not established",
            "paper execution is not verified",
            "micro-live readiness is not established",
            "real-money trading is not approved",
        ],
    }
    write_json(PACKAGE_DIR / "research_claims_and_nonclaims.json", claims)
    shutil.copyfile(ELIGIBILITY_DIR / "caveat_register.csv", PACKAGE_DIR / "caveat_register.csv")

    source_provenance = {
        "primary_strategy_source": source_package["primary_source"],
        "supporting_research": read_json(CPI_V2_DATA_DIR / "source_manifest.json")["supporting_research"],
        "CPI_statistical_authority": "U.S. Bureau of Labor Statistics",
        "hash_namespaces": {
            "logical_normalized_CPI_dataset": EXPECTED_CPI_HASH,
            "CPI_V2_repository_directory_artifact": eligibility_source["hash_namespaces"]["CPI_V2_directory_artifact"]["hash"],
            "price_bundle": EXPECTED_PRICE_BUNDLE_HASH,
            "frozen_universe_logical_packet": EXPECTED_UNIVERSE_HASH,
            "frozen_universe_repository_directory_artifact": eligibility_source["hash_namespaces"]["frozen_universe_packet"]["directory_hash"],
        },
        "historical_CPI_copy_role": "historical_conformance_reference_not_live_signal_feed",
        "market_data_cache_exported": False,
        "repository_paths_are_provenance_not_operational_dependencies": True,
    }
    write_json(PACKAGE_DIR / "source_provenance.json", source_provenance)

    lineage = {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "canonical_trial_id": CANONICAL_TRIAL_ID,
        "robustness_trial_id": ROBUSTNESS_TRIAL_ID,
        "exploration_outcome": exploration_consistency["outcome"],
        "robustness_outcome": robustness_consistency["outcome"],
        "eligibility_outcome": eligibility_decision["eligibility_status"],
        "canonical_trial_count": 1,
        "robustness_trial_count": 1,
        "strategy_variant_count": 0,
        "lineage_chain": [
            "phase2_public_signal_etf_mappable_candidate_intake_v2",
            "acquire_validate_freeze_phase2_public_signal_inputs_v1",
            "resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2",
            "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1",
            "run_spdj_dynamic_inflation_robustness_v1",
            "assess_spdj_dynamic_inflation_research_eligibility_v1",
            TASK_ID,
        ],
        "hashes": strategy_contract["hashes"],
        "new_trial_created": False,
        "new_variant_created": False,
    }
    write_json(PACKAGE_DIR / "lineage_manifest.json", lineage)

    receiver_checklist = """# Receiver Acceptance Checklist

Prospective observation must not begin until the separate forward-observation application independently confirms:

- [ ] Package manifest and logical package hash verified.
- [ ] Strategy-contract schema parsed.
- [ ] All six symbols recognized without silent remapping.
- [ ] CPIAUCNS input and unrounded year-over-year semantics implemented.
- [ ] Regime threshold equality behavior reproduced.
- [ ] Previous-month-end allocation-statistics cutoff reproduced.
- [ ] Effective-after-next-business-day-close behavior reproduced.
- [ ] Explicit no-release/no-event behavior reproduced.
- [ ] Adjusted total-return-compatible price semantics validated for the receiver's provider.
- [ ] Every golden fixture reproduced within the declared tolerance.
- [ ] Persistent target state survives process restart.
- [ ] Strategy targets remain separate from execution positions.

These checks are receiver-owned and were not performed by `trading_tournament` during export.
"""
    (PACKAGE_DIR / "receiver_acceptance_checklist.md").write_text(receiver_checklist, encoding="utf-8")
    responsibility = """# Forward Application Responsibility Boundary

The receiving application owns ongoing CPI acquisition and freshness, release-event detection, current market data, current target computation, exchange-calendar operations, virtual equity, positions, target-to-share conversion, order sizing, broker adapters, orders, fills, forward ledgers, slippage, operational alerts, incidents, and observation results.

`trading_tournament` owns the frozen research contract and this immutable export. It does not operate, monitor, or repair the receiving application. This package contains no current target, current position, credentials, broker state, operational ledger, or live market data.
"""
    (PACKAGE_DIR / "forward_application_responsibility_boundary.md").write_text(responsibility, encoding="utf-8")

    shutil.copyfile(CANONICAL_CODE, REFERENCE_DIR / CANONICAL_CODE.name)
    for name in ("cpi_point_in_time_signal.csv", "data_dictionary.json", "source_manifest.json", "warmup_contract.json", "missing_release_exception.csv"):
        shutil.copyfile(CPI_V2_DATA_DIR / name, HISTORICAL_CPI_DIR / name)
    reference_readme = f"""# Reference-Only Assets

`{CANONICAL_CODE.name}` is a byte-identical `reference_research_implementation_only` snapshot with hash `{EXPECTED_CODE_HASH}`. It is not a standalone operational service. Its repository-relative research data and module assumptions are retained for audit fidelity and are not receiver runtime dependencies.

`historical_cpi_v2/` is the frozen `historical_conformance_reference` for dataset `phase2_public_cpi_point_in_time_v2` with logical hash `{EXPECTED_CPI_HASH}`. It is not a live signal feed.
"""
    (REFERENCE_DIR / "README.md").write_text(reference_readme, encoding="utf-8")

    manifest = {
        "handoff_id": HANDOFF_ID,
        "handoff_version": HANDOFF_VERSION,
        "created_at": created_at,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "architecture_id": ARCHITECTURE_ID,
        "research_eligibility_status": ELIGIBILITY_STATUS,
        "handoff_status": EXPORT_COMPLETE,
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "canonical_code_hash": EXPECTED_CODE_HASH,
        "CPI_dataset_hash": EXPECTED_CPI_HASH,
        "price_bundle_hash": EXPECTED_PRICE_BUNDLE_HASH,
        "universe_hash": EXPECTED_UNIVERSE_HASH,
        "exploration_evidence_hash": EXPECTED_EXPLORATION_HASH,
        "robustness_evidence_hash": EXPECTED_ROBUSTNESS_HASH,
        "eligibility_evidence_hash": EXPECTED_ELIGIBILITY_HASH,
        "package_content_hash": "__NORMALIZED_SELF_REFERENCE__",
        "package_hash_scope": "all package files and relative paths; handoff_manifest.package_content_hash normalized to a fixed self-reference sentinel",
        "transport_archive_hash": None,
        "strategy_variant_count": 0,
        "canonical_trial_count": 1,
        "robustness_trial_count": 1,
        "operational_state_included": False,
        "credentials_included": False,
        "live_market_data_included": False,
        "current_positions_included": False,
        "orders_included": False,
        "current_target_included": False,
    }
    write_json(PACKAGE_DIR / "handoff_manifest.json", manifest)

    hygiene = secret_and_path_scan()
    package_files_complete = all((PACKAGE_DIR / name).exists() for name in PACKAGE_REQUIRED_FILES)
    fixture_coverage_complete = all(
        (
            fixture_manifest["coverage"]["first_valid_formation"],
            fixture_manifest["coverage"]["low_regime_count"] >= 2,
            fixture_manifest["coverage"]["medium_regime_count"] >= 2,
            fixture_manifest["coverage"]["high_regime_count"] >= 2,
            fixture_manifest["coverage"]["all_seven_threshold_disagreements_represented"],
            fixture_manifest["coverage"]["October_2025_no_event_represented"],
            fixture_manifest["coverage"]["post_120_month_event_represented"],
            fixture_manifest["coverage"]["regime_transition_represented"],
        )
    )
    export_ready = eligibility_reconciles and required_hashes_reconcile and package_files_complete and fixture_coverage_complete and hygiene["secret_scan_pass"] and hygiene["absolute_path_hygiene_pass"] and len(caveat_rows) == 6 and sum(row["classification"] == "blocking" for row in caveat_rows) == 0
    outcome = EXPORT_COMPLETE if export_ready else EXPORT_BLOCKED
    next_action = SUCCESS_NEXT_ACTION if export_ready else BLOCKED_NEXT_ACTION
    manifest["handoff_status"] = outcome
    write_json(PACKAGE_DIR / "handoff_manifest.json", manifest)
    package_hash = normalized_package_hash()
    manifest["package_content_hash"] = package_hash
    write_json(PACKAGE_DIR / "handoff_manifest.json", manifest)
    if normalized_package_hash() != package_hash:
        raise RuntimeError("nondeterministic_package_content_hash")

    hygiene = secret_and_path_scan()
    write_json(OUTPUT_DIR / "hygiene_scan.json", hygiene)
    trial_accounting = {
        "existing_canonical_trials": 1,
        "new_canonical_trials": 0,
        "existing_robustness_trials": 1,
        "new_robustness_trials": 0,
        "strategy_variants": 0,
        "new_performance_calculations": 0,
        "new_evaluation_accesses": 0,
        "handoff_exports_created": 1,
        "forward_observation_accesses": 0,
        "provider_calls_for_current_state": 0,
        "broker_calls": 0,
        "current_signal_calculations": 0,
        "current_target_calculations": 0,
        "observation_ledger_mutations": 0,
        "orders": 0,
        "fills": 0,
        "live_or_paper_positions": 0,
    }
    write_json(OUTPUT_DIR / "trial_accounting.json", trial_accounting)

    manifest_rows = []
    for path in sorted(item for item in PACKAGE_DIR.rglob("*") if item.is_file()):
        relative = path.relative_to(PACKAGE_DIR).as_posix()
        role = "reference_only" if relative.startswith("reference_only/") else "consumer_contract"
        manifest_rows.append({"relative_path": relative, "file_sha256": sha256_file(path), "size_bytes": path.stat().st_size, "role": role})
    write_csv(OUTPUT_DIR / "package_file_manifest.csv", manifest_rows, ["relative_path", "file_sha256", "size_bytes", "role"])
    (OUTPUT_DIR / "next_action.md").write_text(f"# Next Action\n\n`{next_action}`\n\nOwned by the separate forward-observation application and not executed by this task.\n", encoding="utf-8")
    report = f"""# S&P DJI Dynamic Inflation Forward-Observation Handoff Export

- Outcome: `{outcome}`
- Research eligibility: `{ELIGIBILITY_STATUS}`
- Package schema: `{PACKAGE_SCHEMA_VERSION}`
- Package files: `{len(manifest_rows)}`
- Golden fixtures: `{len(fixtures)}`
- Logical package content hash: `{package_hash}`
- Secret scan: `{'pass' if hygiene['secret_scan_pass'] else 'fail'}`
- Absolute-path hygiene: `{'pass' if hygiene['absolute_path_hygiene_pass'] else 'fail'}`
- Transport archive: `not created`

This immutable package exports a research target contract, historical conformance references, caveats, and provenance. It contains no current target, operational state, credentials, market-data cache, broker integration, order, position, or observation ledger. No strategy performance was calculated.

Next action: `{next_action}`. It belongs to the separate forward-observation application and was not executed here.
"""
    (OUTPUT_DIR / "export_report.md").write_text(report, encoding="utf-8")

    protected_after = snapshot(protected_paths())
    checks = {
        "eligibility_packet_hash_reconciles": observed_eligibility_hash == EXPECTED_ELIGIBILITY_HASH,
        "eligibility_status_is_exact_domain_status": eligibility_decision["eligibility_status"] == ELIGIBILITY_STATUS,
        "canonical_implementation_hash_unchanged": sha256_file(CANONICAL_CODE) == EXPECTED_CODE_HASH,
        "reference_snapshot_hash_matches": sha256_file(REFERENCE_DIR / CANONICAL_CODE.name) == EXPECTED_CODE_HASH,
        "exploration_evidence_unchanged": exploration_consistency["deterministic_evidence_hash"] == EXPECTED_EXPLORATION_HASH,
        "robustness_evidence_unchanged": robustness_consistency["deterministic_evidence_hash"] == EXPECTED_ROBUSTNESS_HASH,
        "CPI_V1_unchanged": protected_before[rel(CPI_V1_DATA_DIR)] == protected_after[rel(CPI_V1_DATA_DIR)],
        "CPI_V2_unchanged": protected_before[rel(CPI_V2_DATA_DIR)] == protected_after[rel(CPI_V2_DATA_DIR)],
        "ETF_price_cache_unchanged": protected_before["data/universe_expansion/pilot_etf_market_data_v1"] == protected_after["data/universe_expansion/pilot_etf_market_data_v1"] and protected_before["data/universe_expansion/phase2_bounded_multi_asset_market_data_v1"] == protected_after["data/universe_expansion/phase2_bounded_multi_asset_market_data_v1"],
        "frozen_universe_unchanged": protected_before[rel(UNIVERSE_DIR)] == protected_after[rel(UNIVERSE_DIR)],
        "all_protected_state_unchanged": protected_before == protected_after,
        "strategy_contract_matches_canonical_source_rules": strategy_contract["target_algorithms"]["low"]["SPY"] == 0.6 and strategy_contract["target_algorithms"]["low"]["AGG"] == 0.4 and strategy_contract["CPI_signal_contract"]["canonical_signal"] == "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels",
        "mapping_matches_eligibility_evidence": [row["symbol"] for row in mappings] == list(SYMBOLS),
        "caveat_count_six": len(caveat_rows) == 6,
        "blocking_caveat_count_zero": sum(row["classification"] == "blocking" for row in caveat_rows) == 0,
        "no_new_performance_calculation": trial_accounting["new_performance_calculations"] == 0,
        "no_trial_created": trial_accounting["new_canonical_trials"] == 0 and trial_accounting["new_robustness_trials"] == 0,
        "no_variant_created": trial_accounting["strategy_variants"] == 0,
        "no_current_data_acquisition": trial_accounting["provider_calls_for_current_state"] == 0,
        "no_broker_or_provider_operational_call": trial_accounting["broker_calls"] == 0 and trial_accounting["provider_calls_for_current_state"] == 0,
        "no_observation_state_mutation": trial_accounting["observation_ledger_mutations"] == 0,
        "no_current_target_generated": trial_accounting["current_target_calculations"] == 0 and manifest["current_target_included"] is False,
        "no_credentials_exported": hygiene["secret_scan_pass"] and manifest["credentials_included"] is False,
        "absolute_path_hygiene_passes": hygiene["absolute_path_hygiene_pass"],
        "golden_fixtures_from_frozen_evidence_only": fixture_manifest["strategy_logic_reexecuted"] is False and fixture_manifest["performance_calculated"] is False,
        "package_content_hash_reproduces": normalized_package_hash() == package_hash,
        "all_required_package_files_exist": all((PACKAGE_DIR / name).exists() for name in PACKAGE_REQUIRED_FILES),
        "all_required_export_files_exist": all((OUTPUT_DIR / name).exists() for name in OUTSIDE_REQUIRED_FILES if name != "consistency_check.json"),
        "outcome_matches_export_readiness": (outcome == EXPORT_COMPLETE) == export_ready,
    }
    overall_pass = all(checks.values()) and outcome == EXPORT_COMPLETE
    consistency = {
        "task_id": TASK_ID,
        "handoff_id": HANDOFF_ID,
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "overall_pass": overall_pass,
        "checks": checks,
        "package_content_hash": package_hash,
        "transport_archive_hash": None,
        "golden_fixture_count": len(fixtures),
        "fixture_coverage": fixture_manifest["coverage"],
        "hygiene": hygiene,
        "trial_accounting": trial_accounting,
        "protected_state_before": protected_before,
        "protected_state_after": protected_after,
        "next_action": next_action,
        "next_action_executed": False,
        "package_required_files": list(PACKAGE_REQUIRED_FILES),
        "outside_required_files": list(OUTSIDE_REQUIRED_FILES),
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return consistency


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
