from __future__ import annotations

from typing import Any

import pytest

from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError
from tests.alpaca_micro_live_fakes import fake_credentials

pytestmark = pytest.mark.alpaca_micro_live


class FakeResponse:
    def __init__(self, status_code: int, payload: Any | None = None, text: str = "error") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def test_broker_5xx_read_only_retry_classification() -> None:
    session = FakeSession([FakeResponse(500), FakeResponse(200, {"status": "ACTIVE"}, text="{}")])
    client = AlpacaClient(fake_credentials(), AlpacaClientConfig(retry_attempts=2, retry_backoff_seconds=(0,)), session=session)
    assert client.get_account()["status"] == "ACTIVE"
    assert len(session.calls) == 2


def test_broker_submit_5xx_is_ambiguous_and_not_retried() -> None:
    session = FakeSession([FakeResponse(500)])
    client = AlpacaClient(fake_credentials(), AlpacaClientConfig(retry_attempts=3, retry_backoff_seconds=(0,)), session=session)
    with pytest.raises(BrokerError) as exc_info:
        client.submit_order(symbol="SPY", side="buy", notional=5.0, client_order_id="fixed-id")
    exc = exc_info.value
    assert exc.category == "transient_server_error"
    assert exc.ambiguous_submission is True
    assert exc.client_order_id == "fixed-id"
    assert len(session.calls) == 1
