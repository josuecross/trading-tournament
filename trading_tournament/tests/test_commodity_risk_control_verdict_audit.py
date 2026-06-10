from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "commodity_lab" / "risk_control_batch1_verdict_audit"
LATEST_DIR = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_verdict_audit" / "latest"
AUDIT_ZIP = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_verdict_audit" / "latest_risk_control_batch1_verdict_audit_packet.zip"
ALLOWED_DECISIONS = {
    "candidate_exhaustive_review_required_for_combo_plus_commodity_80_20",
    "candidate_exhaustive_review_required_for_base_commodity",
    "candidate_exhaustive_review_required_for_half_bil",
    "more_diagnostics_required_before_candidate_exhaustive_decision",
    "no_commodity_candidate_deserves_candidate_exhaustive",
    "reject_commodity_family_for_now",
}


def _registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def test_verdict_audit_folder_and_evidence_mirror_exist() -> None:
    assert AUDIT_DIR.exists()
    assert LATEST_DIR.exists()
    assert AUDIT_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(AUDIT_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "VERDICT_AUDIT.md" in zf.namelist()
        assert "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md" in zf.namelist()


def test_required_audit_files_and_decision_exist() -> None:
    expected = {
        "README.md",
        "VERDICT_AUDIT.md",
        "SCORE_AND_RANKING_AUDIT.md",
        "TARGET_WINDOW_COMOVEMENT_AUDIT.md",
        "COMPONENT_CONTRIBUTION_AUDIT.md",
        "DRAWDOWN_AND_RISK_BUDGET_AUDIT.md",
        "DUPLICATE_AND_DIVERSIFICATION_AUDIT.md",
        "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md",
        "risk_control_batch1_verdict_audit_manifest.json",
    }
    assert {path.name for path in AUDIT_DIR.iterdir() if path.is_file()} == expected
    assert {path.name for path in LATEST_DIR.iterdir() if path.is_file()} == expected
    decision = (AUDIT_DIR / "CANDIDATE_EXHAUSTIVE_REVIEW_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{item}`" in decision for item in ALLOWED_DECISIONS)


def test_manifest_confirms_research_only_boundaries() -> None:
    manifest = json.loads((LATEST_DIR / "risk_control_batch1_verdict_audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_decision"] in ALLOWED_DECISIONS
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["diagnostics_only_profit_exploration_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["backtest_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["new_commodity_variants_added"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["direct_futures_contract_logic"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_audited_verdicts_match_expected_skeptical_labels() -> None:
    manifest = json.loads((LATEST_DIR / "risk_control_batch1_verdict_audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["audited_verdicts"]["commodity_basket_tsmom_top2_v1"] == "research_sample_candidate_risk_budget_breach"
    assert manifest["audited_verdicts"]["commodity_basket_tsmom_top2_200d_filter_v1"] == "filter_ineffective_or_bug_review"
    assert manifest["audited_verdicts"]["commodity_basket_tsmom_top2_half_bil_v1"] == "too_slow_defensive_watchlist"
    assert manifest["audited_verdicts"]["combo_plus_commodity_basket_80_20_v1"] == "candidate_diagnostics_review_required"
    assert manifest["target_window_comovement_status"] == "unavailable_missing_window_ids"
    assert manifest["component_contribution_status"] == "partial_unavailable_exact_path_contribution"


def test_strategy_lab_statuses_reflect_audit_without_paper_forward_change() -> None:
    registry = _registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = {row["id"]: row for row in registry["strategies"]}
    assert rows["commodity_basket_tsmom_top2_200d_filter_v1"]["status"] == "filter_ineffective_or_bug_review"
    assert rows["commodity_basket_tsmom_top2_half_bil_v1"]["status"] == "too_slow_defensive_watchlist"
    assert rows["combo_plus_commodity_basket_80_20_v1"]["status"] == "watchlist"
    for row_id in {
        "commodity_basket_tsmom_top2_200d_filter_v1",
        "commodity_basket_tsmom_top2_half_bil_v1",
        "combo_plus_commodity_basket_80_20_v1",
    }:
        row = rows[row_id]
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
    assert rows["profit_combo_SPY200d_GLD_50_50_v1"]["paper_forward_active"] is True
    assert rows["SPY_200d_trend_model"]["rules_frozen"] is True


def test_no_forbidden_artifacts_or_claims() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in AUDIT_DIR.iterdir() if path.is_file())
    assert "candidate_exhaustive_run\": true" not in combined
    assert "data_downloaded\": true" not in combined
    assert "real_money_recommendation\": true" not in combined
    assert "broker_integration\": true" not in combined
    assert "live_orders\": true" not in combined
    assert "order_placement\": true" not in combined
    specs = yaml.safe_load((ROOT / "profit_lab" / "profit_experiment_specs.yaml").read_text(encoding="utf-8"))
    risk_rows = [row for row in specs["experiments"] if row.get("experiment_type") == "commodity_risk_control_exploratory"]
    assert len(risk_rows) == 3
    for row in risk_rows:
        assert row["uses_futures_contracts"] is False
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
