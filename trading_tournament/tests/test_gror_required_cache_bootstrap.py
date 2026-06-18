from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import run_gror_required_cache_bootstrap as bootstrap


def synthetic_raw(symbol: str, periods: int = 520) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=periods)
    base = 50.0 + len(symbol)
    prices = [base + idx * 0.05 for idx in range(periods)]
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": [1000000] * periods,
            "Dividends": [0.0] * periods,
            "Stock Splits": [0.0] * periods,
        }
    )


def write_cache(root: Path, symbol: str, periods: int = 520) -> None:
    bootstrap.write_normalized_cache(root, symbol, synthetic_raw(symbol, periods=periods))


def test_existing_required_cache_is_detected_without_provider_call(tmp_path: Path) -> None:
    for symbol in bootstrap.APPROVED_SYMBOLS:
        write_cache(tmp_path, symbol)

    def downloader(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("provider should not be called when all cache files pass QA")

    result = bootstrap.run_cache_bootstrap(tmp_path, run_id="existing", downloader=downloader)
    manifest = result["manifest"]
    assert manifest["symbols_already_present"] == bootstrap.APPROVED_SYMBOLS
    assert manifest["symbols_downloaded"] == []
    assert manifest["symbols_failed"] == []
    assert manifest["provider_api_called"] is False


def test_missing_required_cache_is_downloaded_with_stub_provider(tmp_path: Path) -> None:
    write_cache(tmp_path, "SPY")
    calls: list[str] = []

    def downloader(symbol: str, start: str, end: str | None, params: dict) -> pd.DataFrame:
        calls.append(symbol)
        return synthetic_raw(symbol)

    result = bootstrap.run_cache_bootstrap(tmp_path, run_id="download", downloader=downloader)
    manifest = result["manifest"]
    assert manifest["symbols_already_present"] == ["SPY"]
    assert manifest["symbols_downloaded"] == ["QQQ", "GLD", "IEF", "BIL"]
    assert manifest["symbols_failed"] == []
    assert manifest["provider_api_called"] is True
    assert calls == ["QQQ", "GLD", "IEF", "BIL"]
    assert result["consistency"]["all_required_symbols_passed_qa"] is True


def test_forbidden_symbols_are_rejected_before_download(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="AAPL"):
        bootstrap.run_cache_bootstrap(tmp_path, symbols=["SPY", "AAPL"], run_id="forbidden")


def test_quality_requires_adjusted_close_warmup_and_positive_values(tmp_path: Path) -> None:
    write_cache(tmp_path, "SPY", periods=100)
    qa = bootstrap.qa_cache_file(tmp_path, "SPY")
    assert qa["qa_passed"] is False
    assert qa["warmup_sufficiency"] is False

    write_cache(tmp_path, "QQQ", periods=bootstrap.REQUIRED_WARMUP_ROWS)
    qa = bootstrap.qa_cache_file(tmp_path, "QQQ")
    assert qa["adjusted_close_availability"] is True
    assert qa["qa_passed"] is True


def test_outputs_label_exploratory_non_institutional_and_no_strategy_validation(tmp_path: Path) -> None:
    for symbol in bootstrap.APPROVED_SYMBOLS:
        write_cache(tmp_path, symbol)

    result = bootstrap.run_cache_bootstrap(tmp_path, run_id="labels")
    latest = Path(result["latest_dir"])
    manifest = json.loads((latest / "cache_bootstrap_manifest.json").read_text(encoding="utf-8"))
    consistency = json.loads((latest / "cache_bootstrap_consistency_check.json").read_text(encoding="utf-8"))

    assert manifest["exploratory_data_only"] is True
    assert manifest["institutional_grade_data"] is False
    assert manifest["real_money_ready"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["strategy_validation_run"] is False
    assert consistency["strategy_validation_run"] is False
    assert consistency["required_outputs_exist"] is True
