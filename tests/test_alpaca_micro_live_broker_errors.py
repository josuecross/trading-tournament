from __future__ import annotations

import requests
import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import AlpacaCredentials
from trading_tournament.execution_lab.alpaca_micro_live_v1.execution.broker_errors import BrokerError


pytestmark = pytest.mark.alpaca_micro_live


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or ("{}" if payload is not None else "")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def client(session, attempts=2):
    return AlpacaClient(
        AlpacaCredentials("paper", "key", "secret", "test"),
        AlpacaClientConfig(retry_attempts=attempts, retry_backoff_seconds=(0,)),
        session=session,
    )


def test_read_only_5xx_retries():
    session = FakeSession([FakeResponse(500, text="server"), FakeResponse(200, {"status": "ACTIVE"})])
    result = client(session).get_account()
    assert result["status"] == "ACTIVE"
    assert session.calls == 2


def test_submit_5xx_creates_ambiguous_failure_and_no_duplicate():
    session = FakeSession([FakeResponse(500, text="server")])
    with pytest.raises(BrokerError) as err:
        client(session).submit_order(symbol="QUAL", side="buy", notional=5.0, client_order_id="cid")
    assert session.calls == 1
    assert err.value.ambiguous_submission is True
    assert err.value.client_order_id == "cid"
