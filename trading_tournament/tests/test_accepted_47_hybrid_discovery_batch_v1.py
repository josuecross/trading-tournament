from __future__ import annotations

import json

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import accepted_47_hybrid_discovery_batch_v1 as batch


def test_frozen_work_package_scope_and_symbols() -> None:
    assert batch.EXTERNAL_STRATEGY_ID == "bilello_gayed_beta_rotation_spy_xlu_4w_v1"
    assert batch.EXTERNAL_TRIAL_ID == "accepted47_hybrid_v1__bilello_gayed_beta_rotation__canonical"
    assert batch.INTERNAL_ARCHITECTURE_ID == "standardized_downside_shock_forward_recovery_selection"
    assert len(batch.INTERNAL_CONFIGS) == 4
    assert 1 + len(batch.INTERNAL_CONFIGS) == 5
    assert set(batch.REQUIRED_SYMBOLS) == {
        "SPY", "XLU", "QQQ", "IWM", "EFA", "EEM", "HYG", "LQD", "TLT", "TIP", "GLD", "DBC", "IYR", "BIL"
    }
    assert "IEF" not in batch.REQUIRED_SYMBOLS
    assert "XLK" not in batch.REQUIRED_SYMBOLS


def test_beta_rotation_equality_and_direction_contract() -> None:
    assert batch.beta_rotation_target(0.01, "SPY") == "XLU"
    assert batch.beta_rotation_target(-0.01, "XLU") == "SPY"
    assert batch.beta_rotation_target(0.0, "SPY") == "SPY"
    assert batch.beta_rotation_target(0.0, "XLU") == "XLU"


def test_duplicate_preflight_preserves_distinct_mechanisms() -> None:
    rows = batch.duplicate_preflight_rows()
    assert [row["work_package_id"] for row in rows] == ["external", "internal"]
    assert all(row["preflight_status"] == "pass" for row in rows)
    assert all(row["preperformance_complete"] for row in rows)
    external = rows[0]
    internal = rows[1]
    assert "generic equity/cash trend timing" in external["compared_against"]
    assert external["broad_family_similarity_only"] is True
    assert "mean forward recovery after own-asset standardized downside shocks" in internal["distinctive_mechanism"]


def test_stale_robustness_source_of_truth_reconciliation() -> None:
    rows = batch.stale_robustness_source_of_truth_rows()
    assert len(rows) == 2
    assert {row["strategy_id"] for row in rows} == {
        "varadi_minimum_correlation_8etf_60d_weekly_v1",
        "schwoerer_hyg_ema100_spy_bil_v1",
    }
    assert all(row["old_contract_outcome"] == "robustness_mixed" for row in rows)
    assert all(row["old_contract_failure_reason"] == "concentration_risk" for row in rows)
    assert all(
        row["old_contract_packet_classification"]
        == "historical_generic_robustness_evidence_superseded_for_promotion_decision"
        for row in rows
    )
    assert all(row["authoritative_current_outcome"] == "robustness_positive" for row in rows)
    assert all(row["lifecycle_change_required"] is False for row in rows)
    assert all(row["rerun_required"] is False for row in rows)


def test_internal_shock_scoring_uses_complete_recovery_only() -> None:
    index = pd.bdate_range("2024-01-01", periods=40)
    prices = pd.DataFrame(index=index)
    for symbol in batch.INTERNAL_COLUMNS:
        prices[symbol] = np.linspace(100.0, 110.0, len(index))
    prices.loc[index[[8, 12, 16, 20, 24, 28, 32]], "SPY"] *= 0.80
    config = batch.InternalConfig("T", 35, 3, "s", "t")
    scores, controls, rows = batch.shock_recovery_scores(prices, index[-1], config)
    spy_rows = [row for row in rows if row["asset"] == "SPY"]
    assert spy_rows[0]["complete_shock_recovery_count"] >= 5
    assert "SPY" in scores
    assert "SPY" in controls
    assert all(row["uses_future_after_formation"] is False for row in rows)


def test_selected_top3_target_uses_bil_for_unused_slots() -> None:
    target = batch.selected_top3_target(batch.INTERNAL_COLUMNS, ["SPY", "QQQ"])
    assert np.isclose(target["SPY"], 1.0 / 3.0)
    assert np.isclose(target["QQQ"], 1.0 / 3.0)
    assert np.isclose(target["BIL"], 1.0 / 3.0)
    assert np.isclose(sum(target.values()), 1.0)


def test_frozen_winner_rule_uses_drawdown_then_turnover_then_trial_id() -> None:
    results: dict[str, dict[str, object]] = {}
    specs = [
        (batch.INTERNAL_CONFIGS[0], 0.80, -0.20, 4.0),
        (batch.INTERNAL_CONFIGS[1], 0.795, -0.18, 5.0),
        (batch.INTERNAL_CONFIGS[2], 0.795, -0.18, 3.0),
    ]
    for config, sharpe, drawdown, turnover in specs:
        results[config.trial_id] = {
            "config": config,
            "selection_vector": {"selection_eligible": True},
            "selection_metrics": {
                ("candidate", batch.PRIMARY_COST): {
                    "sharpe_ratio": sharpe,
                    "maximum_drawdown": drawdown,
                    "annualized_turnover": turnover,
                }
            },
            "selected_winner": False,
            "outcome": "selection_eligible",
            "failure_reason": "",
            "decision_reason": "",
        }
    batch.freeze_internal_winner(results)
    winners = [result for result in results.values() if result["selected_winner"]]
    assert len(winners) == 1
    assert winners[0]["config"].trial_id == batch.INTERNAL_CONFIGS[2].trial_id
    assert all(
        result["outcome"] == "closed_optimization"
        and result["failure_reason"] == "not_selected_by_frozen_rule"
        for result in results.values()
        if not result["selected_winner"]
    )


def test_failure_precedence_and_candidate_routing() -> None:
    assert batch.primary_failure_reason({"cagr_positive_5bps": False}) == "weak_return"
    assert batch.primary_failure_reason(
        {"cagr_positive_5bps": True, "invariants_pass_5bps": False}
    ) == "methodology_failure"
    assert batch.primary_failure_reason(
        {
            "cagr_positive_5bps": True,
            "invariants_pass_5bps": True,
            "named_control_not_dominating_5bps": False,
        }
    ) == "weak_vs_primary_control"
    external = {"outcome": "exploratory_followup_candidate", "executed": True, "blocked": False}
    internal = {"x": {"outcome": "closed_optimization"}}
    assert batch.batch_outcome(external, internal) == (
        "hybrid_batch_followup_found",
        batch.FOLLOWUP_NEXT_ACTION,
    )


def test_run_outputs_required_packet_and_entity_counts() -> None:
    result = batch.run()
    assert result["batch_id"] == batch.TASK_ID
    assert result["consistency_overall_pass"] is True
    output = batch.OUTPUT_DIR
    assert {path.name for path in output.iterdir() if path.is_file()} == batch.REQUIRED_OUTPUT_FILES
    counts = json.loads((output / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["source_library_records"] == 1
    assert counts["external_canonical_trials"] == 1
    assert counts["internal_canonical_trials"] == 4
    assert counts["total_canonical_trials"] == 5
    assert counts["source_of_truth_reconciliation_records"] == 1
    assert counts["new_mca_hyg_strategy_configurations"] == 0
    assert counts["new_mca_hyg_robustness_trials"] == 0
    assert counts["mca_hyg_lifecycle_changes"] == 0
    assert counts["robustness_trials_created"] == 0
    assert counts["validation_trials_created"] == 0
    assert counts["handoff_packets"] == 0
    assert counts["observations"] == 0


def test_manifest_and_intake_materialization_contract() -> None:
    manifest = yaml.safe_load((batch.OUTPUT_DIR / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["intake_id"] == batch.INTAKE_ID
    assert manifest["canonical_trial_count"] == 5
    assert manifest["stale_robustness_reconciliation"]["record_count"] == 1
    assert manifest["stale_robustness_reconciliation"]["strategy_row_count"] == 2
    assert manifest["stale_robustness_reconciliation"]["new_robustness_trials"] == 0
    assert manifest["stale_robustness_reconciliation"]["lifecycle_changes"] == 0
    assert manifest["data_boundary"]["network_access"] is False
    assert manifest["data_boundary"]["provider_access"] is False
    assert manifest["data_boundary"]["cache_modification"] is False
    assert (batch.INTAKE_DIR / "intake_manifest.yaml").is_file()
    intake = yaml.safe_load((batch.INTAKE_DIR / "intake_manifest.yaml").read_text(encoding="utf-8"))
    assert intake["work_package_count"] == 2
    assert intake["source_library_record_count"] == 1


def test_nonwinner_evaluation_access_and_routing() -> None:
    output = batch.OUTPUT_DIR
    trial_rows = list(pd.read_csv(output / "trial_ledger.csv").to_dict("records"))
    eval_rows = list(pd.read_csv(output / "evaluation_segment_results.csv").to_dict("records"))
    selected_trials = {row["trial_id"] for row in trial_rows if str(row["evaluation_evaluated"]).lower() == "true"}
    eval_trials = {row["trial_id"] for row in eval_rows}
    assert eval_trials <= selected_trials
    next_actions = pd.read_csv(output / "next_actions.csv")
    assert next_actions["execute_in_this_task"].astype(str).str.lower().eq("false").all()
    outcome = pd.read_csv(output / "outcome_summary.csv")
    process = outcome[outcome["entity_type"] == "process_task"].iloc[0]
    if process["batch_outcome"] == "hybrid_batch_followup_found":
        assert process["batch_next_action"] == batch.FOLLOWUP_NEXT_ACTION
    else:
        assert process["batch_next_action"] in {batch.NO_FOLLOWUP_NEXT_ACTION, batch.BLOCK_NEXT_ACTION}


def test_benchmark_entities_and_cost_reconciliation() -> None:
    benchmark_rows = pd.read_csv(batch.OUTPUT_DIR / "benchmark_reference_log.csv")
    assert benchmark_rows["entity_type"].eq("benchmark_reference").all()
    assert benchmark_rows["counted_as_strategy"].astype(str).str.lower().eq("false").all()
    assert benchmark_rows["counted_as_trial"].astype(str).str.lower().eq("false").all()
    cost_rows = pd.read_csv(batch.OUTPUT_DIR / "turnover_cost_reconciliation.csv")
    zero_cost = cost_rows[cost_rows["cost_bps_one_way"] == 0]
    assert np.isclose(zero_cost["transaction_cost_drag"].to_numpy(dtype=float), 0.0).all()
    assert cost_rows["cost_applied_once_to_one_way_turnover"].astype(str).str.lower().eq("true").all()
    assert cost_rows["turnover_is_drift_adjusted"].astype(str).str.lower().eq("true").all()


def test_deterministic_rerun_hash_stable() -> None:
    first = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    result = batch.run()
    second = json.loads((batch.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["consistency_overall_pass"] is True
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
