from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1"
LATEST_OBS_DIR = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest"
OBS_ZIP = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest_observation_activation_packet.zip"
PAPER_FORWARD_LATEST = ROOT / "evidence" / "paper_forward_runs" / "latest"
ADVISOR_LATEST = ROOT / "evidence" / "advisor_upload" / "latest"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_observation_consistency_packet_exists_and_is_compact() -> None:
    assert (OBS_DIR / "OBSERVATION_CONSISTENCY_AUDIT.md").exists()
    assert (OBS_DIR / "CHECKPOINT_READINESS.md").exists()
    assert (LATEST_OBS_DIR / "OBSERVATION_CONSISTENCY_AUDIT.md").exists()
    assert (LATEST_OBS_DIR / "CHECKPOINT_READINESS.md").exists()
    assert len([p for p in LATEST_OBS_DIR.iterdir() if p.is_file()]) <= 10
    with zipfile.ZipFile(OBS_ZIP) as zf:
        names = set(zf.namelist())
    assert "OBSERVATION_CONSISTENCY_AUDIT.md" in names
    assert "CHECKPOINT_READINESS.md" in names


def test_consistency_decision_and_current_state_are_authoritative() -> None:
    audit = read_text(OBS_DIR / "OBSERVATION_CONSISTENCY_AUDIT.md")
    allowed = {
        "observation_consistency_passed",
        "observation_consistency_passed_with_minor_notes",
        "observation_consistency_failed_needs_fix",
    }
    decisions = {decision for decision in allowed if f"Decision: {decision}" in audit}
    assert decisions == {"observation_consistency_passed"}
    assert "combo paper_forward_active: true" in audit
    assert "corrected combo current equity: $2,998.50" in audit
    assert "checkpoint_status: inconclusive_too_early" in audit
    assert "SPY_200d replaced: false" in audit


def test_no_stale_cache_date_blocker_text_remains() -> None:
    files = [
        OBS_DIR / "RULE_HASH_RECORD.md",
        OBS_DIR / "ACTIVATION_RECORD.md",
        OBS_DIR / "observation_activation_manifest.json",
        OBS_DIR / "observation_config.yaml",
        OBS_DIR / "START_DATE_ACCOUNTING_AUDIT.md",
        OBS_DIR / "OBSERVATION_CONSISTENCY_AUDIT.md",
        OBS_DIR / "CHECKPOINT_READINESS.md",
        PAPER_FORWARD_LATEST / "paper_forward_summary.md",
        PAPER_FORWARD_LATEST / "warnings_and_limitations.md",
    ]
    combined = "\n".join(read_text(path) for path in files)
    stale_phrases = [
        "Do not activate the combo as active paper/demo yet",
        "does not support the requested activation date of `2026-06-05`",
        "cache only supports 2026-05-29",
        "latest_common_cached_date: `2026-05-29`",
        "active_waiting_for_next_cached_trading_day",
        "activation_blocked_rule_hash_missing",
    ]
    for phrase in stale_phrases:
        assert phrase not in combined


def test_combo_active_status_and_checkpoint_are_consistent() -> None:
    config = yaml.safe_load(read_text(OBS_DIR / "observation_config.yaml"))
    manifest = json.loads(read_text(OBS_DIR / "observation_activation_manifest.json"))
    status = pd.read_csv(PAPER_FORWARD_LATEST / "paper_forward_status.csv")
    combo = status[status["strategy"].eq("combo_SPY200d_GLD_50_50_v1")].iloc[0]
    assert config["status"] == "active_paper_demo_observation"
    assert manifest["activation_status"] == "active_paper_demo_observation"
    assert manifest["paper_forward_active"] is True
    assert manifest["observation_consistency_audit_decision"] == "observation_consistency_passed"
    assert manifest["current_checkpoint_status"] == "inconclusive_too_early"
    assert combo["status"] == "active_paper_demo_observation"
    assert round(float(combo["current_equity"]), 2) == 2998.50
    assert combo["decision_status"] == "inconclusive_too_early"


def test_spy200d_remains_frozen_control_and_not_replaced() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["status"] == "active_paper_demo_observation"
    assert combo["paper_forward_active"] is True
    assert combo["real_money_recommendation"] is False
    assert combo["broker_integration"] is False
    assert combo["live_orders"] is False
    assert spy["paper_forward_active"] is True
    assert spy["rules_frozen"] is True
    assert "replaced_by_combo" not in spy
    assert "replace_spy200d_without_governance" in combo["forbidden_next_actions"]


def test_start_date_accounting_and_checkpoint_readiness_are_recorded() -> None:
    accounting = read_text(OBS_DIR / "START_DATE_ACCOUNTING_AUDIT.md")
    readiness = read_text(OBS_DIR / "CHECKPOINT_READINESS.md")
    assert "Decision: start_date_accounting_bug_fixed" in accounting
    assert "No pre-start price return is applied on the first active row" in accounting
    assert "Current checkpoint_status: inconclusive_too_early" in readiness
    assert "No conclusion is allowed before 30 trading days" in readiness
    assert "No strategy changes before checkpoint" in readiness


def test_no_forbidden_execution_or_real_money_flags() -> None:
    registry = read_text(DEFAULT_REGISTRY)
    manifest = json.loads(read_text(OBS_DIR / "observation_activation_manifest.json"))
    assert manifest["strategy_rules_changed"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["data_downloaded_during_consistency_audit"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert "real_money_recommendation: true" not in registry
    assert "broker_integration: true" not in registry
    assert "live_orders: true" not in registry


def test_latest_packets_and_strategy_lab_validate() -> None:
    assert len([p for p in PAPER_FORWARD_LATEST.iterdir() if p.is_file()]) <= 10
    if ADVISOR_LATEST.exists():
        assert len([p for p in ADVISOR_LATEST.iterdir() if p.is_file()]) <= 10
    validation = validate_registry_data(load_registry(DEFAULT_REGISTRY))
    assert validation["passed"] is True, validation
