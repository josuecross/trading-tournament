from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.bt_adapter_multasset_control_poc import (
    FINAL_DECISION_PASSED,
    NEXT_ACTION_COMPARE,
    VALID_FINAL_DECISIONS,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "bt_adapter_multasset_control_poc" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "bt_adapter_multasset_control_poc_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads(
        (EVIDENCE / "bt_adapter_multasset_control_poc_consistency_check.json").read_text(encoding="utf-8")
    )


def test_multasset_poc_manifest_guardrails_and_template_selection() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["bt_adapter_multasset_control_poc"] is True
    assert manifest["bt_adapter_multasset_control_poc_only"] is True
    assert manifest["selected_existing_template"] is True
    assert manifest["source_template_available"] is True
    assert manifest["reference_template_id"] == "global_tsmom_weights"
    assert manifest["reference_variant_id"] == "gma_bounded_base_tsmom_top2_126_v1"
    assert manifest["source_family_id"] == "global_multi_asset_etf_momentum"
    assert manifest["control_concept"] == "global_multi_asset_tsmom_top2_126_bil_fallback"
    assert manifest["lookback_days"] == 126
    assert manifest["top_n"] == 2
    assert manifest["bt_package_available"] is True
    assert manifest["bt_package_version"] == "1.2.0"
    assert manifest["package_install_attempted_in_this_step"] is False
    assert manifest["dependency_file_modified_in_this_step"] is False
    assert manifest["requirements_contains_bt"] is True
    assert manifest["adapter_execution_attempted"] is True
    assert manifest["bt_algo_composition_run"] is True
    assert manifest["adapter_outputs_created"] is True
    assert manifest["reference_comparison_performed"] is True
    assert manifest["selected_assets_ranking_comparison_performed"] is True
    assert manifest["exposure_invariant_checked"] is True
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["final_adapter_decision"] in VALID_FINAL_DECISIONS
    assert manifest["final_adapter_decision"] == FINAL_DECISION_PASSED
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert manifest["next_action"] == NEXT_ACTION_COMPARE
    assert consistency["consistency_passed"] is True


def test_multasset_poc_no_forbidden_paths_or_strategy_evidence() -> None:
    manifest = load_manifest()

    assert manifest["new_public_strategy_implemented"] is False
    assert manifest["public_source_scraped"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["strategy_discovery_run"] is False
    assert manifest["broad_research_batch_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["promotion_candidates_created"] is False
    assert manifest["best_single_variant_promoted"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["new_paper_forward_candidate_created"] is False
    assert manifest["broker_api_called"] is False
    assert manifest["broker_orders_submitted"] is False
    assert manifest["broker_orders_cancelled"] is False
    assert manifest["broker_orders_reconciled"] is False
    assert manifest["live_orders"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["performance_evidence_created"] is False
    assert manifest["outputs_diagnostic_only"] is True
    assert manifest["research_outputs_remain_non_promotable"] is True
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True


def test_multasset_adapter_comparison_and_invariants_pass() -> None:
    comparison = json.loads((EVIDENCE / "adapter_vs_reference_comparison_report.json").read_text(encoding="utf-8"))
    invariant = json.loads((EVIDENCE / "exposure_invariant_report.json").read_text(encoding="utf-8"))

    assert comparison["comparison_performed"] is True
    assert comparison["comparison_status"] == "matched"
    assert comparison["max_abs_weight_difference"] == 0.0
    assert comparison["selection_mismatch_count"] == 0
    assert comparison["selection_rows_compared"] > 0
    assert comparison["rebalance_dates_matched"] is True
    assert comparison["turnover_dates_matched"] is True
    assert comparison["max_abs_daily_return_difference"] == 0.0
    assert comparison["max_abs_equity_difference"] == 0.0
    assert comparison["max_abs_turnover_difference"] == 0.0
    assert comparison["bt_security_weight_export_status"] == "mismatch"
    assert comparison["bt_security_weight_max_abs_difference"] > 0.0

    assert invariant["exposure_invariant_checked"] is True
    assert invariant["exposure_invariant_passed"] is True
    assert invariant["max_daily_exposure"] <= 1.000001
    assert invariant["max_daily_weight_sum"] <= 1.000001
    assert invariant["negative_weight_violation_count"] == 0
    assert invariant["nan_weight_count"] == 0
    assert invariant["impossible_cash_and_risky_exposure_days"] == 0


def test_multasset_required_outputs_and_cache_symbols_exist() -> None:
    required = [
        "selected_reference_template_report.md",
        "adapter_spec_used.json",
        "adapter_spec_used.md",
        "package_dependency_report.json",
        "package_dependency_report.md",
        "local_cache_symbols_used.csv",
        "local_cache_symbols_used.md",
        "daily_weights.csv",
        "equity_curve_returns.csv",
        "rebalance_turnover_report.csv",
        "rebalance_turnover_report.md",
        "selected_assets_ranking_comparison_report.csv",
        "selected_assets_ranking_comparison_report.md",
        "adapter_vs_reference_comparison_report.json",
        "adapter_vs_reference_comparison_report.md",
        "exposure_invariant_report.json",
        "exposure_invariant_report.md",
        "guardrail_checklist.json",
        "bt_adapter_multasset_control_poc_summary.md",
        "bt_adapter_multasset_control_poc_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    cache = pd.read_csv(EVIDENCE / "local_cache_symbols_used.csv")
    expected = {"SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "PDBC", "COMT", "BIL"}
    assert expected == set(cache["symbol"])
    assert (cache["status"] == "cache_ready").all()

    weights = pd.read_csv(EVIDENCE / "daily_weights.csv")
    equity = pd.read_csv(EVIDENCE / "equity_curve_returns.csv")
    selections = pd.read_csv(EVIDENCE / "selected_assets_ranking_comparison_report.csv")
    assert not weights.empty
    assert not equity.empty
    assert not selections.empty
    assert (selections["selected_assets_match"].astype(str).str.lower() == "true").all()


def test_no_forbidden_strategy_libraries_installed_by_multasset_poc() -> None:
    forbidden_modules = ["vectorbt", "backtesting", "backtrader", "qstrader", "pandas_ta", "ta"]
    for module in forbidden_modules:
        assert importlib.util.find_spec(module) is None, module

