from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
LANE_DIR = ROOT / "data_acquisition_runs" / "global_multi_asset_fast_exploratory"
LATEST_DIR = ROOT / "evidence" / "data_acquisition_runs" / "global_multi_asset_fast_exploratory" / "latest"
ZIP_PATH = ROOT / "evidence" / "data_acquisition_runs" / "global_multi_asset_fast_exploratory" / "latest_global_multi_asset_acquisition_packet.zip"
APPROVED_SYMBOLS = {"SPY", "QQQ", "GLD", "IEF", "BIL", "DBC", "PDBC", "COMT", "GSG", "USCI", "IWM", "EFA", "EEM", "TLT"}
STRATEGY_SYMBOLS = {"SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT", "BIL"}


def test_global_acquisition_lane_exists_and_allows_exact_symbols() -> None:
    assert (LANE_DIR / "README.md").exists()
    assert (LANE_DIR / "run_global_multi_asset_fast_exploratory_acquisition.py").exists()
    config = yaml.safe_load((LANE_DIR / "acquisition_config.yaml").read_text(encoding="utf-8"))
    assert set(config["approved_symbols"]) == APPROVED_SYMBOLS
    assert set(config["strategy_universe_symbols"]) == STRATEGY_SYMBOLS
    assert config["provider"] == "yfinance_compatible"
    assert config["provider_policy"]["existing_cache_first"] is True
    assert config["evidence"]["raw_ohlcv_in_evidence"] is False


def test_global_acquisition_latest_evidence_contract() -> None:
    assert LATEST_DIR.exists()
    assert ZIP_PATH.exists()
    files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(files) <= 10
    assert files == {
        "README_FOR_ADVISOR.md",
        "acquisition_summary.md",
        "acquisition_metadata.json",
        "symbol_coverage_summary.csv",
        "data_quality_summary.csv",
        "cache_write_manifest.csv",
        "warnings_and_limitations.md",
        "acquisition_manifest.json",
    }
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == files
    manifest = json.loads((LATEST_DIR / "acquisition_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["approved_symbols"]) == APPROVED_SYMBOLS
    assert set(manifest["strategy_universe_symbols"]) == STRATEGY_SYMBOLS
    assert set(manifest["downloaded_symbols"]).issubset(APPROVED_SYMBOLS)
    assert set(manifest["cache_confirmed_symbols"]).issubset(APPROVED_SYMBOLS)
    assert set(manifest["failed_symbols"]).issubset(APPROVED_SYMBOLS)
    assert manifest["raw_ohlcv_included"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False


def test_global_acquisition_quality_summary_has_required_fields() -> None:
    quality = pd.read_csv(LATEST_DIR / "data_quality_summary.csv")
    assert set(quality["symbol"]) == APPROVED_SYMBOLS
    required = {
        "cached_or_downloaded",
        "cache_written",
        "row_count",
        "first_date",
        "last_date",
        "duplicate_date_count",
        "missing_adjusted_close_count",
        "missing_close_count",
        "missing_volume_count",
        "adjusted_close_available",
        "raw_close_available",
        "volume_available",
        "enough_rows_for_126d_momentum",
        "enough_rows_for_200d_sma",
        "enough_rows_for_180d_after_warmup",
        "quality_status",
    }
    assert required.issubset(quality.columns)
    assert set(quality["quality_status"]).issubset({"pass", "warning", "fail"})
