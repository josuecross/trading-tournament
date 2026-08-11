from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT


TASK_ID = "resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2"
OUTCOME_RESOLVED = "phase2_public_signal_contract_resolved_and_frozen"
OUTCOME_FAILED = "phase2_public_signal_contract_resolution_failed"
STRATEGY_ID = "spdj_multi_asset_dynamic_inflation_etf_portability_v1"
SERIES_ID = "CPIAUCNS"
V1_DATASET_ID = "phase2_public_cpi_point_in_time_v1"
V1_EXPECTED_FROZEN_HASH = "sha256:cac4891195e4c3054de4b680b7ddab7123dafefe25926040b4fbd32a3ee85d7e"
V2_DATASET_ID = "phase2_public_cpi_point_in_time_v2"
SIGNAL_CONTRACT_VERSION = "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels_v2"
CANONICAL_SIGNAL_RULE = "cpi_yoy_unrounded_from_point_in_time_CPIAUCNS_levels"
WARMUP_INTERPRETATION = "three_year_minimum_means_36_underlying_monthly_return_observations"
SOURCE_RESOLUTION_STATUS = "direction_owner_source_supported_portability_interpretation"
MISSING_RELEASE_RULE = "no_CPI_announcement_no_rebalance_event"

V1_DIR = ROOT / "data" / "public_signals" / V1_DATASET_ID
V1_EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "public_signal_data"
    / "acquire_validate_freeze_phase2_public_signal_inputs_v1"
    / "latest"
)
V2_DIR = ROOT / "data" / "public_signals" / V2_DATASET_ID
OUTPUT_DIR = ROOT / "evidence" / "public_signal_data" / TASK_ID / "latest"
UNIVERSE_DIR = (
    ROOT
    / "evidence"
    / "universe_expansion"
    / "phase2_bounded_multi_asset_research_universe_v1"
    / "latest"
)
PILOT_CACHE = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
PHASE2_CACHE = ROOT / "data" / "universe_expansion" / "phase2_bounded_multi_asset_market_data_v1"
PRIOR_INTAKE_DIR = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "phase2_public_signal_etf_mappable_candidate_intake_v2"
    / "latest"
)

PROTECTED_PATHS = (
    V1_DIR,
    V1_EVIDENCE_DIR,
    UNIVERSE_DIR,
    PILOT_CACHE,
    PHASE2_CACHE,
    PRIOR_INTAKE_DIR,
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "paper_forward_observations",
    ROOT / "paper_forward_observation_plans",
)

FROZEN_MAPPING = {
    "U.S. equity": "SPY",
    "U.S. REIT": "IYR",
    "broad commodities": "GSG",
    "gold": "GLD",
    "U.S. aggregate bonds": "AGG",
    "U.S. TIPS": "TIP",
}

EXPECTED_THRESHOLD_REGIMES = {
    "2006-12": "high",
    "2010-12": "low",
    "2013-03": "low",
    "2016-09": "low",
    "2017-01": "high",
    "2018-10": "high",
    "2024-08": "high",
}

SIGNAL_FIELDS = [
    "reference_month",
    "publication_status",
    "bls_release_date",
    "bls_release_time_et",
    "signal_available_timestamp",
    "source_effective_after_close_date",
    "release_source",
    "release_source_locator",
    "release_artifact_hash",
    "cpi_all_items_nsa_level_as_published",
    "prior_year_cpi_level",
    "prior_year_level_source",
    "canonical_cpi_yoy_unrounded",
    "canonical_regime",
    "bls_published_rounded_yoy",
    "bls_published_rounded_regime",
    "rounded_vs_unrounded_regime_disagreement",
    "rebalance_event",
    "point_in_time_safe",
    "signal_contract_version",
    "source_resolution_status",
    "allocation_persistence_rule",
    "forward_fill_used",
    "interpolation_used",
    "imputation_used",
    "parent_dataset_id",
    "parent_dataset_hash",
]

REQUIRED_V2_DATA_FILES = {
    "cpi_point_in_time_signal.csv",
    "source_manifest.json",
    "data_dictionary.json",
    "missing_release_exception.csv",
    "warmup_contract.json",
    "freeze_manifest.json",
}

REQUIRED_EVIDENCE_FILES = {
    "source_contract_resolution.md",
    "v1_v2_signal_diff.csv",
    "threshold_resolution.csv",
    "warmup_resolution.md",
    "missing_release_exception.csv",
    "signal_readiness_v2.json",
    "freeze_manifest.json",
    "consistency_check.json",
    "next_action.md",
}

SP_METHODOLOGY_URL = (
    "https://www.spglobal.com/spdji/en/documents/methodologies/"
    "methodology-sp-multi-asset-dynamic-inflation-strategy-index.pdf"
)
SP_RESEARCH_URL = (
    "https://www.spglobal.com/spdji/en/documents/research/"
    "research-a-dynamic-multi-asset-approach-to-inflation-hedging.pdf"
)


def scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: scalar(row.get(field, "")) for field in writer.fieldnames})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def hash_tree(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        return sha256_path(path)
    digest = hashlib.sha256()
    for item in sorted(child for child in path.rglob("*") if child.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def protected_snapshot() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hash_tree(path)
        for path in PROTECTED_PATHS
    }


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def add_months(value: str, amount: int) -> str:
    year, month = map(int, value.split("-"))
    index = year * 12 + month - 1 + amount
    return month_key(index // 12, index % 12 + 1)


def month_range(start: str, end: str) -> list[str]:
    values: list[str] = []
    cursor = start
    while cursor <= end:
        values.append(cursor)
        cursor = add_months(cursor, 1)
    return values


def decimal_text(value: Decimal, places: int = 12) -> str:
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def regime(value: Decimal) -> str:
    if value < Decimal("1.5"):
        return "low"
    if value <= Decimal("2.5"):
        return "medium"
    return "high"


def dataset_hash(file_hashes: dict[str, str]) -> str:
    payload = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def first_cache_date(path: Path) -> str:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        first = next(reader)
    return first.get("date") or first.get("timestamp", "")[:10]


def verify_v1_manifest() -> dict[str, Any]:
    manifest_path = V1_DIR / "freeze_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    core_checks = {
        path_text: sha256_path(ROOT / path_text) == expected_hash
        for path_text, expected_hash in manifest["core_file_hashes"].items()
    }
    raw_checks = {
        path_text: sha256_path(ROOT / path_text) == expected_hash
        for path_text, expected_hash in manifest["raw_input_hashes"].items()
    }
    return {
        "dataset_id": manifest["dataset_id"],
        "frozen_dataset_hash": manifest["frozen_dataset_hash"],
        "expected_frozen_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "manifest_hash_matches_expected": manifest["frozen_dataset_hash"] == V1_EXPECTED_FROZEN_HASH,
        "all_core_file_hashes_match": all(core_checks.values()),
        "all_raw_file_hashes_match": all(raw_checks.values()),
        "core_file_checks": core_checks,
        "raw_file_checks": raw_checks,
        "tree_hash": hash_tree(V1_DIR),
    }


def build_signal_rows() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    v1_rows = read_csv(V1_DIR / "cpi_point_in_time_signal.csv")
    v1_by_month = {row["reference_month"]: row for row in v1_rows}
    release_rows = read_csv(V1_DIR / "release_reconciliation.csv")
    missing_v1 = next(row for row in release_rows if row["reference_month"] == "2025-10")
    v1_freeze = json.loads((V1_DIR / "freeze_manifest.json").read_text(encoding="utf-8"))
    archive_hash = v1_freeze["raw_input_hashes"][relative(V1_DIR / "raw" / "bls_cpi_archive_index.html")]

    rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    value_checks: list[dict[str, Any]] = []

    for reference_month in month_range("2005-07", "2026-06"):
        if reference_month == "2025-10":
            row = {
                "reference_month": reference_month,
                "publication_status": "canceled_no_official_CPI_release",
                "bls_release_date": "",
                "bls_release_time_et": "",
                "signal_available_timestamp": "",
                "source_effective_after_close_date": "",
                "release_source": "U.S. Bureau of Labor Statistics CPI archive index",
                "release_source_locator": missing_v1["release_url"],
                "release_artifact_hash": archive_hash,
                "cpi_all_items_nsa_level_as_published": "",
                "prior_year_cpi_level": "",
                "prior_year_level_source": "not_applicable_no_release",
                "canonical_cpi_yoy_unrounded": "",
                "canonical_regime": "",
                "bls_published_rounded_yoy": "",
                "bls_published_rounded_regime": "",
                "rounded_vs_unrounded_regime_disagreement": False,
                "rebalance_event": False,
                "point_in_time_safe": True,
                "signal_contract_version": SIGNAL_CONTRACT_VERSION,
                "source_resolution_status": "source_consistent_exception_handling",
                "allocation_persistence_rule": MISSING_RELEASE_RULE,
                "forward_fill_used": False,
                "interpolation_used": False,
                "imputation_used": False,
                "parent_dataset_id": V1_DATASET_ID,
                "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
            }
            rows.append(row)
            diff_rows.append(
                {
                    "reference_month": reference_month,
                    "change_type": "explicit_missing_release_event_added",
                    "v1_row_status": "absent_from_canonical_signal_official_nonpublication_in_release_reconciliation",
                    "v2_publication_status": row["publication_status"],
                    "v1_strategy_regime": "",
                    "v2_canonical_regime": "",
                    "v1_published_rounded_yoy": "",
                    "v2_canonical_unrounded_yoy": "",
                    "cpi_level_changed": False,
                    "prior_year_level_changed": False,
                    "rebalance_event": False,
                    "notes": "No CPI announcement; no signal imputation and no rebalance event.",
                }
            )
            continue

        v1 = v1_by_month[reference_month]
        current = Decimal(v1["cpi_all_items_nsa_level_as_published"])
        prior = Decimal(v1["bls_prior_year_level_available_as_of_release"])
        recomputed = Decimal("100") * (current / prior - Decimal("1"))
        canonical_yoy = decimal_text(recomputed)
        canonical_regime = regime(recomputed)
        rounded_yoy = Decimal(v1["cpi_yoy_percent_as_published"])
        rounded_regime = regime(rounded_yoy)
        disagreement = canonical_regime != rounded_regime
        row = {
            "reference_month": reference_month,
            "publication_status": "published_official_CPI_release",
            "bls_release_date": v1["bls_release_date"],
            "bls_release_time_et": v1["bls_release_time_et"],
            "signal_available_timestamp": v1["signal_available_timestamp"],
            "source_effective_after_close_date": v1["source_effective_after_close_date"],
            "release_source": v1["release_source"],
            "release_source_locator": v1["release_source_locator"],
            "release_artifact_hash": v1["release_artifact_hash"],
            "cpi_all_items_nsa_level_as_published": str(current),
            "prior_year_cpi_level": str(prior),
            "prior_year_level_source": v1["prior_year_level_source"],
            "canonical_cpi_yoy_unrounded": canonical_yoy,
            "canonical_regime": canonical_regime,
            "bls_published_rounded_yoy": str(rounded_yoy),
            "bls_published_rounded_regime": rounded_regime,
            "rounded_vs_unrounded_regime_disagreement": disagreement,
            "rebalance_event": True,
            "point_in_time_safe": v1["point_in_time_safe"] == "true",
            "signal_contract_version": SIGNAL_CONTRACT_VERSION,
            "source_resolution_status": SOURCE_RESOLUTION_STATUS,
            "allocation_persistence_rule": "not_applicable_release_event_exists",
            "forward_fill_used": False,
            "interpolation_used": False,
            "imputation_used": False,
            "parent_dataset_id": V1_DATASET_ID,
            "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        }
        rows.append(row)
        value_checks.append(
            {
                "reference_month": reference_month,
                "level_unchanged": row["cpi_all_items_nsa_level_as_published"]
                == v1["cpi_all_items_nsa_level_as_published"],
                "prior_level_unchanged": row["prior_year_cpi_level"]
                == v1["bls_prior_year_level_available_as_of_release"],
                "v1_computed_yoy_reproduced": canonical_yoy == v1["computed_yoy_from_same_vintage"],
            }
        )
        if disagreement:
            expected = EXPECTED_THRESHOLD_REGIMES.get(reference_month, "unexpected")
            threshold = {
                "reference_month": reference_month,
                "current_cpi_level": str(current),
                "prior_year_cpi_level": str(prior),
                "recomputed_unrounded_yoy": canonical_yoy,
                "bls_published_rounded_yoy": str(rounded_yoy),
                "v1_rounded_regime": rounded_regime,
                "v2_canonical_unrounded_regime": canonical_regime,
                "expected_v2_regime": expected,
                "recomputation_matches_expected": canonical_regime == expected,
                "canonical_rule": CANONICAL_SIGNAL_RULE,
                "threshold_blocker_remaining": False,
            }
            threshold_rows.append(threshold)
            diff_rows.append(
                {
                    "reference_month": reference_month,
                    "change_type": "canonical_regime_changed_to_unrounded_CPIAUCNS_yoy",
                    "v1_row_status": "published_official_CPI_release",
                    "v2_publication_status": row["publication_status"],
                    "v1_strategy_regime": rounded_regime,
                    "v2_canonical_regime": canonical_regime,
                    "v1_published_rounded_yoy": str(rounded_yoy),
                    "v2_canonical_unrounded_yoy": canonical_yoy,
                    "cpi_level_changed": False,
                    "prior_year_level_changed": False,
                    "rebalance_event": True,
                    "notes": "V1 level inputs preserved; only source-contract normalization changed.",
                }
            )

    return rows, threshold_rows, diff_rows, value_checks


def build_warmup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = read_csv(UNIVERSE_DIR / "phase2_frozen_universe.csv")
    selected = [row for row in manifest if row["symbol"] in set(FROZEN_MAPPING.values())]
    first_dates = {row["symbol"]: first_cache_date(ROOT / row["cache_path"]) for row in selected}
    earliest_common = max(first_dates.values())
    first_common_month_end = earliest_common[:7]
    first_monthly_return = add_months(first_common_month_end, 1)
    minimum_underlying_monthly_returns = 36
    last_return_month = add_months(first_monthly_return, minimum_underlying_monthly_returns - 1)
    first_rolling_12m_month = add_months(first_monthly_return, 11)
    pair_months = month_range(first_rolling_12m_month, last_return_month)
    pair_count = len(pair_months)
    expected_pair_count = minimum_underlying_monthly_returns - 12 + 1
    by_month = {row["reference_month"]: row for row in rows}
    formation_row = by_month[last_return_month]
    formation = formation_row["source_effective_after_close_date"]
    paired_rows = [by_month[month] for month in pair_months]
    all_pairs_available = all(
        row["publication_status"] == "published_official_CPI_release"
        and row["bls_release_date"]
        and row["bls_release_date"] <= formation_row["bls_release_date"]
        and row["point_in_time_safe"]
        for row in paired_rows
    )
    return {
        "interpretation": WARMUP_INTERPRETATION,
        "source_resolution_status": SOURCE_RESOLUTION_STATUS,
        "minimum_underlying_monthly_returns": minimum_underlying_monthly_returns,
        "maximum_underlying_monthly_returns": 120,
        "expansion_rule": "expand_one_month_at_a_time_from_36_through_120_then_use_latest_120",
        "first_valid_date_by_symbol": first_dates,
        "first_common_usable_date": earliest_common,
        "first_common_month_end": first_common_month_end,
        "first_monthly_return_month": first_monthly_return,
        "thirty_sixth_monthly_return_month": last_return_month,
        "first_complete_rolling_12m_return_month": first_rolling_12m_month,
        "first_valid_proib_pair_months": pair_months,
        "first_valid_proib_regression_pair_count": pair_count,
        "expected_pair_count_from_36_month_window": expected_pair_count,
        "all_proib_pairs_point_in_time_available": all_pairs_available,
        "price_history_extended_before_permitted_window": False,
        "first_valid_volwt_formation": formation,
        "first_valid_proib_formation": formation,
        "global_first_source_compliant_formation": formation,
        "source_public_evidence": {
            "research_dataset_approximate_start": "1997-03",
            "strategy_performance_sample_approximate_start": "2000-03",
            "expanding_window_minimum": "three_years",
            "ProIB_covered_by_expanding_construction": True,
            "interpretation_limit": (
                "Public evidence supports a portability contract; it does not establish proprietary S&P "
                "calculation internals beyond the published methodology and research description."
            ),
            "methodology_locator": SP_METHODOLOGY_URL,
            "research_locator": SP_RESEARCH_URL,
        },
    }


def data_dictionary() -> dict[str, Any]:
    return {
        "dataset_id": V2_DATASET_ID,
        "parent_dataset_id": V1_DATASET_ID,
        "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "difference_reason": "source_contract_resolution_only",
        "series_id": SERIES_ID,
        "canonical_signal_rule": CANONICAL_SIGNAL_RULE,
        "threshold_contract": {
            "low": "unrounded YoY < 1.5",
            "medium": "1.5 <= unrounded YoY <= 2.5",
            "high": "unrounded YoY > 2.5",
            "preprocessing_rounding": "none",
            "tolerance_band": "none",
        },
        "fields": {
            "publication_status": "Official publication status for the reference month",
            "canonical_cpi_yoy_unrounded": "100 * (CPI_t / CPI_t_minus_12 - 1) without threshold rounding",
            "canonical_regime": "Strategy-use regime derived only from canonical unrounded YoY",
            "bls_published_rounded_yoy": "One-decimal BLS release value retained as a diagnostic",
            "rebalance_event": "Whether an actual CPI announcement creates a source-defined event",
            "source_effective_after_close_date": "Next U.S. equity session after release; not a simulated trade",
        },
        "missing_release_contract": {
            "rule": MISSING_RELEASE_RULE,
            "classification": "source_consistent_exception_handling",
            "signal_forward_fill": False,
            "signal_imputation": False,
            "synthetic_regime": False,
        },
    }


def source_manifest(v1_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_id": V2_DATASET_ID,
        "series_id": SERIES_ID,
        "parent_dataset_id": V1_DATASET_ID,
        "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "parent_dataset_tree_hash": v1_status["tree_hash"],
        "difference_reason": "source_contract_resolution_only",
        "historical_payloads_changed": False,
        "network_acquisition_performed": False,
        "normalized_from": relative(V1_DIR / "cpi_point_in_time_signal.csv"),
        "missing_release_source": relative(V1_DIR / "release_reconciliation.csv"),
        "strategy_methodology": SP_METHODOLOGY_URL,
        "supporting_research": SP_RESEARCH_URL,
        "source_resolution_status": SOURCE_RESOLUTION_STATUS,
    }


def packet_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in OUTPUT_DIR.iterdir() if item.is_file() and item.name != "consistency_check.json"):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def run() -> dict[str, Any]:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = protected_snapshot()
    v1_before = verify_v1_manifest()

    signal_rows, threshold_rows, diff_rows, value_checks = build_signal_rows()
    warmup = build_warmup(signal_rows)
    missing_rows = [row for row in signal_rows if row["publication_status"] != "published_official_CPI_release"]

    write_csv(V2_DIR / "cpi_point_in_time_signal.csv", signal_rows, SIGNAL_FIELDS)
    write_csv(V2_DIR / "missing_release_exception.csv", missing_rows, SIGNAL_FIELDS)
    write_json(V2_DIR / "warmup_contract.json", warmup)
    write_json(V2_DIR / "data_dictionary.json", data_dictionary())
    write_json(V2_DIR / "source_manifest.json", source_manifest(v1_before))

    core_paths = [
        V2_DIR / "cpi_point_in_time_signal.csv",
        V2_DIR / "missing_release_exception.csv",
        V2_DIR / "warmup_contract.json",
        V2_DIR / "data_dictionary.json",
        V2_DIR / "source_manifest.json",
    ]
    core_hashes = {relative(path): sha256_path(path) for path in core_paths}
    frozen_hash = dataset_hash(core_hashes)

    unresolved: list[str] = []
    if not (
        v1_before["manifest_hash_matches_expected"]
        and v1_before["all_core_file_hashes_match"]
        and v1_before["all_raw_file_hashes_match"]
    ):
        unresolved.append("V1 dataset hash or component hashes do not match the frozen parent contract")
    if len(threshold_rows) != 7:
        unresolved.append(f"Expected 7 rounded/unrounded regime disagreements; found {len(threshold_rows)}")
    if {row["reference_month"] for row in threshold_rows} != set(EXPECTED_THRESHOLD_REGIMES):
        unresolved.append("Threshold disagreement month set differs from direction-owner resolution")
    if not all(row["recomputation_matches_expected"] for row in threshold_rows):
        unresolved.append("At least one recomputed disputed regime differs from the expected V2 classification")
    if not all(
        row["level_unchanged"] and row["prior_level_unchanged"] and row["v1_computed_yoy_reproduced"]
        for row in value_checks
    ):
        unresolved.append("A V1 CPI level changed or its unrounded YoY did not reproduce")
    if warmup["first_valid_proib_regression_pair_count"] != 25:
        unresolved.append("The 36-month underlying-history window did not produce 25 rolling-12-month pairs")
    if not warmup["all_proib_pairs_point_in_time_available"]:
        unresolved.append("At least one first-formation ProIB pair was unavailable at the formation decision")
    if warmup["first_valid_volwt_formation"] != "2009-08-17":
        unresolved.append("Mechanically derived first VolWt date differs from 2009-08-17")
    if warmup["first_valid_proib_formation"] != "2009-08-17":
        unresolved.append("Mechanically derived first ProIB date differs from 2009-08-17")
    if len(missing_rows) != 1 or missing_rows[0]["reference_month"] != "2025-10":
        unresolved.append("The official October 2025 nonpublication exception did not resolve uniquely")

    implementation_ready = not unresolved
    outcome = OUTCOME_RESOLVED if implementation_ready else OUTCOME_FAILED
    next_action = (
        "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1"
        if implementation_ready
        else "direction_owner_review_spdj_dynamic_inflation_remaining_source_gap_v1"
    )
    freeze_manifest = {
        "dataset_id": V2_DATASET_ID,
        "series_id": SERIES_ID,
        "task_id": TASK_ID,
        "parent_dataset_id": V1_DATASET_ID,
        "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "difference_reason": "source_contract_resolution_only",
        "frozen_dataset_hash": frozen_hash,
        "core_file_hashes": core_hashes,
        "immutable": True,
        "deterministic_from_preserved_V1_inputs": True,
        "historical_source_payloads_changed": False,
        "strategy_implemented": False,
        "trial_created": False,
        "backtest_run": False,
        "performance_metrics_calculated": False,
        "forward_observation_accessed_or_changed": False,
    }
    write_json(V2_DIR / "freeze_manifest.json", freeze_manifest)

    threshold_fields = [
        "reference_month",
        "current_cpi_level",
        "prior_year_cpi_level",
        "recomputed_unrounded_yoy",
        "bls_published_rounded_yoy",
        "v1_rounded_regime",
        "v2_canonical_unrounded_regime",
        "expected_v2_regime",
        "recomputation_matches_expected",
        "canonical_rule",
        "threshold_blocker_remaining",
    ]
    diff_fields = [
        "reference_month",
        "change_type",
        "v1_row_status",
        "v2_publication_status",
        "v1_strategy_regime",
        "v2_canonical_regime",
        "v1_published_rounded_yoy",
        "v2_canonical_unrounded_yoy",
        "cpi_level_changed",
        "prior_year_level_changed",
        "rebalance_event",
        "notes",
    ]
    write_csv(OUTPUT_DIR / "threshold_resolution.csv", threshold_rows, threshold_fields)
    write_csv(OUTPUT_DIR / "v1_v2_signal_diff.csv", diff_rows, diff_fields)
    write_csv(OUTPUT_DIR / "missing_release_exception.csv", missing_rows, SIGNAL_FIELDS)
    readiness = {
        "task_id": TASK_ID,
        "task_outcome": outcome,
        "dataset_id": V2_DATASET_ID,
        "parent_dataset_id": V1_DATASET_ID,
        "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "point_in_time_safe": all(row["point_in_time_safe"] for row in signal_rows),
        "canonical_signal_rule": CANONICAL_SIGNAL_RULE,
        "threshold_disagreement_count": len(threshold_rows),
        "threshold_disagreement_blocker_count": 0 if implementation_ready else sum(
            not row["recomputation_matches_expected"] for row in threshold_rows
        ),
        "warmup_contract_status": "resolved_source_supported_portability_interpretation",
        "warmup_interpretation": WARMUP_INTERPRETATION,
        "minimum_underlying_monthly_returns": 36,
        "first_valid_volwt_formation": warmup["first_valid_volwt_formation"],
        "first_valid_proib_formation": warmup["first_valid_proib_formation"],
        "first_valid_proib_regression_pair_count": warmup["first_valid_proib_regression_pair_count"],
        "global_first_source_compliant_formation": warmup["global_first_source_compliant_formation"],
        "missing_release_exception_count": len(missing_rows),
        "unresolved_source_contract_count": len(unresolved),
        "unresolved_source_facts": unresolved,
        "frozen_dataset_hash": frozen_hash,
        "implementation_ready": implementation_ready,
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "signal_readiness_v2.json", readiness)
    write_json(OUTPUT_DIR / "freeze_manifest.json", freeze_manifest)

    (OUTPUT_DIR / "source_contract_resolution.md").write_text(
        f"""# S&P Dynamic Inflation Signal Contract Resolution V2

Outcome: `{outcome}`

The canonical strategy-use signal is now `{CANONICAL_SIGNAL_RULE}`. It is recomputed from the two official CPI-U All Items NSA levels preserved in V1 and is not rounded before the 1.5% and 2.5% thresholds. The BLS one-decimal 12-month rate remains a diagnostic.

All 251 V1 published-release rows retain their CPI levels, release dates, point-in-time provenance, and source artifact hashes. V2 adds the official October 2025 nonpublication as an explicit no-event row. No V1 source payload was edited or copied into a competing raw history.

Parent dataset: `{V1_DATASET_ID}`  
Parent hash: `{V1_EXPECTED_FROZEN_HASH}`  
Difference reason: `source_contract_resolution_only`

The warmup interpretation is `{WARMUP_INTERPRETATION}` under the bounded `direction_owner_source_supported_portability_interpretation`. This resolves a public portability contract only and does not claim knowledge of proprietary S&P calculation internals.
""",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "warmup_resolution.md").write_text(
        f"""# Warmup Resolution

Status: `resolved_source_supported_portability_interpretation`

- Interpretation: `{WARMUP_INTERPRETATION}`
- Minimum underlying monthly returns: `36`
- Maximum lookback: `120`
- First common month-end: `{warmup['first_common_month_end']}`
- First monthly return: `{warmup['first_monthly_return_month']}`
- Thirty-sixth monthly return: `{warmup['thirty_sixth_monthly_return_month']}`
- Complete rolling-12-month pairs at N=36: `{warmup['first_valid_proib_regression_pair_count']}`
- First valid VolWt formation: `{warmup['first_valid_volwt_formation']}`
- First valid ProIB formation: `{warmup['first_valid_proib_formation']}`
- Global first source-compliant formation: `{warmup['global_first_source_compliant_formation']}`

The official S&P research context describes an approximate March 1997 research-data start and March 2000 strategy-performance start, while the published construction begins its expanding window at three years and covers ProIB. Requiring 36 completed rolling-12-month beta observations would require additional undocumented prehistory and would not match that demonstrated early-history construction. Therefore V2 uses all 25 complete rolling-12-month observations available inside the first permitted 36-month underlying-history window. No price history before that window is introduced.

Official methodology: {SP_METHODOLOGY_URL}  
Supporting S&P research: {SP_RESEARCH_URL}

This is a source-supported portability interpretation, not a claim about proprietary S&P calculation internals. No performance evidence was accessed.
""",
        encoding="utf-8",
    )
    (OUTPUT_DIR / "next_action.md").write_text(
        f"# Exact Next Action\n\n`{next_action}`\n\nRecorded only; not executed.\n",
        encoding="utf-8",
    )

    protected_after = protected_snapshot()
    v1_after = verify_v1_manifest()
    actual_v2_files = {path.name for path in V2_DIR.iterdir() if path.is_file()}
    actual_evidence_without_consistency = {
        path.name for path in OUTPUT_DIR.iterdir() if path.is_file() and path.name != "consistency_check.json"
    }
    checks = {
        "V1_frozen_hash_matches": v1_after["frozen_dataset_hash"] == V1_EXPECTED_FROZEN_HASH,
        "V1_core_and_raw_hashes_match": v1_after["all_core_file_hashes_match"]
        and v1_after["all_raw_file_hashes_match"],
        "V1_tree_byte_identical": v1_before["tree_hash"] == v1_after["tree_hash"],
        "protected_state_unchanged": protected_before == protected_after,
        "required_V2_files_present": REQUIRED_V2_DATA_FILES <= actual_v2_files,
        "required_evidence_files_present_before_consistency": actual_evidence_without_consistency
        == REQUIRED_EVIDENCE_FILES - {"consistency_check.json"},
        "canonical_months_complete_and_ordered": [row["reference_month"] for row in signal_rows]
        == month_range("2005-07", "2026-06"),
        "canonical_rows_unique": len(signal_rows) == len({row["reference_month"] for row in signal_rows}),
        "published_CPI_levels_unchanged": all(
            row["level_unchanged"] and row["prior_level_unchanged"] for row in value_checks
        ),
        "unrounded_YoY_recomputed_from_V1_levels": all(
            row["v1_computed_yoy_reproduced"] for row in value_checks
        ),
        "exactly_seven_threshold_disagreements": len(threshold_rows) == 7,
        "seven_expected_classifications_reproduced": all(
            row["recomputation_matches_expected"] for row in threshold_rows
        )
        and {row["reference_month"] for row in threshold_rows} == set(EXPECTED_THRESHOLD_REGIMES),
        "no_rounding_before_threshold": all(
            row["canonical_regime"] == regime(Decimal(row["canonical_cpi_yoy_unrounded"]))
            for row in signal_rows
            if row["rebalance_event"]
        ),
        "threshold_blockers_zero": readiness["threshold_disagreement_blocker_count"] == 0,
        "warmup_36_month_contract": warmup["minimum_underlying_monthly_returns"] == 36,
        "ProIB_pair_count_25": warmup["first_valid_proib_regression_pair_count"] == 25,
        "ProIB_no_lookahead": warmup["all_proib_pairs_point_in_time_available"]
        and not warmup["price_history_extended_before_permitted_window"],
        "first_dates_recomputed": warmup["first_valid_volwt_formation"] == "2009-08-17"
        and warmup["first_valid_proib_formation"] == "2009-08-17"
        and warmup["global_first_source_compliant_formation"] == "2009-08-17",
        "October_2025_no_release_explicit": len(missing_rows) == 1
        and missing_rows[0]["reference_month"] == "2025-10"
        and not missing_rows[0]["rebalance_event"]
        and not missing_rows[0]["canonical_cpi_yoy_unrounded"],
        "November_2025_is_next_actual_event": next(
            row for row in signal_rows if row["reference_month"] == "2025-11"
        )["rebalance_event"],
        "no_forward_fill_interpolation_or_imputation": all(
            not row["forward_fill_used"] and not row["interpolation_used"] and not row["imputation_used"]
            for row in signal_rows
        ),
        "diff_limited_to_seven_threshold_rows_plus_missing_event": len(diff_rows) == 8
        and {row["reference_month"] for row in diff_rows}
        == set(EXPECTED_THRESHOLD_REGIMES) | {"2025-10"},
        "frozen_hash_reproducible": frozen_hash == dataset_hash(core_hashes),
        "unresolved_contract_count_zero": len(unresolved) == 0,
        "implementation_ready": implementation_ready,
        "no_strategy_trial_performance_or_forward_work": not freeze_manifest["strategy_implemented"]
        and not freeze_manifest["trial_created"]
        and not freeze_manifest["backtest_run"]
        and not freeze_manifest["performance_metrics_calculated"]
        and not freeze_manifest["forward_observation_accessed_or_changed"],
        "exact_next_action": next_action == "implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1",
    }
    consistency = {
        "task_id": TASK_ID,
        "task_outcome": outcome if all(checks.values()) else OUTCOME_FAILED,
        "overall_pass": all(checks.values()),
        "checks": checks,
        "parent_dataset_id": V1_DATASET_ID,
        "parent_dataset_hash": V1_EXPECTED_FROZEN_HASH,
        "parent_tree_hash_before": v1_before["tree_hash"],
        "parent_tree_hash_after": v1_after["tree_hash"],
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "frozen_dataset_hash": frozen_hash,
        "deterministic_evidence_packet_hash": packet_hash(),
        "entity_counts": {
            "public_signal_datasets_created": 1,
            "strategy_configurations_created": 0,
            "experiment_trials_created": 0,
            "backtests_run": 0,
            "performance_metrics_calculated": 0,
            "forward_observations_accessed_or_changed": 0,
            "broker_or_account_calls": 0,
        },
        "exact_next_action": next_action,
        "next_action_executed": False,
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "task_outcome": consistency["task_outcome"],
        "overall_pass": consistency["overall_pass"],
        "V1_preserved": checks["V1_tree_byte_identical"] and checks["V1_core_and_raw_hashes_match"],
        "V2_dataset_id": V2_DATASET_ID,
        "V2_dataset_hash": frozen_hash,
        "canonical_signal_rule": CANONICAL_SIGNAL_RULE,
        "threshold_disagreement_count": len(threshold_rows),
        "threshold_blockers_remaining": readiness["threshold_disagreement_blocker_count"],
        "warmup_interpretation": WARMUP_INTERPRETATION,
        "first_valid_volwt_formation": warmup["first_valid_volwt_formation"],
        "first_valid_proib_formation": warmup["first_valid_proib_formation"],
        "first_valid_proib_regression_pair_count": warmup["first_valid_proib_regression_pair_count"],
        "global_first_source_compliant_formation": warmup["global_first_source_compliant_formation"],
        "October_2025_exception": missing_rows[0]["publication_status"],
        "unresolved_source_contract_count": len(unresolved),
        "implementation_ready": implementation_ready,
        "protected_state_unchanged": checks["protected_state_unchanged"],
        "exact_next_action": next_action,
        "deterministic_evidence_packet_hash": consistency["deterministic_evidence_packet_hash"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
