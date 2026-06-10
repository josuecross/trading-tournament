import json
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
LATEST_DIR = ROOT / "evidence" / "commodity_exploratory" / "latest"
ZIP_PATH = ROOT / "evidence" / "commodity_exploratory" / "latest_commodity_exploratory_packet.zip"
PROFIT_LATEST = ROOT / "evidence" / "profit_exploration" / "latest"
SYMBOLS = {"DBC", "PDBC", "COMT", "GSG", "USCI", "BIL"}


def test_commodity_exploratory_latest_packet_exists() -> None:
    assert LATEST_DIR.exists()
    assert ZIP_PATH.exists()
    files = [path.name for path in LATEST_DIR.iterdir() if path.is_file()]
    assert len(files) <= 10
    assert {
        "README_FOR_ADVISOR.md",
        "commodity_exploratory_summary.md",
        "commodity_exploratory_results.csv",
        "commodity_exploratory_risk_summary.csv",
        "commodity_exploratory_rankings.csv",
        "commodity_exploratory_status.csv",
        "warnings_and_limitations.md",
        "commodity_exploratory_manifest.json",
    }.issubset(files)


def test_commodity_exploratory_manifest_boundaries() -> None:
    manifest = json.loads((LATEST_DIR / "commodity_exploratory_manifest.json").read_text(encoding="utf-8"))
    assert manifest["experiment_id"] == "commodity_basket_tsmom_top2_v1"
    assert manifest["research_sample_run"] is True
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["direct_futures_contract_logic"] is False
    assert manifest["uses_leverage"] is False
    assert manifest["uses_margin"] is False
    assert manifest["uses_shorting"] is False


def test_profit_exploration_includes_commodity_row_after_run() -> None:
    status = pd.read_csv(ROOT / "evidence" / "commodity_exploratory" / "latest" / "commodity_exploratory_status.csv")
    assert "commodity_basket_tsmom_top2_v1" in set(status["experiment_id"].astype(str))
    row = status[status["experiment_id"].eq("commodity_basket_tsmom_top2_v1")].iloc[0]
    assert row["status"] in {"completed", "incomplete_evidence"}
    assert row["verdict"] == "research_sample_candidate_risk_budget_breach"
    warnings = (ROOT / "evidence" / "commodity_exploratory" / "latest" / "warnings_and_limitations.md").read_text(encoding="utf-8")
    assert "commodity_wrapper_evidence_research_sample_only" in warnings


def test_commodity_strategy_uses_only_reviewed_wrappers_and_bil() -> None:
    specs = yaml.safe_load((ROOT / "profit_lab" / "profit_experiment_specs.yaml").read_text(encoding="utf-8"))["experiments"]
    row = next(spec for spec in specs if spec["experiment_id"] == "commodity_basket_tsmom_top2_v1")
    assert set(row["required_symbols"]) == SYMBOLS
    assert set(row["canonical_rule"]["asset_universe"]) == SYMBOLS
    assert set(row["canonical_rule"]["ranked_assets"]) == {"DBC", "PDBC", "COMT", "GSG", "USCI"}
    assert row["uses_leverage"] is False
    assert row["uses_margin"] is False
    assert row["uses_shorting"] is False
    assert row["uses_futures_contracts"] is False
