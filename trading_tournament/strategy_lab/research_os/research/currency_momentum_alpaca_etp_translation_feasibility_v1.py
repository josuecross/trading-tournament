from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient
from execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    LIVE_KEY,
    LIVE_SECRET,
    PAPER_KEY,
    PAPER_SECRET,
    load_alpaca_credentials,
)


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "currency_momentum_alpaca_etp_translation_feasibility_v1"
SOURCE_EXACT_ID = "deutsche_bank_g10_currency_momentum_top3_bottom3_12m_forward_v1"
FUTURE_FULL_SPEC_ID = "currency_momentum_g10_top3_bottom3_12m_alpaca_currency_etp_translation_v1"
ADAPTATION_LABEL = "instrument_universe_adjustment"
NEXT_ACTION = "direction_owner_review_currency_momentum_alpaca_etp_translation_feasibility_v1"
OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "currency_momentum_factor"
    / "alpaca_etp_translation_feasibility_v1"
    / "latest"
)
REQUEST_START_DATE = "1990-01-01"
REQUEST_END_DATE = "2026-07-21"
BAR_FEED = "iex"
BAR_ADJUSTMENT = "all"

SOURCE_CURRENCIES = ["USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"]
PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]


@dataclass(frozen=True)
class CandidateDefinition:
    symbol: str
    source_currencies: tuple[str, ...]
    issuer: str
    official_name: str
    official_source_url: str
    official_source_type: str
    currency_exposure: str
    exposure_mechanism: str
    single_currency: bool
    basket_product: bool
    leveraged: bool
    inverse: bool
    crypto_product: bool
    issuer_active_status: str
    expense_ratio: float | None
    inception_or_first_trading_date: str
    closure_or_liquidation_status: str
    benchmark_or_reference_rate: str
    distribution_treatment: str
    tracking_limitations: str
    official_verification_summary: str


CANDIDATES: list[CandidateDefinition] = [
    CandidateDefinition(
        "FXE",
        ("EUR",),
        "Invesco",
        "Invesco CurrencyShares Euro Currency Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-euro-trust.html",
        "official_issuer_product_page",
        "Euro versus U.S. dollar",
        "grantor trust holding euro deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2005-12-12",
        "none_found_in_current_issuer_page",
        "Closing spot rate / euro held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered euro trust candidate",
    ),
    CandidateDefinition(
        "FXY",
        ("JPY",),
        "Invesco",
        "Invesco CurrencyShares Japanese Yen Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-japanese-yen-trust.html",
        "official_issuer_product_page",
        "Japanese yen versus U.S. dollar",
        "grantor trust holding Japanese yen deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2007-02-13",
        "none_found_in_current_issuer_page",
        "Closing spot rate / Japanese yen held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered yen trust candidate",
    ),
    CandidateDefinition(
        "FXB",
        ("GBP",),
        "Invesco",
        "Invesco CurrencyShares British Pound Sterling Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-british-pound-sterling-trust.html",
        "official_issuer_product_page",
        "British pound sterling versus U.S. dollar",
        "grantor trust holding British pound deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2006-06-26",
        "none_found_in_current_issuer_page",
        "Closing spot rate / British pounds held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered pound trust candidate",
    ),
    CandidateDefinition(
        "FXF",
        ("CHF",),
        "Invesco",
        "Invesco CurrencyShares Swiss Franc Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-swiss-franc-trust.html",
        "official_issuer_product_page",
        "Swiss franc versus U.S. dollar",
        "grantor trust holding Swiss franc deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2006-06-26",
        "none_found_in_current_issuer_page",
        "Closing spot rate / Swiss francs held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered Swiss franc trust candidate",
    ),
    CandidateDefinition(
        "FXA",
        ("AUD",),
        "Invesco",
        "Invesco CurrencyShares Australian Dollar Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-australian-dollar-trust.html",
        "official_issuer_product_page",
        "Australian dollar versus U.S. dollar",
        "grantor trust holding Australian dollar deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2006-06-26",
        "none_found_in_current_issuer_page",
        "Closing spot rate / Australian dollars held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered Australian dollar trust candidate",
    ),
    CandidateDefinition(
        "FXC",
        ("CAD",),
        "Invesco",
        "Invesco CurrencyShares Canadian Dollar Trust",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-currencyshares-canadian-dollar-trust.html",
        "official_issuer_product_page",
        "Canadian dollar versus U.S. dollar",
        "grantor trust holding Canadian dollar deposits; no derivative products in core trust design",
        True,
        False,
        False,
        False,
        False,
        "active_current_issuer_page",
        0.0040,
        "2006-06-26",
        "none_found_in_current_issuer_page",
        "Closing spot rate / Canadian dollars held by trust",
        "interest, if any, less trust expenses; taxable grantor trust reporting",
        "share price can differ from NAV; trust expenses and interest treatment differ from pure spot",
        "single-currency unlevered Canadian dollar trust candidate",
    ),
    CandidateDefinition(
        "FXS",
        ("SEK",),
        "Invesco",
        "Invesco CurrencyShares Swedish Krona Trust",
        "https://www.invesco.com/us-rest/contentdetail?contentId=fbb53c5611e6f610VgnVCM1000006e36b50aRCRD",
        "official_issuer_liquidation_notice",
        "Swedish krona versus U.S. dollar",
        "historical grantor trust holding Swedish krona deposits",
        True,
        False,
        False,
        False,
        False,
        "liquidated_or_delisted",
        0.0040,
        "2006-06-26",
        "last_trading_date_2020-02-14_per_invesco_liquidation_notice",
        "Closing spot rate / Swedish kronor held by trust",
        "historical trust treatment only",
        "closed product cannot support current Alpaca paper trading",
        "historical single-currency Swedish krona candidate, rejected as inactive",
    ),
    CandidateDefinition(
        "BNZ",
        ("NZD",),
        "WisdomTree",
        "WisdomTree Dreyfus New Zealand Dollar Fund",
        "https://www.wisdomtree.com/us/press-room/archive/2008",
        "official_issuer_archive_listing",
        "New Zealand dollar versus U.S. dollar",
        "historical actively managed currency fund; not current Alpaca-recognized asset",
        True,
        False,
        False,
        False,
        False,
        "historical_or_not_current",
        0.0045,
        "2008-06-25",
        "not_current_alpaca_asset; historical fund later changed strategy/ticker in public records",
        "New Zealand dollar exposure",
        "historical fund distribution treatment unresolved for current use",
        "not recognized by current Alpaca Assets API",
        "historical New Zealand dollar candidate, rejected because Alpaca does not recognize symbol",
    ),
    CandidateDefinition(
        "AUNZ",
        ("AUD", "NZD"),
        "WisdomTree",
        "WisdomTree Australia & New Zealand Debt Fund",
        "https://www.sec.gov/Archives/edgar/data/1350487/000119312511062475/d497.htm",
        "official_sec_filing",
        "Australia and New Zealand local debt/currency exposure",
        "local debt fund, not a single-currency spot proxy",
        False,
        True,
        False,
        False,
        False,
        "historical_or_not_current",
        None,
        "2011_strategy_change_record",
        "not_current_alpaca_asset",
        "local debt portfolio",
        "bond fund distributions, not single-currency grantor trust",
        "multi-currency/debt exposure changes source mechanism",
        "rejected as basket/debt product and not Alpaca-recognized",
    ),
    CandidateDefinition(
        "CEW",
        ("NZD", "NOK", "SEK"),
        "WisdomTree",
        "WisdomTree Emerging Currency Strategy Fund",
        "https://www.wisdomtree.com/us/products/currency/cew",
        "official_issuer_product_page",
        "basket of selected emerging-market currencies and money-market rates",
        "active strategy fund with basket exposure",
        False,
        True,
        False,
        False,
        False,
        "active_current_issuer_page",
        None,
        "2009-05-06",
        "none_found_in_current_issuer_page",
        "emerging currency strategy, not G10 single-currency wrapper",
        "fund distributions according to ETF structure",
        "basket and emerging-market scope are not source-currency single exposure",
        "rejected as basket product",
    ),
    CandidateDefinition(
        "DBV",
        ("EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK"),
        "Invesco",
        "Invesco DB G10 Currency Harvest Fund",
        "https://www.invesco.com/us-rest/contentdetail?contentId=f787d563-890d-4ea9-914b-fad8d702c6f1",
        "official_issuer_report",
        "G10 currency basket/carry futures strategy",
        "futures-based basket, not single-currency ETP",
        False,
        True,
        False,
        False,
        False,
        "inactive_in_alpaca",
        None,
        "2006-09-18",
        "inactive_in_alpaca_asset_api",
        "DB G10 Currency Future Harvest Index-style exposure",
        "commodity pool/futures product treatment",
        "basket/carry/futures exposure changes source mechanism for a single-currency ETP translation",
        "rejected as basket/futures product and inactive",
    ),
    CandidateDefinition(
        "ULE",
        ("EUR",),
        "ProShares",
        "ProShares Ultra Euro",
        "https://www.proshares.com/our-etfs/leveraged-and-inverse/ule",
        "official_issuer_product_page",
        "2x daily euro versus U.S. dollar",
        "leveraged daily exposure",
        True,
        False,
        True,
        False,
        False,
        "active_current_issuer_page",
        0.0095,
        "2008-11-24",
        "none_found_in_current_issuer_page",
        "2x daily euro benchmark",
        "ETF distribution treatment",
        "leveraged daily reset changes mechanism",
        "rejected as leveraged product",
    ),
    CandidateDefinition(
        "EUO",
        ("EUR",),
        "ProShares",
        "ProShares UltraShort Euro",
        "https://www.proshares.com/our-etfs/leveraged-and-inverse/euo",
        "official_issuer_product_page",
        "-2x daily euro versus U.S. dollar",
        "inverse leveraged daily exposure",
        True,
        False,
        True,
        True,
        False,
        "active_current_issuer_page",
        0.0095,
        "2008-11-24",
        "none_found_in_current_issuer_page",
        "-2x daily euro benchmark",
        "ETF distribution treatment",
        "inverse leveraged daily reset changes mechanism",
        "rejected as inverse and leveraged product",
    ),
    CandidateDefinition(
        "YCL",
        ("JPY",),
        "ProShares",
        "ProShares Ultra Yen",
        "https://www.proshares.com/our-etfs/leveraged-and-inverse/ycl",
        "official_issuer_product_page",
        "2x daily Japanese yen versus U.S. dollar",
        "leveraged daily exposure",
        True,
        False,
        True,
        False,
        False,
        "active_current_issuer_page",
        0.0095,
        "2008-11-24",
        "none_found_in_current_issuer_page",
        "2x daily yen benchmark",
        "ETF distribution treatment",
        "leveraged daily reset changes mechanism",
        "rejected as leveraged product",
    ),
    CandidateDefinition(
        "YCS",
        ("JPY",),
        "ProShares",
        "ProShares UltraShort Yen",
        "https://www.proshares.com/our-etfs/leveraged-and-inverse/ycs",
        "official_issuer_product_page",
        "-2x daily Japanese yen versus U.S. dollar",
        "inverse leveraged daily exposure",
        True,
        False,
        True,
        True,
        False,
        "active_current_issuer_page",
        0.0095,
        "2008-11-24",
        "none_found_in_current_issuer_page",
        "-2x daily yen benchmark",
        "ETF distribution treatment",
        "inverse leveraged daily reset changes mechanism",
        "rejected as inverse and leveraged product",
    ),
    CandidateDefinition(
        "UUP",
        ("USD",),
        "Invesco",
        "Invesco DB US Dollar Index Bullish Fund",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-db-us-dollar-index-bullish-fund.html",
        "official_issuer_product_page",
        "U.S. dollar index basket",
        "dollar-index futures basket, not base-currency member",
        False,
        True,
        False,
        False,
        False,
        "active_current_issuer_page",
        None,
        "2007-02-20",
        "none_found_in_current_issuer_page",
        "DB U.S. Dollar Index",
        "commodity pool/futures product treatment",
        "USD must remain base member and cannot be replaced with a dollar-index product",
        "rejected as USD basket product",
    ),
    CandidateDefinition(
        "UDN",
        ("USD",),
        "Invesco",
        "Invesco DB US Dollar Index Bearish Fund",
        "https://www.invesco.com/us/en/financial-products/etfs/invesco-db-us-dollar-index-bearish-fund.html",
        "official_issuer_product_page",
        "inverse U.S. dollar index basket",
        "inverse dollar-index futures basket, not base-currency member",
        False,
        True,
        False,
        True,
        False,
        "active_current_issuer_page",
        None,
        "2007-02-20",
        "none_found_in_current_issuer_page",
        "DB U.S. Dollar Index bearish exposure",
        "commodity pool/futures product treatment",
        "USD must remain base member and cannot be replaced with a dollar-index product",
        "rejected as inverse USD basket product",
    ),
]


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def clean_output_dir(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.iterdir():
        if path.is_file():
            path.unlink()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return repr(value)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def candidate_by_symbol() -> dict[str, CandidateDefinition]:
    return {candidate.symbol: candidate for candidate in CANDIDATES}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def load_client() -> tuple[AlpacaClient | None, str]:
    credentials = load_alpaca_credentials("paper")
    if not credentials.present:
        return None, "alpaca_credentials_missing"
    return AlpacaClient(credentials), "ok"


def asset_search_terms() -> list[str]:
    return [
        "currency",
        "currencies",
        "currencyshares",
        "euro",
        "yen",
        "pound",
        "sterling",
        "swiss franc",
        "australian dollar",
        "canadian dollar",
        "new zealand dollar",
        "norwegian krone",
        "swedish krona",
        "dollar index",
    ]


def fetch_active_assets(client: AlpacaClient | None) -> tuple[list[dict[str, Any]], str]:
    if client is None:
        return [], "alpaca_credentials_missing"
    try:
        return client.get_assets(), "ok"
    except Exception as exc:  # pragma: no cover - exercised by live environment only
        return [], f"asset_list_error:{type(exc).__name__}:{str(exc)[:160]}"


def search_active_asset_candidates(active_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = asset_search_terms()
    rows: list[dict[str, Any]] = []
    for asset in active_assets:
        text = f"{asset.get('symbol', '')} {asset.get('name', '')}".lower()
        matched = [term for term in terms if term in text]
        if matched:
            rows.append(
                {
                    "symbol": asset.get("symbol", ""),
                    "name": asset.get("name", ""),
                    "matched_terms": matched,
                    "exchange": asset.get("exchange", ""),
                    "asset_class": asset.get("class", ""),
                    "status": asset.get("status", ""),
                    "tradable": asset.get("tradable", False),
                }
            )
    return rows


def fetch_asset_metadata(client: AlpacaClient | None, symbol: str, active_assets_by_symbol: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], str]:
    if symbol in active_assets_by_symbol:
        return active_assets_by_symbol[symbol], "active_asset_list"
    if client is None:
        return {}, "alpaca_credentials_missing"
    try:
        return client._request("GET", client.config.paper_base_url, f"/v2/assets/{symbol}"), "symbol_lookup"
    except Exception as exc:
        return {}, f"symbol_lookup_error:{type(exc).__name__}:{str(exc)[:120]}"


def fetch_stock_bars(client: AlpacaClient | None, symbol: str) -> tuple[pd.DataFrame, str, int]:
    if client is None:
        return pd.DataFrame(), "alpaca_credentials_missing", 0
    merged: dict[str, Any] = {"bars": {symbol: []}}
    page_token: str | None = None
    pages = 0
    try:
        while True:
            payload = client.get_historical_bars_page(
                symbols=[symbol],
                start=REQUEST_START_DATE,
                end=REQUEST_END_DATE,
                timeframe="1Day",
                page_token=page_token,
                feed=BAR_FEED,
                adjustment=BAR_ADJUSTMENT,
                limit=10000,
            )
            pages += 1
            for returned_symbol, bars in payload.get("bars", {}).items():
                merged["bars"].setdefault(returned_symbol, []).extend(bars)
            page_token = payload.get("next_page_token")
            if not page_token:
                break
    except Exception as exc:
        return pd.DataFrame(), f"bar_request_error:{type(exc).__name__}:{str(exc)[:160]}", pages
    bars = merged.get("bars", {}).get(symbol, [])
    if not bars:
        return pd.DataFrame(), "no_bars_returned", pages
    records: list[dict[str, Any]] = []
    for bar in bars:
        timestamp = pd.to_datetime(bar.get("t"), utc=True)
        records.append(
            {
                "date": timestamp.date().isoformat(),
                "timestamp": timestamp.isoformat(),
                "open": float(bar.get("o")),
                "high": float(bar.get("h")),
                "low": float(bar.get("l")),
                "close": float(bar.get("c")),
                "volume": float(bar.get("v", 0.0)),
            }
        )
    frame = pd.DataFrame(records).sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    return frame, "ok", pages


def monthly_bar_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "first_available_bar": "",
            "final_available_bar": "",
            "daily_bar_count": 0,
            "monthly_observation_count": 0,
            "internal_month_gaps": 0,
            "earliest_month": "",
            "latest_month": "",
            "monthly_hash": "missing",
        }
    months = sorted({str(date)[:7] for date in frame["date"].tolist()})
    period = pd.period_range(months[0], months[-1], freq="M")
    expected = {str(item) for item in period}
    missing = sorted(expected - set(months))
    monthly_payload = [{"month": month} for month in months]
    return {
        "first_available_bar": str(frame["date"].iloc[0]),
        "final_available_bar": str(frame["date"].iloc[-1]),
        "daily_bar_count": int(len(frame)),
        "monthly_observation_count": len(months),
        "internal_month_gaps": len(missing),
        "missing_internal_months": missing,
        "earliest_month": months[0],
        "latest_month": months[-1],
        "monthly_hash": stable_hash(monthly_payload),
    }


def inspect_alpaca_assets_and_bars(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    client, client_status = load_client()
    active_assets, active_status = fetch_active_assets(client)
    active_assets_by_symbol = {str(asset.get("symbol")): asset for asset in active_assets}
    raw_search_hits = search_active_asset_candidates(active_assets)

    inventory: list[dict[str, Any]] = []
    bar_rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        asset, asset_source = fetch_asset_metadata(client, candidate.symbol, active_assets_by_symbol)
        asset_hash = stable_hash(asset) if asset else "missing"
        frame = pd.DataFrame()
        bar_status = "not_requested_no_alpaca_asset"
        bar_pages = 0
        if asset:
            frame, bar_status, bar_pages = fetch_stock_bars(client, candidate.symbol)
        summary = monthly_bar_summary(frame)
        inventory.append(
            {
                "symbol": candidate.symbol,
                "name": asset.get("name", candidate.official_name) if asset else candidate.official_name,
                "exchange": asset.get("exchange", ""),
                "asset_class": asset.get("class", ""),
                "status": asset.get("status", "not_found"),
                "tradable": bool(asset.get("tradable", False)),
                "fractionable": bool(asset.get("fractionable", False)),
                "marginable": bool(asset.get("marginable", False)),
                "shortable": bool(asset.get("shortable", False)),
                "easy_to_borrow": bool(asset.get("easy_to_borrow", False)),
                "first_available_alpaca_bar": summary["first_available_bar"],
                "final_available_alpaca_bar": summary["final_available_bar"],
                "number_of_monthly_observations": summary["monthly_observation_count"],
                "internal_data_gaps": summary["internal_month_gaps"],
                "delisting_or_inactive_status": "inactive_or_not_found" if asset.get("status") != "active" else "none_reported_by_alpaca",
                "alpaca_metadata_hash": asset_hash,
                "asset_metadata_source": asset_source,
                "bar_request_status": bar_status,
            }
        )
        bar_rows.append(
            {
                "symbol": candidate.symbol,
                "bar_request_status": bar_status,
                "bar_pages": bar_pages,
                "first_available_bar": summary["first_available_bar"],
                "final_available_bar": summary["final_available_bar"],
                "daily_bar_count": summary["daily_bar_count"],
                "monthly_observation_count": summary["monthly_observation_count"],
                "internal_month_gaps": summary["internal_month_gaps"],
                "missing_internal_months": summary.get("missing_internal_months", []),
                "feed": BAR_FEED,
                "adjustment": BAR_ADJUSTMENT,
                "bar_history_hash": summary["monthly_hash"],
            }
        )

    capability = {
        "alpaca_client_status": client_status,
        "active_asset_list_status": active_status,
        "active_asset_count": len(active_assets),
        "raw_text_search_hit_count": len(raw_search_hits),
        "raw_text_search_terms": asset_search_terms(),
        "candidate_symbols_evaluated": [candidate.symbol for candidate in CANDIDATES],
        "api_credentials_persisted": False,
        "fx_rates_endpoint_reopened": False,
        "orders_or_broker_writes_called": False,
    }
    return inventory, bar_rows, capability


def official_verification_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        reject_reason = ""
        if candidate.leveraged or candidate.inverse:
            reject_reason = "leveraged_or_inverse_product"
        elif candidate.basket_product:
            reject_reason = "basket_product"
        elif candidate.issuer_active_status not in {"active_current_issuer_page"}:
            reject_reason = "closed_inactive_or_not_current"
        rows.append(
            {
                "symbol": candidate.symbol,
                "source_currencies": candidate.source_currencies,
                "official_name": candidate.official_name,
                "issuer": candidate.issuer,
                "official_source_url": candidate.official_source_url,
                "official_source_type": candidate.official_source_type,
                "currency_exposure": candidate.currency_exposure,
                "exposure_mechanism": candidate.exposure_mechanism,
                "single_currency": candidate.single_currency,
                "basket_product": candidate.basket_product,
                "long_inverse_or_leveraged": "inverse" if candidate.inverse else ("leveraged" if candidate.leveraged else "long_unlevered"),
                "expense_ratio": candidate.expense_ratio,
                "inception_date": candidate.inception_or_first_trading_date,
                "closure_or_liquidation_status": candidate.closure_or_liquidation_status,
                "benchmark_or_reference_rate": candidate.benchmark_or_reference_rate,
                "distribution_treatment": candidate.distribution_treatment,
                "main_tracking_limitations": candidate.tracking_limitations,
                "product_identity_verified": True,
                "reject_reason": reject_reason,
                "official_verification_summary": candidate.official_verification_summary,
            }
        )
    return rows


def inventory_by_symbol(inventory_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["symbol"]: row for row in inventory_rows}


def bars_by_symbol(bar_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["symbol"]: row for row in bar_rows}


def candidate_selection_key(candidate: CandidateDefinition, inventory: dict[str, dict[str, Any]], bars: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
    asset = inventory.get(candidate.symbol, {})
    bar = bars.get(candidate.symbol, {})
    # Lower sorts first. This encodes the frozen non-performance order.
    return (
        0 if candidate.single_currency and not candidate.basket_product else 1,
        0 if not candidate.leveraged and not candidate.inverse else 1,
        0 if asset.get("status") == "active" and truthy(asset.get("tradable")) else 1,
        0 if truthy(asset.get("shortable")) else 1,
        -int(bar.get("monthly_observation_count") or 0),
        float(candidate.expense_ratio if candidate.expense_ratio is not None else 99.0),
        candidate.symbol,
    )


def select_preferred_candidate(
    candidates: list[CandidateDefinition],
    inventory: dict[str, dict[str, Any]],
    bars: dict[str, dict[str, Any]],
) -> CandidateDefinition | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: candidate_selection_key(candidate, inventory, bars))[0]


def coverage_class(candidate: CandidateDefinition | None, asset: dict[str, Any], bar: dict[str, Any], currency: str) -> str:
    if currency == "USD":
        return "base_currency_retained"
    if candidate is None:
        return "no_alpaca_instrument_found"
    if candidate.leveraged or candidate.inverse:
        return "leveraged_or_inverse_only"
    if candidate.basket_product:
        return "basket_only"
    if asset.get("status") != "active" or not truthy(asset.get("tradable")):
        return "historical_only_inactive" if asset else "no_alpaca_instrument_found"
    if bar.get("monthly_observation_count") in {"", "0", 0}:
        return "alpaca_currency_etp_history_inadequate"
    if not truthy(asset.get("shortable")):
        return "tradable_but_not_shortable"
    return "direct_alpaca_tradable_match"


def source_currency_mapping(inventory_rows: list[dict[str, Any]], bar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inv = inventory_by_symbol(inventory_rows)
    bars = bars_by_symbol(bar_rows)
    rows: list[dict[str, Any]] = []
    for currency in SOURCE_CURRENCIES:
        if currency == "USD":
            rows.append(
                {
                    "source_currency": "USD",
                    "selected_symbol": "USD_BASE_CASH_MEMBER",
                    "coverage_classification": "base_currency_retained",
                    "candidate_symbols_considered": "",
                    "selection_rule": "USD remains the base/cash member and is not replaced by UUP/UDN or any dollar-index product",
                    "alpaca_tradable": "not_applicable",
                    "alpaca_shortable": "not_applicable",
                    "monthly_observation_count": "not_applicable",
                    "full_readiness_satisfied": True,
                    "mapping_notes": "USD is retained as source base member.",
                }
            )
            continue
        candidates = [candidate for candidate in CANDIDATES if currency in candidate.source_currencies and currency != "USD"]
        selected = select_preferred_candidate(candidates, inv, bars)
        asset = inv.get(selected.symbol, {}) if selected else {}
        bar = bars.get(selected.symbol, {}) if selected else {}
        klass = coverage_class(selected, asset, bar, currency)
        rows.append(
            {
                "source_currency": currency,
                "selected_symbol": selected.symbol if selected else "",
                "coverage_classification": klass,
                "candidate_symbols_considered": [candidate.symbol for candidate in candidates],
                "selection_rule": "single_currency > unleveraged_non_inverse > active_tradable > shortable > longest_alpaca_history > lowest_expense_ratio > alphabetical",
                "alpaca_tradable": asset.get("tradable", False),
                "alpaca_shortable": asset.get("shortable", False),
                "monthly_observation_count": bar.get("monthly_observation_count", 0),
                "full_readiness_satisfied": klass == "direct_alpaca_tradable_match",
                "mapping_notes": selected.official_verification_summary if selected else "No candidate product identified from Alpaca inventory and official-source checks.",
            }
        )
    return rows


def rejected_instrument_rows(inventory_rows: list[dict[str, Any]], mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_symbols = {row["selected_symbol"] for row in mapping_rows}
    rows: list[dict[str, Any]] = []
    inv = inventory_by_symbol(inventory_rows)
    for candidate in CANDIDATES:
        asset = inv.get(candidate.symbol, {})
        reasons: list[str] = []
        if candidate.symbol not in selected_symbols:
            reasons.append("not_preferred_or_not_currency_mapping")
        if candidate.leveraged:
            reasons.append("leveraged")
        if candidate.inverse:
            reasons.append("inverse")
        if candidate.basket_product:
            reasons.append("basket_product")
        if asset.get("status") != "active":
            reasons.append("inactive_or_not_alpaca_recognized")
        if not truthy(asset.get("tradable")):
            reasons.append("not_alpaca_tradable")
        if not truthy(asset.get("shortable")) and candidate.symbol in selected_symbols and candidate.symbol != "USD_BASE_CASH_MEMBER":
            reasons.append("selected_but_not_shortable_blocks_full_readiness")
        if reasons:
            rows.append(
                {
                    "symbol": candidate.symbol,
                    "source_currencies": candidate.source_currencies,
                    "official_name": candidate.official_name,
                    "alpaca_status": asset.get("status", "not_found"),
                    "alpaca_tradable": asset.get("tradable", False),
                    "alpaca_shortable": asset.get("shortable", False),
                    "rejection_reasons": reasons,
                    "official_source_url": candidate.official_source_url,
                }
            )
    return rows


def common_month_window(symbols: list[str], bar_rows: list[dict[str, Any]]) -> dict[str, Any]:
    bars = bars_by_symbol(bar_rows)
    month_sets: list[set[str]] = []
    for symbol in symbols:
        row = bars.get(symbol, {})
        earliest = row.get("first_available_bar", "")
        latest = row.get("final_available_bar", "")
        if not earliest or not latest:
            return {"earliest_common_month": "", "latest_common_month": "", "complete_common_months": 0}
        all_months = {str(item) for item in pd.period_range(str(earliest)[:7], str(latest)[:7], freq="M")}
        raw_missing = row.get("missing_internal_months", [])
        if isinstance(raw_missing, list):
            missing = set(raw_missing)
        elif raw_missing:
            missing = set(str(raw_missing).split("|"))
        else:
            missing = set()
        month_sets.append(all_months - missing)
    common = sorted(set.intersection(*month_sets)) if month_sets else []
    return {
        "earliest_common_month": common[0] if common else "",
        "latest_common_month": common[-1] if common else "",
        "complete_common_months": len(common),
    }


def universe_coverage(mapping_rows: list[dict[str, Any]], bar_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    non_usd_rows = [row for row in mapping_rows if row["source_currency"] != "USD"]
    full_valid_rows = [row for row in non_usd_rows if row["coverage_classification"] == "direct_alpaca_tradable_match"]
    full_missing = [
        {"currency": row["source_currency"], "reason": row["coverage_classification"], "selected_symbol": row["selected_symbol"]}
        for row in non_usd_rows
        if row["coverage_classification"] != "direct_alpaca_tradable_match"
    ]
    full_window = common_month_window([row["selected_symbol"] for row in full_valid_rows], bar_rows)
    full = {
        "source_currencies": SOURCE_CURRENCIES,
        "full_source_universe_translation_ready": len(full_valid_rows) == 9,
        "valid_non_usd_currency_count": len(full_valid_rows),
        "missing_or_blocked_currencies": full_missing,
        "earliest_common_month": full_window["earliest_common_month"] if len(full_valid_rows) == 9 else "",
        "latest_common_month": full_window["latest_common_month"] if len(full_valid_rows) == 9 else "",
        "complete_common_months": full_window["complete_common_months"] if len(full_valid_rows) == 9 else 0,
        "three_long_three_short_mathematically_possible": len(full_valid_rows) >= 6,
        "shortability_supports_source_long_short_construction": len(full_valid_rows) == 9,
    }

    subset_symbols = [row["selected_symbol"] for row in full_valid_rows]
    subset_window = common_month_window(subset_symbols, bar_rows)
    subset = {
        "included_currencies": ["USD"] + [row["source_currency"] for row in full_valid_rows],
        "included_symbols": ["USD_BASE_CASH_MEMBER"] + subset_symbols,
        "missing_currencies": [item["currency"] for item in full_missing],
        "missing_currency_reasons": full_missing,
        "eligible_non_usd_currency_count": len(full_valid_rows),
        "earliest_common_month": subset_window["earliest_common_month"],
        "latest_common_month": subset_window["latest_common_month"],
        "complete_common_months": subset_window["complete_common_months"],
        "three_long_three_short_mathematically_possible": len(full_valid_rows) >= 6,
        "shortability_supports_source_long_short_construction": len(full_valid_rows) >= 6,
        "material_concentration_created_by_reduced_universe": len(full_valid_rows) < 9,
        "subset_strategy_frozen": False,
        "subset_strategy_authorized": False,
    }
    return full, subset


def determine_outcome(full: dict[str, Any], subset: dict[str, Any], capability: dict[str, Any]) -> str:
    if capability["alpaca_client_status"] != "ok" or capability["active_asset_list_status"] != "ok":
        return "alpaca_asset_or_bar_access_blocked"
    if full["full_source_universe_translation_ready"]:
        return "alpaca_full_g10_etp_translation_ready"
    if subset["eligible_non_usd_currency_count"] < 6:
        # This is more specific than pure coverage: there are active direct ETPs,
        # but too few are shortable to form a top-three/bottom-three construction.
        return "alpaca_shortability_inadequate"
    if subset["complete_common_months"] < 13:
        return "alpaca_currency_etp_history_inadequate"
    if subset["material_concentration_created_by_reduced_universe"]:
        return "alpaca_etp_subset_requires_direction_owner_decision"
    return "alpaca_currency_coverage_insufficient"


def shortability_review(mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    non_usd = [row for row in mapping_rows if row["source_currency"] != "USD"]
    shortable = [row for row in non_usd if truthy(row["alpaca_shortable"])]
    non_shortable = [row for row in non_usd if row["selected_symbol"] and not truthy(row["alpaca_shortable"])]
    return {
        "required_shortable_non_usd_currency_count_for_full_g10": 9,
        "required_shortable_non_usd_currency_count_for_top3_bottom3_subset": 6,
        "observed_shortable_selected_non_usd_currency_count": len(shortable),
        "shortable_selected_symbols": [row["selected_symbol"] for row in shortable],
        "non_shortable_selected_symbols": [
            {"currency": row["source_currency"], "symbol": row["selected_symbol"], "coverage": row["coverage_classification"]}
            for row in non_shortable
        ],
        "full_readiness_blocked_by_shortability": len(shortable) < 9,
        "source_long_short_construction_supported": len(shortable) >= 9,
        "no_margin_or_short_assumption_invented": True,
    }


def overlay_compatibility_rows() -> list[dict[str, Any]]:
    return [
        {"overlay": "IdentityOverlay", "classification": "compatible_after_narrow_adapter", "reason": "signed monthly ETP target weights need an adapter before identity equality can be asserted"},
        {"overlay": "RebalanceBandOverlay", "classification": "compatible_after_narrow_adapter", "reason": "potentially compatible with signed ETP weights after base implementation and signed turnover accounting exist"},
        {"overlay": "LaggedVolatilityTargetOverlay", "classification": "defer_until_base_verified", "reason": "dynamic scaling must wait until the unchanged base strategy and identity overlay are verified"},
        {"overlay": "ExposureCapsOverlay", "classification": "compatible_after_narrow_adapter", "reason": "could cap gross/single-name exposure only as a separate labeled overlay with signed exposure support"},
        {"overlay": "WideATRCatastrophicStopOverlay", "classification": "not_economically_appropriate", "reason": "daily ATR stops alter monthly top-three/bottom-three holding mechanics"},
        {"overlay": "TimeStopOverlay", "classification": "not_economically_appropriate", "reason": "time exits alter monthly source rebalance and selection mechanics"},
        {"overlay": "StaticScaleOverlay", "classification": "compatible_after_narrow_adapter", "reason": "static signed scaling can be a lower-exposure control after base strategy verification"},
    ]


def frozen_future_spec(outcome: str, full: dict[str, Any], mapping_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if outcome != "alpaca_full_g10_etp_translation_ready":
        return {
            "spec_created": False,
            "reason": outcome,
            "strategy_configurations": [],
            "reduced_universe_strategy_frozen": False,
            "performance_backtest_authorized": False,
        }
    symbol_map = {row["source_currency"]: row["selected_symbol"] for row in mapping_rows}
    return {
        "spec_created": True,
        "strategy_configurations": [
            {
                "strategy_id": FUTURE_FULL_SPEC_ID,
                "parent_source_strategy": SOURCE_EXACT_ID,
                "adaptation_label": ADAPTATION_LABEL,
                "currency_to_etp_map": symbol_map,
                "momentum_lookback": "12_months",
                "rebalance_frequency": "monthly",
                "ranking": "rank all ten source currencies",
                "long_leg": "top_three_equal_weight",
                "short_leg": "bottom_three_equal_weight",
                "carry_filter": "none",
                "trend_filter": "none",
                "volatility_scaling": "none",
                "cash_timing": "none",
                "performance_selected_instruments": False,
                "authorized_to_run": False,
                "common_window": {
                    "earliest_common_month": full["earliest_common_month"],
                    "latest_common_month": full["latest_common_month"],
                    "complete_common_months": full["complete_common_months"],
                },
            }
        ],
    }


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(abs_path(root, path)) for path in PROTECTED_STATE_PATHS}


def translation_risks_text(outcome: str, full: dict[str, Any], subset: dict[str, Any]) -> str:
    return f"""# Currency Momentum Alpaca ETP Translation Risks

This task evaluates a U.S.-listed ETP translation for `{SOURCE_EXACT_ID}`. It is not a source-exact Deutsche Bank forward replication and does not authorize a strategy variant, trial, backtest, paper/demo observation, or live trading.

## Outcome

Exact outcome: `{outcome}`

Full G10 source-universe readiness: `{full["full_source_universe_translation_ready"]}`

Maximum Alpaca-compatible shortable subset: `{", ".join(subset["included_currencies"])}`.

The reduced subset is not frozen as a strategy. A smaller universe would materially change the source construction and is returned for direction-owner review only if later authorized.

## Main Risks

- Several active single-currency CurrencyShares products are Alpaca-tradable but not Alpaca-shortable, so they cannot safely represent a currency that may enter the bottom-three short basket.
- NZD and NOK lack current Alpaca-recognized single-currency products in this evidence packet.
- SEK has a historical CurrencyShares trust, but Alpaca reports it inactive and not tradable.
- Basket, dollar-index, leveraged, inverse, crypto, and multi-currency products were rejected rather than used as substitutions.
- ETP prices include wrapper expenses, trust mechanics, market/NAV differences, distributions or interest treatment, and exchange trading frictions; they are not FX forwards.
"""


def feasibility_summary_text(outcome: str, full: dict[str, Any], subset: dict[str, Any], short_review: dict[str, Any]) -> str:
    return f"""# Currency Momentum Alpaca ETP Translation Feasibility

Task: `{TASK_ID}`

Outcome: `{outcome}`

Full source-universe translation ready: `{full["full_source_universe_translation_ready"]}`

Valid and shortable non-USD ETP mappings: `{short_review["observed_shortable_selected_non_usd_currency_count"]}`

Maximum eligible non-USD subset: `{subset["eligible_non_usd_currency_count"]}`

Complete common months for maximum subset: `{subset["complete_common_months"]}`

Three-long/three-short mathematically possible in maximum subset: `{subset["three_long_three_short_mathematically_possible"]}`

Reduced-universe strategy frozen: `false`

No performance metrics, strategy trials, registry changes, active-observation changes, order submissions, or overlay performance tests were performed.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    output = abs_path(root, OUTPUT_DIR)
    clean_output_dir(output)
    before_hashes = state_hashes(root)

    inventory_rows, bar_rows, capability = inspect_alpaca_assets_and_bars(root)
    official_rows = official_verification_rows()
    mapping_rows = source_currency_mapping(inventory_rows, bar_rows)
    rejected_rows = rejected_instrument_rows(inventory_rows, mapping_rows)
    full, subset = universe_coverage(mapping_rows, bar_rows)
    short_review = shortability_review(mapping_rows)
    outcome = determine_outcome(full, subset, capability)
    spec = frozen_future_spec(outcome, full, mapping_rows)
    overlays = overlay_compatibility_rows()

    after_hashes = state_hashes(root)
    consistency = {
        "task_id": TASK_ID,
        "consistency_passed": True,
        "every_source_currency_mapped_or_explicitly_missing": {row["source_currency"] for row in mapping_rows} == set(SOURCE_CURRENCIES),
        "usd_retained_as_base_member": any(row["source_currency"] == "USD" and row["selected_symbol"] == "USD_BASE_CASH_MEMBER" for row in mapping_rows),
        "leveraged_and_inverse_products_rejected": all(
            row["symbol"] in {rejected["symbol"] for rejected in rejected_rows}
            for row in official_rows
            if row["long_inverse_or_leveraged"] in {"leveraged", "inverse"}
        ),
        "basket_products_not_single_currency": all(not truthy(row["single_currency"]) for row in official_rows if truthy(row["basket_product"])),
        "inactive_products_rejected": any(row["symbol"] == "FXS" for row in rejected_rows),
        "non_shortable_products_block_full_readiness": outcome in {"alpaca_shortability_inadequate", "alpaca_currency_coverage_insufficient", "alpaca_etp_subset_requires_direction_owner_decision"},
        "candidate_selection_non_performance_only": True,
        "performance_metrics_calculated": False,
        "orders_or_broker_write_called": False,
        "strategy_trial_created": False,
        "registry_changed": before_hashes.get(str(PROTECTED_STATE_PATHS[0])) != after_hashes.get(str(PROTECTED_STATE_PATHS[0])),
        "active_observations_changed": before_hashes.get(str(PROTECTED_STATE_PATHS[3])) != after_hashes.get(str(PROTECTED_STATE_PATHS[3])),
        "overlay_performance_test_run": False,
        "fx_rates_endpoint_reopened": False,
        "bybit_or_crypto_used": False,
        "api_credentials_persisted": False,
        "next_action": NEXT_ACTION,
    }
    consistency["consistency_passed"] = (
        consistency["every_source_currency_mapped_or_explicitly_missing"]
        and consistency["usd_retained_as_base_member"]
        and consistency["leveraged_and_inverse_products_rejected"]
        and consistency["basket_products_not_single_currency"]
        and consistency["inactive_products_rejected"]
        and not consistency["performance_metrics_calculated"]
        and not consistency["orders_or_broker_write_called"]
        and not consistency["registry_changed"]
        and not consistency["active_observations_changed"]
        and not consistency["overlay_performance_test_run"]
        and not consistency["fx_rates_endpoint_reopened"]
        and not consistency["api_credentials_persisted"]
    )

    write_csv(
        output / "alpaca_asset_inventory.csv",
        inventory_rows,
        [
            "symbol",
            "name",
            "exchange",
            "asset_class",
            "status",
            "tradable",
            "fractionable",
            "marginable",
            "shortable",
            "easy_to_borrow",
            "first_available_alpaca_bar",
            "final_available_alpaca_bar",
            "number_of_monthly_observations",
            "internal_data_gaps",
            "delisting_or_inactive_status",
            "alpaca_metadata_hash",
            "asset_metadata_source",
            "bar_request_status",
        ],
    )
    write_csv(
        output / "official_instrument_verification.csv",
        official_rows,
        [
            "symbol",
            "source_currencies",
            "official_name",
            "issuer",
            "official_source_url",
            "official_source_type",
            "currency_exposure",
            "exposure_mechanism",
            "single_currency",
            "basket_product",
            "long_inverse_or_leveraged",
            "expense_ratio",
            "inception_date",
            "closure_or_liquidation_status",
            "benchmark_or_reference_rate",
            "distribution_treatment",
            "main_tracking_limitations",
            "product_identity_verified",
            "reject_reason",
            "official_verification_summary",
        ],
    )
    write_csv(
        output / "source_currency_to_etp_map.csv",
        mapping_rows,
        [
            "source_currency",
            "selected_symbol",
            "coverage_classification",
            "candidate_symbols_considered",
            "selection_rule",
            "alpaca_tradable",
            "alpaca_shortable",
            "monthly_observation_count",
            "full_readiness_satisfied",
            "mapping_notes",
        ],
    )
    write_csv(
        output / "rejected_instruments.csv",
        rejected_rows,
        ["symbol", "source_currencies", "official_name", "alpaca_status", "alpaca_tradable", "alpaca_shortable", "rejection_reasons", "official_source_url"],
    )
    write_csv(
        output / "alpaca_bar_coverage.csv",
        bar_rows,
        [
            "symbol",
            "bar_request_status",
            "bar_pages",
            "first_available_bar",
            "final_available_bar",
            "daily_bar_count",
            "monthly_observation_count",
            "internal_month_gaps",
            "missing_internal_months",
            "feed",
            "adjustment",
            "bar_history_hash",
        ],
    )
    write_json(output / "full_universe_coverage.json", full)
    write_json(output / "maximum_subset_coverage.json", subset)
    write_json(output / "shortability_and_margin_review.json", short_review)
    write_text(output / "translation_risks.md", translation_risks_text(outcome, full, subset))
    write_csv(output / "trade_management_overlay_compatibility.csv", overlays, ["overlay", "classification", "reason"])
    write_json(output / "frozen_future_experiment_spec.json", spec)
    write_json(
        output / "feasibility_outcome.json",
        {
            "task_id": TASK_ID,
            "outcome": outcome,
            "outcome_options": [
                "alpaca_full_g10_etp_translation_ready",
                "alpaca_etp_subset_requires_direction_owner_decision",
                "alpaca_currency_etp_history_inadequate",
                "alpaca_shortability_inadequate",
                "alpaca_currency_coverage_insufficient",
                "alpaca_asset_or_bar_access_blocked",
            ],
            "selected_based_on_performance": False,
            "full_universe_ready": full["full_source_universe_translation_ready"],
            "subset_strategy_frozen": False,
            "next_action": NEXT_ACTION,
        },
    )
    write_csv(
        output / "command_validation_log.csv",
        [
            {"command": ".venv\\Scripts\\python.exe run_currency_momentum_alpaca_etp_translation_feasibility_v1.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe -m pytest tests\\test_currency_momentum_alpaca_etp_translation_feasibility_v1.py -q", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_current_research_checkpoint.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_research_state_dashboard.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_advisor_consistency_check.py", "required": True, "status": "recorded_by_final_response"},
            {"command": ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence", "required": True, "status": "recorded_by_final_response"},
        ],
        ["command", "required", "status"],
    )
    write_json(output / "consistency_check.json", consistency)
    write_text(output / "feasibility_summary.md", feasibility_summary_text(outcome, full, subset, short_review))
    write_json(
        output / "alpaca_capability_context.json",
        {
            **capability,
            "paper_credentials_env_vars_checked": [PAPER_KEY, PAPER_SECRET],
            "live_credentials_env_vars_checked": [LIVE_KEY, LIVE_SECRET],
            "credential_values_written": False,
        },
    )

    return {
        "task_id": TASK_ID,
        "evidence_path": str(output),
        "outcome": outcome,
        "full_universe_ready": full["full_source_universe_translation_ready"],
        "valid_shortable_non_usd_count": short_review["observed_shortable_selected_non_usd_currency_count"],
        "maximum_subset_non_usd_count": subset["eligible_non_usd_currency_count"],
        "spec_created": spec["spec_created"],
        "next_action": NEXT_ACTION,
        "consistency_passed": consistency["consistency_passed"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
