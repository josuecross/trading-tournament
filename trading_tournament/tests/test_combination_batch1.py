from __future__ import annotations

import json
import zipfile
from argparse import Namespace
from pathlib import Path

import pandas as pd
import yaml

import run_profit_exploration as profit


ROOT = Path(__file__).resolve().parents[1]
COMBINATION_DIR = ROOT / "combination_lab"
LATEST_DIR = ROOT / "evidence" / "combination_lab" / "latest"


def args_for_batch(finalists: str | None = None) -> Namespace:
    return Namespace(
        mode="research_sample",
        include_crypto_exploratory=False,
        include_fixed_combinations=True,
        include_combination_batch1=True,
        include_blocked=True,
        include_incomplete=True,
        no_network=True,
        reuse_cache=True,
        score_only=False,
        reuse_latest=False,
        max_runtime_minutes=60,
        finalists=finalists,
        horizons="90,180",
    )


def synthetic_batch_prices(rows: int = 460) -> pd.DataFrame:
    index = pd.date_range("2021-01-04", periods=rows, freq="B")
    frame = pd.DataFrame(index=index)
    frame["SPY"] = [100.0 + i * 0.08 for i in range(rows)]
    frame["GLD"] = [100.0 + i * 0.05 + (i % 35) * 0.02 for i in range(rows)]
    frame["IEF"] = [100.0 + i * 0.015 for i in range(rows)]
    frame["BIL"] = [100.0 + i * 0.004 for i in range(rows)]
    frame["DBMF"] = [100.0 + i * 0.035 + (i % 20) * 0.01 for i in range(rows)]
    frame["KMLM"] = [100.0 + i * 0.025 + (i % 25) * 0.015 for i in range(rows)]
    return frame


def test_combination_lab_folder_and_specs_exist() -> None:
    assert COMBINATION_DIR.exists()
    specs = yaml.safe_load((COMBINATION_DIR / "combination_batch1_specs.yaml").read_text(encoding="utf-8"))
    combinations = specs["combinations"]
    assert len(combinations) == 3
    ids = {row["combination_id"] for row in combinations}
    assert ids == set(profit.COMBINATION_BATCH1_IDS)
    assert specs["optimization_allowed"] is False
    assert specs["dynamic_weights_allowed"] is False
    assert specs["candidate_exhaustive_allowed"] is False
    assert specs["data_download_allowed"] is False
    for row in combinations:
        weights = row["fixed_weights"]
        assert abs(sum(float(value) for value in weights.values()) - 1.0) < 1e-12
        assert row["research_sample_allowed_now"] is True
        assert row["candidate_exhaustive_allowed_now"] is False


def test_profit_specs_include_exactly_batch1_rows_and_boundaries() -> None:
    specs = profit.load_specs()
    batch = [spec for spec in specs if spec["experiment_id"] in profit.COMBINATION_BATCH1_IDS]
    assert len(batch) == 3
    for row in batch:
        assert row["experiment_type"] == "fixed_strategy_combination"
        assert row["run_allowed"] == "research_sample_only"
        assert row["implementation_status"] == "implemented_research_sample"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
        assert row["requires_network"] is False
        assert "tune_weights" in row["forbidden_next_actions"]
        assert "replace_spy200d" in row["forbidden_next_actions"]
    managed = [row for row in batch if "managed_futures_proxy_etf_trend_v1" in row["underlying_components"]]
    assert len(managed) == 2
    for row in managed:
        assert row["required_label"] == profit.MANAGED_FUTURES_REQUIRED_LABEL
        assert row["uses_futures_contracts"] is False
        assert set(row["excluded_symbols_first_rule"]) == {"CTA", "FMF", "WTMF"}


def test_combination_batch1_research_sample_outputs_and_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    monkeypatch.setattr(profit, "COMBINATION_OUTPUT_ROOT", tmp_path / "combination_lab")
    monkeypatch.setattr(profit, "load_prices", synthetic_batch_prices)
    monkeypatch.setattr(
        profit,
        "sample_etf_starts",
        lambda prices, horizon, mode, sample_size=40: ([0, max(0, len(prices) - horizon - 1)], 2, "sampled"),
    )
    finalists = ",".join([
        *profit.COMBINATION_BATCH1_IDS,
        "combo_SPY200d_GLD_50_50_v1",
        "asset_class_tsmom_top2_v1",
        "SPY_200d_trend_model",
        "GLD_buy_hold",
        "BIL_cash_proxy",
    ])
    _run_dir, latest, context = profit.write_outputs(args_for_batch(finalists=finalists))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert set(profit.COMBINATION_BATCH1_IDS).issubset(set(results["experiment_id"]))
    assert set(profit.COMBINATION_BATCH1_IDS).issubset(set(rankings["experiment_id"]))
    assert "Historical Combination Batch 1" in summary
    assert "Data downloaded: false" in summary or "data downloaded: false" in summary
    assert not rankings[rankings["experiment_id"].isin(profit.COMBINATION_BATCH1_IDS)]["deserves_candidate_exhaustive"].map(profit.boolish).any()
    combo_latest = context["combination_latest_dir"]
    assert combo_latest.exists()
    assert {path.name for path in combo_latest.iterdir() if path.is_file()} == set(profit.COMBINATION_REQUIRED_LATEST_FILES)
    assert len([path for path in combo_latest.iterdir() if path.is_file()]) <= 10
    manifest = json.loads((combo_latest / "combination_batch1_manifest.json").read_text(encoding="utf-8"))
    assert manifest["fixed_combination_batch"] is True
    assert manifest["profit_exploration_run"] is True
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["active_combo_rule_changed"] is False
    assert manifest["spy200d_replaced"] is False
    assert manifest["real_money_recommendation"] is False
    with zipfile.ZipFile(context["combination_zip_path"]) as zf:
        assert set(zf.namelist()) == set(profit.COMBINATION_REQUIRED_LATEST_FILES)


def test_combination_batch1_docs_predeclare_failure_and_diagnostics() -> None:
    failure = (COMBINATION_DIR / "COMBINATION_BATCH1_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    diagnostics = (COMBINATION_DIR / "COMBINATION_BATCH1_DIAGNOSTICS_SPEC.md").read_text(encoding="utf-8")
    review = (COMBINATION_DIR / "COMBINATION_BATCH1_REVIEW.md").read_text(encoding="utf-8")
    assert "Does not beat combo/top2 on stop-aware profit/risk" in failure
    assert "Correlation versus combo" in diagnostics
    assert "If correlation diagnostics cannot be calculated" in diagnostics
    assert "tests exactly three fixed combinations" in review
    assert "no optimized weights" in review.lower() or "no optimization" in review.lower()


def test_combination_batch1_source_boundaries() -> None:
    source = (ROOT / "run_profit_exploration.py").read_text(encoding="utf-8")
    assert "run_backtest.py" not in source
    assert "run_paper_forward_observation.py" not in source
    # Later fast exploratory ETF/fund lanes may mention yfinance-compatible cache
    # paths, but this fixed combination batch still must not perform downloads.
    assert "candidate_exhaustive_run\": False" in source
    assert "candidate_exhaustive_run\": False" in source
