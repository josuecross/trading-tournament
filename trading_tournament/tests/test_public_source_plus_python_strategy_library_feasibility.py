from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.public_source_plus_python_strategy_library_feasibility import (
    BT_DECISION_FEASIBLE,
    VALID_NEXT_ACTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "evidence"
    / "research_recovery"
    / "public_source_plus_python_strategy_library_feasibility"
    / "latest"
)


def load_manifest() -> dict:
    return json.loads((EVIDENCE / "feasibility_manifest.json").read_text(encoding="utf-8"))


def load_consistency() -> dict:
    return json.loads((EVIDENCE / "feasibility_consistency_check.json").read_text(encoding="utf-8"))


def test_feasibility_packet_guardrails_and_decision() -> None:
    manifest = load_manifest()
    consistency = load_consistency()

    assert manifest["public_source_plus_python_strategy_library_feasibility_only"] is True
    assert manifest["source_layer"] == "quantpedia_style_public_curated_strategy_intake"
    assert manifest["execution_layer_primary_candidate"] == "bt"
    assert manifest["validation_layer"] == "current_tournament_evidence_gates_and_invariants"
    assert manifest["architecture_files_inspected"] is True
    assert manifest["registry_inspected"] is True
    assert manifest["roadmap_inspected"] is True
    assert manifest["research_queue_inspected"] is True
    assert manifest["family_ledger_inspected"] is True
    assert manifest["local_cache_inspected"] is True
    assert manifest["package_availability_checked"] is True
    assert manifest["package_install_attempted"] is False
    assert manifest["bt_feasibility_decision"] == BT_DECISION_FEASIBLE
    assert manifest["candidate_library_comparison_completed"] is True
    assert manifest["thin_adapter_design_created"] is True
    assert manifest["public_source_intake_template_created"] is True
    assert manifest["smallest_future_poc_defined"] is True
    assert manifest["current_evidence_gates_preserved"] is True
    assert manifest["exposure_invariants_remain_project_enforced"] is True
    assert manifest["next_action"] in VALID_NEXT_ACTIONS
    assert consistency["consistency_passed"] is True


def test_no_strategy_backtest_install_scrape_or_execution_paths() -> None:
    manifest = load_manifest()

    assert manifest["external_strategy_code_imported"] is False
    assert manifest["quantpedia_scraped"] is False
    assert manifest["public_site_downloaded"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["strategy_backtest_run"] is False
    assert manifest["current_backtester_replaced"] is False
    assert manifest["new_strategy_discovery_run"] is False
    assert manifest["new_research_batch_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["intraday_data_used"] is False
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
    assert manifest["active_vm_preserved"] is True
    assert manifest["active_dsr_preserved"] is True
    assert manifest["static_all_weather_benchmark_control_only"] is True


def test_required_evidence_files_and_tables_exist() -> None:
    required = [
        "architecture_integration_map.md",
        "public_source_intake_template.md",
        "bt_feasibility_report.md",
        "candidate_library_comparison.csv",
        "candidate_library_comparison.md",
        "package_availability_check.csv",
        "package_availability_check.md",
        "thin_adapter_design.md",
        "smallest_future_poc.md",
        "risks_and_blockers.md",
        "guardrail_checklist.json",
        "feasibility_next_action.md",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename

    packages = pd.read_csv(EVIDENCE / "package_availability_check.csv")
    assert {"bt", "vectorbt", "backtesting", "backtrader", "qstrader", "pandas_ta", "ta"}.issubset(
        set(packages["module_name"])
    )
    assert (packages["install_attempted"].astype(str).str.lower() == "false").all()

    libraries = pd.read_csv(EVIDENCE / "candidate_library_comparison.csv")
    assert "bt" in set(libraries["library"])
    assert "pandas-ta / ta" in set(libraries["library"])


def test_adapter_design_preserves_project_validation_layer() -> None:
    adapter = (EVIDENCE / "thin_adapter_design.md").read_text(encoding="utf-8")
    intake = (EVIDENCE / "public_source_intake_template.md").read_text(encoding="utf-8")
    risks = (EVIDENCE / "risks_and_blockers.md").read_text(encoding="utf-8")

    assert "Daily target weights" in adapter
    assert "Project recomputes or validates exposure invariants" in adapter
    assert "candidate_exhaustive" in adapter
    assert "Source URL or citation" in intake
    assert "Evidence-gate reminder" in intake
    assert "Hidden lookahead risk" in risks
    assert "No public source or Python library" in risks
