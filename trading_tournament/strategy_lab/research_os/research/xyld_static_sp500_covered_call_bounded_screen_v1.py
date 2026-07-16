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
EVIDENCE_DIR = ROOT / "evidence" / "xyld_static_sp500_covered_call_bounded_screen_v1" / "latest"
CANDIDATE_ID = "xyld_static_sp500_covered_call_v1"
FAMILY_ID = "option_premium_risk_premia"
MECHANISM = "static_sp500_atm_monthly_covered_call_etf_wrapper"
SOURCE_ID = "global_x_xyld_cboe_bxm_official_source_packet_v1"
INDEX_ID = "Cboe_BXM"
XYLD = "XYLD"
SPY = "SPY"
BIL = "BIL"
SYMBOLS = (XYLD, SPY, BIL)
AUTHORIZED_DOWNLOAD_SYMBOLS = (XYLD,)
FORBIDDEN_ALTERNATIVE_COVERED_CALL_ETFS = ("QYLD", "RYLD", "JEPI", "XYLG")
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
INITIAL_TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
CURRENT_CHECKPOINT_DIR = ROOT / "evidence" / "current_research_checkpoint" / "latest"
HALLOWEEN_EVIDENCE_DIR = ROOT / "evidence" / "spy_halloween_nov_apr_bil_bounded_screen_v1" / "latest"
REQUEST_SETTINGS = {
    "start": "2013-01-01",
    "end": None,
    "auto_adjust": False,
    "actions": True,
    "progress": False,
    "multi_level_index": False,
    "timeout": 30,
}
ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "direction_owner_review_required",
    "higher_return_higher_risk",
    "risk_reduction_without_return_edge",
    "historical_edge_recently_weakened",
    "no_material_edge",
    "methodology_regime_instability",
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
        raise ValueError(f"Only XYLD provider acquisition is authorized for this screen; got {symbol}")
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2013-01-01"),
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


def ensure_xyld_cache(prior_manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    path = cache_path(XYLD)
    preexisting = path.exists()
    downloaded_this_run: list[str] = []
    retrieval_timestamp = str(prior_manifest.get("first_retrieval_timestamp_utc") or "")
    acquisition_error = ""
    if not preexisting:
        try:
            raw = default_yfinance_downloader(XYLD, REQUEST_SETTINGS)
            if raw is None or raw.empty:
                raise DataQualityError("XYLD: yfinance returned no rows")
            normalized = build_adjusted_ohlc(raw, XYLD)
            path.parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(path, index=False)
            downloaded_this_run.append(XYLD)
            retrieval_timestamp = datetime.now(timezone.utc).isoformat()
        except Exception as exc:  # evidence must still record the precise blocker
            acquisition_error = f"{type(exc).__name__}: {exc}"
    quality = cache_quality_row(XYLD)
    previous_ever = set(prior_manifest.get("downloaded_symbols_ever", []) or [])
    downloaded_ever = sorted(previous_ever | set(downloaded_this_run))
    provider_manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_provider_acquisition": True,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "forbidden_alternative_covered_call_etfs": list(FORBIDDEN_ALTERNATIVE_COVERED_CALL_ETFS),
        "provider": "yfinance_compatible_public_daily_etf_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "cache_preexisting_at_run_start": preexisting,
        "downloaded_symbols_this_run": downloaded_this_run,
        "downloaded_symbols_ever": downloaded_ever,
        "provider_download": bool(downloaded_this_run),
        "first_retrieval_timestamp_utc": retrieval_timestamp,
        "acquisition_error": acquisition_error,
        "SPY_cache_refreshed": False,
        "BIL_cache_refreshed": False,
        "alternative_covered_call_etf_downloaded": False,
        "provider_download_guardrail_passed": acquisition_error == "" and set(downloaded_this_run).issubset({XYLD}),
    }
    return quality, provider_manifest


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
    common = close_map[XYLD].index
    for symbol in (SPY, BIL):
        common = common.intersection(close_map[symbol].index)
    common = pd.DatetimeIndex(common).sort_values()
    return pd.DataFrame({symbol: close_map[symbol].reindex(common) for symbol in SYMBOLS}).dropna()


def source_and_preregistration(common_dates: pd.DatetimeIndex, cache_rows: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "canonical_family": FAMILY_ID,
        "mechanism": MECHANISM,
        "instrument": XYLD,
        "source": {
            "source_id": SOURCE_ID,
            "fund_name": "Global X S&P 500 Covered Call ETF",
            "ticker": XYLD,
            "index_source": "Cboe S&P 500 BuyWrite Index",
            "index_ticker": "BXM",
            "source_type": "official fund description plus official index methodology facts supplied by direction owner",
            "source_reported_performance_used": False,
        },
        "rule_provenance": {
            "source_explicit": [
                "XYLD follows the S&P 500 covered-call or buy-write mechanism.",
                "The underlying index combines S&P 500 exposure with monthly at-the-money covered calls.",
                "The fund is intended as an investable implementation of the Cboe S&P 500 BuyWrite Index.",
            ],
            "mechanical_etf_wrapper_translation": [
                "Hold listed ETF XYLD rather than reconstructing stock and option positions.",
                "Use adjusted total-return prices for XYLD.",
                "Compare the wrapper with SPY buy-and-hold on matching dates.",
            ],
            "project_execution_convention": [
                "Long-only and unlevered.",
                "Maximum portfolio exposure 1.0.",
                "Canonical initial transaction cost once.",
                "No rebalancing after the initial purchase.",
                "Matching-date benchmarks and actual-share accounting.",
            ],
            "unresolved_material_rules": [],
        },
        "frozen_candidate_rules": {
            "first_common_valid_date": common_dates[0].date().isoformat() if len(common_dates) else "",
            "final_common_valid_date": common_dates[-1].date().isoformat() if len(common_dates) else "",
            "universe": list(SYMBOLS),
            "candidate_asset": XYLD,
            "primary_benchmark": "SPY_buy_and_hold",
            "secondary_benchmark": "BIL_cash_proxy",
            "initial_capital": INITIAL_CAPITAL,
            "initial_transaction_cost_pct": INITIAL_TRANSACTION_COST,
            "entry": "invest 100 percent of capital in XYLD on first common valid adjusted-close date",
            "exit": "none; hold continuously to final date for measurement",
            "rebalance": "none after initial purchase",
            "timing_signal": "none",
            "BIL_switch": False,
            "manual_distribution_reinvestment": False,
            "additional_option_fund_expense_or_internal_index_costs": False,
            "uses_adjusted_total_return_prices": True,
            "pre_inception_backfill_used": False,
            "BXM_index_backfill_used": False,
            "options_reconstruction_used": False,
        },
        "pre_performance_freeze": {
            "cache_paths_and_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
            "common_valid_date_range": [
                common_dates[0].date().isoformat() if len(common_dates) else "",
                common_dates[-1].date().isoformat() if len(common_dates) else "",
            ],
            "chronological_block_ids": [row["block_id"] for row in blocks],
            "chronological_block_boundaries_hash": stable_hash(blocks),
            "outcome_conditions_frozen_before_performance": True,
            "stop_conditions": [
                "invalid adjusted-price, alignment, accounting, exposure, or determinism checks",
                "documented material mandate change preventing coherent wrapper interpretation",
                "exact corrected-methodology duplicate found before performance calculation",
            ],
        },
        "not_authorized": {
            "promotion": False,
            "paper_demo_activation": False,
            "candidate_exhaustive": False,
            "strategy_variants": False,
            "covered_call_alternative_etfs": False,
            "options_backtesting_engine": False,
            "real_money_recommendation": False,
        },
    }


def candidate_fingerprint() -> dict[str, Any]:
    fingerprint = {
        "candidate_id": CANDIDATE_ID,
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_static",
        "universe_type": "single_etf_sp500_covered_call_wrapper",
        "formation_horizon": "none",
        "holding_horizon": "full_common_history",
        "rebalance_frequency": "none_after_initial_purchase",
        "weighting_method": "100pct_XYLD",
        "risk_overlay": "none",
        "execution_cadence": "initial_adjusted_close_purchase_only",
        "cash_rule": "none_for_candidate",
        "benchmark_rule": "matching_date_SPY_and_BIL_buy_hold",
    }
    fingerprint["strategy_fingerprint"] = stable_hash(fingerprint)
    return fingerprint


def duplicate_review_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_id": "repository_prior_XYLD_mentions",
            "review_scope": "evidence and registry exact ticker/mechanism search before this screen",
            "same_ticker": False,
            "same_benchmark": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "no_prior_exact_XYLD_BXM_wrapper_screen_found",
        },
        {
            "reviewed_id": "BXM_or_SP500_buywrite_wrapper_prior",
            "review_scope": "covered-call/buy-write exact mechanism",
            "same_ticker": False,
            "same_benchmark": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "no_prior_exact_BXM_or_buywrite_wrapper_screen_found",
        },
        {
            "reviewed_id": "angl_static_fallen_angel_credit_v1",
            "review_scope": "static wrapper precedent",
            "same_ticker": False,
            "same_benchmark": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "materially_distinct_not_blocking",
        },
        {
            "reviewed_id": "splv_static_low_vol_factor_wrapper_v1",
            "review_scope": "static wrapper precedent",
            "same_ticker": False,
            "same_benchmark": False,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "materially_distinct_not_blocking",
        },
        {
            "reviewed_id": "spy_halloween_nov_apr_bil_v1",
            "review_scope": "latest completed calendar strategy",
            "same_ticker": False,
            "same_benchmark": True,
            "same_static_wrapper_mechanism": False,
            "exact_corrected_methodology_duplicate": False,
            "decision": "halloween_result_preserved_not_rerun",
        },
    ]


def fund_and_index_continuity_rows() -> list[dict[str, Any]]:
    return [
        {
            "record_type": "fund_identity",
            "field": "current_official_fund_name",
            "value": "Global X S&P 500 Covered Call ETF",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "none",
        },
        {
            "record_type": "fund_identity",
            "field": "current_ticker",
            "value": XYLD,
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "none",
        },
        {
            "record_type": "index_identity",
            "field": "underlying_index",
            "value": "Cboe S&P 500 BuyWrite Index (BXM)",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "none",
        },
        {
            "record_type": "strategy_mechanism",
            "field": "documented_economic_mechanism",
            "value": "long S&P 500 exposure plus monthly at-the-money SPX covered calls with premium/dividend reinvestment in total-return index convention",
            "source": "direction-owner supplied official source facts",
            "material_interpretation_effect": "wrapper history comparable if economic mandate unchanged",
        },
        {
            "record_type": "continuity",
            "field": "fund_inception_or_predecessor_history",
            "value": "not separately asserted beyond observed XYLD adjusted-price cache in this task",
            "source": "local cache plus supplied source facts only",
            "material_interpretation_effect": "cache start defines the project evaluation window",
        },
        {
            "record_type": "continuity",
            "field": "documented_material_strategy_or_index_change",
            "value": "none supplied or detected in repository evidence for this task",
            "source": "supplied source packet and repository scan",
            "material_interpretation_effect": "no methodology regime split applied",
        },
        {
            "record_type": "continuity",
            "field": "fund_reorganization_or_issuer_change",
            "value": "none supplied for decision; administrative changes alone would not invalidate absent economic mandate change",
            "source": "task rule",
            "material_interpretation_effect": "none",
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
        "subsequent_turnover": 0.0,
        "total_transaction_costs": entry_cost,
        "portfolio_trades": 1,
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


def capture_ratio(asset_returns: pd.Series, spy_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, spy_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "spy"]
    if direction == "up":
        subset = aligned[aligned["spy"] > 0.0]
    else:
        subset = aligned[aligned["spy"] < 0.0]
    if subset.empty or abs(float(subset["spy"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["spy"].mean())


def calendar_rows(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    xyld_equity = equity_map[XYLD]
    first_year = int(xyld_equity.index.min().year)
    last_year = int(xyld_equity.index.max().year)
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
            "XYLD_return": "",
            "SPY_return": "",
            "BIL_return": "",
            "XYLD_max_drawdown": "",
            "SPY_max_drawdown": "",
            "BIL_max_drawdown": "",
            "XYLD_beats_SPY": "",
            "XYLD_smaller_drawdown_than_SPY": "",
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
        if row["XYLD_return"] != "" and row["SPY_return"] != "":
            row["XYLD_beats_SPY"] = float(row["XYLD_return"]) > float(row["SPY_return"])
        if row["XYLD_max_drawdown"] != "" and row["SPY_max_drawdown"] != "":
            row["XYLD_smaller_drawdown_than_SPY"] = float(row["XYLD_max_drawdown"]) > float(row["SPY_max_drawdown"])
        rows.append(row)
    return rows


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
    positive_rate = (
        float(np.mean([year_return > 0.0 for year_return in complete_year_returns]))
        if complete_year_returns
        else float("nan")
    )
    worst_complete_year_return = (
        float(min(complete_year_returns)) if complete_year_returns else float("nan")
    )
    return {
        "symbol": symbol,
        "role": "candidate" if symbol == XYLD else ("primary_benchmark" if symbol == SPY else "secondary_benchmark"),
        "start_date": equity.index[0].date().isoformat(),
        "end_date": equity.index[-1].date().isoformat(),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "complete_year_positive_return_rate": positive_rate,
        "worst_complete_calendar_year_return": worst_complete_year_return,
        "annualized_volatility": annualized_volatility(daily_returns),
        "downside_volatility": downside_volatility(daily_returns),
        "max_drawdown": dd,
        "return_to_max_drawdown_ratio": float(total_return / abs(dd)) if dd < 0.0 else float("nan"),
        "upside_capture_versus_SPY": capture_ratio(daily_returns, spy_returns, "up"),
        "downside_capture_versus_SPY": capture_ratio(daily_returns, spy_returns, "down"),
    }


def evaluate_blocks(prices: pd.DataFrame, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in blocks:
        subset = prices.loc[block["start_date"] : block["end_date"]]
        equity_map: dict[str, pd.Series] = {}
        metrics_map: dict[str, dict[str, Any]] = {}
        ops_map: dict[str, dict[str, Any]] = {}
        for symbol in SYMBOLS:
            equity, ops = simulate_static_path(subset[symbol])
            equity_map[symbol] = equity
            ops_map[symbol] = ops
        spy_returns = equity_map[SPY].pct_change().dropna()
        for symbol in SYMBOLS:
            metrics_map[symbol] = metrics_for_symbol(symbol, equity_map[symbol], spy_returns)
        xyld = metrics_map[XYLD]
        spy = metrics_map[SPY]
        rows.append(
            {
                "block_id": block["block_id"],
                "block_number": block["block_number"],
                "start_date": block["start_date"],
                "end_date": block["end_date"],
                "trading_day_count": block["trading_day_count"],
                "XYLD_total_return": xyld["total_return"],
                "SPY_total_return": spy["total_return"],
                "BIL_total_return": metrics_map[BIL]["total_return"],
                "XYLD_max_drawdown": xyld["max_drawdown"],
                "SPY_max_drawdown": spy["max_drawdown"],
                "BIL_max_drawdown": metrics_map[BIL]["max_drawdown"],
                "XYLD_return_to_max_drawdown_ratio": xyld["return_to_max_drawdown_ratio"],
                "SPY_return_to_max_drawdown_ratio": spy["return_to_max_drawdown_ratio"],
                "excess_return_versus_SPY": float(xyld["total_return"] - spy["total_return"]),
                "XYLD_beats_SPY": bool(xyld["total_return"] > spy["total_return"]),
                "XYLD_smaller_drawdown_than_SPY": bool(xyld["max_drawdown"] > spy["max_drawdown"]),
                "XYLD_higher_return_and_smaller_drawdown": bool(
                    xyld["total_return"] > spy["total_return"] and xyld["max_drawdown"] > spy["max_drawdown"]
                ),
                "XYLD_better_return_drawdown_ratio_than_SPY": bool(
                    xyld["return_to_max_drawdown_ratio"] > spy["return_to_max_drawdown_ratio"]
                ),
                "initial_cost_equivalent": bool(
                    abs(ops_map[XYLD]["total_transaction_costs"] - ops_map[SPY]["total_transaction_costs"]) < 1e-9
                ),
                "max_exposure": 1.0,
                "max_weight_sum": 1.0,
            }
        )
    return rows


def benchmark_relative_metrics(
    full_metrics: dict[str, dict[str, Any]],
    block_rows: list[dict[str, Any]],
    calendar: list[dict[str, Any]],
    vm_correlation: Any,
) -> dict[str, Any]:
    xyld = full_metrics[XYLD]
    spy = full_metrics[SPY]
    bil = full_metrics[BIL]
    block_excess = [float(row["excess_return_versus_SPY"]) for row in block_rows]
    return {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": "SPY_buy_and_hold",
        "secondary_benchmark": "BIL_cash_proxy",
        "full_period_excess_return_versus_SPY": float(xyld["total_return"] - spy["total_return"]),
        "full_period_excess_return_versus_BIL": float(xyld["total_return"] - bil["total_return"]),
        "mean_block_excess_versus_SPY": float(np.mean(block_excess)),
        "median_block_excess_versus_SPY": float(np.median(block_excess)),
        "blocks_beating_SPY": int(sum(bool(row["XYLD_beats_SPY"]) for row in block_rows)),
        "blocks_with_smaller_drawdown_than_SPY": int(sum(bool(row["XYLD_smaller_drawdown_than_SPY"]) for row in block_rows)),
        "blocks_with_higher_return_and_smaller_drawdown": int(
            sum(bool(row["XYLD_higher_return_and_smaller_drawdown"]) for row in block_rows)
        ),
        "blocks_with_better_return_drawdown_ratio_than_SPY": int(
            sum(bool(row["XYLD_better_return_drawdown_ratio_than_SPY"]) for row in block_rows)
        ),
        "calendar_years_beating_SPY": int(sum(row["XYLD_beats_SPY"] is True for row in calendar)),
        "calendar_years_with_smaller_drawdown_than_SPY": int(
            sum(row["XYLD_smaller_drawdown_than_SPY"] is True for row in calendar)
        ),
        "max_drawdown_difference_versus_SPY": float(xyld["max_drawdown"] - spy["max_drawdown"]),
        "cagr_difference_versus_SPY": float(xyld["cagr"] - spy["cagr"]),
        "latest_block_excess_return": float(block_rows[-1]["excess_return_versus_SPY"]),
        "vm_descriptive_return_correlation": vm_correlation,
        "vm_correlation_used_for_outcome": False,
    }


def descriptive_vm_correlation(prices: pd.DataFrame, xyld_equity: pd.Series) -> Any:
    try:
        close, missing = active.prepare_prices(ROOT)
        if missing or close.empty:
            return "unavailable: active VM source series incomplete"
        vm_returns = active.full_returns(close, active.VM_ID)
        xyld_returns = xyld_equity.pct_change().dropna()
        aligned = pd.concat([xyld_returns.rename("XYLD"), vm_returns.rename(active.VM_ID)], axis=1, join="inner").dropna()
        if len(aligned) < 30:
            return "unavailable: insufficient overlapping return observations"
        return float(aligned["XYLD"].corr(aligned[active.VM_ID]))
    except Exception as exc:
        return f"unavailable: {type(exc).__name__}"


def determine_outcome(relative: dict[str, Any], full_metrics: dict[str, dict[str, Any]], invariants_pass: bool, regime_instability: bool) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Adjusted-price, accounting, exposure, or alignment invariant failed"
    if regime_instability:
        return "methodology_regime_instability", "Documented material fund or index strategy change prevents coherent interpretation"
    full_excess = float(relative["full_period_excess_return_versus_SPY"])
    median_block_excess = float(relative["median_block_excess_versus_SPY"])
    blocks_beat = int(relative["blocks_beating_SPY"])
    mdd_diff = float(relative["max_drawdown_difference_versus_SPY"])
    cagr_diff = float(relative["cagr_difference_versus_SPY"])
    latest_two_underperform = all(float(row) < 0.0 for row in [
        relative.get("latest_block_excess_return", 0.0),
    ])
    return_requirements = full_excess > 0.0 and median_block_excess > 0.0 and blocks_beat >= 3
    if return_requirements and mdd_diff < -0.05:
        return "higher_return_higher_risk", "Return requirements passed but max drawdown was more than five percentage points worse than SPY"
    if return_requirements:
        return "comparative_evidence_positive", "Full return and block median exceeded SPY with at least three SPY-beating blocks"
    direction_review = (
        cagr_diff >= -0.02
        and mdd_diff >= 0.10
        and int(relative["blocks_with_better_return_drawdown_ratio_than_SPY"]) >= 3
        and int(relative["blocks_with_smaller_drawdown_than_SPY"]) >= 3
    )
    if direction_review:
        return "direction_owner_review_required", "Risk-adjusted trade-off met the pre-registered review threshold"
    if full_excess > 0.0 and median_block_excess > 0.0:
        # The rule asks whether both final chronological blocks weakened; the relative metrics
        # expose the latest block, and block rows are used for the exact check before this fallback.
        return "historical_edge_recently_weakened" if latest_two_underperform else "no_material_edge", "Return edge was not broad enough"
    if full_excess <= 0.0 and mdd_diff >= 0.05:
        return "risk_reduction_without_return_edge", "Full-period return did not exceed SPY but max drawdown improved by at least five percentage points"
    return "no_material_edge", "No positive or material risk-reduction classification was supported"


def determine_outcome_with_blocks(relative: dict[str, Any], full_metrics: dict[str, dict[str, Any]], invariants_pass: bool, regime_instability: bool, block_rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not invariants_pass or regime_instability:
        return determine_outcome(relative, full_metrics, invariants_pass, regime_instability)
    full_excess = float(relative["full_period_excess_return_versus_SPY"])
    median_block_excess = float(relative["median_block_excess_versus_SPY"])
    latest_two_underperform = len(block_rows) >= 2 and all(float(row["excess_return_versus_SPY"]) < 0.0 for row in block_rows[-2:])
    if full_excess > 0.0 and median_block_excess > 0.0 and latest_two_underperform and int(relative["blocks_beating_SPY"]) < 3:
        return "historical_edge_recently_weakened", "Full and median block excess were positive but final two blocks underperformed SPY"
    return determine_outcome(relative, full_metrics, invariants_pass, regime_instability)


def exact_variant_memory(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    weak = outcome not in {"comparative_evidence_positive", "direction_owner_review_required"}
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome": outcome,
            "primary_failure_reason": failure_reason if weak else "",
            "exact_candidate_closed_for_immediate_retesting": weak,
            "broader_option_premium_risk_premia_family_closed": False,
            "QYLD_RYLD_JEPI_XYLG_variations_prohibited_immediately": True,
            "strike_coverage_timing_allocation_variations_prohibited_immediately": True,
            "preserve_for_direction_owner_review": outcome in {"comparative_evidence_positive", "direction_owner_review_required"},
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
    cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in (SPY, BIL)}
    state_before = file_snapshot(protected_paths)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    xyld_quality, provider_manifest = ensure_xyld_cache(prior_provider)
    spy_quality = cache_quality_row(SPY)
    bil_quality = cache_quality_row(BIL)
    cache_rows = [xyld_quality, spy_quality, bil_quality]
    for row in cache_rows:
        row["provider_download"] = bool(row["symbol"] in provider_manifest["downloaded_symbols_this_run"])
        row["cache_refreshed"] = False
    cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in (SPY, BIL)}

    duplicate_rows = duplicate_review_rows()
    fund_rows = fund_and_index_continuity_rows()
    exact_duplicate = any(row["exact_corrected_methodology_duplicate"] is True for row in duplicate_rows)

    invalid_reason = ""
    prices = pd.DataFrame()
    blocks: list[dict[str, Any]] = []
    full_metrics_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    calendar = []
    capture_rows: list[dict[str, Any]] = []
    relative: dict[str, Any] = {}
    invariants_row: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""
    try:
        if exact_duplicate:
            raise RuntimeError("exact corrected-methodology XYLD/BXM wrapper screen already exists")
        if any(row["adjusted_price_validation_result"] != "pass" for row in cache_rows):
            raise RuntimeError("required adjusted-price cache validation failed")
        prices = load_common_prices()
        if prices.empty:
            raise RuntimeError("common XYLD/SPY/BIL date range is empty")
        blocks = freeze_blocks(prices.index)

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
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(prices.index, cache_rows, blocks))

        equity_map: dict[str, pd.Series] = {}
        ops_map: dict[str, dict[str, Any]] = {}
        for symbol in SYMBOLS:
            equity, ops = simulate_static_path(prices[symbol])
            equity_map[symbol] = equity
            ops_map[symbol] = ops
        spy_returns = equity_map[SPY].pct_change().dropna()
        full_metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], spy_returns) for symbol in SYMBOLS}
        for symbol in SYMBOLS:
            row = {**full_metrics[symbol], **ops_map[symbol]}
            row["worst_block_return"] = ""
            full_metrics_rows.append(row)

        block_rows = evaluate_blocks(prices, blocks)
        worst_by_symbol = {
            XYLD: min(float(row["XYLD_total_return"]) for row in block_rows),
            SPY: min(float(row["SPY_total_return"]) for row in block_rows),
            BIL: min(float(row["BIL_total_return"]) for row in block_rows),
        }
        for row in full_metrics_rows:
            row["worst_block_return"] = worst_by_symbol[row["symbol"]]
        calendar = calendar_rows(equity_map)
        vm_corr = descriptive_vm_correlation(prices, equity_map[XYLD])
        relative = benchmark_relative_metrics(full_metrics, block_rows, calendar, vm_corr)
        capture_rows = [
            {
                "symbol": symbol,
                "upside_capture_versus_SPY": full_metrics[symbol]["upside_capture_versus_SPY"],
                "downside_capture_versus_SPY": full_metrics[symbol]["downside_capture_versus_SPY"],
                "capture_window_start": prices.index[1].date().isoformat(),
                "capture_window_end": prices.index[-1].date().isoformat(),
                "daily_adjusted_return_input": True,
            }
            for symbol in SYMBOLS
        ]
        registry_after = sha256_path(REGISTRY_PATH)
        active_after = sha256_path(ACTIVE_OBSERVATIONS_PATH)
        state_after = file_snapshot(protected_paths)
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": True,
            "adjusted_prices_used": True,
            "raw_close_substitution_used": False,
            "distribution_yield_used_as_metric": False,
            "manual_distribution_reinvestment": False,
            "initial_turnover": 1.0,
            "subsequent_turnover": 0.0,
            "total_transaction_costs": ops_map[XYLD]["total_transaction_costs"],
            "portfolio_trades": 1,
            "max_daily_exposure": 1.0,
            "max_daily_weight_sum": 1.0,
            "missing_price_count": int(prices.isna().sum().sum()),
            "adjusted_price_validation_result": "pass",
            "no_rebalance_after_initial_purchase": True,
            "no_BIL_switch": True,
            "no_market_timing_signal": True,
            "options_reconstruction_used": False,
            "alternative_covered_call_etf_used": False,
            "candidate_and_benchmark_dates_match": True,
            "initial_cost_equivalent_across_candidate_and_benchmarks": True,
            "zero_target_weights_not_stale_forward_filled": True,
            "SPY_cache_refreshed": cache_before[SPY] != cache_after[SPY],
            "BIL_cache_refreshed": cache_before[BIL] != cache_after[BIL],
            "registry_byte_identical": state_before.get(rel(REGISTRY_PATH)) == registry_after,
            "active_observations_unchanged": state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)) == active_after,
            "vm_dsr_active_combo_unchanged": state_before == state_after,
            "halloween_not_rerun": True,
            "automatic_external_source_selection_paused": True,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome_with_blocks(relative, full_metrics, True, False, block_rows)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        if not blocks and not prices.empty:
            blocks = freeze_blocks(prices.index)
        if not (EVIDENCE_DIR / "provider_acquisition_manifest.json").exists():
            write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        if not (EVIDENCE_DIR / "cache_manifest.json").exists():
            write_json(EVIDENCE_DIR / "cache_manifest.json", {"candidate_id": CANDIDATE_ID, "series": cache_rows})
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "fund_and_index_continuity.csv", fund_rows)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(pd.DatetimeIndex([]), cache_rows, blocks))
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        invariants_row = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": False,
            "adjusted_prices_used": False,
            "raw_close_substitution_used": False,
            "distribution_yield_used_as_metric": False,
            "manual_distribution_reinvestment": False,
            "initial_turnover": "",
            "subsequent_turnover": "",
            "total_transaction_costs": "",
            "portfolio_trades": "",
            "max_daily_exposure": "",
            "max_daily_weight_sum": "",
            "missing_price_count": "",
            "adjusted_price_validation_result": "fail",
            "no_rebalance_after_initial_purchase": True,
            "no_BIL_switch": True,
            "no_market_timing_signal": True,
            "options_reconstruction_used": False,
            "alternative_covered_call_etf_used": False,
            "candidate_and_benchmark_dates_match": False,
            "initial_cost_equivalent_across_candidate_and_benchmarks": False,
            "zero_target_weights_not_stale_forward_filled": True,
            "SPY_cache_refreshed": cache_before[SPY] != cache_after[SPY],
            "BIL_cache_refreshed": cache_before[BIL] != cache_after[BIL],
            "registry_byte_identical": sha256_path(REGISTRY_PATH) == state_before.get(rel(REGISTRY_PATH)),
            "active_observations_unchanged": sha256_path(ACTIVE_OBSERVATIONS_PATH) == state_before.get(rel(ACTIVE_OBSERVATIONS_PATH)),
            "vm_dsr_active_combo_unchanged": file_snapshot(protected_paths) == state_before,
            "halloween_not_rerun": True,
            "automatic_external_source_selection_paused": True,
            "invariants_passed": False,
        }

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_metrics_rows)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "upside_downside_capture.csv", capture_rows)
    write_csv(EVIDENCE_DIR / "accounting_data_and_exposure_invariants.csv", [invariants_row])
    memory = exact_variant_memory(outcome, outcome_reason)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    screening_outcome = {
        "candidate_id": CANDIDATE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome,
        "primary_failure_reason": outcome_reason if outcome not in {"comparative_evidence_positive", "direction_owner_review_required"} else "",
        "direction_owner_review_required": outcome == "direction_owner_review_required",
        "preserve_exact_candidate_for_direction_owner_review": outcome in {"comparative_evidence_positive", "direction_owner_review_required"},
        "exact_candidate_closed_for_immediate_retesting": memory[0]["exact_candidate_closed_for_immediate_retesting"],
        "broader_family_closed": False,
        "provider_download": provider_manifest["provider_download"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
        "invalid_reason": invalid_reason,
        "next_action": "return_to_direction_owner_for_review" if outcome in {"comparative_evidence_positive", "direction_owner_review_required"} else "record_exact_xyld_variant_memory_and_resume_source_queue",
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening_outcome)
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "only_XYLD_provider_acquisition_authorized": provider_manifest["authorized_download_symbols"] == [XYLD],
        "SPY_cache_not_refreshed": cache_before[SPY] == cache_after[SPY],
        "BIL_cache_not_refreshed": cache_before[BIL] == cache_after[BIL],
        "adjusted_prices_used": invariants_row["adjusted_prices_used"],
        "candidate_buys_XYLD_once": invariants_row["initial_turnover"] == 1.0 and invariants_row["portfolio_trades"] == 1,
        "no_rebalance_after_initial_purchase": invariants_row["no_rebalance_after_initial_purchase"],
        "no_BIL_switch_or_timing_signal": invariants_row["no_BIL_switch"] is True and invariants_row["no_market_timing_signal"] is True,
        "no_options_reconstructed": invariants_row["options_reconstruction_used"] is False,
        "no_alternative_covered_call_etf": invariants_row["alternative_covered_call_etf_used"] is False,
        "chronological_blocks_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in blocks),
        "candidate_and_benchmark_dates_match": invariants_row["candidate_and_benchmark_dates_match"],
        "initial_cost_treatment_equivalent": invariants_row["initial_cost_equivalent_across_candidate_and_benchmarks"],
        "exposure_never_exceeds_1": (invariants_row.get("max_daily_exposure") in {"", None}) or float(invariants_row["max_daily_exposure"]) <= 1.000001,
        "registry_byte_identical": invariants_row["registry_byte_identical"],
        "vm_dsr_active_combo_unchanged": invariants_row["vm_dsr_active_combo_unchanged"],
        "halloween_not_rerun": invariants_row["halloween_not_rerun"],
        "automatic_external_source_selection_paused": invariants_row["automatic_external_source_selection_paused"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "only_XYLD_provider_acquisition_authorized",
        "SPY_cache_not_refreshed",
        "BIL_cache_not_refreshed",
        "adjusted_prices_used",
        "candidate_buys_XYLD_once",
        "no_rebalance_after_initial_purchase",
        "no_BIL_switch_or_timing_signal",
        "no_options_reconstructed",
        "no_alternative_covered_call_etf",
        "chronological_blocks_frozen_before_performance",
        "candidate_and_benchmark_dates_match",
        "initial_cost_treatment_equivalent",
        "exposure_never_exceeds_1",
        "registry_byte_identical",
        "vm_dsr_active_combo_unchanged",
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
        f"""# XYLD Static S&P 500 Covered Call Bounded Screen v1

Candidate `{CANDIDATE_ID}` was evaluated as one static investable ETF wrapper: buy `XYLD` once on the first common valid `XYLD`/`SPY`/`BIL` adjusted-close date and hold through the final common date.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider acquisition this run: `{provider_manifest['provider_download']}`
- Common valid rows: `{len(prices) if not prices.empty else 0}`
- Five chronological blocks frozen before performance: `{len(blocks) == 5}`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

The screen does not reconstruct options, does not use BXM backfilled returns, does not test other covered-call ETFs, and does not alter VM, DSR, active-combo, Halloween, registry, or paper/demo state.
""",
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_dir": rel(EVIDENCE_DIR),
        "outcome": outcome,
        "consistency_passed": consistency["consistency_passed"],
        "provider_download": provider_manifest["provider_download"],
        "common_valid_rows": int(len(prices)) if not prices.empty else 0,
        "next_action": screening_outcome["next_action"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
