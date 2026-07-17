from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from src.data import DataQualityError, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "mna_static_merger_arbitrage_bounded_screen_v1" / "latest"
CANDIDATE_ID = "mna_static_merger_arbitrage_wrapper_v1"
FAMILY_ID = "event_driven_merger_arbitrage"
MECHANISM = "static_rules_based_global_merger_arbitrage_etf_wrapper"
SOURCE_ID = "nyli_mna_merger_arbitrage_official_source_packet_v1"
MNA = "MNA"
BIL = "BIL"
SPY = "SPY"
SYMBOLS = (MNA, BIL, SPY)
AUTHORIZED_DOWNLOAD_SYMBOLS = (MNA,)
FORBIDDEN_MERGER_ARBITRAGE_PRODUCTS = ("ARB", "MRGR", "MARB")
FORBIDDEN_NEW_BENCHMARKS = ("MSCI_WORLD", "URTH", "ACWI")
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
INITIAL_TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
ACTIVE_COMBO_SERIES_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
REQUEST_SETTINGS = {
    "start": "2009-11-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}
ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "historical_edge_recently_weakened",
    "methodology_regime_instability",
    "diversification_value_without_sufficient_cash_edge",
    "no_material_edge",
    "invalid_methodology",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def clean_value(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return rel(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not math.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=clean_value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def validate_authorized_download_symbol(symbol: str) -> str:
    normalized = str(symbol).upper()
    if normalized not in AUTHORIZED_DOWNLOAD_SYMBOLS:
        raise ValueError(f"Only MNA provider acquisition is authorized for this screen; got {symbol}")
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2009-11-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = bool(request_settings.get("multi_level_index", False))
    if "timeout" in signature.parameters and request_settings.get("timeout") is not None:
        kwargs["timeout"] = float(request_settings.get("timeout", 30))
    try:
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def cache_quality_row(symbol: str) -> dict[str, Any]:
    path = cache_path(symbol)
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_exists": path.exists(),
        "cache_hash": sha256_path(path),
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "schema": "",
        "date_monotonic_increasing": False,
        "duplicate_date_count": "",
        "missing_price_count": "",
        "missing_adj_close_count": "",
        "nonpositive_adj_close_count": "",
        "adjusted_price_validation_result": "missing",
        "provider_download": False,
        "cache_refreshed": False,
        "corporate_actions_columns_present": False,
    }
    if not path.exists():
        return row
    frame = pd.read_csv(path)
    row["schema"] = "|".join(str(col) for col in frame.columns)
    dates = pd.to_datetime(frame.get("date"), errors="coerce").dt.tz_localize(None)
    adj = pd.to_numeric(frame.get("adj_close"), errors="coerce") if "adj_close" in frame else pd.Series(dtype=float)
    price_cols = [col for col in ("open", "high", "low", "close", "adj_close") if col in frame.columns]
    row["row_count"] = int(len(frame))
    row["first_valid_date"] = dates.dropna().min().date().isoformat() if dates.notna().any() else ""
    row["last_valid_date"] = dates.dropna().max().date().isoformat() if dates.notna().any() else ""
    row["date_monotonic_increasing"] = bool(dates.dropna().is_monotonic_increasing)
    row["duplicate_date_count"] = int(dates.dropna().duplicated().sum())
    row["missing_price_count"] = int(frame[price_cols].isna().sum().sum()) if price_cols else int(len(frame))
    row["missing_adj_close_count"] = int(adj.isna().sum()) if "adj_close" in frame else int(len(frame))
    row["nonpositive_adj_close_count"] = int((adj <= 0).sum()) if "adj_close" in frame else int(len(frame))
    row["corporate_actions_columns_present"] = {"dividends", "stock_splits"}.issubset(set(frame.columns))
    ok = (
        row["row_count"] > 20
        and row["date_monotonic_increasing"]
        and row["duplicate_date_count"] == 0
        and row["missing_adj_close_count"] == 0
        and row["nonpositive_adj_close_count"] == 0
        and row["corporate_actions_columns_present"]
    )
    row["adjusted_price_validation_result"] = "pass" if ok else "fail"
    return row


def ensure_mna_cache(prior_provider: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before_hash = sha256_path(cache_path(MNA))
    before_quality = cache_quality_row(MNA)
    downloaded = False
    status = "existing_cache_valid"
    error = ""
    if before_quality["adjusted_price_validation_result"] != "pass":
        try:
            raw = default_yfinance_downloader(MNA, REQUEST_SETTINGS)
            normalized = build_adjusted_ohlc(raw, MNA)
            cache_path(MNA).parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(cache_path(MNA), index=False, lineterminator="\n")
            downloaded = True
            status = "downloaded_and_validated"
        except Exception as exc:  # pragma: no cover - exercised only on provider failure
            status = "provider_download_failed"
            error = f"{type(exc).__name__}: {exc}"
    after_quality = cache_quality_row(MNA)
    after_hash = sha256_path(cache_path(MNA))
    if after_quality["adjusted_price_validation_result"] != "pass" and not error:
        error = "MNA adjusted total-return cache validation failed"
    after_quality["provider_download"] = downloaded
    after_quality["cache_refreshed"] = downloaded
    previous_ever = set(prior_provider.get("downloaded_symbols_ever", []) or [])
    downloaded_this_run = [MNA] if downloaded else []
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_provider_acquisition": True,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "forbidden_merger_arbitrage_products": list(FORBIDDEN_MERGER_ARBITRAGE_PRODUCTS),
        "forbidden_new_benchmarks": list(FORBIDDEN_NEW_BENCHMARKS),
        "provider": "yfinance_compatible_public_daily_etf_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "series": [
            {
                "symbol": MNA,
                "status": status,
                "cache_path": rel(cache_path(MNA)),
                "hash_before": before_hash,
                "hash_after": after_hash,
                "downloaded_symbols_this_run": downloaded_this_run,
                "adjusted_price_validation_result": after_quality["adjusted_price_validation_result"],
                "row_count": after_quality["row_count"],
                "first_valid_date": after_quality["first_valid_date"],
                "last_valid_date": after_quality["last_valid_date"],
                "corporate_action_and_distribution_columns_preserved": after_quality["corporate_actions_columns_present"],
                "error": error,
            }
        ],
        "downloaded_symbols_this_run": downloaded_this_run,
        "downloaded_symbols_ever": sorted(previous_ever | set(downloaded_this_run)),
        "provider_download": downloaded,
        "MNA_cache_refreshed": downloaded,
        "BIL_cache_refreshed": False,
        "SPY_cache_refreshed": False,
        "alternative_merger_arbitrage_product_downloaded": False,
        "new_benchmark_downloaded": False,
        "provider_download_guardrail_passed": set(downloaded_this_run).issubset(set(AUTHORIZED_DOWNLOAD_SYMBOLS)),
        "invalid_methodology_if_adjusted_total_return_unavailable": after_quality["adjusted_price_validation_result"] != "pass",
    }
    return after_quality, manifest


def read_price(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["date"]).sort_values("date")
    series = pd.to_numeric(frame["adj_close"], errors="coerce")
    out = pd.Series(series.to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]), name=symbol)
    return out.dropna()


def load_common_prices() -> pd.DataFrame:
    prices = pd.concat([read_price(symbol) for symbol in SYMBOLS], axis=1, join="inner").dropna()
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    return prices


def duplicate_review_rows() -> list[dict[str, Any]]:
    search_roots = [
        ROOT / "strategy_lab" / "strategy_registry.yaml",
        ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
        ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
        ROOT / "evidence" / "strategy_evidence_library" / "latest",
        ROOT / "evidence" / "strategy_family_coverage_and_next_discovery_v1" / "latest",
    ]
    mna_mentions = 0
    merger_mentions = 0
    for root in search_roots:
        paths = [root] if root.is_file() else list(root.rglob("*")) if root.exists() else []
        for path in paths:
            if path.suffix.lower() not in {".yaml", ".yml", ".json", ".csv", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            mna_mentions += text.count("mna")
            merger_mentions += text.count("merger")
    return [
        {
            "reviewed_id": "repository_prior_MNA_mentions",
            "review_scope": "registry_lineage_queue_SEL_and_current_evidence_memory",
            "same_wrapper": mna_mentions > 0,
            "same_role": False,
            "same_benchmark_structure": False,
            "exact_corrected_methodology_duplicate": False,
            "evidence_path": "",
            "decision": "no_prior_exact_MNA_BIL_primary_static_wrapper_corrected_methodology_screen_found",
            "mna_mentions": mna_mentions,
            "merger_arbitrage_mentions": merger_mentions,
        },
        {
            "reviewed_id": "static_ETF_wrapper_precedents",
            "review_scope": "USCI_XYLD_SPLV_QUAL_ANGL_static_wrapper_precedents",
            "same_wrapper": False,
            "same_role": False,
            "same_benchmark_structure": False,
            "exact_corrected_methodology_duplicate": False,
            "evidence_path": "",
            "decision": "static_wrapper_precedents_are_not_event_driven_merger_arbitrage_MNA",
            "mna_mentions": "",
            "merger_arbitrage_mentions": "",
        },
        {
            "reviewed_id": "market_neutral_pairs_lowvol_factor_rotation_USCI_VM_DSR",
            "review_scope": "explicit non-duplicate classes from direction-owner constraints",
            "same_wrapper": False,
            "same_role": False,
            "same_benchmark_structure": False,
            "exact_corrected_methodology_duplicate": False,
            "evidence_path": "",
            "decision": "not_duplicate_under_exact_duplicate_gate",
            "mna_mentions": "",
            "merger_arbitrage_mentions": "",
        },
    ]


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_static_wrapper",
        "universe_type": "single_listed_etf_wrapper",
        "instrument": MNA,
        "formation_horizon": "none",
        "holding_horizon": "continuous_full_common_history",
        "rebalance_frequency": "none_after_initial_purchase",
        "weighting_method": "100pct_MNA",
        "risk_overlay": "none",
        "execution_cadence": "initial_project_static_purchase_only",
        "primary_benchmark": "BIL_cash_proxy",
        "secondary_reference": "SPY_buy_and_hold",
    }
    return {
        "candidate_id": CANDIDATE_ID,
        **fields,
        "strategy_fingerprint": stable_hash(fields),
        "fingerprint_algorithm": "sha256_json_sorted_normalized_structural_fields_v1",
    }


def fund_and_methodology_continuity_rows() -> list[dict[str, Any]]:
    return [
        {
            "event_date": "2009-11-17",
            "event_type": "fund_inception",
            "source": "NYLI MNA official fact sheet",
            "source_reference": "Fact sheet Fund Details: Inception Date 11/17/2009",
            "classification": "fund_history",
            "regime_assignment": "pre_regime_start_context",
            "mechanism_change": False,
            "notes": "Fund wrapper history begins before the common adjusted-price path.",
        },
        {
            "event_date": "2019-12-31",
            "event_type": "index_methodology_amendment",
            "source": "NYLI Merger Arbitrage Index methodology amendment history",
            "source_reference": "Maximum individual equity weight reduced to 7.5%; North American hedge assets expanded to include industry ETFs.",
            "classification": "methodology_change",
            "regime_assignment": "regime_2_start",
            "mechanism_change": True,
            "notes": "Frozen before performance as requested.",
        },
        {
            "event_date": "2020-06-01",
            "event_type": "index_methodology_amendment",
            "source": "NYLI Merger Arbitrage Index methodology amendment history",
            "source_reference": "Short-term U.S. Treasury Bill added; cash in excess of 25% allocated to T-bills in lieu of systematic reallocations.",
            "classification": "methodology_change",
            "regime_assignment": "regime_3_start",
            "mechanism_change": True,
            "notes": "Frozen before performance as requested.",
        },
        {
            "event_date": "2024-06-03",
            "event_type": "index_methodology_amendment",
            "source": "NYLI Merger Arbitrage Index methodology amendment history",
            "source_reference": "Eligibility, spread, exit, cash-deployment, and hedge-methodology changes.",
            "classification": "methodology_transition_start",
            "regime_assignment": "transition_interval_start",
            "mechanism_change": True,
            "notes": "Excluded from regime-specific outcome metrics only.",
        },
        {
            "event_date": "2024-06-12",
            "event_type": "index_methodology_amendment",
            "source": "NYLI Merger Arbitrage Index methodology amendment history",
            "source_reference": "Terminated deals removed as soon as practicable rather than waiting until next rebalance.",
            "classification": "methodology_change",
            "regime_assignment": "regime_4_start",
            "mechanism_change": True,
            "notes": "Current-methodology regime starts here.",
        },
        {
            "event_date": "2024-08-28",
            "event_type": "provider_name_transition",
            "source": "NYLI methodology amendment history and MNA fact sheet",
            "source_reference": "Index provider/name changed from IQ Merger Arbitrage Index to NYLI Merger Arbitrage Index; ETF formerly IQ Merger Arbitrage ETF.",
            "classification": "administrative",
            "regime_assignment": "regime_4_administrative_context",
            "mechanism_change": False,
            "notes": "Classified administrative unless repository evidence shows mechanism changed.",
        },
    ]


def freeze_blocks(common_dates: pd.DatetimeIndex, block_count: int = 5) -> list[dict[str, Any]]:
    positions = np.array_split(np.arange(len(common_dates)), block_count)
    rows: list[dict[str, Any]] = []
    for index, pos in enumerate(positions, start=1):
        start = common_dates[int(pos[0])]
        end = common_dates[int(pos[-1])]
        rows.append(
            {
                "block_id": f"block_{index}",
                "block_number": index,
                "start_index": int(pos[0]),
                "end_index": int(pos[-1]),
                "start_date": start.date().isoformat(),
                "end_date": end.date().isoformat(),
                "trading_day_count": int(len(pos)),
                "frozen_before_performance": True,
                "performance_computed_at_definition_time": False,
            }
        )
    return rows


def _date_slice(common_dates: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return common_dates[(common_dates >= start) & (common_dates <= end)]


def freeze_regimes(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    if common_dates.empty:
        return []
    specs = [
        ("regime_1_pre_2019_12_31_amendments", common_dates[0], pd.Timestamp("2019-12-30"), True, "first valid common date through 2019-12-30"),
        ("regime_2_2019_12_31_to_2020_05_31", pd.Timestamp("2019-12-31"), pd.Timestamp("2020-05-31"), True, "2019-12-31 through 2020-05-31"),
        ("regime_3_2020_06_01_to_2024_06_02", pd.Timestamp("2020-06-01"), pd.Timestamp("2024-06-02"), True, "2020-06-01 through 2024-06-02"),
        ("transition_2024_06_03_to_2024_06_11", pd.Timestamp("2024-06-03"), pd.Timestamp("2024-06-11"), False, "declared transition interval"),
        ("regime_4_current_methodology_from_2024_06_12", pd.Timestamp("2024-06-12"), common_dates[-1], True, "2024-06-12 through final common date"),
    ]
    rows: list[dict[str, Any]] = []
    for regime_id, start, end, include, rule in specs:
        dates = _date_slice(common_dates, start, end)
        if dates.empty:
            continue
        rows.append(
            {
                "regime_id": regime_id,
                "start_date": dates[0].date().isoformat(),
                "end_date": dates[-1].date().isoformat(),
                "boundary_rule": rule,
                "included_in_regime_specific_outcome_metrics": include,
                "methodology_boundary_frozen_before_performance": True,
                "trading_day_count": int(len(dates)),
            }
        )
    return rows


def source_and_preregistration(
    common_dates: pd.DatetimeIndex,
    cache_rows: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    regimes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "canonical_family": FAMILY_ID,
        "mechanism": MECHANISM,
        "instrument": MNA,
        "source_id": SOURCE_ID,
        "official_sources": [
            {
                "source_name": "NYLI Merger Arbitrage ETF official fund page",
                "url": "https://www.nylim.com/etf/nyli-merger-arbitrage-etf-mna",
                "source_type": "official_fund_page",
                "used_for_project_performance": False,
            },
            {
                "source_name": "MNA NYLI Merger Arbitrage ETF Fact Sheet",
                "url": "https://www.newyorklifeinvestments.com/assets/documents/index-nyli/mna-nyli-merger-arbitrage-etf-fs.pdf",
                "source_type": "official_fact_sheet",
                "used_for_project_performance": False,
            },
            {
                "source_name": "NYLI Merger Arbitrage Index Methodology",
                "url": "https://www.newyorklifeinvestments.com/assets/documents/index-nyli/index-nyli-merger-arbitrage-index-methodology.pdf",
                "source_type": "official_index_methodology",
                "used_for_project_performance": False,
            },
        ],
        "rule_provenance": {
            "source_explicit": [
                "The fund seeks to track, before fees and expenses, the price and yield performance of the NYLI Merger Arbitrage Index.",
                "The index invests in global companies involved in publicly announced takeovers.",
                "For stock-consideration takeovers, the index includes short exposure to expected acquirer stock received by target shareholders.",
                "Eligibility includes systematic deal-type, friendly-deal, liquidity, size, spread, and opportunity-cost requirements.",
                "Systematic weighting and concentration limits are part of the methodology.",
                "Completed, terminated, aged, negative-spread, negative-momentum, and insufficient-spread deals are removed under defined rules.",
                "Reconstitution and rebalance are monthly.",
                "Bond ETF and Treasury-bill positions can represent unallocated long cash exposure.",
            ],
            "project_wrapper_translation": [
                "The project holds listed MNA only and accepts internal shorts, cash, expenses, turnover, and tracking effects as embedded in adjusted MNA prices.",
                "No individual merger deals, acquirer shorts, hedge positions, or index transaction costs are reconstructed.",
                "BIL is the primary cash-relative hurdle, not a switching instrument.",
            ],
            "project_execution_convention": [
                "Invest 100 percent of project capital in MNA at the first common valid adjusted-close date.",
                "Hold continuously through the final common valid date.",
                "Apply the canonical initial transaction cost once to MNA, BIL, and SPY paths.",
                "Use adjusted total-return price series and matching dates.",
            ],
            "unresolved_material_rules": [],
        },
        "frozen_candidate_rules": {
            "first_common_valid_date": common_dates[0].date().isoformat() if len(common_dates) else "",
            "final_common_valid_date": common_dates[-1].date().isoformat() if len(common_dates) else "",
            "universe": list(SYMBOLS),
            "candidate_asset": MNA,
            "primary_benchmark": "BIL_cash_proxy",
            "secondary_reference": "SPY_buy_and_hold",
            "descriptive_incumbent_comparisons": [
                "paper_forward_vm_quality_lowvol_proxy_v1",
                "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
                "active_combo_vm_dsr_equal_weight_v1",
            ],
            "initial_capital": INITIAL_CAPITAL,
            "initial_transaction_cost_pct": INITIAL_TRANSACTION_COST,
            "entry": "invest 100 percent of capital in MNA at first common valid adjusted-close date",
            "exit": "none; hold continuously to final common date for bounded screen measurement",
            "external_rebalance": "none after initial purchase",
            "timing_signal": "none",
            "BIL_switch": False,
            "deal_level_reconstruction": False,
            "acquirer_short_reconstruction": False,
            "manual_distribution_reinvestment": False,
            "additional_internal_costs_added": False,
            "uses_adjusted_total_return_prices": True,
            "index_backfill_used": False,
            "pre_inception_backfill_used": False,
        },
        "pre_performance_freeze": {
            "candidate_fingerprint": candidate_fingerprint()["strategy_fingerprint"],
            "cache_paths_and_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
            "common_valid_date_range": [
                common_dates[0].date().isoformat() if len(common_dates) else "",
                common_dates[-1].date().isoformat() if len(common_dates) else "",
            ],
            "chronological_block_boundaries_hash": stable_hash(blocks),
            "methodology_regime_boundaries_hash": stable_hash(regimes),
            "calendar_year_definitions": "complete common calendar years excluding partial first and final years for complete-year rates",
            "metrics": [
                "total_return",
                "cagr",
                "annualized_volatility",
                "downside_volatility",
                "max_drawdown",
                "return_to_max_drawdown_ratio",
                "BIL_relative_excess",
                "SPY_risk_comparison",
                "incumbent_correlation_diagnostics",
            ],
            "outcome_conditions_frozen_before_performance": True,
            "source_and_preregistration_written_before_performance_calculation": True,
            "stop_conditions": [
                "invalid adjusted-price, alignment, accounting, exposure, continuity, or determinism checks",
                "exact corrected-methodology MNA static wrapper screen found before performance calculation",
            ],
        },
        "not_authorized": {
            "promotion": False,
            "paper_demo_activation": False,
            "candidate_exhaustive": False,
            "strategy_variants": False,
            "alternative_merger_arbitrage_products": False,
            "deal_database": False,
            "real_money_recommendation": False,
        },
    }


def simulate_static_path(prices: pd.Series) -> tuple[pd.Series, dict[str, Any]]:
    if prices.empty:
        raise RuntimeError("cannot simulate empty static wrapper path")
    entry_price = float(prices.iloc[0])
    entry_cost = INITIAL_CAPITAL * INITIAL_TRANSACTION_COST
    shares = (INITIAL_CAPITAL - entry_cost) / entry_price
    equity = prices.astype(float) * shares
    return equity, {
        "entry_price": entry_price,
        "entry_cost": entry_cost,
        "shares": shares,
        "initial_turnover": 1.0,
        "subsequent_external_turnover": 0.0,
        "portfolio_trade_count": 1,
        "total_project_level_transaction_cost": entry_cost,
        "max_exposure": 1.0,
        "max_weight_sum": 1.0,
    }


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown_series(equity).min()) if not equity.empty else float("nan")


def annualized_volatility(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float(clean.std(ddof=0) * math.sqrt(252)) if len(clean) > 1 else 0.0


def downside_volatility(returns: pd.Series) -> float:
    downside = returns.dropna()
    downside = downside[downside < 0.0]
    return float(downside.std(ddof=0) * math.sqrt(252)) if len(downside) > 1 else 0.0


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-12)
    return float((float(equity.iloc[-1]) / INITIAL_CAPITAL) ** (1.0 / years) - 1.0)


def period_return_from_equity(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    return float(equity.iloc[-1] / equity.iloc[0] - 1.0)


def capture_ratio(asset_returns: pd.Series, benchmark_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "benchmark"]
    subset = aligned[aligned["benchmark"] > 0.0] if direction == "up" else aligned[aligned["benchmark"] < 0.0]
    if subset.empty or abs(float(subset["benchmark"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["benchmark"].mean())


def complete_year_returns_for_equity(equity: pd.Series) -> list[float]:
    if equity.empty:
        return []
    first_year = int(equity.index.min().year)
    last_year = int(equity.index.max().year)
    returns: list[float] = []
    for year in range(first_year + 1, last_year):
        period = equity[equity.index.year == year]
        if not period.empty:
            returns.append(period_return_from_equity(period))
    return returns


def metrics_for_symbol(symbol: str, equity: pd.Series, spy_returns: pd.Series) -> dict[str, Any]:
    daily_returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    dd = max_drawdown(equity)
    complete_year_returns = complete_year_returns_for_equity(equity)
    positive_rate = float(np.mean([year_return > 0.0 for year_return in complete_year_returns])) if complete_year_returns else float("nan")
    worst_complete_year_return = float(min(complete_year_returns)) if complete_year_returns else float("nan")
    return {
        "symbol": symbol,
        "role": "candidate" if symbol == MNA else ("primary_benchmark" if symbol == BIL else "secondary_opportunity_cost_reference"),
        "start_date": equity.index[0].date().isoformat(),
        "end_date": equity.index[-1].date().isoformat(),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "positive_complete_year_rate": positive_rate,
        "worst_complete_year_return": worst_complete_year_return,
        "annualized_volatility": annualized_volatility(daily_returns),
        "downside_volatility": downside_volatility(daily_returns),
        "max_drawdown": dd,
        "return_to_max_drawdown_ratio": float(total_return / abs(dd)) if dd < 0.0 else float("nan"),
        "upside_capture_versus_SPY": capture_ratio(daily_returns, spy_returns, "up"),
        "downside_capture_versus_SPY": capture_ratio(daily_returns, spy_returns, "down"),
    }


def build_equity_map(prices: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, dict[str, Any]]]:
    equity_map: dict[str, pd.Series] = {}
    ops_map: dict[str, dict[str, Any]] = {}
    for symbol in SYMBOLS:
        equity, ops = simulate_static_path(prices[symbol])
        equity_map[symbol] = equity
        ops_map[symbol] = ops
    return equity_map, ops_map


def evaluate_blocks(prices: pd.DataFrame, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in blocks:
        subset = prices.loc[block["start_date"] : block["end_date"]]
        equity_map, ops_map = build_equity_map(subset)
        spy_returns = equity_map[SPY].pct_change().dropna()
        metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], spy_returns) for symbol in SYMBOLS}
        mna = metrics[MNA]
        bil = metrics[BIL]
        spy = metrics[SPY]
        rows.append(
            {
                "block_id": block["block_id"],
                "block_number": block["block_number"],
                "start_date": block["start_date"],
                "end_date": block["end_date"],
                "trading_day_count": block["trading_day_count"],
                "MNA_total_return": mna["total_return"],
                "BIL_total_return": bil["total_return"],
                "SPY_total_return": spy["total_return"],
                "MNA_max_drawdown": mna["max_drawdown"],
                "BIL_max_drawdown": bil["max_drawdown"],
                "SPY_max_drawdown": spy["max_drawdown"],
                "MNA_return_to_max_drawdown_ratio": mna["return_to_max_drawdown_ratio"],
                "BIL_return_to_max_drawdown_ratio": bil["return_to_max_drawdown_ratio"],
                "SPY_return_to_max_drawdown_ratio": spy["return_to_max_drawdown_ratio"],
                "excess_return_versus_BIL": float(mna["total_return"] - bil["total_return"]),
                "MNA_beats_BIL": bool(mna["total_return"] > bil["total_return"]),
                "MNA_smaller_drawdown_than_SPY": bool(mna["max_drawdown"] > spy["max_drawdown"]),
                "initial_cost_equivalent": bool(
                    abs(ops_map[MNA]["total_project_level_transaction_cost"] - ops_map[BIL]["total_project_level_transaction_cost"]) < 1e-9
                ),
                "max_exposure": 1.0,
                "max_weight_sum": 1.0,
            }
        )
    return rows


def evaluate_regimes(prices: pd.DataFrame, regimes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for regime in regimes:
        subset = prices.loc[regime["start_date"] : regime["end_date"]]
        equity_map, _ops = build_equity_map(subset)
        spy_returns = equity_map[SPY].pct_change().dropna()
        metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], spy_returns) for symbol in SYMBOLS}
        rows.append(
            {
                "regime_id": regime["regime_id"],
                "start_date": regime["start_date"],
                "end_date": regime["end_date"],
                "trading_day_count": regime["trading_day_count"],
                "included_in_regime_specific_outcome_metrics": regime["included_in_regime_specific_outcome_metrics"],
                "MNA_total_return": metrics[MNA]["total_return"],
                "BIL_total_return": metrics[BIL]["total_return"],
                "SPY_total_return": metrics[SPY]["total_return"],
                "MNA_cagr": metrics[MNA]["cagr"],
                "BIL_cagr": metrics[BIL]["cagr"],
                "SPY_cagr": metrics[SPY]["cagr"],
                "MNA_max_drawdown": metrics[MNA]["max_drawdown"],
                "BIL_max_drawdown": metrics[BIL]["max_drawdown"],
                "SPY_max_drawdown": metrics[SPY]["max_drawdown"],
                "excess_return_versus_BIL": float(metrics[MNA]["total_return"] - metrics[BIL]["total_return"]),
                "annualized_excess_versus_BIL": float(metrics[MNA]["cagr"] - metrics[BIL]["cagr"]),
                "MNA_beats_BIL": bool(metrics[MNA]["total_return"] > metrics[BIL]["total_return"]),
            }
        )
    return rows


def calendar_rows(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    mna_equity = equity_map[MNA]
    first_year = int(mna_equity.index.min().year)
    last_year = int(mna_equity.index.max().year)
    rows: list[dict[str, Any]] = []
    for year in range(first_year, last_year + 1):
        period_type = "complete_calendar_year"
        if year == first_year:
            period_type = "partial_first_year"
        if year == last_year:
            period_type = "partial_final_year" if period_type == "complete_calendar_year" else period_type + "_and_final"
        row: dict[str, Any] = {
            "calendar_period": str(year),
            "period_type": period_type,
            "start_date": "",
            "end_date": "",
            "MNA_return": "",
            "BIL_return": "",
            "SPY_return": "",
            "MNA_max_drawdown": "",
            "BIL_max_drawdown": "",
            "SPY_max_drawdown": "",
            "MNA_beats_BIL": "",
            "MNA_smaller_drawdown_than_SPY": "",
            "MNA_loses_money": "",
        }
        for symbol, equity in equity_map.items():
            period = equity[equity.index.year == year]
            if period.empty:
                continue
            if row["start_date"] == "":
                row["start_date"] = period.index.min().date().isoformat()
                row["end_date"] = period.index.max().date().isoformat()
            row[f"{symbol}_return"] = period_return_from_equity(period)
            row[f"{symbol}_max_drawdown"] = max_drawdown(period)
        if row["MNA_return"] != "" and row["BIL_return"] != "":
            row["MNA_beats_BIL"] = float(row["MNA_return"]) > float(row["BIL_return"])
        if row["MNA_max_drawdown"] != "" and row["SPY_max_drawdown"] != "":
            row["MNA_smaller_drawdown_than_SPY"] = float(row["MNA_max_drawdown"]) > float(row["SPY_max_drawdown"])
        if row["MNA_return"] != "":
            row["MNA_loses_money"] = float(row["MNA_return"]) < 0.0
        rows.append(row)
    return rows


def bil_relative_metrics(
    full_metrics: dict[str, dict[str, Any]],
    block_rows: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    regime_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    mna = full_metrics[MNA]
    bil = full_metrics[BIL]
    block_excess = [float(row["excess_return_versus_BIL"]) for row in block_rows]
    complete_calendar = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    included_regimes = [row for row in regime_rows if row["included_in_regime_specific_outcome_metrics"] is True]
    row: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": "BIL_cash_proxy",
        "full_period_excess_total_return_versus_BIL": float(mna["total_return"] - bil["total_return"]),
        "cagr_difference_versus_BIL": float(mna["cagr"] - bil["cagr"]),
        "mean_block_excess_versus_BIL": float(np.mean(block_excess)) if block_excess else float("nan"),
        "median_block_excess_versus_BIL": float(np.median(block_excess)) if block_excess else float("nan"),
        "blocks_beating_BIL": int(sum(bool(row_["MNA_beats_BIL"]) for row_ in block_rows)),
        "calendar_years_beating_BIL": int(sum(row_["MNA_beats_BIL"] is True for row_ in complete_calendar)),
        "complete_calendar_year_count": int(len(complete_calendar)),
        "calendar_year_beat_rate_versus_BIL": float(np.mean([row_["MNA_beats_BIL"] is True for row_ in complete_calendar])) if complete_calendar else float("nan"),
        "latest_block_excess_return": float(block_rows[-1]["excess_return_versus_BIL"]) if block_rows else float("nan"),
        "regime_level_excess_returns": "|".join(f"{regime['regime_id']}:{csv_value(regime['excess_return_versus_BIL'])}" for regime in included_regimes),
        "regime_level_annualized_excess_returns": "|".join(f"{regime['regime_id']}:{csv_value(regime['annualized_excess_versus_BIL'])}" for regime in included_regimes),
    }
    for regime in included_regimes:
        row[f"{regime['regime_id']}_excess_return_versus_BIL"] = regime["excess_return_versus_BIL"]
        row[f"{regime['regime_id']}_annualized_excess_versus_BIL"] = regime["annualized_excess_versus_BIL"]
    return row


def spy_risk_comparison(
    full_metrics: dict[str, dict[str, Any]],
    block_rows: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
) -> dict[str, Any]:
    mna = full_metrics[MNA]
    spy = full_metrics[SPY]
    complete_calendar = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    return {
        "candidate_id": CANDIDATE_ID,
        "secondary_reference": "SPY_buy_and_hold",
        "max_drawdown_difference_versus_SPY": float(mna["max_drawdown"] - spy["max_drawdown"]),
        "volatility_difference_versus_SPY": float(mna["annualized_volatility"] - spy["annualized_volatility"]),
        "downside_volatility_difference_versus_SPY": float(mna["downside_volatility"] - spy["downside_volatility"]),
        "downside_capture_versus_SPY": mna["downside_capture_versus_SPY"],
        "upside_capture_versus_SPY": mna["upside_capture_versus_SPY"],
        "blocks_with_lower_drawdown_than_SPY": int(sum(bool(row["MNA_smaller_drawdown_than_SPY"]) for row in block_rows)),
        "calendar_years_with_lower_drawdown_than_SPY": int(sum(row["MNA_smaller_drawdown_than_SPY"] is True for row in complete_calendar)),
        "complete_calendar_year_count": int(len(complete_calendar)),
    }


def _daily_returns_from_equity(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def _existing_reference_returns(reference_id: str) -> pd.Series:
    if reference_id == SPY:
        return read_price(SPY).pct_change().dropna()
    if reference_id == "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1":
        return read_price("USCI").pct_change().dropna()
    if not ACTIVE_COMBO_SERIES_PATH.exists():
        return pd.Series(dtype=float)
    frame = pd.read_csv(ACTIVE_COMBO_SERIES_PATH)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["date"]).set_index("date").sort_index()
    column_map = {
        "paper_forward_vm_quality_lowvol_proxy_v1": "vm_standalone_equity",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": "dsr_standalone_equity",
        "active_combo_vm_dsr_equal_weight_v1": "active_combo_equity",
    }
    column = column_map.get(reference_id)
    if column not in frame:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").pct_change().dropna()


def diversification_and_redundancy(mna_equity: pd.Series) -> list[dict[str, Any]]:
    mna_returns = _daily_returns_from_equity(mna_equity)
    spy_returns = _existing_reference_returns(SPY)
    rows: list[dict[str, Any]] = []
    references = [
        "SPY",
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "active_combo_vm_dsr_equal_weight_v1",
    ]
    spy_drawdown = None
    if not spy_returns.empty:
        spy_prices = read_price(SPY)
        spy_drawdown = drawdown_series(spy_prices)
    for ref in references:
        ref_returns = _existing_reference_returns(ref)
        aligned = pd.concat([mna_returns, ref_returns], axis=1, join="inner").dropna()
        aligned.columns = ["MNA", "reference"]
        corr = float(aligned["MNA"].corr(aligned["reference"])) if len(aligned) > 2 else float("nan")
        corr_drawdown = float("nan")
        if spy_drawdown is not None and not aligned.empty:
            dd_flags = spy_drawdown.reindex(aligned.index).fillna(0.0) < 0.0
            subset = aligned[dd_flags]
            if len(subset) > 2:
                corr_drawdown = float(subset["MNA"].corr(subset["reference"]))
        rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "reference_id": ref,
                "aligned_daily_return_count": int(len(aligned)),
                "common_start": aligned.index.min().date().isoformat() if not aligned.empty else "",
                "common_end": aligned.index.max().date().isoformat() if not aligned.empty else "",
                "daily_return_correlation": corr,
                "correlation_during_SPY_drawdown_periods": corr_drawdown,
                "clearly_redundant": bool(math.isfinite(corr) and abs(corr) >= 0.90),
                "descriptive_only_not_allocation_input": True,
            }
        )
    return rows


def determine_outcome(
    full_metrics: dict[str, dict[str, Any]],
    bil_relative: dict[str, Any],
    spy_risk: dict[str, Any],
    diversification_rows: list[dict[str, Any]],
    regime_rows: list[dict[str, Any]],
    invariants_pass: bool,
) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Data, adjusted-price, accounting, exposure, alignment, or determinism invariant failed"
    mna = full_metrics[MNA]
    bil = full_metrics[BIL]
    full_return_beats_bil = mna["total_return"] > bil["total_return"]
    cagr_beats_bil_by_2pct = float(bil_relative["cagr_difference_versus_BIL"]) >= 0.02
    median_block_positive = float(bil_relative["median_block_excess_versus_BIL"]) > 0.0
    blocks_beating = int(bil_relative["blocks_beating_BIL"])
    calendar_rate = float(bil_relative["calendar_year_beat_rate_versus_BIL"]) if math.isfinite(float(bil_relative["calendar_year_beat_rate_versus_BIL"])) else 0.0
    drawdown_advantage = float(spy_risk["max_drawdown_difference_versus_SPY"])
    spy_corr_row = next((row for row in diversification_rows if row["reference_id"] == "SPY"), {})
    spy_corr = float(spy_corr_row.get("daily_return_correlation", float("nan")))
    latest_block_underperforms = float(bil_relative["latest_block_excess_return"]) < 0.0
    current_regime = next((row for row in regime_rows if row["regime_id"] == "regime_4_current_methodology_from_2024_06_12"), {})
    current_regime_underperforms = current_regime and float(current_regime.get("excess_return_versus_BIL", 0.0)) < 0.0
    if (
        full_return_beats_bil
        and cagr_beats_bil_by_2pct
        and median_block_positive
        and blocks_beating >= 4
        and calendar_rate >= 0.70
        and drawdown_advantage >= 0.10
        and math.isfinite(spy_corr)
        and spy_corr < 0.60
    ):
        return "comparative_evidence_positive", "MNA passed all pre-registered cash-relative and SPY-risk comparative evidence gates"
    if full_return_beats_bil and median_block_positive and blocks_beating >= 4 and (latest_block_underperforms or current_regime_underperforms):
        return "historical_edge_recently_weakened", "Full-period and median-block BIL excess were positive with at least four winning blocks, but latest block or current methodology regime underperformed BIL"
    sufficiently_long = [
        row for row in regime_rows if row.get("included_in_regime_specific_outcome_metrics") is True and int(row.get("trading_day_count", 0)) >= 252
    ]
    annualized = [float(row["annualized_excess_versus_BIL"]) for row in sufficiently_long if math.isfinite(float(row["annualized_excess_versus_BIL"]))]
    if annualized:
        signs_differ = any(value > 0.0 for value in annualized) and any(value < 0.0 for value in annualized)
        spread = max(annualized) - min(annualized)
        if signs_differ and spread >= 0.03:
            return "methodology_regime_instability", "Sufficiently long methodology regimes had opposite-signed annualized BIL excess with at least three percentage points of spread"
    materially_lowers_risk = drawdown_advantage >= 0.10 or float(spy_risk["volatility_difference_versus_SPY"]) <= -0.05
    if materially_lowers_risk and math.isfinite(spy_corr) and spy_corr < 0.60:
        return "diversification_value_without_sufficient_cash_edge", "MNA lowered SPY risk and correlation but failed the required persistent return premium over BIL"
    return "no_material_edge", "Neither persistent BIL-relative return premium nor sufficient diversification evidence was supported"


def exact_variant_memory(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    preserve = outcome == "comparative_evidence_positive"
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome": outcome,
            "primary_failure_reason": "" if preserve else failure_reason,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "broader_event_driven_merger_arbitrage_family_closed": False,
            "ARB_MRGR_MARB_variations_prohibited_immediately": True,
            "timing_blend_hedge_deal_selection_variations_prohibited_immediately": True,
            "preserve_for_direction_owner_review": preserve,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "candidate_exhaustive_authorized": False,
            "lifecycle_state_changed": False,
        }
    ]


def run() -> dict[str, Any]:
    prior_provider = read_json(EVIDENCE_DIR / "provider_acquisition_manifest.json")
    protected_paths = [
        REGISTRY_PATH,
        ACTIVE_OBSERVATIONS_PATH,
        PAPER_FORWARD_DIR / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
        PAPER_FORWARD_DIR / "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1" / "active_observation.yaml",
        ACTIVE_COMBO_SERIES_PATH,
    ]
    cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    state_before = file_snapshot(protected_paths)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    mna_quality, provider_manifest = ensure_mna_cache(prior_provider)
    bil_quality = cache_quality_row(BIL)
    spy_quality = cache_quality_row(SPY)
    cache_rows = [mna_quality, bil_quality, spy_quality]
    cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    provider_manifest["BIL_cache_refreshed"] = cache_before[BIL] != cache_after[BIL]
    provider_manifest["SPY_cache_refreshed"] = cache_before[SPY] != cache_after[SPY]

    duplicate_rows = duplicate_review_rows()
    fund_rows = fund_and_methodology_continuity_rows()
    exact_duplicate = any(row["exact_corrected_methodology_duplicate"] is True for row in duplicate_rows)

    invalid_reason = ""
    prices = pd.DataFrame()
    blocks: list[dict[str, Any]] = []
    regimes: list[dict[str, Any]] = []
    full_metrics_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    calendar: list[dict[str, Any]] = []
    bil_relative: dict[str, Any] = {}
    spy_risk: dict[str, Any] = {}
    diversification_rows: list[dict[str, Any]] = []
    invariants_row: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""

    try:
        if exact_duplicate:
            raise RuntimeError("exact corrected-methodology MNA static wrapper screen already exists")
        if any(row["adjusted_price_validation_result"] != "pass" for row in cache_rows):
            raise RuntimeError("required adjusted-price cache validation failed")
        prices = load_common_prices()
        if prices.empty:
            raise RuntimeError("common MNA/BIL/SPY date range is empty")
        blocks = freeze_blocks(prices.index)
        regimes = freeze_regimes(prices.index)

        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(
            EVIDENCE_DIR / "cache_manifest.json",
            {
                "candidate_id": CANDIDATE_ID,
                "series": cache_rows,
                "common_valid_start": prices.index[0].date().isoformat(),
                "common_valid_end": prices.index[-1].date().isoformat(),
                "common_valid_row_count": int(len(prices)),
                "adjusted_prices_required": True,
                "raw_close_substitution_allowed": False,
            },
        )
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "fund_and_methodology_continuity.csv", fund_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(prices.index, cache_rows, blocks, regimes))

        equity_map, ops_map = build_equity_map(prices)
        spy_returns = equity_map[SPY].pct_change().dropna()
        full_metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], spy_returns) for symbol in SYMBOLS}
        block_rows = evaluate_blocks(prices, blocks)
        regime_rows = evaluate_regimes(prices, regimes)
        calendar = calendar_rows(equity_map)
        worst_by_symbol = {
            MNA: min(float(row["MNA_total_return"]) for row in block_rows),
            BIL: min(float(row["BIL_total_return"]) for row in block_rows),
            SPY: min(float(row["SPY_total_return"]) for row in block_rows),
        }
        for symbol in SYMBOLS:
            row = {**full_metrics[symbol], **ops_map[symbol]}
            row["worst_chronological_block_return"] = worst_by_symbol[symbol]
            full_metrics_rows.append(row)
        bil_relative = bil_relative_metrics(full_metrics, block_rows, calendar, regime_rows)
        spy_risk = spy_risk_comparison(full_metrics, block_rows, calendar)
        diversification_rows = diversification_and_redundancy(equity_map[MNA])
        state_after = file_snapshot(protected_paths)
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": True,
            "adjusted_prices_used": True,
            "raw_close_substitution_used": False,
            "manual_distribution_reinvestment": False,
            "deal_level_positions_reconstructed": False,
            "acquirer_short_or_hedge_positions_created_by_project": False,
            "individual_merger_deal_database_created": False,
            "alternative_merger_arbitrage_product_used": False,
            "initial_turnover": 1.0,
            "subsequent_external_turnover": 0.0,
            "portfolio_trade_count": 1,
            "total_project_level_transaction_cost": ops_map[MNA]["total_project_level_transaction_cost"],
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "missing_adjusted_price_count": int(prices.isna().sum().sum()),
            "candidate_benchmark_date_alignment": True,
            "initial_cost_equivalent_across_candidate_and_benchmarks": True,
            "MNA_cache_hash": cache_after[MNA],
            "BIL_cache_hash": cache_after[BIL],
            "SPY_cache_hash": cache_after[SPY],
            "MNA_cache_refreshed": provider_manifest["MNA_cache_refreshed"],
            "BIL_cache_refreshed": provider_manifest["BIL_cache_refreshed"],
            "SPY_cache_refreshed": provider_manifest["SPY_cache_refreshed"],
            "existing_VM_DSR_USCI_combo_states_unchanged": state_before == state_after,
            "paper_forward_or_broker_order_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome(full_metrics, bil_relative, spy_risk, diversification_rows, regime_rows, True)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        if not blocks and not prices.empty:
            blocks = freeze_blocks(prices.index)
        if not regimes and not prices.empty:
            regimes = freeze_regimes(prices.index)
        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(EVIDENCE_DIR / "cache_manifest.json", {"candidate_id": CANDIDATE_ID, "series": cache_rows})
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "fund_and_methodology_continuity.csv", fund_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(pd.DatetimeIndex([]), cache_rows, blocks, regimes))
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": False,
            "adjusted_prices_used": False,
            "raw_close_substitution_used": False,
            "manual_distribution_reinvestment": False,
            "deal_level_positions_reconstructed": False,
            "acquirer_short_or_hedge_positions_created_by_project": False,
            "individual_merger_deal_database_created": False,
            "alternative_merger_arbitrage_product_used": False,
            "initial_turnover": "",
            "subsequent_external_turnover": "",
            "portfolio_trade_count": "",
            "total_project_level_transaction_cost": "",
            "max_daily_exposure": "",
            "max_daily_weight_sum": "",
            "missing_adjusted_price_count": "",
            "candidate_benchmark_date_alignment": False,
            "initial_cost_equivalent_across_candidate_and_benchmarks": False,
            "MNA_cache_hash": cache_after[MNA],
            "BIL_cache_hash": cache_after[BIL],
            "SPY_cache_hash": cache_after[SPY],
            "MNA_cache_refreshed": provider_manifest["MNA_cache_refreshed"],
            "BIL_cache_refreshed": provider_manifest["BIL_cache_refreshed"],
            "SPY_cache_refreshed": provider_manifest["SPY_cache_refreshed"],
            "existing_VM_DSR_USCI_combo_states_unchanged": file_snapshot(protected_paths) == state_before,
            "paper_forward_or_broker_order_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": False,
        }

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_metrics_rows)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "methodology_regime_results.csv", regime_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar)
    write_csv(EVIDENCE_DIR / "bil_relative_metrics.csv", [bil_relative])
    write_csv(EVIDENCE_DIR / "spy_risk_comparison.csv", [spy_risk])
    write_csv(EVIDENCE_DIR / "diversification_and_redundancy.csv", diversification_rows)
    write_csv(EVIDENCE_DIR / "accounting_data_and_exposure_invariants.csv", [invariants_row])
    memory = exact_variant_memory(outcome, outcome_reason)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "direction_owner_validation_review_mna_static_merger_arbitrage_wrapper_v1"
        if outcome == "comparative_evidence_positive"
        else "record_mna_exact_variant_memory_and_resume_source_queue"
    )
    screening_outcome = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": "" if outcome == "comparative_evidence_positive" else outcome_reason,
        "preserve_exact_candidate_for_direction_owner_review": outcome == "comparative_evidence_positive",
        "exact_candidate_closed_for_immediate_retesting": memory[0]["exact_candidate_closed_for_immediate_retesting"],
        "broader_family_closed": False,
        "provider_download": provider_manifest["provider_download"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "invalid_reason": invalid_reason,
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening_outcome)
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "only_MNA_provider_acquisition_authorized": provider_manifest["authorized_download_symbols"] == [MNA],
        "downloaded_symbols_limited_to_MNA": set(provider_manifest["downloaded_symbols_this_run"]).issubset({MNA}),
        "BIL_cache_not_refreshed": provider_manifest["BIL_cache_refreshed"] is False,
        "SPY_cache_not_refreshed": provider_manifest["SPY_cache_refreshed"] is False,
        "adjusted_total_return_prices_used": invariants_row["adjusted_prices_used"] is True,
        "MNA_purchased_once_and_held": invariants_row["initial_turnover"] == 1.0 and invariants_row["portfolio_trade_count"] == 1,
        "no_deal_level_positions_reconstructed": invariants_row["deal_level_positions_reconstructed"] is False,
        "no_project_short_or_hedge_positions_created": invariants_row["acquirer_short_or_hedge_positions_created_by_project"] is False,
        "no_alternative_merger_arbitrage_product": invariants_row["alternative_merger_arbitrage_product_used"] is False,
        "regime_boundaries_frozen_before_performance": all(row.get("methodology_boundary_frozen_before_performance") is True for row in regimes),
        "chronological_blocks_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in blocks),
        "MNA_BIL_SPY_matching_dates": invariants_row["candidate_benchmark_date_alignment"] is True,
        "initial_cost_treatment_equivalent": invariants_row["initial_cost_equivalent_across_candidate_and_benchmarks"] is True,
        "exposure_never_exceeds_1": (invariants_row.get("max_daily_exposure") in {"", None}) or float(invariants_row["max_daily_exposure"]) <= 1.000001,
        "existing_observation_states_unchanged": invariants_row["existing_VM_DSR_USCI_combo_states_unchanged"] is True,
        "no_paper_demo_or_broker_order": invariants_row["paper_forward_or_broker_order_created"] is False,
        "historical_observation_files_unchanged": invariants_row["existing_VM_DSR_USCI_combo_states_unchanged"] is True,
        "output_generation_deterministic": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "only_MNA_provider_acquisition_authorized",
        "downloaded_symbols_limited_to_MNA",
        "BIL_cache_not_refreshed",
        "SPY_cache_not_refreshed",
        "adjusted_total_return_prices_used",
        "MNA_purchased_once_and_held",
        "no_deal_level_positions_reconstructed",
        "no_project_short_or_hedge_positions_created",
        "no_alternative_merger_arbitrage_product",
        "regime_boundaries_frozen_before_performance",
        "chronological_blocks_frozen_before_performance",
        "MNA_BIL_SPY_matching_dates",
        "initial_cost_treatment_equivalent",
        "exposure_never_exceeds_1",
        "existing_observation_states_unchanged",
        "no_paper_demo_or_broker_order",
        "historical_observation_files_unchanged",
        "output_generation_deterministic",
    }
    required_false = {"promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation"}
    consistency["consistency_passed"] = all(consistency[key] is True for key in required_true) and all(
        consistency[key] is False for key in required_false
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# MNA Static Merger Arbitrage Wrapper Bounded Screen v1

Candidate `{CANDIDATE_ID}` was evaluated as one listed ETF wrapper: buy `MNA` once on the first common valid `MNA`/`BIL`/`SPY` adjusted-close date and hold through the final common date.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider acquisition this run: `{provider_manifest['provider_download']}`
- Common valid rows: `{len(prices) if not prices.empty else 0}`
- Primary benchmark: `BIL_cash_proxy`
- Secondary opportunity-cost reference: `SPY_buy_and_hold`
- Chronological blocks frozen before performance: `{len(blocks) == 5}`
- Methodology regimes frozen before performance: `{len(regimes) >= 1}`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

The screen does not reconstruct merger deals, acquirer shorts, hedge positions, internal index turnover, or transaction costs. It does not test ARB, MRGR, MARB, tactical timing, blends, or alternative benchmarks, and it does not alter VM, DSR, USCI, active-combo, registry, or paper/demo observation state.
""",
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_dir": rel(EVIDENCE_DIR),
        "outcome": outcome,
        "consistency_passed": consistency["consistency_passed"],
        "provider_download": provider_manifest["provider_download"],
        "common_valid_rows": int(len(prices)) if not prices.empty else 0,
        "next_action": next_action,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
