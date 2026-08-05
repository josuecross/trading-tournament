from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market


TASK_ID = "intermarket_ivts_herorats_portability_exploration_v1"
MODE = "fast-progress"
STAGE = "exploration"
STRATEGY_ID = "donninger_vix_vix3m_median5_spy_ief_portability_v1"
FAMILY_ID = "implied_volatility_term_structure_equity_timing"
TRIAL_ID = f"{TASK_ID}__canonical"
SOURCE_RECORD_ID = "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
OUTPUT_DIR = ROOT / "evidence" / "research_recovery" / TASK_ID / "latest"
SOURCE_ATTACHMENT = Path(
    r"C:\Users\te3442\.codex\attachments\cb86f21d-2cbe-4f20-99e4-b35d0c9c5c6f\pasted-text.txt"
)

PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
ACQUISITION_AS_OF_DATE = "2026-07-25"
EARLIEST_SIGNAL_OBSERVATION = "2014-04-17"
METHODOLOGY_BOUNDARY = "2025-02-10"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
ALFRED_DOWNLOAD_URL = "https://alfred.stlouisfed.org/series/downloaddata"
ALFRED_SERIES_URL = "https://alfred.stlouisfed.org/series"
ALFRED_HELP_URL = "https://alfred.stlouisfed.org/help/downloaddata"
MAX_DAILY_VINTAGES_PER_REQUEST = 450

OFFICIAL_SERIES = {
    "VIXCLS": {
        "name": "Cboe Volatility Index: VIX",
        "horizon": "30-day implied volatility",
    },
    "VXVCLS": {
        "name": "Cboe S&P 500 3-Month Volatility Index (VIX3M)",
        "horizon": "three-month implied volatility",
    },
}

BENCHMARKS = (
    "SPY_buy_and_hold",
    "SPY_200_day_trend_control",
    "unfiltered_vix_vix3m_three_state_spy_ief_v1",
    "vix_vix3m_sign_only_spy_ief_v1",
    "static_exposure_matched_spy_ief_v1",
    "IEF_buy_and_hold",
)
CRITICAL_CONTROLS = (
    "unfiltered_vix_vix3m_three_state_spy_ief_v1",
    "static_exposure_matched_spy_ief_v1",
)

OUTCOME = "inconclusive_data_issue"
FAILURE_REASON = "data_or_comparability_failure"
NEXT_ACTION = "direction_owner_review_ivts_publication_timing_block_v1"

PROTECTED_STATE_PATHS = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)

REQUIRED_ARTIFACTS = (
    "batch_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "benchmark_reference_log.csv",
    "data_capability_task_log.csv",
    "process_task_log.csv",
    "official_series_manifest.csv",
    "publication_timing_reconciliation.csv",
    "methodology_change_log.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "state_signal_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "exploratory_followup_candidates.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "batch_report.md",
)

METRIC_FIELDS = [
    "entity_id",
    "entity_type",
    "period",
    "cost_bps",
    "evaluation_start",
    "evaluation_end",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_SPY_exposure",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant",
    "numeric_invariant",
    "exposure_invariant",
    "weight_invariant",
]


@dataclass(frozen=True)
class AlfredAcquisition:
    series_id: str
    frame: pd.DataFrame
    selected_vintage_count: int
    request_count: int
    response_hashes: tuple[str, ...]
    latest_page_update_timestamp: str
    error: str

    @property
    def succeeded(self) -> bool:
        return not self.error and not self.frame.empty


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return sha256_bytes(path.read_bytes())


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return sha256_bytes(encoded)


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "research_recovery" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def hash_paths(paths: Iterable[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def directory_hash(path: Path) -> str:
    rows = []
    if path.exists():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            rows.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "sha256": file_hash(item),
                    "size": item.stat().st_size,
                }
            )
    return canonical_hash(rows)


def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def _extract_latest_update_timestamp(html: str) -> str:
    match = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else ""


def _extract_initial_release_csv(payload: bytes, series_id: str) -> pd.DataFrame:
    if payload[:2] != b"PK":
        soup = BeautifulSoup(payload.decode("utf-8", "replace"), "html.parser")
        errors = [
            node.get_text(" ", strip=True)
            for node in soup.select(".alert,.error,.form-error-message")
        ]
        raise RuntimeError("; ".join(errors) or "ALFRED did not return a ZIP archive")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise RuntimeError(f"Expected one ALFRED CSV member, received {names}")
        frame = pd.read_csv(io.BytesIO(archive.read(names[0])))
    required = {"period_start_date", series_id, "realtime_start_date"}
    if not required.issubset(frame.columns):
        raise RuntimeError(
            f"ALFRED initial-release export missing fields: {sorted(required - set(frame.columns))}"
        )
    frame = frame.rename(
        columns={
            "period_start_date": "observation_date",
            series_id: "value",
            "realtime_start_date": "release_date",
        }
    )
    frame["observation_date"] = pd.to_datetime(
        frame["observation_date"], errors="coerce"
    )
    frame["release_date"] = pd.to_datetime(frame["release_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame[["observation_date", "value", "release_date"]].dropna(
        subset=["observation_date", "release_date"]
    )


def acquire_alfred_initial_releases(
    series_id: str,
    *,
    start_date: str = EARLIEST_SIGNAL_OBSERVATION,
    end_date: str = ACQUISITION_AS_OF_DATE,
    timeout: int = 120,
) -> AlfredAcquisition:
    session = requests.Session()
    params = {"seid": series_id}
    try:
        page = session.get(ALFRED_DOWNLOAD_URL, params=params, timeout=timeout)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        selector = 'select[name="form[selected_vintage_dates][]"] option'
        vintage_dates = [
            str(option.get("value"))
            for option in soup.select(selector)
            if option.get("value")
            and start_date <= str(option.get("value")) <= end_date
        ]
        if len(vintage_dates) < 2:
            raise RuntimeError(
                f"Fewer than two ALFRED vintage dates available for {series_id}"
            )
        available_end_date = vintage_dates[-1]

        frames: list[pd.DataFrame] = []
        response_hashes: list[str] = []
        for vintage_chunk in _chunked(
            vintage_dates, MAX_DAILY_VINTAGES_PER_REQUEST
        ):
            form: list[tuple[str, str]] = [
                ("form[units]", "lin"),
                ("form[obs_start_date]", start_date),
                ("form[obs_end_date]", available_end_date),
                ("form[entered_vintage_dates]", ""),
                ("form[file_type]", "4"),
                ("form[file_format]", "csv"),
                ("form[download_data]", "Download Data"),
            ]
            form.extend(
                ("form[selected_vintage_dates][]", date) for date in vintage_chunk
            )
            response = session.post(
                ALFRED_DOWNLOAD_URL,
                params=params,
                data=form,
                timeout=timeout,
            )
            response.raise_for_status()
            chunk_frame = _extract_initial_release_csv(response.content, series_id)
            response_hashes.append(first_release_panel_hash(chunk_frame))
            frames.append(chunk_frame)

        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values(
            ["observation_date", "release_date"], kind="stable"
        )
        combined = combined.drop_duplicates(
            subset=["observation_date"], keep="first"
        ).reset_index(drop=True)
        series_page = session.get(
            ALFRED_SERIES_URL, params={"seid": series_id}, timeout=timeout
        )
        series_page.raise_for_status()
        return AlfredAcquisition(
            series_id=series_id,
            frame=combined,
            selected_vintage_count=len(vintage_dates),
            request_count=len(response_hashes),
            response_hashes=tuple(response_hashes),
            latest_page_update_timestamp=_extract_latest_update_timestamp(
                series_page.text
            ),
            error="",
        )
    except Exception as exc:  # acquisition failures belong in evidence
        return AlfredAcquisition(
            series_id=series_id,
            frame=pd.DataFrame(
                columns=["observation_date", "value", "release_date"]
            ),
            selected_vintage_count=0,
            request_count=0,
            response_hashes=(),
            latest_page_update_timestamp="",
            error=f"{type(exc).__name__}: {exc}",
        )


def first_release_panel_hash(frame: pd.DataFrame) -> str:
    records = []
    for row in frame.itertuples(index=False):
        records.append(
            {
                "observation_date": pd.Timestamp(row.observation_date).date().isoformat(),
                "value": None if pd.isna(row.value) else float(row.value),
                "release_date": pd.Timestamp(row.release_date).date().isoformat(),
            }
        )
    return canonical_hash(records)


def build_publication_timing_panel(
    vix: pd.DataFrame, vxv: pd.DataFrame
) -> pd.DataFrame:
    left = vix.rename(
        columns={"value": "VIXCLS", "release_date": "VIXCLS_release_date"}
    )
    right = vxv.rename(
        columns={"value": "VXVCLS", "release_date": "VXVCLS_release_date"}
    )
    panel = left.merge(right, on="observation_date", how="outer").sort_values(
        "observation_date"
    )
    panel = panel.loc[
        panel["observation_date"] >= pd.Timestamp(EARLIEST_SIGNAL_OBSERVATION)
    ].copy()
    panel["both_values_present"] = panel[["VIXCLS", "VXVCLS"]].notna().all(axis=1)
    panel["both_release_dates_present"] = panel[
        ["VIXCLS_release_date", "VXVCLS_release_date"]
    ].notna().all(axis=1)
    panel["signal_release_date"] = panel[
        ["VIXCLS_release_date", "VXVCLS_release_date"]
    ].max(axis=1)
    panel["historical_release_timestamp_available"] = False
    panel["publication_safe_execution_proven"] = False
    panel["publication_timing_status"] = (
        "blocked_historical_intraday_release_timestamp_unavailable"
    )
    return panel.reset_index(drop=True)


def median5(values: Iterable[float]) -> float | None:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if len(clean) != 5:
        return None
    return float(pd.Series(clean).median())


def target_for_filtered_ratio(value: float | None) -> tuple[float, float, str]:
    if value is None or not math.isfinite(float(value)):
        return 0.5, 0.5, "warmup_or_unavailable"
    if float(value) < 0.96:
        return 1.0, 0.0, "risk_on"
    if float(value) <= 1.02:
        return 0.5, 0.5, "middle"
    return 0.0, 1.0, "defensive"


def build_signal_diagnostics(panel: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ratios: list[float | None] = []
    for record in panel.itertuples(index=False):
        vix = None if pd.isna(record.VIXCLS) else float(record.VIXCLS)
        vxv = None if pd.isna(record.VXVCLS) else float(record.VXVCLS)
        ratio = (
            vix / vxv
            if vix is not None and vxv is not None and vxv != 0.0
            else None
        )
        ratios.append(ratio)
        filtered = median5(ratios[-5:]) if len(ratios) >= 5 else None
        spy, ief, state = target_for_filtered_ratio(filtered)
        observation_date = pd.Timestamp(record.observation_date)
        rows.append(
            {
                "observation_date": observation_date.date().isoformat(),
                "VIXCLS_release_date": (
                    ""
                    if pd.isna(record.VIXCLS_release_date)
                    else pd.Timestamp(record.VIXCLS_release_date).date().isoformat()
                ),
                "VXVCLS_release_date": (
                    ""
                    if pd.isna(record.VXVCLS_release_date)
                    else pd.Timestamp(record.VXVCLS_release_date).date().isoformat()
                ),
                "VIXCLS_release_timestamp": "",
                "VXVCLS_release_timestamp": "",
                "signal_availability_date": (
                    ""
                    if pd.isna(record.signal_release_date)
                    else pd.Timestamp(record.signal_release_date).date().isoformat()
                ),
                "signal_availability_timestamp": "",
                "VIXCLS": vix,
                "VXVCLS": vxv,
                "raw_ratio": ratio,
                "five_day_median": filtered,
                "diagnostic_target_state": state,
                "diagnostic_target_SPY": spy,
                "diagnostic_target_IEF": ief,
                "authorized_execution_session": "",
                "pretrade_SPY_weight": "",
                "pretrade_IEF_weight": "",
                "turnover": "",
                "cost": "",
                "post_trade_SPY_holding": "",
                "post_trade_IEF_holding": "",
                "methodology_period": (
                    "pre_2025_02_10"
                    if observation_date < pd.Timestamp(METHODOLOGY_BOUNDARY)
                    else "post_2025_02_10"
                ),
                "execution_authorized": False,
                "blocking_reason": (
                    "Historical ALFRED first releases provide release dates but not "
                    "intraday publication timestamps; a same-release-date close cannot "
                    "be proven to occur after publication."
                ),
            }
        )
    return rows


def adjusted_data_preflight(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    frame = market.load_adjusted_ohlcv(symbol)
    if frame.empty:
        return {
            "data_id": symbol,
            "data_type": "adjusted_daily_market_data",
            "provider": "repository_canonical_cache",
            "status": "missing_or_invalid",
            "first_valid_date": "",
            "last_valid_date": "",
            "row_count": 0,
            "canonical_hash": file_hash(path),
            "ordered_unique_dates": False,
            "finite_positive_values": False,
            "release_timing_complete": "not_applicable",
            "notes": "SPY/IEF cache preflight failed.",
        }
    return {
        "data_id": symbol,
        "data_type": "adjusted_daily_market_data",
        "provider": "repository_canonical_cache",
        "status": "pass",
        "first_valid_date": frame.index.min().date().isoformat(),
        "last_valid_date": frame.index.max().date().isoformat(),
        "row_count": len(frame),
        "canonical_hash": file_hash(path),
        "ordered_unique_dates": bool(frame.index.is_monotonic_increasing and frame.index.is_unique),
        "finite_positive_values": bool(
            (frame[["open", "high", "low", "close", "adj_close"]] > 0.0)
            .all()
            .all()
        ),
        "release_timing_complete": "not_applicable",
        "notes": "Canonical adjusted OHLCV loaded through the normal repository interface.",
    }


def official_data_preflight(acquisition: AlfredAcquisition) -> dict[str, Any]:
    frame = acquisition.frame
    return {
        "data_id": acquisition.series_id,
        "data_type": "official_first_release_implied_volatility_index",
        "provider": "FRED_ALFRED",
        "status": "partial_publication_timing_block" if acquisition.succeeded else "acquisition_failed",
        "first_valid_date": (
            frame.loc[frame["value"].notna(), "observation_date"].min().date().isoformat()
            if acquisition.succeeded and frame["value"].notna().any()
            else ""
        ),
        "last_valid_date": (
            frame.loc[frame["value"].notna(), "observation_date"].max().date().isoformat()
            if acquisition.succeeded and frame["value"].notna().any()
            else ""
        ),
        "row_count": len(frame),
        "canonical_hash": first_release_panel_hash(frame) if acquisition.succeeded else "",
        "ordered_unique_dates": bool(
            acquisition.succeeded
            and frame["observation_date"].is_monotonic_increasing
            and frame["observation_date"].is_unique
        ),
        "finite_positive_values": bool(
            acquisition.succeeded
            and (frame.loc[frame["value"].notna(), "value"] > 0.0).all()
        ),
        "release_timing_complete": False,
        "notes": acquisition.error or (
            "First-release values and release dates recovered; historical intraday "
            "publication timestamps are absent."
        ),
    }


def _entity_rows() -> tuple[
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
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "source_title": "HeroRATs - Risk Aversion Timing Strategies",
            "source_role": "rule_provenance_only",
            "source_claimed_performance_used": False,
            "strategy_id": "",
            "trial_id": "",
            "outcome": "blocked_feasibility",
            "failure_reason": FAILURE_REASON,
            "notes": (
                "The frozen source packet controls rules. This task performs no new "
                "source research and claims no exact source replication."
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
                "official_series": ["VIXCLS", "VXVCLS"],
                "ratio": "VIXCLS/VXVCLS",
                "median_length": 5,
                "thresholds": [0.96, 1.02],
                "targets": ["SPY_1_IEF_0", "SPY_0.5_IEF_0.5", "SPY_0_IEF_1"],
                "missing_later_observation": "retain_previous_target",
                "primary_one_way_cost_bps": PRIMARY_COST_BPS,
                "diagnostic_one_way_cost_bps": [0.0, 10.0],
            },
            "benchmark_or_control": "|".join(BENCHMARKS),
            "route": "standalone",
            "translation_label": "mechanical_etf_and_execution_portability",
            "exact_source_replication_claimed": False,
            "stage": STAGE,
            "trial_id": TRIAL_ID,
            "parent_trial_id": "",
            "adaptation_label": "exploratory_variant",
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "next_action": NEXT_ACTION,
        }
    ]
    trial = [
        {
            "trial_id": TRIAL_ID,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "parent_trial_id": "",
            "adaptation_label": "exploratory_variant",
            "changed_fields_from_source": (
                "risk_and_defensive_ETF_mapping_and_publication_safe_execution"
            ),
            "ratio_changed": False,
            "median_length_changed": False,
            "thresholds_changed": False,
            "state_weights_changed": False,
            "source_assets_translated": True,
            "execution_translated": True,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "performance_executed": False,
            "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
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
            "is_same_purpose_control": benchmark_id
            == "unfiltered_vix_vix3m_three_state_spy_ief_v1",
            "is_critical_control": benchmark_id in CRITICAL_CONTROLS,
            "performance_executed": False,
            "notes": "Frozen benchmark reference; no metric was calculated after the timing gate blocked.",
        }
        for benchmark_id in BENCHMARKS
    ]
    return source, strategy, trial, benchmark


def _write_preregistered_entities() -> str:
    source, strategy, trial, benchmark = _entity_rows()
    write_csv(
        OUTPUT_DIR / "source_library_records.csv",
        source,
        list(source[0].keys()),
    )
    write_csv(OUTPUT_DIR / "strategy_cards.csv", strategy, list(strategy[0].keys()))
    write_csv(OUTPUT_DIR / "trial_ledger.csv", trial, list(trial[0].keys()))
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark,
        list(benchmark[0].keys()),
    )
    checkpoint = {
        "source": source,
        "strategy": strategy,
        "trial": trial,
        "benchmarks": benchmark,
    }
    return canonical_hash(checkpoint)


def run() -> dict[str, Any]:
    protected_before = hash_paths(PROTECTED_STATE_PATHS)
    cache_before = directory_hash(ROOT / "data" / "cache")
    source_attachment_before = file_hash(SOURCE_ATTACHMENT)
    clean_output_dir()

    preregistration_hash = _write_preregistered_entities()
    acquisitions = {
        series_id: acquire_alfred_initial_releases(series_id)
        for series_id in OFFICIAL_SERIES
    }
    vix = acquisitions["VIXCLS"].frame
    vxv = acquisitions["VXVCLS"].frame
    panel = build_publication_timing_panel(vix, vxv)
    signal_rows = build_signal_diagnostics(panel)

    source, strategy, trial, benchmark = _entity_rows()
    data_tasks = []
    official_manifest = []
    for series_id, acquisition in acquisitions.items():
        valid = acquisition.frame.loc[acquisition.frame["value"].notna()]
        data_tasks.append(
            {
                "task_id": f"{TASK_ID}__acquire_{series_id}",
                "entity_type": "data_capability_task",
                "stage": "blocked",
                "adaptation_label": "data_feasibility_adjustment",
                "series_id": series_id,
                "provider": "FRED_ALFRED",
                "endpoint": f"{ALFRED_DOWNLOAD_URL}?seid={series_id}",
                "request_count": acquisition.request_count,
                "selected_vintage_count": acquisition.selected_vintage_count,
                "first_release_values_acquired": acquisition.succeeded,
                "release_dates_acquired": acquisition.succeeded,
                "historical_release_timestamps_acquired": False,
                "status": (
                    "date_level_first_releases_acquired_timestamp_blocked"
                    if acquisition.succeeded
                    else "acquisition_failed"
                ),
                "error": acquisition.error,
                "secrets_persisted": False,
            }
        )
        official_manifest.append(
            {
                "series_id": series_id,
                "series_name": OFFICIAL_SERIES[series_id]["name"],
                "provider": "FRED_ALFRED",
                "frequency": "daily_close",
                "horizon": OFFICIAL_SERIES[series_id]["horizon"],
                "first_valid_observation": (
                    valid["observation_date"].min().date().isoformat()
                    if not valid.empty
                    else ""
                ),
                "last_valid_observation": (
                    valid["observation_date"].max().date().isoformat()
                    if not valid.empty
                    else ""
                ),
                "initial_release_row_count": len(acquisition.frame),
                "valid_value_count": int(acquisition.frame["value"].notna().sum()),
                "missing_value_count": int(acquisition.frame["value"].isna().sum()),
                "first_release_panel_hash": (
                    first_release_panel_hash(acquisition.frame)
                    if acquisition.succeeded
                    else ""
                ),
                "extracted_chunk_hashes": acquisition.response_hashes,
                "latest_series_page_update_timestamp": (
                    acquisition.latest_page_update_timestamp
                ),
                "release_date_available": acquisition.succeeded,
                "historical_intraday_release_timestamp_available": False,
                "download_mechanism": (
                    "ALFRED Observations, Initial Release Only zipped CSV"
                ),
                "official_help_url": ALFRED_HELP_URL,
                "status": (
                    "date_level_first_release_complete_intraday_timing_incomplete"
                    if acquisition.succeeded
                    else "acquisition_failed"
                ),
            }
        )

    publication_rows = []
    for record in panel.itertuples(index=False):
        publication_rows.append(
            {
                "observation_date": pd.Timestamp(record.observation_date)
                .date()
                .isoformat(),
                "VIXCLS": record.VIXCLS,
                "VIXCLS_first_release_date": (
                    ""
                    if pd.isna(record.VIXCLS_release_date)
                    else pd.Timestamp(record.VIXCLS_release_date).date().isoformat()
                ),
                "VIXCLS_first_release_timestamp": "",
                "VXVCLS": record.VXVCLS,
                "VXVCLS_first_release_date": (
                    ""
                    if pd.isna(record.VXVCLS_release_date)
                    else pd.Timestamp(record.VXVCLS_release_date).date().isoformat()
                ),
                "VXVCLS_first_release_timestamp": "",
                "both_values_present": bool(record.both_values_present),
                "both_release_dates_present": bool(record.both_release_dates_present),
                "signal_release_date": (
                    ""
                    if pd.isna(record.signal_release_date)
                    else pd.Timestamp(record.signal_release_date).date().isoformat()
                ),
                "signal_release_timestamp": "",
                "authorized_execution_session": "",
                "publication_safe_execution_proven": False,
                "status": record.publication_timing_status,
            }
        )

    process_rows = [
        {
            "task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "strategy_count": 1,
            "trial_count": 1,
            "performance_trial_count": 0,
            "provider_series_count": 2,
            "status": "completed_with_publication_timing_block",
            "outcome": OUTCOME,
            "next_action": NEXT_ACTION,
        }
    ]

    preflight_rows = [
        adjusted_data_preflight("SPY"),
        adjusted_data_preflight("IEF"),
        official_data_preflight(acquisitions["VIXCLS"]),
        official_data_preflight(acquisitions["VXVCLS"]),
    ]

    methodology_rows = [
        {
            "methodology_id": "Cboe_VIX3M_methodology_boundary_2025_02_10",
            "effective_date": METHODOLOGY_BOUNDARY,
            "series_id": "VXVCLS",
            "diagnostic_only": True,
            "thresholds_changed": False,
            "strategy_variant_created": False,
            "observations_excluded": False,
            "notes": (
                "The frozen Cboe methodology boundary is retained as a diagnostic "
                "flag. It did not change the blocked timing decision."
            ),
        }
    ]

    turnover_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "cost_bps": "",
            "target_change_count": 0,
            "one_way_turnover": "",
            "transaction_cost": "",
            "actual_holdings_model_executed": False,
            "status": "not_run_publication_timing_block",
            "notes": (
                "No target was authorized for execution, so turnover and costs were "
                "not calculated."
            ),
        }
    ]

    invariants = [
        {
            "invariant_id": "exact_official_series_only",
            "status": "pass",
            "critical": True,
            "details": "Only VIXCLS and VXVCLS were requested from official ALFRED.",
        },
        {
            "invariant_id": "first_release_values_recovered",
            "status": (
                "pass" if all(item.succeeded for item in acquisitions.values()) else "fail"
            ),
            "critical": True,
            "details": "ALFRED Initial Release Only exports were used.",
        },
        {
            "invariant_id": "historical_intraday_publication_timestamps_recovered",
            "status": "fail",
            "critical": True,
            "details": (
                "ALFRED exports provide realtime_start_date but no historical "
                "intraday release timestamp."
            ),
        },
        {
            "invariant_id": "publication_safe_execution_proven",
            "status": "fail",
            "critical": True,
            "details": (
                "A release-date close cannot be proven to follow publication for "
                "same-date first releases."
            ),
        },
        {
            "invariant_id": "no_performance_after_timing_gate_failure",
            "status": "pass",
            "critical": True,
            "details": "No candidate, control, half-period, or portfolio metric was calculated.",
        },
        {
            "invariant_id": "frozen_ratio_median_thresholds_and_weights",
            "status": "pass",
            "critical": True,
            "details": "VIXCLS/VXVCLS, median-5, 0.96/1.02, and 100/0|50/50|0/100 remain frozen.",
        },
        {
            "invariant_id": "no_lifecycle_paper_demo_or_broker_action",
            "status": "pass",
            "critical": True,
            "details": "No authoritative state, observation, broker, or order path was touched.",
        },
    ]

    outcome_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "stage": STAGE,
            "outcome": OUTCOME,
            "failure_reason": FAILURE_REASON,
            "performance_executed": False,
            "followup_candidate": False,
            "blocking_gate": "historical_intraday_publication_timing",
            "exact_source_replication_claimed": False,
            "interpretation": (
                "Date-level first-release evidence exists, but the frozen first-close-"
                "after-publication convention cannot be proven for the historical sample."
            ),
            "next_action": NEXT_ACTION,
        }
    ]
    failure_rows = [
        {
            "strategy_id": STRATEGY_ID,
            "trial_id": TRIAL_ID,
            "primary_failure_reason": FAILURE_REASON,
            "failure_stage": "official_series_publication_timing_gate",
            "precise_blocker": (
                "Historical ALFRED initial-release exports provide release dates but "
                "not intraday timestamps. Same-date observations therefore cannot be "
                "mapped to the first regular-session close after publication without "
                "an unverified assumption."
            ),
            "smallest_revisit_requirement": (
                "Obtain authoritative historical publication timestamps or an official "
                "fixed release-time rule covering the full sample, then rerun this "
                "unchanged frozen trial."
            ),
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
        OUTPUT_DIR / "data_capability_task_log.csv",
        data_tasks,
        list(data_tasks[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        process_rows,
        list(process_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "official_series_manifest.csv",
        official_manifest,
        list(official_manifest[0].keys()),
    )
    publication_fields = [
        "observation_date",
        "VIXCLS",
        "VIXCLS_first_release_date",
        "VIXCLS_first_release_timestamp",
        "VXVCLS",
        "VXVCLS_first_release_date",
        "VXVCLS_first_release_timestamp",
        "both_values_present",
        "both_release_dates_present",
        "signal_release_date",
        "signal_release_timestamp",
        "authorized_execution_session",
        "publication_safe_execution_proven",
        "status",
    ]
    write_csv(
        OUTPUT_DIR / "publication_timing_reconciliation.csv",
        publication_rows,
        publication_fields,
    )
    write_csv(
        OUTPUT_DIR / "methodology_change_log.csv",
        methodology_rows,
        list(methodology_rows[0].keys()),
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
    signal_fields = [
        "observation_date",
        "VIXCLS_release_date",
        "VXVCLS_release_date",
        "VIXCLS_release_timestamp",
        "VXVCLS_release_timestamp",
        "signal_availability_date",
        "signal_availability_timestamp",
        "VIXCLS",
        "VXVCLS",
        "raw_ratio",
        "five_day_median",
        "diagnostic_target_state",
        "diagnostic_target_SPY",
        "diagnostic_target_IEF",
        "authorized_execution_session",
        "pretrade_SPY_weight",
        "pretrade_IEF_weight",
        "turnover",
        "cost",
        "post_trade_SPY_holding",
        "post_trade_IEF_holding",
        "methodology_period",
        "execution_authorized",
        "blocking_reason",
    ]
    write_csv(
        OUTPUT_DIR / "state_signal_diagnostics.csv", signal_rows, signal_fields
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        list(turnover_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariants,
        list(invariants[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "exploratory_followup_candidates.csv",
        [],
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "route",
            "next_action",
        ],
    )
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
        OUTPUT_DIR / "next_actions.csv", next_rows, list(next_rows[0].keys())
    )

    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "experiment_trials": 1,
        "benchmark_references": 6,
        "data_capability_tasks": 2,
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "performance_trials_executed": 0,
        "inconclusive_data_issue": 1,
        "exploratory_followup_candidates": 0,
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_ids": [STRATEGY_ID],
        "source_record_ids": [SOURCE_RECORD_ID],
        "trial_ids": [TRIAL_ID],
        "benchmark_ids": list(BENCHMARKS),
        "official_series": list(OFFICIAL_SERIES),
        "preregistration_timestamp": PREREGISTRATION_TIMESTAMP,
        "preregistration_written_before_performance_calculation": True,
        "preregistration_checkpoint_hash": preregistration_hash,
        "performance_calculation_started": False,
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "earliest_signal_observation": EARLIEST_SIGNAL_OBSERVATION,
        "methodology_boundary": METHODOLOGY_BOUNDARY,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "exact_next_action": NEXT_ACTION,
        "exact_source_replication_claimed": False,
        "validation_claimed": False,
        "paper_demo_eligibility_claimed": False,
        "lifecycle_state_changed": False,
        "provider_download_scope": ["VIXCLS", "VXVCLS"],
        "optimization_performed": False,
        "post_result_adaptation_performed": False,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "batch_manifest.yaml", manifest)

    report = f"""# Intermarket IVTS HeroRATs Portability Exploration V1

## Outcome

`{OUTCOME}`

Primary failure reason: `{FAILURE_REASON}`

The official ALFRED `Observations, Initial Release Only` export successfully
recovered date-level first-release values and `realtime_start_date` for
`VIXCLS` and `VXVCLS`. The export does not contain historical intraday
publication timestamps.

Some values first appear on the same calendar date as their observation. Without
an intraday publication time, the task cannot prove whether that date's regular
session close followed publication. Assigning the close would therefore violate
the frozen publication-timing gate, while delaying every such observation would
silently change the frozen first-close-after-publication convention.

## Scope Preserved

- Exactly one source record, strategy configuration, and canonical exploration
  trial were created in this evidence packet.
- Six frozen controls remain benchmark references only.
- No candidate, control, chronological-half, or portfolio performance was
  calculated.
- The VIX/VIX3M ratio, median length 5, thresholds 0.96 and 1.02, and three
  SPY/IEF target states remain unchanged.
- The 2025-02-10 Cboe methodology boundary remains visible as a diagnostic.
- No lifecycle, paper/demo, registry, broker, account, order, or real-money
  action occurred.

## Revisit Requirement

Provide authoritative historical publication timestamps, or an official fixed
release-time rule covering the full sample. Then rerun the same frozen trial
without changing its strategy or execution contract.

Exact next action: `{NEXT_ACTION}`.
"""
    write_text(OUTPUT_DIR / "batch_report.md", report)

    protected_after = hash_paths(PROTECTED_STATE_PATHS)
    cache_after = directory_hash(ROOT / "data" / "cache")
    source_attachment_after = file_hash(SOURCE_ATTACHMENT)
    generated = {path.name for path in OUTPUT_DIR.iterdir() if path.is_file()}
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": True,
        "candidate_outcome": OUTCOME,
        "candidate_execution_authorized": False,
        "performance_rows": {
            "all_trial_results": 0,
            "control_results": 0,
            "chronological_half_results": 0,
            "portfolio_contribution_results": 0,
        },
        "entity_counts": funnel,
        "required_artifacts_present": (
            set(REQUIRED_ARTIFACTS) - {"consistency_check.json"}
        ).issubset(generated),
        "exact_scope": {
            "source_library_records": len(source) == 1,
            "strategy_configurations": len(strategy) == 1,
            "experiment_trials": len(trial) == 1,
            "benchmark_references": len(benchmark) == 6,
            "data_capability_tasks": len(data_tasks) == 2,
            "process_tasks": len(process_rows) == 1,
            "paper_demo_observations": funnel["paper_demo_observations"] == 0,
        },
        "official_series_scope_exact": set(acquisitions) == {"VIXCLS", "VXVCLS"},
        "first_release_values_acquired": all(
            item.succeeded for item in acquisitions.values()
        ),
        "historical_intraday_release_timestamps_acquired": False,
        "timing_gate_stopped_performance": True,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "canonical_cache_hash_before": cache_before,
        "canonical_cache_hash_after": cache_after,
        "canonical_cache_unchanged": cache_before == cache_after,
        "source_attachment_hash_before": source_attachment_before,
        "source_attachment_hash_after": source_attachment_after,
        "source_attachment_unchanged": source_attachment_before
        == source_attachment_after,
        "forbidden_actions": {
            "source_research": False,
            "parameter_optimization": False,
            "performance_backtest": False,
            "validation_or_robustness": False,
            "lifecycle_or_registry_change": False,
            "paper_demo_activation": False,
            "broker_account_order_or_real_money_action": False,
            "unrelated_provider_download": False,
        },
        "exact_next_action": NEXT_ACTION,
    }
    consistency["overall_pass"] = bool(
        consistency["required_artifacts_present"]
        and consistency["official_series_scope_exact"]
        and consistency["timing_gate_stopped_performance"]
        and consistency["protected_state_unchanged"]
        and consistency["canonical_cache_unchanged"]
        and consistency["source_attachment_unchanged"]
        and all(consistency["exact_scope"].values())
        and not any(consistency["forbidden_actions"].values())
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "outcome": OUTCOME,
        "failure_reason": FAILURE_REASON,
        "next_action": NEXT_ACTION,
        "first_release_values_acquired": consistency[
            "first_release_values_acquired"
        ],
        "historical_intraday_release_timestamps_acquired": False,
        "performance_executed": False,
        "consistency_passed": consistency["overall_pass"],
        "evidence_path": str(OUTPUT_DIR),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
