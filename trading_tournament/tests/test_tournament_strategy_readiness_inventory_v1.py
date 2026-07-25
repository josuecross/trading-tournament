from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from strategy_lab.research_os.research import tournament_strategy_readiness_inventory_v1 as inventory


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = (
    ROOT / "evidence" / "tournament_status" / "tournament_strategy_readiness_inventory_v1" / "latest"
)

REQUIRED_FILES = {
    "report_scope_and_definitions.yaml",
    "source_inventory.csv",
    "exact_strategy_inventory.csv",
    "family_inventory.csv",
    "status_reconciliation.csv",
    "passed_strategy_results.csv",
    "paper_demo_eligible_strategies.csv",
    "active_paper_demo_observations.csv",
    "active_observation_operational_status.csv",
    "benchmark_and_reference_inventory.csv",
    "closed_and_deferred_inventory.csv",
    "recent_fast_lane_results.csv",
    "tournament_funnel_counts.json",
    "tournament_conversion_rates.csv",
    "evidence_path_index.csv",
    "missing_or_conflicting_evidence.csv",
    "consistency_check.json",
    "tournament_strategy_readiness_report.md",
}

PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(name: str) -> dict:
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))


def _run_report() -> dict:
    return inventory.run()


def test_report_writes_required_artifacts_and_expected_outcome() -> None:
    result = _run_report()

    assert result["task_outcome"] == "tournament_readiness_report_complete_with_conflicts"
    assert result["exact_next_action"] == "direction_owner_audit_tournament_strategy_readiness_report_v1"
    for filename in REQUIRED_FILES:
        assert (EVIDENCE_DIR / filename).exists(), filename

    report = (EVIDENCE_DIR / "tournament_strategy_readiness_report.md").read_text(encoding="utf-8")
    for heading in [
        "# Tournament Strategy Readiness Report",
        "## 1. Executive count",
        "## 2. Demo-ready strategies",
        "## 3. Active paper/demo observations",
        "## 4. Strategies that passed exploration but are not demo-ready",
        "## 5. Recent fast-lane results",
        "## 6. Tournament funnel",
        "## 7. Evidence conflicts and missing information",
        "## 8. Audit-ready factual observations",
    ]:
        assert heading in report


def test_demo_ready_requires_explicit_active_or_eligibility_artifact() -> None:
    _run_report()

    exact_rows = _read_csv("exact_strategy_inventory.csv")
    assert all(
        row["paper_demo_eligible"] == "false"
        for row in exact_rows
        if row["current_highest_verified_stage"] == "exploratory_followup_candidate"
    )
    assert all(
        row["paper_demo_eligible"] == "false"
        for row in exact_rows
        if row["current_highest_verified_stage"] == "validation_or_promotion_review_candidate"
    )
    assert all(
        row["paper_demo_eligible"] == "false"
        for row in exact_rows
        if row["current_highest_verified_stage"] == "benchmark_or_reference_only"
    )

    eligible_rows = _read_csv("paper_demo_eligible_strategies.csv")
    assert eligible_rows
    for row in eligible_rows:
        evidence_path = ROOT / row["explicit_eligibility_artifact"]
        assert evidence_path.exists(), row
        assert row["real_money_authorized"] == "false"


def test_active_observations_are_current_config_backed_and_known_expectations_verified() -> None:
    _run_report()

    consistency = _read_json("consistency_check.json")
    assert consistency["active_observation_count"] == 4
    assert consistency["paper_demo_eligible_count"] == 4
    assert consistency["known_active_expectations_verified_from_current_config"] == {
        "active_combo_vm_dsr_equal_weight_v1_benchmark_reference_only": True,
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": True,
        "paper_forward_vm_quality_lowvol_proxy_v1": True,
    }

    active_ids = {row["strategy_id"] for row in _read_csv("active_paper_demo_observations.csv")}
    assert active_ids == {
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    }
    exact_by_id = {row["strategy_id"]: row for row in _read_csv("exact_strategy_inventory.csv")}
    assert exact_by_id["active_combo_vm_dsr_equal_weight_v1"]["current_highest_verified_stage"] == (
        "benchmark_or_reference_only"
    )
    assert exact_by_id["active_combo_vm_dsr_equal_weight_v1"]["paper_demo_eligible"] == "false"


def test_metrics_and_counts_keep_exact_configurations_and_families_separate() -> None:
    _run_report()

    funnel = _read_json("tournament_funnel_counts.json")
    assert "exact_configuration_counts" in funnel
    assert "family_level_counts" in funnel
    assert funnel["exact_configuration_counts"]["paper_demo_active_observations"] == 4
    assert funnel["family_level_counts"]["families_with_paper_demo_active_observations"] == 4

    passed = _read_csv("passed_strategy_results.csv")
    assert passed
    for row in passed:
        supporting_path = ROOT / row["supporting_evidence_path"]
        assert supporting_path.exists(), row

    rates = _read_csv("tournament_conversion_rates.csv")
    assert {row["count_basis"] for row in rates} == {"exact_configuration", "family"}


def test_closed_configs_not_active_and_status_conflicts_are_surfaced() -> None:
    _run_report()

    closed = _read_csv("closed_and_deferred_inventory.csv")
    exact_by_id = {row["strategy_id"]: row for row in _read_csv("exact_strategy_inventory.csv")}
    for row in closed:
        assert exact_by_id[row["strategy_id"]]["paper_demo_active"] == "false"

    conflicts = _read_csv("status_reconciliation.csv")
    conflict_ids = {row["conflict_id"] for row in conflicts}
    assert "active_observation_count_active_yaml_vs_checkpoint_pipeline" in conflict_ids
    assert "strategy_evidence_library_active_rows_absent_from_current_active_config" in conflict_ids
    assert "stale_registry_promotion_like_metadata_not_current_candidate" in conflict_ids


def test_recent_fast_lane_accounting_has_required_rows_without_reruns() -> None:
    _run_report()

    fast_rows = _read_csv("recent_fast_lane_results.csv")
    assert {row["display_name"] for row in fast_rows} == {
        "ADX/DMI",
        "CCI Correction",
        "Larry Connors RSI(2)",
        "Coppock Curve",
        "Parabolic SAR",
        "MACD 12/26/9",
        "Faber GTAA5",
        "Antonacci GEM",
        "VAA-G4",
    }
    assert all(row["evidence_path"] for row in fast_rows)

    consistency = _read_json("consistency_check.json")
    assert consistency["recent_fast_lane_count"] == 9
    assert consistency["all_required_recent_fast_lanes_present"] is True
    assert consistency["backtest_run"] is False
    assert consistency["validation_runner_called"] is False


def test_no_state_mutation_no_broker_write_and_report_is_deterministic() -> None:
    before = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}
    first = _run_report()
    first_bytes = {name: (EVIDENCE_DIR / name).read_bytes() for name in REQUIRED_FILES}

    second = _run_report()
    second_bytes = {name: (EVIDENCE_DIR / name).read_bytes() for name in REQUIRED_FILES}
    after = {path: _sha256(path) for path in PROTECTED_STATE_PATHS if path.exists()}

    assert first["protected_state_unchanged"] is True
    assert second["protected_state_unchanged"] is True
    assert before == after
    assert first_bytes == second_bytes

    consistency = _read_json("consistency_check.json")
    assert consistency["strategy_discovery_run"] is False
    assert consistency["backtest_run"] is False
    assert consistency["validation_runner_called"] is False
    assert consistency["promotion_review_run"] is False
    assert consistency["paper_demo_activation"] is False
    assert consistency["broker_write_endpoint_called"] is False
    assert consistency["broker_orders_submitted"] is False
    assert consistency["registry_cleanup_run"] is False
    assert consistency["real_money_recommendation"] is False
