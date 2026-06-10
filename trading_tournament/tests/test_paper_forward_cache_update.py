from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
UPDATE_DIR = ROOT / "data_acquisition_runs" / "paper_forward_observation_cache_update"
SCRIPT_PATH = UPDATE_DIR / "run_paper_forward_cache_update.py"
LATEST_DIR = ROOT / "evidence" / "data_acquisition_runs" / "paper_forward_observation_cache_update" / "latest"
UPDATE_ZIP = ROOT / "evidence" / "data_acquisition_runs" / "paper_forward_observation_cache_update" / "latest_cache_update_packet.zip"
OBS_DIR = ROOT / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1"
PAPER_LATEST = ROOT / "evidence" / "paper_forward_runs" / "latest"
ADVISOR_LATEST = ROOT / "evidence" / "advisor_upload" / "latest"


def load_update_module():
    spec = importlib.util.spec_from_file_location("paper_forward_cache_update", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cache_update_config_exists_and_allows_only_spy_gld_bil() -> None:
    config = yaml.safe_load((UPDATE_DIR / "cache_update_config.yaml").read_text(encoding="utf-8"))
    assert config["allowed_symbols"] == ["SPY", "GLD", "BIL"]
    assert str(config["requested_activation_date"]) == "2026-06-05"
    assert config["canonical_rule_hash"] == "6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67"
    assert config["strategy_implementation_allowed"] is False
    assert config["backtest_allowed"] is False
    assert config["profit_exploration_allowed"] is False
    assert config["broker_integration"] is False
    assert config["live_orders"] is False
    assert config["order_placement"] is False
    assert config["real_money_recommendation"] is False


def test_unapproved_symbols_are_rejected() -> None:
    module = load_update_module()
    config = module.load_config()
    with pytest.raises(ValueError):
        module.validate_requested_symbols(config, ["SPY", "GLD", "BIL", "QQQ"])
    with pytest.raises(ValueError):
        module.validate_requested_symbols(config, ["SPY", "GLD"])


def test_cache_update_evidence_latest_is_compact_and_excludes_raw_ohlcv() -> None:
    assert LATEST_DIR.exists()
    files = [path for path in LATEST_DIR.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert UPDATE_ZIP.exists()
    with zipfile.ZipFile(UPDATE_ZIP) as zf:
        names = set(zf.namelist())
    assert "cache_update_manifest.json" in names
    forbidden_name_parts = {"raw_ohlcv", "ohlcv"}
    assert not any(any(part in path.name.lower() for part in forbidden_name_parts) for path in files)


def test_cache_update_manifest_records_activation_date_support_and_safety_flags() -> None:
    manifest = json.loads((LATEST_DIR / "cache_update_manifest.json").read_text(encoding="utf-8"))
    assert manifest["requested_activation_date"] == "2026-06-05"
    assert "latest_common_cached_date" in manifest
    assert "requested_activation_date_supported" in manifest
    assert manifest["keyed_provider_used"] is False
    assert manifest["api_key_or_secret_written"] is False
    assert manifest["raw_ohlcv_included"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False


def test_combo_activation_state_matches_cache_support_gate() -> None:
    manifest = json.loads((LATEST_DIR / "cache_update_manifest.json").read_text(encoding="utf-8"))
    config = yaml.safe_load((OBS_DIR / "observation_config.yaml").read_text(encoding="utf-8"))
    activation = json.loads((OBS_DIR / "observation_activation_manifest.json").read_text(encoding="utf-8"))
    supported = bool(manifest["requested_activation_date_supported"])
    assert config["canonical_rule_hash"] == "6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67"
    assert config["rule_hash_verified"] is True
    assert activation["spy200d_replaced"] is False
    if supported:
        assert config["status"] == "active_paper_demo_observation"
        assert activation["activation_status"] == "active_paper_demo_observation"
        assert activation["paper_forward_active"] is True
    else:
        assert config["status"] in {"active_waiting_for_next_cached_trading_day", "activation_blocked_data_unavailable"}
        assert activation["paper_forward_active"] is False


def test_paper_forward_and_advisor_outputs_remain_compact_and_registry_validates() -> None:
    if PAPER_LATEST.exists():
        assert len([path for path in PAPER_LATEST.iterdir() if path.is_file()]) <= 10
    if ADVISOR_LATEST.exists():
        assert len([path for path in ADVISOR_LATEST.iterdir() if path.is_file()]) <= 10
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["real_money_recommendation"] is False
    assert "replace_spy200d_without_governance" in combo["forbidden_next_actions"]
    assert spy["paper_forward_active"] is True
    assert spy["rules_frozen"] is True
