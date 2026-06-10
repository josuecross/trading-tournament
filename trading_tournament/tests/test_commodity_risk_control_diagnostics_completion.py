from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
COMPLETION_DIR = ROOT / "commodity_lab" / "risk_control_batch1_diagnostics_completion"
LATEST_DIR = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_diagnostics_completion" / "latest"
ZIP_PATH = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1_diagnostics_completion" / "latest_risk_control_batch1_diagnostics_completion_packet.zip"
DETAIL = LATEST_DIR / "commodity_risk_control_diagnostics_detail.csv"
ALLOWED_DECISIONS = {
    "diagnostics_support_candidate_exhaustive_review_for_combo_plus_commodity_80_20",
    "diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20",
    "diagnostics_incomplete_need_more_export_fields",
    "diagnostics_reject_commodity_risk_control_rows",
    "diagnostics_keep_200d_filter_under_bug_review",
}


def _registry() -> dict:
    return yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))


def test_diagnostics_completion_folder_mirror_and_zip_exist() -> None:
    assert COMPLETION_DIR.exists()
    assert LATEST_DIR.exists()
    assert ZIP_PATH.exists()
    latest_files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(latest_files) <= 10
    for required in {
        "TARGET_WINDOW_COMOVEMENT_COMPLETION.md",
        "COMPONENT_CONTRIBUTION_COMPLETION.md",
        "DRAWDOWN_OVERLAP_DETAIL_COMPLETION.md",
        "FILTER_EFFECTIVENESS_AUDIT.md",
        "COMMODITY_80_20_INCREMENTAL_VALUE_AUDIT.md",
        "DIAGNOSTICS_COMPLETION_DECISION.md",
        "risk_control_batch1_diagnostics_completion_manifest.json",
    }:
        assert required in latest_files
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert len(zf.namelist()) <= 10
        assert set(zf.namelist()) == latest_files


def test_decision_and_manifest_boundaries() -> None:
    decision = (COMPLETION_DIR / "DIAGNOSTICS_COMPLETION_DECISION.md").read_text(encoding="utf-8")
    assert any(f"Decision: `{item}`" in decision for item in ALLOWED_DECISIONS)
    manifest = json.loads((LATEST_DIR / "risk_control_batch1_diagnostics_completion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20"
    assert manifest["diagnostics_only_profit_exploration_run"] is True
    assert manifest["candidate_exhaustive_review_recommended"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["new_commodity_variants_added"] is False
    assert manifest["new_symbols_added"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["direct_futures_contract_logic"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["target_window_comovement_status"] == "available"
    assert manifest["drawdown_overlap_status"] == "available"
    assert manifest["latest_folder_file_count"] <= 10


def test_diagnostics_detail_exports_required_fields() -> None:
    assert DETAIL.exists()
    detail = pd.read_csv(DETAIL)
    assert len(detail) == 471
    required_columns = {
        "experiment_id",
        "horizon",
        "window_start",
        "window_end",
        "target_300_hit",
        "target_400_hit",
        "target_600_hit",
        "target_900_hit",
        "target_1200_hit",
        "stop_hit",
        "final_equity",
        "worst_drawdown",
        "base_commodity_target_300_hit",
        "base_commodity_target_400_hit",
        "combo_target_300_hit",
        "combo_target_400_hit",
        "top2_target_300_hit",
        "top2_target_400_hit",
        "spy200d_target_300_hit",
        "spy200d_target_400_hit",
        "gld_target_300_hit",
        "gld_target_400_hit",
        "incremental_300_vs_combo",
        "incremental_400_vs_combo",
        "component_primary_contribution_if_available",
        "component_secondary_contribution_if_available",
        "worst_drawdown_start_if_available",
        "worst_drawdown_end_if_available",
        "drawdown_overlap_vs_combo_if_available",
        "drawdown_overlap_vs_top2_if_available",
        "drawdown_overlap_vs_spy200d_if_available",
        "drawdown_overlap_vs_gld_if_available",
    }
    assert required_columns.issubset(set(detail.columns))
    assert set(detail["experiment_id"].astype(str)) == {
        "commodity_basket_tsmom_top2_200d_filter_v1",
        "commodity_basket_tsmom_top2_half_bil_v1",
        "combo_plus_commodity_basket_80_20_v1",
    }
    combo = detail[detail["experiment_id"].eq("combo_plus_commodity_basket_80_20_v1")]
    assert int(combo[combo["horizon"].eq(180)]["incremental_300_vs_combo"].sum()) == 3
    assert int(combo[combo["horizon"].eq(180)]["incremental_400_vs_combo"].sum()) == 3


def test_no_new_variants_or_forbidden_mechanics() -> None:
    specs = yaml.safe_load((ROOT / "profit_lab" / "profit_experiment_specs.yaml").read_text(encoding="utf-8"))
    risk_rows = [row for row in specs["experiments"] if row.get("experiment_type") == "commodity_risk_control_exploratory"]
    assert len(risk_rows) == 3
    allowed_symbols = {"DBC", "PDBC", "COMT", "GSG", "USCI", "BIL", "SPY", "GLD"}
    for row in risk_rows:
        assert set(row["required_symbols"]).issubset(allowed_symbols)
        assert row["uses_futures_contracts"] is False
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert "tune_parameters" in row["forbidden_next_actions"]


def test_strategy_lab_and_active_controls_remain_unchanged() -> None:
    registry = _registry()
    validation = validate_registry_data(registry)
    assert validation["passed"] is True, validation
    rows = {row["id"]: row for row in registry["strategies"]}
    assert rows["combo_plus_commodity_basket_80_20_v1"]["status"] == "watchlist"
    assert rows["commodity_basket_tsmom_top2_200d_filter_v1"]["status"] == "filter_ineffective_or_bug_review"
    assert rows["commodity_basket_tsmom_top2_half_bil_v1"]["status"] == "too_slow_defensive_watchlist"
    assert rows["profit_combo_SPY200d_GLD_50_50_v1"]["paper_forward_active"] is True
    assert rows["SPY_200d_trend_model"]["rules_frozen"] is True
    for row_id in [
        "combo_plus_commodity_basket_80_20_v1",
        "commodity_basket_tsmom_top2_200d_filter_v1",
        "commodity_basket_tsmom_top2_half_bil_v1",
    ]:
        assert rows[row_id]["paper_forward_active"] is False
        assert rows[row_id]["real_money_recommendation"] is False


def test_advisor_upload_remains_compact(tmp_path: Path) -> None:
    result = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )
    top_files = [path.name for path in result["latest_dir"].iterdir() if path.is_file()]
    assert len(top_files) <= 10

