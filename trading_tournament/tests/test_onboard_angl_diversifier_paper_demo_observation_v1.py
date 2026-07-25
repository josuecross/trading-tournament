from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import onboard_angl_diversifier_paper_demo_observation_v1 as onboard


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "paper_demo" / "onboard_angl_diversifier_paper_demo_observation_v1" / "latest"
CORRECTION_EVIDENCE = ROOT / "evidence" / "correction" / "correct_angl_forward_boundary_and_data_freshness_v1" / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
OBSERVATION_ID = "paper_forward_angl_20pct_diversifier_v1"
PARENT_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
REFERENCE_ID = "frozen_current_active_vm_dsr_usci_combo"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    if not (EVIDENCE / "consistency_check.json").exists():
        onboard.run()


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def corrected_observation_state() -> tuple[str, str] | None:
    path = CORRECTION_EVIDENCE / "consistency_check.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("observation_id") != OBSERVATION_ID:
        return None
    return str(payload["observation_stage"]), str(payload["observation_outcome"])


def test_required_artifacts_and_manifest_scope() -> None:
    required = {
        "onboarding_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "paper_demo_observations.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "operational_preflight.csv",
        "historical_reconciliation.csv",
        "initial_target_weights.csv",
        "initial_virtual_positions.csv",
        "initial_virtual_trades.csv",
        "initial_virtual_nav.csv",
        "control_virtual_nav.csv",
        "data_freshness.csv",
        "state_change_manifest.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "consistency_check.json",
        "onboarding_report.md",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []
    manifest = read_yaml("onboarding_manifest.yaml")
    assert manifest["onboarding_id"] == "onboard_angl_diversifier_paper_demo_observation_v1"
    assert manifest["mode"] == "active-direction-execution"
    assert manifest["lane"] == "paper_demo_observation"
    assert manifest["task_stage"] == "paper-demo-eligibility"
    assert manifest["strategy_id"] == STRATEGY_ID
    assert manifest["observation_id"] == OBSERVATION_ID
    assert manifest["route"] == "diversifier_only"
    assert manifest["canonical_portfolio"]["target_reference_weight"] == 0.8
    assert manifest["canonical_portfolio"]["target_sleeve_weight"] == 0.2
    assert manifest["canonical_portfolio"]["cost_assumption_bps"] == 5.0
    assert manifest["funnel_counts"]["eligible_strategy_configurations"] == 1
    assert manifest["funnel_counts"]["new_experiment_trials"] == 0


def test_strategy_observation_trial_benchmark_and_process_entities_are_separate() -> None:
    strategy = read_csv("strategy_cards.csv")
    trial = read_csv("trial_ledger.csv")
    observation = read_csv("paper_demo_observations.csv")
    benchmarks = read_csv("benchmark_reference_log.csv")
    process = read_csv("process_task_log.csv")
    assert len(strategy) == 1
    assert strategy[0]["entity_type"] == "strategy_configuration"
    assert strategy[0]["strategy_id"] == STRATEGY_ID
    assert strategy[0]["stage"] == "paper_demo_eligible"
    assert strategy[0]["outcome"] == "paper_demo_eligible"
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["standalone_100pct_angl_observation_approved"] == "false"
    assert len(trial) == 1
    assert trial[0]["entity_type"] == "experiment_trial_lineage_read_only"
    assert trial[0]["trial_id"] == PARENT_TRIAL_ID
    assert trial[0]["new_experiment_trial_created"] == "false"
    assert len(observation) == 1
    assert observation[0]["entity_type"] == "paper_demo_observation"
    assert observation[0]["observation_id"] == OBSERVATION_ID
    assert observation[0]["parent_strategy_id"] == STRATEGY_ID
    assert observation[0]["parent_trial_id"] == PARENT_TRIAL_ID
    assert observation[0]["reference_portfolio_id"] == REFERENCE_ID
    assert observation[0]["candidate_sleeve_id"] == "ANGL"
    assert observation[0]["rebalance_frequency"] == "monthly"
    assert observation[0]["execution_convention"] == "next_available_session_close"
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert {row["counted_as_strategy"] for row in benchmarks} == {"false"}
    assert {row["counted_as_trial"] for row in benchmarks} == {"false"}
    assert process == [
        {
            "task_id": "onboard_angl_diversifier_paper_demo_observation_v1",
            "entity_type": "process_task",
            "stage": observation[0]["stage"],
            "outcome": observation[0]["outcome"],
            "exact_next_action": observation[0]["next_action"],
            "strategy_counted": "false",
            "trial_counted": "false",
        }
    ]


def test_operational_preflight_and_historical_reconciliation_pass() -> None:
    preflight = read_csv("operational_preflight.csv")
    assert {row["check_id"] for row in preflight} == {
        "local_angl_hyg_jnk_data_loads",
        "frozen_reference_current_virtual_nav_available",
        "latest_common_completed_session",
        "historical_methodology_reconciliation",
        "weight_sum_target_and_pretrade",
        "exposure_never_exceeds_1",
        "turnover_and_cost_nonnegative",
        "observation_runner_persistence_contract",
        "idempotent_observation_record",
        "no_broker_account_or_order_api_invoked",
    }
    assert {row["status"] for row in preflight} == {"pass"}
    reconciliation = read_csv("historical_reconciliation.csv")
    assert len(reconciliation) == 21
    assert {row["label"] for row in reconciliation} == {"historical_reconciliation_only"}
    assert {row["reconciliation_status"] for row in reconciliation} == {"pass"}
    assert all(float(row["absolute_difference"]) <= float(row["tolerance"]) for row in reconciliation)


def test_initial_virtual_snapshot_uses_frozen_80_20_no_broker_orders() -> None:
    targets = {row["component_id"]: float(row["target_weight"]) for row in read_csv("initial_target_weights.csv")}
    assert targets == {REFERENCE_ID: 0.8, "ANGL": 0.2}
    positions = read_csv("initial_virtual_positions.csv")
    assert {row["component_id"] for row in positions} == {REFERENCE_ID, "ANGL"}
    assert sum(float(row["target_weight"]) for row in positions) == pytest.approx(1.0)
    assert {row["broker_order_submitted"] for row in positions} == {"false"}
    trades = read_csv("initial_virtual_trades.csv")
    assert {row["component_id"] for row in trades} == {REFERENCE_ID, "ANGL"}
    assert sum(abs(float(row["virtual_trade_weight"])) for row in trades) == pytest.approx(1.0)
    assert {row["broker_order_submitted"] for row in trades} == {"false"}
    nav = read_csv("initial_virtual_nav.csv")[0]
    assert float(nav["pretrade_portfolio_nav"]) == pytest.approx(1.0)
    assert float(nav["one_way_turnover"]) == pytest.approx(0.5)
    assert float(nav["transaction_cost_drag"]) == pytest.approx(0.00025)
    assert float(nav["post_trade_portfolio_nav"]) == pytest.approx(0.99975)
    assert nav["forward_boundary_label"] == "initial_forward_observation_boundary"
    assert nav["reconciliation_status"] == "pass"


def test_control_nav_and_data_freshness_are_brokerless_and_ready() -> None:
    controls = read_csv("control_virtual_nav.csv")
    assert {row["control_id"] for row in controls} == {
        "frozen_reference_100pct",
        "80pct_reference_20pct_HYG",
        "80pct_reference_20pct_monthly_50_50_HYG_JNK",
    }
    assert {row["broker_order_submitted"] for row in controls} == {"false"}
    freshness = read_csv("data_freshness.csv")
    assert {row["symbol"] for row in freshness} == {"ANGL", "HYG", "JNK", REFERENCE_ID}
    assert {row["status"] for row in freshness} == {"ready"}
    assert {row["provider_download"] for row in freshness} == {"false"}


def test_state_changes_are_limited_and_prior_evidence_is_preserved() -> None:
    state = read_csv("state_change_manifest.csv")
    rows = {row["path"]: row for row in state}
    assert rows["strategy_lab/RESEARCH_ROADMAP.md"]["changed"] == "false"
    assert rows["strategy_lab/research_os/research/research_queue.yaml"]["changed"] == "false"
    assert rows["strategy_lab/research_os/family_lineage/family_ledger.yaml"]["changed"] == "false"
    for path in ["strategy_lab/strategy_registry.yaml", "strategy_lab/research_os/operations/active_observations.yaml"]:
        assert rows[path]["permitted_change"] == "true"
        assert rows[path]["action"] in {"added", "already_present"}
    consistency = read_json("consistency_check.json")
    assert consistency["only_permitted_state_changes"] is True
    assert consistency["research_queue_unchanged"] is True
    assert consistency["family_ledger_unchanged"] is True
    assert consistency["roadmap_unchanged"] is True
    assert consistency["prior_evidence_packets_unchanged"] is True


def test_source_of_truth_contains_single_angl_record_and_preserves_existing_active_observations() -> None:
    registry_text = (ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8")
    assert len(re.findall(rf"(?m)^- id: {re.escape(STRATEGY_ID)}$", registry_text)) == 1
    registry = yaml.safe_load(registry_text)
    registry_rows = [row for row in registry["strategies"] if row.get("id") == STRATEGY_ID]
    assert len(registry_rows) == 1
    assert registry_rows[0]["entity_type"] == "strategy_configuration"
    assert registry_rows[0]["stage"] == "paper_demo_eligible"
    assert registry_rows[0]["outcome"] == "paper_demo_eligible"
    assert registry_rows[0]["route"] == "diversifier_only"
    assert registry_rows[0]["paper_orders"] is False
    active_text = (ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml").read_text(encoding="utf-8")
    assert len(re.findall(rf"(?m)^- observation_id: {re.escape(OBSERVATION_ID)}$", active_text)) == 1
    active = yaml.safe_load(active_text)
    observation_rows = [row for row in active["active_observations"] if row.get("observation_id") == OBSERVATION_ID]
    assert len(observation_rows) == 1
    assert observation_rows[0]["entity_type"] == "paper_demo_observation"
    corrected = corrected_observation_state()
    expected_stage, expected_outcome = corrected if corrected is not None else ("paper_demo_active", "paper_demo_active")
    assert observation_rows[0]["stage"] == expected_stage
    assert observation_rows[0]["outcome"] == expected_outcome
    existing_ids = {row.get("strategy_id") for row in active["active_observations"]}
    assert {
        "paper_forward_vm_quality_lowvol_proxy_v1",
        "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
        "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1",
        "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1",
    }.issubset(existing_ids)


def test_consistency_flags_exclude_forbidden_work_and_record_next_action() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["preflight_passed"] is True
    assert consistency["new_experiment_trials_created"] == 0
    assert consistency["broker_order_submitted"] is False
    assert consistency["paper_order_submitted"] is False
    assert consistency["live_order_submitted"] is False
    assert consistency["real_money_action"] is False
    for key in [
        "new_validation_or_robustness_test",
        "parameter_change",
        "instrument_substitution",
        "source_research_or_completion",
        "benchmark_correction",
        "universe_expansion",
        "trade_management_overlay_testing",
        "performance_based_timeframe_selection",
        "backfilled_forward_performance_claim",
        "live_or_paper_broker_orders",
        "account_inspection",
        "real_money_action",
        "broad_registry_cleanup",
        "dashboard_or_framework_rebuild",
    ]:
        assert consistency[key] is False
    assert consistency["exact_next_action"] == "include_angl_in_next_paper_demo_operational_review_v1"
    assert read_csv("next_actions.csv")[0]["exact_next_action"] == "include_angl_in_next_paper_demo_operational_review_v1"
