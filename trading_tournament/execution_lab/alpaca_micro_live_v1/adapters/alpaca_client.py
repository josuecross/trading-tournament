from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.broker_errors import (
    BrokerError,
    broker_error_from_response,
    classify_exception,
    classify_http_status,
)


READ_ONLY_METHODS = {"GET"}


@dataclass
class AlpacaClientConfig:
    paper_base_url: str = "https://paper-api.alpaca.markets"
    data_base_url: str = "https://data.alpaca.markets"
    data_feed: str = "iex"
    data_adjustment: str = "all"
    retry_attempts: int = 3
    retry_backoff_seconds: tuple[int, ...] = (1, 3)


class AlpacaClient:
    def __init__(
        self,
        credentials: AlpacaCredentials,
        config: AlpacaClientConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        if credentials.environment != "paper":
            raise ValueError("Only Alpaca paper mode is supported.")
        self.credentials = credentials
        self.config = config or AlpacaClientConfig()
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        if not self.credentials.present:
            raise BrokerError("auth_error", "Alpaca paper credentials are missing.")
        return {
            "APCA-API-KEY-ID": self.credentials.api_key or "",
            "APCA-API-SECRET-KEY": self.credentials.secret_key or "",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        retry_read: bool = True,
    ) -> Any:
        method = method.upper()
        attempts = self.config.retry_attempts if retry_read and method in READ_ONLY_METHODS else 1
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: BrokerError | None = None
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=json,
                    timeout=20,
                )
            except requests.RequestException as exc:
                last_error = BrokerError(classify_exception(exc), str(exc))
            else:
                if 200 <= response.status_code < 300:
                    return response.json() if response.text else {}
                category = classify_http_status(response.status_code)
                last_error = broker_error_from_response(response)
                if category not in {"transient_server_error", "rate_limit_error"} or method not in READ_ONLY_METHODS:
                    raise last_error
            if attempt < attempts - 1:
                backoffs = self.config.retry_backoff_seconds
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
        raise last_error or BrokerError("unknown_broker_error", "Alpaca request failed.")

    def get_account(self) -> dict[str, Any]:
        return self._request("GET", self.config.paper_base_url, "/v2/account")

    def get_positions(self) -> list[dict[str, Any]]:
        return self._request("GET", self.config.paper_base_url, "/v2/positions")

    def get_assets(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        params = {"status": "active"}
        assets = self._request("GET", self.config.paper_base_url, "/v2/assets", params=params)
        if not symbols:
            return assets
        allowed = set(symbols)
        return [asset for asset in assets if asset.get("symbol") in allowed]

    def get_market_clock(self) -> dict[str, Any]:
        return self._request("GET", self.config.paper_base_url, "/v2/clock")

    def list_open_orders(self) -> list[dict[str, Any]]:
        return self._request("GET", self.config.paper_base_url, "/v2/orders", params={"status": "open"})

    def get_order_by_id(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", self.config.paper_base_url, f"/v2/orders/{order_id}")

    def submit_order(
        self,
        *,
        symbol: str,
        side: str,
        notional: float | None = None,
        qty: float | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "day",
    ) -> dict[str, Any]:
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
            "extended_hours": False,
            "client_order_id": client_order_id or f"alpaca-micro-{uuid.uuid4().hex[:20]}",
        }
        if notional is not None:
            payload["notional"] = f"{notional:.2f}"
        if qty is not None:
            payload["qty"] = str(qty)
        try:
            return self._request("POST", self.config.paper_base_url, "/v2/orders", json=payload, retry_read=False)
        except BrokerError as exc:
            exc.client_order_id = payload["client_order_id"]
            exc.submission_attempt_id = uuid.uuid4().hex
            if exc.category in {"transient_server_error", "network_error", "unknown_broker_error"}:
                exc.ambiguous_submission = True
            raise

    def get_historical_bars_page(
        self,
        *,
        symbols: list[str],
        start: str,
        end: str | None = None,
        timeframe: str = "1Day",
        page_token: str | None = None,
        feed: str | None = None,
        adjustment: str | None = None,
        limit: int = 10000,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "timeframe": timeframe,
            "start": start,
            "limit": limit,
            "feed": feed or self.config.data_feed,
            "adjustment": adjustment or self.config.data_adjustment,
        }
        if end:
            params["end"] = end
        if page_token:
            params["page_token"] = page_token
        return self._request("GET", self.config.data_base_url, "/v2/stocks/bars", params=params)
