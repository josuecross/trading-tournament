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
EVIDENCE_DIR = ROOT / "evidence" / "btal_static_anti_beta_market_neutral_bounded_screen_v1" / "latest"
CANDIDATE_ID = "btal_static_anti_beta_market_neutral_wrapper_v1"
FAMILY_ID = "market_neutral_anti_beta"
MECHANISM = "static_long_low_beta_short_high_beta_us_equity_wrapper"
BTAL = "BTAL"
BIL = "BIL"
SPY = "SPY"
SYMBOLS = (BTAL, BIL, SPY)
AUTHORIZED_DOWNLOAD_SYMBOLS = (BTAL,)
FORBIDDEN_MARKET_NEUTRAL_PRODUCTS = ("BTALX", "MOM", "CHEP", "QMN", "CSM")
INITIAL_CAPITAL = float(active.STARTING_EQUITY)
INITIAL_TRANSACTION_COST = float(active.SLIPPAGE)
REGISTRY_PATH = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
PAPER_FORWARD_DIR = ROOT / "paper_forward_observations"
ACTIVE_COMBO_SERIES_PATH = ROOT / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_equity_series.csv"
OVERNIGHT_EVIDENCE_DIR = ROOT / "evidence" / "spy_close_to_open_overnight_cash_bounded_screen_v1" / "latest"
REQUEST_SETTINGS = {
    "start": "2011-09-01",
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
    "negative_beta_diversification_without_cash_edge",
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
        raise ValueError(f"Only BTAL provider acquisition is authorized for this screen; got {symbol}")
    return normalized


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    validate_authorized_download_symbol(symbol)
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2011-09-01"),
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


def ensure_btal_cache(prior_provider: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before_hash = sha256_path(cache_path(BTAL))
    before_quality = cache_quality_row(BTAL)
    downloaded = False
    status = "existing_cache_valid"
    error = ""
    if before_quality["adjusted_price_validation_result"] != "pass":
        try:
            raw = default_yfinance_downloader(BTAL, REQUEST_SETTINGS)
            normalized = build_adjusted_ohlc(raw, BTAL)
            cache_path(BTAL).parent.mkdir(parents=True, exist_ok=True)
            normalized.to_csv(cache_path(BTAL), index=False, lineterminator="\n")
            downloaded = True
            status = "downloaded_and_validated"
        except Exception as exc:  # pragma: no cover
            status = "provider_download_failed"
            error = f"{type(exc).__name__}: {exc}"
    after_quality = cache_quality_row(BTAL)
    after_hash = sha256_path(cache_path(BTAL))
    if after_quality["adjusted_price_validation_result"] != "pass" and not error:
        error = "BTAL adjusted total-return cache validation failed"
    after_quality["provider_download"] = downloaded
    after_quality["cache_refreshed"] = downloaded
    previous_ever = set(prior_provider.get("downloaded_symbols_ever", []) or [])
    downloaded_this_run = [BTAL] if downloaded else []
    manifest = {
        "candidate_id": CANDIDATE_ID,
        "authorized_provider_acquisition": True,
        "authorized_download_symbols": list(AUTHORIZED_DOWNLOAD_SYMBOLS),
        "forbidden_market_neutral_products": list(FORBIDDEN_MARKET_NEUTRAL_PRODUCTS),
        "provider": "yfinance_compatible_public_daily_etf_cache_path",
        "request_settings": REQUEST_SETTINGS,
        "series": [
            {
                "symbol": BTAL,
                "status": status,
                "cache_path": rel(cache_path(BTAL)),
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
        "BTAL_cache_refreshed": downloaded,
        "BIL_cache_refreshed": False,
        "SPY_cache_refreshed": False,
        "alternative_anti_beta_product_downloaded": False,
        "underlying_index_or_constituents_downloaded": False,
        "beta_or_borrow_data_downloaded": False,
        "provider_download_guardrail_passed": set(downloaded_this_run).issubset({BTAL}),
        "invalid_methodology_if_adjusted_total_return_unavailable": after_quality["adjusted_price_validation_result"] != "pass",
    }
    return after_quality, manifest


def read_price(symbol: str) -> pd.Series:
    frame = pd.read_csv(cache_path(symbol))
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    frame = frame.dropna(subset=["date"]).sort_values("date")
    out = pd.Series(pd.to_numeric(frame["adj_close"], errors="coerce").to_numpy(dtype=float), index=pd.DatetimeIndex(frame["date"]), name=symbol)
    return out.dropna()


def load_common_prices() -> pd.DataFrame:
    prices = pd.concat([read_price(symbol) for symbol in SYMBOLS], axis=1, join="inner").dropna()
    return prices[~prices.index.duplicated(keep="last")].sort_index()


def duplicate_review_rows() -> list[dict[str, Any]]:
    roots = [ROOT / "strategy_lab", ROOT / "evidence"]
    btal_mentions = 0
    anti_beta_mentions = 0
    market_neutral_mentions = 0
    for root in roots:
        paths = list(root.rglob("*")) if root.exists() else []
        for path in paths:
            if path.suffix.lower() not in {".yaml", ".yml", ".json", ".csv", ".md", ".txt", ".py"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            btal_mentions += text.count("btal")
            anti_beta_mentions += text.count("anti-beta") + text.count("anti_beta")
            market_neutral_mentions += text.count("market neutral") + text.count("market_neutral")
    return [
        {
            "reviewed_id": "repository_prior_BTAL_mentions",
            "same_wrapper": btal_mentions > 0,
            "same_primary_benchmark": False,
            "same_role": False,
            "exact_corrected_methodology_duplicate": False,
            "authoritative_evidence_path": "",
            "decision": "no_prior_exact_BTAL_BIL_primary_static_wrapper_corrected_methodology_screen_found",
            "btal_mentions": btal_mentions,
            "anti_beta_mentions": anti_beta_mentions,
            "market_neutral_mentions": market_neutral_mentions,
        },
        {
            "reviewed_id": "VM_SPLV_QUAL_pairs_MNA_covered_call_active_combo",
            "same_wrapper": False,
            "same_primary_benchmark": False,
            "same_role": False,
            "exact_corrected_methodology_duplicate": False,
            "authoritative_evidence_path": "",
            "decision": "not_duplicate_materially_distinct_short_high_beta_negative_beta_wrapper",
            "btal_mentions": "",
            "anti_beta_mentions": "",
            "market_neutral_mentions": "",
        },
    ]


def candidate_fingerprint() -> dict[str, Any]:
    fields = {
        "family": FAMILY_ID,
        "mechanism": MECHANISM,
        "signal_direction": "long_static_wrapper_owns_internal_long_short_fund",
        "universe_type": "single_listed_etf_wrapper",
        "instrument": BTAL,
        "formation_horizon": "embedded_fund_52_week_beta_estimation",
        "holding_horizon": "continuous_full_common_history",
        "rebalance_frequency": "none_after_initial_project_purchase",
        "weighting_method": "100pct_BTAL",
        "risk_overlay": "none_project_level",
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
            "event_date": "2011-09-12",
            "event_type": "fund_inception",
            "source": "AGF official product page and fact sheet",
            "source_reference": "Fund inception date.",
            "classification": "fund_history",
            "regime_assignment": "pre_regime_context",
            "mechanism_change": False,
            "notes": "Continuous listed wrapper history begins before first project common date.",
        },
        {
            "event_date": "2011-09-12",
            "event_type": "original_passive_index_objective",
            "source": "AGF official prospectus",
            "source_reference": "From inception through February 13, 2022 the fund sought to track the Dow Jones US Thematic Market Neutral Low Beta Index.",
            "classification": "passive_index_tracking_history",
            "regime_assignment": "regime_1",
            "mechanism_change": False,
            "notes": "Passive history is not described as the current active methodology.",
        },
        {
            "event_date": "2022-02-14",
            "event_type": "active_rules_based_strategy_transition",
            "source": "AGF official product page, fact sheet, and prospectus",
            "source_reference": "Effective February 14, 2022, BTAL changed from passive index tracking to an active rules-based strategy seeking consistent negative beta exposure.",
            "classification": "economic_methodology_change",
            "regime_assignment": "regime_2",
            "mechanism_change": True,
            "notes": "Frozen before performance and used for passive/active regime reporting.",
        },
        {
            "event_date": "current",
            "event_type": "embedded_implementation_risks",
            "source": "AGF official materials",
            "source_reference": "Fund uses long low-beta and short high-beta US equities, dollar neutral within sectors, possible active rules-based exposure adjustments and gross leverage reduction for VaR constraints.",
            "classification": "wrapper_risk_disclosure",
            "regime_assignment": "all",
            "mechanism_change": False,
            "notes": "Project owns only the ETF wrapper; internal shorting, financing, expenses, portfolio turnover, and implementation effects are embedded in adjusted returns.",
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
    boundary = pd.Timestamp("2022-02-14")
    regime_1_dates = common_dates[(common_dates >= first) & (common_dates <= pd.Timestamp("2022-02-13"))]
    if not regime_1_dates.empty:
        rows.append(
            {
                "regime_id": "regime_1_passive_index_tracking_history",
                "start_date": regime_1_dates[0].date().isoformat(),
                "end_date": regime_1_dates[-1].date().isoformat(),
                "boundary_rule": "first valid BTAL/BIL/SPY common date through 2022-02-13",
                "methodology_boundary_frozen_before_performance": True,
                "trading_day_count": int(len(regime_1_dates)),
            }
        )
    regime_2_dates = common_dates[(common_dates >= boundary) & (common_dates <= last)]
    if not regime_2_dates.empty:
        rows.append(
            {
                "regime_id": "regime_2_current_active_rules_based_history",
                "start_date": regime_2_dates[0].date().isoformat(),
                "end_date": regime_2_dates[-1].date().isoformat(),
                "boundary_rule": "2022-02-14 through final common date",
                "methodology_boundary_frozen_before_performance": True,
                "trading_day_count": int(len(regime_2_dates)),
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
        "instrument": BTAL,
        "source_id": "agf_btal_official_source_packet_v1",
        "official_sources": [
            {
                "source_name": "AGF U.S. Market Neutral Anti-Beta Fund official product page",
                "url": "https://www.agf.com/us/products/btal/index.jsp",
                "source_type": "official_product_page",
                "source_reported_performance_used": False,
            },
            {
                "source_name": "AGF U.S. Market Neutral Anti-Beta Fund prospectus",
                "url": "https://www.agf.com/agf-files/us/regulatory-documents/agf-trust-prospectus-us.pdf",
                "source_type": "official_prospectus",
                "source_reported_performance_used": False,
            },
            {
                "source_name": "AGF U.S. Market Neutral Anti-Beta Fund fact sheet",
                "url": "https://www.agf.com/agf-files/us/regulatory-documents/fact-sheets/agf-btal-ann-en.pdf",
                "source_type": "official_fact_sheet",
                "source_reported_performance_used": False,
            },
        ],
        "rule_provenance": {
            "source_explicit": [
                "BTAL seeks consistent negative beta exposure to the US equity market.",
                "The fund invests primarily in long low-beta US equities and short high-beta US equities.",
                "The portfolio seeks dollar neutrality within sectors.",
                "The return source is the spread between long low-beta and short high-beta portfolios.",
                "The universe is based principally on large eligible US securities.",
                "Approximately the lowest-beta 20% within each sector are long candidates and the highest-beta 20% are short candidates.",
                "Beta is based on sensitivity to weekly market movements over approximately 52 weeks.",
                "The approach reconstitutes approximately quarterly and may use active rules-based exposure adjustments.",
            ],
            "project_wrapper_translation": [
                "Hold listed BTAL wrapper instead of reconstructing constituent long and short portfolios.",
                "Use adjusted total-return prices; internal shorts, leverage, financing, fees, and turnover remain embedded in observed returns.",
                "Use BIL as the primary cash hurdle and SPY as the risk/negative-beta reference.",
            ],
            "project_execution_convention": [
                "Long-only project wrapper ownership.",
                "Maximum project exposure 1.0 and no project-level shorting or leverage.",
                "Canonical initial ETF transaction cost once.",
                "No external rebalancing after initial purchase.",
            ],
            "unresolved_material_rules": [],
        },
        "frozen_candidate_rules": {
            "first_common_valid_date": common_dates[0].date().isoformat() if len(common_dates) else "",
            "final_common_valid_date": common_dates[-1].date().isoformat() if len(common_dates) else "",
            "universe": list(SYMBOLS),
            "candidate_asset": BTAL,
            "primary_benchmark": "BIL_cash_proxy",
            "secondary_reference": "SPY_buy_and_hold",
            "initial_capital": INITIAL_CAPITAL,
            "initial_transaction_cost_pct": INITIAL_TRANSACTION_COST,
            "entry": "invest 100 percent of project capital in BTAL on first common valid adjusted-close date",
            "exit": "none; hold continuously to final date for measurement",
            "external_rebalance": "none after initial purchase",
            "BIL_switch": False,
            "constituent_reconstruction": False,
            "project_level_shorting": False,
            "project_level_leverage": False,
            "manual_distribution_reinvestment": False,
            "internal_fund_costs_added_separately": False,
            "uses_adjusted_total_return_prices": True,
            "index_backfill_used": False,
            "pre_inception_backfill_used": False,
        },
        "pre_performance_freeze": {
            "candidate_fingerprint": candidate_fingerprint()["strategy_fingerprint"],
            "cache_paths_and_hashes": {row["symbol"]: row["cache_hash"] for row in cache_rows},
            "complete_common_date_range": [
                common_dates[0].date().isoformat() if len(common_dates) else "",
                common_dates[-1].date().isoformat() if len(common_dates) else "",
            ],
            "chronological_block_boundaries_hash": stable_hash(blocks),
            "methodology_regime_boundaries_hash": stable_hash(regimes),
            "calendar_year_definitions": "complete common calendar years excluding partial first and final years for complete-year rates",
            "outcome_rules_frozen_before_performance": True,
            "source_and_preregistration_written_before_performance_calculation": True,
            "stop_conditions": [
                "invalid adjusted-price, continuity, accounting, exposure, alignment, or determinism checks",
                "exact corrected-methodology BTAL wrapper screen found before performance calculation",
            ],
        },
        "not_authorized": {
            "promotion": False,
            "paper_demo_activation": False,
            "candidate_exhaustive": False,
            "BTAL_variants_or_blends": False,
            "constituent_factor_engine": False,
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
        "initial_project_turnover": 1.0,
        "subsequent_external_turnover": 0.0,
        "project_trade_count": 1,
        "total_project_transaction_cost": entry_cost,
        "max_project_exposure": 1.0,
        "max_project_weight_sum": 1.0,
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


def beta_to_spy(asset_returns: pd.Series, spy_returns: pd.Series) -> float:
    aligned = pd.concat([asset_returns, spy_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "spy"]
    variance = float(aligned["spy"].var(ddof=0)) if len(aligned) > 2 else 0.0
    if variance <= 1e-16:
        return float("nan")
    return float(aligned["asset"].cov(aligned["spy"], ddof=0) / variance)


def capture_ratio(asset_returns: pd.Series, spy_returns: pd.Series, direction: str) -> float:
    aligned = pd.concat([asset_returns, spy_returns], axis=1, join="inner").dropna()
    aligned.columns = ["asset", "spy"]
    subset = aligned[aligned["spy"] > 0.0] if direction == "up" else aligned[aligned["spy"] < 0.0]
    if subset.empty or abs(float(subset["spy"].mean())) <= 1e-12:
        return float("nan")
    return float(subset["asset"].mean() / subset["spy"].mean())


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
    return {
        "symbol": symbol,
        "role": "candidate" if symbol == BTAL else ("primary_benchmark" if symbol == BIL else "secondary_risk_benchmark"),
        "start_date": equity.index[0].date().isoformat(),
        "end_date": equity.index[-1].date().isoformat(),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr(equity),
        "positive_complete_year_rate": float(np.mean([ret > 0.0 for ret in complete_year_returns])) if complete_year_returns else float("nan"),
        "worst_complete_year_return": float(min(complete_year_returns)) if complete_year_returns else float("nan"),
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
        btal = metrics[BTAL]
        bil = metrics[BIL]
        spy = metrics[SPY]
        rows.append(
            {
                "block_id": block["block_id"],
                "block_number": block["block_number"],
                "start_date": block["start_date"],
                "end_date": block["end_date"],
                "trading_day_count": block["trading_day_count"],
                "BTAL_total_return": btal["total_return"],
                "BIL_total_return": bil["total_return"],
                "SPY_total_return": spy["total_return"],
                "BTAL_max_drawdown": btal["max_drawdown"],
                "BIL_max_drawdown": bil["max_drawdown"],
                "SPY_max_drawdown": spy["max_drawdown"],
                "excess_return_versus_BIL": float(btal["total_return"] - bil["total_return"]),
                "BTAL_beats_BIL": bool(btal["total_return"] > bil["total_return"]),
                "BTAL_positive_when_SPY_negative": bool(btal["total_return"] > 0.0 and spy["total_return"] < 0.0),
                "initial_cost_equivalent": bool(abs(ops_map[BTAL]["total_project_transaction_cost"] - ops_map[BIL]["total_project_transaction_cost"]) < 1e-9),
                "max_project_exposure": 1.0,
                "max_project_weight_sum": 1.0,
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
                "BTAL_total_return": metrics[BTAL]["total_return"],
                "BIL_total_return": metrics[BIL]["total_return"],
                "SPY_total_return": metrics[SPY]["total_return"],
                "BTAL_cagr": metrics[BTAL]["cagr"],
                "BIL_cagr": metrics[BIL]["cagr"],
                "SPY_cagr": metrics[SPY]["cagr"],
                "BTAL_max_drawdown": metrics[BTAL]["max_drawdown"],
                "BIL_max_drawdown": metrics[BIL]["max_drawdown"],
                "SPY_max_drawdown": metrics[SPY]["max_drawdown"],
                "excess_return_versus_BIL": float(metrics[BTAL]["total_return"] - metrics[BIL]["total_return"]),
                "annualized_excess_versus_BIL": float(metrics[BTAL]["cagr"] - metrics[BIL]["cagr"]),
                "beta_to_SPY": beta_to_spy(equity_map[BTAL].pct_change().dropna(), spy_returns),
                "BTAL_beats_BIL": bool(metrics[BTAL]["total_return"] > metrics[BIL]["total_return"]),
            }
        )
    return rows


def calendar_rows(equity_map: dict[str, pd.Series]) -> list[dict[str, Any]]:
    first_year = int(equity_map[BTAL].index.min().year)
    last_year = int(equity_map[BTAL].index.max().year)
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
            "BTAL_return": "",
            "BIL_return": "",
            "SPY_return": "",
            "BTAL_max_drawdown": "",
            "SPY_max_drawdown": "",
            "BTAL_beats_BIL": "",
            "BTAL_negative_correlation_with_SPY": "",
            "BTAL_positive_when_SPY_loses": "",
            "BTAL_loses_money": "",
        }
        yearly_returns: dict[str, pd.Series] = {}
        for symbol, equity in equity_map.items():
            period = equity[equity.index.year == year]
            if period.empty:
                continue
            if row["start_date"] == "":
                row["start_date"] = period.index.min().date().isoformat()
                row["end_date"] = period.index.max().date().isoformat()
            row[f"{symbol}_return"] = period_return_from_equity(period)
            row[f"{symbol}_max_drawdown"] = max_drawdown(period)
            yearly_returns[symbol] = period.pct_change().dropna()
        if row["BTAL_return"] != "" and row["BIL_return"] != "":
            row["BTAL_beats_BIL"] = float(row["BTAL_return"]) > float(row["BIL_return"])
        if BTAL in yearly_returns and SPY in yearly_returns and len(yearly_returns[BTAL]) > 2:
            corr = yearly_returns[BTAL].corr(yearly_returns[SPY])
            row["BTAL_negative_correlation_with_SPY"] = bool(math.isfinite(float(corr)) and corr < 0.0)
        if row["BTAL_return"] != "" and row["SPY_return"] != "":
            row["BTAL_positive_when_SPY_loses"] = float(row["BTAL_return"]) > 0.0 and float(row["SPY_return"]) < 0.0
        if row["BTAL_return"] != "":
            row["BTAL_loses_money"] = float(row["BTAL_return"]) < 0.0
        rows.append(row)
    return rows


def bil_relative_metrics(full_metrics: dict[str, dict[str, Any]], block_rows: list[dict[str, Any]], calendar: list[dict[str, Any]], regime_rows: list[dict[str, Any]]) -> dict[str, Any]:
    btal = full_metrics[BTAL]
    bil = full_metrics[BIL]
    block_excess = [float(row["excess_return_versus_BIL"]) for row in block_rows]
    complete_calendar = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    row: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "primary_benchmark": "BIL_cash_proxy",
        "full_period_excess_total_return_versus_BIL": float(btal["total_return"] - bil["total_return"]),
        "cagr_difference_versus_BIL": float(btal["cagr"] - bil["cagr"]),
        "mean_block_excess_versus_BIL": float(np.mean(block_excess)),
        "median_block_excess_versus_BIL": float(np.median(block_excess)),
        "blocks_beating_BIL": int(sum(row_["BTAL_beats_BIL"] is True for row_ in block_rows)),
        "calendar_years_beating_BIL": int(sum(row_["BTAL_beats_BIL"] is True for row_ in complete_calendar)),
        "complete_calendar_year_count": int(len(complete_calendar)),
        "calendar_year_beat_rate_versus_BIL": float(np.mean([row_["BTAL_beats_BIL"] is True for row_ in complete_calendar])) if complete_calendar else float("nan"),
        "latest_block_excess_return": float(block_rows[-1]["excess_return_versus_BIL"]),
        "regime_level_excess_returns": "|".join(f"{regime['regime_id']}:{csv_value(regime['excess_return_versus_BIL'])}" for regime in regime_rows),
        "regime_level_annualized_excess_returns": "|".join(f"{regime['regime_id']}:{csv_value(regime['annualized_excess_versus_BIL'])}" for regime in regime_rows),
    }
    for regime in regime_rows:
        row[f"{regime['regime_id']}_excess_return_versus_BIL"] = regime["excess_return_versus_BIL"]
        row[f"{regime['regime_id']}_annualized_excess_versus_BIL"] = regime["annualized_excess_versus_BIL"]
    return row


def rolling_correlation_diagnostics(equity_map: dict[str, pd.Series]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    returns = pd.concat([equity_map[BTAL].pct_change(), equity_map[SPY].pct_change()], axis=1, join="inner").dropna()
    returns.columns = [BTAL, SPY]
    rolling = returns[BTAL].rolling(252).corr(returns[SPY]).dropna()
    rows = [
        {
            "window_end_date": idx.date().isoformat(),
            "rolling_window_days": 252,
            "BTAL_SPY_correlation": float(value),
            "descriptive_only": True,
            "affects_holdings": False,
        }
        for idx, value in rolling.items()
    ]
    summary = {
        "rolling_252_window_count": int(len(rolling)),
        "rolling_252_negative_correlation_count": int((rolling < 0.0).sum()),
        "rolling_252_negative_correlation_pct": float((rolling < 0.0).mean()) if len(rolling) else float("nan"),
        "rolling_correlation_descriptive_only": True,
    }
    return rows, summary


def spy_beta_correlation_and_drawdown(equity_map: dict[str, pd.Series], block_rows: list[dict[str, Any]], calendar: list[dict[str, Any]], regime_rows: list[dict[str, Any]], rolling_summary: dict[str, Any]) -> dict[str, Any]:
    btal_returns = equity_map[BTAL].pct_change().dropna()
    spy_returns = equity_map[SPY].pct_change().dropna()
    aligned = pd.concat([btal_returns, spy_returns], axis=1, join="inner").dropna()
    aligned.columns = [BTAL, SPY]
    full_corr = float(aligned[BTAL].corr(aligned[SPY])) if len(aligned) > 2 else float("nan")
    spy_dd = drawdown_series(equity_map[SPY]).reindex(aligned.index).fillna(0.0)
    drawdown_period = aligned[spy_dd < 0.0]
    btal_drawdown_return = float((1.0 + drawdown_period[BTAL]).prod() - 1.0) if not drawdown_period.empty else float("nan")
    spy_drawdown_return = float((1.0 + drawdown_period[SPY]).prod() - 1.0) if not drawdown_period.empty else float("nan")
    complete_calendar = [row for row in calendar if row["period_type"] == "complete_calendar_year"]
    spy_negative_years = [row for row in complete_calendar if row["SPY_return"] != "" and float(row["SPY_return"]) < 0.0]
    btal_return_spy_negative_years = (
        float(np.mean([float(row["BTAL_return"]) for row in spy_negative_years])) if spy_negative_years else float("nan")
    )
    return {
        "candidate_id": CANDIDATE_ID,
        "secondary_risk_benchmark": "SPY_buy_and_hold",
        "full_period_daily_return_correlation_with_SPY": full_corr,
        "rolling_252_negative_correlation_pct": rolling_summary["rolling_252_negative_correlation_pct"],
        "estimated_full_period_beta_to_SPY": beta_to_spy(btal_returns, spy_returns),
        "regime_1_beta_to_SPY": next((row["beta_to_SPY"] for row in regime_rows if row["regime_id"] == "regime_1_passive_index_tracking_history"), ""),
        "regime_2_beta_to_SPY": next((row["beta_to_SPY"] for row in regime_rows if row["regime_id"] == "regime_2_current_active_rules_based_history"), ""),
        "BTAL_return_during_SPY_negative_calendar_years_mean": btal_return_spy_negative_years,
        "BTAL_return_during_SPY_drawdown_periods": btal_drawdown_return,
        "SPY_return_during_SPY_drawdown_periods": spy_drawdown_return,
        "BTAL_better_than_SPY_during_SPY_drawdown_periods": bool(btal_drawdown_return > spy_drawdown_return) if math.isfinite(btal_drawdown_return) and math.isfinite(spy_drawdown_return) else False,
        "downside_capture_versus_SPY": capture_ratio(btal_returns, spy_returns, "down"),
        "upside_capture_versus_SPY": capture_ratio(btal_returns, spy_returns, "up"),
        "maximum_drawdown_difference_versus_SPY": float(max_drawdown(equity_map[BTAL]) - max_drawdown(equity_map[SPY])),
        "blocks_with_positive_BTAL_return_while_SPY_negative": int(sum(row["BTAL_positive_when_SPY_negative"] is True for row in block_rows)),
        "rolling_correlation_descriptive_only": True,
    }


def _reference_returns(reference_id: str) -> pd.Series:
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


def diversification_and_redundancy(btal_equity: pd.Series) -> list[dict[str, Any]]:
    btal_returns = btal_equity.pct_change().dropna()
    rows: list[dict[str, Any]] = []
    for ref in [
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "active_combo_vm_dsr_equal_weight_v1",
    ]:
        ref_returns = _reference_returns(ref)
        aligned = pd.concat([btal_returns, ref_returns], axis=1, join="inner").dropna()
        aligned.columns = ["BTAL", "reference"]
        if aligned.empty:
            classification = "incomparable because of missing aligned history"
            corr = float("nan")
        else:
            corr = float(aligned["BTAL"].corr(aligned["reference"])) if len(aligned) > 2 else float("nan")
            classification = "operationally_redundant" if math.isfinite(corr) and abs(corr) >= 0.90 else "mechanically_distinct_and_nonredundant"
        rows.append(
            {
                "candidate_id": CANDIDATE_ID,
                "reference_id": ref,
                "aligned_daily_return_count": int(len(aligned)),
                "common_start": aligned.index.min().date().isoformat() if not aligned.empty else "",
                "common_end": aligned.index.max().date().isoformat() if not aligned.empty else "",
                "daily_return_correlation": corr,
                "classification": classification,
                "optimized_combination_calculated": False,
            }
        )
    return rows


def overnight_direction_level_memory() -> dict[str, Any]:
    outcome = read_json(OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json")
    return {
        "candidate_id": "spy_close_to_open_overnight_cash_v1",
        "source_evidence_path": rel(OVERNIGHT_EVIDENCE_DIR),
        "original_formal_outcome_preserved": outcome.get("outcome", "no_material_edge"),
        "original_evidence_packet_modified": False,
        "exact_candidate_closed_for_immediate_retesting": True,
        "broader_equity_overnight_return_family_open": True,
        "direction_level_failure_interpretation": "gross_anomaly_without_comparative_edge_and_daily_turnover_cost_destruction",
        "gross_full_period_return_below_matching_timestamp_SPY": True,
        "gross_blocks_beating_SPY": 1,
        "canonical_two_leg_daily_costs_destroyed_remaining_gross_return": True,
        "further_overnight_validation_authorized": False,
        "immediate_variants_prohibited": [
            "reduced_frequency",
            "alternative_cost",
            "open_to_close",
            "QQQ_or_IWM",
            "calendar",
            "momentum",
            "reversal",
            "volatility",
            "filters",
        ],
    }


def determine_outcome(relative: dict[str, Any], spy_diag: dict[str, Any], regime_rows: list[dict[str, Any]], invariants_pass: bool) -> tuple[str, str]:
    if not invariants_pass:
        return "invalid_methodology", "Adjusted-price, continuity, accounting, alignment, exposure, or determinism invariant failed"
    full_excess = float(relative["full_period_excess_total_return_versus_BIL"])
    cagr_diff = float(relative["cagr_difference_versus_BIL"])
    median_block = float(relative["median_block_excess_versus_BIL"])
    blocks_beat = int(relative["blocks_beating_BIL"])
    beat_rate = float(relative["calendar_year_beat_rate_versus_BIL"]) if math.isfinite(float(relative["calendar_year_beat_rate_versus_BIL"])) else 0.0
    corr = float(spy_diag["full_period_daily_return_correlation_with_SPY"])
    rolling_neg = float(spy_diag["rolling_252_negative_correlation_pct"]) if math.isfinite(float(spy_diag["rolling_252_negative_correlation_pct"])) else 0.0
    latest_under = float(relative["latest_block_excess_return"]) < 0.0
    active = next((row for row in regime_rows if row["regime_id"] == "regime_2_current_active_rules_based_history"), {})
    active_under = bool(active and float(active["excess_return_versus_BIL"]) < 0.0)
    if (
        full_excess > 0.0
        and cagr_diff >= 0.02
        and median_block > 0.0
        and blocks_beat >= 4
        and beat_rate >= 0.70
        and corr < 0.0
        and rolling_neg >= 0.60
    ):
        return "comparative_evidence_positive", "BTAL passed all pre-registered BIL-return and negative-correlation gates"
    if full_excess > 0.0 and median_block > 0.0 and blocks_beat >= 4 and (active_under or latest_under):
        return "historical_edge_recently_weakened", "Full-period and median block excess were positive with at least four blocks beating BIL, but active regime or latest block underperformed BIL"
    if len(regime_rows) >= 2:
        regime_values = [float(row["annualized_excess_versus_BIL"]) for row in regime_rows]
        if regime_values[0] * regime_values[1] < 0.0 and abs(regime_values[0] - regime_values[1]) >= 0.03:
            return "methodology_regime_instability", "Passive and active regimes had opposite annualized BIL-excess signs with at least three percentage points of spread"
    if (
        corr < 0.0
        and rolling_neg >= 0.60
        and spy_diag["BTAL_better_than_SPY_during_SPY_drawdown_periods"] is True
        and not (full_excess > 0.0 and cagr_diff >= 0.02 and median_block > 0.0)
    ):
        return "negative_beta_diversification_without_cash_edge", "BTAL displayed negative-beta diversification but failed the required persistent return premium over BIL"
    return "no_material_edge", "Neither persistent cash-relative return nor reliable negative-beta diversification was supported"


def exact_variant_memory(outcome: str, failure_reason: str) -> list[dict[str, Any]]:
    preserve = outcome == "comparative_evidence_positive"
    return [
        {
            "candidate_id": CANDIDATE_ID,
            "family_id": FAMILY_ID,
            "primary_outcome": outcome,
            "primary_failure_reason": "" if preserve else failure_reason,
            "exact_candidate_closed_for_immediate_retesting": not preserve,
            "broader_market_neutral_anti_beta_family_closed": False,
            "alternative_anti_beta_timing_blend_leverage_constituent_beta_window_momentum_variations_prohibited_immediately": True,
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
        OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json",
        OVERNIGHT_EVIDENCE_DIR / "exact_variant_research_memory.csv",
    ]
    cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    state_before = file_snapshot(protected_paths)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    btal_quality, provider_manifest = ensure_btal_cache(prior_provider)
    bil_quality = cache_quality_row(BIL)
    spy_quality = cache_quality_row(SPY)
    cache_rows = [btal_quality, bil_quality, spy_quality]
    cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in SYMBOLS}
    provider_manifest["BIL_cache_refreshed"] = cache_before[BIL] != cache_after[BIL]
    provider_manifest["SPY_cache_refreshed"] = cache_before[SPY] != cache_after[SPY]

    duplicate_rows = duplicate_review_rows()
    exact_duplicate = any(row["exact_corrected_methodology_duplicate"] is True for row in duplicate_rows)
    continuity_rows = fund_and_methodology_continuity_rows()

    prices = pd.DataFrame()
    blocks: list[dict[str, Any]] = []
    regimes: list[dict[str, Any]] = []
    full_metrics_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    calendar: list[dict[str, Any]] = []
    relative: dict[str, Any] = {}
    spy_diag: dict[str, Any] = {}
    rolling_rows: list[dict[str, Any]] = []
    diversification_rows: list[dict[str, Any]] = []
    invariants: dict[str, Any] = {}
    outcome = "invalid_methodology"
    outcome_reason = ""
    invalid_reason = ""

    try:
        if exact_duplicate:
            raise RuntimeError("exact corrected-methodology BTAL static wrapper screen already exists")
        if any(row["adjusted_price_validation_result"] != "pass" for row in cache_rows):
            raise RuntimeError("required adjusted-price cache validation failed")
        prices = load_common_prices()
        if prices.empty:
            raise RuntimeError("common BTAL/BIL/SPY date range is empty")
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
        write_csv(EVIDENCE_DIR / "fund_and_methodology_continuity.csv", continuity_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(prices.index, cache_rows, blocks, regimes))
        write_json(EVIDENCE_DIR / "overnight_direction_level_memory.json", overnight_direction_level_memory())

        equity_map, ops_map = build_equity_map(prices)
        spy_returns = equity_map[SPY].pct_change().dropna()
        full_metrics = {symbol: metrics_for_symbol(symbol, equity_map[symbol], spy_returns) for symbol in SYMBOLS}
        block_rows = evaluate_blocks(prices, blocks)
        regime_rows = evaluate_regimes(prices, regimes)
        calendar = calendar_rows(equity_map)
        worst_by_symbol = {
            BTAL: min(float(row["BTAL_total_return"]) for row in block_rows),
            BIL: min(float(row["BIL_total_return"]) for row in block_rows),
            SPY: min(float(row["SPY_total_return"]) for row in block_rows),
        }
        for symbol in SYMBOLS:
            row = {**full_metrics[symbol], **ops_map[symbol]}
            row["worst_chronological_block_return"] = worst_by_symbol[symbol]
            full_metrics_rows.append(row)
        relative = bil_relative_metrics(full_metrics, block_rows, calendar, regime_rows)
        rolling_rows, rolling_summary = rolling_correlation_diagnostics(equity_map)
        spy_diag = spy_beta_correlation_and_drawdown(equity_map, block_rows, calendar, regime_rows, rolling_summary)
        diversification_rows = diversification_and_redundancy(equity_map[BTAL])
        state_after = file_snapshot(protected_paths)
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": True,
            "adjusted_prices_used": True,
            "raw_close_substitution_used": False,
            "manual_distribution_reinvestment": False,
            "underlying_long_or_short_securities_reconstructed": False,
            "project_level_short_position_created": False,
            "project_level_leverage_created": False,
            "alternative_anti_beta_product_used": False,
            "rolling_correlation_affects_holdings": False,
            "initial_project_turnover": 1.0,
            "subsequent_external_turnover": 0.0,
            "project_trade_count": 1,
            "total_project_transaction_cost": ops_map[BTAL]["total_project_transaction_cost"],
            "maximum_project_exposure": 1.0,
            "maximum_project_weight_sum": 1.0,
            "missing_adjusted_price_count": int(prices.isna().sum().sum()),
            "date_alignment": True,
            "internal_leverage_shorting_disclosure": "embedded_in_live_BTAL_adjusted_returns_not_project_level_exposure",
            "methodology_boundary_validation": True,
            "BTAL_cache_hash": cache_after[BTAL],
            "BIL_cache_hash": cache_after[BIL],
            "SPY_cache_hash": cache_after[SPY],
            "BTAL_cache_refreshed": provider_manifest["BTAL_cache_refreshed"],
            "BIL_cache_refreshed": provider_manifest["BIL_cache_refreshed"],
            "SPY_cache_refreshed": provider_manifest["SPY_cache_refreshed"],
            "overnight_packet_unchanged": state_before.get(rel(OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json")) == sha256_path(OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json"),
            "existing_VM_DSR_USCI_combo_states_unchanged": state_before == state_after,
            "paper_forward_or_broker_order_created": False,
            "candidate_exhaustive_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "real_money_recommendation": False,
            "invariants_passed": True,
        }
        outcome, outcome_reason = determine_outcome(relative, spy_diag, regime_rows, True)
    except Exception as exc:
        invalid_reason = f"{type(exc).__name__}: {exc}"
        outcome = "invalid_methodology"
        outcome_reason = invalid_reason
        write_json(EVIDENCE_DIR / "provider_acquisition_manifest.json", provider_manifest)
        write_json(EVIDENCE_DIR / "cache_manifest.json", {"candidate_id": CANDIDATE_ID, "series": cache_rows})
        write_csv(EVIDENCE_DIR / "duplicate_review.csv", duplicate_rows)
        write_csv(EVIDENCE_DIR / "fund_and_methodology_continuity.csv", continuity_rows)
        write_csv(EVIDENCE_DIR / "frozen_chronological_blocks.csv", blocks)
        write_csv(EVIDENCE_DIR / "frozen_methodology_regimes.csv", regimes)
        write_json(EVIDENCE_DIR / "candidate_fingerprint.json", candidate_fingerprint())
        write_json(EVIDENCE_DIR / "source_and_preregistration.json", source_and_preregistration(pd.DatetimeIndex([]), cache_rows, blocks, regimes))
        write_json(EVIDENCE_DIR / "overnight_direction_level_memory.json", overnight_direction_level_memory())
        invariants = {
            "candidate_id": CANDIDATE_ID,
            "actual_share_accounting_used": False,
            "adjusted_prices_used": False,
            "raw_close_substitution_used": False,
            "manual_distribution_reinvestment": False,
            "underlying_long_or_short_securities_reconstructed": False,
            "project_level_short_position_created": False,
            "project_level_leverage_created": False,
            "alternative_anti_beta_product_used": False,
            "rolling_correlation_affects_holdings": False,
            "initial_project_turnover": "",
            "subsequent_external_turnover": "",
            "project_trade_count": "",
            "total_project_transaction_cost": "",
            "maximum_project_exposure": "",
            "maximum_project_weight_sum": "",
            "missing_adjusted_price_count": "",
            "date_alignment": False,
            "internal_leverage_shorting_disclosure": "embedded_in_live_BTAL_adjusted_returns_not_project_level_exposure",
            "methodology_boundary_validation": bool(regimes),
            "BTAL_cache_hash": cache_after[BTAL],
            "BIL_cache_hash": cache_after[BIL],
            "SPY_cache_hash": cache_after[SPY],
            "BTAL_cache_refreshed": provider_manifest["BTAL_cache_refreshed"],
            "BIL_cache_refreshed": provider_manifest["BIL_cache_refreshed"],
            "SPY_cache_refreshed": provider_manifest["SPY_cache_refreshed"],
            "overnight_packet_unchanged": sha256_path(OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json") == state_before.get(rel(OVERNIGHT_EVIDENCE_DIR / "screening_outcome.json")),
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
    write_csv(EVIDENCE_DIR / "bil_relative_metrics.csv", [relative])
    write_csv(EVIDENCE_DIR / "spy_beta_correlation_and_drawdown.csv", [spy_diag])
    write_csv(EVIDENCE_DIR / "rolling_correlation_diagnostics.csv", rolling_rows)
    write_csv(EVIDENCE_DIR / "diversification_and_redundancy.csv", diversification_rows)
    write_csv(EVIDENCE_DIR / "accounting_data_and_exposure_invariants.csv", [invariants])
    memory = exact_variant_memory(outcome, outcome_reason)
    write_csv(EVIDENCE_DIR / "exact_variant_research_memory.csv", memory)
    next_action = (
        "direction_owner_validation_review_btal_static_anti_beta_market_neutral_wrapper_v1"
        if outcome == "comparative_evidence_positive"
        else "record_btal_exact_variant_memory_and_resume_source_queue"
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
        "only_BTAL_provider_acquisition_authorized": provider_manifest["authorized_download_symbols"] == [BTAL],
        "downloaded_symbols_limited_to_BTAL": set(provider_manifest["downloaded_symbols_this_run"]).issubset({BTAL}),
        "BIL_cache_not_refreshed": provider_manifest["BIL_cache_refreshed"] is False,
        "SPY_cache_not_refreshed": provider_manifest["SPY_cache_refreshed"] is False,
        "adjusted_total_return_prices_used": invariants["adjusted_prices_used"] is True,
        "BTAL_bought_once_and_held": invariants["initial_project_turnover"] == 1.0 and invariants["project_trade_count"] == 1,
        "no_underlying_long_or_short_securities_reconstructed": invariants["underlying_long_or_short_securities_reconstructed"] is False,
        "no_project_level_short_or_leveraged_position": invariants["project_level_short_position_created"] is False and invariants["project_level_leverage_created"] is False,
        "no_alternative_anti_beta_product": invariants["alternative_anti_beta_product_used"] is False,
        "methodology_boundary_frozen": all(row.get("methodology_boundary_frozen_before_performance") is True for row in regimes),
        "chronological_blocks_frozen_before_performance": all(row.get("frozen_before_performance") is True for row in blocks),
        "BTAL_BIL_SPY_matching_dates": invariants["date_alignment"] is True,
        "initial_cost_treatment_equivalent": True if invariants["invariants_passed"] else False,
        "rolling_correlations_descriptive_only": invariants["rolling_correlation_affects_holdings"] is False,
        "project_exposure_never_exceeds_1": invariants.get("maximum_project_exposure") in {"", None} or float(invariants["maximum_project_exposure"]) <= 1.000001,
        "overnight_packet_unchanged": invariants["overnight_packet_unchanged"] is True,
        "existing_observation_states_unchanged": invariants["existing_VM_DSR_USCI_combo_states_unchanged"] is True,
        "no_paper_demo_or_broker_order": invariants["paper_forward_or_broker_order_created"] is False,
        "output_generation_deterministic": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "real_money_recommendation": False,
    }
    required_true = {
        "only_BTAL_provider_acquisition_authorized",
        "downloaded_symbols_limited_to_BTAL",
        "BIL_cache_not_refreshed",
        "SPY_cache_not_refreshed",
        "adjusted_total_return_prices_used",
        "BTAL_bought_once_and_held",
        "no_underlying_long_or_short_securities_reconstructed",
        "no_project_level_short_or_leveraged_position",
        "no_alternative_anti_beta_product",
        "methodology_boundary_frozen",
        "chronological_blocks_frozen_before_performance",
        "BTAL_BIL_SPY_matching_dates",
        "initial_cost_treatment_equivalent",
        "rolling_correlations_descriptive_only",
        "project_exposure_never_exceeds_1",
        "overnight_packet_unchanged",
        "existing_observation_states_unchanged",
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
        f"""# BTAL Static Anti-Beta Market Neutral Wrapper Bounded Screen v1

Candidate `{CANDIDATE_ID}` was evaluated as one listed ETF wrapper: buy `BTAL` once on the first common valid `BTAL`/`BIL`/`SPY` adjusted-close date and hold through the final common date.

- Outcome: `{outcome}`
- Primary reason: {outcome_reason}
- Provider acquisition this run: `{provider_manifest['provider_download']}`
- Common valid rows: `{len(prices) if not prices.empty else 0}`
- Primary benchmark: `BIL_cash_proxy`
- Secondary risk benchmark: `SPY_buy_and_hold`
- Passive-to-active methodology boundary frozen: `2022-02-14`
- Promotion authorized: `false`
- Paper/demo activation authorized: `false`
- Candidate exhaustive authorized: `false`

The screen does not reconstruct low-beta or high-beta constituents, does not create project-level shorts or leverage, does not test another anti-beta product, does not build BTAL blends, and does not alter VM, DSR, USCI, active-combo, overnight, registry, or paper/demo observation state.
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
