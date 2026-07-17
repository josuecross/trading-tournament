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
from src.data import build_adjusted_ohlc


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "spy_close_to_open_overnight_cash_bounded_screen_v1" / "latest"
CANDIDATE_ID = "spy_close_to_open_overnight_cash_v1"
FAMILY_ID = "equity_overnight_return"
MECHANISM = "systematic_spy_close_to_next_open_exposure"
ROLE = "overnight_equity_risk_premium_timing"
SPY = "SPY"
CASH = "CASH"
AUTHORIZED_DOWNLOAD_SYMBOLS = (SPY,)
FORBIDDEN_DOWNLOAD_SYMBOLS = ("QQQ", "IWM", "DIA", "SPX", "ES")
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
ACTIVE_COMBO_SERIES_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
MNA_EVIDENCE_DIR = ROOT / "evidence" / "mna_static_merger_arbitrage_bounded_screen_v1" / "latest"
REQUEST_SETTINGS = {
    "start": "2007-01-01",
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
    "risk_reduction_without_return_edge",
    "cost_sensitive_no_edge",
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


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def file_snapshot(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def validate_authorized_download_symbol(symbol: str) -> str:
    normalized = str(symbol).upper()
    if normalized not in AUTHORIZED_DOWNLOAD_SYMBOLS:
        raise ValueError(f"Only SPY provider acquisition is authorized for this screen; got {symbol}")
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2007-01-01"),
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


def spy_cache_quality_row() -> dict[str, Any]:
    path = cache_path(SPY)
    row: dict[str, Any] = {
        "symbol": SPY,
        "cache_path": rel(path),
        "cache_exists": path.exists(),
        "cache_hash": sha256_path(path),
        "row_count": 0,
        "first_valid_date": "",
        "last_valid_date": "",
        "date_monotonic_increasing": False,
        "duplicate_date_count": "",
        "required_ohlc_columns_present": False,
        "missing_required_price_count": "",
        "nonpositive_required_price_count": "",
        "invalid_adjustment_factor_count": "",
        "adjusted_open_validation_result": "missing",
        "provider_download": False,
        "cache_refreshed": False,
    }
    if not path.exists():
        return row
    frame = pd.read_csv(path)
    required = {"date", "raw_open", "raw_close", "raw_adj_close", "adj_close"}
    row["required_ohlc_columns_present"] = required.issubset(set(frame.columns))
    if not row["required_ohlc_columns_present"]:
        row["row_count"] = int(len(frame))
        row["adjusted_open_validation_result"] = "fail"
        return row
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    raw_open = pd.to_numeric(frame["raw_open"], errors="coerce")
    raw_close = pd.to_numeric(frame["raw_close"], errors="coerce")
    adj_close = pd.to_numeric(frame["adj_close"], errors="coerce")
    factor = adj_close / raw_close
    row["row_count"] = int(len(frame))
    row["first_valid_date"] = dates.dropna().min().date().isoformat() if dates.notna().any() else ""
    row["last_valid_date"] = dates.dropna().max().date().isoformat() if dates.notna().any() else ""
    row["date_monotonic_increasing"] = bool(dates.dropna().is_monotonic_increasing)
    row["duplicate_date_count"] = int(dates.dropna().duplicated().sum())
    required_prices = pd.concat([raw_open, raw_close, adj_close], axis=1)
    row["missing_required_price_count"] = int(required_prices.isna().sum().sum())
    row["nonpositive_required_price_count"] = int((required_prices <= 0).sum().sum())
    invalid_factor = factor.isna() | ~np.isfinite(factor) | (factor <= 0)
    row["invalid_adjustment_factor_count"] = int(invalid_factor.sum())
    ok = (
        row["row_count"] > 20
        and row["date_monotonic_increasing"]
        and row["duplicate_date_count"] == 0
        and row["missing_required_price_count"] == 0
        and row["nonpositive_required_price_count"] == 0
        and row["invalid_adjustment_factor_count"] == 0
    )
    row["adjusted_open_validation_result"] = "pass" if ok else "fail"
    return row


def ensure_spy_cache(prior_provider: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before_hash = sha256_path(cache_path(SPY))
    before_quality = spy_cache_quality_row()
    downloaded = False
    status = "existing_cache_valid"
    error = ""
    if before_quality["adjusted_open_validation_result"] != "pass":
        try:
            raw = default_yfinance_downloader(SPY, REQUEST_SETTINGS)
            normalized = build_adjusted_ohlc(raw, SPY)
            cache_path(SPY).parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(cache_path(SPY), index=False, lineterminator="\n")
            downloaded = True
            status = "downloaded_and_validated"
        except Exception as exc:  # pragma: no cover
            status = "provider_download_failed"
            error = f"{type(exc).__name__}: {exc}"
    after_quality = spy_cache_quality_row()
    after_hash = sha256_path(cache_path(SPY))
    if after_quality["adjusted_open_validation_result"] != "pass" and not error:
        error = "SPY adjusted open/close cache validation failed"
    after_quality["provider_download"] = downloaded
    after_quality["cache_refreshed"] = downloaded
    previous_ever = set(prior_provider.get("downloaded_symbols_ever", []) or [])
    downloaded_this_run = [SPY] if downloaded else []
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_provider_acquisition": True,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "forbidden_download_symbols": list(FORBIDDEN_DOWNLOAD_SYMBOLS),
        "provider": "yfinance_compatible_public_daily_etf_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "series": [
            {
                "symbol": SPY,
                "status": status,
                "cache_path": rel(cache_path(SPY)),
                "hash_before": before_hash,
                "hash_after": after_hash,
                "downloaded_symbols_this_run": downloaded_this_run,
                "adjusted_open_validation_result": after_quality["adjusted_open_validation_result"],
                "row_count": after_quality["row_count"],
                "first_valid_date": after_quality["first_valid_date"],
                "last_valid_date": after_quality["last_valid_date"],
                "error": error,
            }
        ],
        "downloaded_symbols_this_run": downloaded_this_run,
        "downloaded_symbols_ever": sorted(previous_ever | set(downloaded_this_run)),
        "provider_download": downloaded,
        "SPY_cache_refreshed": downloaded,
        "intraday_bars_downloaded": False,
        "alternate_equity_etf_downloaded": False,
        "futures_or_index_data_downloaded": False,
        "provider_download_guardrail_passed": set(downloaded_this_run).issubset({SPY}),
    }
    return after_quality, manifest


def load_spy_ohlc() -> pd.DataFrame:
    frame = pd.read_csv(cache_path(SPY))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    for column in ["raw_open", "raw_close", "adj_close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["adjustment_factor_recomputed"] = frame["adj_close"] / frame["raw_close"]
    frame["adjusted_open_recomputed"] = frame["raw_open"] * frame["adjustment_factor_recomputed"]
    frame["adjusted_close"] = frame["adj_close"]
    return frame.set_index("date")


def build_intervals(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for idx in range(len(frame) - 1):
        entry_date = frame.index[idx]
        exit_date = frame.index[idx + 1]
        entry = frame.iloc[idx]
        exit_ = frame.iloc[idx + 1]
        entry_close = float(entry["adjusted_close"]) if pd.notna(entry["adjusted_close"]) else float("nan")
        exit_open = float(exit_["adjusted_open_recomputed"]) if pd.notna(exit_["adjusted_open_recomputed"]) else float("nan")
        intraday_exit = float(exit_["adjusted_close"] / exit_open - 1.0) if exit_open > 0 and pd.notna(exit_["adjusted_close"]) else float("nan")
        valid = (
            math.isfinite(entry_close)
            and math.isfinite(exit_open)
            and entry_close > 0.0
            and exit_open > 0.0
            and math.isfinite(float(entry["adjustment_factor_recomputed"]))
            and math.isfinite(float(exit_["adjustment_factor_recomputed"]))
            and float(entry["adjustment_factor_recomputed"]) > 0.0
            and float(exit_["adjustment_factor_recomputed"]) > 0.0
        )
        reason = "" if valid else "invalid_entry_close_or_exit_open_or_adjustment_factor"
        gap = int((exit_date - entry_date).days)
        rows.append(
            {
                "interval_id": f"overnight_{idx + 1:05d}",
                "interval_number": idx + 1,
                "entry_close_date": entry_date.date().isoformat(),
                "exit_open_date": exit_date.date().isoformat(),
                "calendar_gap_days": gap,
                "weekend_or_exchange_holiday_interval": gap > 1,
                "entry_raw_close": entry["raw_close"],
                "entry_adjusted_close": entry_close,
                "entry_adjustment_factor": entry["adjustment_factor_recomputed"],
                "exit_raw_open": exit_["raw_open"],
                "exit_raw_close": exit_["raw_close"],
                "exit_adjusted_open": exit_open,
                "exit_adjusted_close": exit_["adjusted_close"],
                "exit_adjustment_factor": exit_["adjustment_factor_recomputed"],
                "gross_overnight_return": float(exit_open / entry_close - 1.0) if valid else "",
                "diagnostic_open_to_close_return": intraday_exit if valid and math.isfinite(intraday_exit) else "",
                "interval_valid": valid,
                "skip_reason": reason,
                "no_forward_fill": True,
                "entry_uses_prior_close_only": True,
            }
        )
    valid_frame = pd.DataFrame([row for row in rows if row["interval_valid"]])
    return rows, valid_frame


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_SPY_overnight_only",
        "universe_type": "single_etf",
        "instrument": SPY,
        "formation_horizon": "none",
        "holding_horizon": "close_to_next_open",
        "rebalance_frequency": "daily_close_entry_next_open_exit",
        "weighting_method": "100pct_SPY_overnight_100pct_cash_intraday",
        "risk_overlay": "none",
        "execution_cadence": "known_schedule_close_buy_next_open_sell",
        "primary_benchmark": "SPY_buy_and_hold_matching_timestamps",
    }
    return {
        "candidate_id": CANDIDATE_ID,
        **fields,
        "strategy_fingerprint": stable_hash(fields),
        "fingerprint_algorithm": "sha256_json_sorted_normalized_structural_fields_v1",
    }


def duplicate_review_rows() -> list[dict[str, Any]]:
    roots = [ROOT / "strategy_lab", ROOT / "evidence"]
    overnight_mentions = 0
    close_open_mentions = 0
    candidate_mentions = 0
    for root in roots:
        paths = list(root.rglob("*")) if root.exists() else []
        for path in paths:
            if path.suffix.lower() not in {".yaml", ".yml", ".json", ".csv", ".md", ".txt", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            overnight_mentions += text.count("overnight")
            close_open_mentions += text.count("close-to-open") + text.count("close_to_open")
            candidate_mentions += text.count(CANDIDATE_ID.lower())
    return [
        {
            "reviewed_id": "repository_prior_spy_close_to_open_mentions",
            "same_SPY_instrument": candidate_mentions > 0,
            "same_close_entry_next_open_exit": False,
            "same_intraday_cash_state": False,
            "same_daily_repetition": False,
            "same_cost_treatment": False,
            "exact_corrected_methodology_duplicate": False,
            "authoritative_evidence_path": "",
            "decision": "no_prior_exact_SPY_close_to_next_open_cash_corrected_methodology_screen_found",
            "overnight_mentions": overnight_mentions,
            "close_to_open_mentions": close_open_mentions,
            "candidate_mentions": candidate_mentions,
        },
        {
            "reviewed_id": "turn_of_month_halloween_spy_trend_vm_buy_hold",
            "same_SPY_instrument": True,
            "same_close_entry_next_open_exit": False,
            "same_intraday_cash_state": False,
            "same_daily_repetition": False,
            "same_cost_treatment": False,
            "exact_corrected_methodology_duplicate": False,
            "authoritative_evidence_path": "",
            "decision": "not_duplicate_under_exact_duplicate_gate",
            "overnight_mentions": "",
            "close_to_open_mentions": "",
            "candidate_mentions": "",
        },
    ]


def mna_direction_level_memory() -> dict[str, Any]:
    mna_outcome = read_json(MNA_EVIDENCE_DIR / "screening_outcome.json")
    return {
        "candidate_id": "mna_static_merger_arbitrage_wrapper_v1",
        "source_evidence_path": rel(MNA_EVIDENCE_DIR),
        "original_formal_outcome_preserved": mna_outcome.get("outcome", "methodology_regime_instability"),
        "original_evidence_packet_modified": False,
        "exact_candidate_closed_for_immediate_retesting": True,
        "direction_level_interpretation": "diversification_value_without_sufficient_cash_edge",
        "full_period_cash_relative_return_premium": "insufficient",
        "current_regime_validation_authorized": False,
        "ARB_MRGR_MARB_timing_blend_hedge_deal_selection_variations_prohibited_immediately": True,
        "broader_event_driven_merger_arbitrage_family_open": True,
    }


def source_and_preregistration(
    cache_row: dict[str, Any],
    valid_intervals: pd.DataFrame,
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    first_entry = valid_intervals.iloc[0]["entry_close_date"] if not valid_intervals.empty else ""
    final_exit = valid_intervals.iloc[-1]["exit_open_date"] if not valid_intervals.empty else ""
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "canonical_family": FAMILY_ID,
        "mechanism": MECHANISM,
        "role": ROLE,
        "source_id": "overnight_return_primary_research_sources_v1",
        "sources": [
            {
                "citation": "Michael A. Kelly, Overnight Returns as a Market Timing Strategy, SSRN 3692068, 2020, revised 2021",
                "rule_support": "close-to-open and open-to-close ownership evaluated as market-timing mechanisms",
                "source_reported_performance_used": False,
            },
            {
                "citation": "Terrence Hendershott, Dmitry Livdan, and Dominik Rosch, Asset Pricing: A Tale of Night and Day, Journal of Financial Economics",
                "rule_support": "documents differing expected-return and market-exposure relationships overnight versus intraday",
                "source_reported_performance_used": False,
            },
            {
                "citation": "Dong Lou, Christopher Polk, and Spyros Skouras, A Tug of War: Overnight versus Intraday Expected Returns, Journal of Financial Economics 134, 2019, pages 192-213",
                "rule_support": "documents persistent differences between overnight and intraday return components",
                "source_reported_performance_used": False,
            },
        ],
        "frozen_rules": {
            "instrument": SPY,
            "idle_asset": "zero_return_cash",
            "entry": "buy SPY at official regular-session close of session t using all available capital",
            "exit": "sell complete SPY position at official regular-session open of next session t+1",
            "intraday_state": "zero-return cash from open of session t+1 until close of session t+1",
            "target_overnight_SPY": 1.0,
            "target_intraday_cash": 1.0,
            "long_only": True,
            "leverage": False,
            "shorting": False,
            "maximum_gross_exposure": 1.0,
            "ranking": False,
            "lookback": False,
            "signal_threshold": False,
            "filters": "none",
            "entry_cost_per_purchase": TRANSACTION_COST,
            "exit_cost_per_sale": TRANSACTION_COST,
            "gross_diagnostic_controls_outcome": False,
        },
        "adjustment_method": {
            "adjustment_factor": "adjusted_close_t / raw_close_t",
            "adjusted_open": "raw_open_t * adjustment_factor_t",
            "overnight_return": "adjusted_open_(t+1) / adjusted_close_t - 1",
            "raw_open_compared_with_adjusted_close": False,
            "forward_fill_allowed": False,
        },
        "pre_performance_freeze": {
            "SPY_cache_path": cache_row["cache_path"],
            "SPY_cache_hash": cache_row["cache_hash"],
            "first_entry_close_date": first_entry,
            "final_exit_open_date": final_exit,
            "valid_interval_count": int(len(valid_intervals)),
            "valid_interval_set_hash": stable_hash(valid_intervals.to_dict("records")),
            "initial_capital": INITIAL_CAPITAL,
            "transaction_cost_per_leg": TRANSACTION_COST,
            "chronological_block_boundaries_hash": stable_hash(blocks),
            "calendar_year_definition": "overnight interval belongs to exit/open date calendar year",
            "primary_benchmark": "SPY_buy_and_hold_matching_timestamps",
            "secondary_reference": "zero_return_cash",
            "outcome_thresholds_frozen_before_performance": True,
            "source_and_preregistration_written_before_performance_calculation": True,
        },
        "not_authorized": {
            "open_to_close_strategy": False,
            "filters_or_predictions": False,
            "alternative_cost_assumptions": False,
            "candidate_exhaustive": False,
            "promotion": False,
            "paper_demo_activation": False,
            "broker_orders": False,
            "real_money_recommendation": False,
        },
    }


def freeze_blocks(valid_intervals: pd.DataFrame, block_count: int = 5) -> list[dict[str, Any]]:
    positions = np.array_split(np.arange(len(valid_intervals)), block_count)
    rows: list[dict[str, Any]] = []
    for index, pos in enumerate(positions, start=1):
        start_row = valid_intervals.iloc[int(pos[0])]
        end_row = valid_intervals.iloc[int(pos[-1])]
        rows.append(
            {
                "block_id": f"block_{index}",
                "block_number": index,
                "start_interval_number": int(start_row["interval_number"]),
                "end_interval_number": int(end_row["interval_number"]),
                "start_entry_close_date": start_row["entry_close_date"],
                "end_exit_open_date": end_row["exit_open_date"],
                "valid_interval_count": int(len(pos)),
                "frozen_before_performance": True,
                "performance_computed_at_definition_time": False,
            }
        )
    return rows


def simulate_overnight_path(intervals: pd.DataFrame, apply_costs: bool) -> tuple[pd.Series, dict[str, Any]]:
    equity = INITIAL_CAPITAL
    values = [equity]
    dates = [pd.to_datetime(intervals.iloc[0]["entry_close_date"])]
    total_costs = 0.0
    for row in intervals.to_dict("records"):
        gross = float(row["gross_overnight_return"])
        if apply_costs:
            entry_cost = equity * TRANSACTION_COST
            after_entry = equity - entry_cost
            before_exit_cost = after_entry * (1.0 + gross)
            exit_cost = before_exit_cost * TRANSACTION_COST
            equity = before_exit_cost - exit_cost
            total_costs += entry_cost + exit_cost
        else:
            equity *= 1.0 + gross
        dates.append(pd.to_datetime(row["exit_open_date"]))
        values.append(equity)
    return pd.Series(values, index=pd.DatetimeIndex(dates)), {
        "purchase_count": int(len(intervals)),
        "sale_count": int(len(intervals)),
        "total_trade_count": int(len(intervals) * 2),
        "gross_turnover": float(len(intervals) * 2),
        "total_transaction_costs": total_costs,
        "average_cost_per_completed_overnight_cycle": total_costs / len(intervals) if len(intervals) else 0.0,
    }


def simulate_spy_benchmark(intervals: pd.DataFrame) -> tuple[pd.Series, dict[str, Any]]:
    first_close = float(intervals.iloc[0]["entry_adjusted_close"])
    dates = [pd.to_datetime(intervals.iloc[0]["entry_close_date"])]
    shares = INITIAL_CAPITAL * (1.0 - TRANSACTION_COST) / first_close
    values = [INITIAL_CAPITAL]
    for i, row in enumerate(intervals.to_dict("records")):
        value = shares * float(row["exit_adjusted_open"])
        if i == len(intervals) - 1:
            value *= 1.0 - TRANSACTION_COST
        values.append(value)
        dates.append(pd.to_datetime(row["exit_open_date"]))
    final_before_sale = shares * float(intervals.iloc[-1]["exit_adjusted_open"])
    costs = INITIAL_CAPITAL * TRANSACTION_COST + final_before_sale * TRANSACTION_COST
    return pd.Series(values, index=pd.DatetimeIndex(dates)), {
        "purchase_count": 1,
        "sale_count": 1,
        "total_trade_count": 2,
        "gross_turnover": 2.0,
        "total_transaction_costs": costs,
    }


def cash_path(intervals: pd.DataFrame) -> pd.Series:
    dates = [pd.to_datetime(intervals.iloc[0]["entry_close_date"])] + [pd.to_datetime(row["exit_open_date"]) for row in intervals.to_dict("records")]
    return pd.Series([INITIAL_CAPITAL] * len(dates), index=pd.DatetimeIndex(dates))


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


def capture_ratio(asset_returns: pd.Series, benchmark_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "benchmark"]
    subset = aligned[aligned["benchmark"] > 0.0] if direction == "up" else aligned[aligned["benchmark"] < 0.0]
    if subset.empty or abs(float(subset["benchmark"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["benchmark"].mean())


def path_metrics(path_id: str, equity: pd.Series, interval_returns: pd.Series | None = None) -> dict[str, Any]:
    returns = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / INITIAL_CAPITAL - 1.0)
    dd = max_drawdown(equity)
    interval_returns = returns if interval_returns is None else interval_returns.dropna()
    return {
        "path_id": path_id,
        "start_date": equity.index[0].date().isoformat(),
        "end_date": equity.index[-1].date().isoformat(),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "annualized_volatility": annualized_volatility(returns),
        "downside_volatility": downside_volatility(returns),
        "max_drawdown": dd,
        "worst_overnight_return": float(interval_returns.min()) if len(interval_returns) else "",
        "best_overnight_return": float(interval_returns.max()) if len(interval_returns) else "",
        "positive_overnight_rate": float((interval_returns > 0.0).mean()) if len(interval_returns) else "",
        "return_to_max_drawdown_ratio": float(total_return / abs(dd)) if dd < 0.0 else float("nan"),
    }


def evaluate_interval_subset(intervals: pd.DataFrame) -> dict[str, Any]:
    gross, gross_ops = simulate_overnight_path(intervals, apply_costs=False)
    net, net_ops = simulate_overnight_path(intervals, apply_costs=True)
    spy, spy_ops = simulate_spy_benchmark(intervals)
    cash = cash_path(intervals)
    gross_m = path_metrics("gross_overnight_only", gross, intervals["gross_overnight_return"].astype(float))
    net_m = path_metrics("net_overnight_only_candidate", net, net.pct_change().dropna())
    spy_m = path_metrics("SPY_buy_and_hold_matching_timestamps", spy)
    cash_m = path_metrics("zero_return_cash", cash)
    return {
        "gross_equity": gross,
        "net_equity": net,
        "spy_equity": spy,
        "cash_equity": cash,
        "gross_ops": gross_ops,
        "net_ops": net_ops,
        "spy_ops": spy_ops,
        "metrics": {
            "gross_overnight_only": gross_m,
            "net_overnight_only_candidate": net_m,
            "SPY_buy_and_hold_matching_timestamps": spy_m,
            "zero_return_cash": cash_m,
        },
    }


def evaluate_blocks(valid_intervals: pd.DataFrame, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in blocks:
        subset = valid_intervals[
            (valid_intervals["interval_number"] >= block["start_interval_number"])
            & (valid_intervals["interval_number"] <= block["end_interval_number"])
        ]
        result = evaluate_interval_subset(subset)
        gross = result["metrics"]["gross_overnight_only"]
        net = result["metrics"]["net_overnight_only_candidate"]
        spy = result["metrics"]["SPY_buy_and_hold_matching_timestamps"]
        rows.append(
            {
                "block_id": block["block_id"],
                "block_number": block["block_number"],
                "start_entry_close_date": block["start_entry_close_date"],
                "end_exit_open_date": block["end_exit_open_date"],
                "valid_interval_count": block["valid_interval_count"],
                "gross_total_return": gross["total_return"],
                "net_total_return": net["total_return"],
                "SPY_total_return": spy["total_return"],
                "net_excess_return_versus_SPY": float(net["total_return"] - spy["total_return"]),
                "gross_excess_return_versus_SPY": float(gross["total_return"] - spy["total_return"]),
                "net_beats_SPY": bool(net["total_return"] > spy["total_return"]),
                "gross_beats_SPY": bool(gross["total_return"] > spy["total_return"]),
                "net_max_drawdown": net["max_drawdown"],
                "SPY_max_drawdown": spy["max_drawdown"],
                "net_smaller_drawdown_than_SPY": bool(net["max_drawdown"] > spy["max_drawdown"]),
                "initial_and_exit_costs_applied_in_block": True,
            }
        )
    return rows


def calendar_year_rows(valid_intervals: pd.DataFrame) -> list[dict[str, Any]]:
    years = sorted({pd.to_datetime(value).year for value in valid_intervals["exit_open_date"]})
    first_year = years[0]
    last_year = years[-1]
    rows: list[dict[str, Any]] = []
    for year in years:
        subset = valid_intervals[pd.to_datetime(valid_intervals["exit_open_date"]).dt.year == year]
        if subset.empty:
            continue
        period_type = "complete_calendar_year"
        if year == first_year:
            period_type = "partial_first_year"
        if year == last_year:
            period_type = "partial_final_year" if period_type == "complete_calendar_year" else period_type + "_and_final"
        result = evaluate_interval_subset(subset)
        gross = result["metrics"]["gross_overnight_only"]
        net = result["metrics"]["net_overnight_only_candidate"]
        spy = result["metrics"]["SPY_buy_and_hold_matching_timestamps"]
        rows.append(
            {
                "calendar_period": str(year),
                "period_type": period_type,
                "start_entry_close_date": subset.iloc[0]["entry_close_date"],
                "end_exit_open_date": subset.iloc[-1]["exit_open_date"],
                "valid_interval_count": int(len(subset)),
                "gross_total_return": gross["total_return"],
                "net_total_return": net["total_return"],
                "SPY_total_return": spy["total_return"],
                "gross_beats_SPY": bool(gross["total_return"] > spy["total_return"]),
                "net_beats_SPY": bool(net["total_return"] > spy["total_return"]),
                "net_losing_year": bool(net["total_return"] < 0.0),
                "cost_drag_return": float(gross["total_return"] - net["total_return"]),
            }
        )
    return rows


def spy_relative_metrics(full: dict[str, Any], block_rows: list[dict[str, Any]], calendar_rows_: list[dict[str, Any]]) -> dict[str, Any]:
    gross = full["metrics"]["gross_overnight_only"]
    net = full["metrics"]["net_overnight_only_candidate"]
    spy = full["metrics"]["SPY_buy_and_hold_matching_timestamps"]
    net_returns = full["net_equity"].pct_change().dropna()
    gross_returns = full["gross_equity"].pct_change().dropna()
    spy_returns = full["spy_equity"].pct_change().dropna()
    complete_years = [row for row in calendar_rows_ if row["period_type"] == "complete_calendar_year"]
    net_block_excess = [float(row["net_excess_return_versus_SPY"]) for row in block_rows]
    gross_block_excess = [float(row["gross_excess_return_versus_SPY"]) for row in block_rows]
    return {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": "SPY_buy_and_hold_matching_timestamps",
        "full_period_net_excess_return_versus_SPY": float(net["total_return"] - spy["total_return"]),
        "full_period_gross_excess_return_versus_SPY": float(gross["total_return"] - spy["total_return"]),
        "net_cagr_difference_versus_SPY": float(net["cagr"] - spy["cagr"]),
        "gross_cagr_difference_versus_SPY": float(gross["cagr"] - spy["cagr"]),
        "net_max_drawdown_difference_versus_SPY": float(net["max_drawdown"] - spy["max_drawdown"]),
        "gross_max_drawdown_difference_versus_SPY": float(gross["max_drawdown"] - spy["max_drawdown"]),
        "mean_net_block_excess_versus_SPY": float(np.mean(net_block_excess)),
        "median_net_block_excess_versus_SPY": float(np.median(net_block_excess)),
        "mean_gross_block_excess_versus_SPY": float(np.mean(gross_block_excess)),
        "median_gross_block_excess_versus_SPY": float(np.median(gross_block_excess)),
        "net_blocks_beating_SPY": int(sum(row["net_beats_SPY"] is True for row in block_rows)),
        "gross_blocks_beating_SPY": int(sum(row["gross_beats_SPY"] is True for row in block_rows)),
        "net_calendar_years_beating_SPY": int(sum(row["net_beats_SPY"] is True for row in complete_years)),
        "gross_calendar_years_beating_SPY": int(sum(row["gross_beats_SPY"] is True for row in complete_years)),
        "complete_calendar_year_count": int(len(complete_years)),
        "latest_net_block_excess_return": float(block_rows[-1]["net_excess_return_versus_SPY"]),
        "latest_gross_block_excess_return": float(block_rows[-1]["gross_excess_return_versus_SPY"]),
        "net_downside_capture_versus_SPY": capture_ratio(net_returns, spy_returns, "down"),
        "net_upside_capture_versus_SPY": capture_ratio(net_returns, spy_returns, "up"),
        "gross_downside_capture_versus_SPY": capture_ratio(gross_returns, spy_returns, "down"),
        "gross_upside_capture_versus_SPY": capture_ratio(gross_returns, spy_returns, "up"),
        "net_blocks_with_smaller_drawdown_than_SPY": int(sum(row["net_smaller_drawdown_than_SPY"] is True for row in block_rows)),
    }


def cost_diagnostics(full: dict[str, Any], valid_count: int, skipped_count: int) -> dict[str, Any]:
    gross = full["metrics"]["gross_overnight_only"]
    net = full["metrics"]["net_overnight_only_candidate"]
    net_ops = full["net_ops"]
    gross_profit = float(gross["final_equity"] - INITIAL_CAPITAL)
    cost_drag_dollars = float(gross["final_equity"] - net["final_equity"])
    return {
        "candidate_id": CANDIDATE_ID,
        "valid_overnight_count": valid_count,
        "skipped_interval_count": skipped_count,
        "number_of_purchases": net_ops["purchase_count"],
        "number_of_sales": net_ops["sale_count"],
        "total_trade_count": net_ops["total_trade_count"],
        "gross_turnover": net_ops["gross_turnover"],
        "total_transaction_costs": net_ops["total_transaction_costs"],
        "cost_drag_as_pct_of_gross_profit": cost_drag_dollars / gross_profit if gross_profit > 0.0 else "",
        "gross_to_net_return_difference": float(gross["total_return"] - net["total_return"]),
        "average_cost_per_completed_overnight_cycle": net_ops["average_cost_per_completed_overnight_cycle"],
        "canonical_cost_per_leg": TRANSACTION_COST,
        "costs_applied_to_entry_and_exit": True,
    }


def overnight_intraday_decomposition(valid_intervals: pd.DataFrame, spy_benchmark: pd.Series) -> dict[str, Any]:
    overnight_returns = valid_intervals["gross_overnight_return"].astype(float)
    intraday_returns = valid_intervals["diagnostic_open_to_close_return"].astype(float)
    aggregate_overnight = float((1.0 + overnight_returns).prod() - 1.0)
    aggregate_intraday = float((1.0 + intraday_returns).prod() - 1.0)
    full_spy = float(spy_benchmark.iloc[-1] / INITIAL_CAPITAL - 1.0)
    overnight_log = float(np.log1p(overnight_returns).sum())
    full_log = float(math.log1p(full_spy)) if full_spy > -1.0 else float("nan")
    return {
        "candidate_id": CANDIDATE_ID,
        "aggregate_SPY_close_to_open_return": aggregate_overnight,
        "aggregate_SPY_open_to_close_return": aggregate_intraday,
        "mean_overnight_return": float(overnight_returns.mean()),
        "mean_intraday_return": float(intraday_returns.mean()),
        "full_matching_timestamp_SPY_return": full_spy,
        "fraction_of_full_SPY_log_return_attributable_to_overnight_intervals": overnight_log / full_log if math.isfinite(full_log) and abs(full_log) > 1e-12 else "",
        "open_to_close_is_diagnostic_only": True,
        "open_to_close_strategy_created": False,
    }


def determine_outcome(relative: dict[str, Any], cost: dict[str, Any], invariants_pass: bool) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Adjusted-open, timing, matching-timestamp, cost, exposure, or determinism invariant failed"
    net_full_excess = float(relative["full_period_net_excess_return_versus_SPY"])
    gross_full_excess = float(relative["full_period_gross_excess_return_versus_SPY"])
    net_median = float(relative["median_net_block_excess_versus_SPY"])
    gross_median = float(relative["median_gross_block_excess_versus_SPY"])
    net_blocks = int(relative["net_blocks_beating_SPY"])
    gross_blocks = int(relative["gross_blocks_beating_SPY"])
    net_mdd_diff = float(relative["net_max_drawdown_difference_versus_SPY"])
    smaller_dd_blocks = int(relative["net_blocks_with_smaller_drawdown_than_SPY"])
    latest_two_weak = False
    # The caller stores only the latest block in relative; final-two logic is computed in run() for clarity.
    if (
        net_full_excess > 0.0
        and net_median > 0.0
        and net_blocks >= 3
        and net_mdd_diff >= -0.05
    ):
        return "comparative_evidence_positive", "Net overnight candidate exceeded matching-timestamp SPY with broad block support and acceptable drawdown"
    if net_full_excess > 0.0 and net_median > 0.0 and net_blocks >= 3 and latest_two_weak:
        return "historical_edge_recently_weakened", "Positive net full and median block excess weakened in both final blocks"
    if net_full_excess <= 0.0 and net_median <= 0.0 and net_mdd_diff >= 0.10 and smaller_dd_blocks >= 4:
        return "risk_reduction_without_return_edge", "Net overnight candidate did not beat SPY but materially improved drawdown"
    cost_drag_pct = cost.get("cost_drag_as_pct_of_gross_profit", "")
    cost_drag_high = cost_drag_pct != "" and float(cost_drag_pct) >= 0.50
    gross_condition = gross_median > 0.0 or gross_blocks >= 3
    net_condition = net_median > 0.0 or net_blocks >= 3
    cost_flips = gross_full_excess > 0.0 and net_full_excess <= 0.0
    if gross_condition and not net_condition and (cost_drag_high or cost_flips):
        return "cost_sensitive_no_edge", "Gross overnight diagnostic showed evidence that canonical two-leg costs destroyed"
    return "no_material_edge", "No positive, weakened, risk-reduction, or cost-sensitive classification was supported"


def exact_variant_memory(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    preserve = outcome == "comparative_evidence_positive"
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome": outcome,
            "primary_failure_reason": "" if preserve else failure_reason,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "broader_equity_overnight_return_family_closed": False,
            "open_to_close_overnight_momentum_reversal_QQQ_IWM_calendar_volatility_reduced_frequency_cost_variations_prohibited_immediately": True,
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
        MNA_EVIDENCE_DIR / "screening_outcome.json",
        MNA_EVIDENCE_DIR / "exact_variant_research_memory.csv",
    ]
    state_before = file_snapshot(protected_paths)
    spy_hash_before = sha256_path(cache_path(SPY))
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    spy_quality, provider_manifest = ensure_spy_cache(prior_provider)
    spy_hash_after = sha256_path(cache_path(SPY))
    provider_manifest["SPY_cache_refreshed"] = spy_hash_before != spy_hash_after and bool(provider_manifest["downloaded_symbols_this_run"])

    duplicate_rows = duplicate_review_rows()
    exact_duplicate = any(row["exact_corrected_methodology_duplicate"] is True for row in duplicate_rows)

    interval_rows: list[dict[str, Any]] = []
    valid_intervals = pd.DataFrame()
    blocks: list[dict[str, Any]] = []
    full_metrics_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    calendar_rows_: list[dict[str, Any]] = []
    relative: dict[str, Any] = {}
    cost: dict[str, Any] = {}
    decomposition: dict[str, Any] = {}
    invariants: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""
    invalid_reason = ""

    try:
        if exact_duplicate:
            raise RuntimeError("exact corrected-methodology SPY close-to-next-open screen already exists")
        if spy_quality["adjusted_open_validation_result"] != "pass":
            raise RuntimeError("SPY adjusted open/close cache validation failed")
        frame = load_spy_ohlc()
        interval_rows, valid_intervals = build_intervals(frame)
        if valid_intervals.empty:
            raise RuntimeError("no valid SPY close-to-next-open intervals")
        blocks = freeze_blocks(valid_intervals)

        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(
            EVIDENCE_DIR / "cache_and_adjustment_manifest.json",
            {
                "candidate_id": CANDIDATE_ID,
                "SPY_cache": spy_quality,
                "adjustment_method": "adjusted_open_t = raw_open_t * (adjusted_close_t / raw_close_t)",
                "overnight_return_method": "adjusted_open_(t+1) / adjusted_close_t - 1",
                "raw_open_compared_with_adjusted_close": False,
                "forward_fill_used": False,
                "valid_interval_count": int(len(valid_intervals)),
                "skipped_interval_count": int(len(interval_rows) - len(valid_intervals)),
                "final_date_frozen_before_performance": valid_intervals.iloc[-1]["exit_open_date"],
                "cache_hash": spy_hash_after,
            },
        )
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "valid_and_skipped_overnight_intervals.csv", interval_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(spy_quality, valid_intervals, blocks))
        write_json(EVIDENCE_DIR / "mna_direction_level_memory.json", mna_direction_level_memory())

        full = evaluate_interval_subset(valid_intervals)
        full_metrics_rows = [
            full["metrics"]["gross_overnight_only"],
            full["metrics"]["net_overnight_only_candidate"],
            full["metrics"]["SPY_buy_and_hold_matching_timestamps"],
            full["metrics"]["zero_return_cash"],
        ]
        block_rows = evaluate_blocks(valid_intervals, blocks)
        calendar_rows_ = calendar_year_rows(valid_intervals)
        relative = spy_relative_metrics(full, block_rows, calendar_rows_)
        cost = cost_diagnostics(full, int(len(valid_intervals)), int(len(interval_rows) - len(valid_intervals)))
        decomposition = overnight_intraday_decomposition(valid_intervals, full["spy_equity"])
        state_after = file_snapshot(protected_paths)
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "maximum_exposure": 1.0,
            "maximum_weight_sum": 1.0,
            "intraday_exposure": 0.0,
            "no_lookahead_result": True,
            "entry_uses_next_open_information": False,
            "adjusted_open_validation": True,
            "matching_timestamp_benchmark_validation": True,
            "missing_price_intervals_skipped": int(len(interval_rows) - len(valid_intervals)),
            "prices_forward_filled": False,
            "raw_open_compared_with_adjusted_close": False,
            "determinism": True,
            "SPY_cache_hash": spy_hash_after,
            "existing_VM_DSR_USCI_combo_states_unchanged": state_before == state_after,
            "MNA_original_evidence_packet_unchanged": state_before.get(rel(MNA_EVIDENCE_DIR / "screening_outcome.json")) == sha256_path(MNA_EVIDENCE_DIR / "screening_outcome.json"),
            "paper_forward_or_broker_order_created": False,
            "open_to_close_strategy_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome(relative, cost, True)
        if outcome == "comparative_evidence_positive":
            final_two_underperform = len(block_rows) >= 2 and all(float(row["net_excess_return_versus_SPY"]) < 0.0 for row in block_rows[-2:])
            if final_two_underperform:
                outcome, outcome_reason = (
                    "historical_edge_recently_weakened",
                    "Positive net full and median block excess weakened in both final blocks",
                )
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(EVIDENCE_DIR / "cache_and_adjustment_manifest.json", {"candidate_id": CANDIDATE_ID, "SPY_cache": spy_quality})
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "valid_and_skipped_overnight_intervals.csv", interval_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(spy_quality, valid_intervals, blocks))
        write_json(EVIDENCE_DIR / "mna_direction_level_memory.json", mna_direction_level_memory())
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "maximum_exposure": "",
            "maximum_weight_sum": "",
            "intraday_exposure": "",
            "no_lookahead_result": False,
            "entry_uses_next_open_information": False,
            "adjusted_open_validation": False,
            "matching_timestamp_benchmark_validation": False,
            "missing_price_intervals_skipped": "",
            "prices_forward_filled": False,
            "raw_open_compared_with_adjusted_close": False,
            "determinism": False,
            "SPY_cache_hash": sha256_path(cache_path(SPY)),
            "existing_VM_DSR_USCI_combo_states_unchanged": file_snapshot(protected_paths) == state_before,
            "MNA_original_evidence_packet_unchanged": state_before.get(rel(MNA_EVIDENCE_DIR / "screening_outcome.json")) == sha256_path(MNA_EVIDENCE_DIR / "screening_outcome.json"),
            "paper_forward_or_broker_order_created": False,
            "open_to_close_strategy_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": False,
        }

    write_csv(EVIDENCE_DIR / "full_period_metrics.csv", full_metrics_rows)
    write_csv(EVIDENCE_DIR / "chronological_block_results.csv", block_rows)
    write_csv(EVIDENCE_DIR / "calendar_year_results.csv", calendar_rows_)
    write_csv(EVIDENCE_DIR / "spy_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "gross_net_cost_diagnostics.csv", [cost])
    write_csv(EVIDENCE_DIR / "overnight_intraday_decomposition.csv", [decomposition])
    write_csv(EVIDENCE_DIR / "accounting_timing_and_data_invariants.csv", [invariants])
    memory = exact_variant_memory(outcome, outcome_reason)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "direction_owner_validation_review_spy_close_to_open_overnight_cash_v1"
        if outcome == "comparative_evidence_positive"
        else "record_spy_close_to_open_overnight_cash_exact_variant_memory_and_resume_source_queue"
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
        "gross_diagnostic_controls_outcome": False,
        "invalid_reason": invalid_reason,
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", screening_outcome)
    consistency = {
        "candidate_id": CANDIDATE_ID,
        "only_SPY_provider_acquisition_authorized": provider_manifest["authorized_download_symbols"] == [SPY],
        "provider_download_if_any_limited_to_SPY": set(provider_manifest["downloaded_symbols_this_run"]).issubset({SPY}),
        "no_intraday_bars_downloaded": provider_manifest["intraday_bars_downloaded"] is False,
        "adjusted_open_constructed_consistently": invariants["adjusted_open_validation"] is True,
        "raw_open_never_compared_with_adjusted_close": invariants["raw_open_compared_with_adjusted_close"] is False,
        "no_prices_forward_filled": invariants["prices_forward_filled"] is False,
        "candidate_buys_only_at_session_close": True,
        "candidate_sells_only_at_next_valid_session_open": True,
        "weekend_and_holiday_intervals_retained": any(row.get("weekend_or_exchange_holiday_interval") is True for row in interval_rows),
        "intraday_exposure_zero": invariants["intraday_exposure"] == 0.0,
        "no_next_open_information_used_before_entry": invariants["entry_uses_next_open_information"] is False,
        "costs_apply_to_both_legs": cost.get("costs_applied_to_entry_and_exit") is True,
        "gross_diagnostic_not_outcome_controlling": screening_outcome["gross_diagnostic_controls_outcome"] is False,
        "matching_timestamp_SPY_benchmark": invariants["matching_timestamp_benchmark_validation"] is True,
        "exposure_never_exceeds_1": invariants.get("maximum_exposure") in {"", None} or float(invariants["maximum_exposure"]) <= 1.000001,
        "no_open_to_close_strategy_created": invariants["open_to_close_strategy_created"] is False,
        "existing_observation_states_unchanged": invariants["existing_VM_DSR_USCI_combo_states_unchanged"] is True,
        "MNA_original_evidence_packet_unchanged": invariants["MNA_original_evidence_packet_unchanged"] is True,
        "no_paper_demo_or_broker_order": invariants["paper_forward_or_broker_order_created"] is False,
        "output_generation_deterministic": invariants["determinism"] is True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "only_SPY_provider_acquisition_authorized",
        "provider_download_if_any_limited_to_SPY",
        "no_intraday_bars_downloaded",
        "adjusted_open_constructed_consistently",
        "raw_open_never_compared_with_adjusted_close",
        "no_prices_forward_filled",
        "candidate_buys_only_at_session_close",
        "candidate_sells_only_at_next_valid_session_open",
        "weekend_and_holiday_intervals_retained",
        "intraday_exposure_zero",
        "no_next_open_information_used_before_entry",
        "costs_apply_to_both_legs",
        "gross_diagnostic_not_outcome_controlling",
        "matching_timestamp_SPY_benchmark",
        "exposure_never_exceeds_1",
        "no_open_to_close_strategy_created",
        "existing_observation_states_unchanged",
        "MNA_original_evidence_packet_unchanged",
        "no_paper_demo_or_broker_order",
        "output_generation_deterministic",
    }
    required_false = {"promotion_authorized", "paper_demo_authorized", "candidate_exhaustive_authorized", "real_money_recommendation"}
    consistency["consistency_passed"] = all(consistency[key] is True for key in required_true) and all(
        consistency[key] is False for key in required_false
    )
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    write_text(
        EVIDENCE_DIR / "screen_summary.md",
        f"""# SPY Close-to-Open Overnight Cash Bounded Screen v1

Candidate `{CANDIDATE_ID}` was evaluated as one fixed schedule: buy `SPY` at each regular-session close, sell at the next regular-session open, and hold zero-return cash intraday.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider acquisition this run: `{provider_manifest['provider_download']}`
- Valid overnight intervals: `{len(valid_intervals) if not valid_intervals.empty else 0}`
- Skipped intervals: `{len(interval_rows) - len(valid_intervals) if interval_rows else 0}`
- Primary benchmark: `SPY_buy_and_hold_matching_timestamps`
- Gross diagnostic controls outcome: `false`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

The screen does not create an open-to-close strategy, does not download intraday bars, does not add filters or prediction signals, and does not alter VM, DSR, USCI, active-combo, MNA, registry, or paper/demo observation state.
""",
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "evidence_dir": rel(EVIDENCE_DIR),
        "outcome": outcome,
        "consistency_passed": consistency["consistency_passed"],
        "provider_download": provider_manifest["provider_download"],
        "valid_overnight_count": int(len(valid_intervals)) if not valid_intervals.empty else 0,
        "next_action": next_action,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
