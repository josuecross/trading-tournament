from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import run_advisor_audit_packet as advisor_packet


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_tmp_packet(tmp_path: Path) -> Path:
    result = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )
    return result["latest_dir"]


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def test_advisor_packet_files_exist() -> None:
    assert Path("run_advisor_audit_packet.py").exists()
    assert Path("advisor_audit/advisor_packet_spec.yaml").exists()


def test_advisor_packet_latest_folder_and_required_zips(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    assert latest.exists()
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "00_ADVISOR_INDEX.zip" in top_files
    assert "01_CHALLENGE_AND_FAMILY_AUDIT.zip" in top_files
    assert "03_RISK_AND_STRATEGY_GOVERNANCE.zip" in top_files
    assert "04_RESEARCH_DIRECTION_AND_GATES.zip" in top_files
    if Path("evidence/paper_forward_runs/latest").exists():
        assert "02_PAPER_FORWARD_AUDIT.zip" in top_files


def test_every_zip_has_manifest_and_advisor_readme(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    for zip_path in latest.glob("*.zip"):
        names = zip_names(zip_path)
        assert "PACKET_MANIFEST.json" in names
        assert "README_FOR_ADVISOR.md" in names
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read("PACKET_MANIFEST.json"))
        assert manifest["real_money_recommendation"] is False
        assert manifest["raw_data_included"] is False
        assert manifest["broker_integration"] is False
        assert manifest["live_orders"] is False
        assert "consistency_errors_count" in manifest


def test_zips_exclude_raw_cache_venv_and_nested_zips(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    forbidden = ["data/cache", "data/raw", ".venv", "__pycache__", ".pytest_cache", "ohlcv"]
    for zip_path in latest.glob("*.zip"):
        for name in zip_names(zip_path):
            lower = name.lower()
            assert not lower.endswith(".zip")
            assert not any(token in lower for token in forbidden)


def test_advisor_index_contains_required_matrices(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    index_zip = latest / "00_ADVISOR_INDEX.zip"
    names = zip_names(index_zip)
    assert "FAMILY_STATUS_MATRIX.csv" in names
    assert "CURRENT_DECISION_MATRIX.csv" in names
    assert "EVIDENCE_TIER_MAP.csv" in names
    assert "MISSING_OR_INCOMPLETE_EVIDENCE.csv" in names
    assert "PROFIT_EXPLORATION_DECISION_MATRIX.csv" in names
    assert "PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv" in names
    with zipfile.ZipFile(index_zip) as zf:
        profit_matrix = zf.read("PROFIT_EXPLORATION_DECISION_MATRIX.csv").decode("utf-8")
        review_index = zf.read("PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "deserves_candidate_exhaustive" in profit_matrix
    assert "queue_reason" in profit_matrix
    assert "combo_SPY200d_GLD_50_50_v1" in review_index
    assert "promote_to_paper_forward_review" in review_index
    assert "qqq_spy_gld_ief_dual_momentum_v1" in review_index
    assert "approve_research_sample_implementation" in review_index
    assert "value_momentum_factor_etf_rotation_v1" in review_index
    assert "approve_research_sample_implementation" in review_index
    assert "managed_futures_proxy_etf_trend_v1" in review_index
    assert "data_acquisition_required" in review_index
    assert "managed_futures_proxy_methodology_review" in review_index
    assert "conditional_approval_short_history_label_required" in review_index
    assert "candidate_testing_triage" in review_index
    assert "triage_complete_no_new_candidate_exhaustive_additions" in review_index
    assert "combo_paper_forward_observation_plan_review" in review_index
    assert "approve_future_paper_forward_observation_activation_prompt" in review_index
    assert "combo_paper_forward_observation_activation" in review_index
    assert ("active_waiting_for_next_cached_trading_day" in review_index) or ("active_paper_demo_observation" in review_index)
    assert "combo_rule_hash_resolution" in review_index
    assert "source_spec_reconstructed_hash_verified" in review_index
    assert "historical_research_expansion" in review_index
    assert "historical_research_expansion_parallel_to_paper_demo_observation" in review_index
    assert "research_state_dashboard" in review_index
    assert "historical_combination_batch1_verdict_audit" in review_index
    assert "verdict_labels_corrected_with_no_candidate_exhaustive_run" in review_index
    assert "historical_combination_batch1_diagnostics_completion" in review_index
    assert "diagnostics_support_short_history_watchlist_only" in review_index
    assert "historical_attribution_diagnostics" in review_index
    assert "attribution_diagnostics_available" in review_index
    assert "individual_stock_momentum_gate1b" in review_index
    assert "conditional_pending_provider_cost_review" in review_index
    assert "individual_stock_momentum_gate1c" in review_index
    assert "conditional_choose_provider_before_data_acquisition" in review_index
    assert "individual_stock_momentum_gate1d" in review_index
    assert "choose_norgate_for_gate1e_acquisition_review" in review_index
    assert "individual_stock_momentum_gate1e" in review_index
    assert "blocked_no_local_norgate_access" in review_index
    assert "individual_stock_momentum_gate1f_sharadar_fallback" in review_index
    assert "conditional_pending_package_and_terms_selection" in review_index
    assert "historical_research_queue_reprioritization" in review_index
    assert "choose_commodity_basket_etf_momentum_review" in review_index
    assert "commodity_basket_etf_momentum_v1" in review_index
    assert "commodity_basket_etf_product_data_review" in review_index
    assert "approve_data_acquisition_review" in review_index
    assert "commodity_data_acquisition_review" in review_index
    assert "commodity_basket_etf_data_acquisition_review" in review_index
    assert "conditional_pending_product_identity_terms_review" in review_index
    assert "product_identity_terms_review" in review_index
    for symbol in ["DBC", "PDBC", "COMT", "GSG", "USCI"]:
        assert symbol in review_index
    assert "Combo promotion review packet:" in executive
    assert "Combo paper-forward observation plan packet:" in executive
    assert "Combo paper-forward observation activation packet:" in executive
    assert "Combo rule-hash resolution packet:" in executive
    assert "Historical research expansion packet:" in executive
    assert "Current-state research dashboard:" in executive
    assert "Historical Combination Batch 1 verdict audit:" in executive
    assert "Historical Combination Batch 1 diagnostics completion:" in executive
    assert "diagnostics_support_short_history_watchlist_only" in executive
    assert "Historical attribution diagnostics packet:" in executive
    assert "attribution_diagnostics_available" in executive
    assert "Individual stock momentum Gate 1B packet:" in executive
    assert "conditional_pending_provider_cost_review" in executive
    assert "Individual stock momentum Gate 1C packet:" in executive
    assert "conditional_choose_provider_before_data_acquisition" in executive
    assert "Individual stock momentum Gate 1D packet:" in executive
    assert "choose_norgate_for_gate1e_acquisition_review" in executive
    assert "Individual stock momentum Gate 1E packet:" in executive
    assert "blocked_no_local_norgate_access" in executive
    assert "Individual stock momentum Gate 1F Sharadar fallback packet:" in executive
    assert "conditional_pending_package_and_terms_selection" in executive
    assert "Historical research queue reprioritization packet:" in executive
    assert "choose_commodity_basket_etf_momentum_review" in executive
    assert "commodity_basket_etf_momentum_v1" in executive
    assert "create_commodity_basket_etf_momentum_review" in executive
    assert "Commodity basket ETF product/data review packet:" in executive
    assert "approve_data_acquisition_review" in executive
    assert "commodity_data_acquisition_review" in executive
    assert "Commodity basket ETF data acquisition review packet:" in executive
    assert "conditional_pending_product_identity_terms_review" in executive
    assert "product_identity_terms_review" in executive
    assert "Commodity Risk-Control Batch 1 packet:" in executive
    assert "commodity_risk_control_batch1" in review_index
    assert "no_candidate_exhaustive_review" in review_index
    assert "combo_plus_commodity_basket_80_20_v1" in executive
    assert "Commodity Risk-Control Batch 1 verdict audit packet:" in executive
    assert "commodity_risk_control_batch1_verdict_audit" in review_index
    assert "more_diagnostics_required_before_candidate_exhaustive_decision" in review_index
    assert "Commodity Risk-Control Batch 1 diagnostics completion packet:" in executive
    assert "commodity_risk_control_batch1_diagnostics_completion" in review_index
    assert "diagnostics_support_watchlist_only_for_combo_plus_commodity_80_20" in review_index
    assert "watchlist-only" in review_index
    assert "candidate_exhaustive recommended: False" in executive
    assert "Crypto spot fast acquisition/cache packet:" in executive
    assert "crypto_spot_fast_acquisition" in review_index
    assert "Crypto Spot Tier 2 Risk-Control Batch 1 packet:" in executive
    assert "crypto_spot_tier2_risk_control_batch1" in review_index
    assert "Global multi-asset fast acquisition packet:" in executive
    assert "global_multi_asset_fast_acquisition" in review_index
    assert "Global Multi-Asset ETF Fast Exploration Batch 1 packet:" in executive
    assert "global_multi_asset_fast_exploration_batch1" in review_index
    assert "global_multi_asset_tsmom_top2_v1" in executive
    assert "no_candidate_exhaustive_review" in review_index
    assert "active paper/demo observation does not freeze historical research" in executive
    assert "QQQ implementation review packet:" in executive
    assert "Value/momentum factor ETF implementation review packet:" in executive
    assert "Managed-futures proxy implementation review packet:" in executive
    assert "Managed-futures proxy methodology review packet:" in executive
    assert "Candidate testing triage packet:" in executive
    assert "DATA_ACQUISITION_REVIEW_INDEX.csv" in names
    with zipfile.ZipFile(index_zip) as zf:
        data_acquisition_index = zf.read("DATA_ACQUISITION_REVIEW_INDEX.csv").decode("utf-8")
    assert "value_momentum_factor_etf_rotation_v1" in data_acquisition_index
    assert "conditional_pending_terms_or_api_key" in data_acquisition_index
    assert "approve_future_yfinance_download_prompt" in data_acquisition_index
    assert "managed_futures_proxy_etf_trend_v1" in data_acquisition_index
    assert "acquisition_review_passed_create_provider_terms_review" in data_acquisition_index
    assert "approve_future_yfinance_download_prompt_dbmf_kmlm_only" in data_acquisition_index
    assert "managed_futures_proxy_data_acquisition_run" in data_acquisition_index
    assert "paper_forward_observation_cache_update" in data_acquisition_index
    assert "ADVISOR_CONSISTENCY_REPORT.json" in names
    assert "ADVISOR_CONSISTENCY_REPORT.md" in names
    assert "ADVISOR_CONSISTENCY_REPORT.csv" not in names
    with zipfile.ZipFile(index_zip) as zf:
        missing = zf.read("MISSING_OR_INCOMPLETE_EVIDENCE.csv").decode("utf-8")
        consistency = json.loads(zf.read("ADVISOR_CONSISTENCY_REPORT.json"))
    assert "incomplete_evidence" in missing or "blocked_by_gate" in missing
    assert "consistency_status" in consistency


def test_profit_packet_contains_drawdown_aware_v2(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    profit_zip = latest / "07_PROFIT_EXPLORATION.zip"
    assert profit_zip.exists()
    with zipfile.ZipFile(profit_zip) as zf:
        rankings = zf.read("source/evidence/profit_exploration/latest/profit_rankings.csv").decode("utf-8")
        summary = zf.read("source/evidence/profit_exploration/latest/profit_exploration_summary.md").decode("utf-8")
    assert "balanced_drawdown_aware_score_v2" in rankings
    assert "risk_budget_used_90d" in rankings
    assert "practical_verdict_v2" in rankings
    assert "Drawdown-Aware Score v2" in summary


def test_challenge_packet_contains_generated_family_matrices(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    challenge_zip = latest / "01_CHALLENGE_AND_FAMILY_AUDIT.zip"
    names = zip_names(challenge_zip)
    assert "ROW_FINALITY_MATRIX.csv" in names
    assert "FAMILY_COMPARISON_MATRIX.csv" in names
    assert "BEST_FAMILY_DECISION.md" in names


def test_missing_files_are_reported_not_ignored(tmp_path: Path) -> None:
    latest = build_tmp_packet(tmp_path)
    research_zip = latest / "04_RESEARCH_DIRECTION_AND_GATES.zip"
    with zipfile.ZipFile(research_zip) as zf:
        manifest = json.loads(zf.read("PACKET_MANIFEST.json"))
    assert "missing_files" in manifest


def test_script_does_not_modify_strategy_or_data_modules(tmp_path: Path) -> None:
    protected = [
        Path("src/backtester.py"),
        Path("src/strategies.py"),
        Path("src/data.py"),
        Path("src/validation.py"),
    ]
    before = {path: file_hash(path) for path in protected}
    build_tmp_packet(tmp_path)
    after = {path: file_hash(path) for path in protected}
    assert before == after


def test_script_source_does_not_call_backtest_or_report() -> None:
    source = Path("run_advisor_audit_packet.py").read_text(encoding="utf-8")
    assert "run_backtest.py" not in source
    assert "run_report.py" not in source
    assert "subprocess" not in source
