from __future__ import annotations

import csv
import json

from strategy_lab.research_os.research import faa_psar_trade_management_overlay_batch_v1 as task


def rows(name: str) -> list[dict[str, str]]:
    with (task.OUTPUT_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_compatibility_matrix_is_complete_and_performance_free() -> None:
    matrix = task.compatibility_rows()
    assert len(matrix) == 14
    assert {row["base_strategy_id"] for row in matrix} == {task.FAA_ID, task.PSAR_ID}
    assert all(row["performance_fields_used_for_classification"] is False for row in matrix)
    assert sum(
        row["classification"] == "compatible" and row["overlay_id"] != "IDENTITY"
        for row in matrix
    ) == 1


def test_only_psar_outer_rebalance_band_is_selected() -> None:
    selected = task.selected_trial_rows()
    assert len(selected) == 1
    assert selected[0]["base_strategy_id"] == task.PSAR_ID
    assert selected[0]["overlay_id"] == task.REBALANCE_ID
    assert selected[0]["parent_trial_id"] == task.PSAR_PARENT
    assert selected[0]["adaptation_label"] == "trade_management_overlay_variant"
    assert selected[0]["optimization_performed"] is False


def test_existing_rebalance_band_class_drives_adapter() -> None:
    overlay = task.RebalanceBandOverlay(**task.REBALANCE_CONFIG)
    overlay.bind(
        run_id="test",
        base_strategy_id=task.PSAR_ID,
        base_strategy_hash="hash",
        data={},
        indexed_data={},
        calendar=[],
        config=task._portfolio_config(("REFERENCE", "SLEEVE"), task.PSAR_ID),
    )
    managed, suppressed = task.apply_existing_rebalance_band(
        overlay,
        task.PSAR_START,
        task.np.array([0.805, 0.195]),
        task.np.array([0.8, 0.2]),
        ("REFERENCE", "SLEEVE"),
        task.PSAR_ID,
    )
    assert suppressed is True
    assert task.np.array_equal(managed, task.np.array([0.805, 0.195]))
    assert set(overlay.events_frame()["reason_code"]) >= {"below_weight_band"}


def test_serial_evidence_has_exact_identity_reproduction() -> None:
    reproduction = rows("identity_reproduction_check.csv")
    assert reproduction
    assert {row["base_strategy_id"] for row in reproduction} == {task.FAA_ID, task.PSAR_ID}
    assert all(row["pass"] == "true" for row in reproduction)
    assert max(abs(float(row["difference"])) for row in reproduction) <= task.REPRODUCTION_TOLERANCE


def test_trial_and_entity_counts_remain_separate() -> None:
    trials = rows("trial_ledger.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(trials) == 1
    assert len(benchmarks) == 2
    assert all(row["entity_type"] == "benchmark_reference" for row in benchmarks)
    assert len(process) == 1 and process[0]["entity_type"] == "process_task"
    assert not (task.OUTPUT_DIR / "strategy_cards.csv").exists()


def test_all_required_outputs_and_consistency_pass() -> None:
    assert {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["deterministic_rerun_passed"] is True
    assert consistency["protected_state_cache_observation_and_prior_evidence_unchanged"] is True
    assert consistency["paper_demo_observation_changed"] is False
    assert consistency["provider_access_performed"] is False
    assert consistency["broker_account_order_or_real_money_action"] is False


def test_no_base_rules_or_routes_changed() -> None:
    lineage = rows("base_strategy_lineage.csv")
    assert len(lineage) == 2
    assert all(row["base_rules_changed"] == "false" for row in lineage)
    assert all(row["base_observation_changed"] == "false" for row in lineage)
    trial = rows("trial_ledger.csv")[0]
    assert trial["base_strategy_rule_changed"] == "false"
    assert trial["base_route_changed"] == "false"


def test_overlay_results_keep_costs_and_periods_visible() -> None:
    results = rows("all_overlay_results.csv")
    assert {(row["base_strategy_id"], row["overlay_id"]) for row in results} == {
        (task.FAA_ID, "IDENTITY"),
        (task.PSAR_ID, "IDENTITY"),
        (task.PSAR_ID, task.REBALANCE_ID),
    }
    assert {float(row["cost_bps_one_way"]) for row in results} == set(task.COSTS)
    assert all(row["invariant_pass"] == "true" for row in results)
    assert len(rows("chronological_quarter_results.csv")) == 12
    assert rows("calendar_year_results.csv")


def test_outcome_and_next_action_are_standardized() -> None:
    outcomes = rows("outcome_summary.csv")
    allowed = {
        "overlay_exploratory_followup_candidate",
        "overlay_closed_exploration",
        "overlay_blocked_feasibility",
        "overlay_incompatible",
    }
    assert outcomes and all(row["outcome"] in allowed for row in outcomes)
    next_action = rows("next_actions.csv")[0]["exact_next_action"]
    assert next_action in {
        "direction_owner_review_faa_psar_overlay_candidates_v1",
        "direction_owner_review_after_two_factories_and_overlay_batch_v1",
        "direction_owner_review_trade_management_overlay_block_v1",
    }
