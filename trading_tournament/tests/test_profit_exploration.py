from __future__ import annotations

import hashlib
import json
import zipfile
from argparse import Namespace
from pathlib import Path

import pandas as pd
import yaml

import run_advisor_audit_packet as advisor_packet
import run_profit_exploration as profit


def args_for(
    mode: str = "smoke",
    include_crypto_exploratory: bool = False,
    include_fixed_combinations: bool = True,
    include_combination_batch1: bool = False,
    include_commodity_basket_exploratory: bool = False,
    include_commodity_risk_control_batch1: bool = False,
    include_crypto_tier2_risk_control_batch1: bool = False,
    include_global_multi_asset_batch1: bool = False,
    include_blocked: bool = True,
    finalists: str | None = None,
    horizons: str | None = None,
) -> Namespace:
    return Namespace(
        mode=mode,
        include_crypto_exploratory=include_crypto_exploratory,
        include_fixed_combinations=include_fixed_combinations,
        include_combination_batch1=include_combination_batch1,
        include_commodity_basket_exploratory=include_commodity_basket_exploratory,
        include_commodity_risk_control_batch1=include_commodity_risk_control_batch1,
        include_crypto_tier2_risk_control_batch1=include_crypto_tier2_risk_control_batch1,
        include_global_multi_asset_batch1=include_global_multi_asset_batch1,
        include_blocked=include_blocked,
        include_incomplete=True,
        no_network=True,
        reuse_cache=True,
        score_only=False,
        reuse_latest=False,
        max_runtime_minutes=60,
        finalists=finalists,
        horizons=horizons,
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_prices(values: list[float] | None = None) -> pd.DataFrame:
    values = values or [100.0, 101.0, 102.0, 103.0, 104.0]
    index = pd.date_range("2020-01-01", periods=len(values), freq="B")
    frame = pd.DataFrame(index=index)
    frame["SPY"] = values
    frame["GLD"] = values
    frame["IEF"] = values
    frame["BIL"] = values
    return frame


def buy_hold_model(symbol: str = "SPY", values: list[float] | None = None) -> profit.ExperimentModel:
    prices = synthetic_prices(values)
    return profit.ExperimentModel(
        f"{symbol}_buy_hold",
        "weighted",
        prices,
        profit.buy_hold_weights(prices, symbol),
        reference_symbol=symbol,
    )


def test_profit_lab_specs_exist_and_load() -> None:
    assert Path("profit_lab/profit_objective.yaml").exists()
    assert Path("profit_lab/profit_experiment_specs.yaml").exists()
    objective = yaml.safe_load(Path("profit_lab/profit_objective.yaml").read_text())
    assert objective["account"]["target_600_equity"] == 3600
    assert objective["account"]["target_900_equity"] == 3900
    assert objective["account"]["target_1200_equity"] == 4200
    specs = profit.load_specs()
    assert specs
    ids = {spec["experiment_id"] for spec in specs}
    assert {
        "asset_class_tsmom_equal_weight_v1",
        "asset_class_tsmom_top1_v1",
        "asset_class_tsmom_top2_v1",
        "qqq_spy_gld_ief_dual_momentum_v1",
        "value_momentum_factor_etf_rotation_v1",
        "sector_top2_momentum_simple_v1",
        "managed_futures_proxy_etf_trend_v1",
        "dual_momentum_SPY_GLD_IEF_v1",
        "GLD_200d_trend_model_v1",
    }.issubset(ids)


def test_qqq_dual_momentum_spec_is_research_sample_only() -> None:
    specs = profit.load_specs()
    qqq = next(spec for spec in specs if spec["experiment_id"] == "qqq_spy_gld_ief_dual_momentum_v1")
    assert qqq["lane"] == "profit_exploration"
    assert qqq["experiment_type"] == "strategy_variant"
    assert qqq["run_allowed"] == "research_sample_only"
    assert qqq["implementation_status"] == "implemented_research_sample"
    assert qqq["paper_forward_active"] is False
    assert qqq["paper_forward_allowed_by_risk_framework"] is False
    assert qqq["real_money_recommendation"] is False
    assert qqq["uses_leverage"] is False
    assert qqq["uses_shorting"] is False
    assert qqq["uses_margin"] is False
    assert qqq["requires_network"] is False
    assert set(qqq["required_symbols"]) == {"QQQ", "SPY", "GLD", "IEF", "BIL"}
    assert set(qqq["canonical_rule"]["asset_universe"]) == {"QQQ", "SPY", "GLD", "IEF", "BIL"}
    assert qqq["canonical_rule"]["number_of_selected_assets"] == 1
    assert qqq["canonical_rule"]["execution_timing_rule"] == "next_trading_day_after_rebalance_signal"


def test_value_momentum_factor_rotation_spec_is_research_sample_only() -> None:
    specs = profit.load_specs()
    row = next(spec for spec in specs if spec["experiment_id"] == "value_momentum_factor_etf_rotation_v1")
    assert row["implementation_rule_id"] == "value_momentum_factor_etf_rotation_top2_option_a_v1"
    assert row["lane"] == "profit_exploration"
    assert row["experiment_type"] == "strategy_variant"
    assert row["run_allowed"] == "research_sample_only"
    assert row["implementation_status"] == "implemented_research_sample"
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert row["uses_leverage"] is False
    assert row["uses_shorting"] is False
    assert row["uses_margin"] is False
    assert row["requires_network"] is False
    assert set(row["required_symbols"]) == {"MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"}
    assert set(row["reviewed_but_not_used_symbols"]) == {"VLUE", "SPLV"}
    assert set(row["canonical_rule"]["asset_universe"]) == {"MTUM", "VTV", "QUAL", "USMV", "SPY", "BIL"}
    assert set(row["canonical_rule"]["ranked_assets"]) == {"MTUM", "VTV", "QUAL", "USMV", "SPY"}
    assert "VLUE" not in row["canonical_rule"]["ranked_assets"]
    assert "SPLV" not in row["canonical_rule"]["ranked_assets"]
    assert row["canonical_rule"]["number_of_selected_assets"] == 2
    assert row["canonical_rule"]["execution_timing_rule"] == "next_trading_day_after_rebalance_signal"
    assert row["canonical_rule"]["max_gross_exposure"] == 1.0


def test_sector_top2_momentum_spec_is_research_sample_only() -> None:
    specs = profit.load_specs()
    row = next(spec for spec in specs if spec["experiment_id"] == "sector_top2_momentum_simple_v1")
    assert row["implementation_rule_id"] == "sector_top2_core_nine_momentum_v1"
    assert row["lane"] == "profit_exploration"
    assert row["experiment_type"] == "strategy_variant"
    assert row["run_allowed"] == "research_sample_only"
    assert row["implementation_status"] == "implemented_research_sample"
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert row["uses_leverage"] is False
    assert row["uses_shorting"] is False
    assert row["uses_margin"] is False
    assert row["requires_network"] is False
    assert set(row["required_symbols"]) == {"XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "BIL"}
    assert set(row["excluded_symbols_first_rule"]) == {"XLC", "XLRE"}
    assert set(row["canonical_rule"]["asset_universe"]) == {"XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "BIL"}
    assert set(row["canonical_rule"]["ranked_assets"]) == {"XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
    assert "XLC" not in row["canonical_rule"]["ranked_assets"]
    assert "XLRE" not in row["canonical_rule"]["ranked_assets"]
    assert row["canonical_rule"]["number_of_selected_assets"] == 2
    assert row["canonical_rule"]["execution_timing_rule"] == "next_trading_day_after_rebalance_signal"
    assert row["canonical_rule"]["max_gross_exposure"] == 1.0


def test_commodity_basket_exploratory_spec_is_research_sample_only() -> None:
    specs = profit.load_specs()
    row = next(spec for spec in specs if spec["experiment_id"] == "commodity_basket_tsmom_top2_v1")
    assert row["implementation_rule_id"] == "commodity_basket_tsmom_top2_fast_exploratory_v1"
    assert row["lane"] == "profit_exploration"
    assert row["experiment_type"] == "strategy_variant"
    assert row["run_allowed"] == "research_sample_only"
    assert row["implementation_status"] == "implemented_research_sample"
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert row["uses_leverage"] is False
    assert row["uses_shorting"] is False
    assert row["uses_margin"] is False
    assert row["uses_futures_contracts"] is False
    assert row["requires_network"] is False
    assert set(row["required_symbols"]) == {"DBC", "PDBC", "COMT", "GSG", "USCI", "BIL"}
    assert set(row["canonical_rule"]["ranked_assets"]) == {"DBC", "PDBC", "COMT", "GSG", "USCI"}
    assert row["canonical_rule"]["trend_filter"] == "none_first_fast_screen"
    assert row["canonical_rule"]["number_of_selected_assets"] == 2
    assert row["canonical_rule"]["futures_contract_logic"] == "none"
    assert row["canonical_rule"]["leverage_setting"] == "none"


def test_commodity_risk_control_batch1_specs_are_fixed_research_sample_only() -> None:
    specs = profit.load_specs()
    ids = {
        "commodity_basket_tsmom_top2_200d_filter_v1",
        "commodity_basket_tsmom_top2_half_bil_v1",
        "combo_plus_commodity_basket_80_20_v1",
    }
    rows = [row for row in specs if row["experiment_id"] in ids]
    assert {row["experiment_id"] for row in rows} == ids
    assert len([row for row in specs if row.get("experiment_type") == "commodity_risk_control_exploratory"]) == 3
    for row in rows:
        assert row["run_allowed"] == "research_sample_only"
        assert row["evidence_tier"] == "tier1_or_tier2_exploratory"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert row["uses_leverage"] is False
        assert row["uses_shorting"] is False
        assert row["uses_margin"] is False
        assert row["uses_futures_contracts"] is False
        assert row["requires_network"] is False
        assert "candidate_exhaustive_in_this_task" in row["forbidden_next_actions"]
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert row["canonical_rule"]["futures_contract_logic"] == "none"
        assert row["canonical_rule"]["leverage_setting"] == "none"
        assert row["canonical_rule"]["margin_setting"] == "none"
        assert row["canonical_rule"]["shorting_setting"] == "none"
    half = next(row for row in rows if row["experiment_id"] == "commodity_basket_tsmom_top2_half_bil_v1")
    combo = next(row for row in rows if row["experiment_id"] == "combo_plus_commodity_basket_80_20_v1")
    assert half["canonical_rule"]["fixed_weights"] == {"commodity_basket_tsmom_top2_v1": 0.50, "BIL_cash_proxy": 0.50}
    assert combo["canonical_rule"]["fixed_weights"] == {"combo_SPY200d_GLD_50_50_v1": 0.80, "commodity_basket_tsmom_top2_v1": 0.20}
    assert combo["canonical_rule"]["active_combo_paper_forward_rule_changed"] is False


def test_global_multi_asset_batch1_specs_are_fixed_research_sample_only() -> None:
    specs = profit.load_specs()
    ids = {
        "global_multi_asset_tsmom_top2_v1",
        "global_multi_asset_tsmom_top2_defensive_50_v1",
        "combo_plus_global_multi_asset_80_20_v1",
    }
    rows = [row for row in specs if row["experiment_id"] in ids]
    assert {row["experiment_id"] for row in rows} == ids
    assert len([row for row in specs if row.get("experiment_type") == "global_multi_asset_fast_exploratory"]) == 3
    for row in rows:
        assert row["run_allowed"] == "research_sample_only"
        assert row["evidence_tier"] == "tier1_or_tier2_exploratory"
        assert row["paper_forward_active"] is False
        assert row["real_money_recommendation"] is False
        assert row["uses_leverage"] is False
        assert row["uses_shorting"] is False
        assert row["uses_margin"] is False
        assert row["uses_futures_contracts"] is False
        assert row["uses_options"] is False
        assert row["uses_forex"] is False
        assert row["uses_intraday"] is False
        assert row["requires_network"] is False
        assert "candidate_exhaustive_in_this_task" in row["forbidden_next_actions"]
        assert "use_futures_contract_logic" in row["forbidden_next_actions"]
        assert "use_leverage" in row["forbidden_next_actions"]
        assert "use_margin" in row["forbidden_next_actions"]
        assert row["canonical_rule"]["futures_contract_logic"] == "none"
        assert row["canonical_rule"]["leverage_setting"] == "none"
        assert row["canonical_rule"]["margin_setting"] == "none"
        assert row["canonical_rule"]["shorting_setting"] == "none"
    base = next(row for row in rows if row["experiment_id"] == "global_multi_asset_tsmom_top2_v1")
    defensive = next(row for row in rows if row["experiment_id"] == "global_multi_asset_tsmom_top2_defensive_50_v1")
    combo = next(row for row in rows if row["experiment_id"] == "combo_plus_global_multi_asset_80_20_v1")
    assert set(base["canonical_rule"]["ranked_assets"]) == {"SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT"}
    assert "DBC" not in base["canonical_rule"]["ranked_assets"]
    assert "GSG" not in base["canonical_rule"]["ranked_assets"]
    assert "USCI" not in base["canonical_rule"]["ranked_assets"]
    assert defensive["canonical_rule"]["fixed_weights"] == {"global_multi_asset_tsmom_top2_v1": 0.50, "BIL_cash_proxy": 0.50}
    assert combo["canonical_rule"]["fixed_weights"] == {"combo_SPY200d_GLD_50_50_v1": 0.80, "global_multi_asset_tsmom_top2_v1": 0.20}
    assert combo["canonical_rule"]["active_combo_paper_forward_rule_changed"] is False


def test_managed_futures_proxy_spec_is_research_sample_only() -> None:
    specs = profit.load_specs()
    row = next(spec for spec in specs if spec["experiment_id"] == "managed_futures_proxy_etf_trend_v1")
    assert row["implementation_rule_id"] == "managed_futures_proxy_dbmf_kmlm_trend_v1"
    assert row["lane"] == "profit_exploration"
    assert row["experiment_type"] == "strategy_variant"
    assert row["run_allowed"] == "research_sample_only"
    assert row["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
    assert row["implementation_status"] == "implemented_research_sample"
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    assert row["uses_leverage"] is False
    assert row["uses_shorting"] is False
    assert row["uses_margin"] is False
    assert row["uses_futures_contracts"] is False
    assert row["requires_network"] is False
    assert set(row["required_symbols"]) == {"DBMF", "KMLM", "BIL"}
    assert set(row["excluded_symbols_first_rule"]) == {"CTA", "FMF", "WTMF"}
    assert set(row["canonical_rule"]["asset_universe"]) == {"DBMF", "KMLM", "BIL"}
    assert set(row["canonical_rule"]["ranked_assets"]) == {"DBMF", "KMLM"}
    assert "CTA" not in row["canonical_rule"]["ranked_assets"]
    assert "FMF" not in row["canonical_rule"]["ranked_assets"]
    assert "WTMF" not in row["canonical_rule"]["ranked_assets"]
    assert row["canonical_rule"]["number_of_selected_assets"] == 2
    assert row["canonical_rule"]["execution_timing_rule"] == "next_trading_day_after_rebalance_signal"
    assert row["canonical_rule"]["max_gross_exposure"] == 1.0
    assert row["canonical_rule"]["futures_contract_logic"] == "none"


def test_experiment_ids_unique_and_independent() -> None:
    specs = profit.load_specs()
    ids = [spec["experiment_id"] for spec in specs]
    assert len(ids) == len(set(ids))
    runnable = [spec for spec in specs if spec["run_allowed"] is True or str(spec["run_allowed"]).startswith("true_")]
    assert runnable
    assert all(spec["independent_account"] is True for spec in runnable)
    assert all(spec["starting_equity"] == 3000 for spec in runnable)


def test_profit_run_outputs_contract_no_crypto_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    args = args_for()
    _run_dir, latest, _context = profit.write_outputs(args)
    files = [path.name for path in latest.iterdir() if path.is_file()]
    assert sorted(files) == sorted(profit.REQUIRED_LATEST_FILES)
    assert len(files) <= 10
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    rolling = pd.read_csv(latest / "rolling_profit_distribution.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    assert not results["experiment_id"].astype(str).str.contains("crypto", case=False).any()
    assert status[status["experiment_id"].astype(str).str.contains("crypto", case=False)]["run_status"].eq("excluded_by_flag").all()
    assert {"target_600_before_stop", "target_900_before_stop", "target_1200_before_stop"}.issubset(results.columns)
    assert {"p_target_600_before_stop", "p_target_900_before_stop", "p_target_1200_before_stop"}.issubset(rolling.columns)
    assert {"profit_score", "risk_penalty", "final_score"}.issubset(rankings.columns)
    score_component_cols = {
        "score_target_300_component",
        "score_target_400_component",
        "score_target_600_component",
        "score_median_equity_component",
        "score_p95_equity_component",
        "score_expected_profit_component",
        "score_stop_penalty_component",
        "score_drawdown_excess_penalty_component",
        "score_stress_penalty_component",
    }
    score_view_cols = {
        "profit_seeking_score",
        "balanced_score",
        "drawdown_control_score",
        "rank_profit_seeking_score",
        "rank_balanced_score",
        "rank_drawdown_control_score",
        "score_audit_notes",
        "balanced_drawdown_aware_score_v2",
        "rank_balanced_drawdown_aware_v2",
        "risk_budget_used_90d",
        "risk_budget_used_180d",
        "target_score_component",
        "upside_score_component",
        "median_equity_score_component",
        "tail_equity_score_component",
        "stop_penalty_component",
        "drawdown_budget_penalty_component",
        "stress_penalty_component",
        "evidence_quality_penalty_component",
        "practical_verdict_v2",
        "practical_score_notes",
    }
    assert score_component_cols.issubset(rankings.columns)
    assert score_view_cols.issubset(rankings.columns)
    assert {"accounting_integrity_status", "profit_results_usable", "ranking_blocked_reason"}.issubset(rankings.columns)
    assert {"candidate_exhaustive_queue_rank", "deserves_candidate_exhaustive", "queue_reason"}.issubset(rankings.columns)
    assert {"reference_check_available", "reference_max_abs_error", "accounting_integrity_status"}.issubset(rolling.columns)
    assert "Accounting Integrity Audit" in (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert "Candidate Exhaustive Queue" in (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert "Profit Score Audit" in (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert "Drawdown-Aware Score v2" in (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assumptions = yaml.safe_load((latest / "assumptions_and_costs.yaml").read_text(encoding="utf-8"))
    assert assumptions["scoring_v2"]["name"] == "balanced_drawdown_aware_score_v2"
    warnings = (latest / "warnings_and_limitations.md").read_text(encoding="utf-8")
    assert "Score v2 changes ranking interpretation only" in warnings
    assert not rankings[rankings["evidence_tier"].eq("tier1_exploratory")]["profit_verdict"].eq("leading_profit_candidate").any()
    assert not any("ohlcv" in path.name.lower() or "raw" in path.name.lower() for path in latest.iterdir())


def test_qqq_research_sample_output_includes_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    finalists = ",".join(
        [
            "qqq_spy_gld_ief_dual_momentum_v1",
            "asset_class_tsmom_top2_v1",
            "combo_SPY200d_GLD_50_50_v1",
            "SPY_200d_trend_model",
            "SPY_buy_hold",
            "GLD_buy_hold",
            "BIL_cash_proxy",
            "asset_class_tsmom_equal_weight_v1",
        ]
    )
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="research_sample", finalists=finalists))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    qqq_results = results[results["experiment_id"].eq("qqq_spy_gld_ief_dual_momentum_v1")]
    qqq_status = status[status["experiment_id"].eq("qqq_spy_gld_ief_dual_momentum_v1")]
    qqq_ranking = rankings[rankings["experiment_id"].eq("qqq_spy_gld_ief_dual_momentum_v1")]
    assert not qqq_results.empty
    assert qqq_results["run_status"].eq("completed").all()
    assert not qqq_status.empty
    assert qqq_status["run_status"].eq("completed").all()
    diagnostic_cols = {
        "canonical_rule_hash",
        "duplicate_of",
        "duplicate_status",
        "qqq_selection_frequency",
        "spy_selection_frequency",
        "gld_selection_frequency",
        "ief_selection_frequency",
        "bil_allocation_frequency",
        "max_single_asset_allocation",
        "qqq_allocation_share",
        "equity_asset_allocation_share",
        "defensive_asset_allocation_share",
        "concentration_warning",
        "equity_beta_duplicate_warning",
    }
    assert diagnostic_cols.issubset(results.columns)
    assert diagnostic_cols.issubset(status.columns)
    assert diagnostic_cols.issubset(rankings.columns)
    assert qqq_results["duplicate_status"].eq("canonical_unique").all()
    assert pd.to_numeric(qqq_results["qqq_selection_frequency"], errors="coerce").notna().all()
    assert pd.to_numeric(qqq_results["equity_asset_allocation_share"], errors="coerce").between(0.0, 1.0).all()
    assert qqq_ranking["profit_verdict"].iloc[0] in {
        "research_sample_candidate",
        "candidate_exhaustive_queue",
        "watchlist",
        "high_upside_high_risk",
        "too_risky",
        "too_slow",
        "duplicate_or_near_duplicate",
        "incomplete_evidence",
    }
    assert "QQQ Dual Momentum Research Sample" in summary
    assert "Data downloaded: false" in summary
    assert "No real-money recommendation" in summary


def test_value_momentum_research_sample_output_includes_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    finalists = ",".join(
        [
            "value_momentum_factor_etf_rotation_v1",
            "combo_SPY200d_GLD_50_50_v1",
            "asset_class_tsmom_top2_v1",
            "SPY_200d_trend_model",
            "SPY_buy_hold",
            "GLD_buy_hold",
            "BIL_cash_proxy",
            "qqq_spy_gld_ief_dual_momentum_v1",
            "asset_class_tsmom_equal_weight_v1",
        ]
    )
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="research_sample", finalists=finalists))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    value_results = results[results["experiment_id"].eq("value_momentum_factor_etf_rotation_v1")]
    value_status = status[status["experiment_id"].eq("value_momentum_factor_etf_rotation_v1")]
    value_ranking = rankings[rankings["experiment_id"].eq("value_momentum_factor_etf_rotation_v1")]
    assert not value_results.empty
    assert value_results["run_status"].eq("completed").all()
    assert not value_status.empty
    assert value_status["run_status"].eq("completed").all()
    diagnostic_cols = {
        "canonical_rule_hash",
        "duplicate_of",
        "duplicate_status",
        "mtum_selection_frequency",
        "vtv_selection_frequency",
        "qual_selection_frequency",
        "usmv_selection_frequency",
        "spy_selection_frequency",
        "bil_allocation_frequency",
        "max_single_etf_allocation",
        "mtum_allocation_share",
        "vtv_allocation_share",
        "qual_allocation_share",
        "usmv_allocation_share",
        "spy_allocation_share",
        "bil_allocation_share",
        "equity_factor_allocation_share",
        "cash_treasury_allocation_share",
        "concentration_warning",
        "equity_beta_duplicate_warning",
    }
    assert diagnostic_cols.issubset(results.columns)
    assert diagnostic_cols.issubset(status.columns)
    assert diagnostic_cols.issubset(rankings.columns)
    assert value_results["duplicate_status"].eq("canonical_unique").all()
    assert pd.to_numeric(value_results["mtum_selection_frequency"], errors="coerce").notna().all()
    assert pd.to_numeric(value_results["equity_factor_allocation_share"], errors="coerce").between(0.0, 1.0).all()
    assert pd.to_numeric(value_results["cash_treasury_allocation_share"], errors="coerce").between(0.0, 1.0).all()
    assert value_ranking["profit_verdict"].iloc[0] in {
        "research_sample_candidate",
        "candidate_exhaustive_queue",
        "watchlist",
        "duplicate_or_near_duplicate",
        "high_upside_high_risk",
        "too_risky",
        "too_slow",
        "incomplete_evidence",
    }
    assert "Value/Momentum Factor ETF Rotation Research Sample" in summary
    assert "Data downloaded: false" in summary
    assert "VLUE" not in value_results.to_string()
    assert "SPLV" not in value_results.to_string()
    assert "No real-money recommendation" in summary


def test_sector_top2_research_sample_output_includes_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    finalists = ",".join(
        [
            "sector_top2_momentum_simple_v1",
            "combo_SPY200d_GLD_50_50_v1",
            "asset_class_tsmom_top2_v1",
            "SPY_200d_trend_model",
            "SPY_buy_hold",
            "GLD_buy_hold",
            "BIL_cash_proxy",
            "qqq_spy_gld_ief_dual_momentum_v1",
            "value_momentum_factor_etf_rotation_v1",
            "asset_class_tsmom_equal_weight_v1",
        ]
    )
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="research_sample", finalists=finalists))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    sector_results = results[results["experiment_id"].eq("sector_top2_momentum_simple_v1")]
    sector_status = status[status["experiment_id"].eq("sector_top2_momentum_simple_v1")]
    sector_ranking = rankings[rankings["experiment_id"].eq("sector_top2_momentum_simple_v1")]
    assert not sector_results.empty
    assert sector_results["run_status"].eq("completed").all()
    assert not sector_status.empty
    assert sector_status["run_status"].eq("completed").all()
    diagnostic_cols = {
        "canonical_rule_hash",
        "duplicate_of",
        "duplicate_status",
        "xlb_selection_frequency",
        "xle_selection_frequency",
        "xlf_selection_frequency",
        "xli_selection_frequency",
        "xlk_selection_frequency",
        "xlp_selection_frequency",
        "xlu_selection_frequency",
        "xlv_selection_frequency",
        "xly_selection_frequency",
        "bil_allocation_frequency",
        "xlb_allocation_share",
        "xle_allocation_share",
        "xlf_allocation_share",
        "xli_allocation_share",
        "xlk_allocation_share",
        "xlp_allocation_share",
        "xlu_allocation_share",
        "xlv_allocation_share",
        "xly_allocation_share",
        "bil_allocation_share",
        "equity_sector_allocation_share",
        "cash_treasury_allocation_share",
        "max_single_sector_allocation",
        "top_sector_dominance",
        "sector_turnover",
        "concentration_warning",
        "equity_beta_duplicate_warning",
    }
    assert diagnostic_cols.issubset(results.columns)
    assert diagnostic_cols.issubset(status.columns)
    assert diagnostic_cols.issubset(rankings.columns)
    assert sector_results["duplicate_status"].eq("canonical_unique").all()
    assert pd.to_numeric(sector_results["xlb_selection_frequency"], errors="coerce").notna().all()
    assert pd.to_numeric(sector_results["equity_sector_allocation_share"], errors="coerce").between(0.0, 1.0).all()
    assert pd.to_numeric(sector_results["cash_treasury_allocation_share"], errors="coerce").between(0.0, 1.0).all()
    assert sector_ranking["profit_verdict"].iloc[0] in {
        "research_sample_candidate",
        "candidate_exhaustive_queue",
        "watchlist",
        "duplicate_or_near_duplicate",
        "high_upside_high_risk",
        "too_risky",
        "too_slow",
        "incomplete_evidence",
    }
    assert "Sector Top-2 Momentum Research Sample" in summary
    assert "Data downloaded: false" in summary
    assert "XLC and XLRE excluded: true" in summary
    assert "xlc_selection_frequency" not in results.columns
    assert "xlre_selection_frequency" not in results.columns
    assert "xlc_allocation_share" not in results.columns
    assert "xlre_allocation_share" not in results.columns
    assert "No real-money recommendation" in summary


def test_managed_futures_proxy_research_sample_output_includes_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    finalists = ",".join(
        [
            "managed_futures_proxy_etf_trend_v1",
            "combo_SPY200d_GLD_50_50_v1",
            "asset_class_tsmom_top2_v1",
            "SPY_200d_trend_model",
            "SPY_buy_hold",
            "GLD_buy_hold",
            "BIL_cash_proxy",
            "qqq_spy_gld_ief_dual_momentum_v1",
            "value_momentum_factor_etf_rotation_v1",
            "sector_top2_momentum_simple_v1",
            "asset_class_tsmom_equal_weight_v1",
        ]
    )
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="research_sample", finalists=finalists))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    managed_results = results[results["experiment_id"].eq("managed_futures_proxy_etf_trend_v1")]
    managed_status = status[status["experiment_id"].eq("managed_futures_proxy_etf_trend_v1")]
    managed_ranking = rankings[rankings["experiment_id"].eq("managed_futures_proxy_etf_trend_v1")]
    assert not managed_results.empty
    assert managed_results["run_status"].eq("completed").all()
    assert not managed_status.empty
    assert managed_status["run_status"].eq("completed").all()
    diagnostic_cols = {
        "canonical_rule_hash",
        "duplicate_of",
        "duplicate_status",
        "required_label",
        "wrapper_proxy_warning",
        "short_history_warning",
        "dbmf_selection_frequency",
        "kmlm_selection_frequency",
        "bil_allocation_frequency",
        "dbmf_allocation_share",
        "kmlm_allocation_share",
        "bil_allocation_share",
        "max_single_proxy_allocation",
        "proxy_concentration_warning",
        "too_slow_warning",
        "wrapper_proxy_only_warning",
        "direct_futures_claim_disallowed",
        "correlation_to_combo_if_available",
        "correlation_to_top2_if_available",
        "correlation_to_spy200d_if_available",
        "drawdown_coincidence_warning_if_available",
    }
    assert diagnostic_cols.issubset(results.columns)
    assert diagnostic_cols.issubset(status.columns)
    assert diagnostic_cols.issubset(rankings.columns)
    assert managed_results["duplicate_status"].eq("canonical_unique").all()
    assert managed_results["required_label"].eq("fund_wrapper_proxy_short_history_limited_inception_research_sample_only").all()
    assert managed_results["wrapper_proxy_warning"].map(profit.boolish).all()
    assert managed_results["short_history_warning"].map(profit.boolish).all()
    assert managed_results["wrapper_proxy_only_warning"].map(profit.boolish).all()
    assert managed_results["direct_futures_claim_disallowed"].map(profit.boolish).all()
    assert pd.to_numeric(managed_results["dbmf_selection_frequency"], errors="coerce").notna().all()
    assert pd.to_numeric(managed_results["kmlm_selection_frequency"], errors="coerce").notna().all()
    assert pd.to_numeric(managed_results["bil_allocation_frequency"], errors="coerce").between(0.0, 1.0).all()
    assert managed_ranking["profit_verdict"].iloc[0] in {
        "research_sample_candidate",
        "candidate_exhaustive_queue_short_history_labeled",
        "watchlist",
        "too_slow",
        "high_upside_high_risk",
        "too_risky",
        "duplicate_or_near_duplicate",
        "incomplete_evidence",
        "reject_proxy_not_useful",
    }
    assert "Managed-Futures Proxy Research Sample" in summary
    assert "Data downloaded: false" in summary
    assert "CTA, FMF, and WTMF excluded: true" in summary
    assert "direct_futures_claim_disallowed=true" in summary
    assert "No real-money recommendation" in summary


def test_candidate_exhaustive_cli_accepts_finalists(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "candidate_exhaustive",
            "--finalists",
            "SPY_200d_trend_model,BIL_cash_proxy",
            "--reuse-cache",
            "--no-network",
            "--max-runtime-minutes",
            "360",
        ],
    )
    args = profit.parse_args()
    assert args.mode == "candidate_exhaustive"
    assert profit.parse_finalist_ids(args.finalists) == ["SPY_200d_trend_model", "BIL_cash_proxy"]
    assert args.max_runtime_minutes == 360


def test_horizons_cli_parses_reduced_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "candidate_exhaustive",
            "--finalists",
            "SPY_200d_trend_model,BIL_cash_proxy",
            "--horizons",
            "90,180",
            "--reuse-cache",
            "--no-network",
        ],
    )
    args = profit.parse_args()
    assert profit.selected_horizons_for_args(args) == [90, 180]
    meta = profit.validation_metadata(args)
    assert meta["run_validation_scope"] == "finalist_reduced_90_180"
    assert meta["selected_horizons"] == "90,180"
    assert meta["omitted_horizons"] == "30,60"
    assert meta["reduced_validation"] is True
    assert meta["full_horizon_validation_completed"] is False


def test_combination_batch1_cli_is_research_sample_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "research_sample",
            "--reuse-cache",
            "--no-network",
            "--include-combination-batch1",
        ],
    )
    args = profit.parse_args()
    assert args.mode == "research_sample"
    assert args.include_combination_batch1 is True


def test_commodity_risk_control_diagnostics_only_cli_is_cache_only(monkeypatch) -> None:
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
            "--diagnostics-only",
            "--export-attribution-diagnostics",
        ],
    )
    args = profit.parse_args()
    assert args.mode == "research_sample"
    assert args.include_commodity_basket_exploratory is True
    assert args.include_commodity_risk_control_batch1 is True
    assert args.diagnostics_only is True
    assert args.export_attribution_diagnostics is True
    assert args.no_network is True
    assert args.reuse_cache is True


def test_candidate_exhaustive_finalists_filter_and_all_possible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    monkeypatch.setattr(profit, "load_prices", lambda: synthetic_prices([100.0 + i * 0.1 for i in range(230)]))
    args = args_for(mode="candidate_exhaustive", finalists="SPY_200d_trend_model,BIL_cash_proxy")
    _run_dir, latest, _context = profit.write_outputs(args)
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    rolling = pd.read_csv(latest / "rolling_profit_distribution.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert set(results["experiment_id"]) == {"SPY_200d_trend_model", "BIL_cash_proxy"}
    assert set(rankings["experiment_id"]) == {"SPY_200d_trend_model", "BIL_cash_proxy"}
    assert "crypto" not in ",".join(results["experiment_id"].astype(str)).lower()
    assert "blocked_by_gate" not in set(results["run_status"].astype(str))
    assert rolling["rolling_method"].eq("all_possible").all()
    assert rolling["evidence_finality"].eq("exact_all_possible").all()
    assert results["final_validation_completed"].map(profit.boolish).all()
    assert results["sampled_results_are_final"].map(profit.boolish).all()
    assert results["candidate_exhaustive_completed"].map(profit.boolish).all()
    assert "Full Candidate-Exhaustive Finalist Validation Comparison" in summary
    assert "candidate_exhaustive_completed: true" in summary
    assert "all_possible_30_60_90_180_standard_and_stress_completed: true" in summary


def test_drawdown_budget_penalty_curve_penalizes_inside_budget() -> None:
    assert profit.drawdown_budget_penalty_for_usage(0.40) == 0.0
    assert profit.drawdown_budget_penalty_for_usage(0.60) > profit.drawdown_budget_penalty_for_usage(0.50)
    assert profit.drawdown_budget_penalty_for_usage(0.90) > profit.drawdown_budget_penalty_for_usage(0.60)
    assert profit.drawdown_budget_penalty_for_usage(1.10) > profit.drawdown_budget_penalty_for_usage(0.90)


def test_score_only_rebuilds_v2_without_changing_raw_metrics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    _run_dir, latest, _context = profit.write_outputs(args_for())
    results_before = pd.read_csv(latest / "profit_exploration_results.csv")
    rolling_before = pd.read_csv(latest / "rolling_profit_distribution.csv")
    score_args = args_for()
    score_args.score_only = True
    score_args.reuse_latest = True
    score_latest, context = profit.write_score_only_outputs(score_args)
    assert score_latest == latest
    results_after = pd.read_csv(latest / "profit_exploration_results.csv")
    rolling_after = pd.read_csv(latest / "rolling_profit_distribution.csv")
    result_metric_cols = [
        "experiment_id",
        "standard_or_stress",
        "unconditional_final_equity",
        "stop_enforced_final_equity",
        "max_drawdown_dollars",
        "target_300_before_stop",
        "target_400_before_stop",
        "target_600_before_stop",
        "target_900_before_stop",
        "target_1200_before_stop",
    ]
    rolling_metric_cols = [
        "experiment_id",
        "horizon",
        "standard_or_stress",
        "p_target_300_before_stop",
        "p_target_400_before_stop",
        "p_target_600_before_stop",
        "p_target_900_before_stop",
        "p_target_1200_before_stop",
        "p_any_project_stop_hit",
        "median_stop_enforced_final_equity",
        "p95_stop_enforced_final_equity",
        "worst_max_drawdown",
    ]
    pd.testing.assert_frame_equal(results_after[result_metric_cols], results_before[result_metric_cols], check_dtype=False)
    pd.testing.assert_frame_equal(rolling_after[rolling_metric_cols], rolling_before[rolling_metric_cols], check_dtype=False)
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    assert "balanced_drawdown_aware_score_v2" in rankings.columns
    assert "practical_verdict_v2" in rankings.columns
    assert "Drawdown-Aware Score v2" in (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert len([path for path in latest.iterdir() if path.is_file()]) <= 10
    assert context["zip_path"].exists()


def test_reduced_candidate_exhaustive_horizons_are_scoped_non_final(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    monkeypatch.setattr(profit, "load_prices", lambda: synthetic_prices([100.0 + i * 0.1 for i in range(230)]))
    args = args_for(mode="candidate_exhaustive", finalists="SPY_200d_trend_model,BIL_cash_proxy", horizons="90,180")
    _run_dir, latest, _context = profit.write_outputs(args)
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    rolling = pd.read_csv(latest / "rolling_profit_distribution.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    status = pd.read_csv(latest / "experiment_status.csv")
    summary = (latest / "profit_exploration_summary.md").read_text(encoding="utf-8")
    assert set(rolling["horizon"]) == {90, 180}
    assert results["omitted_horizons"].astype(str).eq("30,60").all()
    assert rolling["omitted_horizons"].astype(str).eq("30,60").all()
    assert rankings["omitted_horizons"].astype(str).eq("30,60").all()
    assert status["omitted_horizons"].astype(str).eq("30,60").all()
    assert results["reduced_validation"].map(profit.boolish).all()
    assert rankings["reduced_validation"].map(profit.boolish).all()
    assert results["selected_horizons_completed"].map(profit.boolish).all()
    assert not results["full_horizon_validation_completed"].map(profit.boolish).any()
    assert not results["final_validation_completed"].map(profit.boolish).any()
    assert not results["sampled_results_are_final"].map(profit.boolish).any()
    assert rolling["evidence_finality"].eq("exact_selected_horizons").all()
    assert "Reduced Finalist Validation Comparison" in summary
    assert "selected_horizons: 90,180" in summary
    assert "omitted_horizons: 30,60" in summary
    assert "full_horizon_validation_completed: false" in summary


def test_blocked_and_incomplete_rows_do_not_have_fabricated_metrics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    args = args_for()
    _run_dir, latest, _context = profit.write_outputs(args)
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    non_metric = results[results["run_status"].isin(["blocked_by_gate", "incomplete_evidence"])]
    assert not non_metric.empty
    metric_cols = ["unconditional_final_equity", "stop_enforced_final_equity", "target_300_before_stop", "target_1200_before_stop"]
    assert non_metric[metric_cols].isna().all().all()


def test_duplicate_rule_hashes_are_detected_and_skipped(tmp_path: Path, monkeypatch) -> None:
    specs = profit.load_specs()
    top1 = next(spec for spec in specs if spec["experiment_id"] == "asset_class_tsmom_top1_v1")
    dual = next(spec for spec in specs if spec["experiment_id"] == "dual_momentum_SPY_GLD_IEF_v1")
    assert profit.canonical_rule_hash(top1) == profit.canonical_rule_hash(dual)
    duplicates = profit.duplicate_map_for_specs(specs)
    assert duplicates["dual_momentum_SPY_GLD_IEF_v1"] == "asset_class_tsmom_top1_v1"
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="smoke"))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    rankings = pd.read_csv(latest / "profit_rankings.csv")
    duplicate_result = results[results["experiment_id"].eq("dual_momentum_SPY_GLD_IEF_v1")].iloc[0]
    duplicate_ranking = rankings[rankings["experiment_id"].eq("dual_momentum_SPY_GLD_IEF_v1")].iloc[0]
    assert duplicate_result["run_status"] == "duplicate_skipped"
    assert duplicate_result["duplicate_of"] == "asset_class_tsmom_top1_v1"
    assert duplicate_ranking["profit_verdict"] == "duplicate_skipped"
    assert not profit.boolish(duplicate_ranking["profit_results_usable"])


def test_monthly_strategy_weights_are_next_day_effective() -> None:
    index = pd.date_range("2020-01-01", periods=320, freq="B")
    prices = pd.DataFrame(index=index)
    prices["SPY"] = [100.0 + i * 0.2 for i in range(len(index))]
    prices["GLD"] = [100.0 - i * 0.01 for i in range(len(index))]
    prices["IEF"] = [100.0 - i * 0.01 for i in range(len(index))]
    prices["BIL"] = 100.0
    weights = profit.asset_class_tsmom_weights(prices, "top", top_n=1)
    first_spy_idx = next(i for i, value in enumerate(weights["SPY"].to_list()) if value == 1.0)
    assert first_spy_idx > 0
    # The signal is known at the prior close/rebalance date; exposure becomes effective on the next trading day.
    assert weights["SPY"].iloc[first_spy_idx - 1] != 1.0
    assert weights["SPY"].iloc[first_spy_idx] == 1.0


def test_managed_futures_proxy_weights_exclude_unapproved_symbols_and_are_next_day_effective() -> None:
    index = pd.date_range("2020-01-01", periods=360, freq="B")
    prices = pd.DataFrame(index=index)
    prices["DBMF"] = [100.0 + i * 0.15 for i in range(len(index))]
    prices["KMLM"] = [100.0 + i * 0.10 for i in range(len(index))]
    prices["BIL"] = 100.0
    prices["CTA"] = [100.0 + i * 0.50 for i in range(len(index))]
    weights = profit.managed_futures_proxy_weights(prices)
    assert "CTA" in weights.columns
    assert weights["CTA"].eq(0.0).all()
    assert weights[["DBMF", "KMLM", "BIL"]].sum(axis=1).le(1.0 + 1e-12).all()
    first_proxy_idx = next(i for i, value in enumerate(weights["DBMF"].to_list()) if value > 0.0)
    assert first_proxy_idx > 0
    assert weights["DBMF"].iloc[first_proxy_idx - 1] == 0.0
    assert weights["DBMF"].iloc[first_proxy_idx] > 0.0


def test_missing_cached_data_marks_incomplete_without_download(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    monkeypatch.setattr(profit, "load_prices", lambda: pd.DataFrame())
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="smoke"))
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    runnable = results[results["experiment_id"].isin(["asset_class_tsmom_equal_weight_v1", "asset_class_tsmom_top1_v1", "SPY_200d_trend_model"])]
    assert not runnable.empty
    assert runnable["run_status"].eq("incomplete_evidence").all()
    assert runnable["notes"].astype(str).str.contains("no download attempted").all()


def test_crypto_rows_are_tier1_when_included(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    args = args_for(include_crypto_exploratory=True)
    _run_dir, latest, _context = profit.write_outputs(args)
    results = pd.read_csv(latest / "profit_exploration_results.csv")
    crypto = results[results["experiment_id"].astype(str).str.contains("crypto", case=False)]
    assert not crypto.empty
    assert crypto["evidence_tier"].eq("tier1_exploratory").all()
    assert not crypto["profit_verdict"].eq("leading_profit_candidate").any()


def test_crypto_tier2_risk_control_specs_and_flag_are_fixed(monkeypatch) -> None:
    specs = {row["experiment_id"]: row for row in profit.load_specs()}
    ids = set(profit.CRYPTO_TIER2_RISK_CONTROL_BATCH1_IDS)
    declared = {
        exp_id
        for exp_id, row in specs.items()
        if row.get("experiment_type") == "crypto_spot_risk_control_exploratory"
    }
    assert declared == ids
    for exp_id in ids:
        row = specs[exp_id]
        assert row["run_allowed"] == "research_sample_only"
        assert row["evidence_tier"] == "tier2_exploratory"
        assert row["uses_leverage"] is False
        assert row["uses_margin"] is False
        assert row["uses_shorting"] is False
        assert row["uses_futures_contracts"] is False
        assert row["uses_perpetuals"] is False
        assert row["uses_options"] is False
        assert row["requires_network"] is False
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


def test_global_multi_asset_batch1_flag_is_research_sample_only(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_profit_exploration.py",
            "--mode",
            "research_sample",
            "--reuse-cache",
            "--no-network",
            "--include-global-multi-asset-batch1",
        ],
    )
    args = profit.parse_args()
    assert args.include_global_multi_asset_batch1 is True
    assumptions = profit.build_assumptions(args)
    assert assumptions["include_global_multi_asset_batch1"] is True
    batch = assumptions["global_multi_asset_fast_exploration_batch1"]
    assert batch["included"] is True
    assert batch["candidate_exhaustive_run"] is False
    assert batch["paper_forward_active"] is False
    assert batch["uses_leverage"] is False
    assert batch["uses_margin"] is False
    assert batch["uses_shorting"] is False
    assert batch["uses_futures_contracts"] is False


def test_script_does_not_modify_strategy_or_data_modules(tmp_path: Path, monkeypatch) -> None:
    protected = [
        Path("src/backtester.py"),
        Path("src/strategies.py"),
        Path("src/data.py"),
        Path("src/validation.py"),
    ]
    before = {path: file_hash(path) for path in protected}
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    args = args_for(mode="smoke")
    profit.write_outputs(args)
    after = {path: file_hash(path) for path in protected}
    assert before == after


def test_no_real_money_recommendation_language_in_profit_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    args = args_for()
    _run_dir, latest, _context = profit.write_outputs(args)
    for path in latest.iterdir():
        if path.suffix.lower() in {".md", ".csv", ".json", ".yaml"}:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert "real-money recommendation" not in text or "no real-money recommendation" in text or "not a real-money recommendation" in text


def test_advisor_upload_includes_profit_packet_when_evidence_exists(tmp_path: Path) -> None:
    assert Path("evidence/profit_exploration/latest").exists()
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "07_PROFIT_EXPLORATION.zip" in top_files
    with zipfile.ZipFile(latest / "07_PROFIT_EXPLORATION.zip") as zf:
        assert "PACKET_MANIFEST.json" in zf.namelist()
        manifest = json.loads(zf.read("PACKET_MANIFEST.json"))
    assert manifest["real_money_recommendation"] is False
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        matrix = zf.read("PROFIT_EXPLORATION_DECISION_MATRIX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "accounting_integrity_status" in matrix
    assert "Profit exploration accounting integrity" in executive


def test_synthetic_rolling_windows_rebase_accounting_state() -> None:
    model = buy_hold_model("SPY", [100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    metrics, _possible, _method = profit.rolling_metrics_for_model(model, horizon=3, mode="candidate_exhaustive", cost=0.0)
    assert metrics["window_start_equity_min"] == profit.STARTING_EQUITY
    assert metrics["window_start_equity_max"] == profit.STARTING_EQUITY
    assert metrics["window_start_equity_violation_count"] == 0
    assert metrics["high_water_start_violation_count"] == 0
    assert metrics["target_state_start_violation_count"] == 0
    assert metrics["stop_state_start_violation_count"] == 0
    assert metrics["accounting_integrity_status"] == "passed"


def test_buy_hold_synthetic_flat_and_plus_ten_reference() -> None:
    flat = profit.simulate_model_window(buy_hold_model("SPY", [100.0, 100.0, 100.0]), 0, 3, 0.0)
    assert flat["curve"]["equity"].iloc[0] == profit.STARTING_EQUITY
    assert flat["curve"]["equity"].iloc[-1] == profit.STARTING_EQUITY
    assert flat["reference"]["reference_error_status"] == "passed"
    plus_ten = profit.simulate_model_window(buy_hold_model("SPY", [100.0, 110.0]), 0, 2, 0.0)
    assert plus_ten["curve"]["equity"].iloc[0] == profit.STARTING_EQUITY
    assert abs(float(plus_ten["curve"]["equity"].iloc[-1]) - 3300.0) <= profit.REFERENCE_TOLERANCE
    assert plus_ten["reference"]["reference_error_status"] == "passed"


def test_real_buy_hold_reference_checks_pass_in_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(profit, "OUTPUT_ROOT", tmp_path / "profit_exploration")
    _run_dir, latest, _context = profit.write_outputs(args_for(mode="smoke"))
    rolling = pd.read_csv(latest / "rolling_profit_distribution.csv")
    for exp_id in ["SPY_buy_hold", "GLD_buy_hold", "IEF_buy_hold", "BIL_cash_proxy"]:
        row = rolling[(rolling["experiment_id"].eq(exp_id)) & (rolling["standard_or_stress"].eq("standard"))]
        assert not row.empty
        assert row["reference_check_available"].map(profit.boolish).all()
        assert row["reference_error_status"].eq("passed").all()
        assert pd.to_numeric(row["reference_max_abs_error"], errors="coerce").max() <= profit.REFERENCE_TOLERANCE


def test_fixed_combination_synthetic_weighted_return_reference() -> None:
    prices = synthetic_prices([100.0, 110.0, 121.0])
    sleeve_models = {
        "SPY_buy_hold": profit.ExperimentModel("SPY_buy_hold", "weighted", prices, profit.buy_hold_weights(prices, "SPY"), reference_symbol="SPY"),
        "GLD_buy_hold": profit.ExperimentModel("GLD_buy_hold", "weighted", prices, profit.buy_hold_weights(prices, "GLD"), reference_symbol="GLD"),
    }
    model = profit.ExperimentModel(
        "combo_test",
        "combo",
        prices,
        sleeve_models=sleeve_models,
        sleeve_weights={"SPY_buy_hold": 0.5, "GLD_buy_hold": 0.5},
    )
    run = profit.simulate_model_window(model, 0, 3, 0.0)
    assert run["curve"]["equity"].iloc[0] == profit.STARTING_EQUITY
    assert round(float(run["curve"]["equity"].iloc[-1]), 8) == 3630.0
    assert run["combination_check_passed"] is True


def test_non_rebased_cumulative_equity_fails_integrity() -> None:
    curve = pd.DataFrame({"equity": [3500.0, 3600.0]})
    check = profit.accounting_start_check(curve)
    assert check["window_rebased_correctly"] is False
    assert check["integrity_error"]


def test_failed_integrity_cannot_be_leading_profit_candidate() -> None:
    spec = {
        "experiment_id": "bad_accounting",
        "display_name": "Bad Accounting",
        "evidence_tier": "tier2_credible_prototype",
    }
    results = pd.DataFrame(
        [
            {
                "experiment_id": "bad_accounting",
                "standard_or_stress": "standard",
                "run_status": "completed",
                "stress_degradation": 0.0,
                "accounting_integrity_status": "failed",
                "profit_results_usable": False,
            }
        ]
    )
    rolling = pd.DataFrame(
        [
            {
                "experiment_id": "bad_accounting",
                "horizon": 90,
                "standard_or_stress": "standard",
                "p_target_300_before_stop": 1.0,
                "p_target_400_before_stop": 1.0,
                "p_target_600_before_stop": 1.0,
                "p_target_900_before_stop": 1.0,
                "p_target_1200_before_stop": 1.0,
                "p_any_project_stop_hit": 0.0,
                "median_stop_enforced_final_equity": 5000.0,
                "p95_stop_enforced_final_equity": 6000.0,
                "worst_max_drawdown": 0.0,
                "expected_profit_dollars": 2000.0,
            }
        ]
    )
    rankings = profit.build_rankings(results, rolling, [spec])
    row = rankings.iloc[0]
    assert row["profit_verdict"] == "invalid_accounting"
    assert row["profit_verdict"] != "leading_profit_candidate"
    assert not profit.boolish(row["profit_results_usable"])
