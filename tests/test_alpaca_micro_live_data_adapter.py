from __future__ import annotations

from datetime import datetime, timezone

import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.data.alpaca_historical_bars import parse_bars_response


pytestmark = pytest.mark.alpaca_micro_live


def test_historical_bars_parsing_drops_incomplete_current_day():
    today = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "bars": {
            "SPY": [
                {"t": "2026-01-02T05:00:00Z", "o": 1, "h": 2, "l": 1, "c": 2, "v": 10},
                {"t": f"{today}T05:00:00Z", "o": 2, "h": 3, "l": 2, "c": 3, "v": 10},
            ]
        }
    }
    parsed = parse_bars_response(payload)
    assert len(parsed["SPY"]) == 1
    assert parsed["SPY"]["date"].iloc[0] == "2026-01-02"
