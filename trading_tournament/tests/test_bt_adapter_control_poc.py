from __future__ import annotations

import json
import importlib.util
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.external_adapters.bt_adapter import (
    BtAdapterSpec,
    invariant_summary,
    reference_spy200d_weights,
)
from strategy_lab.research_os.research.bt_adapter_control_poc import (
    FINAL_DECISION_BLOCKED,
    NEXT_ACTION_INSTALL,
    VALID_FINAL_DECISIONS,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / "bt_adapter_control_poc" / "latest"


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "bt_adapter_control_poc_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "bt_adapter_control_poc_consistency_check.json").read_text(encoding="utf-8"))


def test_poc_manifest_guardrails_and_dependency_scope() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["bt_adapter_control_poc"] is True
    assert manifest["bt_adapter_control_poc_only"] is True
    assert manifest["control_style_strategy_only"] is True
    assert manifest["dependency_management_inspected"] is True
    assert manifest["dependency_file_modified"] is True
    assert manifest["dependency_added_to_requirements"] is True
    assert manifest["package_install_attempted"] is True
    assert manifest["only_bt_dependency_considered"] is True
    assert manifest["forbidden_packages_added"] is False
    assert manifest["bt_package_available"] is True
    assert manifest["adapter_execution_attempted"] is True
    assert manifest["bt_algo_composition_run"] is True
    assert manifest["reference_comparison_performed"] is True
    assert manifest["adapter_outputs_created"] is True
    assert manifest["exposure_invariant_checked"] is True
    assert manifest["exposure_invariant_passed"] is True
    assert manifest["final_adapter_decision"] in VALID_FINAL_DECISIONS
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_no_strategy_discovery_promotion_paper_broker_or_performance_evidence() -> None:
    manifest = load_manifest()

    assert manifest["strategy_implemented"] is False
    assert manifest["public_strategy_implemented"] is False
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


def test_dependency_blocked_state_is_explicit_when_bt_is_missing() -> None:
    manifest = load_manifest()
    if manifest["bt_package_available"]:
        assert manifest["adapter_execution_attempted"] is True
        assert manifest["bt_algo_composition_run"] is True
        assert manifest["final_adapter_decision"] != FINAL_DECISION_BLOCKED
    else:
        assert manifest["final_adapter_decision"] == FINAL_DECISION_BLOCKED
        assert manifest["next_action"] == NEXT_ACTION_INSTALL
        assert manifest["adapter_execution_attempted"] is False
        assert manifest["bt_algo_composition_run"] is False
        assert manifest["reference_comparison_performed"] is False
        assert manifest["adapter_outputs_created"] is False


def test_adapter_reference_comparison_and_invariants_pass() -> None:
    comparison = json.loads((EVIDENCE / "adapter_vs_reference_comparison_report.json").read_text(encoding="utf-8"))
    invariant = json.loads((EVIDENCE / "exposure_invariant_report.json").read_text(encoding="utf-8"))

    assert comparison["comparison_performed"] is True
    assert comparison["comparison_status"] == "matched"
    assert comparison["max_abs_weight_difference"] == 0.0
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


def test_required_evidence_files_exist() -> None:
    required = [
        "package_dependency_report.md",
        "package_dependency_report.json",
        "adapter_spec_used.json",
        "adapter_spec_used.md",
        "local_cache_symbols_used.csv",
        "local_cache_symbols_used.md",
        "bt_package_version.md",
        "daily_weights.csv",
        "equity_curve_returns.csv",
        "rebalance_turnover_report.csv",
        "rebalance_turnover_report.md",
        "adapter_vs_reference_comparison_report.json",
        "adapter_vs_reference_comparison_report.md",
        "exposure_invariant_report.json",
        "exposure_invariant_report.md",
        "guardrail_checklist.json",
        "bt_adapter_control_poc_summary.md",
        "bt_adapter_control_poc_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    dep_report = json.loads((EVIDENCE / "package_dependency_report.json").read_text(encoding="utf-8"))
    assert dep_report["package"] == "bt"
    assert dep_report["install_attempted"] is True
    assert dep_report["dependency_file_modified"] is True
    assert "pip install bt" in (EVIDENCE / "package_dependency_report.md").read_text(encoding="utf-8")


def test_no_forbidden_strategy_libraries_installed_by_poc() -> None:
    forbidden_modules = ["vectorbt", "backtesting", "backtrader", "qstrader", "pandas_ta", "ta"]
    for module in forbidden_modules:
        assert importlib.util.find_spec(module) is None, module


def test_reference_spy200d_control_weights_are_deterministic_and_bounded() -> None:
    spec = BtAdapterSpec()
    dates = pd.bdate_range("2020-01-01", periods=320)
    rising = pd.DataFrame({"SPY": range(100, 420), "BIL": [100.0] * 320}, index=dates, dtype=float)
    falling = pd.DataFrame({"SPY": range(420, 100, -1), "BIL": [100.0] * 320}, index=dates, dtype=float)

    rising_weights = reference_spy200d_weights(rising, spec)
    falling_weights = reference_spy200d_weights(falling, spec)

    assert float(rising_weights.iloc[-1]["SPY"]) == 1.0
    assert float(rising_weights.iloc[-1]["BIL"]) == 0.0
    assert float(falling_weights.iloc[-1]["SPY"]) == 0.0
    assert float(falling_weights.iloc[-1]["BIL"]) == 1.0
    assert invariant_summary(rising_weights)["exposure_invariant_passed"] is True
    assert invariant_summary(falling_weights)["exposure_invariant_passed"] is True
