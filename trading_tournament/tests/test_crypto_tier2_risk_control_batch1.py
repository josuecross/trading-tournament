from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import yaml

import run_profit_exploration as profit


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "crypto_lab" / "tier2_risk_control_batch1"
LATEST_DIR = ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest"
ZIP_PATH = ROOT / "evidence" / "crypto_lab" / "tier2_risk_control_batch1" / "latest_tier2_risk_control_batch1_packet.zip"
PROFIT_LATEST = ROOT / "evidence" / "profit_exploration" / "latest"
RISK_IDS = {
    "crypto_spot_tsmom_top1_cash_filter_v1",
    "crypto_spot_equal_weight_200d_filter_v1",
    "combo_plus_crypto_spot_tsmom_90_10_v1",
}
CRYPTO_SYMBOLS = {"BTC-USD", "ETH-USD"}


def _specs_by_id() -> dict[str, dict]:
    data = yaml.safe_load((ROOT / "profit_lab" / "profit_experiment_specs.yaml").read_text(encoding="utf-8"))
    return {row["experiment_id"]: row for row in data["experiments"]}


def test_batch_folder_specs_and_latest_packet_exist() -> None:
    assert BATCH_DIR.exists()
    assert (BATCH_DIR / "TIER2_RISK_CONTROL_BATCH1_SPECS.yaml").exists()
    assert LATEST_DIR.exists()
    assert ZIP_PATH.exists()
    files = {path.name for path in LATEST_DIR.iterdir() if path.is_file()}
    expected = {
        "README_FOR_ADVISOR.md",
        "tier2_risk_control_batch1_summary.md",
        "tier2_risk_control_batch1_results.csv",
        "tier2_risk_control_batch1_rankings.csv",
        "tier2_risk_control_batch1_risk_summary.csv",
        "tier2_risk_control_batch1_diagnostics.csv",
        "tier2_risk_control_batch1_status.csv",
        "warnings_and_limitations.md",
        "tier2_risk_control_batch1_manifest.json",
    }
    assert files == expected
    assert len(files) <= 10
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == expected


def test_exactly_three_crypto_risk_control_candidates_are_declared() -> None:
    specs = _specs_by_id()
    declared = {
        row_id
        for row_id, row in specs.items()
        if row.get("experiment_type") == "crypto_spot_risk_control_exploratory"
    }
    assert declared == RISK_IDS
    batch_specs = yaml.safe_load((BATCH_DIR / "TIER2_RISK_CONTROL_BATCH1_SPECS.yaml").read_text(encoding="utf-8"))
    assert set(batch_specs["allowed_crypto_symbols"]) == CRYPTO_SYMBOLS
    assert len(batch_specs["fixed_candidates"]) == 3
    assert {row["experiment_id"] for row in batch_specs["fixed_candidates"]} == RISK_IDS


def test_crypto_specs_use_btc_eth_only_and_no_forbidden_mechanics() -> None:
    specs = _specs_by_id()
    for row_id in RISK_IDS:
        row = specs[row_id]
        assert row["run_allowed"] == "research_sample_only"
        assert row["evidence_tier"] == "tier2_exploratory"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
        assert row["uses_futures_contracts"] is False
        assert row["uses_perpetuals"] is False
        assert row["uses_options"] is False
        assert row["requires_network"] is False
        assert "add_crypto_assets_without_review" in row["forbidden_next_actions"]
        text = yaml.safe_dump(row, sort_keys=False)
        assert "perpetual" in text
        assert "futures" in text
        assert "options" in text
        assert "leverage" in text
        assert "margin" in text
    assert set(specs["crypto_spot_tsmom_top1_cash_filter_v1"]["canonical_rule"]["ranked_assets"]) == CRYPTO_SYMBOLS
    assert set(specs["crypto_spot_equal_weight_200d_filter_v1"]["canonical_rule"]["ranked_assets"]) == CRYPTO_SYMBOLS
    combo_components = set(specs["combo_plus_crypto_spot_tsmom_90_10_v1"]["canonical_rule"]["components"])
    assert combo_components == {"combo_SPY200d_GLD_50_50_v1", "crypto_spot_tsmom_top1_cash_filter_v1"}


def test_profit_exploration_output_contains_crypto_batch() -> None:
    status = pd.read_csv(LATEST_DIR / "tier2_risk_control_batch1_status.csv")
    assert set(status["experiment_id"].astype(str)) == RISK_IDS
    assert status["status"].isin(["completed", "incomplete_evidence"]).all()
    assert status["candidate_exhaustive_recommended"].map(profit.boolish).isin([True, False]).all()
    assert status["paper_forward_active"].map(profit.boolish).eq(False).all()
    assert status["real_money_recommendation"].map(profit.boolish).eq(False).all()


def test_crypto_risk_control_manifest_confirms_research_boundaries() -> None:
    manifest = json.loads((LATEST_DIR / "tier2_risk_control_batch1_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["experiment_ids"]) == RISK_IDS
    assert manifest["research_sample_run"] is True
    assert manifest["profit_exploration_run"] is True
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["new_symbols_added"] == []
    assert manifest["symbols_used"] == ["BTC-USD", "ETH-USD", "BIL"]
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["uses_leverage"] is False
    assert manifest["uses_margin"] is False
    assert manifest["uses_shorting"] is False
    assert manifest["uses_futures_contracts"] is False
    assert manifest["uses_perpetuals"] is False
    assert manifest["uses_options"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["latest_folder_file_count"] <= 10


def test_crypto_risk_control_status_and_results_have_expected_rows() -> None:
    results = pd.read_csv(LATEST_DIR / "tier2_risk_control_batch1_results.csv")
    risk = pd.read_csv(LATEST_DIR / "tier2_risk_control_batch1_risk_summary.csv")
    diagnostics = pd.read_csv(LATEST_DIR / "tier2_risk_control_batch1_diagnostics.csv")
    horizon_rows = results[results["row_type"].eq("candidate_horizon")]
    assert RISK_IDS.issubset(set(horizon_rows["experiment_id"].astype(str)))
    assert set(horizon_rows["horizon"].astype(int)) == {30, 60, 90, 180}
    assert {"combo_SPY200d_GLD_50_50_v1", "asset_class_tsmom_top2_v1", "SPY_200d_trend_model", "GLD_buy_hold", "BIL_cash_proxy"}.issubset(
        set(results["benchmark_id"].dropna().astype(str))
    )
    assert RISK_IDS.issubset(set(risk["experiment_id"].astype(str)))
    assert RISK_IDS.issubset(set(diagnostics["experiment_id"].astype(str)))


def test_crypto_risk_control_cli_flag_guardrails(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "research_sample",
            "--reuse-cache",
            "--no-network",
            "--include-crypto-tier2-risk-control-batch1",
        ],
    )
    args = profit.parse_args()
    assert args.include_crypto_tier2_risk_control_batch1 is True
    assert args.no_network is True
    assert args.reuse_cache is True
