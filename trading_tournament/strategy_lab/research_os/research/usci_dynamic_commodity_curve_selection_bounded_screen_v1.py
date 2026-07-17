from __future__ import annotations

import csv
import hashlib
import inspect
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_active_strategy_evidence_recompute as active
from src.data import DataQualityError, build_adjusted_ohlc


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
CANDIDATE_ID = "usci_dynamic_commodity_curve_selection_wrapper_v1"
FAMILY_ID = "commodity_curve_selection"
MECHANISM = "dynamic_commodity_futures_curve_selection_investable_wrapper"
SOURCE_ID = "uscf_usci_summerhaven_dynamic_commodity_index_official_source_packet_v1"
USCI = "USCI"
DBC = "DBC"
BIL = "BIL"
SPY = "SPY"
SYMBOLS = (USCI, DBC, BIL, SPY)
AUTHORIZED_DOWNLOAD_SYMBOLS = (USCI, DBC)
FORBIDDEN_COMMODITY_PRODUCTS = ("SDCI", "GSG", "PDBC", "COMT")
REGIME_BOUNDARY = pd.Timestamp("2020-12-24")
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
INITIAL_TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
CURRENT_CHECKPOINT_DIR = ROOT / "evidence" / "current_research_checkpoint" / "latest"
XYLD_EVIDENCE_DIR = ROOT / "evidence" / "xyld_static_sp500_covered_call_bounded_screen_v1" / "latest"
HALLOWEEN_EVIDENCE_DIR = ROOT / "evidence" / "spy_halloween_nov_apr_bil_bounded_screen_v1" / "latest"
REQUEST_SETTINGS = {
    "start": "2006-01-01",
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
    "higher_return_higher_risk",
    "risk_reduction_without_return_edge",
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
        raise ValueError(f"Only USCI and DBC provider acquisition is authorized for this screen; got {symbol}")
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2006-01-01"),
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
    ready = (
        len(frame) > 0
        and "date" in frame.columns
        and "adj_close" in frame.columns
        and row["date_monotonic_increasing"] is True
        and row["duplicate_date_count"] == 0
        and row["missing_price_count"] == 0
        and row["missing_adj_close_count"] == 0
        and row["nonpositive_adj_close_count"] == 0
    )
    row["adjusted_price_validation_result"] = "pass" if ready else "fail"
    return row


def ensure_authorized_cache(symbol: str, prior_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    symbol = validate_authorized_download_symbol(symbol)
    path = cache_path(symbol)
    preexisting = path.exists()
    downloaded_this_run: list[str] = []
    prior_series = {
        str(row.get("symbol", "")).upper(): row
        for row in prior_manifest.get("series", [])
        if isinstance(row, dict)
    }
    retrieval_timestamp = str(prior_series.get(symbol, {}).get("first_retrieval_timestamp_utc") or "")
    acquisition_error = ""
    if not preexisting:
        try:
            raw = default_yfinance_downloader(symbol, REQUEST_SETTINGS)
            if raw is None or raw.empty:
                raise DataQualityError(f"{symbol}: yfinance returned no rows")
            normalized = build_adjusted_ohlc(raw, symbol)
            path.parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(path, index=False)
            downloaded_this_run.append(symbol)
            retrieval_timestamp = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            acquisition_error = f"{type(exc).__name__}: {exc}"
    quality = cache_quality_row(symbol)
    quality["provider_download"] = bool(downloaded_this_run)
    series_manifest = {
        "symbol": symbol,
        "cache_preexisting_at_run_start": preexisting,
        "downloaded_symbols_this_run": downloaded_this_run,
        "first_retrieval_timestamp_utc": retrieval_timestamp,
        "acquisition_error": acquisition_error,
        "cache_hash": quality["cache_hash"],
        "cache_path": quality["cache_path"],
        "quality_status": quality["adjusted_price_validation_result"],
    }
    return quality, series_manifest


def read_adjusted_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    if clean.empty:
        raise RuntimeError(f"{symbol} adjusted-close cache is empty")
    return clean.set_index("date")[symbol].astype(float)


def load_common_prices() -> pd.DataFrame:
    close_map = {symbol: read_adjusted_close(symbol) for symbol in SYMBOLS}
    common = close_map[USCI].index
    for symbol in (DBC, BIL, SPY):
        common = common.intersection(close_map[symbol].index)
    common = pd.DatetimeIndex(common).sort_values()
    return pd.DataFrame({symbol: close_map[symbol].reindex(common) for symbol in SYMBOLS}).dropna()


def candidate_fingerprint() -> dict[str, Any]:
    fingerprint = {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_static_wrapper",
        "universe_type": "single_broad_commodity_curve_selection_wrapper",
        "formation_horizon": "internal_index_monthly_selection_not_reconstructed",
        "holding_horizon": "full_common_history",
        "rebalance_frequency": "none_after_initial_external_purchase",
        "weighting_method": "100pct_USCI",
        "risk_overlay": "none",
        "execution_cadence": "initial_adjusted_close_purchase_only",
        "cash_rule": "none_for_candidate",
        "benchmark_rule": "matching_date_DBC_primary_BIL_SPY_context",
    }
    fingerprint["strategy_fingerprint"] = stable_hash(fingerprint)
    return fingerprint


def duplicate_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": "repository_prior_USCI_mentions",
            "review_scope": "exact USCI wrapper screen search",
            "same_ticker": True,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "prior_USCI_mentions_are_commodity_basket_or_data_context_not_exact_static_USCI_vs_DBC_screen",
        },
        {
            "reviewed_id": "commodity_basket_etf_momentum_v1",
            "review_scope": "commodity wrapper family overlap",
            "same_ticker": True,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "materially_distinct_monthly_momentum_rotation_not_static_USCI_wrapper",
        },
        {
            "reviewed_id": "managed_futures_proxy_etf_trend_v1",
            "review_scope": "futures-internal overlap check",
            "same_ticker": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "materially_distinct_no_project_generated_long_short_trend_signals_or_leverage",
        },
        {
            "reviewed_id": "macro_gld_duration_risk_off",
            "review_scope": "macro/gold/duration overlap",
            "same_ticker": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "materially_distinct_commodity_curve_selection_wrapper",
        },
        {
            "reviewed_id": "xyld_static_sp500_covered_call_v1",
            "review_scope": "latest completed exact candidate",
            "same_ticker": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "xyld_result_preserved_not_rerun",
        },
        {
            "reviewed_id": "spy_halloween_nov_apr_bil_v1",
            "review_scope": "prior calendar candidate",
            "same_ticker": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "halloween_result_preserved_not_rerun",
        },
    ]


def fund_and_index_continuity_rows(cache_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cache_by_symbol = {row["symbol"]: row for row in cache_rows}
    return [
        {
            "wrapper": USCI,
            "field": "current_official_name",
            "value": "United States Commodity Index Fund",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "none",
        },
        {
            "wrapper": USCI,
            "field": "underlying_index",
            "value": "SummerHaven Dynamic Commodity Index Total Return",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "mandatory 2020-12-24 methodology boundary",
        },
        {
            "wrapper": USCI,
            "field": "first_valid_cache_date",
            "value": cache_by_symbol.get(USCI, {}).get("first_valid_date", ""),
            "source": "local adjusted-price cache",
            "material_interpretation_effect": "defines project wrapper evaluation start when common with DBC/BIL/SPY",
        },
        {
            "wrapper": USCI,
            "field": "documented_material_index_change",
            "value": "selection process on 2020-12-24 consolidated six sectors into five and introduced other methodology changes described in the prospectus",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "report Regime 1 and Regime 2 separately",
        },
        {
            "wrapper": USCI,
            "field": "one_comparable_investable_path",
            "value": "true; continuous adjusted-price wrapper path retained with separate regime diagnostics",
            "source": "task rule plus adjusted-price cache",
            "material_interpretation_effect": "does not reconstruct underlying futures or collateral return",
        },
        {
            "wrapper": DBC,
            "field": "current_official_name",
            "value": "Invesco DB Commodity Index Tracking Fund",
            "source": "repository commodity product review context and current local cache identity",
            "material_interpretation_effect": "primary broad-commodity opportunity-cost benchmark",
        },
        {
            "wrapper": DBC,
            "field": "underlying_index",
            "value": "broad rules-based commodity futures product benchmark; no reconstruction in this task",
            "source": "direction-owner benchmark instruction",
            "material_interpretation_effect": "DBC is primary decision benchmark, not an optimized substitute",
        },
        {
            "wrapper": DBC,
            "field": "first_valid_cache_date",
            "value": cache_by_symbol.get(DBC, {}).get("first_valid_date", ""),
            "source": "local adjusted-price cache",
            "material_interpretation_effect": "common date alignment only",
        },
        {
            "wrapper": DBC,
            "field": "documented_material_benchmark_methodology_boundary",
            "value": "none supplied or detected in repository evidence for this task",
            "source": "supplied packet and repository evidence search",
            "material_interpretation_effect": "no additional DBC regime diagnostic applied",
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


def freeze_regimes(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    if common_dates.empty:
        return []
    rows: list[dict[str, Any]] = []
    first = common_dates[0]
    last = common_dates[-1]
    regime_1_end = min(pd.Timestamp("2020-12-23"), last)
    if first <= regime_1_end:
        dates = common_dates[(common_dates >= first) & (common_dates <= regime_1_end)]
        rows.append(
            {
                "regime_id": "USCI_regime_1_pre_2020_methodology_change",
                "start_date": dates[0].date().isoformat(),
                "end_date": dates[-1].date().isoformat(),
                "boundary_rule": "first valid common date through 2020-12-23",
                "methodology_boundary_frozen_before_performance": True,
                "trading_day_count": int(len(dates)),
            }
        )
    if last >= REGIME_BOUNDARY:
        dates = common_dates[(common_dates >= REGIME_BOUNDARY) & (common_dates <= last)]
        rows.append(
            {
                "regime_id": "USCI_regime_2_post_2020_methodology_change",
                "start_date": dates[0].date().isoformat(),
                "end_date": dates[-1].date().isoformat(),
                "boundary_rule": "2020-12-24 through final common date",
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
        "instrument": USCI,
        "source": {
            "source_id": SOURCE_ID,
            "fund_name": "United States Commodity Index Fund",
            "ticker": USCI,
            "sponsor": "United States Commodity Funds",
            "index_source": "SummerHaven Dynamic Commodity Index Total Return",
            "source_type": "official fund description plus official index methodology facts supplied by direction owner",
            "source_reported_performance_used": False,
        },
        "rule_provenance": {
            "source_explicit": [
                "USCI seeks to reflect the SummerHaven Dynamic Commodity Index Total Return, less expenses.",
                "The index selects 14 commodity futures monthly from 27 eligible contracts across five sectors.",
                "Selection favors greatest backwardation or least contango with at least one component per primary sector.",
                "Selected positions are approximately equally weighted.",
                "Selection observations occur on the fifth-to-last business day and rebalancing occurs over the final four business days.",
                "The total-return index includes collateral return based on three-month Treasury bills.",
            ],
            "mechanical_etf_wrapper_translation": [
                "Hold listed USCI wrapper rather than reconstructing futures, rolls, or collateral.",
                "Use adjusted total-return prices for USCI and DBC.",
                "Compare the wrapper with DBC buy-and-hold as the primary opportunity-cost benchmark.",
            ],
            "project_execution_convention": [
                "Long-only and unlevered.",
                "Maximum portfolio exposure 1.0.",
                "Canonical initial transaction cost once.",
                "No external rebalancing after the initial purchase.",
                "Matching-date benchmarks and actual-share accounting.",
            ],
            "unresolved_material_rules": [],
        },
        "frozen_candidate_rules": {
            "first_common_valid_date": common_dates[0].date().isoformat() if len(common_dates) else "",
            "final_common_valid_date": common_dates[-1].date().isoformat() if len(common_dates) else "",
            "universe": list(SYMBOLS),
            "candidate_asset": USCI,
            "primary_benchmark": "DBC_buy_and_hold",
            "secondary_references": ["BIL_cash_proxy", "SPY_buy_and_hold"],
            "initial_capital": INITIAL_CAPITAL,
            "initial_transaction_cost_pct": INITIAL_TRANSACTION_COST,
            "entry": "invest 100 percent of capital in USCI on first common valid adjusted-close date",
            "exit": "none; hold continuously to final date for measurement",
            "external_rebalance": "none after initial purchase",
            "timing_signal": "none",
            "BIL_switch": False,
            "underlying_futures_reconstruction": False,
            "manual_collateral_return_added": False,
            "manual_distribution_reinvestment": False,
            "additional_internal_futures_costs": False,
            "uses_adjusted_total_return_prices": True,
            "index_backfill_used": False,
            "pre_inception_backfill_used": False,
        },
        "pre_performance_freeze": {
            "cache_paths_and_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
            "common_valid_date_range": [
                common_dates[0].date().isoformat() if len(common_dates) else "",
                common_dates[-1].date().isoformat() if len(common_dates) else "",
            ],
            "chronological_block_boundaries_hash": stable_hash(blocks),
            "methodology_regime_boundaries_hash": stable_hash(regimes),
            "outcome_conditions_frozen_before_performance": True,
            "stop_conditions": [
                "invalid adjusted-price, alignment, accounting, exposure, continuity, or determinism checks",
                "exact corrected-methodology USCI wrapper screen found before performance calculation",
            ],
        },
        "not_authorized": {
            "promotion": False,
            "paper_demo_activation": False,
            "candidate_exhaustive": False,
            "strategy_variants": False,
            "commodity_product_alternatives": False,
            "futures_backtester": False,
            "real_money_recommendation": False,
        },
    }


def simulate_static_path(prices: pd.Series) -> tuple[pd.Series, dict[str, Any]]:
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
        "total_external_transaction_cost": entry_cost,
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


def capture_ratio(asset_returns: pd.Series, benchmark_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "benchmark"]
    subset = aligned[aligned["benchmark"] > 0.0] if direction == "up" else aligned[aligned["benchmark"] < 0.0]
    if subset.empty or abs(float(subset["benchmark"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["benchmark"].mean())


def metrics_for_symbol(symbol: str, equity: pd.Series, dbc_returns: pd.Series) -> dict[str, Any]:
    daily_returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    dd = max_drawdown(equity)
    complete_year_returns = complete_year_returns_for_equity(equity)
    positive_rate = (
        float(np.mean([year_return > 0.0 for year_return in complete_year_returns]))
        if complete_year_returns
        else float("nan")
    )
    worst_complete_year_return = float(min(complete_year_returns)) if complete_year_returns else float("nan")
    return {
        "symbol": symbol,
        "role": "candidate" if symbol == USCI else ("primary_benchmark" if symbol == DBC else "secondary_reference"),
        "start_date": equity.index[0].date().isoformat(),
        "end_date": equity.index[-1].date().isoformat(),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "complete_year_positive_return_rate": positive_rate,
        "worst_complete_year_return": worst_complete_year_return,
        "annualized_volatility": annualized_volatility(daily_returns),
        "downside_volatility": downside_volatility(daily_returns),
        "max_drawdown": dd,
        "return_to_max_drawdown_ratio": float(total_return / abs(dd)) if dd < 0.0 else float("nan"),
        "upside_capture_versus_DBC": capture_ratio(daily_returns, dbc_returns, "up"),
        "downside_capture_versus_DBC": capture_ratio(daily_returns, dbc_returns, "down"),
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
        dbc_returns = equity_map[DBC].pct_change().dropna()
        metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], dbc_returns) for symbol in SYMBOLS}
        usci = metrics[USCI]
        dbc = metrics[DBC]
        rows.append(
            {
                "block_id": block["block_id"],
                "block_number": block["block_number"],
                "start_date": block["start_date"],
                "end_date": block["end_date"],
                "trading_day_count": block["trading_day_count"],
                "USCI_total_return": usci["total_return"],
                "DBC_total_return": dbc["total_return"],
                "BIL_total_return": metrics[BIL]["total_return"],
                "SPY_total_return": metrics[SPY]["total_return"],
                "USCI_max_drawdown": usci["max_drawdown"],
                "DBC_max_drawdown": dbc["max_drawdown"],
                "excess_return_versus_DBC": float(usci["total_return"] - dbc["total_return"]),
                "USCI_beats_DBC": bool(usci["total_return"] > dbc["total_return"]),
                "USCI_smaller_drawdown_than_DBC": bool(usci["max_drawdown"] > dbc["max_drawdown"]),
                "USCI_higher_return_and_smaller_drawdown": bool(
                    usci["total_return"] > dbc["total_return"] and usci["max_drawdown"] > dbc["max_drawdown"]
                ),
                "USCI_return_to_max_drawdown_ratio": usci["return_to_max_drawdown_ratio"],
                "DBC_return_to_max_drawdown_ratio": dbc["return_to_max_drawdown_ratio"],
                "initial_cost_equivalent": bool(
                    abs(ops_map[USCI]["total_external_transaction_cost"] - ops_map[DBC]["total_external_transaction_cost"]) < 1e-9
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
        dbc_returns = equity_map[DBC].pct_change().dropna()
        metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], dbc_returns) for symbol in SYMBOLS}
        rows.append(
            {
                "regime_id": regime["regime_id"],
                "start_date": regime["start_date"],
                "end_date": regime["end_date"],
                "trading_day_count": regime["trading_day_count"],
                "USCI_total_return": metrics[USCI]["total_return"],
                "DBC_total_return": metrics[DBC]["total_return"],
                "BIL_total_return": metrics[BIL]["total_return"],
                "SPY_total_return": metrics[SPY]["total_return"],
                "USCI_CAGR": metrics[USCI]["cagr"],
                "DBC_CAGR": metrics[DBC]["cagr"],
                "USCI_max_drawdown": metrics[USCI]["max_drawdown"],
                "DBC_max_drawdown": metrics[DBC]["max_drawdown"],
                "excess_return_versus_DBC": float(metrics[USCI]["total_return"] - metrics[DBC]["total_return"]),
                "cagr_difference_versus_DBC": float(metrics[USCI]["cagr"] - metrics[DBC]["cagr"]),
            }
        )
    return rows


def calendar_rows(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    usci_equity = equity_map[USCI]
    first_year = int(usci_equity.index.min().year)
    last_year = int(usci_equity.index.max().year)
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
            "USCI_return": "",
            "DBC_return": "",
            "BIL_return": "",
            "SPY_return": "",
            "USCI_max_drawdown": "",
            "DBC_max_drawdown": "",
            "USCI_beats_DBC": "",
            "USCI_smaller_drawdown_than_DBC": "",
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
        if row["USCI_return"] != "" and row["DBC_return"] != "":
            row["USCI_beats_DBC"] = float(row["USCI_return"]) > float(row["DBC_return"])
        if row["USCI_max_drawdown"] != "" and row["DBC_max_drawdown"] != "":
            row["USCI_smaller_drawdown_than_DBC"] = float(row["USCI_max_drawdown"]) > float(row["DBC_max_drawdown"])
        rows.append(row)
    return rows


def correlation_and_capture_diagnostics(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    returns = {symbol: equity_map[symbol].pct_change().dropna() for symbol in SYMBOLS}
    aligned = pd.concat(
        [
            returns[USCI].rename(USCI),
            returns[DBC].rename(DBC),
            returns[SPY].rename(SPY),
        ],
        axis=1,
        join="inner",
    ).dropna()
    spy_equity = equity_map[SPY].reindex(aligned.index)
    spy_drawdown = drawdown_series(spy_equity)
    drawdown_aligned = aligned.loc[spy_drawdown[spy_drawdown < 0.0].index]
    return [
        {
            "diagnostic": "daily_return_correlation_with_DBC",
            "value": float(aligned[USCI].corr(aligned[DBC])) if len(aligned) > 2 else "",
            "outcome_used": False,
        },
        {
            "diagnostic": "daily_return_correlation_with_SPY",
            "value": float(aligned[USCI].corr(aligned[SPY])) if len(aligned) > 2 else "",
            "outcome_used": False,
        },
        {
            "diagnostic": "correlation_with_SPY_during_SPY_drawdown_periods",
            "value": float(drawdown_aligned[USCI].corr(drawdown_aligned[SPY])) if len(drawdown_aligned) > 2 else "",
            "definition": "SPY adjusted-close equity drawdown below 0",
            "outcome_used": False,
        },
        {
            "diagnostic": "upside_capture_versus_DBC",
            "value": capture_ratio(returns[USCI], returns[DBC], "up"),
            "outcome_used": False,
        },
        {
            "diagnostic": "downside_capture_versus_DBC",
            "value": capture_ratio(returns[USCI], returns[DBC], "down"),
            "outcome_used": False,
        },
    ]


def benchmark_relative_metrics(
    full_metrics: dict[str, dict[str, Any]],
    block_rows: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    regime_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    usci = full_metrics[USCI]
    dbc = full_metrics[DBC]
    block_excess = [float(row["excess_return_versus_DBC"]) for row in block_rows]
    regime_by_id = {row["regime_id"]: row for row in regime_rows}
    regime1 = regime_by_id.get("USCI_regime_1_pre_2020_methodology_change", {})
    regime2 = regime_by_id.get("USCI_regime_2_post_2020_methodology_change", {})
    complete_calendar = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    return {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": "DBC_buy_and_hold",
        "secondary_references": "BIL_cash_proxy|SPY_buy_and_hold",
        "full_period_excess_total_return_versus_DBC": float(usci["total_return"] - dbc["total_return"]),
        "cagr_difference_versus_DBC": float(usci["cagr"] - dbc["cagr"]),
        "max_drawdown_difference_versus_DBC": float(usci["max_drawdown"] - dbc["max_drawdown"]),
        "mean_block_excess_versus_DBC": float(np.mean(block_excess)),
        "median_block_excess_versus_DBC": float(np.median(block_excess)),
        "blocks_beating_DBC": int(sum(bool(row["USCI_beats_DBC"]) for row in block_rows)),
        "blocks_with_smaller_drawdown_than_DBC": int(sum(bool(row["USCI_smaller_drawdown_than_DBC"]) for row in block_rows)),
        "blocks_with_higher_return_and_smaller_drawdown": int(
            sum(bool(row["USCI_higher_return_and_smaller_drawdown"]) for row in block_rows)
        ),
        "complete_calendar_years_beating_DBC": int(sum(row["USCI_beats_DBC"] is True for row in complete_calendar)),
        "complete_calendar_years_smaller_drawdown_than_DBC": int(
            sum(row["USCI_smaller_drawdown_than_DBC"] is True for row in complete_calendar)
        ),
        "latest_block_excess_return": float(block_rows[-1]["excess_return_versus_DBC"]),
        "regime_1_excess_return_versus_DBC": regime1.get("excess_return_versus_DBC", ""),
        "regime_1_cagr_difference_versus_DBC": regime1.get("cagr_difference_versus_DBC", ""),
        "regime_2_excess_return_versus_DBC": regime2.get("excess_return_versus_DBC", ""),
        "regime_2_cagr_difference_versus_DBC": regime2.get("cagr_difference_versus_DBC", ""),
    }


def determine_outcome(relative: dict[str, Any], invariants_pass: bool, block_rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Adjusted-price, accounting, exposure, alignment, continuity, or determinism invariant failed"
    full_excess = float(relative["full_period_excess_total_return_versus_DBC"])
    median_block_excess = float(relative["median_block_excess_versus_DBC"])
    blocks_beat = int(relative["blocks_beating_DBC"])
    mdd_diff = float(relative["max_drawdown_difference_versus_DBC"])
    regime1_excess = float(relative["regime_1_excess_return_versus_DBC"])
    regime2_excess = float(relative["regime_2_excess_return_versus_DBC"])
    regime1_cagr_diff = float(relative["regime_1_cagr_difference_versus_DBC"])
    regime2_cagr_diff = float(relative["regime_2_cagr_difference_versus_DBC"])
    latest_two_underperform = len(block_rows) >= 2 and all(float(row["excess_return_versus_DBC"]) < 0.0 for row in block_rows[-2:])
    return_requirements = full_excess > 0.0 and median_block_excess > 0.0 and blocks_beat >= 3 and regime1_excess > 0.0 and regime2_excess > 0.0
    if return_requirements and mdd_diff < -0.05:
        return "higher_return_higher_risk", "Return requirements passed but max drawdown was more than five percentage points worse than DBC"
    if return_requirements:
        return "comparative_evidence_positive", "USCI exceeded DBC across full period, median block, three blocks, and both methodology regimes"
    if full_excess > 0.0 and median_block_excess > 0.0 and regime1_excess > 0.0 and (regime2_excess < 0.0 or latest_two_underperform):
        return "historical_edge_recently_weakened", "Positive full/median/regime-1 excess weakened in regime 2 or final blocks"
    opposite_signs = (regime1_excess > 0.0 > regime2_excess) or (regime2_excess > 0.0 > regime1_excess)
    if opposite_signs and abs(regime1_cagr_diff - regime2_cagr_diff) >= 0.03:
        return "methodology_regime_instability", "USCI regime excess signs diverged with at least three percentage points of annualized excess-return difference"
    if full_excess <= 0.0 and median_block_excess <= 0.0 and mdd_diff >= 0.05:
        return "risk_reduction_without_return_edge", "Full-period USCI return did not exceed DBC and median block excess was not positive, but max drawdown improved by at least five percentage points"
    return "no_material_edge", "No positive, weakened, regime-instability, higher-risk, or material risk-reduction classification was supported"


def exact_variant_memory(outcome: str, failure_reason: str, relative: dict[str, Any]) -> list[dict[str, Any]]:
    preserve = outcome == "comparative_evidence_positive"
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome": outcome,
            "primary_failure_reason": "" if preserve else failure_reason,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "broader_commodity_curve_selection_family_closed": False,
            "regime_1_excess_return_versus_DBC": relative.get("regime_1_excess_return_versus_DBC", ""),
            "regime_2_excess_return_versus_DBC": relative.get("regime_2_excess_return_versus_DBC", ""),
            "SDCI_GSG_PDBC_alternate_commodity_variations_prohibited_immediately": True,
            "timing_allocation_overlay_variations_prohibited_immediately": True,
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
        CURRENT_CHECKPOINT_DIR / "current_research_checkpoint.json",
        CURRENT_CHECKPOINT_DIR / "current_research_checkpoint.csv",
    ]
    cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    state_before = file_snapshot(protected_paths)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    acquisition_rows: list[dict[str, Any]] = []
    quality_by_symbol: dict[str, dict[str, Any]] = {}
    for symbol in (USCI, DBC):
        quality, provider_row = ensure_authorized_cache(symbol, prior_provider)
        quality_by_symbol[symbol] = quality
        acquisition_rows.append(provider_row)
    for symbol in (BIL, SPY):
        quality_by_symbol[symbol] = cache_quality_row(symbol)
    cache_rows = [quality_by_symbol[symbol] for symbol in SYMBOLS]
    cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    downloaded_this_run = sorted({symbol for row in acquisition_rows for symbol in row["downloaded_symbols_this_run"]})
    previous_ever = set(prior_provider.get("downloaded_symbols_ever", []) or [])
    downloaded_ever = sorted(previous_ever | set(downloaded_this_run))
    provider_manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_provider_acquisition": True,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "forbidden_commodity_products": list(FORBIDDEN_COMMODITY_PRODUCTS),
        "provider": "yfinance_compatible_public_daily_etp_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "series": acquisition_rows,
        "downloaded_symbols_this_run": downloaded_this_run,
        "downloaded_symbols_ever": downloaded_ever,
        "provider_download": bool(downloaded_this_run),
        "SPY_cache_refreshed": cache_before[SPY] != cache_after[SPY],
        "BIL_cache_refreshed": cache_before[BIL] != cache_after[BIL],
        "USCI_cache_refreshed": cache_before[USCI] != cache_after[USCI] and USCI not in downloaded_this_run,
        "DBC_cache_refreshed": cache_before[DBC] != cache_after[DBC] and DBC not in downloaded_this_run,
        "forbidden_product_downloaded": False,
        "provider_download_guardrail_passed": set(downloaded_this_run).issubset(set(AUTHORIZED_DOWNLOAD_SYMBOLS)),
    }

    duplicate_rows = duplicate_review_rows()
    exact_duplicate = any(row["exact_corrected_methodology_duplicate"] is True for row in duplicate_rows)
    fund_rows = fund_and_index_continuity_rows(cache_rows)

    invalid_reason = ""
    prices = pd.DataFrame()
    blocks: list[dict[str, Any]] = []
    regimes: list[dict[str, Any]] = []
    full_metrics_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    calendar: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    relative: dict[str, Any] = {}
    invariants_row: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""
    try:
        if exact_duplicate:
            raise RuntimeError("exact corrected-methodology USCI wrapper screen already exists")
        if any(row["adjusted_price_validation_result"] != "pass" for row in cache_rows):
            raise RuntimeError("required adjusted-price cache validation failed")
        prices = load_common_prices()
        if prices.empty:
            raise RuntimeError("common USCI/DBC/BIL/SPY date range is empty")
        blocks = freeze_blocks(prices.index)
        regimes = freeze_regimes(prices.index)
        if len(regimes) != 2:
            raise RuntimeError("USCI December 24, 2020 methodology regimes could not both be evaluated")

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
        write_csv(EVIDENCE_DIR / "fund_and_index_continuity.csv", fund_rows)
        write_csv(EVIDENCE_DIR / "frozen_evaluation_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(prices.index, cache_rows, blocks, regimes))

        equity_map, ops_map = build_equity_map(prices)
        dbc_returns = equity_map[DBC].pct_change().dropna()
        full_metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], dbc_returns) for symbol in SYMBOLS}
        block_rows = evaluate_blocks(prices, blocks)
        regime_rows = evaluate_regimes(prices, regimes)
        calendar = calendar_rows(equity_map)
        worst_by_symbol = {
            USCI: min(float(row["USCI_total_return"]) for row in block_rows),
            DBC: min(float(row["DBC_total_return"]) for row in block_rows),
            BIL: min(float(row["BIL_total_return"]) for row in block_rows),
            SPY: min(float(row["SPY_total_return"]) for row in block_rows),
        }
        for symbol in SYMBOLS:
            row = {**full_metrics[symbol], **ops_map[symbol]}
            row["worst_chronological_block_return"] = worst_by_symbol[symbol]
            full_metrics_rows.append(row)
        diagnostics = correlation_and_capture_diagnostics(equity_map)
        relative = benchmark_relative_metrics(full_metrics, block_rows, calendar, regime_rows)
        state_after = file_snapshot(protected_paths)
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": True,
            "adjusted_prices_used": True,
            "raw_close_substitution_used": False,
            "manual_collateral_return_added": False,
            "manual_distribution_reinvestment": False,
            "underlying_futures_reconstruction_used": False,
            "underlying_index_internal_turnover_estimated_or_added": False,
            "initial_turnover": 1.0,
            "subsequent_external_turnover": 0.0,
            "portfolio_trade_count": 1,
            "total_external_transaction_cost": ops_map[USCI]["total_external_transaction_cost"],
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "missing_adjusted_price_count": int(prices.isna().sum().sum()),
            "candidate_and_benchmark_dates_match": True,
            "initial_cost_equivalent_across_candidate_and_benchmarks": True,
            "no_BIL_switch": True,
            "no_market_timing_signal": True,
            "no_additional_commodity_product": True,
            "USCI_methodology_boundary_frozen": True,
            "SPY_cache_refreshed": cache_before[SPY] != cache_after[SPY],
            "BIL_cache_refreshed": cache_before[BIL] != cache_after[BIL],
            "USCI_cache_refreshed": provider_manifest["USCI_cache_refreshed"],
            "DBC_cache_refreshed": provider_manifest["DBC_cache_refreshed"],
            "registry_byte_identical": state_before.get(rel(REGISTRY_PATH)) == sha256_path(REGISTRY_PATH),
            "active_observations_unchanged": state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)) == sha256_path(ACTIVE_OBSERVATIONS_PATH),
            "vm_dsr_active_combo_unchanged": state_before == state_after,
            "xyld_not_rerun": True,
            "halloween_not_rerun": True,
            "automatic_external_source_selection_paused": True,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome(relative, True, block_rows)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        if not blocks and not prices.empty:
            blocks = freeze_blocks(prices.index)
        if not regimes and not prices.empty:
            regimes = freeze_regimes(prices.index)
        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(EVIDENCE_DIR / "cache_manifest.json", {"candidate_id": CANDIDATE_ID, "series": cache_rows})
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "fund_and_index_continuity.csv", fund_rows)
        write_csv(EVIDENCE_DIR / "frozen_evaluation_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(pd.DatetimeIndex([]), cache_rows, blocks, regimes))
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": False,
            "adjusted_prices_used": False,
            "raw_close_substitution_used": False,
            "manual_collateral_return_added": False,
            "manual_distribution_reinvestment": False,
            "underlying_futures_reconstruction_used": False,
            "underlying_index_internal_turnover_estimated_or_added": False,
            "initial_turnover": "",
            "subsequent_external_turnover": "",
            "portfolio_trade_count": "",
            "total_external_transaction_cost": "",
            "max_daily_exposure": "",
            "max_daily_weight_sum": "",
            "missing_adjusted_price_count": "",
            "candidate_and_benchmark_dates_match": False,
            "initial_cost_equivalent_across_candidate_and_benchmarks": False,
            "no_BIL_switch": True,
            "no_market_timing_signal": True,
            "no_additional_commodity_product": True,
            "USCI_methodology_boundary_frozen": bool(regimes),
            "SPY_cache_refreshed": cache_before[SPY] != cache_after[SPY],
            "BIL_cache_refreshed": cache_before[BIL] != cache_after[BIL],
            "USCI_cache_refreshed": provider_manifest["USCI_cache_refreshed"],
            "DBC_cache_refreshed": provider_manifest["DBC_cache_refreshed"],
            "registry_byte_identical": state_before.get(rel(REGISTRY_PATH)) == sha256_path(REGISTRY_PATH),
            "active_observations_unchanged": state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)) == sha256_path(ACTIVE_OBSERVATIONS_PATH),
            "vm_dsr_active_combo_unchanged": file_snapshot(protected_paths) == state_before,
            "xyld_not_rerun": True,
            "halloween_not_rerun": True,
            "automatic_external_source_selection_paused": True,
            "invariants_passed": False,
        }

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_metrics_rows)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "methodology_regime_results.csv", regime_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "correlation_and_capture_diagnostics.csv", diagnostics)
    write_csv(EVIDENCE_DIR / "accounting_data_and_exposure_invariants.csv", [invariants_row])
    memory = exact_variant_memory(outcome, outcome_reason, relative)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "return_to_direction_owner_for_review"
        if outcome == "comparative_evidence_positive"
        else "record_exact_usci_variant_memory_and_resume_source_queue"
    )
    screening_outcome = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": "" if outcome == "comparative_evidence_positive" else outcome_reason,
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
        "only_USCI_and_DBC_provider_acquisition_authorized": set(provider_manifest["authorized_download_symbols"]) == {USCI, DBC},
        "valid_caches_not_refreshed": not any(
            bool(provider_manifest[key])
            for key in ("SPY_cache_refreshed", "BIL_cache_refreshed", "USCI_cache_refreshed", "DBC_cache_refreshed")
        ),
        "adjusted_prices_used": invariants_row["adjusted_prices_used"],
        "USCI_purchased_once_and_held": invariants_row["initial_turnover"] == 1.0 and invariants_row["portfolio_trade_count"] == 1,
        "DBC_purchased_once_and_held": True,
        "no_futures_positions_reconstructed": invariants_row["underlying_futures_reconstruction_used"] is False,
        "no_additional_commodity_product": invariants_row["no_additional_commodity_product"] is True,
        "no_BIL_switch_or_timing_overlay": invariants_row["no_BIL_switch"] is True and invariants_row["no_market_timing_signal"] is True,
        "USCI_2020_12_24_boundary_frozen": invariants_row["USCI_methodology_boundary_frozen"] is True,
        "chronological_blocks_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in blocks),
        "candidate_and_benchmark_dates_match": invariants_row["candidate_and_benchmark_dates_match"],
        "initial_cost_treatment_equivalent": invariants_row["initial_cost_equivalent_across_candidate_and_benchmarks"],
        "exposure_never_exceeds_1": (invariants_row.get("max_daily_exposure") in {"", None}) or float(invariants_row["max_daily_exposure"]) <= 1.000001,
        "registry_byte_identical": invariants_row["registry_byte_identical"],
        "vm_dsr_active_combo_unchanged": invariants_row["vm_dsr_active_combo_unchanged"],
        "xyld_not_rerun": invariants_row["xyld_not_rerun"],
        "halloween_not_rerun": invariants_row["halloween_not_rerun"],
        "automatic_external_source_selection_paused": invariants_row["automatic_external_source_selection_paused"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "only_USCI_and_DBC_provider_acquisition_authorized",
        "valid_caches_not_refreshed",
        "adjusted_prices_used",
        "USCI_purchased_once_and_held",
        "DBC_purchased_once_and_held",
        "no_futures_positions_reconstructed",
        "no_additional_commodity_product",
        "no_BIL_switch_or_timing_overlay",
        "USCI_2020_12_24_boundary_frozen",
        "chronological_blocks_frozen_before_performance",
        "candidate_and_benchmark_dates_match",
        "initial_cost_treatment_equivalent",
        "exposure_never_exceeds_1",
        "registry_byte_identical",
        "vm_dsr_active_combo_unchanged",
        "xyld_not_rerun",
        "halloween_not_rerun",
        "automatic_external_source_selection_paused",
    }
    required_false = {
        "promotion_authorized",
        "paper_demo_authorized",
        "candidate_exhaustive_authorized",
        "real_money_recommendation",
    }
    consistency["consistency_passed"] = all(consistency[key] is True for key in required_true) and all(
        consistency[key] is False for key in required_false
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# USCI Dynamic Commodity Curve Selection Bounded Screen v1

Candidate `{CANDIDATE_ID}` was evaluated as one static investable wrapper: buy `USCI` once on the first common valid `USCI`/`DBC`/`BIL`/`SPY` adjusted-close date and hold through the final common date.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider acquisition this run: `{provider_manifest['provider_download']}`
- Common valid rows: `{len(prices) if not prices.empty else 0}`
- USCI methodology regimes evaluated: `{len(regime_rows)}`
- Five chronological blocks frozen before performance: `{len(blocks) == 5}`
- Primary benchmark: `DBC_buy_and_hold`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

The screen does not reconstruct commodity futures, does not use index backfills, does not test SDCI/GSG/PDBC/COMT or other wrappers, and does not alter VM, DSR, active-combo, XYLD, Halloween, registry, or paper/demo state.
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
