from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


MODULE_PATH = Path("data_acquisition_runs/value_momentum_factor_etf_rotation_v1/run_factor_etf_data_acquisition.py")
CONFIG_PATH = Path("data_acquisition_runs/value_momentum_factor_etf_rotation_v1/acquisition_config.yaml")
ALLOWED = ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPLV"]


def load_module():
    spec = importlib.util.spec_from_file_location("factor_etf_acquisition", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fake_raw_frame(rows: int = 420) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    close = pd.Series(range(rows), dtype=float) * 0.1 + 50.0
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": close + 0.1,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Adj Close": close * 0.98,
            "Volume": 100000,
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        }
    )
    return frame.set_index("Date")


def test_acquisition_config_exists_and_symbol_scope_is_exact() -> None:
    assert CONFIG_PATH.exists()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["allowed_symbols"] == ALLOWED
    assert config["excluded_default_refresh_symbols"] == ["SPY", "BIL"]
    assert config["allow_symbol_refresh"] is False
    assert config["strategy_implementation_allowed"] is False
    assert config["backtest_allowed"] is False
    assert config["paper_forward_allowed"] is False
    assert config["real_money_recommendation"] is False


def test_unapproved_symbols_are_rejected() -> None:
    module = load_module()
    config = module.load_config(CONFIG_PATH)
    with pytest.raises(ValueError):
        module.validate_requested_symbols(config, ["MTUM", "VLUE", "VTV", "QUAL", "USMV", "SPY"])
    with pytest.raises(ValueError):
        module.validate_requested_symbols(config, ALLOWED + ["BIL"])


def test_fake_acquisition_outputs_compact_evidence_and_no_raw_ohlcv(tmp_path: Path) -> None:
    module = load_module()

    def downloader(symbol: str, settings: dict) -> pd.DataFrame:
        assert symbol in ALLOWED
        return fake_raw_frame()

    outputs = module.run_acquisition(
        repo_root=tmp_path,
        config_path=CONFIG_PATH,
        downloader=downloader,
        run_id="test_run",
        update_registry=False,
    )
    latest_files = {path.name for path in outputs.latest_dir.iterdir() if path.is_file()}
    assert len(latest_files) <= 10
    assert latest_files == {
        "README_FOR_ADVISOR.md",
        "acquisition_summary.md",
        "acquisition_metadata.json",
        "symbol_coverage_summary.csv",
        "data_quality_summary.csv",
        "data_gap_report.csv",
        "adjustment_field_report.csv",
        "cache_write_manifest.csv",
        "warnings_and_limitations.md",
        "acquisition_manifest.json",
    }
    assert outputs.zip_path.exists()
    with zipfile.ZipFile(outputs.zip_path) as zf:
        assert set(zf.namelist()) == latest_files
    assert not any(path.name.endswith(".csv") and path.name in {f"{symbol}.csv" for symbol in ALLOWED} for path in outputs.latest_dir.iterdir())
    assert (tmp_path / "data/cache/MTUM.csv").exists()


def test_fake_acquisition_reports_quality_and_cache_manifest(tmp_path: Path) -> None:
    module = load_module()
    outputs = module.run_acquisition(
        repo_root=tmp_path,
        config_path=CONFIG_PATH,
        downloader=lambda symbol, settings: fake_raw_frame(),
        run_id="test_quality",
        update_registry=False,
    )
    coverage = pd.read_csv(outputs.latest_dir / "symbol_coverage_summary.csv")
    quality = pd.read_csv(outputs.latest_dir / "data_quality_summary.csv")
    adjustment = pd.read_csv(outputs.latest_dir / "adjustment_field_report.csv")
    cache_manifest = pd.read_csv(outputs.latest_dir / "cache_write_manifest.csv")
    assert set(coverage["symbol"]) == set(ALLOWED)
    assert set(quality["symbol"]) == set(ALLOWED)
    assert set(adjustment["symbol"]) == set(ALLOWED)
    assert set(cache_manifest["symbol"]) == set(ALLOWED)
    assert quality["adjusted_close_available"].all()
    assert quality["raw_close_available"].all()
    assert quality["enough_rows_for_180d_rolling_after_warmup"].all()
    assert set(quality["quality_status"]) == {"pass"}
    assert cache_manifest["write_status"].eq("written").all()
    assert cache_manifest["sha256"].astype(str).str.len().gt(20).all()


def test_manifest_safety_flags_and_no_secrets(tmp_path: Path) -> None:
    module = load_module()
    outputs = module.run_acquisition(
        repo_root=tmp_path,
        config_path=CONFIG_PATH,
        downloader=lambda symbol, settings: fake_raw_frame(),
        run_id="test_manifest",
        update_registry=False,
    )
    manifest = json.loads((outputs.latest_dir / "acquisition_manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_downloaded"] is True
    assert manifest["api_called"] is True
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["raw_ohlcv_included"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{12,}"),
        re.compile(r"api[_-]?key\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
        re.compile(r"token\\s*[:=]\\s*['\\\"][A-Za-z0-9_\\-]{12,}['\\\"]", re.IGNORECASE),
    ]
    for path in outputs.latest_dir.iterdir():
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(pattern.search(text) for pattern in secret_patterns)
        assert "recommended real trade" not in text.lower()
        assert "real-money ready" not in text.lower()


def test_no_strategy_implementation_or_backtest_trigger_in_script() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "run_profit_exploration" not in source
    assert "import run_backtest" not in source
    assert "run_backtest.py" not in source
    assert "run_report" not in source
    assert "subprocess" not in source
    assert "Strategy" not in source


def test_strategy_lab_value_row_remains_not_implemented() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == "value_momentum_factor_etf_rotation_v1")
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["paper_forward_active"] is False
    assert row["real_money_recommendation"] is False


def test_advisor_upload_stays_compact(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
