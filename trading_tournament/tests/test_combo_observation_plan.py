from __future__ import annotations

import json
import zipfile
from pathlib import Path

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = ROOT / "paper_forward_observation_plans" / "combo_SPY200d_GLD_50_50_v1"
LATEST_DIR = ROOT / "evidence" / "paper_forward_observation_plans" / "combo_SPY200d_GLD_50_50_v1" / "latest"
PLAN_ZIP = ROOT / "evidence" / "paper_forward_observation_plans" / "combo_SPY200d_GLD_50_50_v1" / "latest_observation_plan_packet.zip"
ALLOWED_DECISIONS = {
    "approve_future_paper_forward_observation_activation_prompt",
    "watchlist_more_evidence_before_activation_plan",
    "reject_observation_plan_for_now",
}


def test_combo_observation_plan_packet_exists_and_is_compact() -> None:
    assert PLAN_DIR.exists()
    assert LATEST_DIR.exists()
    files = [path for path in LATEST_DIR.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert PLAN_ZIP.exists()
    with zipfile.ZipFile(PLAN_ZIP) as zf:
        names = set(zf.namelist())
    assert "OBSERVATION_PLAN_DECISION.md" in names
    assert "RULE_FREEZE_CONFIRMATION.md" in names
    assert "CHECKPOINT_POLICY.md" in names


def test_observation_decision_is_allowed_and_review_only() -> None:
    manifest = json.loads((LATEST_DIR / "observation_plan_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["observation_activated"] is False
    assert manifest["paper_forward_active_set_true"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["real_money_recommendation"] is False


def test_combo_registry_records_later_activation_blocker_and_spy200d_remains() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["status"] in {"active_waiting_for_next_cached_trading_day", "active_paper_demo_observation"}
    if combo["status"] == "active_paper_demo_observation":
        assert combo["allowed_next_action"] == "run_monthly_paper_forward_checkpoint"
        assert combo["paper_forward_active"] is True
    else:
        assert combo["allowed_next_action"] == "controlled_cache_update_or_next_cached_observation_date"
        assert combo["paper_forward_active"] is False
    assert combo["paper_forward_allowed_by_risk_framework"] is combo["paper_forward_active"]
    assert combo["real_money_recommendation"] is False
    assert "activate_without_observation_prompt" in combo["forbidden_next_actions"]
    assert "replace_spy200d_without_governance" in combo["forbidden_next_actions"]
    assert "change_strategy_rules" in combo["forbidden_next_actions"]
    assert spy["status"] == "active_observation"
    assert spy["paper_forward_active"] is True


def test_rule_freeze_and_failure_policy_files_are_present() -> None:
    freeze = (LATEST_DIR / "RULE_FREEZE_CONFIRMATION.md").read_text(encoding="utf-8")
    failure = (LATEST_DIR / "FAILURE_AND_EXIT_CRITERIA.md").read_text(encoding="utf-8")
    scope = (LATEST_DIR / "OBSERVATION_SCOPE.md").read_text(encoding="utf-8")
    assert "no parameters are changed" in freeze
    assert "No paper-forward activation occurs" in freeze
    assert "rule hash mismatch" in failure
    assert "simulated paper/demo" in failure
    assert "parallel observation candidate, not replacement" in scope


def test_no_strategy_backtest_profit_or_data_script_is_triggered_by_plan() -> None:
    source = (ROOT / "run_profit_exploration.py").read_text(encoding="utf-8")
    assert "combo_SPY200d_GLD_50_50_v1_observation_plan_v1" not in source
    readme = (LATEST_DIR / "README.md").read_text(encoding="utf-8")
    assert "does not run a backtest" in readme
    assert "does not activate" in readme
    manifest = json.loads((LATEST_DIR / "observation_plan_manifest.json").read_text(encoding="utf-8"))
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False


def test_advisor_upload_remains_compact_and_references_observation_plan(tmp_path: Path) -> None:
    result = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        no_nested_zips=True,
    )
    latest = result["latest_dir"]
    assert result["manifest"]["top_level_file_count"] <= 10
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        review_index = zf.read("PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "combo_paper_forward_observation_plan_review" in review_index
    assert "approve_future_paper_forward_observation_activation_prompt" in review_index
    assert "Combo paper-forward observation plan packet:" in executive
