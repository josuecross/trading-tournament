from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = ROOT / "combination_lab" / "batch1_diagnostics_completion"
LATEST_DIR = ROOT / "evidence" / "combination_lab" / "batch1_diagnostics_completion" / "latest"
DIAGNOSTICS_ZIP = (
    ROOT
    / "evidence"
    / "combination_lab"
    / "batch1_diagnostics_completion"
    / "latest_batch1_diagnostics_completion_packet.zip"
)
ALLOWED_DECISIONS = {
    "diagnostics_support_candidate_exhaustive_review_for_combo_plus_managed_futures_80_20",
    "diagnostics_support_candidate_exhaustive_review_for_top2_plus_managed_futures_80_20",
    "diagnostics_support_short_history_watchlist_only",
    "diagnostics_incomplete_need_export_fields",
    "diagnostics_reject_candidate_exhaustive",
}
COMBINATION_IDS = {
    "combo_plus_top2_50_50_v1",
    "combo_plus_managed_futures_80_20_v1",
    "top2_plus_managed_futures_80_20_v1",
}


def load_registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def by_id(registry: dict) -> dict[str, dict]:
    return {row["id"]: row for row in registry["strategies"]}


def test_diagnostics_completion_folder_evidence_and_zip_exist() -> None:
    assert DIAGNOSTICS_DIR.exists()
    assert LATEST_DIR.exists()
    assert DIAGNOSTICS_ZIP.exists()
    assert len([path for path in LATEST_DIR.iterdir() if path.is_file()]) <= 10
    with zipfile.ZipFile(DIAGNOSTICS_ZIP) as zf:
        assert len(zf.namelist()) <= 10
        assert "TARGET_WINDOW_COMOVEMENT_AUDIT.md" in zf.namelist()
        assert "DIAGNOSTICS_COMPLETION_DECISION.md" in zf.namelist()


def test_required_audit_files_and_decision_exist() -> None:
    expected = {
        "README.md",
        "TARGET_WINDOW_COMOVEMENT_AUDIT.md",
        "COMPONENT_CONTRIBUTION_AUDIT.md",
        "COMMON_HISTORY_SENSITIVITY_AUDIT.md",
        "DRAWDOWN_COINCIDENCE_DETAIL_AUDIT.md",
        "DIAGNOSTICS_COMPLETION_DECISION.md",
        "batch1_diagnostics_completion_manifest.json",
    }
    assert expected.issubset({path.name for path in DIAGNOSTICS_DIR.iterdir() if path.is_file()})
    assert expected.issubset({path.name for path in LATEST_DIR.iterdir() if path.is_file()})
    decision_text = (DIAGNOSTICS_DIR / "DIAGNOSTICS_COMPLETION_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{decision}`" in decision_text for decision in ALLOWED_DECISIONS)


def test_manifest_confirms_no_forbidden_actions() -> None:
    manifest = json.loads((LATEST_DIR / "batch1_diagnostics_completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["diagnostics_completion_decision"] in ALLOWED_DECISIONS
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["candidate_exhaustive_review_recommended"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["target_window_comovement_status"] == "available"
    assert manifest["latest_folder_file_count"] <= 10


def test_diagnostics_detail_has_window_level_fields_for_exactly_batch1() -> None:
    detail = pd.read_csv(LATEST_DIR / "combination_diagnostics_detail.csv")
    assert set(detail["combination_id"]) == COMBINATION_IDS
    required_columns = {
        "window_start",
        "window_end",
        "target_300_hit",
        "target_400_hit",
        "target_600_hit",
        "combo_benchmark_target_300_hit",
        "combo_benchmark_target_400_hit",
        "top2_benchmark_target_300_hit",
        "top2_benchmark_target_400_hit",
        "incremental_target_300_vs_combo",
        "incremental_target_400_vs_combo",
        "component_primary_return_contribution_if_available",
        "component_secondary_return_contribution_if_available",
        "combo_drawdown_overlap_flags_if_available",
        "top2_drawdown_overlap_flags_if_available",
        "spy200d_drawdown_overlap_flags_if_available",
    }
    assert required_columns.issubset(set(detail.columns))
    for row_id in COMBINATION_IDS:
        assert not detail[detail["combination_id"].eq(row_id)].empty


def test_no_new_combination_was_added_to_specs() -> None:
    specs = yaml.safe_load((ROOT / "combination_lab" / "combination_batch1_specs.yaml").read_text(encoding="utf-8"))
    ids = {row["combination_id"] for row in specs["combinations"]}
    assert ids == COMBINATION_IDS
    assert len(specs["combinations"]) == 3
    assert specs["optimization_allowed"] is False
    assert specs["dynamic_weights_allowed"] is False


def test_registry_preserves_active_combo_spy_control_and_short_history_labels() -> None:
    registry = load_registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = by_id(registry)
    combo = rows["profit_combo_SPY200d_GLD_50_50_v1"]
    assert combo["status"] == "active_paper_demo_observation"
    assert combo["paper_forward_active"] is True
    spy = rows["SPY_200d_trend_model"]
    assert spy["rules_frozen"] is True
    assert "replaced" not in str(spy).lower()
    for row_id in {"combo_plus_managed_futures_80_20_v1", "top2_plus_managed_futures_80_20_v1"}:
        row = rows[row_id]
        assert row["status"] == "short_history_watchlist"
        assert row["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False


def test_advisor_upload_top_level_remains_capped_if_present() -> None:
    latest = ROOT / "evidence" / "advisor_upload" / "latest"
    if latest.exists():
        assert len([path for path in latest.iterdir() if path.is_file()]) <= 10


def test_source_boundaries_do_not_call_forbidden_runners_or_downloads() -> None:
    source_paths = [
        ROOT / "run_research_state_dashboard.py",
        ROOT / "run_advisor_audit_packet.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    assert "run_backtest.py" not in combined
    assert "run_paper_forward_observation.py" not in combined
    assert "candidate_exhaustive_run\": true" not in combined
    assert "yfinance.download" not in combined
    assert "real_money_recommendation: true" not in combined
