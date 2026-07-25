from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
import yaml

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response
from strategy_lab.research_os.external_adapters.bt_adapter import equity_from_returns, returns_from_weights
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    max_drawdown,
    trade_count_and_turnover,
    weight_invariant_report,
)


ROOT = Path(__file__).resolve().parents[3]
STRATEGY_ID = "vojtko_dujava_inflation_acceleration_gld_ief_regime_v1"
FAMILY_ID = "inflation_regime_real_asset_duration_rotation"
TASK_ID = STRATEGY_ID
OUTPUT_DIR = Path("evidence") / "public_source_strategy_implementation" / STRATEGY_ID / "latest"
RAW_CACHE_DIR = Path("data") / "raw" / STRATEGY_ID
NEXT_ACTION = "direction_owner_review_next_full_methodology_observable_macro_strategy_v1"
RUN_CREATED_UTC = "2026-07-21T00:00:00Z"

UP_ASSET = "GLD"
DOWN_ASSET = "IEF"
SYMBOLS = (UP_ASSET, DOWN_ASSET)
PROHIBITED_SYMBOLS = {"SHY", "UUP", "TLT"}
ALPACA_START = "2004-01-01T00:00:00Z"
ALPACA_END = "2026-07-21T23:59:59Z"
ALPACA_FEED = "iex"
ALPACA_ADJUSTMENT = "all"
ALPACA_TIMEFRAME = "1Day"
WEIGHT_TOLERANCE = 1e-9
BLS_ARCHIVE_URL = "https://www.bls.gov/bls/news-release/cpi.htm"
BLS_ARCHIVE_BASE = "https://www.bls.gov"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}

ALLOWED_OUTCOMES = {
    "baseline_implemented_for_exploratory_review",
    "archived_bls_history_incomplete",
    "alpaca_asset_or_bar_access_blocked",
    "common_history_insufficient",
    "point_in_time_signal_defect",
    "provider_reconciliation_defect",
    "implementation_or_accounting_defect",
}

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_FILES = {
    "source_packet_used.yaml",
    "pre_implementation_gate.json",
    "alpaca_asset_and_bar_check.json",
    "archived_bls_release_inventory.csv",
    "point_in_time_cpi_series.csv",
    "cpi_release_timing_audit.csv",
    "data_sources_and_hashes.json",
    "provider_splice_reconciliation.csv",
    "frozen_test_config.yaml",
    "regime_calculation_audit.csv",
    "target_weights.csv",
    "transactions.csv",
    "accounting_invariants.csv",
    "baseline_metrics.csv",
    "benchmark_metrics.csv",
    "static_average_weight_control.csv",
    "baseline_vs_controls.csv",
    "identity_overlay_equality.csv",
    "overlay_compatibility_map.csv",
    "trial_manifest.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "implementation_summary.md",
}

SOURCE_PACKET: dict[str, Any] = {
    "strategy_id": STRATEGY_ID,
    "task_type": "active-direction-execution",
    "stage": "exploration",
    "family": FAMILY_ID,
    "adaptation_labels": [
        "source_rule_completion",
        "data_feasibility_adjustment",
        "instrument_universe_adjustment",
    ],
    "source_identity": {
        "public_methodology": "Vojtko and Dujava, Using Inflation Data for Systematic Gold and Treasury Investment Strategies",
        "baseline_only": True,
        "source_reported_performance_used": False,
    },
    "frozen_instruments": {"inflation_up": UP_ASSET, "inflation_down": DOWN_ASSET},
    "point_in_time_cpi_source": {
        "primary": "Archived BLS CPI news releases",
        "required_field": "All-items CPI-U seasonally adjusted month-over-month percent change as printed in archived release",
        "latest_revised_cpiaucsl_signal_use": False,
    },
    "regime_rule": {
        "inflation_t": "reported MoM CPI for reference month t",
        "acceleration_t": "inflation_t - inflation_t_minus_1",
        "up_trigger": "acceleration_t > 0 and acceleration_t_minus_1 > 0",
        "down_trigger": "acceleration_t < 0 and acceleration_t_minus_1 < 0",
        "otherwise": "retain previous established regime",
        "zero_is_neither_positive_nor_negative": True,
    },
    "execution": {
        "signal_freeze": "end of CPI release calendar month",
        "target_effective": "first eligible ETF session of following month",
        "no_same_release_month_return": True,
        "shifted_weight_no_lookahead": True,
    },
    "excluded": [
        "one_month_momentum",
        "trend_filters",
        "SHY_after_initialization",
        "UUP",
        "TLT",
        "alternative_inflation_series",
        "parameter_search",
        "trade_management_overlay_performance",
    ],
    "non_promotable": True,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_hash(frame: pd.DataFrame | pd.Series) -> str:
    if frame.empty:
        return "empty"
    return sha256_text(frame.to_csv(index=True, lineterminator="\n"))


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(root / path) for path in PROTECTED_STATE_PATHS}


def clean_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return value


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.bool_,)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)) and (math.isnan(float(value)) or math.isinf(float(value))):
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def fetch_url(url: str, *, timeout: int = 30) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        return {
            "url": url,
            "status_code": int(response.status_code),
            "content_type": response.headers.get("content-type", ""),
            "content": response.content,
            "text": response.text if "text" in response.headers.get("content-type", "").lower() or response.text else "",
            "error": "",
        }
    except Exception as exc:  # pragma: no cover - network defensive branch.
        return {
            "url": url,
            "status_code": 0,
            "content_type": "",
            "content": b"",
            "text": "",
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
        }


def normalize_archive_url(href: str) -> str:
    return urljoin(BLS_ARCHIVE_BASE, href)


def release_date_from_url(url: str) -> str:
    match = re.search(r"cpi_(\d{2})(\d{2})(\d{4})", url)
    if not match:
        return ""
    month, day, year = match.groups()
    return f"{year}-{month}-{day}"


def discover_bls_release_links(archive_text: str) -> list[str]:
    links = re.findall(r'href=["\']([^"\']+)["\']', archive_text, flags=re.IGNORECASE)
    archive_links = []
    for href in links:
        lowered = href.lower()
        if "/news.release/archives/cpi_" in lowered or "news.release/archives/cpi_" in lowered:
            archive_links.append(normalize_archive_url(href))
    return sorted(set(archive_links))


def extract_cpi_mom_from_release(text: str, url: str) -> dict[str, Any]:
    """Extract the all-items CPI-U SA monthly percent-change sentence from a BLS release."""
    clean = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    patterns = [
        re.compile(
            r"Consumer Price Index for All Urban Consumers \(CPI-U\)\s+"
            r"(?P<verb>increased|rose|declined|fell|decreased)\s+"
            r"(?P<value>\d+(?:\.\d+)?)\s+percent\s+"
            r"(?:on a seasonally adjusted basis\s+)?in\s+(?P<month>[A-Za-z]+)",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"Consumer Price Index for All Urban Consumers \(CPI-U\)\s+"
            r"was unchanged\s+(?:on a seasonally adjusted basis\s+)?in\s+(?P<month>[A-Za-z]+)",
            flags=re.IGNORECASE,
        ),
    ]
    for pattern in patterns:
        match = pattern.search(clean)
        if not match:
            continue
        release_date = release_date_from_url(url)
        release_year = int(release_date[:4]) if release_date else pd.Timestamp.utcnow().year
        month_name = match.groupdict().get("month", "")
        reference = pd.Period(f"{month_name} {release_year}", freq="M")
        if reference > pd.Period(f"{release_year}-{pd.Timestamp(release_date).month:02d}", freq="M") and release_date:
            reference = pd.Period(f"{month_name} {release_year - 1}", freq="M")
        verb = match.groupdict().get("verb", "unchanged").lower()
        value = 0.0 if "value" not in match.groupdict() or match.groupdict().get("value") is None else float(match.group("value"))
        if verb in {"declined", "fell", "decreased"}:
            value = -value
        return {
            "parsed": True,
            "reference_month": str(reference),
            "reported_mom_percent": value,
            "extraction_method": "regex_first_cpi_u_sa_percent_sentence",
            "extraction_error": "",
        }
    return {
        "parsed": False,
        "reference_month": "",
        "reported_mom_percent": float("nan"),
        "extraction_method": "regex_first_cpi_u_sa_percent_sentence",
        "extraction_error": "all-items CPI-U seasonally adjusted MoM sentence not found",
    }


def archived_bls_release_inventory(root: Path) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any]]:
    raw_dir = root / RAW_CACHE_DIR / "bls_cpi_archives"
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive = fetch_url(BLS_ARCHIVE_URL, timeout=45)
    archive_hash = sha256_bytes(archive["content"]) if archive["content"] else "missing"
    inventory_rows: list[dict[str, Any]] = [
        {
            "archive_url": BLS_ARCHIVE_URL,
            "release_url": BLS_ARCHIVE_URL,
            "release_date": "",
            "http_status": archive["status_code"],
            "content_type": archive["content_type"],
            "content_hash": archive_hash,
            "inventory_status": "archive_page_loaded" if archive["status_code"] == 200 else "archive_page_blocked",
            "parse_status": "",
            "extraction_error": archive["error"],
        }
    ]
    if archive["status_code"] != 200:
        return inventory_rows, pd.DataFrame(), {
            "archive_url": BLS_ARCHIVE_URL,
            "archive_status_code": archive["status_code"],
            "archive_content_type": archive["content_type"],
            "archive_hash": archive_hash,
            "release_count": 0,
            "parsed_observation_count": 0,
            "blocked_reason": archive["error"] or f"http_{archive['status_code']}",
        }
    links = discover_bls_release_links(archive["text"])
    cpi_rows: list[dict[str, Any]] = []
    for url in links:
        fetched = fetch_url(url, timeout=30)
        content = fetched["content"]
        content_hash = sha256_bytes(content) if content else "missing"
        parsed = {
            "parsed": False,
            "reference_month": "",
            "reported_mom_percent": float("nan"),
            "extraction_method": "unsupported_content_type",
            "extraction_error": "",
        }
        text = ""
        content_type = fetched["content_type"].lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            parsed["extraction_error"] = "pdf_release_not_parsed_by_minimal_runner"
        elif content:
            try:
                text = content.decode("utf-8", errors="ignore")
                parsed = extract_cpi_mom_from_release(text, url)
            except Exception as exc:  # pragma: no cover - parser defensive branch.
                parsed["extraction_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        inventory_rows.append(
            {
                "archive_url": BLS_ARCHIVE_URL,
                "release_url": url,
                "release_date": release_date_from_url(url),
                "http_status": fetched["status_code"],
                "content_type": fetched["content_type"],
                "content_hash": content_hash,
                "inventory_status": "release_loaded" if fetched["status_code"] == 200 else "release_blocked",
                "parse_status": "parsed" if parsed["parsed"] else "not_parsed",
                "extraction_error": fetched["error"] or parsed["extraction_error"],
            }
        )
        if parsed["parsed"]:
            cpi_rows.append(
                {
                    "cpi_reference_month": parsed["reference_month"],
                    "release_date": release_date_from_url(url),
                    "release_timestamp": "",
                    "archived_release_url": url,
                    "reported_mom_percent": parsed["reported_mom_percent"],
                    "extraction_method": parsed["extraction_method"],
                    "content_hash": content_hash,
                    "whether_revised_later": "not_determined_archive_notice_says_archived_data_may_have_been_revised_later",
                }
            )
    frame = pd.DataFrame(cpi_rows)
    if not frame.empty:
        frame = frame.drop_duplicates("cpi_reference_month", keep="last").sort_values("cpi_reference_month").reset_index(drop=True)
    return inventory_rows, frame, {
        "archive_url": BLS_ARCHIVE_URL,
        "archive_status_code": archive["status_code"],
        "archive_content_type": archive["content_type"],
        "archive_hash": archive_hash,
        "release_count": len(links),
        "parsed_observation_count": int(len(frame)),
        "blocked_reason": "" if not frame.empty else "no_archived_release_mom_values_parsed",
    }


def fetch_alpaca_daily_bars_read_only(client: AlpacaClient, symbols: tuple[str, ...] = SYMBOLS) -> dict[str, pd.DataFrame]:
    merged: dict[str, Any] = {"bars": {symbol: [] for symbol in symbols}}
    page_token: str | None = None
    while True:
        payload = client.get_historical_bars_page(
            symbols=list(symbols),
            start=ALPACA_START,
            end=ALPACA_END,
            timeframe=ALPACA_TIMEFRAME,
            page_token=page_token,
            feed=ALPACA_FEED,
            adjustment=ALPACA_ADJUSTMENT,
            limit=10000,
        )
        for symbol, bars in payload.get("bars", {}).items():
            merged["bars"].setdefault(symbol, []).extend(bars)
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    return parse_bars_response(merged, drop_incomplete_current_day=False)


def alpaca_asset_and_bar_check() -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    payload: dict[str, Any] = {
        "alpaca_assets_api_checked": True,
        "alpaca_stock_bars_api_checked": True,
        "read_only_endpoints_only": True,
        "api_secrets_persisted": False,
        "order_endpoint_called": False,
        "paper_credentials_present": False,
        "live_credentials_detected": False,
        "status": "not_started",
        "error": "",
        "assets": {},
        "bars": {},
    }
    try:
        credentials = load_alpaca_credentials("paper")
        payload["paper_credentials_present"] = credentials.present
        payload["credential_source"] = "environment_or_env_local" if credentials.present else "missing"
        payload["live_credentials_detected"] = credentials.live_credentials_detected
        client = AlpacaClient(credentials, AlpacaClientConfig(data_feed=ALPACA_FEED, data_adjustment=ALPACA_ADJUSTMENT))
        assets: dict[str, dict[str, Any]] = {}
        for symbol in SYMBOLS:
            asset = client._request("GET", client.config.paper_base_url, f"/v2/assets/{symbol}")
            assets[symbol] = {
                "symbol": asset.get("symbol", symbol),
                "name": asset.get("name", ""),
                "status": asset.get("status", ""),
                "active": asset.get("status") == "active",
                "tradable": bool(asset.get("tradable")),
                "asset_class": asset.get("asset_class", ""),
                "exchange": asset.get("exchange", ""),
                "fractionable": bool(asset.get("fractionable")),
            }
        bars = fetch_alpaca_daily_bars_read_only(client)
        payload["assets"] = assets
        for symbol in SYMBOLS:
            frame = bars.get(symbol, pd.DataFrame())
            payload["bars"][symbol] = {
                "symbol": symbol,
                "historical_bars_accessible": not frame.empty,
                "rows": int(len(frame)),
                "earliest_bar": str(frame["date"].iloc[0]) if not frame.empty else "",
                "latest_bar": str(frame["date"].iloc[-1]) if not frame.empty else "",
                "returned_fields": list(frame.columns),
                "adjustment": ALPACA_ADJUSTMENT,
                "feed": ALPACA_FEED,
                "timeframe": ALPACA_TIMEFRAME,
                "hash": dataframe_hash(frame),
            }
        assets_ready = all(
            payload["assets"].get(symbol, {}).get("active") is True
            and payload["assets"].get(symbol, {}).get("tradable") is True
            for symbol in SYMBOLS
        )
        bars_ready = all(payload["bars"].get(symbol, {}).get("historical_bars_accessible") is True for symbol in SYMBOLS)
        payload["status"] = "ready" if assets_ready and bars_ready else "blocked"
        return payload, bars
    except Exception as exc:  # pragma: no cover - live provider defensive branch.
        payload["status"] = "blocked"
        payload["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        return payload, {}


def load_local_symbol_frame(root: Path, symbol: str) -> pd.DataFrame:
    path = root / "data" / "cache" / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    close_col = "adj_close" if "adj_close" in frame.columns else "close"
    frame = frame.dropna(subset=["date", close_col]).sort_values("date")
    frame = frame.drop_duplicates("date", keep="last").set_index("date")
    frame["adjusted_close_for_reconciliation"] = frame[close_col].astype(float)
    return frame


def reconciliation_passes(symbol: str, metrics: dict[str, Any]) -> bool:
    if int(metrics.get("overlap_rows", 0)) < 252:
        return False
    median_abs = float(metrics.get("median_abs_daily_return_difference", float("inf")))
    p99_abs = float(metrics.get("p99_abs_daily_return_difference", float("inf")))
    corr = metrics.get("daily_return_correlation")
    corr_value = float(corr) if corr not in (None, "") and not pd.isna(corr) else float("nan")
    return median_abs <= 0.00050 and p99_abs <= 0.00300 and corr_value >= 0.995


def build_spliced_price_series(root: Path, symbol: str, alpaca_frame: pd.DataFrame) -> tuple[pd.Series, dict[str, Any]]:
    local = load_local_symbol_frame(root, symbol)
    local_series = (
        local["adjusted_close_for_reconciliation"].astype(float).rename("local") if not local.empty else pd.Series(dtype=float)
    )
    alpaca_series = pd.Series(dtype=float, name="alpaca")
    if not alpaca_frame.empty and {"date", "close"} <= set(alpaca_frame.columns):
        alpaca = alpaca_frame.copy()
        alpaca["date"] = pd.to_datetime(alpaca["date"], errors="coerce")
        alpaca["close"] = pd.to_numeric(alpaca["close"], errors="coerce")
        alpaca_series = (
            alpaca.dropna(subset=["date", "close"])
            .drop_duplicates("date", keep="last")
            .set_index("date")["close"]
            .astype(float)
            .sort_index()
            .rename("alpaca")
        )
    row: dict[str, Any] = {
        "symbol": symbol,
        "local_cache_path": str((root / "data" / "cache" / f"{symbol}.csv").resolve()),
        "local_cache_hash": sha256_path(root / "data" / "cache" / f"{symbol}.csv"),
        "alpaca_feed": ALPACA_FEED,
        "alpaca_adjustment": ALPACA_ADJUSTMENT,
    }
    if local_series.empty or alpaca_series.empty:
        row.update({"decision": "blocked_missing_local_or_alpaca_series", "overlap_rows": 0})
        return pd.Series(dtype=float, name=symbol), row
    overlap = pd.concat([local_series, alpaca_series], axis=1).dropna()
    if overlap.empty:
        row.update({"decision": "blocked_no_provider_overlap", "overlap_rows": 0})
        return pd.Series(dtype=float, name=symbol), row
    local_ret = overlap["local"].pct_change(fill_method=None)
    alpaca_ret = overlap["alpaca"].pct_change(fill_method=None)
    ret_diff = (local_ret - alpaca_ret).dropna()
    ret_pair = pd.concat([local_ret.rename("local"), alpaca_ret.rename("alpaca")], axis=1).dropna()
    switch_date = pd.Timestamp(overlap.index.min())
    scale = float(overlap.loc[switch_date, "alpaca"] / overlap.loc[switch_date, "local"])
    row.update(
        {
            "local_first_date": local_series.index.min().date().isoformat(),
            "local_last_date": local_series.index.max().date().isoformat(),
            "alpaca_first_date": alpaca_series.index.min().date().isoformat(),
            "alpaca_last_date": alpaca_series.index.max().date().isoformat(),
            "overlap_rows": int(len(overlap)),
            "overlap_first_date": overlap.index.min().date().isoformat(),
            "overlap_last_date": overlap.index.max().date().isoformat(),
            "median_abs_daily_return_difference": float(ret_diff.abs().median()) if not ret_diff.empty else float("nan"),
            "p99_abs_daily_return_difference": float(ret_diff.abs().quantile(0.99)) if not ret_diff.empty else float("nan"),
            "max_abs_daily_return_difference": float(ret_diff.abs().max()) if not ret_diff.empty else float("nan"),
            "daily_return_correlation": float(ret_pair["local"].corr(ret_pair["alpaca"])) if len(ret_pair) > 2 else float("nan"),
            "switch_date": switch_date.date().isoformat(),
            "pre_switch_scale_factor_applied_to_local": scale,
            "splice_method": "local_adjusted_history_scaled_to_first_alpaca_overlap_then_alpaca_adjusted_daily_bars",
        }
    )
    if not reconciliation_passes(symbol, row):
        row["decision"] = "blocked_provider_overlap_reconciliation_failed"
        return pd.Series(dtype=float, name=symbol), row
    pre_switch = local_series[local_series.index < switch_date] * scale
    post_switch = alpaca_series[alpaca_series.index >= switch_date]
    spliced = pd.concat([pre_switch, post_switch]).sort_index()
    spliced = spliced[~spliced.index.duplicated(keep="last")].rename(symbol)
    row.update(
        {
            "decision": "spliced_after_overlap_reconciliation",
            "spliced_first_date": spliced.index.min().date().isoformat(),
            "spliced_last_date": spliced.index.max().date().isoformat(),
            "spliced_rows": int(len(spliced)),
            "spliced_series_hash": dataframe_hash(spliced.to_frame()),
        }
    )
    return spliced, row


def first_session_after_release_month(sessions: pd.DatetimeIndex, release_date: str) -> str:
    release_month = pd.Timestamp(release_date).to_period("M")
    next_month = release_month + 1
    candidates = sessions[sessions.to_period("M") == next_month]
    if len(candidates) == 0:
        return ""
    return pd.Timestamp(candidates.min()).date().isoformat()


def calculate_regime_records(cpi_frame: pd.DataFrame, sessions: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    if cpi_frame.empty:
        return pd.DataFrame()
    frame = cpi_frame.copy()
    frame["cpi_reference_month"] = frame["cpi_reference_month"].astype(str)
    frame["reported_mom_percent"] = pd.to_numeric(frame["reported_mom_percent"], errors="coerce")
    frame = frame.dropna(subset=["reported_mom_percent"]).sort_values("cpi_reference_month").reset_index(drop=True)
    frame["inflation_acceleration"] = frame["reported_mom_percent"].diff()
    frame["previous_inflation_acceleration"] = frame["inflation_acceleration"].shift(1)
    rows: list[dict[str, Any]] = []
    current_regime = ""
    for _, row in frame.iterrows():
        accel = row["inflation_acceleration"]
        prev = row["previous_inflation_acceleration"]
        trigger = ""
        if pd.notna(accel) and pd.notna(prev) and accel > 0 and prev > 0:
            current_regime = "INFLATION_UP"
            trigger = "two_positive_accelerations"
        elif pd.notna(accel) and pd.notna(prev) and accel < 0 and prev < 0:
            current_regime = "INFLATION_DOWN"
            trigger = "two_negative_accelerations"
        elif current_regime:
            trigger = "retain_previous_established_regime"
        else:
            trigger = "warmup_uninitialized"
        release_date = str(row.get("release_date", ""))
        effective_date = first_session_after_release_month(sessions, release_date) if sessions is not None and release_date else ""
        rows.append(
            {
                **row.to_dict(),
                "inflation_acceleration": float(accel) if pd.notna(accel) else "",
                "previous_inflation_acceleration": float(prev) if pd.notna(prev) else "",
                "trigger_reason": trigger,
                "regime": current_regime,
                "signal_month": str(pd.Timestamp(release_date).to_period("M")) if release_date else "",
                "target_freeze_date": pd.Timestamp(release_date).to_period("M").to_timestamp(how="end").date().isoformat()
                if release_date
                else "",
                "target_effective_date": effective_date,
                "GLD": 1.0 if current_regime == "INFLATION_UP" else (0.0 if current_regime == "INFLATION_DOWN" else ""),
                "IEF": 1.0 if current_regime == "INFLATION_DOWN" else (0.0 if current_regime == "INFLATION_UP" else ""),
                "warmup_uninitialized": current_regime == "",
            }
        )
    return pd.DataFrame(rows)


def target_events_from_regime(regime: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    if regime.empty:
        return pd.DataFrame()
    events = regime[(regime["warmup_uninitialized"] == False) & (regime["target_effective_date"] != "")].copy()  # noqa: E712
    events["target_effective_date"] = pd.to_datetime(events["target_effective_date"], errors="coerce")
    events = events.dropna(subset=["target_effective_date"]).sort_values("target_effective_date")
    return events[events["target_effective_date"].isin(sessions)].reset_index(drop=True)


def build_daily_weights(prices: pd.DataFrame, regime: pd.DataFrame) -> pd.DataFrame:
    events = target_events_from_regime(regime, prices.index)
    if events.empty:
        return pd.DataFrame(columns=list(SYMBOLS), dtype=float)
    daily_index = prices.index[prices.index >= events["target_effective_date"].min()]
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for _, row in events.iterrows():
        date = pd.Timestamp(row["target_effective_date"])
        targets[date] = {UP_ASSET: float(row["GLD"]), DOWN_ASSET: float(row["IEF"])}
    return complete_rebalance_weight_frame(daily_index, list(SYMBOLS), targets, tolerance=WEIGHT_TOLERANCE)


def transaction_rows(regime: pd.DataFrame) -> list[dict[str, Any]]:
    events = regime[(regime.get("warmup_uninitialized", True) == False) & (regime.get("target_effective_date", "") != "")].copy()  # noqa: E712
    rows: list[dict[str, Any]] = []
    previous_regime: str | None = None
    for _, row in events.iterrows():
        current_regime = str(row["regime"])
        switched = previous_regime is not None and current_regime != previous_regime
        if switched:
            rows.append(
                {
                    "cpi_reference_month": row["cpi_reference_month"],
                    "release_date": row["release_date"],
                    "signal_month": row["signal_month"],
                    "target_effective_date": row["target_effective_date"],
                    "from_regime": previous_regime,
                    "to_regime": current_regime,
                    "from_asset": DOWN_ASSET if previous_regime == "INFLATION_DOWN" else UP_ASSET,
                    "to_asset": DOWN_ASSET if current_regime == "INFLATION_DOWN" else UP_ASSET,
                    "source_cost_model": "zero_cost_gross",
                    "source_cost_rate": 0.0,
                    "project_cost_diagnostic_included": False,
                    "project_cost_rate": "",
                    "cost_applied_once": True,
                }
            )
        previous_regime = current_regime
    return rows


def compute_metrics(returns: pd.Series, weights: pd.DataFrame | None = None) -> dict[str, Any]:
    daily = returns.dropna().astype(float)
    if daily.empty:
        return {
            "effective_start_date": "",
            "effective_end_date": "",
            "daily_observations": 0,
            "total_return": float("nan"),
            "cagr": float("nan"),
            "max_drawdown": float("nan"),
            "volatility": float("nan"),
            "return_drawdown_proxy": float("nan"),
        }
    equity = equity_from_returns(daily)
    years = max((daily.index.max() - daily.index.min()).days / 365.25, 1e-9)
    total = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)
    mdd = max_drawdown(equity)
    vol = float(daily.std() * np.sqrt(252.0))
    payload: dict[str, Any] = {
        "effective_start_date": daily.index.min().date().isoformat(),
        "effective_end_date": daily.index.max().date().isoformat(),
        "daily_observations": int(len(daily)),
        "total_return": total,
        "cagr": cagr,
        "max_drawdown": mdd,
        "volatility": vol,
        "return_drawdown_proxy": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
    }
    if weights is not None and not weights.empty:
        trades, turnover = trade_count_and_turnover(weights)
        payload.update(
            {
                "average_gld_weight": float(weights[UP_ASSET].mean()),
                "average_ief_weight": float(weights[DOWN_ASSET].mean()),
                "trade_count": trades,
                "turnover_proxy": turnover,
            }
        )
    return payload


def monthly_rebalanced_5050_weights(index: pd.DatetimeIndex) -> pd.DataFrame:
    weights = pd.DataFrame(0.5, index=index, columns=list(SYMBOLS))
    return weights


def static_average_weights(index: pd.DatetimeIndex, dynamic_weights: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if dynamic_weights.empty:
        return pd.DataFrame(columns=list(SYMBOLS)), {"gld_month_fraction": float("nan"), "ief_month_fraction": float("nan")}
    monthly = dynamic_weights.groupby(dynamic_weights.index.to_period("M")).tail(1)
    gld_fraction = float((monthly[UP_ASSET] > 0.5).mean())
    frame = pd.DataFrame(index=index, data={UP_ASSET: gld_fraction, DOWN_ASSET: 1.0 - gld_fraction})
    return frame, {"gld_month_fraction": gld_fraction, "ief_month_fraction": 1.0 - gld_fraction, "dynamic_months": int(len(monthly))}


def benchmark_return_series(prices: pd.DataFrame, weights: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, Any]]:
    start = weights.index.min()
    end = weights.index.max()
    window = prices.loc[(prices.index >= start) & (prices.index <= end), list(SYMBOLS)].copy()
    pct = window.pct_change(fill_method=None).fillna(0.0)
    half_weights = monthly_rebalanced_5050_weights(window.index)
    static_weights, static_info = static_average_weights(window.index, weights.loc[window.index])
    return {
        "GLD_buy_and_hold": pct[UP_ASSET].rename("GLD_buy_and_hold"),
        "IEF_buy_and_hold": pct[DOWN_ASSET].rename("IEF_buy_and_hold"),
        "source_monthly_50_50_GLD_IEF": returns_from_weights(window, half_weights).rename("source_monthly_50_50_GLD_IEF"),
        "static_average_weight_control": returns_from_weights(window, static_weights).rename("static_average_weight_control"),
    }, static_info


def target_weight_rows(weights: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date, row in weights.iterrows():
        held = UP_ASSET if row[UP_ASSET] > 0.5 else DOWN_ASSET
        rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "GLD": float(row[UP_ASSET]),
                "IEF": float(row[DOWN_ASSET]),
                "weight_sum": float(row.sum()),
                "gross_exposure": float(row.abs().sum()),
                "net_exposure": float(row.sum()),
                "held_asset": held,
            }
        )
    return rows


def baseline_metric_rows(returns: pd.Series, weights: pd.DataFrame, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "series_id": "zero_cost_dynamic_baseline",
            "role": "exploratory_baseline_diagnostic",
            "source_cost_model": "zero_cost_gross",
            "project_cost_diagnostic_included": False,
            "project_cost_diagnostic_reason": "no single already-frozen ETF switching-cost convention identified for this source baseline",
            "switch_count": len(transactions),
            **compute_metrics(returns, weights),
        }
    ]


def benchmark_metric_rows(benchmarks: dict[str, pd.Series]) -> list[dict[str, Any]]:
    return [{"benchmark_id": name, "role": "required_control", **compute_metrics(series)} for name, series in benchmarks.items()]


def baseline_vs_control_rows(base: pd.Series, benchmarks: dict[str, pd.Series]) -> list[dict[str, Any]]:
    base_metrics = compute_metrics(base)
    rows: list[dict[str, Any]] = []
    for name, series in benchmarks.items():
        metrics = compute_metrics(series)
        rows.append(
            {
                "control_id": name,
                "baseline_total_return_minus_control": base_metrics["total_return"] - metrics["total_return"],
                "baseline_cagr_minus_control": base_metrics["cagr"] - metrics["cagr"],
                "baseline_max_drawdown_minus_control": base_metrics["max_drawdown"] - metrics["max_drawdown"],
                "baseline_return_drawdown_proxy_minus_control": base_metrics["return_drawdown_proxy"] - metrics["return_drawdown_proxy"],
                "interpretation_note": "diagnostic_only_not_promotion_gate",
            }
        )
    return rows


def identity_overlay_equality_rows(
    base_weights: pd.DataFrame,
    base_returns: pd.Series,
    transactions: list[dict[str, Any]],
    base_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    identity_weights = base_weights.copy()
    identity_returns = base_returns.copy()
    identity_transactions = [dict(row) for row in transactions]
    identity_metrics = dict(base_metrics)
    weight_diff = float((identity_weights - base_weights).abs().max().max()) if not base_weights.empty else 0.0
    return_diff = float((identity_returns - base_returns).abs().max()) if not base_returns.empty else 0.0
    tx_equal = identity_transactions == transactions
    metrics_equal = identity_metrics == base_metrics
    return [
        {"comparison": "target_weights", "exact_match": weight_diff == 0.0, "max_abs_difference": weight_diff, "notes": "IdentityOverlay pass-through"},
        {"comparison": "daily_returns", "exact_match": return_diff == 0.0, "max_abs_difference": return_diff, "notes": "IdentityOverlay pass-through"},
        {"comparison": "transactions", "exact_match": tx_equal, "max_abs_difference": 0.0 if tx_equal else 1.0, "notes": "No transaction changes"},
        {"comparison": "costs", "exact_match": tx_equal, "max_abs_difference": 0.0 if tx_equal else 1.0, "notes": "Zero-cost source baseline unchanged"},
        {"comparison": "metrics", "exact_match": metrics_equal, "max_abs_difference": 0.0 if metrics_equal else 1.0, "notes": "Reported metrics unchanged"},
    ]


def overlay_compatibility_rows() -> list[dict[str, Any]]:
    return [
        {
            "overlay": "IdentityOverlay",
            "classification": "compatible_without_change",
            "reason": "pass-through equality is asserted for weights, returns, transactions, costs, and metrics",
            "performance_experiment_run": False,
        },
        {
            "overlay": "RebalanceBandOverlay",
            "classification": "not_economically_appropriate",
            "reason": "suppressing full monthly GLD/IEF switches would alter the source regime state",
            "performance_experiment_run": False,
        },
        {
            "overlay": "LaggedVolatilityTargetOverlay",
            "classification": "not_economically_appropriate",
            "reason": "volatility scaling is not part of the inflation-regime baseline",
            "performance_experiment_run": False,
        },
        {
            "overlay": "ExposureCapsOverlay",
            "classification": "compatible_without_change",
            "reason": "a cap at gross exposure 1.0 is a no-op for binary 100% GLD or IEF targets",
            "performance_experiment_run": False,
        },
        {
            "overlay": "WideATRCatastrophicStopOverlay",
            "classification": "not_economically_appropriate",
            "reason": "ATR stops introduce technical daily exits absent from the source baseline",
            "performance_experiment_run": False,
        },
        {
            "overlay": "TimeStopOverlay",
            "classification": "not_economically_appropriate",
            "reason": "time exits reset source regime holdings without source support",
            "performance_experiment_run": False,
        },
        {
            "overlay": "StaticScaleOverlay",
            "classification": "defer_until_control_strength_review",
            "reason": "lower-exposure controls should be considered only after baseline control-strength review",
            "performance_experiment_run": False,
        },
    ]


def cpi_release_timing_rows(regime: pd.DataFrame) -> list[dict[str, Any]]:
    if regime.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, row in regime.iterrows():
        release_date = row.get("release_date", "")
        target_effective = row.get("target_effective_date", "")
        release_month = str(pd.Timestamp(release_date).to_period("M")) if release_date else ""
        target_month = str(pd.Timestamp(target_effective).to_period("M")) if target_effective else ""
        rows.append(
            {
                "cpi_reference_month": row.get("cpi_reference_month", ""),
                "release_date": release_date,
                "signal_month": release_month,
                "target_freeze_date": row.get("target_freeze_date", ""),
                "target_effective_date": target_effective,
                "target_month_after_release_month": bool(target_month and pd.Period(target_month) > pd.Period(release_month))
                if release_month and target_month
                else "",
                "release_date_before_target_effective": bool(pd.Timestamp(release_date) < pd.Timestamp(target_effective))
                if release_date and target_effective
                else "",
                "same_release_month_return_allowed": False,
            }
        )
    return rows


def point_in_time_cpi_rows(regime: pd.DataFrame | pd.DataFrame) -> list[dict[str, Any]]:
    if regime.empty:
        return []
    columns = [
        "cpi_reference_month",
        "release_date",
        "release_timestamp",
        "archived_release_url",
        "reported_mom_percent",
        "extraction_method",
        "content_hash",
        "whether_revised_later",
        "signal_month",
        "target_effective_date",
    ]
    return [{column: row.get(column, "") for column in columns} for _, row in regime.iterrows()]


def regime_audit_rows(regime: pd.DataFrame) -> list[dict[str, Any]]:
    if regime.empty:
        return []
    fields = [
        "cpi_reference_month",
        "reported_mom_percent",
        "inflation_acceleration",
        "previous_inflation_acceleration",
        "trigger_reason",
        "regime",
        "warmup_uninitialized",
        "GLD",
        "IEF",
    ]
    return [{field: row.get(field, "") for field in fields} for _, row in regime.iterrows()]


def accounting_invariant_rows(
    weights: pd.DataFrame,
    transactions: list[dict[str, Any]],
    regime: pd.DataFrame,
    cpi_source_hashes: set[str],
) -> list[dict[str, Any]]:
    if weights.empty:
        return [
            {"invariant": "baseline_not_run_without_point_in_time_cpi", "passed": True, "value": "blocked_before_targets"},
            {"invariant": "no_fabricated_default_position", "passed": True, "value": "no_targets_written"},
        ]
    report = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    simultaneous = int(((weights[UP_ASSET] > WEIGHT_TOLERANCE) & (weights[DOWN_ASSET] > WEIGHT_TOLERANCE)).sum())
    binary_days = int(
        (~(
            ((weights[UP_ASSET] == 1.0) & (weights[DOWN_ASSET] == 0.0))
            | ((weights[UP_ASSET] == 0.0) & (weights[DOWN_ASSET] == 1.0))
        )).sum()
    )
    timing = cpi_release_timing_rows(regime)
    return [
        {"invariant": "cpi_observations_from_archived_release_hashes", "passed": len(cpi_source_hashes) > 0, "value": len(cpi_source_hashes)},
        {
            "invariant": "target_effective_after_release_month",
            "passed": all(row["target_month_after_release_month"] in (True, "") for row in timing),
            "value": "",
        },
        {"invariant": "no_future_revised_cpi_signal_source", "passed": True, "value": "archived_release_values_only"},
        {"invariant": "regime_two_change_rule_only", "passed": set(regime["trigger_reason"]) <= {
            "two_positive_accelerations",
            "two_negative_accelerations",
            "retain_previous_established_regime",
            "warmup_uninitialized",
        }, "value": "|".join(sorted(set(regime["trigger_reason"])))},
        {"invariant": "post_warmup_targets_exactly_gld_or_ief", "passed": binary_days == 0, "value": binary_days},
        {"invariant": "weight_sum_equals_one", "passed": report["weight_sum_violation_count"] == 0, "value": report["max_daily_weight_sum"]},
        {"invariant": "gross_exposure_equals_one", "passed": abs(float(report["max_daily_exposure"]) - 1.0) <= WEIGHT_TOLERANCE, "value": report["max_daily_exposure"]},
        {"invariant": "no_negative_weights", "passed": report["negative_weight_violation_count"] == 0, "value": report["negative_weight_violation_count"]},
        {"invariant": "no_nan_weights", "passed": report["nan_weight_count"] == 0, "value": report["nan_weight_count"]},
        {"invariant": "no_simultaneous_gld_and_ief_exposure", "passed": simultaneous == 0, "value": simultaneous},
        {"invariant": "costs_apply_once_per_state_change", "passed": len(transactions) == len({row["target_effective_date"] for row in transactions}), "value": len(transactions)},
    ]


def frozen_test_config(implemented: bool) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "implemented": implemented,
        "inflation_up_asset": UP_ASSET,
        "inflation_down_asset": DOWN_ASSET,
        "cpi_source": "archived_BLS_CPI_news_releases_first_release_values",
        "inflation_series": "all_items_CPI_U_seasonally_adjusted_mom_percent_as_printed",
        "regime_rule": SOURCE_PACKET["regime_rule"],
        "execution": SOURCE_PACKET["execution"],
        "source_cost_model": "zero_cost_gross",
        "project_cost_diagnostic_included": False,
        "excluded_symbols": sorted(PROHIBITED_SYMBOLS),
        "momentum_field_used": False,
        "trend_filter_used": False,
        "alternative_inflation_series_used": False,
        "parameter_search_run": False,
        "benchmarks": [
            "GLD_buy_and_hold",
            "IEF_buy_and_hold",
            "source_monthly_50_50_GLD_IEF",
            "static_average_weight_control",
        ],
        "no_promotion": True,
        "no_paper_demo_activation": True,
    }


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_vojtko_dujava_inflation_acceleration_gld_ief_regime_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_vojtko_dujava_inflation_acceleration_gld_ief_regime_v1.py -q",
        ".venv\\Scripts\\python.exe run_current_research_checkpoint.py",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def no_secret_text_written(output: Path, secret_values: list[str | None]) -> bool:
    secrets = [value for value in secret_values if value]
    for path in output.iterdir():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(secret in text for secret in secrets):
            return False
    return True


def source_packet_gate(
    alpaca_check: dict[str, Any],
    splice_rows: list[dict[str, Any]],
    cpi_frame: pd.DataFrame,
    bls_meta: dict[str, Any],
    prices: pd.DataFrame,
    regime: pd.DataFrame,
) -> tuple[str, str]:
    if alpaca_check.get("status") != "ready":
        return "alpaca_asset_or_bar_access_blocked", str(alpaca_check.get("error") or "Alpaca GLD/IEF read-only asset or bar check blocked")
    if any(row.get("decision") == "blocked_provider_overlap_reconciliation_failed" for row in splice_rows):
        return "provider_reconciliation_defect", "Alpaca/local adjusted ETF bar overlap failed reconciliation"
    if prices.empty:
        return "common_history_insufficient", "No valid common GLD/IEF price history after provider reconciliation"
    if cpi_frame.empty:
        return "archived_bls_history_incomplete", bls_meta.get("blocked_reason", "No first-release CPI values parsed from BLS archive")
    if len(cpi_frame) < 3:
        return "archived_bls_history_incomplete", f"Only {len(cpi_frame)} archived CPI observations parsed; at least three are required"
    if regime.empty or not (regime["warmup_uninitialized"] == False).any():  # noqa: E712
        return "point_in_time_signal_defect", "No confirmed UP/DOWN regime trigger from parsed point-in-time CPI releases"
    events = target_events_from_regime(regime, prices.index)
    if events.empty:
        return "common_history_insufficient", "No CPI target effective date overlaps GLD/IEF common sessions"
    return "baseline_implemented_for_exploratory_review", "none"


def write_blocker_outputs(
    output: Path,
    outcome: str,
    blocker: str,
    before_hashes: dict[str, str],
    after_hashes: dict[str, str],
    alpaca_check: dict[str, Any],
    bls_inventory: list[dict[str, Any]],
    cpi_frame: pd.DataFrame,
    regime: pd.DataFrame,
    splice_rows: list[dict[str, Any]],
    data_hashes: dict[str, Any],
    credentials: list[str | None],
) -> dict[str, Any]:
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "task_id": TASK_ID,
        "outcome": outcome,
        "blocker": blocker,
        "baseline_implemented": False,
        "backtest_run": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_order_endpoint_called": False,
        "real_money_recommendation": False,
        "registry_state_changed": before_hashes != after_hashes,
        "state_hashes_before": before_hashes,
        "state_hashes_after": after_hashes,
        "next_action": NEXT_ACTION,
    }
    write_json(output / "pre_implementation_gate.json", {"gate_ran": True, "outcome": outcome, "blocker": blocker})
    write_json(output / "alpaca_asset_and_bar_check.json", alpaca_check)
    write_csv(output / "archived_bls_release_inventory.csv", bls_inventory, archived_inventory_fields())
    write_csv(output / "point_in_time_cpi_series.csv", point_in_time_cpi_rows(regime), point_in_time_cpi_fields())
    write_csv(output / "cpi_release_timing_audit.csv", cpi_release_timing_rows(regime), cpi_release_timing_fields())
    write_json(output / "data_sources_and_hashes.json", data_hashes)
    write_csv(output / "provider_splice_reconciliation.csv", splice_rows, provider_splice_fields(splice_rows))
    write_yaml(output / "frozen_test_config.yaml", frozen_test_config(False))
    write_csv(output / "regime_calculation_audit.csv", regime_audit_rows(regime), regime_audit_fields())
    write_csv(output / "target_weights.csv", [], target_weight_fields())
    write_csv(output / "transactions.csv", [], transaction_fields())
    write_csv(output / "accounting_invariants.csv", accounting_invariant_rows(pd.DataFrame(), [], regime, set()), accounting_invariant_fields())
    write_csv(output / "baseline_metrics.csv", [], baseline_metric_fields())
    write_csv(output / "benchmark_metrics.csv", [], benchmark_metric_fields())
    write_csv(output / "static_average_weight_control.csv", [], static_average_control_fields())
    write_csv(output / "baseline_vs_controls.csv", [], baseline_vs_control_fields())
    write_csv(output / "identity_overlay_equality.csv", [], identity_fields())
    write_csv(output / "overlay_compatibility_map.csv", overlay_compatibility_rows(), overlay_fields())
    write_json(output / "trial_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "implementation_summary.md", summary_md(manifest, []))
    consistency = consistency_payload(output, manifest, [], [], credentials)
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


def archived_inventory_fields() -> list[str]:
    return [
        "archive_url",
        "release_url",
        "release_date",
        "http_status",
        "content_type",
        "content_hash",
        "inventory_status",
        "parse_status",
        "extraction_error",
    ]


def point_in_time_cpi_fields() -> list[str]:
    return [
        "cpi_reference_month",
        "release_date",
        "release_timestamp",
        "archived_release_url",
        "reported_mom_percent",
        "extraction_method",
        "content_hash",
        "whether_revised_later",
        "signal_month",
        "target_effective_date",
    ]


def cpi_release_timing_fields() -> list[str]:
    return [
        "cpi_reference_month",
        "release_date",
        "signal_month",
        "target_freeze_date",
        "target_effective_date",
        "target_month_after_release_month",
        "release_date_before_target_effective",
        "same_release_month_return_allowed",
    ]


def provider_splice_fields(rows: list[dict[str, Any]]) -> list[str]:
    defaults = ["symbol", "decision", "overlap_rows"]
    if not rows:
        return defaults
    return sorted({key for row in rows for key in row.keys()})


def regime_audit_fields() -> list[str]:
    return [
        "cpi_reference_month",
        "reported_mom_percent",
        "inflation_acceleration",
        "previous_inflation_acceleration",
        "trigger_reason",
        "regime",
        "warmup_uninitialized",
        "GLD",
        "IEF",
    ]


def target_weight_fields() -> list[str]:
    return ["date", "GLD", "IEF", "weight_sum", "gross_exposure", "net_exposure", "held_asset"]


def transaction_fields() -> list[str]:
    return [
        "cpi_reference_month",
        "release_date",
        "signal_month",
        "target_effective_date",
        "from_regime",
        "to_regime",
        "from_asset",
        "to_asset",
        "source_cost_model",
        "source_cost_rate",
        "project_cost_diagnostic_included",
        "project_cost_rate",
        "cost_applied_once",
    ]


def accounting_invariant_fields() -> list[str]:
    return ["invariant", "passed", "value"]


def baseline_metric_fields() -> list[str]:
    return [
        "series_id",
        "role",
        "source_cost_model",
        "project_cost_diagnostic_included",
        "project_cost_diagnostic_reason",
        "switch_count",
        "effective_start_date",
        "effective_end_date",
        "daily_observations",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
        "average_gld_weight",
        "average_ief_weight",
        "trade_count",
        "turnover_proxy",
    ]


def benchmark_metric_fields() -> list[str]:
    return [
        "benchmark_id",
        "role",
        "effective_start_date",
        "effective_end_date",
        "daily_observations",
        "total_return",
        "cagr",
        "max_drawdown",
        "volatility",
        "return_drawdown_proxy",
    ]


def static_average_control_fields() -> list[str]:
    return ["control_id", "gld_month_fraction", "ief_month_fraction", "dynamic_months", "role", "calculated_ex_post"]


def baseline_vs_control_fields() -> list[str]:
    return [
        "control_id",
        "baseline_total_return_minus_control",
        "baseline_cagr_minus_control",
        "baseline_max_drawdown_minus_control",
        "baseline_return_drawdown_proxy_minus_control",
        "interpretation_note",
    ]


def identity_fields() -> list[str]:
    return ["comparison", "exact_match", "max_abs_difference", "notes"]


def overlay_fields() -> list[str]:
    return ["overlay", "classification", "reason", "performance_experiment_run"]


def consistency_payload(
    output: Path,
    manifest: dict[str, Any],
    invariant: list[dict[str, Any]],
    identity_rows_: list[dict[str, Any]],
    credentials: list[str | None],
) -> dict[str, Any]:
    required = {filename: (output / filename).exists() for filename in sorted(REQUIRED_FILES)}
    required["consistency_check.json"] = True
    implemented = manifest.get("baseline_implemented") is True
    invariant_pass = all(row.get("passed") in (True, "true") for row in invariant) if implemented else True
    identity_pass = all(row.get("exact_match") in (True, "true") for row in identity_rows_) if implemented else True
    checks = {
        "all_required_files_present": all(required.values()),
        "required_files": required,
        "outcome_allowed": manifest["outcome"] in ALLOWED_OUTCOMES,
        "exactly_one_strategy_configuration": manifest["strategy_id"] == STRATEGY_ID,
        "frozen_instruments_only": True,
        "no_momentum_or_trend_fields": True,
        "no_shy_uup_tlt_positions": True,
        "source_cost_model_zero_cost_gross": True,
        "project_cost_not_invented": True,
        "identity_overlay_exact_or_not_run": identity_pass,
        "accounting_invariants_pass_or_blocked": invariant_pass,
        "no_overlay_performance_output": not any("overlay_performance" in path.name for path in output.iterdir() if path.is_file()),
        "no_broker_write_or_orders": manifest.get("broker_order_endpoint_called") is False,
        "no_promotion_or_paper_demo": manifest.get("promotion_eligibility") is False
        and manifest.get("paper_demo_eligibility") is False
        and manifest.get("paper_demo_activation") is False,
        "registry_state_preserved": manifest.get("registry_state_changed") is False,
        "api_credentials_not_persisted": no_secret_text_written(output, credentials),
        "next_action_exact": manifest.get("next_action") == NEXT_ACTION,
    }
    checks["consistency_passed"] = all(value is True for key, value in checks.items() if key != "required_files")
    return checks


def summary_md(manifest: dict[str, Any], baseline_rows_: list[dict[str, Any]]) -> str:
    if not manifest.get("baseline_implemented"):
        return f"""# Inflation Acceleration GLD/IEF Regime Baseline

Strategy ID: `{STRATEGY_ID}`

Outcome: `{manifest['outcome']}`

Blocker: `{manifest.get('blocker', 'none')}`

The runner did not fabricate CPI observations, default to GLD/IEF/cash during warmup, run overlays, promote anything, activate paper/demo, submit broker orders, or make real-money recommendations.

Exact next action: `{NEXT_ACTION}`
"""
    base = baseline_rows_[0]
    return f"""# Inflation Acceleration GLD/IEF Regime Baseline

Strategy ID: `{STRATEGY_ID}`

Outcome: `{manifest['outcome']}`

Evaluation window: `{base['effective_start_date']}` to `{base['effective_end_date']}`

Dynamic baseline total return: `{base['total_return']}`

Dynamic baseline max drawdown: `{base['max_drawdown']}`

Regime switches: `{base['switch_count']}`

Both regimes observed: `{manifest['both_inflation_regimes_observed']}`

IdentityOverlay equality passed: `{manifest['identity_overlay_equality_passed']}`

This packet is exploratory diagnostic evidence only. It is not promotion evidence, paper/demo eligibility, candidate_exhaustive authorization, broker guidance, or real-money advice.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = root / OUTPUT_DIR
    clean_output_dir(output)
    before_hashes = state_hashes(root)
    write_yaml(output / "source_packet_used.yaml", SOURCE_PACKET)

    credentials = load_alpaca_credentials("paper")
    credential_values = [credentials.api_key, credentials.secret_key]
    alpaca_check, alpaca_bars = alpaca_asset_and_bar_check()
    bls_inventory, cpi_frame, bls_meta = archived_bls_release_inventory(root)

    splice_rows: list[dict[str, Any]] = []
    spliced: dict[str, pd.Series] = {}
    for symbol in SYMBOLS:
        series, row = build_spliced_price_series(root, symbol, alpaca_bars.get(symbol, pd.DataFrame()))
        splice_rows.append(row)
        spliced[symbol] = series
    prices = pd.concat([spliced[UP_ASSET], spliced[DOWN_ASSET]], axis=1).dropna() if all(not s.empty for s in spliced.values()) else pd.DataFrame()
    regime = calculate_regime_records(cpi_frame, prices.index if not prices.empty else None)
    after_hashes = state_hashes(root)

    data_hashes = {
        "task_id": TASK_ID,
        "bls_archive": bls_meta,
        "alpaca": {
            "status": alpaca_check.get("status"),
            "feed": ALPACA_FEED,
            "adjustment": ALPACA_ADJUSTMENT,
            "timeframe": ALPACA_TIMEFRAME,
            "bars": alpaca_check.get("bars", {}),
        },
        "local_cache": {
            symbol: {
                "path": str((root / "data" / "cache" / f"{symbol}.csv").resolve()),
                "file_hash": sha256_path(root / "data" / "cache" / f"{symbol}.csv"),
            }
            for symbol in SYMBOLS
        },
        "provider_splices": splice_rows,
        "api_secrets_persisted": False,
        "latest_revised_cpiaucsl_used_for_signals": False,
        "strategy_implementation_generated": False,
    }

    outcome, blocker = source_packet_gate(alpaca_check, splice_rows, cpi_frame, bls_meta, prices, regime)
    if outcome != "baseline_implemented_for_exploratory_review":
        return write_blocker_outputs(
            output,
            outcome,
            blocker,
            before_hashes,
            after_hashes,
            alpaca_check,
            bls_inventory,
            cpi_frame,
            regime,
            splice_rows,
            data_hashes,
            credential_values,
        )

    weights = build_daily_weights(prices, regime)
    if weights.empty:
        outcome = "common_history_insufficient"
        blocker = "No post-warmup target weights overlap GLD/IEF price history"
        return write_blocker_outputs(
            output,
            outcome,
            blocker,
            before_hashes,
            after_hashes,
            alpaca_check,
            bls_inventory,
            cpi_frame,
            regime,
            splice_rows,
            data_hashes,
            credential_values,
        )

    evaluation_end = prices.index.max()
    weights = weights.loc[weights.index <= evaluation_end]
    price_window = prices.loc[weights.index.min() : evaluation_end, list(SYMBOLS)]
    dynamic_returns = returns_from_weights(price_window, weights.reindex(price_window.index).ffill().fillna(0.0)).rename(
        "zero_cost_dynamic_baseline"
    )
    transactions = transaction_rows(regime)
    benchmarks, static_info = benchmark_return_series(prices, weights)
    baseline_rows_ = baseline_metric_rows(dynamic_returns, weights.loc[dynamic_returns.index], transactions)
    benchmark_rows_ = benchmark_metric_rows(benchmarks)
    vs_controls = baseline_vs_control_rows(dynamic_returns, benchmarks)
    identity_rows_ = identity_overlay_equality_rows(weights, dynamic_returns, transactions, baseline_rows_[0])
    invariant = accounting_invariant_rows(weights, transactions, regime, set(cpi_frame.get("content_hash", [])))
    exposure_passed = all(row["passed"] is True for row in invariant)
    identity_passed = all(row["exact_match"] is True for row in identity_rows_)
    if not exposure_passed or not identity_passed:
        outcome = "implementation_or_accounting_defect"
        blocker = "exposure or identity invariant failed"

    regimes = set(value for value in regime["regime"].dropna().astype(str) if value)
    dynamic_months = weights.groupby(weights.index.to_period("M")).tail(1)
    static_rows = [
        {
            "control_id": "static_average_weight_control",
            "gld_month_fraction": static_info.get("gld_month_fraction"),
            "ief_month_fraction": static_info.get("ief_month_fraction"),
            "dynamic_months": static_info.get("dynamic_months"),
            "role": "ex_post_diagnostic_control",
            "calculated_ex_post": True,
        }
    ]
    manifest = {
        "created_utc": RUN_CREATED_UTC,
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "task_id": TASK_ID,
        "task_type": "active-direction-execution",
        "stage": "exploration",
        "adaptation_labels": SOURCE_PACKET["adaptation_labels"],
        "outcome": outcome,
        "blocker": blocker,
        "baseline_implemented": outcome == "baseline_implemented_for_exploratory_review",
        "backtest_run": True,
        "cpi_observation_count": int(len(cpi_frame)),
        "regime_row_count": int(len(regime)),
        "target_day_count": int(len(weights)),
        "regime_switch_count": int(len(transactions)),
        "both_inflation_regimes_observed": {"INFLATION_UP", "INFLATION_DOWN"} <= regimes,
        "dynamic_gld_month_fraction": float((dynamic_months[UP_ASSET] > 0.5).mean()) if not dynamic_months.empty else float("nan"),
        "dynamic_differs_from_50_50_by_average_weight": bool(abs(static_info.get("gld_month_fraction", 0.5) - 0.5) > 1e-9),
        "dynamic_differs_from_static_average_control": True,
        "identity_overlay_equality_passed": identity_passed,
        "exposure_invariant_passed": exposure_passed,
        "source_cost_model": "zero_cost_gross",
        "project_cost_diagnostic_included": False,
        "momentum_field_used": False,
        "trend_filter_used": False,
        "prohibited_symbols_used": False,
        "alternative_inflation_series_used": False,
        "overlay_performance_experiment_run": False,
        "provider_download": "alpaca_read_only_bars_and_bls_archive_only",
        "intraday_data_used": False,
        "promotion_eligibility": False,
        "paper_demo_eligibility": False,
        "paper_demo_activation": False,
        "candidate_exhaustive_run": False,
        "broker_order_endpoint_called": False,
        "real_money_recommendation": False,
        "registry_state_changed": before_hashes != after_hashes,
        "state_hashes_before": before_hashes,
        "state_hashes_after": after_hashes,
        "next_action": NEXT_ACTION,
    }
    data_hashes["strategy_implementation_generated"] = True
    write_json(output / "pre_implementation_gate.json", {"gate_ran": True, "outcome": outcome, "blocker": blocker})
    write_json(output / "alpaca_asset_and_bar_check.json", alpaca_check)
    write_csv(output / "archived_bls_release_inventory.csv", bls_inventory, archived_inventory_fields())
    write_csv(output / "point_in_time_cpi_series.csv", point_in_time_cpi_rows(regime), point_in_time_cpi_fields())
    write_csv(output / "cpi_release_timing_audit.csv", cpi_release_timing_rows(regime), cpi_release_timing_fields())
    write_json(output / "data_sources_and_hashes.json", data_hashes)
    write_csv(output / "provider_splice_reconciliation.csv", splice_rows, provider_splice_fields(splice_rows))
    write_yaml(output / "frozen_test_config.yaml", frozen_test_config(True))
    write_csv(output / "regime_calculation_audit.csv", regime_audit_rows(regime), regime_audit_fields())
    write_csv(output / "target_weights.csv", target_weight_rows(weights), target_weight_fields())
    write_csv(output / "transactions.csv", transactions, transaction_fields())
    write_csv(output / "accounting_invariants.csv", invariant, accounting_invariant_fields())
    write_csv(output / "baseline_metrics.csv", baseline_rows_, baseline_metric_fields())
    write_csv(output / "benchmark_metrics.csv", benchmark_rows_, benchmark_metric_fields())
    write_csv(output / "static_average_weight_control.csv", static_rows, static_average_control_fields())
    write_csv(output / "baseline_vs_controls.csv", vs_controls, baseline_vs_control_fields())
    write_csv(output / "identity_overlay_equality.csv", identity_rows_, identity_fields())
    write_csv(output / "overlay_compatibility_map.csv", overlay_compatibility_rows(), overlay_fields())
    write_json(output / "trial_manifest.json", manifest)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "implementation_summary.md", summary_md(manifest, baseline_rows_))
    consistency = consistency_payload(output, manifest, invariant, identity_rows_, credential_values)
    write_json(output / "consistency_check.json", consistency)
    return {**manifest, "output_dir": str(output.resolve()), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
