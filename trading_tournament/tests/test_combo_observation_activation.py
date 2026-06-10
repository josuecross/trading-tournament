from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_paper_forward_observation as pfo
from run_strategy_lab import DEFAULT_REGISTRY, load_registry


ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1"
LATEST_DIR = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest"
OBS_ZIP = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest_observation_activation_packet.zip"


def test_combo_observation_activation_packet_exists_and_is_compact() -> None:
    assert OBS_DIR.exists()
    assert (OBS_DIR / "observation_config.yaml").exists()
    assert (OBS_DIR / "ACTIVATION_RECORD.md").exists()
    assert (OBS_DIR / "RULE_HASH_RECORD.md").exists()
    assert (OBS_DIR / "OBSERVATION_BOUNDARY.md").exists()
    assert LATEST_DIR.exists()
    assert len([p for p in LATEST_DIR.iterdir() if p.is_file()]) <= 10
    assert OBS_ZIP.exists()
    with zipfile.ZipFile(OBS_ZIP) as zf:
        names = set(zf.namelist())
    assert "observation_config.yaml" in names
    assert "RULE_HASH_RECORD.md" in names


def test_combo_activation_config_waits_after_rule_hash_resolution() -> None:
    config = yaml.safe_load((OBS_DIR / "observation_config.yaml").read_text(encoding="utf-8"))
    assert config["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    assert str(config["requested_activation_date"]) == "2026-06-05"
    assert config["rule_hash_required"] is True
    assert config["rule_hash_verified"] is True
    assert config["canonical_rule_hash"]
    assert config["hash_source_type"] == "source_spec_reconstructed_hash"
    assert config["replaces_spy200d"] is False
    assert config["broker_integration"] is False
    assert config["live_orders"] is False
    assert config["order_placement"] is False
    assert config["real_money_recommendation"] is False


def test_rule_hash_record_documents_source_spec_resolution() -> None:
    text = (OBS_DIR / "RULE_HASH_RECORD.md").read_text(encoding="utf-8")
    assert "canonical_rule_hash: `6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67`" in text
    assert "hash_source_type: `source_spec_reconstructed_hash`" in text
    assert "evidence/profit_exploration/latest/profit_rankings.csv" in text
    assert "strategy_lab/strategy_registry.yaml" in text
    assert "prior cache-date blocker is superseded" in text
    assert "combo is active as a separate simulated paper/demo observation" in text


def test_combo_registry_remains_inactive_and_spy_not_replaced() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    if combo["status"] == "active_paper_demo_observation":
        assert combo["paper_forward_active"] is True
        assert combo["allowed_next_action"] == "run_monthly_paper_forward_checkpoint"
        assert combo["paper_forward_allowed_by_risk_framework"] is True
    else:
        assert combo["paper_forward_active"] is False
        assert combo["allowed_next_action"] == "controlled_cache_update_or_next_cached_observation_date"
        assert combo["paper_forward_allowed_by_risk_framework"] is False
    assert combo["canonical_rule_hash"] == "6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67"
    assert combo["hash_source_type"] == "source_spec_reconstructed_hash"
    assert combo["real_money_recommendation"] is False
    assert "replace_spy200d_without_governance" in combo["forbidden_next_actions"]
    assert spy["paper_forward_active"] is True
    assert spy["rules_frozen"] is True


def test_paper_forward_writer_can_include_blocked_combo_row(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "paper_forward_runs"
    monkeypatch.setattr(pfo, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(pfo, "LATEST_ZIP", output_root / "latest_paper_forward_packet.zip")

    run_id = "combo_waiting_test"
    state = pfo.stop_state(pd.Series([pfo.STARTING_EQUITY]), pd.Index([pd.Timestamp("2026-06-05")]))
    spy_row = pfo.status_row(
        run_id,
        "2026-06-05",
        "2026-05-29",
        "SPY_200d_trend_model",
        "primary_watchlist_candidate",
        state,
        "no_new_data",
        "unavailable",
        "unavailable",
        "unavailable",
        0,
    )
    combo_row, combo_signals = pfo.build_combo_activation_outputs(run_id, "2026-06-05", "2026-05-29", "no_new_data")
    status = pd.DataFrame([spy_row, combo_row])
    signals = pd.DataFrame(
        [
            {
                "as_of_date": "2026-05-29",
                "strategy": "SPY_200d_trend_model",
                "role": "primary_watchlist_candidate",
                "symbol": "SPY",
                "close": float("nan"),
                "sma_200": float("nan"),
                "above_sma_200": "",
                "signal": "unavailable",
                "target_weight": float("nan"),
                "reason": "test row",
                "data_quality_flag": "no_new_data",
            },
            *combo_signals,
        ]
    )
    assumptions = pfo.build_assumptions("2026-06-05", "2026-05-29", "existing cache only", True, True)
    _run_dir, latest = pfo.write_outputs(run_id, status, pd.DataFrame(), signals, pd.DataFrame(), assumptions, pd.DataFrame())
    summary = (latest / "paper_forward_summary.md").read_text(encoding="utf-8")
    manifest = json.loads((latest / "paper_forward_manifest.json").read_text(encoding="utf-8"))
    assert "combo_SPY200d_GLD_50_50_v1" in summary
    assert "combo_replaces_spy200d: false" in summary
    assert "active_waiting_for_next_cached_trading_day" in summary
    assert manifest["combo_observation_status"] == "active_waiting_for_next_cached_trading_day"
    assert manifest["combo_paper_forward_active"] is False
    assert manifest["rule_hash_verified"] is True
    assert manifest["data_downloaded"] is False
    assert len([p for p in latest.iterdir() if p.is_file()]) <= 10


def test_activation_source_does_not_invoke_backtest_profit_or_download() -> None:
    source = Path("run_paper_forward_observation.py").read_text(encoding="utf-8")
    assert "run_profit_exploration.py" not in source
    assert "run_backtest.py" not in source
    assert "yfinance.download" not in source
