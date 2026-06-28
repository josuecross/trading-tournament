from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from intraday_research.data_schema import ALLOWED_TIMEFRAMES, parse_utc_timestamp, validate_intraday_bars


@dataclass(frozen=True)
class CacheInspection:
    status: str
    data_present: bool
    metadata_present: bool
    row_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    stale: bool
    missing_bar_count: int
    missing_bar_examples: tuple[str, ...]


@dataclass(frozen=True)
class IntradayCacheContract:
    root: Path = Path("data/intraday")
    metadata_suffix: str = ".metadata.json"

    @property
    def allowed_timeframes(self) -> tuple[str, ...]:
        return tuple(sorted(ALLOWED_TIMEFRAMES))

    def cache_path(self, symbol: str, timeframe: str) -> Path:
        self._validate_timeframe(timeframe)
        return self.root / timeframe / f"{symbol.upper()}_{timeframe}.csv"

    def metadata_path(self, symbol: str, timeframe: str) -> Path:
        path = self.cache_path(symbol, timeframe)
        return path.with_suffix(self.metadata_suffix)

    def metadata_template(self, symbol: str, timeframe: str, source: str = "manual_review_required") -> dict[str, Any]:
        self._validate_timeframe(timeframe)
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "source": source,
            "timezone_policy": "timestamps_normalized_to_utc",
            "schema": "intraday_research_v1",
            "first_timestamp": None,
            "last_timestamp": None,
            "row_count": 0,
            "adjusted": None,
            "early_close_calendar": "placeholder_required_before_research",
            "holiday_calendar": "placeholder_required_before_research",
            "provider_download_performed_by_contract": False,
        }

    def inspect(self, symbol: str, timeframe: str, max_stale_days: int = 7) -> CacheInspection:
        path = self.cache_path(symbol, timeframe)
        metadata_path = self.metadata_path(symbol, timeframe)
        if not path.exists():
            return CacheInspection(
                status="intraday_cache_contract_created_but_no_data_present",
                data_present=False,
                metadata_present=metadata_path.exists(),
                row_count=0,
                first_timestamp=None,
                last_timestamp=None,
                stale=True,
                missing_bar_count=0,
                missing_bar_examples=(),
            )
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        bars = validate_intraday_bars(rows)
        timestamps = [bar["timestamp"] for bar in bars]
        expected_delta = timedelta(seconds=ALLOWED_TIMEFRAMES[timeframe])
        missing_examples: list[str] = []
        missing_count = 0
        for previous, current in zip(timestamps, timestamps[1:]):
            gap = current - previous
            if gap > expected_delta:
                missing_count += max(int(gap.total_seconds() // expected_delta.total_seconds()) - 1, 1)
                if len(missing_examples) < 5:
                    missing_examples.append(f"{previous.isoformat()}->{current.isoformat()}")
        last_timestamp = max(timestamps)
        stale = datetime.now(timezone.utc) - last_timestamp > timedelta(days=max_stale_days)
        return CacheInspection(
            status="intraday_cache_present_requires_source_approval",
            data_present=True,
            metadata_present=metadata_path.exists(),
            row_count=len(bars),
            first_timestamp=min(timestamps).isoformat(),
            last_timestamp=last_timestamp.isoformat(),
            stale=stale,
            missing_bar_count=missing_count,
            missing_bar_examples=tuple(missing_examples),
        )

    def read_metadata(self, symbol: str, timeframe: str) -> dict[str, Any] | None:
        path = self.metadata_path(symbol, timeframe)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("first_timestamp"):
            parse_utc_timestamp(payload["first_timestamp"])
        if payload.get("last_timestamp"):
            parse_utc_timestamp(payload["last_timestamp"])
        return payload

    def _validate_timeframe(self, timeframe: str) -> None:
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {sorted(ALLOWED_TIMEFRAMES)}")
