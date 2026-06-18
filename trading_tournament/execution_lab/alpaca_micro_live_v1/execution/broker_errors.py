from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class BrokerError(Exception):
    category: str
    message: str
    status_code: int | None = None
    response_text: str | None = None
    ambiguous_submission: bool = False
    client_order_id: str | None = None
    submission_attempt_id: str | None = None

    def __str__(self) -> str:
        return f"{self.category}: {self.message}"


def classify_http_status(status_code: int) -> str:
    if status_code == 429:
        return "rate_limit_error"
    if status_code in {401, 403}:
        return "auth_error"
    if status_code in {400, 422}:
        return "validation_error"
    if 500 <= status_code <= 599:
        return "transient_server_error"
    return "unknown_broker_error"


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return "network_error"
    if isinstance(exc, requests.RequestException):
        return "unknown_broker_error"
    return "unknown_broker_error"


def broker_error_from_response(response: requests.Response, message: str | None = None) -> BrokerError:
    return BrokerError(
        category=classify_http_status(response.status_code),
        message=message or f"Alpaca returned HTTP {response.status_code}",
        status_code=response.status_code,
        response_text=response.text,
    )

