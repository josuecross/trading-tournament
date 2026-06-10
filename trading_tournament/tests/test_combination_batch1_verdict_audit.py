from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "combination_lab" / "batch1_verdict_audit"
LATEST_DIR = ROOT / "evidence" / "combination_lab" / "batch1_verdict_audit" / "latest"
AUDIT_ZIP = ROOT / "evidence" / "combination_lab" / "batch1_verdict_audit" / "latest_batch1_verdict_audit_packet.zip"
ALLOWED_DECISIONS = {
    "no_combination_deserves_candidate_exhaustive",
    "candidate_exhaustive_review_required_for_combo_plus_managed_futures_80_20",
    "candidate_exhaustive_review_required_for_top2_plus_managed_futures_80_20",
    "candidate_exhaustive_review_required_for_combo_plus_top2_50_50",
    "more_diagnostics_required_before_candidate_exhaustive_decision",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_verdict_audit_folder_and_evidence_exist() -> None:
    assert AUDIT_DIR.exists()
    assert LATEST_DIR.exists()
    assert AUDIT_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(AUDIT_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "VERDICT_AUDIT.md" in zf.namelist()
        assert "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md" in zf.namelist()


def test_verdict_audit_required_files_and_decision() -> None:
    expected = {
        "README.md",
        "VERDICT_AUDIT.md",
        "SCORE_AND_RANKING_AUDIT.md",
        "TARGET_VS_DRAWDOWN_AUDIT.md",
        "SHORT_HISTORY_AND_MF_LABEL_AUDIT.md",
        "CORRELATION_DIAGNOSTICS_AUDIT.md",
        "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md",
        "batch1_verdict_audit_manifest.json",
    }
    assert {path.name for path in AUDIT_DIR.iterdir() if path.is_file()} == expected
    assert {path.name for path in LATEST_DIR.iterdir() if path.is_file()} == expected
    decision_text = (AUDIT_DIR / "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{decision}`" in decision_text for decision in ALLOWED_DECISIONS)


def test_manifest_confirms_no_forbidden_actions() -> None:
    manifest = json.loads((LATEST_DIR / "batch1_verdict_audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_decision"] in ALLOWED_DECISIONS
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["backtest_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_audited_verdicts_and_short_history_labels_are_preserved() -> None:
    manifest = json.loads((LATEST_DIR / "batch1_verdict_audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["audited_verdicts"]["combo_plus_top2_50_50_v1"] == "duplicate_or_near_duplicate"
    assert manifest["audited_verdicts"]["combo_plus_managed_futures_80_20_v1"] == "short_history_watchlist"
    assert manifest["audited_verdicts"]["top2_plus_managed_futures_80_20_v1"] == "short_history_watchlist"
    short_history = (AUDIT_DIR / "SHORT_HISTORY_AND_MF_LABEL_AUDIT.md").read_text(encoding="utf-8")
    assert "fund_wrapper_proxy_short_history_limited_inception_research_sample_only" in short_history
    assert "not direct futures strategy evidence" in short_history
    assert "no paper-forward approval from this audit" in short_history


def test_strategy_lab_statuses_reflect_audit_without_paper_forward_changes() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    assert rows["combo_plus_top2_50_50_v1"]["status"] == "duplicate_or_near_duplicate"
    for row_id in {"combo_plus_managed_futures_80_20_v1", "top2_plus_managed_futures_80_20_v1"}:
        row = rows[row_id]
        assert row["status"] == "short_history_watchlist"
        assert row["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
    combo = rows["profit_combo_SPY200d_GLD_50_50_v1"]
    assert combo["paper_forward_active"] is True
    assert combo["status"] == "active_paper_demo_observation"
    spy = rows["SPY_200d_trend_model"]
    assert spy["rules_frozen"] is True
    assert "replaced" not in str(spy).lower()


def test_audit_source_does_not_call_forbidden_runners_or_downloads() -> None:
    source_paths = [
        ROOT / "run_strategy_lab.py",
        ROOT / "run_research_state_dashboard.py",
        ROOT / "run_advisor_audit_packet.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    assert "run_profit_exploration.py" not in (AUDIT_DIR / "README.md").read_text(encoding="utf-8")
    assert "candidate_exhaustive_run\": true" not in combined
    assert "yfinance.download" not in combined
    assert "run_backtest.py" not in combined
    assert "run_paper_forward_observation.py" not in combined

