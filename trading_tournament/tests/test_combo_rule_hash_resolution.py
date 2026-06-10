from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "rule_hash_reviews" / "combo_SPY200d_GLD_50_50_v1"
LATEST_DIR = ROOT / "evidence" / "rule_hash_reviews" / "combo_SPY200d_GLD_50_50_v1" / "latest"
REVIEW_ZIP = ROOT / "evidence" / "rule_hash_reviews" / "combo_SPY200d_GLD_50_50_v1" / "latest_rule_hash_review_packet.zip"
OBS_DIR = ROOT / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1"
PAPER_LATEST = ROOT / "evidence" / "paper_forward_runs" / "latest"

ALLOWED_DECISIONS = {
    "historical_rule_hash_verified",
    "source_spec_reconstructed_hash_verified",
    "rule_hash_unresolvable",
    "rule_hash_mismatch",
    "rule_hash_missing_still_blocked",
}


def test_rule_hash_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_DIR.exists()
    assert LATEST_DIR.exists()
    files = [path for path in LATEST_DIR.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert REVIEW_ZIP.exists()
    with zipfile.ZipFile(REVIEW_ZIP) as zf:
        names = set(zf.namelist())
    assert "CANONICAL_RULE_SPEC.json" in names
    assert "RULE_HASH_DECISION.md" in names
    assert "rule_hash_review_manifest.json" in names


def test_canonical_rule_spec_and_decision_are_valid() -> None:
    spec = json.loads((REVIEW_DIR / "CANONICAL_RULE_SPEC.json").read_text(encoding="utf-8"))
    manifest = json.loads((REVIEW_DIR / "rule_hash_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert spec["strategy_id"] == "combo_SPY200d_GLD_50_50_v1"
    assert spec["rule_schema_version"] == "rule_hash_schema_v1"
    assert spec["strategy_family"] == "fixed_combo"
    assert spec["max_gross_exposure"] == 1.0
    assert spec["uses_leverage"] is False
    assert spec["uses_shorting"] is False
    assert spec["uses_margin"] is False
    assert spec["broker_integration"] is False
    assert spec["live_orders"] is False
    assert spec["real_money_recommendation"] is False
    components = {component["component_id"]: component["weight"] for component in spec["components"]}
    assert components == {"SPY_200d_trend_model": 0.5, "GLD_buy_hold": 0.5}


def test_verified_hash_updates_activation_packet_without_activating() -> None:
    manifest = json.loads((REVIEW_DIR / "rule_hash_review_manifest.json").read_text(encoding="utf-8"))
    config = yaml.safe_load((OBS_DIR / "observation_config.yaml").read_text(encoding="utf-8"))
    activation = json.loads((OBS_DIR / "observation_activation_manifest.json").read_text(encoding="utf-8"))
    if manifest["decision"] in {"historical_rule_hash_verified", "source_spec_reconstructed_hash_verified"}:
        assert manifest["canonical_rule_hash"]
        assert config["canonical_rule_hash"] == manifest["canonical_rule_hash"]
        assert activation["canonical_rule_hash"] == manifest["canonical_rule_hash"]
        assert config["rule_hash_verified"] is True
        assert activation["rule_hash_verified"] is True
    else:
        assert config["paper_forward_active"] is False
    assert config["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    assert activation["activation_status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    assert activation["paper_forward_active"] is (activation["activation_status"] == "active_paper_demo_observation")
    assert activation["spy200d_replaced"] is False
    assert activation["data_downloaded"] in {False, True}
    assert activation["backtest_run"] is False
    assert activation["profit_exploration_run"] is False


def test_registry_reflects_hash_resolution_and_preserves_spy_control() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    assert combo["paper_forward_active"] is (combo["status"] == "active_paper_demo_observation")
    assert combo["canonical_rule_hash"]
    assert combo["hash_source_type"] == "source_spec_reconstructed_hash"
    assert combo["allowed_next_action"] in {"controlled_cache_update_or_next_cached_observation_date", "run_monthly_paper_forward_checkpoint"}
    assert "fabricate_missing_data" in combo["forbidden_next_actions"]
    assert combo["real_money_recommendation"] is False
    assert spy["paper_forward_active"] is True
    assert spy["rules_frozen"] is True


def test_no_strategy_backtest_download_or_broker_behavior_was_added() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in REVIEW_DIR.iterdir() if path.is_file())
    assert "No strategy rules are changed" in text
    manifest = json.loads((REVIEW_DIR / "rule_hash_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_rules_changed"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    if PAPER_LATEST.exists():
        assert len([path for path in PAPER_LATEST.iterdir() if path.is_file()]) <= 10
