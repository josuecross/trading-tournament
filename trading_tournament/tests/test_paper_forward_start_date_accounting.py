from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_paper_forward_observation as pfo
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1"
LATEST_OBS_DIR = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest"
OBS_ZIP = ROOT / "evidence" / "paper_forward_observations" / "combo_SPY200d_GLD_50_50_v1" / "latest_observation_activation_packet.zip"
PAPER_FORWARD_LATEST = ROOT / "evidence" / "paper_forward_runs" / "latest"
AUDIT_FILE = OBS_DIR / "START_DATE_ACCOUNTING_AUDIT.md"


def test_start_date_accounting_audit_exists_and_is_mirrored() -> None:
    assert AUDIT_FILE.exists()
    assert (LATEST_OBS_DIR / "START_DATE_ACCOUNTING_AUDIT.md").exists()
    assert len([p for p in LATEST_OBS_DIR.iterdir() if p.is_file()]) <= 10
    with zipfile.ZipFile(OBS_ZIP) as zf:
        assert "START_DATE_ACCOUNTING_AUDIT.md" in set(zf.namelist())


def test_start_date_accounting_decision_is_allowed_and_documents_bug_fix() -> None:
    text = AUDIT_FILE.read_text(encoding="utf-8")
    allowed = {
        "start_date_accounting_valid",
        "start_date_accounting_valid_but_needs_clearer_label",
        "start_date_accounting_bug_fixed",
        "start_date_accounting_blocked_needs_followup",
    }
    decisions = {decision for decision in allowed if f"Decision: {decision}" in text}
    assert decisions == {"start_date_accounting_bug_fixed"}
    assert "$2,904.97" in text
    assert "No. The $2,904.97 value" in text
    assert "pre-start return" in text
    assert "Strategy rules changed: false" in text
    assert "Backtest run: false" in text
    assert "Profit Exploration run: false" in text
    assert "Data downloaded: false" in text


def test_combo_first_observation_row_excludes_pre_start_sleeve_returns() -> None:
    dates = pd.bdate_range("2025-01-01", periods=260)
    full_prices = pd.DataFrame(
        {
            "SPY": [100.0 + i * 0.2 for i in range(260)],
            "GLD": [200.0 + i * 0.3 for i in range(260)],
            "BIL": [100.0 + i * 0.01 for i in range(260)],
        },
        index=dates,
    )
    observation_prices = full_prices.iloc[[-1]]
    curve, weights, _rebalances = pfo.combo_curve_from_sleeves(full_prices, observation_prices)
    assert len(curve) == 1
    assert round(float(curve.iloc[0]["equity"]), 2) == 2998.50
    assert not weights.empty
    assert round(float(weights.iloc[0].sum()), 4) <= 1.0


def test_latest_paper_forward_equity_uses_corrected_start_date_accounting() -> None:
    status = pd.read_csv(PAPER_FORWARD_LATEST / "paper_forward_status.csv")
    combo = status[status["strategy"].eq("combo_SPY200d_GLD_50_50_v1")].iloc[0]
    spy = status[status["strategy"].eq("SPY_200d_trend_model")].iloc[0]
    assert combo["status"] == "active_paper_demo_observation"
    assert round(float(combo["current_equity"]), 2) == 2998.50
    assert round(float(spy["current_equity"]), 2) == 2998.50
    assert round(float(combo["current_equity"]), 2) != 2904.97
    assert combo["decision_status"] == "inconclusive_too_early"


def test_summary_and_warnings_document_start_date_convention() -> None:
    summary = (PAPER_FORWARD_LATEST / "paper_forward_summary.md").read_text(encoding="utf-8")
    warnings = (PAPER_FORWARD_LATEST / "warnings_and_limitations.md").read_text(encoding="utf-8")
    assert "start_date_accounting: first observation row excludes pre-start returns" in summary
    assert "Start-date accounting excludes pre-start returns" in warnings
    assert "combo_replaces_spy200d: false" in summary


def test_combo_remains_active_only_after_valid_accounting_and_spy_not_replaced() -> None:
    config = yaml.safe_load((OBS_DIR / "observation_config.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((OBS_DIR / "observation_activation_manifest.json").read_text(encoding="utf-8"))
    data = load_registry(DEFAULT_REGISTRY)
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert config["status"] == "active_paper_demo_observation"
    assert manifest["start_date_accounting_audit_decision"] == "start_date_accounting_bug_fixed"
    assert manifest["data_downloaded_during_start_date_accounting_audit"] is False
    assert combo["paper_forward_active"] is True
    assert combo["status"] == "active_paper_demo_observation"
    assert combo["real_money_recommendation"] is False
    assert combo["broker_integration"] is False
    assert combo["live_orders"] is False
    assert spy["paper_forward_active"] is True
    assert spy["rules_frozen"] is True
    assert "replaced_by_combo" not in spy


def test_no_forbidden_execution_or_live_behavior_was_added() -> None:
    source = (ROOT / "run_paper_forward_observation.py").read_text(encoding="utf-8")
    assert "run_profit_exploration.py" not in source
    assert "run_backtest.py" not in source
    assert "yfinance.download" not in source
    registry = DEFAULT_REGISTRY.read_text(encoding="utf-8")
    assert "real_money_recommendation: true" not in registry
    assert "broker_integration: true" not in registry
    assert "live_orders: true" not in registry


def test_paper_forward_latest_and_advisor_constraints() -> None:
    assert len([p for p in PAPER_FORWARD_LATEST.iterdir() if p.is_file()]) <= 10
    advisor_latest = ROOT / "advisor_audit" / "latest"
    if advisor_latest.exists():
        assert len([p for p in advisor_latest.iterdir() if p.is_file()]) <= 10
    validation = validate_registry_data(load_registry(DEFAULT_REGISTRY))
    assert validation["passed"] is True, validation
