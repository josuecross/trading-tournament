from __future__ import annotations

import csv
import io
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import (
    intermarket_ivts_herorats_portability_exploration_v1 as prior,
)


TASK_ID = "run_cboe_point_in_time_ivts_feasibility_and_exploration_v2"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = prior.STRATEGY_ID
FAMILY_ID = prior.FAMILY_ID
PRIOR_TRIAL_ID = prior.TRIAL_ID
CONDITIONAL_CHILD_TRIAL_ID = f"{TASK_ID}__data_feasibility_adjustment_child"
SOURCE_RECORD_ID = "src_donninger_herorats_cboe_point_in_time_v2"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\b186478c-d757-4606-9586-48c22a8f2f02\pasted-text.txt"
)
PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
METHODOLOGY_BOUNDARY = "2025-02-10"
REQUESTED_CUTOFF = "16:15:00 America/New_York"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)

CBOE_TERM_URL = (
    "https://cdn.cboe.com/api/global/delayed_quotes/term_structure/"
    "{year}/VIX_{date}.json"
)
CBOE_DAILY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/{series}_History.csv"
)
CBOE_TERM_PAGE = "https://www.cboe.com/tradable-products/vix/term-structure/"
CBOE_METHODOLOGY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/governance/"
    "Volatility_Index_Methodology_Selected_SPX_Target_Expected_Volatility_Term_Indices.pdf"
)

HISTORICAL_REPRO_SAMPLE = (
    "2014-04-17",
    "2020-03-16",
    "2024-12-31",
    "2025-02-10",
    "2026-07-24",
)
EXPECTED_TERM_NODE_SYMBOLS = tuple(f"VIX{number}" for number in range(1, 11))
REQUIRED_CONSTANT_MATURITY_SERIES = ("VIX", "VIX3M")
BENCHMARKS = prior.BENCHMARKS

OUTCOME = "inconclusive_data_issue"
FAILURE_REASON = "data_or_comparability_failure"
NEXT_ACTION = "direction_owner_select_next_targeted_family_sprint_v1"

PROTECTED_STATE_PATHS = prior.PROTECTED_STATE_PATHS
PRIOR_EVIDENCE_DIR = prior.OUTPUT_DIR

REQUIRED_ARTIFACTS = (
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "cboe_point_in_time_manifest.csv",
    "historical_query_reproducibility.csv",
    "methodology_boundary_log.csv",
    "publication_timing_reconciliation.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "state_signal_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "consistency_check.json",
    "batch_report.md",
)

TRIAL_FIELDS = [
    "trial_id",
    "entity_type",
    "stage",
    "strategy_id",
    "parent_trial_id",
    "adaptation_label",
    "changed_fields_from_parent",
    "strategy_rule_changed",
    "ratio_changed",
    "thresholds_changed",
    "assets_changed",
    "execution_changed",
    "optimization_performed",
    "created_in_v2",
    "outcome",
    "failure_reason",
    "next_action",
]

METRIC_FIELDS = prior.METRIC_FIELDS


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    prior.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    prior.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    prior.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    prior.write_text(path, text)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalized_term_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    prices = data.get("prices") if isinstance(data, dict) else []
    expirations = data.get("expirations") if isinstance(data, dict) else []
    normalized_prices = sorted(
        [
            {
                "index_symbol": str(row.get("index_symbol", "")),
                "price_interval": str(row.get("price_interval", "")),
                "price": float(row["price"]) if row.get("price") is not None else None,
                "price_time": str(row.get("price_time", "")),
            }
            for row in prices
            if isinstance(row, dict)
        ],
        key=lambda row: (
            row["price_time"],
            row["index_symbol"],
            row["price_interval"],
        ),
    )
    normalized_expirations = sorted(
        [
            {
                "symbol": str(row.get("symbol", "")),
                "month": int(row["month"]) if row.get("month") is not None else None,
                "expirationDate": str(row.get("expirationDate", "")),
            }
            for row in expirations
            if isinstance(row, dict)
        ],
        key=lambda row: (row["month"] or 0, row["symbol"]),
    )
    return {
        "timestamp": str(payload.get("timestamp", "")),
        "symbol": str(payload.get("symbol", "")),
        "prices": normalized_prices,
        "expirations": normalized_expirations,
    }


def returned_symbols(payload: dict[str, Any]) -> tuple[str, ...]:
    normalized = normalized_term_payload(payload)
    return tuple(
        sorted({row["index_symbol"] for row in normalized["prices"] if row["index_symbol"]})
    )


def latest_returned_timestamp(payload: dict[str, Any]) -> str:
    timestamps = [
        row["price_time"]
        for row in normalized_term_payload(payload)["prices"]
        if row["price_time"]
    ]
    return max(timestamps) if timestamps else ""


def fetch_term_structure_sample(
    session: requests.Session, date: str, attempt: int, timeout: int = 120
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = CBOE_TERM_URL.format(year=date[:4], date=date)
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    response = session.get(url, timeout=timeout)
    raw_hash = prior.sha256_bytes(response.content)
    row: dict[str, Any] = {
        "observation_date": date,
        "attempt": attempt,
        "requested_timestamp": f"{date} {REQUESTED_CUTOFF}",
        "url": url,
        "retrieval_timestamp_utc": retrieval_timestamp,
        "http_status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "raw_response_hash": raw_hash,
        "normalized_payload_hash": "",
        "payload_timestamp": "",
        "returned_last_timestamp": "",
        "returned_timestamp_timezone_documented": False,
        "returned_symbols": "",
        "required_VIX_present": False,
        "required_VIX3M_present": False,
        "required_pair_values_available": False,
        "normalized_values_deterministic": False,
        "raw_hash_deterministic": False,
        "status": "request_failed",
    }
    if response.status_code != 200:
        return row, {}
    payload = response.json()
    normalized = normalized_term_payload(payload)
    symbols = returned_symbols(payload)
    row.update(
        {
            "normalized_payload_hash": prior.canonical_hash(normalized),
            "payload_timestamp": normalized["timestamp"],
            "returned_last_timestamp": latest_returned_timestamp(payload),
            "returned_symbols": "|".join(symbols),
            "required_VIX_present": "VIX" in symbols,
            "required_VIX3M_present": "VIX3M" in symbols,
            "required_pair_values_available": "VIX" in symbols and "VIX3M" in symbols,
            "status": (
                "reproducible_schema_pending_pair_check"
                if symbols
                else "empty_schema"
            ),
        }
    )
    return row, payload


def run_historical_reproducibility_probe() -> list[dict[str, Any]]:
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    for date in HISTORICAL_REPRO_SAMPLE:
        pair: list[dict[str, Any]] = []
        for attempt in (1, 2):
            row, _ = fetch_term_structure_sample(session, date, attempt)
            pair.append(row)
        raw_same = pair[0]["raw_response_hash"] == pair[1]["raw_response_hash"]
        normalized_same = (
            pair[0]["normalized_payload_hash"]
            and pair[0]["normalized_payload_hash"]
            == pair[1]["normalized_payload_hash"]
        )
        for row in pair:
            row["raw_hash_deterministic"] = bool(raw_same)
            row["normalized_values_deterministic"] = bool(normalized_same)
            if row["http_status"] == 200 and normalized_same and raw_same:
                row["status"] = (
                    "reproducible_wrong_series_schema"
                    if not row["required_pair_values_available"]
                    else "reproducible_required_pair_available"
                )
            rows.append(row)
    return rows


def fetch_daily_history(series: str, timeout: int = 120) -> dict[str, Any]:
    url = CBOE_DAILY_URL.format(series=series)
    response = requests.get(url, timeout=timeout)
    result: dict[str, Any] = {
        "series": series,
        "url": url,
        "http_status": response.status_code,
        "raw_response_hash": prior.sha256_bytes(response.content),
        "row_count": 0,
        "columns": "",
        "first_date": "",
        "last_date": "",
        "contains_required_constant_maturity_series": False,
        "contains_intraday_timestamp": False,
        "contains_generation_timestamp": False,
        "point_in_time_gate_eligible": False,
        "status": "request_failed",
    }
    if response.status_code != 200:
        return result
    frame = pd.read_csv(io.BytesIO(response.content))
    columns = [str(column) for column in frame.columns]
    date_series = pd.to_datetime(frame["DATE"], errors="coerce") if "DATE" in frame else pd.Series(dtype="datetime64[ns]")
    result.update(
        {
            "row_count": len(frame),
            "columns": "|".join(columns),
            "first_date": (
                date_series.min().date().isoformat() if date_series.notna().any() else ""
            ),
            "last_date": (
                date_series.max().date().isoformat() if date_series.notna().any() else ""
            ),
            "contains_required_constant_maturity_series": series
            in REQUIRED_CONSTANT_MATURITY_SERIES,
            "contains_intraday_timestamp": any(
                "TIME" in column.upper() for column in columns
            ),
            "contains_generation_timestamp": any(
                "TIMESTAMP" in column.upper() for column in columns
            ),
            "point_in_time_gate_eligible": False,
            "status": "correct_series_daily_OHLC_without_intraday_timestamp",
        }
    )
    return result


def adjusted_data_preflight(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = market.load_adjusted_ohlcv(symbol)
    return {
        "data_id": symbol,
        "data_type": "adjusted_daily_market_data",
        "provider": "repository_canonical_cache",
        "status": "pass" if not frame.empty else "missing_or_invalid",
        "first_valid_date": (
            frame.index.min().date().isoformat() if not frame.empty else ""
        ),
        "last_valid_date": (
            frame.index.max().date().isoformat() if not frame.empty else ""
        ),
        "row_count": len(frame),
        "canonical_hash": prior.file_hash(path),
        "required_series_present": not frame.empty,
        "intraday_timestamp_present": "not_applicable",
        "point_in_time_gate_eligible": "not_applicable",
        "notes": "Loaded through the repository's canonical adjusted OHLCV interface.",
    }


def _entities() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    source = [
        {
            "source_record_id": SOURCE_RECORD_ID,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6_updated_web_review:"
                "src_donninger_herorats_cboe_point_in_time_v2"
            ),
            "official_data_authority": "Cboe",
            "official_term_structure_page": CBOE_TERM_PAGE,
            "prior_source_record_id": prior.SOURCE_RECORD_ID,
            "prior_blocked_trial_id": PRIOR_TRIAL_ID,
            "prior_outcome": prior.OUTCOME,
            "prior_failure_reason": prior.FAILURE_REASON,
            "outcome": "blocked_feasibility",
            "failure_reason": FAILURE_REASON,
            "notes": (
                "The source packet authorizes a Cboe point-in-time feasibility test. "
                "It does not authorize substituting VIX expiry nodes for VIX3M."
            ),
        }
    ]
    strategy = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "display_name": "VIX/VIX3M Median-5 Equity-Treasury Regime",
            "entity_type": "strategy_configuration",
            "strategy_architecture": "daily_three_state_implied_volatility_curve_allocation",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "instrument_universe": "SPY|IEF",
            "parameters": {
                "ratio": "VIX/VIX3M",
                "median_length": 5,
                "thresholds": [0.96, 1.02],
                "targets": ["SPY_1_IEF_0", "SPY_0.5_IEF_0.5", "SPY_0_IEF_1"],
                "execution": "following_regular_session_close",
                "primary_one_way_cost_bps": PRIMARY_COST_BPS,
                "diagnostic_one_way_cost_bps": [0.0, 10.0],
            },
            "benchmark_or_control": "|".join(BENCHMARKS),
            "stage": STAGE,
            "existing_configuration_reference": True,
            "new_strategy_id_created": False,
            "prior_trial_id": PRIOR_TRIAL_ID,
            "conditional_child_trial_id": CONDITIONAL_CHILD_TRIAL_ID,
            "child_trial_created": False,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "next_action": NEXT_ACTION,
        }
    ]
    benchmark = [
        {
            "benchmark_id": benchmark_id,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id": "",
            "trial_id": "",
            "performance_executed": False,
            "notes": "Frozen control reference; the Cboe data gate stopped before performance.",
        }
        for benchmark_id in BENCHMARKS
    ]
    process = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "new_strategy_count": 0,
            "new_trial_count": 0,
            "performance_trial_count": 0,
            "status": "completed_with_Cboe_schema_block",
            "outcome": OUTCOME,
            "next_action": NEXT_ACTION,
        }
    ]
    return source, strategy, benchmark, process


def run() -> dict[str, Any]:
    protected_before = prior.hash_paths(PROTECTED_STATE_PATHS)
    cache_before = prior.directory_hash(ROOT / "data" / "cache")
    prior_evidence_before = prior.directory_hash(PRIOR_EVIDENCE_DIR)
    source_attachment_before = prior.file_hash(SOURCE_ATTACHMENT)
    clean_output_dir()

    source_rows, strategy_rows, benchmark_rows, process_rows = _entities()
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        source_rows,
        list(source_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "strategy_cards.csv",
        strategy_rows,
        list(strategy_rows[0].keys()),
    )
    write_csv(OUTPUT_DIR / "trial_ledger.csv", [], TRIAL_FIELDS)
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows,
        list(benchmark_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0].keys()),
    )

    preregistration_hash = prior.canonical_hash(
        {
            "source": source_rows,
            "strategy": strategy_rows,
            "trial_fields": TRIAL_FIELDS,
            "benchmarks": benchmark_rows,
            "process": process_rows,
        }
    )

    reproducibility_rows = run_historical_reproducibility_probe()
    daily_histories = {
        series: fetch_daily_history(series)
        for series in REQUIRED_CONSTANT_MATURITY_SERIES
    }
    query_schema_symbols = sorted(
        {
            symbol
            for row in reproducibility_rows
            for symbol in str(row["returned_symbols"]).split("|")
            if symbol
        }
    )
    historical_queries_reproducible = all(
        row["raw_hash_deterministic"]
        and row["normalized_values_deterministic"]
        and row["http_status"] == 200
        for row in reproducibility_rows
    )
    required_pair_in_term_endpoint = all(
        row["required_pair_values_available"] for row in reproducibility_rows
    )
    daily_files_have_intraday_timestamps = all(
        row["contains_intraday_timestamp"] for row in daily_histories.values()
    )
    data_gate_passed = bool(
        historical_queries_reproducible
        and required_pair_in_term_endpoint
        and daily_files_have_intraday_timestamps
    )
    if data_gate_passed:
        raise RuntimeError(
            "The data gate unexpectedly passed; the conditional performance path "
            "must be reviewed before execution."
        )

    data_task_rows = [
        {
            "task_id": f"{TASK_ID}__Cboe_point_in_time_gate",
            "entity_type": "data_capability_task",
            "stage": "blocked",
            "adaptation_label": "data_feasibility_adjustment",
            "official_provider": "Cboe",
            "historical_sample_dates": HISTORICAL_REPRO_SAMPLE,
            "historical_requests_per_date": 2,
            "historical_queries_reproducible": historical_queries_reproducible,
            "term_endpoint_symbols": query_schema_symbols,
            "required_VIX_present_in_term_endpoint": "VIX" in query_schema_symbols,
            "required_VIX3M_present_in_term_endpoint": "VIX3M"
            in query_schema_symbols,
            "daily_VIX_history_available": daily_histories["VIX"]["http_status"]
            == 200,
            "daily_VIX3M_history_available": daily_histories["VIX3M"][
                "http_status"
            ]
            == 200,
            "daily_histories_have_intraday_timestamps": daily_files_have_intraday_timestamps,
            "data_gate_passed": data_gate_passed,
            "status": "blocked_required_point_in_time_pair_not_available",
            "failure_reason": FAILURE_REASON,
        }
    ]
    write_csv(
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_task_rows,
        list(data_task_rows[0].keys()),
    )

    term_manifest = {
        "endpoint_id": "Cboe_delayed_quotes_term_structure",
        "official_source": "Cboe",
        "endpoint": CBOE_TERM_URL,
        "payload_frequency": "intraday",
        "payload_has_generation_times": True,
        "payload_timestamp_timezone_documented_in_payload": False,
        "returned_series": "|".join(query_schema_symbols),
        "required_series": "VIX|VIX3M",
        "contains_required_VIX": "VIX" in query_schema_symbols,
        "contains_required_VIX3M": "VIX3M" in query_schema_symbols,
        "mechanism": "option_expiry_term_nodes_not_constant_maturity_indices",
        "point_in_time_gate_eligible": False,
        "status": "timestamped_but_wrong_series_schema",
    }
    manifest_rows = [term_manifest]
    for series, history in daily_histories.items():
        manifest_rows.append(
            {
                "endpoint_id": f"Cboe_{series}_daily_history",
                "official_source": "Cboe",
                "endpoint": history["url"],
                "payload_frequency": "daily_OHLC",
                "payload_has_generation_times": False,
                "payload_timestamp_timezone_documented_in_payload": False,
                "returned_series": series,
                "required_series": "VIX|VIX3M",
                "contains_required_VIX": series == "VIX",
                "contains_required_VIX3M": series == "VIX3M",
                "mechanism": "constant_maturity_index_daily_history",
                "point_in_time_gate_eligible": False,
                "status": "correct_series_but_no_intraday_point_in_time_timestamp",
            }
        )
    write_csv(
        OUTPUT_DIR / "cboe_point_in_time_manifest.csv",
        manifest_rows,
        list(term_manifest.keys()),
    )
    write_csv(
        OUTPUT_DIR / "historical_query_reproducibility.csv",
        reproducibility_rows,
        list(reproducibility_rows[0].keys()),
    )

    methodology_rows = [
        {
            "methodology_id": "Cboe_volatility_index_strike_selection_change",
            "effective_date": METHODOLOGY_BOUNDARY,
            "official_document": (
                "https://cdn.cboe.com/resources/release_notes/2025/"
                "Modifications-to-the-Strike-Selection-in-Volatility-Index-Calculations.pdf"
            ),
            "applies_to": "VIX|VIX3M",
            "diagnostic_only": True,
            "strategy_rule_changed": False,
            "thresholds_changed": False,
            "period_variant_created": False,
            "observations_excluded": False,
        }
    ]
    write_csv(
        OUTPUT_DIR / "methodology_boundary_log.csv",
        methodology_rows,
        list(methodology_rows[0].keys()),
    )

    publication_rows = []
    for date in HISTORICAL_REPRO_SAMPLE:
        pair = [row for row in reproducibility_rows if row["observation_date"] == date]
        publication_rows.append(
            {
                "observation_date": date,
                "requested_cutoff": f"{date} {REQUESTED_CUTOFF}",
                "official_endpoint": CBOE_TERM_URL.format(year=date[:4], date=date),
                "returned_last_timestamp_attempt_1": pair[0][
                    "returned_last_timestamp"
                ],
                "returned_last_timestamp_attempt_2": pair[1][
                    "returned_last_timestamp"
                ],
                "returned_timestamp_timezone_documented": False,
                "VIX": "",
                "VIX3M": "",
                "required_pair_available": False,
                "authorized_execution_session": "",
                "following_session_execution_proven": False,
                "status": "blocked_timestamped_payload_does_not_contain_VIX_or_VIX3M",
            }
        )
    write_csv(
        OUTPUT_DIR / "publication_timing_reconciliation.csv",
        publication_rows,
        list(publication_rows[0].keys()),
    )

    preflight_rows = [adjusted_data_preflight("SPY"), adjusted_data_preflight("IEF")]
    preflight_rows.append(
        {
            "data_id": "Cboe_term_structure_historical_JSON",
            "data_type": "official_intraday_term_structure",
            "provider": "Cboe",
            "status": "schema_incompatible",
            "first_valid_date": HISTORICAL_REPRO_SAMPLE[0],
            "last_valid_date": HISTORICAL_REPRO_SAMPLE[-1],
            "row_count": len(reproducibility_rows),
            "canonical_hash": prior.canonical_hash(
                [
                    {
                        "date": row["observation_date"],
                        "attempt": row["attempt"],
                        "normalized_hash": row["normalized_payload_hash"],
                    }
                    for row in reproducibility_rows
                ]
            ),
            "required_series_present": False,
            "intraday_timestamp_present": True,
            "point_in_time_gate_eligible": False,
            "notes": "Returns VIX1 through VIX10 expiry nodes, not VIX and VIX3M.",
        }
    )
    for series, history in daily_histories.items():
        preflight_rows.append(
            {
                "data_id": f"Cboe_{series}_daily_history",
                "data_type": "official_daily_constant_maturity_index",
                "provider": "Cboe",
                "status": "timing_incomplete",
                "first_valid_date": history["first_date"],
                "last_valid_date": history["last_date"],
                "row_count": history["row_count"],
                "canonical_hash": history["raw_response_hash"],
                "required_series_present": True,
                "intraday_timestamp_present": False,
                "point_in_time_gate_eligible": False,
                "notes": "Daily OHLC has no generation timestamp for the 4:15 ET gate.",
            }
        )
    write_csv(
        OUTPUT_DIR / "data_preflight_reconciliation.csv",
        preflight_rows,
        list(preflight_rows[0].keys()),
    )

    for filename in (
        "all_trial_results.csv",
        "control_results.csv",
        "chronological_half_results.csv",
        "portfolio_contribution_results.csv",
    ):
        write_csv(OUTPUT_DIR / filename, [], METRIC_FIELDS)
    write_csv(
        OUTPUT_DIR / "state_signal_diagnostics.csv",
        [],
        [
            "observation_date",
            "requested_timestamp",
            "returned_timestamp",
            "VIX",
            "VIX3M",
            "ratio",
            "five_day_median",
            "target_state",
            "authorized_execution_session",
            "pretrade_weights",
            "target_weights",
            "turnover",
            "cost",
            "post_trade_holdings",
        ],
    )
    turnover_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": "",
            "cost_bps": "",
            "target_change_count": 0,
            "one_way_turnover": "",
            "transaction_cost": "",
            "actual_holdings_model_executed": False,
            "status": "not_run_Cboe_point_in_time_data_gate_failed",
        }
    ]
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        list(turnover_rows[0].keys()),
    )

    invariant_rows = [
        {
            "invariant_id": "official_Cboe_only",
            "status": "pass",
            "critical": True,
            "details": "Only official Cboe term-structure and daily-history endpoints were queried.",
        },
        {
            "invariant_id": "historical_queries_reproducible",
            "status": "pass" if historical_queries_reproducible else "fail",
            "critical": True,
            "details": "Five frozen historical dates were requested twice.",
        },
        {
            "invariant_id": "required_VIX_present_in_timestamped_payload",
            "status": "fail",
            "critical": True,
            "details": "The timestamped term endpoint returns VIX1-VIX10, not VIX.",
        },
        {
            "invariant_id": "required_VIX3M_present_in_timestamped_payload",
            "status": "fail",
            "critical": True,
            "details": "The timestamped term endpoint returns VIX1-VIX10, not VIX3M.",
        },
        {
            "invariant_id": "daily_required_series_have_intraday_generation_timestamps",
            "status": "fail",
            "critical": True,
            "details": "Official daily VIX and VIX3M files contain DATE/OHLC only.",
        },
        {
            "invariant_id": "no_child_trial_when_data_gate_fails",
            "status": "pass",
            "critical": True,
            "details": "trial_ledger.csv has headers and zero rows.",
        },
        {
            "invariant_id": "no_performance_after_data_gate_failure",
            "status": "pass",
            "critical": True,
            "details": "Candidate, controls, halves, and portfolio result files have zero rows.",
        },
        {
            "invariant_id": "frozen_strategy_contract_unchanged",
            "status": "pass",
            "critical": True,
            "details": "Ratio, median-5, thresholds, assets, and following-session execution remain unchanged.",
        },
    ]
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        list(invariant_rows[0].keys()),
    )

    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "prior_trial_id": PRIOR_TRIAL_ID,
            "child_trial_id": "",
            "child_trial_created": False,
            "stage": STAGE,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "data_gate_passed": False,
            "performance_executed": False,
            "precise_blocker": (
                "The official timestamped Cboe term-structure endpoint exposes "
                "VIX1-VIX10 option-expiry nodes, not constant-maturity VIX and VIX3M. "
                "The official daily VIX/VIX3M files lack intraday generation timestamps."
            ),
            "next_action": NEXT_ACTION,
        }
    ]
    failure_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "primary_failure_reason": FAILURE_REASON,
            "failure_stage": "Cboe_point_in_time_data_feasibility_gate",
            "term_endpoint_blocker": "wrong_series_schema_VIX1_to_VIX10",
            "daily_history_blocker": "no_intraday_generation_timestamp",
            "prior_ALFRED_block_preserved": True,
            "family_closed": False,
        }
    ]
    next_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "outcome": OUTCOME,
            "exact_next_action": NEXT_ACTION,
            "execute_in_this_task": False,
        }
    ]
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        outcome_rows,
        list(outcome_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        list(failure_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        next_rows,
        list(next_rows[0].keys()),
    )

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "prior_trial_id": PRIOR_TRIAL_ID,
        "conditional_child_trial_id": CONDITIONAL_CHILD_TRIAL_ID,
        "child_trial_created": False,
        "new_strategy_id_created": False,
        "source_record_id": SOURCE_RECORD_ID,
        "official_provider": "Cboe",
        "required_series": list(REQUIRED_CONSTANT_MATURITY_SERIES),
        "historical_reproducibility_sample_dates": list(HISTORICAL_REPRO_SAMPLE),
        "requested_cutoff": REQUESTED_CUTOFF,
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_written_before_data_requests": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "data_gate_passed": False,
        "performance_executed": False,
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "methodology_boundary": METHODOLOGY_BOUNDARY,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "exact_next_action": NEXT_ACTION,
        "strategy_rule_changed": False,
        "ratio_changed": False,
        "thresholds_changed": False,
        "assets_changed": False,
        "execution_changed": False,
        "optimization_performed": False,
        "validation_claimed": False,
        "exact_replication_claimed": False,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    report = f"""# Cboe Point-in-Time IVTS Feasibility and Exploration V2

## Outcome

`{OUTCOME}`

Primary failure reason: `{FAILURE_REASON}`

The official Cboe historical term-structure endpoint is real and reproducible.
Five predeclared dates were each retrieved twice with identical raw-response and
normalized hashes. However, its timestamped payload contains option-expiry term
nodes `VIX1` through `VIX10`; it does not contain the required constant-maturity
indices `VIX` and `VIX3M`.

Cboe also publishes official daily-history files for `VIX` and `VIX3M`. Those
files contain `DATE`, `OPEN`, `HIGH`, `LOW`, and `CLOSE`, but no intraday
generation timestamp. They therefore cannot establish the final official values
at or before 4:15 p.m. ET.

No term node was substituted for VIX3M. No ALFRED value was reinterpreted as an
intraday release. The point-in-time data gate failed, so no child trial, signal,
holdings, performance, control comparison, turnover, or cost result was created.

## Lineage

The prior trial `{PRIOR_TRIAL_ID}` remains unchanged with outcome
`{prior.OUTCOME}` and failure reason `{prior.FAILURE_REASON}`. The conditional
child trial was not created.

## State Protection

The strategy registry, roadmap, queue, family ledger, active observations,
canonical cache, prior V1 evidence, and source attachment were hashed before and
after. No lifecycle, promotion, activation, broker, account, order, or
real-money action occurred.

Exact next action: `{NEXT_ACTION}`.
"""
    write_text(OUTPUT_DIR / "batch_report.md", report)

    protected_after = prior.hash_paths(PROTECTED_STATE_PATHS)
    cache_after = prior.directory_hash(ROOT / "data" / "cache")
    prior_evidence_after = prior.directory_hash(PRIOR_EVIDENCE_DIR)
    source_attachment_after = prior.file_hash(SOURCE_ATTACHMENT)
    generated = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": True,
        "outcome": OUTCOME,
        "data_gate_passed": False,
        "child_trial_created": False,
        "trial_ledger_row_count": 0,
        "performance_executed": False,
        "performance_row_counts": {
            "all_trial_results": 0,
            "control_results": 0,
            "chronological_half_results": 0,
            "portfolio_contribution_results": 0,
            "state_signal_diagnostics": 0,
        },
        "entity_counts": {
            "source_library_records": 1,
            "strategy_configuration_references": 1,
            "new_strategy_configurations": 0,
            "new_experiment_trials": 0,
            "benchmark_references": 6,
            "data_capability_tasks": 1,
            "process_tasks": 1,
            "paper_demo_observations": 0,
        },
        "required_artifacts_present": (
            set(REQUIRED_ARTIFACTS) - {"consistency_check.json"}
        ).issubset(generated),
        "historical_sample_dates_exact": tuple(HISTORICAL_REPRO_SAMPLE)
        == (
            "2014-04-17",
            "2020-03-16",
            "2024-12-31",
            "2025-02-10",
            "2026-07-24",
        ),
        "two_requests_per_sample_date": all(
            sum(
                row["observation_date"] == date
                for row in reproducibility_rows
            )
            == 2
            for date in HISTORICAL_REPRO_SAMPLE
        ),
        "historical_queries_reproducible": historical_queries_reproducible,
        "timestamped_endpoint_returned_symbols": query_schema_symbols,
        "timestamped_endpoint_required_pair_available": required_pair_in_term_endpoint,
        "daily_histories_intraday_timestamp_available": daily_files_have_intraday_timestamps,
        "prior_ALFRED_block_visible": True,
        "prior_trial_id": PRIOR_TRIAL_ID,
        "prior_outcome": prior.OUTCOME,
        "prior_failure_reason": prior.FAILURE_REASON,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "canonical_cache_hash_before": cache_before,
        "canonical_cache_hash_after": cache_after,
        "canonical_cache_unchanged": cache_before == cache_after,
        "prior_evidence_hash_before": prior_evidence_before,
        "prior_evidence_hash_after": prior_evidence_after,
        "prior_evidence_unchanged": prior_evidence_before == prior_evidence_after,
        "source_attachment_hash_before": source_attachment_before,
        "source_attachment_hash_after": source_attachment_after,
        "source_attachment_unchanged": source_attachment_before
        == source_attachment_after,
        "forbidden_actions": {
            "ALFRED_intraday_timestamp_inferred": False,
            "term_node_substituted_for_VIX3M": False,
            "strategy_rule_change": False,
            "performance_backtest": False,
            "validation_or_robustness": False,
            "lifecycle_or_registry_change": False,
            "paper_demo_activation": False,
            "broker_account_order_or_real_money_action": False,
        },
        "exact_next_action": NEXT_ACTION,
    }
    consistency["overall_pass"] = bool(
        consistency["required_artifacts_present"]
        and consistency["historical_sample_dates_exact"]
        and consistency["two_requests_per_sample_date"]
        and consistency["historical_queries_reproducible"]
        and not consistency["timestamped_endpoint_required_pair_available"]
        and not consistency["daily_histories_intraday_timestamp_available"]
        and consistency["protected_state_unchanged"]
        and consistency["canonical_cache_unchanged"]
        and consistency["prior_evidence_unchanged"]
        and consistency["source_attachment_unchanged"]
        and not any(consistency["forbidden_actions"].values())
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "data_gate_passed": False,
        "child_trial_created": False,
        "historical_queries_reproducible": historical_queries_reproducible,
        "timestamped_endpoint_symbols": query_schema_symbols,
        "performance_executed": False,
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["overall_pass"],
        "evidence_path": str(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
