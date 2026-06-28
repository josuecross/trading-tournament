from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


ALLOWED_TIMEFRAMES = {"1Min": 60, "5Min": 300}
REQUIRED_FIELDS = {
    "symbol",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "timeframe",
    "source",
}


def parse_utc_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("timestamp is empty")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    else:
        raise ValueError(f"unsupported timestamp type: {type(value).__name__}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _decimal_field(row: Mapping[str, Any], field: str) -> Decimal:
    value = row.get(field)
    if value is None or value == "":
        raise ValueError(f"{field} must not be null")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if field != "volume" and parsed <= 0:
        raise ValueError(f"{field} must be positive")
    if field == "volume" and parsed < 0:
        raise ValueError("volume must be non-negative")
    return parsed


def normalize_intraday_bar(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_FIELDS - set(row))
    if missing:
        raise ValueError(f"missing intraday bar fields: {', '.join(missing)}")
    symbol = str(row["symbol"]).strip().upper()
    if not symbol:
        raise ValueError("symbol must not be empty")
    timeframe = str(row["timeframe"]).strip()
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(f"timeframe must be one of {sorted(ALLOWED_TIMEFRAMES)}")
    source = str(row["source"]).strip()
    if not source:
        raise ValueError("source must not be empty")
    timestamp = parse_utc_timestamp(row["timestamp"])
    open_price = _decimal_field(row, "open")
    high = _decimal_field(row, "high")
    low = _decimal_field(row, "low")
    close = _decimal_field(row, "close")
    volume = _decimal_field(row, "volume")
    if high < max(open_price, close, low):
        raise ValueError("high must be greater than or equal to open, low, and close")
    if low > min(open_price, close, high):
        raise ValueError("low must be less than or equal to open, high, and close")
    return {
        "symbol": symbol,
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "timeframe": timeframe,
        "source": source,
        "adjusted": bool(row.get("adjusted", False)),
    }


def validate_intraday_bars(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, datetime]] = set()
    last_by_symbol: dict[str, datetime] = {}
    for row in rows:
        bar = normalize_intraday_bar(row)
        key = (bar["symbol"], bar["timestamp"])
        if key in seen:
            raise ValueError(f"duplicate symbol/timestamp row: {bar['symbol']} {bar['timestamp'].isoformat()}")
        previous = last_by_symbol.get(bar["symbol"])
        if previous is not None and bar["timestamp"] <= previous:
            raise ValueError(f"timestamps must be monotonic for {bar['symbol']}")
        seen.add(key)
        last_by_symbol[bar["symbol"]] = bar["timestamp"]
        normalized.append(bar)
    if not normalized:
        raise ValueError("intraday bar set must not be empty")
    return normalized
