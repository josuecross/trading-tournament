from __future__ import annotations

import csv
import json
import math

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import accepted_47_targeted_internal_technical_batch_v1 as subject


OUTPUT = ROOT / "evidence" / "research_recovery" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exact_frozen_architecture_and_grid_scope() -> None:
    assert len(subject.ARCHITECTURES) == 3
    assert len(subject.CONFIGS) == 12
    assert all(len(subject.configs_for_architecture(arch.architecture_code)) == 4 for arch in subject.ARCHITECTURES)
    assert len({config.strategy_id for config in subject.CONFIGS}) == 12
    assert len({config.trial_id for config in subject.CONFIGS}) == 12
    assert [config.configuration_code for config in subject.CONFIGS] == [
        "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4",
    ]


def test_duplicate_preflight_rejects_b_before_performance() -> None:
    duplicate_rows = subject.duplicate_preflight_rows()
    by_code = {row["architecture_code"]: row for row in duplicate_rows}
    assert by_code["A"]["preflight_status"] == "pass"
    assert by_code["B"]["preflight_status"] == "duplicate_or_redundant"
    assert by_code["B"]["execute_architecture_trials"] is False
    assert by_code["B"]["matched_existing_architecture_id"] == "factory_v2_sector_overnight_intraday_differential"
    assert by_code["C"]["preflight_status"] == "pass"


def test_signal_formula_fixtures_and_following_session_execution() -> None:
    frames = subject.load_frames()
    arch_a = subject.architecture_by_code("A")
    split_a = subject.architecture_split(frames, arch_a)
    config_a = subject.configs_for_architecture("A")[0]
    prepared_a = subject.build_events_for_config(arch_a, config_a, split_a)
    signal_a, execution_a = split_a.signal_execution_pairs[0]
    assert execution_a == subject.next_session(split_a.prices.index, signal_a)
    assert execution_a in prepared_a["candidate_events"].index
    scores, up_capture, down_capture, counts = subject.capture_scores(
        split_a.prices, arch_a.universe, signal_a, config_a.lookback_sessions
    )
    top = subject.sorted_desc(scores)[0]
    assert counts["upside_count"] >= 10
    assert counts["downside_count"] >= 10
    assert math.isclose(scores[top], up_capture[top] - down_capture[top], abs_tol=1e-14)

    arch_c = subject.architecture_by_code("C")
    split_c = subject.architecture_split(frames, arch_c)
    config_c = subject.configs_for_architecture("C")[0]
    signal_c, execution_c = split_c.signal_execution_pairs[0]
    stability, cv_values, current_rv = subject.volatility_stability_scores(
        split_c.prices, arch_c.universe, signal_c, config_c.lookback_sessions
    )
    top_c = subject.sorted_desc(stability)[0]
    assert execution_c == subject.next_session(split_c.prices.index, signal_c)
    assert math.isclose(stability[top_c], -cv_values[top_c], abs_tol=1e-14)
    assert all(value > 0.0 for value in current_rv.values())


def test_run_outputs_and_entity_reconciliation_are_bounded() -> None:
    result = subject.run()
    assert result["batch_id"] == subject.TASK_ID
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUT_FILES
    counts = json.loads((OUTPUT / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["architectures"] == 3
    assert counts["strategy_configurations"] == 12
    assert counts["canonical_experiment_trials"] == 12
    assert counts["robustness_trials_created"] == 0
    assert counts["validation_trials_created"] == 0
    assert counts["paper_demo_eligibility_records_created"] == 0
    assert counts["observations_created"] == 0
    assert counts["executed_trials"] == 8
    assert counts["duplicate_or_blocked_trials"] == 4


def test_required_csv_contracts_and_nonwinner_evaluation_prohibition() -> None:
    assert len(rows("parameter_grid.csv")) == 12
    assert len(rows("strategy_cards.csv")) == 12
    assert len(rows("trial_ledger.csv")) == 12
    selection = rows("selection_segment_results.csv")
    assert len(selection) == 36
    assert {row["cost_bps_one_way"] for row in selection} == {"0", "5", "10"}
    duplicate_trials = {config.trial_id for config in subject.configs_for_architecture("B")}
    assert all(row["performance_executed"] == "false" for row in selection if row["trial_id"] in duplicate_trials)
    winners = {row["selected_trial_id"] for row in rows("architecture_winner_selection.csv") if row["selected_trial_id"]}
    evaluated = {row["trial_id"] for row in rows("evaluation_segment_results.csv")}
    assert evaluated <= winners
    assert len(evaluated) <= 2


def test_manifest_outcome_next_action_and_consistency() -> None:
    manifest = yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["mode"] == subject.MODE
    assert manifest["source_or_research_lineage"] == subject.SOURCE_LINEAGE
    assert manifest["data_boundary"]["provider_access"] is False
    assert manifest["data_boundary"]["network_access"] is False
    assert manifest["batch_outcome"] == "targeted_internal_batch_partially_blocked"
    assert manifest["exact_next_action"] == subject.BLOCK_NEXT_ACTION
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["checks"]["architecture_b_zero_trials_due_duplicate"] is True
    assert consistency["checks"]["nonwinner_evaluation_access_prohibited"] is True
    assert consistency["checks"]["protected_state_cache_and_prior_evidence_unchanged"] is True


def test_deterministic_rerun_hash_stable() -> None:
    before = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    subject.run()
    after = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    assert after == before


def test_split_boundary_is_reproducible_from_selection_definition() -> None:
    definitions = rows("selection_segment_definition.csv")
    for row in definitions:
        if row["segment_status"] != "executed":
            continue
        count = int(row["valid_rebalance_count"])
        expected_selection = int(math.floor(0.6 * count))
        assert int(row["selection_rebalance_count"]) == expected_selection
        assert int(row["evaluation_rebalance_count"]) == count - expected_selection
        boundary = pd.Timestamp(row["boundary_execution_date"])
        assert pd.Timestamp(row["selection_end"]) < boundary
        assert pd.Timestamp(row["evaluation_start"]) == boundary
