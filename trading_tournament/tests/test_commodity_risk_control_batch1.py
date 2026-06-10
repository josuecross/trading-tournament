from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_profit_exploration as profit


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "commodity_lab" / "risk_control_batch1"
LATEST_DIR = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest"
ZIP_PATH = ROOT / "evidence" / "commodity_lab" / "risk_control_batch1" / "latest_risk_control_batch1_packet.zip"
PROFIT_LATEST = ROOT / "evidence" / "profit_exploration" / "latest"
RISK_IDS = {
    "commodity_basket_tsmom_top2_200d_filter_v1",
    "commodity_basket_tsmom_top2_half_bil_v1",
    "combo_plus_commodity_basket_80_20_v1",
}
COMMODITY_WRAPPERS = {"DBC", "PDBC", "COMT", "GSG", "USCI"}


def _specs_by_id() -> dict[str, dict]:
    data = yaml.safe_load((ROOT / "profit_lab" / "profit_experiment_specs.yaml").read_text(encoding="utf-8"))
    return {row["experiment_id"]: row for row in data["experiments"]}


def test_batch_folder_specs_and_latest_packet_exist() -> None:
    assert BATCH_DIR.exists()
    assert (BATCH_DIR / "RISK_CONTROL_BATCH1_SPECS.yaml").exists()
    assert LATEST_DIR.exists()
    assert ZIP_PATH.exists()
    files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    assert len(files) <= 10
    assert files == {
        "README_FOR_ADVISOR.md",
        "risk_control_batch1_summary.md",
        "risk_control_batch1_results.csv",
        "risk_control_batch1_rankings.csv",
        "risk_control_batch1_risk_summary.csv",
        "risk_control_batch1_diagnostics.csv",
        "risk_control_batch1_status.csv",
        "warnings_and_limitations.md",
        "risk_control_batch1_manifest.json",
    }
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == files


def test_exactly_three_risk_control_candidates_are_declared() -> None:
    specs = _specs_by_id()
    declared = {
        row_id
        for row_id, row in specs.items()
        if row.get("experiment_type") == "commodity_risk_control_exploratory"
    }
    assert declared == RISK_IDS
    batch_specs = yaml.safe_load((BATCH_DIR / "RISK_CONTROL_BATCH1_SPECS.yaml").read_text(encoding="utf-8"))
    assert {row["experiment_id"] for row in batch_specs["candidates"]} == RISK_IDS
    assert len(batch_specs["candidates"]) == 3


def test_risk_control_specs_use_fixed_rules_and_no_forbidden_mechanics() -> None:
    specs = _specs_by_id()
    allowed_symbols = COMMODITY_WRAPPERS | {"BIL", "SPY", "GLD"}
    for row_id in RISK_IDS:
        row = specs[row_id]
        rule = row["canonical_rule"]
        assert row["run_allowed"] == "research_sample_only"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
        assert row["uses_futures_contracts"] is False
        assert row["requires_network"] is False
        assert set(row["required_symbols"]).issubset(allowed_symbols)
        assert set(rule.get("ranked_assets", [])).issubset(COMMODITY_WRAPPERS)
        assert rule["leverage_setting"] == "none"
        assert rule["margin_setting"] == "none"
        assert rule["shorting_setting"] == "none"
        assert rule["futures_contract_logic"] == "none"
        assert "tune_parameters" in row["forbidden_next_actions"]
        assert "grid_search" in row["forbidden_next_actions"]
    assert specs["commodity_basket_tsmom_top2_half_bil_v1"]["canonical_rule"]["fixed_weights"] == {
        "commodity_basket_tsmom_top2_v1": 0.50,
        "BIL_cash_proxy": 0.50,
    }
    assert specs["combo_plus_commodity_basket_80_20_v1"]["canonical_rule"]["fixed_weights"] == {
        "combo_SPY200d_GLD_50_50_v1": 0.80,
        "commodity_basket_tsmom_top2_v1": 0.20,
    }
    assert specs["combo_plus_commodity_basket_80_20_v1"]["canonical_rule"]["active_combo_paper_forward_rule_changed"] is False


def test_profit_exploration_output_contains_batch_and_base_risk_aware_verdict() -> None:
    base_status = pd.read_csv(ROOT / "evidence" / "commodity_exploratory" / "latest" / "commodity_exploratory_status.csv")
    base = base_status[base_status["experiment_id"].eq("commodity_basket_tsmom_top2_v1")].iloc[0]
    assert base["verdict"] == "research_sample_candidate_risk_budget_breach"
    status = pd.read_csv(LATEST_DIR / "risk_control_batch1_status.csv")
    assert RISK_IDS.issubset(set(status["experiment_id"].astype(str)))
    rows = status[status["experiment_id"].isin(RISK_IDS)]
    assert rows["status"].eq("completed").all()
    assert rows["candidate_exhaustive_recommended"].map(profit.boolish).eq(False).all()
    assert status["paper_forward_active"].map(profit.boolish).eq(False).all()
    assert status["real_money_recommendation"].map(profit.boolish).eq(False).all()


def test_risk_control_manifest_confirms_research_boundaries() -> None:
    manifest = json.loads((LATEST_DIR / "risk_control_batch1_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["experiment_ids"]) == RISK_IDS
    assert manifest["base_commodity_verdict_correction"] == "research_sample_candidate_risk_budget_breach"
    assert manifest["research_sample_run"] is True
    assert manifest["profit_exploration_run"] is True
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["candidate_exhaustive_recommended"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["new_symbols_added"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["uses_leverage"] is False
    assert manifest["uses_margin"] is False
    assert manifest["uses_shorting"] is False
    assert manifest["direct_futures_contract_logic"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_risk_control_status_and_results_have_expected_rows() -> None:
    status = pd.read_csv(LATEST_DIR / "risk_control_batch1_status.csv")
    results = pd.read_csv(LATEST_DIR / "risk_control_batch1_results.csv")
    risk = pd.read_csv(LATEST_DIR / "risk_control_batch1_risk_summary.csv")
    diagnostics = pd.read_csv(LATEST_DIR / "risk_control_batch1_diagnostics.csv")
    assert set(status["experiment_id"].astype(str)) == RISK_IDS
    assert status["status"].eq("completed").all()
    assert status["candidate_exhaustive_recommended"].map(profit.boolish).eq(False).all()
    horizon_rows = results[results["row_type"].eq("candidate_horizon")]
    assert set(horizon_rows["horizon"].astype(int)) == {30, 60, 90, 180}
    assert RISK_IDS.issubset(set(horizon_rows["experiment_id"].astype(str)))
    assert {"commodity_basket_tsmom_top2_v1", "combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1", "SPY_200d_trend_model", "GLD_buy_hold", "BIL_cash_proxy"}.issubset(
        set(results["benchmark_id"].dropna().astype(str))
    )
    assert RISK_IDS.issubset(set(risk["experiment_id"].astype(str)))
    assert RISK_IDS.issubset(set(diagnostics["experiment_id"].astype(str)))


def test_run_profit_exploration_cli_has_risk_control_flag_guardrails(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "research_sample",
            "--reuse-cache",
            "--no-network",
            "--include-commodity-basket-exploratory",
            "--include-commodity-risk-control-batch1",
        ],
    )
    args = profit.parse_args()
    assert args.include_commodity_risk_control_batch1 is True
    assert args.include_commodity_basket_exploratory is True
